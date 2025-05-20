# Standard library imports
import os
import sqlite3
import logging
import asyncio

# Third-party imports
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# Import harvesting constants
from constants import HARVEST_DC_TABLES

# --- Constants ---
# D&D 5e spellcasting classes
SPELLCASTING_CLASSES = [
    "bard", "cleric", "druid", "sorcerer", "wizard", "warlock",
    "paladin", "ranger", "artificer"
]

# --- Environment & Logging ---
load_dotenv()
token = os.getenv('DISCORD_TOKEN')
test_server = os.getenv('DEV_SERVER_ID')
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

cursor.execute('''
    CREATE TABLE IF NOT EXISTS harvests (
        character_name TEXT,
        components TEXT,
        component_type TEXT,
        amount INTEGER
    )'''
)





# --- Events ---
class Client(commands.Bot):
    async def on_ready(self):
        print(f"Logged on as {self.user}")

        try:
            guild  = discord.Object(id=test_server)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild {guild.id}")
        except Exception as e:
            print(f"Error syncing commands: {e}")

    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.content.startswith('hello'):
            await message.channel.send(f"Hi there {message.author}")





# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
GUILD_ID  = discord.Object(id=test_server)
bot = Client(command_prefix='!', intents=intents)



# adds user to db when they first type
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
        # Send and delete the user creation message after 10 seconds
        creation_msg = await message.channel.send(f"Added {message.author.name} to the database")
        await asyncio.sleep(10)
        try:
            await creation_msg.delete()
        except Exception:
            pass
    await bot.process_commands(message)


# create character
@bot.tree.command(
        name="create_character",
        description="This will create and add your character which allows you to use other features",
        guild=GUILD_ID,
    )
async def add_character(
        intereaction: discord.Interaction,
        name: str,
        class_name: str
    ):
    cursor.execute('SELECT COUNT(*) FROM characters WHERE discord_id = ?', (str(intereaction.user.id),))
    count = cursor.fetchone()[0]
    if count >= 3:
        await intereaction.send("You can only have up to 3 characters!")
        return
    is_spellcaster = class_name.lower() in SPELLCASTING_CLASSES

    approval_channel = discord.utils.get(intereaction.guild.text_channels, name="character-approvals")
    if not approval_channel:
        await intereaction.response.send_message("No 'character-approvals' channel found for admin approval.", ephemeral=True)
        return

    await intereaction.response.send_message(f"An admin has been asked to approve this character addition in {approval_channel.mention}. Please wait for their response.", ephemeral=True)

    try:
        approval_msg = await approval_channel.send(
            f"User {intereaction.user.mention} wants to add character '{name}' (class: {class_name}, spellcaster: {is_spellcaster}).\n"
            f"Admins: React with ✅ to approve or ❌ to deny."
        )
        await approval_msg.add_reaction("✅")
        await approval_msg.add_reaction("❌")

        def approval_check(reaction, user):
            # Only allow admins to approve/deny
            if reaction.message.id != approval_msg.id:
                return False
            if str(reaction.emoji) not in ["✅", "❌"]:
                return False
            member = intereaction.guild.get_member(user.id)
            return member is not None and any(role.permissions.administrator for role in member.roles) and not user.bot

        reaction, user = await bot.wait_for('reaction_add', check=approval_check)
    except Exception as e:
        await intereaction.followup.send("No admin response. Character addition cancelled.", ephemeral=True)
        print(f"Error: {e}")
        return

    if str(reaction.emoji) == "✅":
        cursor.execute(
            'INSERT INTO characters (discord_id, name, class, spellcaster) VALUES (?, ?, ?, ?)',
            (str(intereaction.user.id), name, class_name, is_spellcaster)
        )
        database.commit()
        await intereaction.followup.send(f"Character {name} ({class_name}) added!", ephemeral=True)
        confirm_msg = await approval_channel.send(f"{user.mention} approved the character '{name}' ({class_name}) for {intereaction.user.mention}.")
    else:
        await intereaction.followup.send("Character addition denied by admin.", ephemeral=True)
        confirm_msg = await approval_channel.send(f"{user.mention} denied the character '{name}' ({class_name}) for {intereaction.user.mention}.")

    # Delete approval request and admin response after 60 seconds
    # await asyncio.sleep(60)
    # try:
    #    await approval_msg.delete()
    #     await confirm_msg.delete()
    # except Exception:
    #     pass


@bot.tree.command(
    name="harvest",
    description="This command will harvest creatures for you",
    guild=GUILD_ID
)
async def harvest(
    interaction: discord.Interaction,
    creature: str,
    count: int
):
    offered_components = HARVEST_DC_TABLES.get(creature.lower())
    if not offered_components:
        await interaction.response.send_message(f"No harvesting data for creature type '{creature}'.")
        return

    # Group components by DC for display
    dc_components = {}
    for dc, components in offered_components.items():
        dc_components.setdefault(dc, []).extend(components)

    display_lines = []
    for dc in sorted(dc_components):
        display_lines.append(f"**DC {dc}**")
        for comp in dc_components[dc]:
            display_lines.append(f"- {comp.title()}")
        display_lines.append("")  # Blank line for spacing

    # Use interaction.response.send_message for the first reply, then followup for subsequent
    await interaction.response.send_message(
        "\nAvailable components for this creature:\n" +
        "\n".join(display_lines)
    )
    await interaction.followup.send(
        "Type the components you want to harvest in the format `add <amount> <component>` (e.g., `add 3 eye`).\n"
        "Type `done` when finished."
    )

    # Get the channel from the interaction, not bot.get_channel()
    channel = interaction.channel

    def check(m):
        return m.author == interaction.user and m.channel == channel

    # Example: collect user input (not fully implemented)
    # while True:
    #     try:
    #         msg = await bot.wait_for('message', check=check, timeout=60)
    #         if msg.content.lower() == 'done':
    #             break
    #         # Parse and process the input here
    #     except asyncio.TimeoutError:
    #         await channel.send("Harvesting timed out.")
    #         break

# --- Run Bot ---
bot.run(token, log_handler=handler, log_level=logging.DEBUG)



# add mat to list with dc