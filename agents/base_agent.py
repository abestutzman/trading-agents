import json
import re
import anthropic
from config import ANTHROPIC_API_KEY


def fmt(v, spec=".2f", na="N/A"):
    """Format a numeric value or return N/A string."""
    if v is None or v == "" or v == "N/A":
        return na
    try:
        return format(float(v), spec)
    except (TypeError, ValueError):
        return str(v)


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
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"error": "Failed to parse JSON", "raw": text}

    def analyze(self, data: dict) -> dict:
        raise NotImplementedError
