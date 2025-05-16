# Standard library imports
import os
import sqlite3
import logging

# Third-party imports
import discord
from discord.ext import commands
from dotenv import load_dotenv

# --- Constants ---
# D&D 5e spellcasting classes
SPELLCASTING_CLASSES = [
    "bard", "cleric", "druid", "sorcerer", "wizard", "warlock",
    "paladin", "ranger", "artificer"
]

# --- Environment & Logging ---
load_dotenv()
token = os.getenv('DISCORD_TOKEN')
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

# --- Database Setup ---
database = sqlite3.connect('database.db')
cursor = database.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS members (
        discord_id TEXT,
        discord_tag TEXT
    )'''
)

cursor.execute('''
    CREATE TABLE IF NOT EXISTS characters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id TEXT,
        name TEXT,
        class TEXT,
        spellcaster BOOLEAN
    )'''
)

cursor.execute('''
    CREATE TABLE IF NOT EXISTS buildings (
        owner_name TEXT,
        building_type TEXT,
        gold_output INTEGER,
        resource_output INTEGER
    )'''
)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

# --- Events ---
@bot.event
async def on_ready():
    print(f'Logged on as {bot.user.name}!')

@bot.event
async def on_member_join(member):
    await member.send(f"Welcome to the server {member.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    # Check if the user is already in the database
    cursor.execute('SELECT 1 FROM members WHERE discord_id = ?', (str(message.author.id),))
    if cursor.fetchone() is None:
        cursor.execute(
            'INSERT INTO members (discord_id, discord_tag) VALUES (?, ?)',
            (str(message.author.id), str(message.author))
        )
        database.commit()
        print(f"Added {message.author.name} to the database")
    await bot.process_commands(message)

# --- Commands ---
@bot.command()
async def add_character(ctx, name: str, class_name: str):
    cursor.execute('SELECT 1 FROM members WHERE discord_id = ?', (str(ctx.author.id),))
    if cursor.fetchone() is None:
        await ctx.send("You need to register first!")
        return

    cursor.execute('SELECT COUNT(*) FROM characters WHERE discord_id = ?', (str(ctx.author.id),))
    count = cursor.fetchone()[0]
    if count >= 3:
        await ctx.send("You can only have up to 3 characters!")
        return

    is_spellcaster = class_name.lower() in SPELLCASTING_CLASSES

    approval_channel = discord.utils.get(ctx.guild.text_channels, name="character-approvals")
    if not approval_channel:
        await ctx.send("No 'character-approvals' channel found for admin approval.")
        return

    await ctx.send(f"An admin has been asked to approve this character addition in {approval_channel.mention}. Please wait for their response.")

    try:
        approval_msg = await approval_channel.send(
            f"User {ctx.author.mention} wants to add character '{name}' (class: {class_name}, spellcaster: {is_spellcaster}).\n"
            f"Admins: Reply with 'approve' or 'deny' in this channel to approve or deny."
        )

        def approval_check(m):
            return (
                m.channel == approval_channel and
                m.content.lower() in ["approve", "deny"] and
                any(role.permissions.administrator for role in m.author.roles)
            )

        msg = await bot.wait_for('message', check=approval_check, timeout=60)
    except Exception:
        await ctx.send("No admin response. Character addition cancelled.")
        return

    if msg.content.lower() == "approve":
        cursor.execute(
            'INSERT INTO characters (discord_id, name, class, spellcaster) VALUES (?, ?, ?, ?)',
            (str(ctx.author.id), name, class_name, is_spellcaster)
        )
        database.commit()
        await ctx.send(f"Character {name} ({class_name}) added!")
        confirm_msg = await approval_channel.send(f"{msg.author.mention} approved the character '{name}' ({class_name}) for {ctx.author.mention}.")
    else:
        await ctx.send("Character addition denied by admin.")
        confirm_msg = await approval_channel.send(f"{msg.author.mention} denied the character '{name}' ({class_name}) for {ctx.author.mention}.")

    # Delete approval request and admin response after 60 seconds
    import asyncio
    await asyncio.sleep(60)
    try:
        await approval_msg.delete()
        await msg.delete()
        await confirm_msg.delete()
    except Exception:
        pass

@bot.command()
async def test(ctx):
    await ctx.send("Test command works!")
    await ctx.send(f"{ctx.author.mention}")


@bot.command()
async def harvesting(ctx):
    pass

# --- Run Bot ---
bot.run(token, log_handler=handler, log_level=logging.DEBUG)



