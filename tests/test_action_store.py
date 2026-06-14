from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.action_store import action_stats, fetch_action_events, record_pet_action


class ActionStoreTest(unittest.TestCase):
    def test_records_sanitized_action_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "actions.sqlite3"
            with patch.dict("os.environ", {"TOYBOX_ACTION_DB_PATH": str(db_path)}, clear=False):
                record_pet_action(
                    {
                        "pet": "fire_boy",
                        "message": "Fire Boy, pick up the box",
                        "cameraFrame": "data:image/png;base64,abc123",
                        "cameraFrameSource": "agent-view",
                    },
                    {
                        "speech": "Me hold it.",
                        "intent": "pickup",
                        "emotion": "happy",
                        "animation": "walk",
                        "interaction": {"verb": "pickup", "targetId": "cube-blue"},
                        "power": {"name": "ember_jump", "targetId": "cube-blue"},
                        "debug": {
                            "policy": "modal_omni_action",
                            "provider": "modal",
                            "model": "openbmb/MiniCPM-o-4_5",
                            "promptTokens": 10,
                            "completionTokens": 3,
                            "tokensPerSecond": 2.5,
                            "functionCalls": 1,
                            "stateUpdatesRequested": 1,
                        },
                    },
                    123.4,
                )

                events = fetch_action_events(limit=5)
                stats = action_stats()

        self.assertEqual(events["count"], 1)
        self.assertEqual(events["events"][0]["policy"], "modal_omni_action")
        self.assertEqual(events["events"][0]["interaction_verb"], "pickup")
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["modalActions"], 1)


if __name__ == "__main__":
    unittest.main()
