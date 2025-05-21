# Standard library imports
import os
import sqlite3
import logging
import asyncio
from typing import List

# Third-party imports
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# Import harvesting constants
from constants import HARVEST_DC_TABLES, CREATURE_TYPE_SKILLS
from discord.ui import Button, View

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
        building_type TEXT,
        resource_output TEXT,
        resource_type TEXT
    )'''
)

# cursor.execute('''
#     CREATE TABLE IF NOT EXISTS harvests (
#         character_name TEXT,
#         components TEXT,
#         component_type TEXT,
#         amount INTEGER
#     )'''
# )

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


# --- Add this autocomplete function for creatures ---
async def creature_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    # Suggest creatures from HARVEST_DC_TABLES
    return [
        app_commands.Choice(name=creature.title(), value=creature)
        for creature in HARVEST_DC_TABLES
        if current.lower() in creature.lower()
    ][:25]

# --- Add this autocomplete function for components ---
async def component_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    # Get the selected creature from the interaction
    creature = getattr(interaction.namespace, 'creature', None)
    if not creature:
        return []
    offered_components = HARVEST_DC_TABLES.get(creature.lower(), {})
    # Flatten all components for this creature
    all_components = set()
    for comps in offered_components.values():
        all_components.update(comp.lower() for comp in comps)
    # Filter by current input
    return [
        app_commands.Choice(name=comp.title(), value=comp)
        for comp in all_components if current.lower() in comp.lower()
    ][:25]

# Define harvest_group as an app_commands.Group
harvest_group = app_commands.Group(
    name="harvest",
    description="Commands related to harvesting",
    guild_ids=[int(test_server)]  # Ensure it is registered to the correct guild
)

# Subcommand to list components
@harvest_group.command(
    name="list",
    description="List all components for a creature"
)
@app_commands.describe(
    creature="The creature to harvest (autocomplete)"
)
@app_commands.autocomplete(
    creature=creature_autocomplete
)
async def list_components(
    interaction: discord.Interaction,
    creature: str
):
    offered_components = HARVEST_DC_TABLES.get(creature.lower())
    if not offered_components:
        await interaction.response.send_message(f"No harvesting data for creature type '{creature}'.", ephemeral=True)
        return

    # Combine all DC sections into one message
    dc_messages = []
    for dc, comps in offered_components.items():
        dc_lines = [f"**{comp.title()}**" for comp in comps]
        dc_messages.append(f"\n**DC {dc} Components:**\n" + "\n".join(dc_lines)) #dont change
    combined_message = "\n\n".join(dc_messages)
    await interaction.response.send_message(combined_message, ephemeral=True)

@harvest_group.command(
    name="roll",
    description="Roll to see if you succeed in harvesting components"
)
@app_commands.describe(
    creature="The creature to harvest (autocomplete)",
    components="Comma-separated list of components to harvest"
)
@app_commands.autocomplete(
    creature=creature_autocomplete
)
async def roll_harvest(
    interaction: discord.Interaction,
    creature: str,
    components: str
):
    offered_components = HARVEST_DC_TABLES.get(creature.lower())
    if not offered_components:
        await interaction.response.send_message(f"No harvesting data for creature type '{creature}'.", ephemeral=True)
        return

    skill = CREATURE_TYPE_SKILLS.get(creature.lower())
    if not skill:
        await interaction.response.send_message(f"No skill data for creature type '{creature}'.", ephemeral=True)
        return

    # Ask the user for their intelligence modifier and proficiency
    await interaction.response.send_message(
        f"The skill required for harvesting a {creature.title()} is **{skill}**.\nDo you have proficiency in {skill}? Type 0 if no and the modifier if yes.",
        ephemeral=True
    )

    def check(msg):
        return msg.author == interaction.user and msg.channel == interaction.channel

    try:
        user_response = await bot.wait_for("message", check=check, timeout=60)
        proficiency_bonus = int(user_response.content)
    except (ValueError, asyncio.TimeoutError):
        await interaction.followup.send("Invalid input or timeout. Please try again.", ephemeral=True)
        return
    
    await interaction.followup.send(
        f"The skill required for harvesting a {creature.title()} is **{skill}**.\n"
        "What is your Intelligence modifier.",
        ephemeral=True
    )

    def check(msg):
        return msg.author == interaction.user and msg.channel == interaction.channel

    try:
        user_response = await bot.wait_for("message", check=check, timeout=60)
        int_modifier = int(user_response.content)
    except (ValueError, asyncio.TimeoutError):
        await interaction.followup.send("Invalid input or timeout. Please try again.", ephemeral=True)
        return

    # Create a button for rolling a d20
    class RollButton(View):
        def __init__(self):
            super().__init__()
            self.result = None

        @discord.ui.button(label="Roll d20", style=discord.ButtonStyle.primary)
        async def roll(self, interaction: discord.Interaction, button: Button):
            import random
            d20_roll = random.randint(1, 20)
            total_roll = d20_roll + int_modifier + proficiency_bonus
            self.result = total_roll
            await interaction.response.send_message(
                f"You rolled a **{d20_roll}** (d20) + **{int_modifier}** (Int modifier) + **{proficiency_bonus}** (Proficiency) = **{total_roll}**.",
                ephemeral=True
            )
            self.stop()

    roll_view = RollButton()
    await interaction.followup.send("Click the button below to roll a d20.", view=roll_view, ephemeral=True)
    await roll_view.wait()

    if roll_view.result is None:
        await interaction.followup.send("You did not roll in time. Please try again.", ephemeral=True)
        return

    # Determine which components the user successfully harvested
    requested_components = [comp.strip().lower() for comp in components.split(",")]
    successful_components = []
    roll = roll_view.result

    for requested_component in requested_components:
        harvested = False
        for dc, comps in offered_components.items():
            if requested_component in [comp.lower() for comp in comps]:
                if roll >= int(dc):
                    successful_components.append(requested_component)
                    roll -= int(dc)
                    harvested = True
                    break
        if not harvested:
            break  # Stop processing if the roll is insufficient for the current component

    if not successful_components:
        await interaction.followup.send("You failed to harvest any components.", ephemeral=True)
        return

    # Respond with the successful components
    successful_list = ", ".join([comp.title() for comp in successful_components])
    await interaction.followup.send(
        f"Successfully harvested: {successful_list}", ephemeral=True
    )

# Register the harvest_group to the bot's command tree
bot.tree.add_command(harvest_group)

# --- Run Bot ---
bot.run(token, log_handler=handler, log_level=logging.DEBUG)