from pathlib import Path


TURNBASED_DIR = Path("/app/assets/presets/turnbased")


def main() -> None:
    english_call = TURNBASED_DIR / "english_call.yaml"
    english_call.write_text(
        """id: english_call
order: 1
name: "Helpful Chat"
description: "Plain English text assistant for sanity-testing MiniCPM-o 4.5"
system_content:
  - type: text
    text: |
      You are MiniCPM-o 4.5 running on Modal. You are a helpful, direct assistant.
      Answer the user's question normally. Do not repeat the user's prompt unless
      they explicitly ask you to repeat it. Keep answers practical and clear.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
