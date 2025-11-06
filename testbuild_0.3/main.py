# load environment variables first
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, render_template,session
import logging
from Utility.ingredient_utils import normalize_meals
from Utility.mealSaver import saveNewMeals,generatemealIDs,addMealToCollection,createNewCollection

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
from AI import constraints_store as cs
from AI import constraints_db as cdb

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
    # db.create_all()  # This will create all tables for imported models
    pass

# Routes
@app.route("/")
def index():


@app.route('/save_meals', methods=['POST'])
def save_meals():
    data = request.get_json()
    meal_ids = data.get('meal_ids', [])
    
    try:
        print("Saving meals:", meal_ids)
        for id in meal_ids:
            addMealToCollection(session['user_id'],collection_name,id)

        return jsonify({"status": "success", "saved": meal_ids}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get_started")
def get_started():
    if 'user_id' not in session:
        return render_template('signup.html')
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
    # Tess TO DO:
    # modify to be able to read global user preferences
    # merge final constraints
    # pass merged constraints into promptGen.generate_prompt(final_constraints)
    if request.method == 'GET':
        return render_template("mealGen.html")

    # Log the received form data
    form_prefs = dict(request.form)
    logging.debug(f"Received form data: {form_prefs}")

    # Load stored global constraints and user-specific constraints (if logged in)
    global_constraints = cs.get() or {}
    user_constraints = {}
    user_id = session.get('user_id')
    if user_id:
        try:
            user_constraints = cdb.get_user_constraints(int(user_id)) or {}
        except Exception:
            logging.exception("Failed to load user constraints")

    # Merge constraints (pure function; does not persist)
    merged_prefs = cs.merge_constraints(global_constraints, user_constraints, form_prefs)
    logging.debug("Merged preferences used for prompt: %s", merged_prefs)

    # Generate the prompt and log it
    prompt = generate_prompt(merged_prefs)
    logging.debug(f"Generated prompt: {prompt}")

    # Call the model and log the response
    data = call_model(prompt)
    logging.debug(f"Model response: {data}")

    # Normalize meals (ingredients and instructions) using Utility helper
    if data and isinstance(data, dict):
        meals = data.get("meals", []) or []
        normalize_meals(meals)

    ids=generatemealIDs(session["user_id"],len(data)) # generate ids for the meals for ui and databse
    # data["meals"]["id"]=ids # add to json
    ctr=0
    for m in data["meals"]:
        data["meals"][ctr]["id"]=ids[ctr]
        ctr+=1

    saveNewMeals(session["user_id"],data) # saves the meals to database

    return render_template("results.html", data=data)

if __name__ == "__main__":
    app.run(debug=True)