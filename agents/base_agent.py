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
        """
        Extract the first complete JSON object from model output.

        Strategy (in order):
          1. Direct json.loads — fastest path for pure-JSON responses.
          2. Strip markdown code fences (```json … ```) and retry.
          3. Bracket-counting extractor — correctly handles nested {} objects
             that confuse greedy/non-greedy regex.
          4. Truncation repair — if max_tokens cut the response mid-JSON,
             close unclosed strings/arrays/objects and parse what we have.
             This preserves signal/confidence even when reasoning is truncated.
          5. Return error sentinel so callers can handle gracefully.
        """
        text = (text or "").strip()

        # ── 1. Pure JSON ──────────────────────────────────────────────────────
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        # ── 2. Strip code fences ──────────────────────────────────────────────
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL).strip()
        if stripped != text:
            try:
                return json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                pass

        # ── 3. Bracket-counting extraction ────────────────────────────────────
        # Walks the string character by character, tracking brace depth and
        # string state so nested objects don't confuse the search.
        def _extract_object(src: str) -> dict | None:
            start = src.find("{")
            if start < 0:
                return None
            depth  = 0
            in_str = False
            esc    = False
            for i, ch in enumerate(src[start:], start):
                if esc:
                    esc = False
                    continue
                if ch == "\\" and in_str:
                    esc = True
                    continue
                if ch == '"':
                    in_str = not in_str
                if not in_str:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            candidate = src[start:i + 1]
                            try:
                                return json.loads(candidate)
                            except (json.JSONDecodeError, ValueError):
                                # Found balanced braces but still invalid JSON
                                # (e.g. trailing comma). Fall through to repair.
                                return None
            return None

        result = _extract_object(text)
        if result is not None:
            return result

        # ── 4. Truncation repair ──────────────────────────────────────────────
        # If max_tokens cut the response mid-JSON (no closing brace), close all
        # unclosed strings / arrays / objects so we recover whatever fields
        # were already emitted (signal, confidence typically come first).
        start = text.find("{")
        if start >= 0:
            fragment = text[start:]
            depth_obj = depth_arr = 0
            in_str = esc = False
            buf: list[str] = []
            for ch in fragment:
                if esc:
                    esc = False
                    buf.append(ch)
                    continue
                if ch == "\\" and in_str:
                    esc = True
                    buf.append(ch)
                    continue
                if ch == '"':
                    in_str = not in_str
                if not in_str:
                    if ch == "{":
                        depth_obj += 1
                    elif ch == "}":
                        depth_obj -= 1
                    elif ch == "[":
                        depth_arr += 1
                    elif ch == "]":
                        depth_arr -= 1
                buf.append(ch)

            if in_str:
                buf.append('"')                       # close open string
            buf.extend("]" * max(0, depth_arr))       # close open arrays
            buf.extend("}" * max(0, depth_obj))       # close open objects

            repaired = "".join(buf)
            try:
                parsed = json.loads(repaired)
                # Only return if we got a non-empty dict (not just "{}")
                if isinstance(parsed, dict) and parsed:
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass

        # ── 5. Failure sentinel ───────────────────────────────────────────────
        return {"error": "Failed to parse JSON", "raw": text[:500]}

    def analyze(self, data: dict) -> dict:
        raise NotImplementedError
