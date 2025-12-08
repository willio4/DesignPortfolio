# To Do: add `merge_constraints(global_user_prefs)` helper"
"""
Validated constraints store for development.
- File-backed JSON store at AI/constraints.json
- update(mapping) will validate and sanitize keys before persisting

This is intentionally conservative and safe to add incrementally.
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict, List
import builtins

FILE = os.path.join(os.path.dirname(__file__), "constraints.json")

# Define the allowed values and bounds for our constraints here
ALLOWED_DIET = {
    "none",
    "omnivore",
    "vegetarian",
    "vegan",
    "pescatarian",
    "gluten-free",
    "keto",
    "paleo",
    "low-carb",
    "dairy-free",
    "kosher",
}

# Base diet-to-banned ingredient mapping (kept intentionally short and generic)
_MEATS = {"beef", "pork", "ham", "bacon", "sausage", "chicken", "turkey", "duck", "lamb", "veal"}
_PORK_PRODUCTS = {"pork", "ham", "bacon", "prosciutto", "pepperoni", "salami", "chorizo", "pancetta"}
_SHELLFISH = {"shrimp", "lobster", "crab", "clam", "clams", "mussel", "mussels", "oyster", "oysters", "scallop", "scallops"}
_SEAFOOD = _SHELLFISH | {"fish", "salmon", "tuna", "anchovy", "anchovies", "sardine", "sardines"}
_DAIRY = {"milk", "cheese", "butter", "cream", "yogurt", "whey", "casein", "ghee", "half-and-half"}
_EGGS = {"egg", "eggs"}
_HONEY = {"honey"}
_GLUTEN_GRAINS = {"wheat", "barley", "rye", "spelt", "farro", "semolina", "triticale", "couscous", "breadcrumbs", "flour", "seitan"}
_HIGH_CARBS = {"sugar", "brown sugar", "maple syrup", "agave", "rice", "quinoa", "corn", "beans", "lentils", "potato", "potatoes", "bread", "pasta", "oats", "tortilla", "bagel", "cereal"}
_LEGUMES = {"beans", "lentils", "peas", "peanuts", "peanut butter", "soy", "soybeans", "tofu", "tempeh", "edamame", "chickpeas"}
_REFINED_SWEETS = {"white sugar", "brown sugar", "candy", "soda", "dessert", "cake", "cookies", "donut", "pastry"}
_STARCHY_VEG = {"potato", "potatoes", "sweet potato", "yams", "cassava", "plantain", "parsnip", "beet"}
_NON_KOSHER_FISH = {"catfish", "eel", "shark", "octopus", "squid"}

_DIET_BANNED_INGREDIENTS = {
    "none": set(),
    "omnivore": set(),
    "vegetarian": _MEATS | _SEAFOOD | {"gelatin", "lard", "fish sauce", "anchovy paste"},
    "vegan": _MEATS | _SEAFOOD | _DAIRY | _EGGS | _HONEY | {"gelatin", "lard", "fish sauce", "anchovy paste"},
    "pescatarian": _MEATS | {"gelatin", "lard"},
    "gluten-free": _GLUTEN_GRAINS,
    "keto": _HIGH_CARBS,
    "low-carb": _HIGH_CARBS | _REFINED_SWEETS | _STARCHY_VEG,
    "paleo": _GLUTEN_GRAINS | _LEGUMES | _DAIRY | _REFINED_SWEETS | {"corn syrup", "processed sugar", "processed oil", "soy sauce", "tofu", "tempeh", "peanut butter"},
    "dairy-free": _DAIRY,
    "kosher": _PORK_PRODUCTS | _SHELLFISH | _NON_KOSHER_FISH | {"gelatin", "lard", "blood sausage"},
}
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

    if key in ("disliked_ingredients", "banned_ingredients"):
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

# merge mutiple constraints dicts, the later ones will override previous ones
def merge_list_values(*values: Any) -> list:
    """Merge list-like constraint values preserving order and removing dupes."""
    items: list[str] = []
    for values in values:
        if not values:
            continue
        if isinstance(values, list):
            items.extend([str(x).strip().lower() for x in values if str(x).strip()])
        elif isinstance(values, str):
            items.extend([x.strip().lower() for x in values.split(",") if x.strip()])
        else:
            items.append(str(values).strip().lower())

    # use builtins.set because this module defines a `set()` function below
    seen: set[str] = builtins.set()
    out: list[str] = []
    for it in items:
        # `it` is already a lower-cased, stripped string
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out

def _dietary_banned_for(diet: str | None) -> List[str]:
    key = (diet or "none").strip().lower()
    banned_set = _DIET_BANNED_INGREDIENTS.get(key, builtins.set()) # adjusted to call builtins.set() because of local set() function
    return sorted(banned_set)

def banned_for_diets(diets: List[str] | None) -> List[str]:
    """Return the union of banned ingredients for all diets in the list."""
    if not diets:
        return []
    combined = builtins.set()
    for diet in diets:
        key = (diet or "none").strip().lower()
        combined.update(_DIET_BANNED_INGREDIENTS.get(key, ()))
    return sorted(combined)

def merge_constraints(global_constraints: Dict[str, Any] | None,
                      user_constraints: Dict[str, Any] | None = None,
                      prefs: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Merge constraints with precedence: prefs > user_constraints > global_constraints.
    
    - Accepts None for any input.
    - Merges 'disliked_ingredients' as the union of all sources.
    - Returns a sanitized dict via validate_constraints().
    - Pure function:, does not persist anything."""

    global_constraints = global_constraints or {}
    user_constraints = user_constraints or {}
    prefs = prefs or {}

    # begin with global, then overlay user, then prefs (last-writer-wins)
    merged: Dict[str, Any] = dict(global_constraints)
    merged.update(user_constraints)
    merged.update(prefs)

    # special handling of list-like merging for disliked_ingredients (disliked
    # ingredients is just an example, we can extend this)
    merged["disliked_ingredients"] = merge_list_values(
        global_constraints.get("disliked_ingredients"),
        user_constraints.get("disliked_ingredients"),
        prefs.get("disliked_ingredients"),
    )

    diet_banned = _dietary_banned_for(merged.get("dietary_restrictions"))
    merged["banned_ingredients"] = merge_list_values(
        diet_banned,
        global_constraints.get("banned_ingredients"),
        user_constraints.get("banned_ingredients"),
        prefs.get("banned_ingredients"),
    )

    # sanitize everything before returning
    return validate_constraints(merged)

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
