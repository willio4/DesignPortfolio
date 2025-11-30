# load environment variables first
from __future__ import annotations

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
from AI.retriever import (
    DEFAULT_STUB_STORE,
    StubIngredientRetriever,
    USDAIngredientRetriever,
)
from AI.usda_client import USDAFoodDataClient

# Routes
from Feed.feed import register_feed_routes
from User_Auth.user_auth import register_auth_routes

# Flask app setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///prepify.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your-secret-key'

logging.basicConfig(level=logging.DEBUG)
_GRAM_UNITS = {'g', 'gram', 'grams'}
_OZ_UNITS = {'oz', 'ounce', 'ounces'}
_WEIGHT_PATTERN = re.compile(r'(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>g|gram|grams|oz|ounce|ounces)\b', re.IGNORECASE)

_STOPWORDS = {
    'fresh', 'chopped', 'minced', 'diced', 'large', 'small', 'medium',
    'sliced', 'fillet', 'fillets', 'boneless', 'skinless', 'ground',
    'lean', 'ripe', 'whole', 'pieces', 'halved', 'to', 'taste',
    'cup', 'cups', 'tbsp', 'tablespoon', 'tablespoons', 'tsp', 'teaspoon',
    'teaspoons', 'ounce', 'ounces', 'oz', 'gram', 'grams', 'g', 'lb', 'pound',
    'pounds'
}

_CONDIMENT_TERMS = {
    'salt', 'pepper', 'salt pepper', 'black pepper', 'seasoning',
    'seasonings', 'spice blend', 'herb blend'
}


def _init_retriever() -> StubIngredientRetriever | USDAIngredientRetriever:
    choice = (os.getenv("INGREDIENT_RETRIEVER") or "stub").strip().lower()
    if choice == "usda":
        api_key = os.getenv("USDA_API_KEY", "").strip()
        if not api_key:
            logging.warning("INGREDIENT_RETRIEVER=usda but USDA_API_KEY is not set; falling back to stub data")
        else:
            client = USDAFoodDataClient(api_key=api_key)
            page_size = int(os.getenv("USDA_PAGE_SIZE", "3") or 3)
            logging.info("Using USDAIngredientRetriever (page_size=%s)", page_size)
            return USDAIngredientRetriever(client=client, page_size=page_size)

    logging.info("Using StubIngredientRetriever")
    return StubIngredientRetriever(DEFAULT_STUB_STORE)


INGREDIENT_RETRIEVER = _init_retriever()


def _extract_weight_details(text: str | None) -> tuple[float | None, bool, bool]:
    """Return (grams, has_grams, has_ounces) parsed from text."""
    if not text:
        return None, False, False

    grams_from_grams = None
    grams_from_ounces = None
    has_grams = False
    has_ounces = False

    for match in _WEIGHT_PATTERN.finditer(text):
        try:
            value = float(match.group('value'))
        except (TypeError, ValueError):
            continue
        unit = (match.group('unit') or '').lower()
        if unit in _GRAM_UNITS:
            has_grams = True
            grams_from_grams = value
        elif unit in _OZ_UNITS:
            has_ounces = True
            grams_from_ounces = value * 28.3495

    grams = grams_from_grams
    if grams is None and grams_from_ounces is not None:
        grams = grams_from_ounces

    return grams, has_grams, has_ounces


def _extract_weight_from_text(text: str | None) -> float | None:
    grams, _, _ = _extract_weight_details(text)
    return grams


def _parse_ingredient_weight(ingredient) -> tuple[float | None, bool, bool, str]:
    """Return (grams, has_grams, has_ounces, display_name) for an ingredient entry."""
    grams = None
    has_grams = False
    has_ounces = False
    display_name = ''
    raw_text = ''

    if isinstance(ingredient, dict):
        parts = [ingredient.get('name'), ingredient.get('raw'), ingredient.get('note')]
        raw_text = " ".join(filter(None, parts)).strip()
        display_name = ingredient.get('name') or ingredient.get('raw') or ''

        if ingredient.get('weight_g') not in (None, ''):
            try:
                grams = float(ingredient['weight_g'])
                has_grams = True
            except (TypeError, ValueError):
                grams = None

        if ingredient.get('weight_oz') not in (None, ''):
            try:
                oz_val = float(ingredient['weight_oz'])
                has_ounces = True
                if grams is None:
                    grams = oz_val * 28.3495
            except (TypeError, ValueError):
                pass
    else:
        raw_text = str(ingredient)
        display_name = raw_text

    parsed_grams, parsed_has_g, parsed_has_oz = _extract_weight_details(raw_text or display_name)
    if grams is None and parsed_grams is not None:
        grams = parsed_grams
    has_grams = has_grams or parsed_has_g
    has_ounces = has_ounces or parsed_has_oz

    return grams, has_grams, has_ounces, display_name or raw_text


def _has_explicit_weight(ingredient) -> bool:
    grams, has_grams, has_ounces, _ = _parse_ingredient_weight(ingredient)
    # Accept if either grams or ounces are present so macros can be derived.
    return grams is not None and (has_grams or has_ounces)


def _extract_ingredient_parts(ingredient) -> tuple[float | None, str | None, str]:
    grams, _, _, name = _parse_ingredient_weight(ingredient)
    name = name or (str(ingredient) if ingredient is not None else '')
    return grams, 'g' if grams is not None else None, name


def _normalize_term(name: str) -> str:
    text = (name or '').lower()
    text = re.sub(r'\([^)]*\)', ' ', text)
    text = re.sub(r'[^a-z\s]', ' ', text)
    tokens = [tok for tok in text.split() if tok and tok not in _STOPWORDS]
    return ' '.join(tokens[:4]).strip()


def apply_usda_macros(meals: list[dict]) -> None:
    if not meals or INGREDIENT_RETRIEVER is None:
        return

    cache: dict[str, object | None] = {}

    for meal in meals:
        totals = {'calories': 0.0, 'protein': 0.0, 'carbs': 0.0, 'fats': 0.0}
        matched = False
        contributions: list[dict[str, float | str]] = []

        for ingredient in meal.get('ingredients') or []:
            quantity, unit, name = _extract_ingredient_parts(ingredient)
            if unit != 'g' or quantity is None:
                continue

            term = _normalize_term(name)
            if not term or term in _CONDIMENT_TERMS:
                continue

            if term not in cache:
                try:
                    batch = INGREDIENT_RETRIEVER.fetch([term])
                except Exception:
                    logging.exception('USDA lookup failed for %s', term)
                    cache[term] = None
                    continue
                cache[term] = batch.facts[0] if batch.facts else None

            fact = cache[term]
            if not fact:
                continue

            serving_size = fact.nutrition.serving_size_g or 100.0
            scale = max(quantity, 0.0) / serving_size if serving_size else 1.0
            matched = True

            cal = fact.nutrition.calories * scale
            protein = fact.nutrition.protein_g * scale
            carbs = fact.nutrition.carbs_g * scale
            fats = fact.nutrition.fats_g * scale

            totals['calories'] += cal
            totals['protein'] += protein
            totals['carbs'] += carbs
            totals['fats'] += fats

            contributions.append({
                'ingredient': term,
                'grams': round(quantity, 1),
                'calories': round(cal, 1),
            })

        if matched:
            meal['calories'] = int(round(totals['calories']))
            meal['protein'] = int(round(totals['protein']))
            meal['carbs'] = int(round(totals['carbs']))
            meal['fats'] = int(round(totals['fats']))

            logging.debug(
                'USDA breakdown for %s: total=%s kcal contributions=%s',
                meal.get('name'),
                meal.get('calories'),
                contributions,
            )

# Initialize DB with app
db.init_app(app)

# Register routes
register_feed_routes(app)
register_auth_routes(app)


# Ensure tables are created
with app.app_context():
    # db.session.remove() # Uncomment this if you want to delete all data each time you run
    # db.drop_all()       # Uncomment this if you want to delete all data each time you run
    try:
        db.create_all()  # Ensure required tables (collections, etc.) exist before requests
    except Exception:
        logging.exception('Database initialization failed')

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
            for collction in collections:
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

    # Gather list-style preferences before flattening
    favorite_terms = [f.strip().lower() for f in request.form.getlist("favorites[]") if f.strip()]

    # Log the received form data
    form_prefs = request.form.to_dict(flat=True)
    selected_diets = [d.strip().lower() for d in request.form.getlist("dietary") if d.strip()]
    if selected_diets:
        # store the first one for compatibility; remainder are handled when we build banned lists
        form_prefs["dietary_restrictions"] = selected_diets[0]
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

    banned_terms = [str(x).strip().lower() for x in (merged_prefs.get("banned_ingredients") or []) if str(x).strip()]
    if selected_diets:
        extra_banned = cs.banned_for_diets(selected_diets)
        if extra_banned:
            existing = set(banned_terms)
            for term in extra_banned:
                low = term.strip().lower()
                if low and low not in existing:
                    banned_terms.append(low)
                    existing.add(low)

    def _find_banned_hit(ingredients):
        """Return (banned_term, ingredient_text) if any normalized ingredient violates banned constraints."""
        if not banned_terms:
            return (None, None)

        plant_milk_allow = (
            'almond milk', 'soy milk', 'oat milk', 'coconut milk',
            'cashew milk', 'hemp milk', 'pea milk', 'rice milk'
        )

        for ing in ingredients or []:
            if isinstance(ing, dict):
                text = " ".join(filter(None, [ing.get("name"), ing.get("raw"), ing.get("note")]))
            else:
                text = str(ing)
            haystack = text.lower()
            for banned in banned_terms:
                if banned and banned in haystack:
                    if banned == 'milk' and any(alt in haystack for alt in plant_milk_allow):
                        # Allow plant-based milks even when "milk" is banned for vegan diets
                        continue
                    return banned, text.strip() or text
        return (None, None)

    retrieval_batch = None
    if favorite_terms:
        try:
            retrieval_batch = INGREDIENT_RETRIEVER.fetch(favorite_terms)
            logging.debug("Retrieved ingredient facts: %s", retrieval_batch.to_dict())
        except Exception:
            logging.exception("Ingredient retrieval failed")

    # Generate the prompt and log it
    prompt = generate_prompt(merged_prefs, retrieval_batch=retrieval_batch)
    logging.debug(f"Generated prompt: {prompt}")

    def _safe_count(value):
        try:
            return max(0, int(value))
        except Exception:
            return 0

    desired_counts = {
        'breakfast': _safe_count(merged_prefs.get('num_breakfast', merged_prefs.get('num1'))),
        'lunch': _safe_count(merged_prefs.get('num_lunch', merged_prefs.get('num2'))),
        'dinner': _safe_count(merged_prefs.get('num_dinner', merged_prefs.get('num3'))),
    }
    total_needed = sum(desired_counts.values())

    def _normalize_meal_type(tag: str | None) -> str:
        t = (tag or '').strip().lower()
        if t.startswith('breakfast'):
            return 'breakfast'
        if t.startswith('lunch'):
            return 'lunch'
        if t.startswith('dinner'):
            return 'dinner'
        return ''

    MAX_MODEL_ATTEMPTS = 2
    attempt = 0
    meals: list[dict] = []
    data: dict = {"meals": []}

    while True:
        raw_data = call_model(prompt)
        if not isinstance(raw_data, dict):
            logging.warning('Model returned invalid payload (attempt %s): %r', attempt + 1, raw_data)
            raw_data = {}

        partial_response = bool(raw_data.pop('_partial', False))
        logging.debug("Model response (attempt %s): %s", attempt + 1, raw_data)

        data = raw_data or {"meals": []}
        meals = data.get("meals", []) or []

        try:
            normalize_meals(meals)
        except Exception:
            logging.exception('normalize_meals failed')

        cleaned: list[dict] = []
        dropped_for_weight = 0
        for m in meals:
            if not isinstance(m, dict):
                logging.warning('Skipping non-dict meal: %r', m)
                continue

            name = (m.get('name') or '').strip() or '(Untitled)'
            m['name'] = name
            m['mealType'] = (m.get('mealType') or '').strip()

            for k in ('calories', 'carbs', 'fats', 'protein'):
                v = m.get(k)
                try:
                    if v in (None, ''):
                        m[k] = 0
                    elif isinstance(v, str):
                        num = re.sub(r'[^0-9\.\-]', '', v)
                        m[k] = int(float(num)) if num else 0
                    else:
                        m[k] = int(float(v))
                except Exception:
                    m[k] = 0

            new_ings = []
            for ig in (m.get('ingredients') or []):
                if isinstance(ig, dict):
                    if (ig.get('name') or '').strip() or ig.get('quantity') is not None:
                        new_ings.append(ig)
                elif isinstance(ig, str):
                    if ig.strip() and ig.strip() != '-':
                        new_ings.append(ig.strip())
            m['ingredients'] = new_ings

            missing_weight = next((ig for ig in new_ings if not _has_explicit_weight(ig)), None)
            if missing_weight is not None:
                logging.warning('Dropping %s because ingredient lacks explicit g/oz weight: %r', name, missing_weight)
                dropped_for_weight += 1
                continue

            banned_term, offending = _find_banned_hit(new_ings)
            if banned_term:
                logging.warning('Dropping %s because it contains banned ingredient "%s" (matched term "%s")', name, offending, banned_term)
                continue

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

        if total_needed and meals:
            counts = {k: 0 for k in desired_counts}
            limited: list[dict] = []
            for meal in meals:
                if len(limited) >= total_needed:
                    break
                mtype = _normalize_meal_type(meal.get('mealType'))
                if mtype and counts[mtype] >= desired_counts[mtype]:
                    continue
                if mtype:
                    counts[mtype] += 1
                limited.append(meal)
            meals = limited

        data['meals'] = meals

        need_retry = False
        if not meals and dropped_for_weight and attempt < (MAX_MODEL_ATTEMPTS - 1):
            logging.warning(
                'All meals rejected for missing ingredient weights; retrying attempt %d/%d',
                attempt + 1, MAX_MODEL_ATTEMPTS
            )
            need_retry = True
        elif total_needed and len(meals) < total_needed and attempt < (MAX_MODEL_ATTEMPTS - 1):
            logging.warning(
                'Generated %d/%d meals (partial=%s); retrying attempt %d/%d',
                len(meals), total_needed, partial_response, attempt + 1, MAX_MODEL_ATTEMPTS
            )
            need_retry = True

        if need_retry:
            attempt += 1
            continue

        break

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

    try:
        apply_usda_macros(meals)
    except Exception:
        logging.exception('Failed to overwrite macros with USDA data')

    # save if logged in
    try:
        if uid and meals:
            saveNewMeals(uid, data)
    except Exception:
        logging.exception('Failed to save new meals')

    if uid:
        collections = getUserMeals(uid)
    else:
        collections = []
    return render_template("results.html", data=data,collections=collections) # pass data to ui


if __name__ == "__main__":
    app.run(debug=True)