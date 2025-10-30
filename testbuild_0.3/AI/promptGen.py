# ------------------------ Tess -------------------------------

from textwrap import dedent
# import constraints_store as cs

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
    # test to make sure constraits works
    # cs.update({"favorite_grocery_store": "Walmart"})

    # get constraints from constraints store
    # constraints = cs.get()
    # {
    #     "favorite_grocery_store": "Walmart"
    # }
    # add test constraints here if needed
    # extract relevant preferences
    # favorite_grocery_store = constraints.get("favorite_grocery_store", "any")
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
          4. Provide clear, step-by-step cooking instructions. Each instruction should be
          placed on its own line and numbered sequentially.
          5. Each ingredient entry MUST include a quantity and a unit where appropriate (for example: "2 cups cooked quinoa", "1 tsp salt", "3 oz salmon").
              Use common units (tsp, tbsp, cup, g, kg, oz, lb, slice) and prefer numeric quantities (decimals or simple fractions).
          6. Example ingredient array format (for clarity):
              ["2 slices whole grain bread", "1 ripe avocado", "1/2 cup cooked quinoa", "1 tbsp olive oil"]
          7. Ensure nutritional values (calories, carbs, fats, protein) are realistic and appropriate for the meal type.
          8. Meals should be easy to prepare with common ingredients.
          9. {'. '.join(extras) if extras else 'No specific dietary constraints.'}
          10. Avoid repetition in meal names and ingredient lists across all meals.
          11. Prioritize variety: where multiple recipes of the same mealType are requested, ensure each one differs from the others by at least two major ingredients or by cuisine/style (e.g., one Mediterranean, one Asian, one Tex-Mex).
          12. Try to vary primary proteins, grains, vegetables, and dominant flavors across meals to maximize diversity.
          13. If possible, limit overlap of the top 3 ingredients between any two meals.
          14. JSON only, no extra text.
    """).strip()

