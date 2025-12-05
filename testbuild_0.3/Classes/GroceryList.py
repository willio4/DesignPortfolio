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
        """
        Initialize a GroceryList.

        :param listID: Unique identifier for this grocery list.
        :param user: User this grocery list belongs to.
        :param ingredients: Optional starting list of Ingredient objects.
        """
        self.listID = listID
        self.user = user
        self.ingredients = ingredients if ingredients is not None else []

    def generateFromMealPlan(self, mealPlan: MealPlan) -> None:
        """
        Populate the grocery list from the given MealPlan.

        Combines duplicate ingredients by increasing their quantity.
        """
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
        """
        Print the grocery list to the console in a readable format.
        """
        print(f"\nGrocery List ID: {self.listID}")
        print(f"User: {self.user}")
        print("=" * 30)
        if not self.ingredients:
            print("No ingredients found.")
            return

        for ingredient in self.ingredients:
            print(f"{ingredient.quantity} {ingredient.unit} of {ingredient.name}")
        print("=" * 30)
