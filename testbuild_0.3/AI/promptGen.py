# ------------------------ Tess -------------------------------
from textwrap import dedent
from typing import Any

# local imports when running inside the package
try:
    from . import constraints_store
    from .retrieval_contract import RetrievalBatch
except ImportError:  # script execution fallback
    import importlib
    import os
    import sys
    PACKAGE_ROOT = os.path.dirname(os.path.dirname(__file__))
    if PACKAGE_ROOT not in sys.path:
        sys.path.insert(0, PACKAGE_ROOT)
    constraints_store = importlib.import_module("AI.constraints_store")
    RetrievalBatch = importlib.import_module("AI.retrieval_contract").RetrievalBatch

# Schema the model must produce (backend-friendly)
# - ingredients are objects with explicit weights
# - macros are 0; backend overwrites using USDA + weights
SCHEMA = (
    '{"meals":[{'
      '"mealType":"breakfast|lunch|dinner",'
      '"name":"string",'
      '"ingredients":[{"name":"string","weight_g":0,"weight_oz":0,"quantity":0,"unit":"string","note":"string"}],'
      '"calories":0,"carbs":0,"fats":0,"protein":0,'
      '"instructions":["string"]'
    '}]}'
)

def safe_int(value, default=0, non_negative=True):
    try:
        iv = int(value)
        return iv if (not non_negative or iv >= 0) else default
    except (ValueError, TypeError):
        return default

def _constraint_text(dietary_restrictions: str, calories: int, banned_items: list[str]):
    extras = []
    if isinstance(dietary_restrictions, str) and dietary_restrictions.strip() and dietary_restrictions.lower() != "none":
        extras.append(f"Dietary constraints: {dietary_restrictions}")
    if calories > 0:
        extras.append(f"Per-meal target ~{calories} kcal (true totals computed by backend).")
    if banned_items:
        preview = ", ".join(banned_items[:12]) + ("..." if len(banned_items) > 12 else "")
        extras.append(f"Forbidden ingredients: {preview}. Never include them.")
    constraint_text = ". ".join(extras) if extras else "No specific dietary constraints."
    banned_rule = (
        "No additional banned ingredients beyond the general constraints."
        if not banned_items else
        "Absolutely DO NOT use any of the banned ingredients listed above."
    )
    return constraint_text, banned_rule

def generate_prompt(
    merged_constraints: dict | None = None,
    retrieval_batch: RetrievalBatch | None = None,
    calorie_rules: list[str] | None = None
) -> str:
    """
    Creative recipes; nutrition totals are computed in backend from ingredient weights.
    """
    prefs = merged_constraints or {}

    dietary_restrictions = prefs.get("dietary_restrictions") or prefs.get("diet") or "none"
    num_breakfast = safe_int(prefs.get("num_breakfast", prefs.get("num1", 0)))
    num_lunch     = safe_int(prefs.get("num_lunch",    prefs.get("num2", 0)))
    num_dinner    = safe_int(prefs.get("num_dinner",   prefs.get("num3", 1)))
    calories      = safe_int(prefs.get("calories", 0))
    banned_items  = [str(x).strip() for x in (prefs.get("banned_ingredients") or []) if str(x).strip()]

    constraint_text, banned_rule = _constraint_text(dietary_restrictions, calories, banned_items)

    facts_block = ""
    if retrieval_batch:
        block = retrieval_batch.to_prompt_block()
        if block:
            facts_block = block + "\n\n"

    calorie_lines = ""
    if calorie_rules:
        bullet_lines = "\n        ".join(f"- {rule}" for rule in calorie_rules)
        calorie_lines = f"Calorie goals (backend-enforced):\n        {bullet_lines}\n\n"

    body = dedent(f"""
        You generate creative meal recipes.
        Do NOT estimate nutrition totals yourself—our backend will compute accurate calories and macros using USDA and the weights you provide.

        Return ONLY valid JSON using this schema:
        {SCHEMA}

        Make exactly {num_breakfast} breakfast, {num_lunch} lunch, and {num_dinner} dinner recipes.

        Hard requirements:
        1) Ingredient entries MUST be objects with explicit weights:
           - "name": plain ingredient name (e.g., "chicken breast, cooked, skinless")
           - "weight_g": number (grams, REQUIRED)
           - "weight_oz": number (ounces, OPTIONAL; backend converts if missing)
           - "quantity": number (OPTIONAL; for display, not used in math)
           - "unit": string (OPTIONAL; e.g., "cup", "tbsp")
           - "note": string (OPTIONAL; brief prep note)
        2) Before finalizing ingredients, call the tool:
           lookupIngredient({{"ingredient":"<plain term>"}})
           Use tool results ONLY to confirm the ingredient is sensible and commonly available.
           If a lookup fails, replace the ingredient with a similar one and proceed. Do NOT output tool payloads.
        3) Set "calories","carbs","fats","protein" to 0 for every meal. The backend overwrites these.
        4) Instructions must be a list of concise, numbered steps (strings). Keep them cook-friendly.
        5) JSON only: no prose outside the JSON, no comments, no trailing commas.

        {calorie_lines}Quality rules:
        - Be creative: vary cuisines, proteins, grains, and dominant flavors across meals.
        - Use 4–10 ingredients per meal. Prefer fresh whole foods; pantry staples ok (beans, tomatoes, broth).
        - Always avoid banned ingredients if any are provided. {constraint_text}
        - {banned_rule}
    """).strip()

    return f"{facts_block}{body}" if facts_block else body

# -------------------- User + Constraints Wrapper -------------------------
def user_to_prompt(user: Any) -> str:
    if not user:
        return ""
    def _get(o, *names, default=None):
        for n in names:
            if isinstance(o, dict) and n in o:
                return o[n]
            if hasattr(o, n):
                return getattr(o, n)
        return default
    parts = []
    age = _get(user, "age", "Age")
    if age is not None: parts.append(f"age={age}")
    diet = _get(user, "dietary_restrictions", "diet", "dietary")
    if diet: parts.append(f"diet={diet}")
    dislikes = _get(user, "disliked_ingredients", "dislikes")
    if dislikes:
        parts.append("disliked=" + (", ".join(map(str, dislikes)) if isinstance(dislikes, (list, tuple, set)) else str(dislikes)))
    allergies = _get(user, "allergies", "allergy")
    if allergies:
        parts.append("allergies=" + (", ".join(allergies) if isinstance(allergies, (list, tuple)) else str(allergies)))
    prefs = _get(user, "prefs", "preferences")
    if prefs: parts.append("prefs=" + str(prefs))
    return "" if not parts else "User profile: " + "; ".join(parts)

def build_prompt(
    user: Any = None,
    global_constraints: dict | None = None,
    user_constraints: dict | None = None,
    prefs: dict | None = None,
    retrieval_batch: RetrievalBatch | None = None,
    calorie_rules: list[str] | None = None
) -> str:
    merged = constraints_store.merge_constraints(global_constraints, user_constraints, prefs)
    ufrag = user_to_prompt(user)
    constraint_lines = []
    if merged.get("dietary_restrictions"):
        constraint_lines.append(f"diet: {merged['dietary_restrictions']}")
    if merged.get("disliked_ingredients"):
        constraint_lines.append("dislikes: " + ", ".join(merged["disliked_ingredients"]))
    if merged.get("calories"):
        constraint_lines.append(f"target_calories: {merged['calories']}")
    if merged.get("banned_ingredients"):
        preview = ", ".join(merged["banned_ingredients"][:6])
        if len(merged["banned_ingredients"]) > 6:
            preview += ", ..."
        constraint_lines.append(f"banned: {preview}")

    body = generate_prompt(merged, retrieval_batch=retrieval_batch, calorie_rules=calorie_rules)

    header = ""
    if ufrag: header += ufrag + "\n"
    if constraint_lines: header += "Constraints: " + "; ".join(constraint_lines) + "\n"
    return header + body
