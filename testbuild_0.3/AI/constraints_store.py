"""
Validated constraints store for development.
- File-backed JSON store at AI/constraints.json
- update(mapping) will validate and sanitize keys before persisting

This is intentionally conservative and safe to add incrementally.
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict

FILE = os.path.join(os.path.dirname(__file__), "constraints.json")

# Define the allowed values and bounds for our constraints here
ALLOWED_DIET = {"none", "vegetarian", "vegan", "pescatarian", "gluten-free", "keto", "omnivore"}
MAX_MEALS = 10
MIN_MEALS = 0

# read constraints from file
def _read() -> Dict[str, Any]:
    if not os.path.exists(FILE):
        return {}
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# write to a temp file and rename 
def _write(obj: Dict[str, Any]) -> None:
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, FILE)


def get() -> Dict[str, Any]:
    return _read()

# sanitize the individual constraint value
# (by sanitize we mean ensure it's within the allowed values/ranges)
def _sanitize_value(key: str, value: Any) -> Any:
    """Sanitize a single constraint value according to key rules."""
    if key == "dietary_restrictions":
        if not isinstance(value, str):
            return "none"
        v = value.strip().lower()
        return v if v in ALLOWED_DIET else "none"

    if key in ("num1", "num2", "num3"):
        try:
            n = int(value)
            if n < MIN_MEALS:
                return MIN_MEALS
            if n > MAX_MEALS:
                return MAX_MEALS
            return n
        except Exception:
            return 0

    if key == "calories":
        try:
            n = int(value)
            return max(0, n)
        except Exception:
            return 0

    if key == "disliked_ingredients":
        # expect list-like or comma separated string
        if isinstance(value, list):
            return [str(x).strip().lower() for x in value if str(x).strip()]
        if isinstance(value, str):
            return [x.strip().lower() for x in value.split(",") if x.strip()]
        return []

    # default: coerce to string for simple keys
    if isinstance(value, (str, int, float, bool)):
        return value

    # unknown complex objects are stored as their string representation
    return str(value)

def validate_constraints(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Return a sanitized copy of mapping.

    Unknown keys are allowed but their values are coerced to a safe form.
    """
    out: Dict[str, Any] = {}
    for k, v in mapping.items():
        out[k] = _sanitize_value(k, v)
    return out


def update(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Merge mapping (after validation) into stored constraints and persist."""
    if not isinstance(mapping, dict):
        raise TypeError("mapping must be a dict")

    safe = validate_constraints(mapping)
    data = _read()
    data.update(safe)
    _write(data)
    return data

# set a single constraint key/value pair
def set(key: str, value: Any) -> Dict[str, Any]:
    data = _read()
    data[key] = _sanitize_value(key, value)
    _write(data)
    return data

# clear all stored constraints 
def clear() -> None:
    if os.path.exists(FILE):
        os.remove(FILE)
