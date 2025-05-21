import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
TEST_SERVER_ID = os.getenv('DEV_SERVER_ID')

SPELLCASTING_CLASSES = [
    "bard", "cleric", "druid", "sorcerer", "wizard", "warlock",
    "paladin", "ranger", "artificer"
]

DND_CLASSES = [
    "Artificer", "Barbarian", "Bard", "Cleric", "Druid", "Fighter", "Monk",
    "Paladin", "Ranger", "Rogue", "Sorcerer", "Warlock", "Wizard",
]
