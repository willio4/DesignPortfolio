# load environment variables first
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, render_template, abort

# Classes
from Classes.User import User
from Classes.Meal import Meal
from Classes.Ingredient import Ingredient
from Classes.MealPlan import MealPlan
from Classes.GroceryList import GroceryList
from Utility.recipeGen import generateRecipes

# AI imports
from AI.promptGen import generate_prompt
from AI.callModel import call_model

import logging

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)



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

    # Log the received form data
    prefs = dict(request.form)
    logging.debug(f"Received form data: {prefs}")

    # Generate the prompt and log it
    prompt = generate_prompt(prefs)
    logging.debug(f"Generated prompt: {prompt}")

    # Call the model and log the response
    data = call_model(prompt)
    logging.debug(f"Model response: {data}")

    return render_template("results.html", data=data)

if __name__ == "__main__":
    app.run(debug=True)



