import certifi
import os

os.environ["SSL_CERT_FILE"] = certifi.where() # This was a required workaround on my MacOS system. Might work without

import discord
from discord import app_commands, Embed
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta, time

import database

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Definitions
PETITIONS_CHANNEL_ID = 1462204507269238804 # The channel IDs are already set to #submit-world-petition and #world-votes in the CozyMC discord respectively
VOTES_CHANNEL_ID = 1389992532967948369
VOTING_TIME = time(hour=18, minute=0, tzinfo=datetime.now().astimezone().tzinfo) # Local hardware time

bot = commands.Bot(command_prefix=">", intents=intents)

database.init_db()

# Replaces @everyone and @here with its raw text. Called by "petition()" when creating the embed
def catch_mentions(text: str):
    return text.replace("@everyone", "@\u200beveryone").replace("@here","@\u200bhere")

# A function to create polls in vote channel. Called by the manual "push_petitions()" and the automatic "push_petition_task"
async def push_pending_petitions():
    votes_channel = bot.get_channel(VOTES_CHANNEL_ID)
    petitions = database.get_pending_petitions()
    for i in petitions:
        await votes_channel.send(f"Every petition requires at least 60% approval to pass!\n\n\n**Discussion thread for vote #{i[0]}:** {i[2]}")

        petition_type = "petition" if i[1] == "Other" else i[1]

        # Create Poll
        poll = discord.Poll(question=f"World Vote #{i[0]}: Approve this {petition_type}?", duration=timedelta(hours=72))
        poll.add_answer(text="👍 Yes")
        poll.add_answer(text="👎 No")

        await votes_channel.send(poll=poll)

        database.add_to_voted(i[0])

# Fetches petition status from the database. Called by "get_petition_status", "delete_petition" and "revive_petition"
async def get_status(id):
    petition = database.get_petition(id)
    if petition == None:
        return "Empty"
    elif petition[4] == 0:
        return "Pending"
    elif petition[4] == 1:
        return "Voted"
    elif petition[4] == 2:
        return "Deleted"

@bot.event
async def on_ready():
    if not push_petition_task.is_running(): # This needs to be running in the background to ensure petitions automatically get pushed Friday evening
        push_petition_task.start()
    print(f"{bot.user} is online!")
    await bot.tree.sync()

# Error handling to notify users when they create petitions to fast
@bot.tree.error
async def petition_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            f"Upload failed. Please wait a minute between uploading petitions!",
            ephemeral=True
        )
        return
    raise error

# ----- Create Petition -----
@bot.tree.command()
@app_commands.checks.has_any_role("Voter")
@app_commands.checks.cooldown(rate=1, per=60, key=lambda i: i.user.id) # Each user has a 60s cooldown between uploading petitions
# Fetch petition data
@app_commands.describe(title="Short, descriptive and specific")
@app_commands.describe(location="Exact coordinates, region name, or clear boundaries")
@app_commands.choices(type=[
    app_commands.Choice(name="Rule Change", value="Rule Change"),
    app_commands.Choice(name="Shop Takeover", value="Shop Takeover"),
    app_commands.Choice(name="Shop Expansion", value="Shop Expansion"),
    app_commands.Choice(name="Build Takeover", value="Build Takeover"),
    app_commands.Choice(name="Build Removal", value="Build Removal"),
    app_commands.Choice(name="Exception", value="Exception"),
    app_commands.Choice(name="Reservation", value="Reservation"),
    app_commands.Choice(name="Infrastructure Change", value="Infrastructure Change"),
    app_commands.Choice(name="Other", value="Other")
])
@app_commands.describe(state="What exists now? Who uses it? Why is this an issue?")
@app_commands.describe(proposal="Exactly what would change if this passes")
@app_commands.describe(impact="Who is affected? Positives and tradeoffs")
@app_commands.describe(scope="What this does NOT affect; any boundaries or constraints")
@app_commands.describe(duration="Permanent / Temporary / Trial period, if applicable")
@app_commands.describe(maintenance="Who maintains it? What happens if it's abandoned?")
@app_commands.describe(alternatives="What other solutions have been considered?")
@app_commands.choices(acknowledgement=[
    app_commands.Choice(name="I understand that approval is not guaranteed and that the outcome of this vote is final", value="I understand that approval is not guaranteed and that the outcome of this vote is final")
])
async def petition(
    interaction: discord.Interaction,
    title: str,
    location: str,
    type: str,
    state: str,
    proposal: str,
    impact: str,
    scope: str,
    duration: str,
    maintenance: str,
    alternatives: str,
    acknowledgement: str
):
    await interaction.response.defer(ephemeral=True)
    # Save petition to database
    user_id = interaction.user.id
    petition_id = database.add_petition(type=type)

    # Fetch @user
   user_mention = interaction.user.mention

    # Send petition in petition channel
    petitions_channel = bot.get_channel(PETITIONS_CHANNEL_ID)
    
    embed = Embed(
        title=f"Petition #{petition_id}: {title}",
        description=f"**Submitted by:** {user_mention}"
    )
    embed.add_field(name="Location", value=catch_mentions(location), inline=True)
    embed.add_field(name="Type", value=type, inline=True) # No custom user input
    embed.add_field(name="State", value=catch_mentions(state), inline=False)
    embed.add_field(name="Proposal", value=catch_mentions(proposal), inline=False)
    embed.add_field(name="Impact", value=catch_mentions(impact), inline=False)
    embed.add_field(name="Scope", value=catch_mentions(scope), inline=False)
    embed.add_field(name="Duration", value=catch_mentions(duration), inline=False)
    embed.add_field(name="Maintenance", value=catch_mentions(maintenance), inline=False)
    embed.add_field(name="Alternatives", value=catch_mentions(alternatives), inline=False)
    embed.add_field(name="Acknowledgement", value=acknowledgement, inline=False) # No custom user input

    petition_message = await petitions_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    thread = await petition_message.create_thread(
        name=f"Petition #{petition_id}: {title}",
        reason=f"Discussion thread for petition #{petition_id}"
    )

    database.update_thread_link(thread_link=thread.mention, petition_id=petition_id)
    await interaction.followup.send(f"Petition saved for review. Screenshots can be added in the discussion thread {thread.mention}. Votes will start on Friday!", ephemeral=True)

# ----- Delete Petitions -----
@bot.tree.command()
@app_commands.checks.has_any_role("Moderator", "Admin") # Because of the role check (instead of administrator check), this command is still visible to regular users, but when used by them always results in errors
async def delete_petition(interaction: discord.Interaction, petition_id: int):
    status = await get_status(id=petition_id)
    if status == "Empty":
        await interaction.response.send_message(f"Couldn't delete petition #{petition_id} because it doesn't exist yet!", ephemeral=True)
    elif status == "Pending":
        database.hold_back(petition_id=petition_id)
        await interaction.response.send_message(f"Petition #{petition_id} has been removed from the queue! It will not appear in the next voting round.", ephemeral=True)
    elif status == "Voted":
        await interaction.response.send_message(f"Couldn't delete petition #{petition_id} because it has already been pushed to vote.", ephemeral=True)
    elif status == "Deleted":
        await interaction.response.send_message(f"Petition #{petition_id} has already been deleted!", ephemeral=True)

# ----- Revive Petitions -----
@bot.tree.command()
@app_commands.checks.has_any_role("Moderator", "Admin")
async def revive_petition(interaction: discord.Interaction, petition_id: int):
    status = await get_status(id=petition_id)
    if status == "Empty":
        await interaction.response.send_message(f"Couldn't revive petition #{petition_id} because it doesn't exist yet!", ephemeral=True)
    elif status == "Pending":
        await interaction.response.send_message(f"Petition #{petition_id} is already active!", ephemeral=True)
    elif status == "Voted":
        await interaction.response.send_message(f"Couldn't revive petition #{petition_id} because it has already been pushed to vote.", ephemeral=True)
    elif status == "Deleted":
        await interaction.response.send_message(f"Petition #{petition_id} has been added back to the queue! It will appear in the next voting round.", ephemeral=True)
        database.revive(petition_id=petition_id)

# ----- Push Petitions -----
@bot.tree.command()
@app_commands.checks.has_permissions(administrator=True) # This permission check completely hides the command to any non admin users
async def push_petitions(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    votes_channel = bot.get_channel(VOTES_CHANNEL_ID)
    await push_pending_petitions()
    await interaction.followup.send(f"Petitions now put up for vote in {votes_channel.mention}!", ephemeral=True)

# ----- Check Petition Status -----
@bot.tree.command()
async def get_petition_status(interaction: discord.Interaction, petition_id: int):
    status = await get_status(id=petition_id)
    await interaction.response.send_message(f"Status of petition #{petition_id}: {status}", ephemeral=True)

# ----- Automated Petitions every Friday -----
@tasks.loop(time=VOTING_TIME)
async def push_petition_task():
    if datetime.now().weekday() != 4: # 4 = Friday. Increment or decrement to change weekday
        return
    await push_pending_petitions()

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
