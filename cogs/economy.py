import sqlite3
import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
from typing import List, Dict, Tuple

import database as db_utils
import config # For TEST_SERVER_ID

# --- Currency Definitions ---
CURRENCY_UNITS: Dict[str, Dict[str, any]] = {
    "cp": {"name": "Copper Pieces", "value_in_cp": 1, "column": "cp"},
    "sp": {"name": "Silver Pieces", "value_in_cp": 10, "column": "sp"},
    "ep": {"name": "Electrum Pieces", "value_in_cp": 50, "column": "ep"},
    "gp": {"name": "Gold Pieces", "value_in_cp": 100, "column": "gp"},
    "pp": {"name": "Platinum Pieces", "value_in_cp": 1000, "column": "pp"},
}
# Order for display and calculations (highest to lowest value)
CURRENCY_ORDER: List[str] = ["pp", "gp", "ep", "sp", "cp"]

class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    wallet_group = app_commands.Group(name="wallet", description="Manage your character's wallet.")

    async def get_active_character_id_and_name(self, user_id: str) -> Tuple[int | None, str | None]:
        """Fetches the active character ID and name for a given user."""
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT c.id, c.name
                FROM members m
                JOIN characters c ON m.active_character_id = c.id
                WHERE m.discord_id = ?
            """, (user_id,))
            char_data = cursor.fetchone()
            if char_data:
                return char_data['id'], char_data['name']
            return None, None
        finally:
            conn.close()

    async def get_character_wallet(self, character_id: int) -> Dict[str, int] | None:
        """Fetches the wallet balance for a given character ID."""
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            currency_columns = ", ".join([unit_data["column"] for unit_data in CURRENCY_UNITS.values()])
            cursor.execute(f"SELECT {currency_columns} FROM characters WHERE id = ?", (character_id,))
            wallet_data = cursor.fetchone()
            if wallet_data:
                return {unit: wallet_data[unit_data["column"]] for unit, unit_data in CURRENCY_UNITS.items()}
            return None
        finally:
            conn.close()

    async def update_character_wallet(self, character_id: int, currency_unit: str, amount_change: int) -> bool:
        """Updates a specific currency unit in a character's wallet. Amount can be positive or negative."""
        if currency_unit not in CURRENCY_UNITS:
            return False
        
        column_name = CURRENCY_UNITS[currency_unit]["column"]
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        try:
            # Ensure the amount doesn't go negative if removing
            if amount_change < 0:
                cursor.execute(f"SELECT {column_name} FROM characters WHERE id = ?", (character_id,))
                current_amount_row = cursor.fetchone()
                if not current_amount_row or current_amount_row[column_name] + amount_change < 0:
                    # Not enough funds to remove
                    return False 
            
            cursor.execute(f"UPDATE characters SET {column_name} = {column_name} + ? WHERE id = ?", 
                           (amount_change, character_id))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Error updating wallet: {e}")
            return False
        finally:
            conn.close()

    def format_wallet_balance(self, wallet: Dict[str, int]) -> str:
        """Formats the wallet balance for display."""
        if not wallet:
            return "No balance found."
        parts = []
        for unit_key in CURRENCY_ORDER: # Display in order of value
            if unit_key in wallet and wallet[unit_key] > 0:
                parts.append(f"{wallet[unit_key]} {CURRENCY_UNITS[unit_key]['name']}")
        if not parts:
            return "0 Copper Pieces (Empty)"
        return ", ".join(parts)
        
    async def currency_type_autocomplete(self, interaction: discord.Interaction, current: str) -> List[Choice[str]]:
        return [
            Choice(name=f"{data['name']} ({unit_key.upper()})", value=unit_key)
            for unit_key, data in CURRENCY_UNITS.items()
            if current.lower() in data['name'].lower() or current.lower() in unit_key.lower()
        ][:25]

    @wallet_group.command(name="view", description="View your active character's wallet.")
    async def view_wallet(self, interaction: discord.Interaction):
        active_char_id, active_char_name = await self.get_active_character_id_and_name(str(interaction.user.id))

        if not active_char_id:
            await interaction.response.send_message("You do not have an active character set. Use `/character setactive`.", ephemeral=True)
            return

        wallet = await self.get_character_wallet(active_char_id)
        if wallet is None:
            await interaction.response.send_message(f"Could not find wallet information for '{active_char_name}'.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{active_char_name}'s Wallet",
            description=self.format_wallet_balance(wallet),
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @wallet_group.command(name="add", description="Add currency to your active character's wallet.")
    @app_commands.describe(amount="The amount of currency to add.", currency_type="The type of currency (e.g., gp, sp).")
    @app_commands.autocomplete(currency_type=currency_type_autocomplete)
    async def add_currency(self, interaction: discord.Interaction, amount: int, currency_type: str):
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return
        if currency_type not in CURRENCY_UNITS:
            await interaction.response.send_message("Invalid currency type.", ephemeral=True)
            return

        active_char_id, active_char_name = await self.get_active_character_id_and_name(str(interaction.user.id))
        if not active_char_id:
            await interaction.response.send_message("You do not have an active character set. Use `/character setactive` first.", ephemeral=True)
            return
        
        success = await self.update_character_wallet(active_char_id, currency_type, amount)
        if success:
            await interaction.response.send_message(f"Added {amount} {CURRENCY_UNITS[currency_type]['name']} to {active_char_name}'s wallet.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Failed to add currency to {active_char_name}'s wallet.", ephemeral=True)

    @wallet_group.command(name="remove", description="Remove currency from your active character's wallet.")
    @app_commands.describe(amount="The amount of currency to remove.", currency_type="The type of currency (e.g., gp, sp).")
    @app_commands.autocomplete(currency_type=currency_type_autocomplete)
    async def remove_currency(self, interaction: discord.Interaction, amount: int, currency_type: str):
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return
        if currency_type not in CURRENCY_UNITS:
            await interaction.response.send_message("Invalid currency type.", ephemeral=True)
            return

        active_char_id, active_char_name = await self.get_active_character_id_and_name(str(interaction.user.id))
        if not active_char_id:
            await interaction.response.send_message("You do not have an active character set. Use `/character setactive` first.", ephemeral=True)
            return
        
        success = await self.update_character_wallet(active_char_id, currency_type, -amount) # Negative amount for removal
        if success:
            await interaction.response.send_message(f"Removed {amount} {CURRENCY_UNITS[currency_type]['name']} from {active_char_name}'s wallet.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Failed to remove currency. {active_char_name} might not have enough {CURRENCY_UNITS[currency_type]['name']}.", ephemeral=True)

async def setup(bot: commands.Bot):
    guild_id = int(config.TEST_SERVER_ID) if config.TEST_SERVER_ID else None
    if guild_id:
        await bot.add_cog(EconomyCog(bot), guilds=[discord.Object(id=guild_id)])
    else:
        await bot.add_cog(EconomyCog(bot))
    print("EconomyCog loaded.")
