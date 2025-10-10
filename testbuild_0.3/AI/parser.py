# ---------------------------Omar W------------------------------------
#toDO:
# parse the model results so that they are structued
# this will intake the raw text returned from the model
# return a mealplan object
# you must first understand the way the model outputs its data
# then you will need to create instances of the following objects in order to return a meal plan object
# you need to detrmine a way to figure out where each recipe in the text returned from the model begins and ends

#  parse each Ingredient of each recipe,one recipe at a time, create the Ingredient class with the correct quantity of each Ingredient
# after getting the Ingredients for each recipe create a new meal object with the ingredeints and the recipe, ensure the recipe is cleaned
# as needed
# after all meal objects are created add them to a new mealPlan object and return it from the function
from Classes import Meal
from Classes import MealPlan
from Classes import Ingredient
from Classes import User
import re

def parseModelResults(user: User, response: str):
    meals = re.split(r"(?=## )", response) # each meal gets assigned to a chunk
    for meal_text in meals:
        if meal_text.strip():
            print("Meal chunk:")
            print(meal_text)
        
    