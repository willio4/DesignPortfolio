# ------------------------ Tess -------------------------------
# AI/callModel.py
import json
import logging
import os
import re
from typing import Any, Callable, Dict, Optional

from openai import OpenAI

client = OpenAI()
logging.getLogger(__name__).setLevel(logging.DEBUG)

SYSTEM = (
    "You are a recipe generator. Respond with ONLY valid JSON; no prose, no comments, no trailing commas."
)

_CHAT_COMPLETION_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
_RESPONSES_MODEL = os.getenv("OPENAI_RESPONSES_MODEL", "gpt-4.1-nano")

_LOOKUP_INGREDIENT_TOOL = {
    "type": "function",
    "function": {
        "name": "lookupIngredient",
        "description": "Fetch USDA-backed nutrition facts for a single ingredient term.",
        "parameters": {
            "type": "object",
            "properties": {
                "ingredient": {
                    "type": "string",
                    "description": "Plain ingredient term to look up (e.g., 'salmon fillet').",
                }
            },
            "required": ["ingredient"],
            "additionalProperties": False,
        },
    },
}


def _parse_partial_meals(text: str | None) -> dict | None:
    """Attempt to salvage well-formed meal objects from a truncated JSON blob."""
    if not text:
        return None

    match = re.search(r'"meals"\s*:\s*\[', text)
    if not match:
        return None

    decoder = json.JSONDecoder()
    meals: list[dict] = []
    idx = match.end()
    text_len = len(text)

    while idx < text_len:
        # skip whitespace or commas between entries
        while idx < text_len and text[idx] in " \t\r\n,":
            idx += 1

        if idx >= text_len or text[idx] == ']':
            break

        try:
            obj, consumed = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError as exc:
            logging.debug("Partial decode stopped at index %s: %s", idx, exc)
            break

        if isinstance(obj, dict):
            meals.append(obj)
        else:
            logging.debug("Skipping non-dict meal recovered from partial JSON: %r", obj)

        idx += consumed

    if meals:
        logging.debug("Recovered %d meals from partial JSON", len(meals))
        return {"meals": meals, "_partial": True}

    return None

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


def call_model(
    prompt: str,
    *,
    tool_executor: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
    max_tokens: int = 1500,
) -> dict:
    """Call the model via chat-completions when tools are provided; fall back to Responses API otherwise."""

    if tool_executor is not None:
        return _call_with_chat_tools(prompt, tool_executor=tool_executor, max_tokens=max_tokens)
    return _call_with_responses(prompt, max_tokens=max_tokens)


def _call_with_chat_tools(
    prompt: str,
    *,
    tool_executor: Callable[[str, Dict[str, Any]], Dict[str, Any]],
    max_tokens: int,
) -> dict:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]

    while True:
        response = client.chat.completions.create(
            model=_CHAT_COMPLETION_MODEL,
            messages=messages,
            tools=[_LOOKUP_INGREDIENT_TOOL],
            tool_choice="auto",
            temperature=0.6,
            top_p=1.0,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        message = choice.message
        tool_calls = message.tool_calls or []

        if tool_calls:
            messages.append(_assistant_message_payload(message))
            for call in tool_calls:
                function_name = call.function.name
                raw_args = call.function.arguments or "{}"
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    logging.warning("Tool %s received invalid args JSON: %s", function_name, raw_args)
                    args = {}

                try:
                    result = tool_executor(function_name, args) or {}
                except Exception:
                    logging.exception("Tool %s execution failed", function_name)
                    result = {"ok": False, "error": "tool_execution_failed"}

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            continue

        text = message.content or ""
        logging.debug("Chat completion output:\n%s", text)
        return _parse_json_with_repair(text, max_tokens)


def _assistant_message_payload(message) -> dict:
    payload = {
        "role": "assistant",
        "content": message.content or "",
    }
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": call.type,
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in message.tool_calls
        ]
    return payload


def _call_with_responses(prompt: str, max_tokens: int) -> dict:
    r = client.responses.create(
        model=_RESPONSES_MODEL,
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,
        top_p=1.0,
        max_output_tokens=max_tokens,
    )
    text = r.output_text or ""
    logging.debug("Raw model output (responses API):\n%s", text)
    return _parse_json_with_repair(text, max_tokens)


def _parse_json_with_repair(text: str, max_tokens: int) -> dict:
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

    # Try to salvage any meals that decoded successfully before the truncation
    partial = _parse_partial_meals(candidate or text)
    if partial:
        return partial

    # Fallback: ask the model to repair to valid JSON only
    try:
        fix = client.responses.create(
            model=_RESPONSES_MODEL,
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

        # Last-ditch effort: salvage whatever meals are valid in the repaired text
        partial_fixed = _parse_partial_meals(fixed_text)
        if partial_fixed:
            return partial_fixed
    except Exception as e:
        logging.error("Error during repair request: %s", e)

    logging.error("Unable to parse model output as JSON; returning empty dict")
    return {}


        















"""recipesFromModel= #call model here pass to the parse function below
    modelResults=parseModelResults(recipesFromModel)
    return modelResults"""
