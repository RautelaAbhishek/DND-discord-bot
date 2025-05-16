# Imports
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import sqlite3

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8',mode='w')



database = sqlite3.connect('database.db')
cursor = database.cursor()
# Create a table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS members (
        discord_id TEXT,
        discord_tag TEXT
    )'''
)

cursor.execute('''
    CREATE TABLE IF NOT EXISTS characters (
        discord_id INTEGER PRIMARY KEY ,
        name TEXT,
        spellcaster boolean 
    )'''
)

cursor.execute('''
    CREATE TABLE IF NOT EXISTS buildings (
        owner_name text,
        building_type text,
        gold_output integer,
        resource_output integer
    )'''
)


# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

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
        # Add the member to the database
        cursor.execute(
            'INSERT INTO members (discord_id, discord_tag) VALUES (?, ?)',
            (str(message.author.id), str(message.author))
        )
        database.commit()
        print(f"Added {message.author.name} to the database")
    await bot.process_commands(message)

@bot.command()
async def test(ctx):
    await ctx.send("Test command works!")
    await ctx.send(f"{ctx.author.mention}")

# @bot.command()
# async def make_building():
#     await ctx.send("Building created!")
    

bot.run(token, log_handler=handler, log_level=logging.DEBUG)



