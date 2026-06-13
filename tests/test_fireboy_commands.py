from __future__ import annotations

import unittest

from src.pet_actions import fallback_policy


def fireboy_payload(message: str) -> dict:
    return {
        "pet": "fire_boy",
        "message": message,
        "scene": {
            "objects": [
                {
                    "id": "cube-blue",
                    "kind": "box",
                    "name": "blue cube",
                    "speed": 0.0,
                    "distanceToPet": 1.1,
                    "moving": False,
                    "affordances": ["play", "inspect", "throw"],
                    "tags": ["box", "cube", "blue"],
                },
                {
                    "id": "soft-ball",
                    "kind": "sphere",
                    "name": "soft ball",
                    "speed": 0.0,
                    "distanceToPet": 1.6,
                    "moving": False,
                    "affordances": ["play", "roll"],
                    "tags": ["ball"],
                },
            ],
            "pet": {"needs": {"hunger": 18}},
        },
        "forces": [],
        "detectedObjects": [],
        "interactions": [],
    }


class FireBoyCommandPolicyTest(unittest.TestCase):
    def test_pick_up_box_uses_pickup_interaction(self) -> None:
        action = fallback_policy(fireboy_payload("Fire Boy, pick up the blue box"))

        self.assertEqual(action["interaction"]["verb"], "pickup")
        self.assertEqual(action["interaction"]["targetId"], "cube-blue")
        self.assertEqual(action["power"]["targetId"], "cube-blue")

    def test_fireball_targets_named_cube(self) -> None:
        action = fallback_policy(fireboy_payload("Fire Boy, fireball the blue cube"))

        self.assertEqual(action["power"]["name"], "fireball")
        self.assertEqual(action["power"]["targetId"], "cube-blue")

    def test_run_around_uses_run_interaction(self) -> None:
        action = fallback_policy(fireboy_payload("Fire Boy, run around the toy room"))

        self.assertEqual(action["interaction"]["verb"], "run")
        self.assertEqual(action["power"]["name"], "ember_jump")


if __name__ == "__main__":
    unittest.main()
