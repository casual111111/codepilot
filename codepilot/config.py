import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class CodePilotConfig:
    api_key: str
    base_url: str
    model: str


def load_config() -> CodePilotConfig:
    load_dotenv()

    api_key = os.getenv("CODEPILOT_API_KEY", "")
    base_url = os.getenv("CODEPILOT_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("CODEPILOT_MODEL", "gpt-4o-mini")

    return CodePilotConfig(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        model=model,
    )
