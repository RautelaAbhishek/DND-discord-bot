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
        await self.load_extension("cogs.character") # Load the new cog
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
        """Processes resource production for all active buildings."""
        print("DEBUG: Running process_building_production task.")
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT building_type, channel_id, last_roll_time FROM active_rolls')
            active_rolls_data = cursor.fetchall()

            if not active_rolls_data:
                print("DEBUG: No active rolls to process.")
                return

            current_time = int(time.time())

            for building_type, channel_id, db_last_roll_time in active_rolls_data:
                channel = self.get_channel(channel_id)
                if not channel:
                    print(f"WARNING: Channel ID {channel_id} for {building_type} not found. Skipping.")
                    continue

                cursor.execute(
                    '''SELECT resource_output, resource_type, resource_frequency
                       FROM buildings WHERE building_type = ?''', (building_type,)
                )
                building_info = cursor.fetchone()
                if not building_info:
                    print(f"WARNING: Building type '{building_type}' not found in buildings table. Skipping.")
                    continue

                resource_output, resource_type, resource_frequency = building_info
                frequency_mapping = {
                    "daily": 86400, "hourly": 3600, "weekly": 604800, "test": 15
                }
                interval = frequency_mapping.get(resource_frequency.lower())
                if not interval:
                    print(f"WARNING: Invalid frequency '{resource_frequency}' for {building_type}. Skipping.")
                    continue

                time_difference = current_time - db_last_roll_time
                if time_difference >= interval:
                    num_rolls_to_process = int(time_difference // interval)
                    total_resources_gained = 0
                    for _ in range(num_rolls_to_process):
                        total_resources_gained += db_utils.calculate_roll_result(resource_output) # Use helper from db_utils
                    
                    if num_rolls_to_process > 0: # Send message only if resources were gained
                        await channel.send(
                            f"Building '{building_type}' has produced **{total_resources_gained} {resource_type}** over {num_rolls_to_process} period(s)."
                        )
                    
                    new_last_roll_time = db_last_roll_time + (num_rolls_to_process * interval)
                    cursor.execute(
                        '''UPDATE active_rolls SET last_roll_time = ? WHERE building_type = ?''',
                        (new_last_roll_time, building_type)
                    )
                    conn.commit()
                    print(f"DEBUG: Processed {num_rolls_to_process} rolls for {building_type}. New last_roll_time: {new_last_roll_time}")
                else:
                    # Optional: Log that no production was due if needed for debugging
                    # print(f"DEBUG: No production due for {building_type}. Last roll: {db_last_roll_time}, Current time: {current_time}, Interval: {interval}")
                    pass
        except Exception as e:
            print(f"ERROR: An error occurred during building production processing: {e}")
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