import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
import asyncio
from typing import List

# Assuming config.py and database.py are in the parent directory (project root)
import config
import database as db_utils

class CharacterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    character_group = app_commands.Group(name="character", description="Manage your characters")

    async def user_character_autocomplete(self, interaction: discord.Interaction, current: str) -> List[Choice[str]]:
        """Autocompletes character names owned by the user."""
        choices = []
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, name FROM characters WHERE discord_id = ?", (str(interaction.user.id),))
            user_characters = cursor.fetchall()
            for char_id, char_name in user_characters:
                if current.lower() in char_name.lower():
                    choices.append(Choice(name=char_name, value=str(char_id))) # Store ID as value
            return choices[:25]
        finally:
            conn.close()

    @character_group.command(name="create", description="Create a new character (max 3).")
    @app_commands.describe(name="Your character's name.", class_name="Your character's class.")
    async def create_character(self, interaction: discord.Interaction, name: str, class_name: str):
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM characters WHERE discord_id = ?', (str(interaction.user.id),))
            count = cursor.fetchone()[0]
            if count >= 3:
                await interaction.response.send_message("You can only have up to 3 characters!", ephemeral=True)
                return

            is_spellcaster = class_name.lower() in config.SPELLCASTING_CLASSES

            approval_channel = discord.utils.get(interaction.guild.text_channels, name="character-approvals")
            if not approval_channel:
                await interaction.response.send_message("Configuration error: 'character-approvals' channel not found.", ephemeral=True)
                return

            await interaction.response.send_message(f"Your character creation request for '{name}' has been sent for admin approval in {approval_channel.mention}.", ephemeral=True)

            embed = discord.Embed(
                title="Character Approval Request",
                description=f"User {interaction.user.mention} wants to create character:",
                color=discord.Color.blue()
            )
            embed.add_field(name="Character Name", value=name, inline=False)
            embed.add_field(name="Class", value=class_name, inline=False)
            embed.add_field(name="Spellcaster", value=str(is_spellcaster), inline=False)
            
            approval_msg = await approval_channel.send(embed=embed)
            await approval_msg.add_reaction("✅")
            await approval_msg.add_reaction("❌")

            def check(reaction, user):
                return reaction.message.id == approval_msg.id and str(reaction.emoji) in ["✅", "❌"] and \
                       not user.bot and any(role.permissions.administrator for role in interaction.guild.get_member(user.id).roles)

            reaction, user = await self.bot.wait_for('reaction_add', timeout=86400.0, check=check) # 24 hour timeout

            if str(reaction.emoji) == "✅":
                cursor.execute(
                    'INSERT INTO characters (discord_id, name, class, spellcaster) VALUES (?, ?, ?, ?)',
                    (str(interaction.user.id), name, class_name, is_spellcaster)
                )
                conn.commit()
                await interaction.followup.send(f"Character '{name}' ({class_name}) has been approved and created!", ephemeral=True)
                await approval_channel.send(f"{user.mention} approved character '{name}' for {interaction.user.mention}.")
            else:
                await interaction.followup.send(f"Character creation for '{name}' was denied by an admin.", ephemeral=True)
                await approval_channel.send(f"{user.mention} denied character '{name}' for {interaction.user.mention}.")

        except asyncio.TimeoutError:
            await interaction.followup.send("Character approval request for '{name}' timed out.", ephemeral=True)
            if 'approval_msg' in locals():
                try:
                    await approval_msg.edit(content="This request has timed out.", embed=None, view=None)
                except discord.HTTPException: pass
        except Exception as e:
            await interaction.followup.send("An error occurred during character creation.", ephemeral=True)
            print(f"Error in create_character: {e}")
        finally:
            conn.close()

    @character_group.command(name="setactive", description="Set your active character.")
    @app_commands.describe(character="The character to set as active.")
    @app_commands.autocomplete(character=user_character_autocomplete)
    async def set_active_character(self, interaction: discord.Interaction, character: str):
        character_id_to_set = int(character) # Value from autocomplete is the character ID

        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            # Verify the character belongs to the user (though autocomplete should handle this)
            cursor.execute("SELECT name FROM characters WHERE id = ? AND discord_id = ?", 
                           (character_id_to_set, str(interaction.user.id)))
            char_data = cursor.fetchone()

            if not char_data:
                await interaction.response.send_message("Invalid character selected or character not found.", ephemeral=True)
                return

            character_name = char_data['name']

            # Update the members table
            cursor.execute("UPDATE members SET active_character_id = ? WHERE discord_id = ?",
                           (character_id_to_set, str(interaction.user.id)))
            # If the user wasn't in members table yet (e.g., only interacted via slash commands)
            if cursor.rowcount == 0:
                cursor.execute("INSERT INTO members (discord_id, discord_tag, active_character_id) VALUES (?, ?, ?)",
                               (str(interaction.user.id), str(interaction.user), character_id_to_set))
            conn.commit()
            await interaction.response.send_message(f"'{character_name}' is now your active character.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            print(f"Error in set_active_character: {e}")
        finally:
            conn.close()

    @character_group.command(name="viewactive", description="View your currently active character.")
    async def view_active_character(self, interaction: discord.Interaction):
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT c.name, c.class, c.spellcaster 
                FROM members m
                JOIN characters c ON m.active_character_id = c.id
                WHERE m.discord_id = ?
            """, (str(interaction.user.id),))
            active_char = cursor.fetchone()

            if active_char:
                embed = discord.Embed(title="Active Character", color=discord.Color.green())
                embed.add_field(name="Name", value=active_char['name'], inline=False)
                embed.add_field(name="Class", value=active_char['class'], inline=False)
                embed.add_field(name="Spellcaster", value="Yes" if active_char['spellcaster'] else "No", inline=False)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("You do not have an active character set. Use `/character setactive`.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            print(f"Error in view_active_character: {e}")
        finally:
            conn.close()


async def setup(bot: commands.Bot):
    guild_id = int(config.TEST_SERVER_ID) if config.TEST_SERVER_ID else None
    if guild_id:
        await bot.add_cog(CharacterCog(bot), guilds=[discord.Object(id=guild_id)])
    else:
        await bot.add_cog(CharacterCog(bot))
    print("CharacterCog loaded.")

