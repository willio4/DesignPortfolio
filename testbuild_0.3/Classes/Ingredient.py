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
    
    def toString(self):
        return f"{self.ingredientID} {self.name}/s"
