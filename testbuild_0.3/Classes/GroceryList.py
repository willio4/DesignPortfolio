# Kenny
# toDO:
# set constructor and methods, see UML diagram for more
# for the generate meal list method: return the Ingredient names with their quantities 
# for the display method, call the generate meal list method,
#  and print the result out to the console in a readable manner
from .Ingredient import Ingredient
from .MealPlan import MealPlan

class GroceryList:
    def __init__(self, listID: int, user, ingredients=None):
        self.listID = listID
        self.user = user
        self.ingredients = ingredients if ingredients is not None else []

    def generateFromMealPlan(self, mealPlan: MealPlan) -> None:
        ingredients_dict = {}

        for meal in mealPlan.getMealPlan():
            for ing in meal.ingredients:
                if ing.name in ingredients_dict:
                    ingredients_dict[ing.name].quantity += ing.quantity
                else:
                    ingredients_dict[ing.name] = Ingredient(
                        ing.ingredientID, ing.name, ing.quantity, ing.unit
                    )
        self.ingredients = list(ingredients_dict.values())
        
    def displayList(self) -> None:
        print(f"\nGrocery List ID: {self.listID}")
        print(f"User: {self.user}")
        print("=" * 30)
        if not self.ingredients:
            print("No ingredients found.")
            return

        for ingredient in self.ingredients:
            print(f"{ingredient.quantity} {ingredient.unit} of {ingredient.name}")
        print("=" * 30)
