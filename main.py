# Standard library imports
import os
import discord
from discord.ext import commands, tasks
import logging
import asyncio
import time # Keep for on_ready processing

# Import from local modules
import config # For TOKEN, TEST_SERVER_ID, SPELLCASTING_CLASSES
import database as db_utils # For database connection and helper functions
from cogs.economy import CURRENCY_UNITS # Import for checking resource type

# --- Environment & Logging ---
# load_dotenv() is now in config.py
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

# --- Bot Class ---
class Client(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The task will be started in on_ready after initial processing

    async def setup_hook(self):
        # This function is called once the bot is logged in and ready,
        # but before on_ready. It's the ideal place to load cogs and sync commands.
        print("DEBUG: Entered setup_hook")
        
        # Load cogs
        await self.load_extension("cogs.harvesting")
        await self.load_extension("cogs.building")
        await self.load_extension("cogs.character") 
        await self.load_extension("cogs.economy") # Load the new economy cog
        print("DEBUG: Cogs loaded.")

        try:
            guild_id_int = int(config.TEST_SERVER_ID) if config.TEST_SERVER_ID else None
            if guild_id_int:
                guild = discord.Object(id=guild_id_int) # Use config.TEST_SERVER_ID
                synced = await self.tree.sync(guild=guild)
                print(f"Synced {len(synced)} commands to guild {guild.id}")
            else: # Sync globally if no test server ID
                synced = await self.tree.sync()
                print(f"Synced {len(synced)} commands globally.")
        except Exception as e:
            print(f"Error syncing commands: {e}")

    async def on_ready(self):
        print("DEBUG: Entered on_ready method")
        print(f"Logged on as {self.user}")
        print(f"Bot ID: {self.user.id}")
        print("HarvestingBot has logged on")

        print("DEBUG: Initial check for building production on startup...")
        await self.process_building_production() # Call the processing logic directly on startup

        print("DEBUG: Starting background task check_building_production...")
        if not self.check_building_production.is_running():
            self.check_building_production.start()
        print("DEBUG: Finished processing on_ready.")

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
        
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            # Ensure member exists, if not, create them.
            # This is important for active_character_id to be settable.
            cursor.execute('SELECT 1 FROM members WHERE discord_id = ?', (str(message.author.id),))
            if cursor.fetchone() is None:
                cursor.execute(
                    'INSERT INTO members (discord_id, discord_tag) VALUES (?, ?)',
                    (str(message.author.id), str(message.author))
                )
                conn.commit()
                # Send a temporary confirmation message
                creation_msg = await message.channel.send(f"Added {message.author.name} to the database (first message).")
                await asyncio.sleep(10) # Wait 10 seconds
                try:
                    await creation_msg.delete() # Delete the confirmation message
                except discord.NotFound: # Message might have been deleted manually
                    pass
                except discord.Forbidden: # Bot might lack permissions
                    pass
                except Exception as e: # Catch other potential errors
                    print(f"Error deleting user creation message: {e}")
        finally:
            conn.close()
        
        await self.process_commands(message)

    async def process_building_production(self):
        """Processes resource production for all character_buildings."""
        print("DEBUG: Running process_building_production task for character buildings.")
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        # Need access to economy cog's update_character_wallet or a similar utility
        economy_cog = self.get_cog("EconomyCog")
        if not economy_cog:
            print("ERROR: EconomyCog not found. Cannot process building production.")
            conn.close()
            return

        try:
            cursor.execute("""
                SELECT cb.id, cb.character_id, c.name AS character_name, cb.channel_id, cb.last_collection_time, cb.custom_name,
                       bt.name AS building_type_name, bt.resource_output, bt.resource_type, bt.resource_frequency
                FROM character_buildings cb
                JOIN building_types bt ON cb.building_type_id = bt.id
                JOIN characters c ON cb.character_id = c.id
            """) # Added JOIN with characters table and c.name
            all_character_buildings = cursor.fetchall()

            if not all_character_buildings:
                # print("DEBUG: No character buildings to process.")
                conn.close()
                return

            current_time = int(time.time())

            for building_data in all_character_buildings:
                building_instance_id = building_data["id"]
                character_id = building_data["character_id"]
                character_name = building_data["character_name"] # Get character_name from the query result
                channel_id = building_data["channel_id"]
                last_collection_time = building_data["last_collection_time"]
                building_display_name = building_data["custom_name"] if building_data["custom_name"] else building_data["building_type_name"]
                
                resource_output = building_data["resource_output"]
                resource_type_key = building_data["resource_type"].lower() # e.g., "gp", "sp"
                resource_frequency = building_data["resource_frequency"]

                frequency_mapping = {
                    "daily": 86400, "hourly": 3600, "weekly": 604800, "test": 15
                }
                interval = frequency_mapping.get(resource_frequency.lower())
                if not interval:
                    print(f"WARNING: Invalid frequency '{resource_frequency}' for building instance ID {building_instance_id}. Skipping.")
                    continue

                time_difference = current_time - last_collection_time
                if time_difference >= interval:
                    num_collections_to_process = int(time_difference // interval)
                    total_resources_gained_amount = 0
                    for _ in range(num_collections_to_process):
                        total_resources_gained_amount += db_utils.calculate_roll_result(resource_output)
                    
                    if num_collections_to_process > 0 and total_resources_gained_amount > 0:
                        notification_channel = self.get_channel(channel_id)
                        
                        # Check if the resource_type is a known currency
                        if resource_type_key in CURRENCY_UNITS:
                            # Add to character's wallet
                            update_success = await economy_cog.update_character_wallet(
                                character_id, 
                                resource_type_key, 
                                total_resources_gained_amount
                            )

                            if update_success:
                                if notification_channel:
                                    await notification_channel.send(
                                        f"Your building '{building_display_name}' has produced **{total_resources_gained_amount} {CURRENCY_UNITS[resource_type_key]['name']}** for {character_name}."
                                    )
                                print(f"DEBUG: Added {total_resources_gained_amount} {resource_type_key} to {character_name} (ID: {character_id}) from building {building_instance_id}")
                            else:
                                if notification_channel:
                                    await notification_channel.send(
                                        f"Tried to add resources from '{building_display_name}' to {character_name} (ID: {character_id}), but the wallet update failed."
                                    )
                                print(f"ERROR: Failed to update wallet for {character_name} (ID: {character_id}) from building {building_instance_id}")
                        else:
                            # Handle non-currency resources (e.g., log, or if inventory system exists, add there)
                            if notification_channel:
                                await notification_channel.send(
                                    f"Your building '{building_display_name}' has produced **{total_resources_gained_amount} {resource_type_key}** for {character_name}."
                                )
                            print(f"DEBUG: Building {building_instance_id} produced non-currency item: {total_resources_gained_amount} {resource_type_key} for {character_name} (ID: {character_id})")

                        # Update last_collection_time for this specific building instance
                        new_last_collection_time = last_collection_time + (num_collections_to_process * interval)
                        cursor.execute(
                            "UPDATE character_buildings SET last_collection_time = ? WHERE id = ?",
                            (new_last_collection_time, building_instance_id)
                        )
                        conn.commit()
                        print(f"DEBUG: Processed {num_collections_to_process} collections for building instance {building_instance_id}. New last_collection_time: {new_last_collection_time}")
        except Exception as e:
            print(f"ERROR: An error occurred during character building production processing: {e}")
        finally:
            conn.close()

    @tasks.loop(minutes=1)
    async def check_building_production(self):
        await self.process_building_production()

    @check_building_production.before_loop
    async def before_check_building_production(self):
        await self.wait_until_ready()

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Ensure members intent is enabled for guild.get_member
bot = Client(command_prefix='!', intents=intents)

# Character creation command is now moved to cogs/character.py

# --- Run Bot ---
if __name__ == "__main__":
    bot.run(config.TOKEN, log_handler=handler, log_level=logging.DEBUG)