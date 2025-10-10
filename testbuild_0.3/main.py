from flask import Flask, request, render_template, abort
from Classes.User import User
from Classes.Meal import Meal
from Classes.Ingredient import Ingredient
from Classes.MealPlan import MealPlan
from Classes.GroceryList import GroceryList
from Utility.recipeGen import generateRecipes
from dotenv import load_dotenv
from openai import OpenAI
import os

# load the environment variable from the .env file
# applied here after load_dotenv() to ensure API key is available first
load_dotenv()
app = Flask(__name__)
client = OpenAI()

#importing the test api route
# To test the openai connection and api key then run the server and navigate to
# http://127.0.0.1:5000/test_openai
from test_api_route import test_api
app.register_blueprint(test_api)


# Route to the homepage
# Returns the index template
@app.route("/")
def index():
    return render_template("index.html")

# main function 
# use for testing
# adjust user prefrences here
# if you add new preferences in the above classes
# be sure to add them here too
@app.route("/startMealPlan", methods = ['GET', 'POST'])
def startMealPlan():
    if request.method == 'GET':
        return render_template("mealGen.html")

    elif request.method == "POST":
        """
        testPrefs = User.MealPlanPrefs(3,2,4) # creating new meal plan preferences, 3 breakfast meals, 2 lunch, and 4 dinners
        AIrecipes = generateRecipes(testPrefs.getPrefs()) # passing the prefs to our process
        mealCtr  = 0
        for meal in AIrecipes.meals: # displaying the recipe for each meal returned by our process
            print(f"MEAL #{mealCtr}: ")
            meal.printRecipe()
            mealCtr+=1
        """
        return render_template("results.html")

if __name__ == "__main__":
    app.run(debug=True)
    


