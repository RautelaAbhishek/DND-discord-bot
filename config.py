import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
TEST_SERVER_ID = os.getenv('DEV_SERVER_ID')

SPELLCASTING_CLASSES = [
    "bard", "cleric", "druid", "sorcerer", "wizard", "warlock",
    "paladin", "ranger", "artificer"
]

# You can also move HARVEST_DC_TABLES and CREATURE_TYPE_SKILLS here
# if they are static and don't change often.
# For now, let's assume they are in constants.py as per your original import.
