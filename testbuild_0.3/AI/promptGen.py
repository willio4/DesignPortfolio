# ------------------------ Tess -------------------------------

from textwrap import dedent

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

def generate_prompt(preferences: dict | None = None) -> str:
    prefs = preferences or {}
    dietary_restrictions = prefs.get("dietary_restrictions", "none")
    num_breakfast = safe_int(prefs.get("num1", 0))
    num_lunch = safe_int(prefs.get("num2", 0))
    num_dinner = safe_int(prefs.get("num3", 1)) # set 1 as default just in case

    calories = safe_int(prefs.get("calories", 0))

    extras = []
    if dietary_restrictions.lower() != "none": extras.append(f"Dietary constraints: {dietary_restrictions}")
    if calories > 0: extras.append(f"Per meal target ~{calories} calories (±10%)")


    return dedent(f"""
        You are a recipe generator that focuses on healthy, and delicious meals.
        Return ONLY valid JSON with the exact schema: {SCHEMA}

        Requirements:
        1. Generate {num_breakfast} breakfast, {num_lunch} lunch, and {num_dinner} dinner recipes.
        2. Set mealType correctly for each meal.
        3. Each meal should have a unique name and a list of ingredients.
        4. Provide clear, step-by-step cooking instructions.
        5. Ensure nutritional values (calories, carbs, fats, protein) are realistic and appropriate for the meal type.
        6. Meals should be easy to prepare with common ingredients
        7. {'. '.join(extras) if extras else 'No specific dietary constraints.'}
        8. Avoid repetition in meal names and ingredients across all meals.
        JSON only, no extra text.
    """).strip()

