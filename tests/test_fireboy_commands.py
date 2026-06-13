from __future__ import annotations

import unittest
from unittest.mock import patch

from src.model_policy import model_status
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

    def test_walk_around_uses_walk_interaction(self) -> None:
        action = fallback_policy(fireboy_payload("Fire Boy, walk around the toy room"))

        self.assertEqual(action["interaction"]["verb"], "walk")
        self.assertEqual(action["animation"], "walk")

    def test_model_status_reports_minicpm_v_action_missing_secret(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "TOYBOX_MINICPM_V_ACTION": "1",
                "TOYBOX_VISION_ENDPOINT": "https://api.modelbest.cn/v1/chat/completions",
                "TOYBOX_VISION_MODEL": "MiniCPM-V-4.6-Instruct",
                "TOYBOX_ALLOW_HEURISTIC_FALLBACK": "",
                "TOYBOX_VISION_API_KEY": "",
                "MINICPM_V_API_KEY": "",
                "MODELBEST_API_KEY": "",
            },
            clear=False,
        ):
            status = model_status()

        self.assertTrue(status["configured"])
        self.assertTrue(status["visionActionConfigured"])
        self.assertFalse(status["visionActionEnabled"])
        self.assertTrue(status["visionAuthRequired"])
        self.assertFalse(status["visionAuthConfigured"])
        self.assertEqual(status["provider"], "modelbest")
        self.assertEqual(status["fallbackPolicy"], "asleep_when_configured")


if __name__ == "__main__":
    unittest.main()
