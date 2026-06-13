from __future__ import annotations

import random
from typing import Any


VALID_EMOTIONS = ["happy", "curious", "surprised", "glee", "focused", "sleepy", "petted", "startled", "dizzy", "shy"]

FACE_BLENDSHAPE_KEYS = ["eye", "smile", "mouth", "brow", "cheek", "squash", "tilt", "sparkle"]

PET_PROFILES = {
    "squeaky": {
        "name": "Squeaky",
        "traits": "gentle, punctual, fussy about loud crashes, secretly theatrical",
        "powers": ["time_freeze", "shrink", "rewind", "clock_bubble"],
        "animations": ["trunk_wiggle", "bounce", "look_left_right", "tiny_scamper", "nuzzle", "startle"],
        "sounds": ["clock_chime", "soft_pop", "tick_tock", "pet_touch", "happy_chirp", "startle", "purr", "tiny_giggle", "curious_hm"],
    },
    "electraica": {
        "name": "Electraica",
        "traits": "bright, helpful, excitable, loves lamps and metal objects",
        "powers": ["shock", "lamp_burst", "magnet_pull"],
        "animations": ["spark_spin", "bounce", "look_left_right", "nuzzle", "startle"],
        "sounds": ["spark", "bulb_ping", "pet_touch", "happy_chirp", "startle", "purr", "electric_pip", "curious_hm"],
    },
    "fire_boy": {
        "name": "Fire Boy",
        "traits": "warm, babyish, brave, dramatic, tries to be safe but loves a tiny flourish",
        "powers": ["fireball", "ember_jump", "smoke_poof"],
        "animations": ["flame_wiggle", "bounce", "look_left_right", "nuzzle", "startle"],
        "sounds": ["whoosh", "soft_pop", "pet_touch", "happy_chirp", "startle", "purr", "ember_purr", "tiny_giggle"],
    },
    "shark_girl": {
        "name": "Shark Girl",
        "traits": "sweet, musical, ocean-brained, protective of tiny things",
        "powers": ["wave", "bubble_lift", "tide_pull"],
        "animations": ["fin_sway", "bounce", "look_left_right", "nuzzle", "startle"],
        "sounds": ["water_plink", "soft_pop", "pet_touch", "happy_chirp", "startle", "purr", "bubble_chirp", "curious_hm"],
    },
}


FALLBACK_LINES = {
    "time_freeze": [
        "Tick-tock. Everybody take a tiny pause.",
        "Hold still, noisy little room.",
        "I lent the cube my pocket watch.",
    ],
    "shrink": [
        "Small mode. Very serious business.",
        "I am travel-sized for science.",
        "Tiny Squeaky has entered the timeline.",
    ],
    "rewind": [
        "Back you go, bouncy thing.",
        "That moment needed a retake.",
        "I put the crash back in its box.",
    ],
    "clock_bubble": [
        "A clock bubble for dramatic weather.",
        "The room needed one soft second.",
        "I made time rounder.",
    ],
    "shock": [
        "Zap with manners.",
        "A tiny spark for the brave object.",
        "The lamp heard me.",
    ],
    "magnet_pull": [
        "Come closer, shiny little thing.",
        "I made gravity more friendly.",
        "Tiny magnet mood activated.",
    ],
    "lamp_burst": [
        "The lamp got extremely cheerful.",
        "Bright idea, literally.",
        "I pinged the light awake.",
    ],
    "fireball": [
        "Lil whoosh, safe safe.",
        "Tiny comet, be nice.",
        "Me make warm sparkle.",
    ],
    "ember_jump": [
        "Boop, warm hop.",
        "Tiny flame jumpy.",
        "Me did candle bounce.",
    ],
    "smoke_poof": [
        "Poof, hidey cloud.",
        "Me soft smoke baby.",
        "Tiny smoke blankie.",
    ],
    "wave": [
        "Little tide, big feelings.",
        "The floor remembered the sea.",
        "Splish, but make it plush.",
    ],
    "bubble_lift": [
        "Up you float, tiny friend.",
        "Bubble elevator is open.",
        "I made the room buoyant.",
    ],
    "tide_pull": [
        "The tide wants everyone closer.",
        "Scoot with the sea.",
        "A gentle room current.",
    ],
}


def normalize_pet(value: Any) -> str:
    pet = str(value or "squeaky").lower().replace("-", "_")
    return pet if pet in PET_PROFILES else "squeaky"


def line_for(power_name: str) -> str:
    return random.choice(FALLBACK_LINES.get(power_name, ["I have a tiny plan."]))


def valid_choice(value: Any, choices: list[str], fallback: str) -> str:
    text = str(value or "")
    return text if text in choices else fallback
