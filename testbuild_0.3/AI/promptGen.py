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


# Schema the model must produce
SCHEMA = (
    '{"meals":[{"mealType":"breakfast|lunch|dinner","name":"string","ingredients":["string"],'
    '"calories":0,"instructions":"string","carbs":0,"fats":0,"protein":0}]}'
)


def safe_int(value, default=0, non_negative=True):
    try:
        int_val = int(value)
        return int_val if (not non_negative or int_val >= 0) else default
    except (ValueError, TypeError):
        return default


def _constraint_text(dietary_restrictions: str, calories: int, banned_items: list[str]):
    extras = []
    if isinstance(dietary_restrictions, str) and dietary_restrictions.strip() and dietary_restrictions.lower() != "none":
        extras.append(f"Dietary constraints: {dietary_restrictions}")
    if calories > 0:
        extras.append(f"Per meal target ~{calories} calories (approx.; backend will compute true values)")
    if banned_items:
        preview = ", ".join(banned_items[:12]) + ("..." if len(banned_items) > 12 else "")
        extras.append(f"Forbidden ingredients: {preview}. Never include them.")

    constraint_text = ". ".join(extras) if extras else "No specific dietary constraints."
    banned_rule = (
        "No additional banned ingredients beyond the general constraints."
        if not banned_items
        else "Absolutely DO NOT use any of the banned ingredients listed above."
    )
    return constraint_text, banned_rule


def generate_prompt(
    merged_constraints: dict | None = None,
    retrieval_batch: RetrievalBatch | None = None,
    calorie_rules: list[str] | None = None
) -> str:
    """Build the strict tool-driven meal-generation prompt."""

    prefs = merged_constraints or {}

    dietary_restrictions = prefs.get("dietary_restrictions") or prefs.get("diet") or "none"
    num_breakfast = safe_int(prefs.get("num_breakfast", prefs.get("num1", 0)))
    num_lunch = safe_int(prefs.get("num_lunch", prefs.get("num2", 0)))
    num_dinner = safe_int(prefs.get("num_dinner", prefs.get("num3", 1)))
    calories = safe_int(prefs.get("calories", 0))
    banned_items = [str(x).strip() for x in (prefs.get("banned_ingredients") or []) if str(x).strip()]

    constraint_text, banned_rule = _constraint_text(
        dietary_restrictions, calories, banned_items
    )

    facts_block = ""
    if retrieval_batch:
        block = retrieval_batch.to_prompt_block()
        if block:
            facts_block = block + "\n\n"

    calorie_line = ""
    if calorie_rules:
        bullet_lines = "\n        ".join(f"- {rule}" for rule in calorie_rules)
        calorie_line = f"Calorie goals:\n        {bullet_lines}\n\n"

    body = dedent(f"""
        You generate meal recipes. All calorie and macro math happens in the backend; never estimate totals yourself.

        Return ONLY valid JSON using this schema:
        {SCHEMA}

        Make exactly {num_breakfast} breakfast, {num_lunch} lunch, and {num_dinner} dinner recipes.

        Hard requirements:
        1) Before listing any ingredient, call lookupIngredient({{"ingredient":"<plain term>"}}).
           Use the tool output only to confirm ingredient suitability and portion sizes.
        2) If an ingredient has no tool facts, swap it for a similar ingredient that does.
        3) Lead with a kitchen-friendly measure when reasonable (cups, tbsp, tsp, slices, pieces, etc.), then append grams AND ounces in parentheses, e.g. "1 cup cooked quinoa (185 g | 6.5 oz)" or "2 tbsp olive oil (27 g | 0.95 oz)".
        4) Set "calories", "carbs", "fats", and "protein" to 0 for every meal. The backend overwrites these with USDA math.
        5) Keep JSON strict: no comments, no trailing commas, no prose outside the JSON.

        {calorie_line}Quality rules:
        - Use 4–10 ingredients per meal with numbered, concise instructions.
        - Maximize variety across meals (cuisines, proteins, grains, veggies).
        - Favor fresh, whole ingredients you’d grab from a standard Smith’s/Kroger; only use canned or powdered items when they’re pantry staples (e.g., tomatoes, beans) and never as the hero ingredient.
        - Avoid banned ingredients if any are listed. {constraint_text}
        - {banned_rule}

        If tool results contradict your plan, adjust the ingredients before emitting JSON instead of guessing.
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
    if age is not None:
        parts.append(f"age={age}")
    diet = _get(user, "dietary_restrictions", "diet", "dietary")
    if diet:
        parts.append(f"diet={diet}")
    dislikes = _get(user, "disliked_ingredients", "dislikes")
    if dislikes:
        if isinstance(dislikes, (list, tuple, set)):
            parts.append("disliked=" + ", ".join(map(str, dislikes)))
        else:
            parts.append(f"disliked={dislikes}")
    allergies = _get(user, "allergies", "allergy")
    if allergies:
        parts.append("allergies=" + (
            ", ".join(allergies) if isinstance(allergies, (list, tuple)) else str(allergies)
        ))
    prefs = _get(user, "prefs", "preferences")
    if prefs:
        parts.append("prefs=" + str(prefs))

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
    if ufrag:
        header += ufrag + "\n"
    if constraint_lines:
        header += "Constraints: " + "; ".join(constraint_lines) + "\n"

    return header + body
