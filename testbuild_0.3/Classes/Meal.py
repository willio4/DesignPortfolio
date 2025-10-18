# Kenny
# toDO:
# set constructor , see UML diagram for more
# main focus is display recipe method, ensure each Ingredient is printed line by line using the toString method
# from the Ingredient class
# besure to print the meal name as well

# use the get nutritional info method to return the calories of the meal as an integer and any other health related info if we have it

from Ingredient import Ingredient
from enum import Enum
from typing import List

class MealType(Enum):
    BREAKFAST = 1
    LUNCH = 2
    DINNER = 3
    SNACK = 4

class Meal:
    def __init__(self, meal_type: MealType, name: str, ingredients: List[Ingredient], calories: int, instructions: str, carbs: int, fats: int, protein: int):
        self.meal_type = meal_type          # added: breakfast, lunch, dinner
        self.name = name                    # name of meal
        self.ingredients = ingredients      # list of ingredients
        self.calories = calories            # calories per meal
        self.instructions = instructions    # cooking instructions for each meal
        self.carbs = carbs                  ## Macronutrients
        self.fats = fats                    ##
        self.protein = protein              ##
        
    # Neatly displays the name, ingredients and instructions of meal object
    def display_meal(self):
        print()
        print(f"Name: {self.name}")
        print("  Ingredients:")
        for ing in self.ingredients:
            print(f"    {ing}")
        print(f"  Instructions: {self.instructions}")
        print()
        
    # neatly displays the macros of each meal object
    def display_macros(self):
        print(f"  Calories: \t{self.calories}")
        print(f"  Total Carbs: \t{self.carbs}g")
        print(f"  Total Fat: \t{self.fats}g")
        print(f"  Protein: \t{self.protein}g")
        
    def get_name(self):
        pass
    def get_ingredients(self):
        pass
    def get_instructions(self):
        pass
    def get_calories(self):
        pass
    def get_carbs(self):
        pass
    def get_fats(self):
        pass
    def get_protein(self):
        pass