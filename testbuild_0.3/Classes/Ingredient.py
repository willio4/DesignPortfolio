# Pat
# toDO:
# set constructor , see UML diagram for more
# for toString method just return a string the format '<nOfIngredient> <IngredientName> (s)'
class Ingredient:
    def __init__(self, ingredientID: int, name: str, quantity: float, unit: str):
        self.ingredientID = ingredientID
        self.name = name
        self.quantity = quantity
        self.unit = unit
        
    # Added __str__ method to Ingredient for easy display of name, quantity, and unit without extra formatting in Meal.displayMeal
    def __str__(self):
        return f"{self.name} {self.quantity} {self.unit}"
    
    # keep toString removed in favor of __str__ (Java-style method removed)

# added helper function to create the ingredient object from model output
def create_ingredients_from_output(items):
    """Convert model output into a list of Ingredient objects.

    Accepts either:
      - a list of strings (e.g. "1 cup rice")
      - a list of dicts with keys: name, quantity, unit (optional)

    This is intentionally forgiving: if the model returns simple strings we pack
    them into Ingredient objects using the string as the name and default
    quantity/unit values. If dicts are provided we use those fields.
    """
    result = []
    if not items:
        return result

    for idx, it in enumerate(items):
        if isinstance(it, dict):
            name = it.get("name") or it.get("ingredient") or str(it)
            try:
                quantity = float(it.get("quantity", 1))
            except Exception:
                quantity = 1
            unit = it.get("unit", "")
        else:
            # treat as a free-form string
            name = str(it)
            quantity = 1
            unit = ""

        result.append(Ingredient(ingredientID=idx, name=name, quantity=quantity, unit=unit))

    return result
