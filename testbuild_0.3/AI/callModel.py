# ------------------------ Tess -------------------------------
# AI/callModel.py
import json
import logging
import re
from openai import OpenAI
client = OpenAI()
logging.getLogger(__name__).setLevel(logging.DEBUG)

SYSTEM = (
    "You are a recipe generator. Respond with ONLY valid JSON; no prose, no comments, no trailing commas."
)

def _extract_json_from_text(text: str) -> str | None:
    """Try to extract the first JSON object or array from text and balance braces/brackets.

    Returns a JSON string if extraction appears successful, otherwise None.
    """
    if not text:
        return None

    # find first { or [ and try to capture a balanced JSON block
    start_match = re.search(r"[\{\[]", text)
    if not start_match:
        return None

    start = start_match.start()
    stack = []
    pairs = {"{": "}", "[": "]"}
    end = None
    for i in range(start, len(text)):
        ch = text[i]
        if ch in "[{":
            stack.append(pairs[ch])
        elif ch in "}]":
            if not stack:
                # unmatched closing - skip
                continue
            expected = stack.pop()
            if ch != expected:
                # mismatched; give up
                return None
            if not stack:
                end = i + 1
                break

    if end is None:
        return None

    candidate = text[start:end]
    return candidate


def call_model(prompt: str, max_tokens: int = 900) -> dict:

    prompt += f"\n\n# Request timestamp: {datetime.utcnow().isoformat()}"
    logging.debug(f"Final prompt sent to model: {prompt}")

    r = client.responses.create(
        model="gpt-4.1-nano",
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,          # some creativity
        top_p=1.0,               # more creative
        max_output_tokens=max_tokens,
    )
    text = r.output_text or ""
    logging.debug("Raw model output:\n%s", text)

    # First attempt: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logging.debug("Initial json.loads failed: %s", e)

    # Try extraction of a JSON block from the text
    candidate = _extract_json_from_text(text)
    if candidate:
        logging.debug("Extracted JSON candidate (truncated): %s", candidate[:1000])
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            logging.debug("json.loads on extracted candidate failed: %s", e)

    # Fallback: ask the model to repair to valid JSON only
    try:
        fix = client.responses.create(
            model="gpt-4.1-nano",
            input=f"Fix to strictly valid JSON only (no commentary):\n{text}",
            temperature=0.0,
            top_p=0.0,
            max_output_tokens=max_tokens,
        )
        fixed_text = fix.output_text or ""
        logging.debug("Repair attempt output:\n%s", fixed_text)
        try:
            return json.loads(fixed_text)
        except json.JSONDecodeError as e:
            logging.error("Repair attempt still failed to produce valid JSON: %s", e)
    except Exception as e:
        logging.error("Error during repair request: %s", e)

    # As a final fallback, return an empty structure and avoid crashing the app
    logging.error("Unable to parse model output as JSON; returning empty dict")
    return {}

        















"""recipesFromModel= #call model here pass to the parse function below
    modelResults=parseModelResults(recipesFromModel)
    return modelResults"""
