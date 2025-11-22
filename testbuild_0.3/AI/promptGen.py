# ------------------------ Tess -------------------------------

from textwrap import dedent
from typing import Any

# local import from this package
from . import constraints_store

# Todo: increase complexity of prompt as needed
# schema - what we want the model to return
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
# To Do: update to accept merged dict and include a sort section
# in the prompt showing the constraints that have been applied 
# log the merged constraints within the prompt in `main.py` before calling the model
def generate_prompt(merged_constraints: dict | None = None) -> str:
    """
    Generate the model prompt body from a merged/sanitized constraints dict.

    This function expects a dict already produced by
    `constraints_store.merge_constraints(...)` (i.e. values are coerced and
    normalized). It performs only minimal, last-resort coercion for safety.
    """
    prefs = merged_constraints or {}

    # prefer explicit, descriptive keys if present; fallback to legacy keys
    dietary_restrictions = prefs.get("dietary_restrictions") or prefs.get("diet") or "none"
    num_breakfast = safe_int(prefs.get("num_breakfast", prefs.get("num1", 0)))
    num_lunch = safe_int(prefs.get("num_lunch", prefs.get("num2", 0)))
    num_dinner = safe_int(prefs.get("num_dinner", prefs.get("num3", 1)))

    calories = safe_int(prefs.get("calories", 0))
    banned_items = [str(x).strip() for x in (prefs.get("banned_ingredients") or []) if str(x).strip()]

    extras = []
    if isinstance(dietary_restrictions, str) and dietary_restrictions.strip():
        if dietary_restrictions.lower() != "none":
            extras.append(f"Dietary constraints: {dietary_restrictions}")
    if calories > 0:
        extras.append(f"Per meal target ~{calories} calories (±10%)")
    if banned_items:
        preview = ", ".join(banned_items[:12])
        if len(banned_items) > 12:
            preview += ", ..."
        extras.append(f"Forbidden ingredients: {preview}. Never include them.")

    constraint_text = '. '.join(extras) if extras else 'No specific dietary constraints.'
    banned_rule = (
        "No additional banned ingredients beyond the general constraints."
        if not banned_items else
        "Absolutely DO NOT use any of the banned ingredients listed above in any recipe."
    )

    return dedent(f"""
        You are a recipe generator that focuses on healthy, and delicious meals.
        Return ONLY valid JSON with the exact schema: {SCHEMA}

          Requirements:
          1. Generate {num_breakfast} breakfast, {num_lunch} lunch, and {num_dinner} dinner recipes.
          2. Set mealType correctly for each meal.
          3. Each meal should have a unique name and a list of ingredients.
          4. Provide clear, step-by-step cooking instructions. Each instruction should be
          placed on its own line and numbered sequentially.
          5. Each ingredient entry MUST include a quantity and a unit where appropriate (for example: "2 cups cooked quinoa", "1 tsp salt", "3 oz salmon").
              Use common units (tsp, tbsp, cup, g, kg, oz, lb, slice) and prefer numeric quantities (decimals or simple fractions).
          6. Example ingredient array format (for clarity):
              ["2 slices whole grain bread", "1 ripe avocado", "1/2 cup cooked quinoa", "1 tbsp olive oil"]
          7. Ensure nutritional values (calories, carbs, fats, protein) are realistic and appropriate for the meal type.
          8. Meals should be easy to prepare with common ingredients.
          9. {constraint_text}
          10. {banned_rule}
          11. Avoid repetition in meal names and ingredient lists across all meals.
          12. Prioritize variety: where multiple recipes of the same mealType are requested, ensure each one differs from the others by at least two major ingredients or by cuisine/style (e.g., one Mediterranean, one Asian, one Tex-Mex).
          13. Try to vary primary proteins, grains, vegetables, and dominant flavors across meals to maximize diversity.
          14. If possible, limit overlap of the top 3 ingredients between any two meals.
          15. JSON only, no extra text.
    """).strip()


def user_to_prompt(user: Any) -> str:
    """
    Convert a User instance or dict into a short, human-readable prompt fragment.

    Accepts dicts, objects with attributes, or None. Returns an empty string when
    no usable fields are found.
    """
    if not user:
        return ""

    def _get(o, *names, default=None):
        for n in names:
            if isinstance(o, dict) and n in o:
                return o[n]
            if hasattr(o, n):
                return getattr(o, n)
        return default

    parts: list[str] = []
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
        parts.append("allergies=" + (", ".join(allergies) if isinstance(allergies, (list, tuple)) else str(allergies)))
    prefs = _get(user, "prefs", "preferences")
    if prefs:
        parts.append("prefs=" + str(prefs))

    if not parts:
        return ""
    return "User profile: " + "; ".join(parts)


def build_prompt(user: Any = None,
                 global_constraints: dict | None = None,
                 user_constraints: dict | None = None,
                 prefs: dict | None = None) -> str:
    """
    Build the full model prompt by merging constraints and including a short
    user fragment.

    - Merges constraints with precedence: prefs > user_constraints > global_constraints
    - Calls `generate_prompt` with the merged constraints to produce the body
    - Prepends a human-readable user fragment and a short constraints summary
    """
    merged = constraints_store.merge_constraints(global_constraints, user_constraints, prefs)

    ufrag = user_to_prompt(user)

    constraint_lines: list[str] = []
    if merged.get("dietary_restrictions"):
        constraint_lines.append(f"diet: {merged['dietary_restrictions']}")
    if merged.get("disliked_ingredients"):
        constraint_lines.append("dislikes: " + ", ".join(merged["disliked_ingredients"]))
    if merged.get("calories"):
        constraint_lines.append(f"max_calories: {merged['calories']}")
    if merged.get("banned_ingredients"):
        banned_preview = ", ".join(merged["banned_ingredients"][:6])
        if len(merged["banned_ingredients"]) > 6:
            banned_preview += ", ..."
        constraint_lines.append(f"banned: {banned_preview}")

    body = generate_prompt(merged)

    header = ""
    if ufrag:
        header += ufrag + "\n"
    if constraint_lines:
        header += "Constraints: " + "; ".join(constraint_lines) + "\n"

    return header + body

