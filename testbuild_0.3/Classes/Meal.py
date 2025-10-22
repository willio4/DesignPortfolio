# Kenny
# toDO:
# set constructor , see UML diagram for more
# main focus is display recipe method, ensure each Ingredient is printed line by line using the toString method
# from the Ingredient class
# besure to print the meal name as well

# use the get nutritional info method to return the calories of the meal as an integer and any other health related info if we have it

import Ingredient
import json

class Meal:
    def __init__(self, mealType: str, name: str, ingredients: Ingredient, calories: int, instructions: str, carbs: int, fats: int, protein: int):
        self.mealType = mealType            # added: breakfast, lunch, dinner
        self.name = name                    # name of meal
        self.ingredients = ingredients      # list of ingredients
        self.calories = calories            # calories per meal
        self.instructions = instructions    # cooking instructions for each meal
        self.carbs = carbs                  ## Macronutrients
        self.fats = fats                     ##
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
        print(f"  Calories: \t{self.calories}")
        print(f"  Total Carbs: \t{self.carbs}g")
        print(f"  Total Fat: \t{self.fats}g")
        print(f"  Protein: \t{self.protein}g")
        
    @classmethod
    def create_meals_from_output(cls, llm_output):
        data = json.loads(llm_output)
        meal_plan = []
        for meal_data in data["meals"]:
            ingredients = create_ingredients_from_output(meal_data["ingredients"])
            meal = cls(
                mealType=meal_data["mealType"],
                name=meal_data["name"],
                ingredients=ingredients,
                calories=meal_data["calories"],
                instructions=meal_data["instructions"],
                carbs=meal_data["carbs"],
                fats=meal_data["fats"],
                protein=meal_data["protein"],
            )
            meal_plan.append(meal)
        return meal_plan

