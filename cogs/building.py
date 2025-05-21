import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
import sqlite3
import time
import os
from typing import List

import database as db_utils
import config # For TEST_SERVER_ID
from .economy import CURRENCY_UNITS # To check if resource_type is a currency

class BuildingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    building_group = app_commands.Group(name="building", description="Manage your character's buildings.")

    async def building_type_autocomplete(self, interaction: discord.Interaction, current: str) -> List[Choice[str]]:
        choices = []
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, name FROM building_types WHERE name LIKE ?", (f"%{current}%",))
            building_types = cursor.fetchall()
            for bt_id, bt_name in building_types:
                choices.append(Choice(name=bt_name, value=str(bt_id)))
            return choices[:25]
        finally:
            conn.close()

    @building_group.command(name="addtype", description="Define a new type of building (Admin only).")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        name="The unique name for this building type (e.g., Small Mine).",
        resource_output="The dice roll for resource amount (e.g., 1d6).",
        resource_type="The type of resource (e.g., gp, sp, iron_ore).",
        resource_frequency="How often it produces (daily, hourly, weekly)." # Removed "test"
    )
    async def add_building_type(self, interaction: discord.Interaction, name: str, resource_output: str, resource_type: str, resource_frequency: str):
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO building_types (name, resource_output, resource_type, resource_frequency) VALUES (?, ?, ?, ?)",
                (name, resource_output, resource_type, resource_frequency.lower())
            )
            conn.commit()
            await interaction.response.send_message(f"Building type '{name}' added.", ephemeral=True)
        except sqlite3.IntegrityError:
            await interaction.response.send_message(f"Building type '{name}' already exists.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        finally:
            conn.close()

    @building_group.command(name="construct", description="Construct a building for your active character.")
    @app_commands.describe(
        building_type_id="The type of building to construct.",
        custom_name="An optional custom name for your building."
    )
    @app_commands.autocomplete(building_type_id=building_type_autocomplete)
    async def construct_building(self, interaction: discord.Interaction, building_type_id: str, custom_name: str = None):
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            # Get active character ID
            cursor.execute("SELECT active_character_id FROM members WHERE discord_id = ?", (str(interaction.user.id),))
            member_data = cursor.fetchone()
            if not member_data or not member_data["active_character_id"]:
                await interaction.response.send_message("You need to set an active character first using `/character setactive`.", ephemeral=True)
                return
            
            active_character_id = member_data["active_character_id"]
            bt_id = int(building_type_id)

            # Verify building type exists
            cursor.execute("SELECT name FROM building_types WHERE id = ?", (bt_id,))
            building_type_info = cursor.fetchone()
            if not building_type_info:
                await interaction.response.send_message("Invalid building type selected.", ephemeral=True)
                return

            current_time = int(time.time())
            channel_id = interaction.channel_id

            cursor.execute(
                """INSERT INTO character_buildings 
                   (character_id, building_type_id, custom_name, channel_id, last_collection_time) 
                   VALUES (?, ?, ?, ?, ?)""",
                (active_character_id, bt_id, custom_name, channel_id, current_time)
            )
            conn.commit()
            building_display_name = custom_name if custom_name else building_type_info["name"]
            await interaction.response.send_message(f"Your active character has constructed a '{building_display_name}'! Resource collection will begin.", ephemeral=False)

        except Exception as e:
            await interaction.response.send_message(f"An error occurred while constructing the building: {e}", ephemeral=True)
            print(f"Error in construct_building: {e}")
        finally:
            conn.close()
            
    @building_group.command(name="mybuildings", description="View buildings owned by your active character.")
    async def view_my_buildings(self, interaction: discord.Interaction):
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT active_character_id FROM members WHERE discord_id = ?", (str(interaction.user.id),))
            member_data = cursor.fetchone()
            if not member_data or not member_data["active_character_id"]:
                await interaction.response.send_message("You need to set an active character first.", ephemeral=True)
                return
            
            active_character_id = member_data["active_character_id"]
            
            cursor.execute("""
                SELECT cb.id, cb.custom_name, bt.name AS type_name, cb.last_collection_time, bt.resource_frequency
                FROM character_buildings cb
                JOIN building_types bt ON cb.building_type_id = bt.id
                WHERE cb.character_id = ?
            """, (active_character_id,))
            
            buildings = cursor.fetchall()
            if not buildings:
                await interaction.response.send_message("Your active character owns no buildings.", ephemeral=True)
                return

            embed = discord.Embed(title="My Character's Buildings", color=discord.Color.blue())
            for building in buildings:
                name = building["custom_name"] if building["custom_name"] else building["type_name"]
                frequency_seconds = {"daily": 86400, "hourly": 3600, "weekly": 604800, "test": 15}.get(building["resource_frequency"].lower(), 0)
                next_collection_timestamp = building["last_collection_time"] + frequency_seconds
                next_collection_str = f"<t:{next_collection_timestamp}:R>" if frequency_seconds > 0 else "N/A"
                embed.add_field(name=f"{name} (Type: {building['type_name']})", value=f"Next collection: {next_collection_str}", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            print(f"Error in view_my_buildings: {e}")
        finally:
            conn.close()


async def setup(bot: commands.Bot):
    guild_id = int(config.TEST_SERVER_ID) if config.TEST_SERVER_ID else None
    if guild_id:
        await bot.add_cog(BuildingCog(bot), guilds=[discord.Object(id=guild_id)])
    else:
        await bot.add_cog(BuildingCog(bot))
    print("BuildingCog loaded.")

