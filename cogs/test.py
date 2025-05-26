import discord
from discord.ext import commands
from discord import app_commands

class TestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="test", description="A command for testers only.")
    async def test_command(self, interaction: discord.Interaction):
        # Check if the user has the "tester" role
        tester_role = discord.utils.get(interaction.guild.roles, name="tester")
        if tester_role and tester_role in interaction.user.roles:
            await interaction.response.send_message("You have access to the test command!", ephemeral=True)
        else:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TestCog(bot))
