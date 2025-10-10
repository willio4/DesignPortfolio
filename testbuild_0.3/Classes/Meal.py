# Kenny
# toDO:
# set constructor , see UML diagram for more
# main focus is display recipe method, ensure each Ingredient is printed line by line using the toString method
# from the Ingredient class
# besure to print the meal name as well

# use the get nutritional info method to return the calories of the meal as an integer and any other health related info if we have it

from Classes import Ingredient

class Meal:
    def __init__(self, mealType: str, name: str, ingredients: Ingredient, calories: int, instructions: str, carbs: int, fat: int, protein: int):
        self.mealType = mealType            # added: breakfast, lunch, dinner
        self.name = name                    # name of meal
        self.ingredients = ingredients      # list of ingredients
        self.calories = calories            # calories per meal
        self.instructions = instructions    # cooking instructions for each meal
        self.carbs = carbs                  ## Macronutrients
        self.fats = fat                     ##
        self.protein = protein              ##
        
    # Neatly displays the name, ingredients and instructions of meal object
    def displayMeal(self):
        print()
        print(f"Name: {self.name}")
        print("  Ingredients:")
        for ing in self.ingredients:
            print(f"    {ing}")
        print(f"  Instructions: {self.instructions}")
        print()
        
    # neatly displays the macros of each meal object
    def displayMacros(self):
        print(f"  Calories: \t{self.calories}g")
        print(f"  Total Carbs: \t{self.carbs}g")
        print(f"  Total Fat: \t{self.fats}g")
        print(f"  Protein: \t{self.protein}g")
        

