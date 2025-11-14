# load environment variables first
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request, render_template,session
import logging
import re
from Utility.ingredient_utils import normalize_meals
from Utility.mealSaver import saveNewMeals,generatemealIDs,addMealToCollection,createNewCollection,getCollections,getUserMeals

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
    return render_template("index.html")  # Replace "index.html" with the appropriate template if needed


@app.route('/save_meals', methods=['POST'])
def save_meals():
    data = request.get_json()
    meal_ids = data.get('meal_ids', [])
    collections=data.get('collections',[])
    try:
        print("Saving meals:", meal_ids)
        for id in meal_ids:
            for collction in collecitons:
            # collection_name = "default_collection"  # Define a default collection name or retrieve it dynamically
                addMealToCollection(session['user_id'], collction, id)

        return jsonify({"status": "success", "saved": meal_ids}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/create_collection',methods=['POST'])
def create_collection():
    data=request.get_json()
    collectionName=data.get('name')
    collectionCreated=createNewCollection(session['user_id'],collectionName)
    if collectionCreated==False:
        return jsonify({
        "success": False,
        "message": f"Collection '{collectionName}' was already created!"
    })
    else:
        return jsonify({
        "success": True,
        "message": f"Collection '{collectionName}' was created successfully!"
    })



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

    # Defensive: ensure we have a dict with a meals list
    if not data or not isinstance(data, dict):
        logging.warning('Model returned invalid data: %r', data)
        return render_template("results.html", data={"meals": []})

    meals = data.get("meals", []) or []
    # normalize ingredients and instructions in-place
    try:
        normalize_meals(meals)
    except Exception:
        logging.exception('normalize_meals failed')

    # sanitize and filter meals: ensure name, ingredients, and numeric nutrition
    cleaned = []
    for m in meals:
        if not isinstance(m, dict):
            logging.warning('Skipping non-dict meal: %r', m)
            continue
        # normalize name
        name = (m.get('name') or '').strip()
        if not name:
            name = '(Untitled)'
        m['name'] = name

        # mealType normalization (keep original if present)
        m['mealType'] = (m.get('mealType') or '').strip()


        # coerce nutrition fields
        for k in ('calories', 'carbs', 'fats', 'protein'):
            v = m.get(k)
            try:
                if v in (None, ''):
                    m[k] = 0
                else:
                    if isinstance(v, str):
                        num = re.sub(r'[^0-9\.\-]', '', v)
                        m[k] = int(float(num)) if num else 0
                    else:
                        m[k] = int(float(v))
            except Exception:
                m[k] = 0

        # clean ingredients: remove empty entries
        new_ings = []
        for ig in (m.get('ingredients') or []):
            if isinstance(ig, dict):
                if (ig.get('name') or '').strip() or ig.get('quantity') is not None:
                    new_ings.append(ig)
            elif isinstance(ig, str):
                if ig.strip() and ig.strip() != '-':
                    new_ings.append(ig.strip())
        m['ingredients'] = new_ings

        # normalize instructions to a list
        instr = m.get('instructions')
        if instr is None:
            m['instructions'] = []
        elif isinstance(instr, str):
            m['instructions'] = [ln.strip() for ln in instr.splitlines() if ln.strip()]
        elif isinstance(instr, list):
            m['instructions'] = [str(x).strip() for x in instr if str(x).strip()]

        if not m['ingredients']:
            logging.warning('Dropping meal with no ingredients: %s', m.get('name'))
            continue

        cleaned.append(m)

    meals = cleaned

    # generate ids and attach
    uid = session.get('user_id')
    try:
        ids = generatemealIDs(uid, len(meals)) if isinstance(meals, list) else []
    except Exception:
        logging.exception('generatemealIDs failed')
        ids = [f"{uid or 0}_{i+1}" for i in range(len(meals))]

    for i in range(len(meals)):
        meals[i]['id'] = ids[i]

    data['meals'] = meals

    # save if logged in
    try:
        if uid and meals:
            saveNewMeals(uid, data)
    except Exception:
        logging.exception('Failed to save new meals')

    # collections=getCollections(session["user_id"])# get the collecitons for a given user
    collections=getUserMeals(session["user_id"])
    return render_template("results.html", data=data,collections=collections) # pass data to ui


if __name__ == "__main__":
    app.run(debug=True)