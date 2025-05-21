import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button # Import View and Button
from typing import List
import random
import asyncio
import os # For os.getenv in setup

# Import directly from the project root
from constants import HARVEST_DC_TABLES, CREATURE_TYPE_SKILLS
# No more sys.path manipulation needed here

class HarvestingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def creature_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        # Suggest creatures from HARVEST_DC_TABLES
        return [
            app_commands.Choice(name=creature.title(), value=creature)
            for creature in HARVEST_DC_TABLES
            if current.lower() in creature.lower()
        ][:25]

    async def component_autocomplete(
        self,
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

    harvest_group = app_commands.Group(
        name="harvest",
        description="Commands related to harvesting"
        # guild_ids will be applied when adding the cog in main.py
    )

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
        self,
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
            dc_lines = [f"\t**{comp.title()}**" for comp in comps]
            # Adjusted the string formatting here:
            dc_messages.append(f"**DC {dc} Components:**\n" + "\n".join(dc_lines)) 
        combined_message = "\n-----------------------\n".join(dc_messages) # Use two newlines to separate DC blocks
        await interaction.response.send_message("--\n" + combined_message + "\n-----------------------", ephemeral=False)

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
        self,
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

        # Calculate the total DC required for all requested components (for display purposes)
        # This part remains the same, it's for user information.
        total_dc_display = 0
        requested_components_list = [comp.strip().lower() for comp in components.split(",")] # Renamed for clarity
        for requested_component_name in requested_components_list:
            for dc_value, component_names_in_dc_table in offered_components.items():
                if requested_component_name in [cn.lower() for cn in component_names_in_dc_table]:
                    total_dc_display += int(dc_value)
                    break
        
        formatted_components = "\n".join([f"- {comp.title()}" for comp in requested_components_list])
        await interaction.response.send_message(
            f"**You requested to harvest:**\n{formatted_components}\n\n"
            f"**Total DC required (sum of individual DCs):** `{total_dc_display}`", # Clarified message
            ephemeral=False
        )

        # Ask the user for their intelligence modifier and proficiency
        await interaction.followup.send(
            f"The skill required for harvesting a {creature.title()} is **{skill}**.\nDo you have proficiency in {skill}? Type 0 if no and the modifier if yes.",
            ephemeral=False
        )

        def check(msg):
            return msg.author == interaction.user and msg.channel == interaction.channel

        try:
            user_response = await self.bot.wait_for("message", check=check, timeout=60)
            proficiency_bonus = int(user_response.content)
        except (ValueError, asyncio.TimeoutError):
            await interaction.followup.send("Invalid input or timeout. Please try again.", ephemeral=True)
            return
        
        await interaction.followup.send(
            f"The skill required for harvesting a {creature.title()} is **{skill}**.\n"
            "What is your Intelligence modifier.",
            ephemeral=False
        )

        try:
            user_response = await self.bot.wait_for("message", check=check, timeout=60)
            int_modifier = int(user_response.content)
        except (ValueError, asyncio.TimeoutError):
            await interaction.followup.send("Invalid input or timeout. Please try again.", ephemeral=True)
            return

        # Create a button for rolling a d20 for assessment
        class AssessmentRollButton(View):
            def __init__(self, int_mod, prof_bonus): # Removed outer_instance, pass only needed values
                super().__init__(timeout=180.0) # Added timeout to the View
                self.result = None
                # self.outer_instance = outer_instance # Not strictly needed if bot is accessible via interaction
                self.int_modifier = int_mod
                self.proficiency_bonus = prof_bonus


            @discord.ui.button(label="Roll d20 for Assessment", style=discord.ButtonStyle.primary)
            async def roll(self, button_interaction: discord.Interaction, button: Button): # Renamed interaction to button_interaction
                d20_roll = random.randint(1, 20)
                total_roll = d20_roll + self.int_modifier + self.proficiency_bonus
                self.result = total_roll
                await button_interaction.response.send_message( # Use button_interaction
                    f"You rolled a **{d20_roll}** (d20) + **{self.int_modifier}** (Int modifier) + **{self.proficiency_bonus}** (Proficiency) = **{total_roll}**.",
                    ephemeral=False
                )
                self.stop()

        assessment_roll_view = AssessmentRollButton(int_modifier, proficiency_bonus) # Pass modifiers
        await interaction.followup.send("Click the button below to roll a d20 for assessment.", view=assessment_roll_view, ephemeral=False)
        await assessment_roll_view.wait()

        if assessment_roll_view.result is None:
            await interaction.followup.send("You did not roll in time. Please try again.", ephemeral=False)
            return

        assessment_roll = assessment_roll_view.result

        # Ask the user for their Dexterity modifier for carving
        await interaction.followup.send(
            "What is your Dexterity modifier for carving?",
            ephemeral=False
        )

        try:
            user_response = await self.bot.wait_for("message", check=check, timeout=60)
            dex_modifier = int(user_response.content)
        except (ValueError, asyncio.TimeoutError):
            await interaction.followup.send("Invalid input or timeout. Please try again.", ephemeral=True)
            return

        # Create a button for rolling a d20 for carving
        class CarvingRollButton(View):
            def __init__(self, dex_mod, prof_bonus): # Removed outer_instance
                super().__init__(timeout=180.0) # Added timeout to the View
                self.result = None
                # self.outer_instance = outer_instance
                self.dex_modifier = dex_mod
                self.proficiency_bonus = prof_bonus


            @discord.ui.button(label="Roll d20 for Carving", style=discord.ButtonStyle.primary)
            async def roll(self, button_interaction: discord.Interaction, button: Button): # Renamed interaction
                d20_roll = random.randint(1, 20)
                total_roll = d20_roll + self.dex_modifier + self.proficiency_bonus
                self.result = total_roll
                await button_interaction.response.send_message( # Use button_interaction
                    f"You rolled a **{d20_roll}** (d20) + **{self.dex_modifier}** (Dex modifier) + **{self.proficiency_bonus}** (Proficiency) = **{total_roll}**.",
                    ephemeral=False
                )
                self.stop()

        carving_roll_view = CarvingRollButton(dex_modifier, proficiency_bonus) # Pass modifiers
        await interaction.followup.send("Click the button below to roll a d20 for carving.", view=carving_roll_view, ephemeral=False)
        await carving_roll_view.wait()

        if carving_roll_view.result is None:
            await interaction.followup.send("You did not roll in time. Please try again.", ephemeral=False)
            return

        carving_roll = carving_roll_view.result
        # Show the combined roll of assessment and carving
        combined_roll = assessment_roll + carving_roll # This is the crucial value now
        await interaction.followup.send(
            f"Your combined Assessment and Carving check is: **{assessment_roll} + {carving_roll} = {combined_roll}**.",
            ephemeral=False
        )
        
        # Determine which components the user successfully harvested using the combined_roll
        successful_components = []
        remaining_combined_roll = combined_roll # Use a new variable for the diminishing combined roll

        # Sort requested components by DC (optional, but can be fairer if DCs vary)
        # For simplicity, we'll process in the order requested.
        # If you want to sort by DC, you'd need to fetch DC for each requested_component first.

        for requested_component_name in requested_components_list:
            found_component_dc = None
            for dc_value, component_names_in_dc_table in offered_components.items():
                if requested_component_name in [cn.lower() for cn in component_names_in_dc_table]:
                    found_component_dc = int(dc_value)
                    break
            
            if found_component_dc is not None:
                if remaining_combined_roll >= found_component_dc:
                    successful_components.append(requested_component_name)
                    remaining_combined_roll -= found_component_dc # Subtract component's DC from the combined roll
                else:
                    # Stop processing further components if the combined roll is not enough for this one
                    await interaction.followup.send(
                        f"You attempted to harvest '{requested_component_name.title()}' (DC {found_component_dc}) but your remaining roll of {remaining_combined_roll} was insufficient.",
                        ephemeral=True
                    )
                    break # Stop trying to harvest more components
            else:
                # This case should ideally not happen if component_autocomplete is working correctly
                # and HARVEST_DC_TABLES is accurate.
                print(f"Warning: Component '{requested_component_name}' not found in DC table for '{creature}'.")


        if not successful_components:
            await interaction.followup.send("You failed to harvest any components with your combined roll.", ephemeral=True)
            return

        # Respond with the successfully harvested and carved components
        # Format the successfully harvested components as a bulleted list
        formatted_successful_components = "\n".join([f"- {comp.title()}" for comp in successful_components])
        await interaction.followup.send(
            f"**Successfully harvested:**\n{formatted_successful_components}\n\n(Remaining roll: **{remaining_combined_roll}**)", 
            ephemeral=False
        )

async def setup(bot):
    # Import config here to access TEST_SERVER_ID if not already available
    # This ensures config is loaded when the cog is set up.
    from config import TEST_SERVER_ID
    if TEST_SERVER_ID is None:
        # Fallback or raise error if not found, os.getenv is also an option
        # but config.py should handle loading .env
        raise ValueError("TEST_SERVER_ID not found in config. Ensure .env is loaded by config.py.")
    await bot.add_cog(HarvestingCog(bot), guilds=[discord.Object(id=int(TEST_SERVER_ID))])
