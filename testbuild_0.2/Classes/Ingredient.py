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
    
    def toString(self):
        return f"{self.ingredientID} {self.name}/s"
