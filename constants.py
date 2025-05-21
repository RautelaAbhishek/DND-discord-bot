SPELLCASTING_CLASSES = [
    "bard", "cleric", "druid", "sorcerer", "wizard", "warlock",
    "paladin", "ranger", "artificer"
]

HARVEST_DC_TABLES = {
    "aberration": {
        5: ["Antenna", "eye", "flesh", "phial of blood"],
        10: ["Bone", "egg", "fat", "pouch of claws", "pouch of teeth", "tentacle"],
        15: ["Heart", "phial of mucus", "liver", "stinger"],
        20: ["Brain", "chitin", "hide", "main eye"],
    },
    "beast": {
        5: ["Antenna", "eye", "flesh", "hair", "phial of blood"],
        10: ["Antler", "beak", "bone", "egg", "fat", "fin", "horn", "pincer", "pouch of claws", "pouch of teeth", "talon", "tusk"],
        15: ["Heart", "liver", "poison gland", "pouch of feathers", "pouch of scales", "stinger", "tentacle"],
        20: ["Chitin", "pelt"],
    },
    "celestial": {
        5: ["Eye", "flesh", "hair", "phial of blood", "pouch of dust"],
        10: ["Bone", "fat", "horn", "pouch of teeth"],
        15: ["Heart", "liver", "pouch of feathers", "pouch of scales"],
        20: ["Brain", "skin"],
        25: ["Soul"],
    },
    "construct": {
        5: ["Phial of blood", "phial of oil"],
        10: ["Flesh", "plating", "stone"],
        15: ["Bone", "heart", "liver", "gears"],
        20: ["Brain", "instructions"],
        25: ["Lifespark"],
    },
    "dragon": {
        5: ["Eye", "flesh", "phial of blood"],
        10: ["Bone", "egg", "fat", "pouch of claws", "pouch of teeth"],
        15: ["Horn", "liver", "pouch of scales"],
        20: ["Heart"],
        25: ["Breath sac"],
    },
    "elemental": {
        5: ["Eye", "primordial dust"],
        10: ["Bone"],
        15: [
            "Volatile mote of air",
            "Volatile mote of earth",
            "Volatile mote of fire",
            "Volatile mote of water"
        ],
        25: [
            "Core of air",
            "Core of earth",
            "Core of fire",
            "Core of water"
        ],
    },
    "fey": {
        5: ["Antenna", "eye", "flesh", "hair", "phial of blood"],
        10: ["Antler", "beak", "bone", "egg", "horn", "pouch of claws", "pouch of teeth", "talon", "tusk"],
        15: ["Heart", "fat", "liver", "poison gland", "pouch of feathers", "pouch of scales", "tentacle", "tongue"],
        20: ["Brain", "skin", "pelt"],
        25: ["Psyche"],
    },
    "fiend": {
        5: ["Eye", "flesh", "hair", "phial of blood", "pouch of dust"],
        10: ["Beak", "bone", "horn", "pouch of claws", "pouch of teeth"],
        15: ["Heart", "fat", "liver", "poison gland", "pouch of feathers", "pouch of scales"],
        20: ["Brain", "skin"],
        25: ["Soul"],
    },
    "giant": {
        5: ["Flesh", "hair", "nail", "phial of blood"],
        10: ["Bone", "fat", "tooth"],
        15: ["Heart", "liver"],
        20: ["Skin"],
    },
    "humanoid": {
        5: ["Eye", "phial of blood"],
        10: ["Bone", "egg", "pouch of teeth"],
        15: ["Heart", "liver", "pouch of feathers", "pouch of scales"],
        20: ["Brain", "skin"],
    },
    "monstrosity": {
        5: ["Antenna", "eye", "flesh", "hair", "phial of blood"],
        10: ["Antler", "beak", "bone", "egg", "fat", "fin", "horn", "pincer", "pouch of claws", "pouch of teeth", "talon", "tusk"],
        15: ["Heart", "liver", "poison gland", "pouch of feathers", "pouch of scales", "stinger", "tentacle"],
        20: ["Chitin", "pelt"],
    },
    "ooze": {
        5: ["Phial of acid"],
        10: ["Phial of mucus"],
        15: ["Vesicle"],
        20: ["Membrane"],
    },
    "plant": {
        5: ["Phial of sap", "tuber"],
        10: ["Bundle of roots", "phial of wax", "pouch of hyphae", "pouch of leaves", "pouch of seeds"],
        15: ["Poison gland", "pouch of pollen", "pouch of spores"],
        20: ["Bark", "membrane"],
    },
    "undead": {
        5: ["Eye", "bone", "phial of congealed blood"],
        10: ["Marrow", "pouch of teeth", "rancid fat"],
        15: ["Ethereal ichor", "undying flesh"],
        20: ["Undying heart"],
    },
}

CREATURE_TYPE_SKILLS = {
    "aberration": "Arcana",
    "beast": "Survival",
    "celestial": "Religion",
    "construct": "Investigation",
    "dragon": "Survival",
    "elemental": "Arcana",
    "fey": "Arcana",
    "fiend": "Religion",
    "giant": "Medicine",
    "humanoid": "Medicine",
    "monstrosity": "Survival",
    "ooze": "Nature",
    "plant": "Nature",
    "undead": "Medicine",
}

