from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pet_policy import choose_pet_action, model_status


sample_payload = {
    "pet": "squeaky",
    "message": "i gently pet you, then freeze the blue cube",
    "camera": {"enabled": False},
    "scene": {
        "objects": [
            {"id": "cube-blue", "kind": "cube", "speed": 1.4, "distanceToPet": 1.1, "moving": True},
            {"id": "ball-red", "kind": "sphere", "speed": 0.2, "distanceToPet": 2.0, "moving": False},
        ]
    },
    "forces": [{"kind": "mouse-drag", "targetId": "cube-blue", "strength": 0.7}],
    "detectedObjects": [],
    "interactions": [{"kind": "pet", "pet": "squeaky", "at": 1}],
    "cooldowns": {},
    "petState": {"emotion": "curious"},
}

print(json.dumps({"status": model_status(), "action": choose_pet_action(sample_payload)}, indent=2))
