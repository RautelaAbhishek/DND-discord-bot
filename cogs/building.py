import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import time
import os # For os.getenv in setup

# Import directly from the project root
import database as db_utils 
# No more sys.path manipulation

# --- Constants ---
# D&D 5e spellcasting classes (if needed here, otherwise import from config)
# SPELLCASTING_CLASSES = [...] 

class BuildingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # The task is now managed by the main bot class

    # Subcommand to add a building
    @app_commands.command(
        name="addbuilding", # Renamed to avoid conflict if you have a global 'add' command
        description="Add a new building type with its resource details"
    )
    @app_commands.describe(
        building_type="The type of building to add",
        resource_output="The amount of resource the building outputs (e.g., 1d6)",
        resource_type="The type of resource the building outputs (e.g., Gold)",
        resource_frequency="How often the building outputs the resource (e.g., daily, hourly, weekly, test)"
    )
    async def add_building(
        self,
        interaction: discord.Interaction,
        building_type: str,
        resource_output: str,
        resource_type: str,
        resource_frequency: str
    ):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                '''
                INSERT INTO buildings (building_type, resource_output, resource_type, resource_frequency)
                VALUES (?, ?, ?, ?)
                ''',
                (building_type, resource_output, resource_type, resource_frequency)
            )
            conn.commit()
            await interaction.response.send_message(
                f"Building '{building_type}' added with resource output '{resource_output} {resource_type}' every '{resource_frequency}'.",
                ephemeral=True
            )
        except sqlite3.Error as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        finally:
            conn.close()

    # Subcommand to roll resource output for a building
    @app_commands.command(
        name="rollbuilding", # Renamed to avoid conflict
        description="Roll the resource output for a building and repeat based on its frequency"
    )
    @app_commands.describe(
        building_type="The type of building to roll for"
    )
    async def roll_building(
        self,
        interaction: discord.Interaction,
        building_type: str
    ):
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''SELECT resource_output, resource_type, resource_frequency
               FROM buildings WHERE building_type = ?''', (building_type,)
        )
        building_info = cursor.fetchone()

        if not building_info:
            await interaction.response.send_message(f"No building found with type '{building_type}'.", ephemeral=True)
            conn.close()
            return

        resource_output, resource_type, resource_frequency = building_info
        frequency_mapping = {
            "daily": 86400, "hourly": 3600, "weekly": 604800, "test": 15 # Consistent test interval
        }
        interval = frequency_mapping.get(resource_frequency.lower())
        if not interval:
            await interaction.response.send_message(f"Invalid frequency '{resource_frequency}' for building '{building_type}'.", ephemeral=True)
            conn.close()
            return

        current_time = int(time.time())
        
        cursor.execute("SELECT last_roll_time FROM active_rolls WHERE building_type = ?", (building_type,))
        active_roll_entry = cursor.fetchone()

        if not active_roll_entry:
            # First time rolling for this building
            roll_result = db_utils._calculate_roll_result(resource_output) # Use helper from db_utils
            await interaction.response.send_message(
                f"Building '{building_type}' (first roll) produced **{roll_result} {resource_type}**.",
                ephemeral=False 
            )
            cursor.execute(
                '''INSERT INTO active_rolls (building_type, channel_id, last_roll_time)
                   VALUES (?, ?, ?)''',
                (building_type, interaction.channel_id, current_time)
            )
            conn.commit()
        else:
            db_last_roll_time = active_roll_entry[0]
            time_difference = current_time - db_last_roll_time
            num_rolls_to_process = 0
            
            if time_difference >= interval:
                num_rolls_to_process = int(time_difference // interval)
            
            if num_rolls_to_process > 0:
                total_resources_gained = 0
                for _ in range(num_rolls_to_process):
                    total_resources_gained += db_utils._calculate_roll_result(resource_output) # Use helper
                
                await interaction.response.send_message(
                    f"Building '{building_type}' produced **{total_resources_gained} {resource_type}** over {num_rolls_to_process} period(s).",
                    ephemeral=False
                )
                
                new_last_roll_time = db_last_roll_time + (num_rolls_to_process * interval)
                cursor.execute(
                    '''UPDATE active_rolls SET last_roll_time = ?, channel_id = ? 
                       WHERE building_type = ?''',
                    (new_last_roll_time, interaction.channel.id, building_type)
                )
                conn.commit()
            else:
                await interaction.response.send_message(
                    f"Not enough time has passed for '{building_type}' to produce new resources. Last collection was at <t:{db_last_roll_time}:R>.",
                    ephemeral=True
                )
        conn.close()

async def setup(bot):
    # Import config here to access TEST_SERVER_ID
    from config import TEST_SERVER_ID
    if TEST_SERVER_ID is None:
        raise ValueError("TEST_SERVER_ID not found in config. Ensure .env is loaded by config.py.")
    await bot.add_cog(BuildingCog(bot), guilds=[discord.Object(id=int(TEST_SERVER_ID))])

