# load environment variables first
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, render_template
import logging

# Database
from User_Auth.database import db

# Classes and Models
from User_Auth.user_auth import UserModel
from User_Auth.user_profile import UserProfile
from Classes.User import User
from Classes.Meal import Meal
from Classes.Ingredient import Ingredient
from Classes.MealPlan import MealPlan
from Classes.GroceryList import GroceryList

# AI imports
from AI.promptGen import generate_prompt
from AI.callModel import call_model

# Routes
from Feed.feed import register_feed_routes
from User_Auth.user_auth import register_auth_routes

# Flask app setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///prepify.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your-secret-key'

logging.basicConfig(level=logging.DEBUG)

# Initialize DB with app
db.init_app(app)

# Register routes
register_feed_routes(app)
register_auth_routes(app)


# Ensure tables are created
with app.app_context():
    # db.session.remove() # Uncomment this if you want to delete all data each time you run
    # db.drop_all()       # Uncomment this if you want to delete all data each time you run
    db.create_all()  # This will create all tables for imported models

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_started")
def get_started():
    return render_template("get_started.html")

@app.route("/shopping_list")
def shopping_list():
    return render_template("shopping_list.html")

@app.route("/calendar")
def calendar():
    return render_template("calendar.html")

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