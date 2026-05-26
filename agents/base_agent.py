import json
import re
import anthropic
from config import ANTHROPIC_API_KEY


class BaseAgent:
    name = "BaseAgent"

    def __init__(self, model: str):
        self.model = model
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def _call(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "You are an expert financial analyst. Always respond with valid JSON.",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def _parse_json(self, text: str) -> dict:
        """Extract the first JSON object found in model output."""
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try extracting from markdown code block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try finding any JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"error": "Failed to parse JSON", "raw": text}

    def analyze(self, data: dict) -> dict:
        raise NotImplementedError
