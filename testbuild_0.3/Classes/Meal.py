#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ OMAR W ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
        
    # used class method to be able to create meal objects
    @classmethod
    def create_meals_from_output(cls, llm_output):
        data = json.loads(llm_output)       # parses JSON text into objects
        meal_plan = []                      # list of meals as a meal plan
        
        # loop that iterates through each meal from llm output
        for meal_data in data["meals"]:     
            ingredients = create_ingredients_from_output(meal_data["ingredients"]) # create ingredient objects. may need to rename function once implemented
            # creates meal object from JSON
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
            #adds meal to mealplan list
            meal_plan.append(meal)
        return meal_plan    # return mealplan to MealPlan class (hopefully)

