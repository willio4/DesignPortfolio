# load environment variables first
from __future__ import annotations

import ast
import json
import os
from typing import Any, Mapping, Optional
from pathlib import Path
from dotenv import load_dotenv

# Ensure environment variables are loaded whether the app is launched from the
# project root or the testbuild directory.
load_dotenv()
load_dotenv(Path(__file__).resolve().parent / ".env")

from flask import Flask, jsonify, request, render_template, session, redirect, url_for
import logging
import re
from sqlalchemy import text
from Utility.ingredient_utils import normalize_meals
from Utility.mealSaver import getCollectionMeals,saveNewMeals,generatemealIDs,addMealToCollection,createNewCollection,getCollections,getUserMeals,getAllMeals

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
from Classes.MealCollection import MealCollection

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
from AI.retrieval_contract import IngredientFact, RetrievalBatch
from AI.usda_client import USDAFoodDataClient

# Routes
from Feed.feed import register_feed_routes
from User_Auth.user_auth import register_auth_routes

# Flask app setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://postgres.rhqtkbyizztncyrnrwvf:{os.getenv("DB_PASS")}@aws-1-us-east-1.pooler.supabase.com:5432/postgres'#'sqlite:///prepify.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your-secret-key'

logging.basicConfig(level=logging.DEBUG)
_GRAM_UNITS = {'g', 'gram', 'grams'}
_OZ_UNITS = {'oz', 'ounce', 'ounces'}
_GRAMS_PER_OUNCE = 28.3495
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

_CALORIE_OPERATOR_MAP = {
    'about': {'code': 'about', 'text': 'about'},
    'at least': {'code': 'at_least', 'text': 'at least'},
    'under': {'code': 'under', 'text': 'under'},
}

_CALORIE_SCOPE_MAP = {
    'each meal': {'type': 'per_meal', 'meal_type': None, 'label': 'each meal'},
    'each breakfast': {'type': 'per_meal', 'meal_type': 'breakfast', 'label': 'each breakfast'},
    'each lunch': {'type': 'per_meal', 'meal_type': 'lunch', 'label': 'each lunch'},
    'each dinner': {'type': 'per_meal', 'meal_type': 'dinner', 'label': 'each dinner'},
    'all meals': {'type': 'aggregate', 'meal_type': None, 'label': 'all meals'},
    'all breakfasts': {'type': 'aggregate', 'meal_type': 'breakfast', 'label': 'all breakfasts'},
    'all lunches': {'type': 'aggregate', 'meal_type': 'lunch', 'label': 'all lunches'},
    'all dinners': {'type': 'aggregate', 'meal_type': 'dinner', 'label': 'all dinners'},
}

_CALORIE_ABOUT_TOLERANCE = float(os.getenv("CALORIE_ABOUT_TOLERANCE", "0.20"))  # default ±20%
_CALORIE_MIN_DELTA = int(os.getenv("CALORIE_MIN_DELTA", "200"))  # fallback slack when targets are small (~±200 kcal)

_AUTO_FAVORITE_LIMIT = 4
_VARIETY_PRESETS = [
    {
        "label": "Mediterranean market bowls with herbs, citrus, and legumes",
        "terms": ["farro", "kalamata olives", "sumac", "chickpeas"],
    },
    {
        "label": "Latin-inspired roasted meals with smoky sauces",
        "terms": ["achiote paste", "black beans", "plantain", "chimichurri"],
    },
    {
        "label": "East Asian comfort dishes that balance umami and freshness",
        "terms": ["gochujang", "shiitake mushrooms", "soba noodles", "bok choy"],
    },
    {
        "label": "Spiced North African stews with grains and bright toppings",
        "terms": ["harissa", "preserved lemon", "pearl couscous", "chickpeas"],
    },
]


def _normalize_activity_level(raw: Optional[str]) -> str:
    if not raw:
        return "moderate"
    text = raw.strip().lower()
    if text in {"sedentary", "light", "moderate", "active", "very active"}:
        return text
    if "extra" in text:
        return "very active"
    if "very" in text:
        return "active"
    if "light" in text or "slightly" in text:
        return "light"
    if "sedentary" in text or "little" in text:
        return "sedentary"
    if "moderate" in text or "moderately" in text:
        return "moderate"
    if "vigorous" in text:
        return "active"
    return "moderate"


def _normalize_goal(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    text = raw.strip().lower()
    if "lose" in text:
        return "lose"
    if "gain" in text:
        return "gain"
    if "maintain" in text or "keep" in text:
        return "maintain"
    return text or None


def _normalize_sex(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    text = raw.strip().lower()
    if text.startswith('m'):
        return 'M'
    if text.startswith('f'):
        return 'F'
    return raw.strip()


def _safe_float(value) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value, default: Optional[int] = None) -> Optional[int]:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _user_from_form(form) -> Optional[User]:
    weight_lbs = _safe_float(form.get('weight') or form.get('weight_lbs'))
    height_total = _safe_float(form.get('height'))
    height_ft = height_in = None
    if height_total is not None and height_total > 0:
        total_inches = int(round(height_total))
        height_ft = total_inches // 12
        height_in = total_inches - height_ft * 12
    age = _safe_int(form.get('age'))
    sex = _normalize_sex(form.get('gender') or form.get('sex'))
    goal = _normalize_goal(form.get('goal'))

    if all(val in (None, "", 0) for val in (weight_lbs, height_ft, height_in, age, goal, sex)):
        return None

    return User(
        name=None,
        weight_lbs=weight_lbs,
        height_ft=height_ft,
        height_in=height_in,
        age=age,
        sex=sex,
        goal=goal,
    )


def _safe_count(value, default: int = 0) -> int:
    try:
        num = int(value)
        return max(0, num)
    except (TypeError, ValueError):
        return default


def _requested_meal_counts(prefs: Mapping[str, Any] | None) -> dict[str, int]:
    prefs = prefs or {}

    def _value(primary: str, fallback: str | None = None, default: int = 0) -> int:
        raw = prefs.get(primary)
        if (raw is None or raw == "") and fallback:
            raw = prefs.get(fallback)
        return _safe_count(raw, default=default)

    return {
        'breakfast': _value('num_breakfast', 'num1'),
        'lunch': _value('num_lunch', 'num2'),
        'dinner': _value('num_dinner', 'num3', default=1),
    }


def _dedupe_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for term in terms:
        clean = (term or '').strip()
        if not clean:
            continue
        low = clean.lower()
        if low in seen:
            continue
        seen.add(low)
        output.append(clean)
        if len(output) >= _AUTO_FAVORITE_LIMIT:
            break
    return output


def _select_variety_terms(existing_terms: list[str], desired_counts: Mapping[str, int]) -> tuple[list[str], str | None, bool]:
    trimmed = _dedupe_terms(existing_terms)
    if trimmed:
        return trimmed, None, False

    if not _VARIETY_PRESETS:
        return [], None, False

    weight = (
        desired_counts.get('breakfast', 0)
        + 2 * desired_counts.get('lunch', 0)
        + 3 * desired_counts.get('dinner', 0)
    )
    preset = _VARIETY_PRESETS[weight % len(_VARIETY_PRESETS)]
    auto_terms = preset.get('terms', [])[:_AUTO_FAVORITE_LIMIT]
    return auto_terms, preset.get('label'), True


def _deserialize_list(value):
    if value in (None, ''):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        for loader in (json.loads, ast.literal_eval):
            try:
                parsed = loader(text)
            except Exception:
                continue
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        return [text]
    return [value]
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
            grams_from_ounces = value * _GRAMS_PER_OUNCE

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
                    grams = oz_val * _GRAMS_PER_OUNCE
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


def _term_tokens(term: str) -> set[str]:
    normalized = _normalize_term(term)
    base_tokens = [tok for tok in normalized.split() if tok]
    tokens: set[str] = set()
    for tok in base_tokens:
        tokens.add(tok)
        if len(tok) > 3 and tok.endswith('es'):
            tokens.add(tok[:-2])
        elif len(tok) > 2 and tok.endswith('s'):
            tokens.add(tok[:-1])
    return tokens


def _best_cached_fact(term: str, fact_cache: dict[str, IngredientFact]) -> IngredientFact | None:
    if not fact_cache:
        return None

    direct = fact_cache.get(term)
    if direct:
        return direct

    term_tokens = _term_tokens(term)
    if not term_tokens:
        return None

    normalized = ' '.join(sorted(term_tokens))
    direct_norm = fact_cache.get(normalized)
    if direct_norm:
        return direct_norm

    best = None
    best_overlap = 0
    for key, fact in fact_cache.items():
        key_tokens = _term_tokens(key)
        if not key_tokens:
            continue
        overlap = len(term_tokens & key_tokens)
        if overlap > best_overlap:
            best = fact
            best_overlap = overlap
    return best if best_overlap else None


def _parse_calorie_rules(form) -> tuple[list[dict], list[str]]:
    operators = form.getlist('calorie_operator[]')
    values = form.getlist('calorie_value[]')
    targets = form.getlist('calorie_target[]')
    rules: list[dict] = []
    summaries: list[str] = []

    for op_raw, value_raw, target_raw in zip(operators, values, targets):
        try:
            value = int(value_raw)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue

        op_key = (op_raw or '').strip().lower()
        operator = _CALORIE_OPERATOR_MAP.get(op_key)
        if not operator:
            operator = _CALORIE_OPERATOR_MAP['about']

        target_key = (target_raw or '').strip().lower()
        scope = _CALORIE_SCOPE_MAP.get(target_key)
        if not scope:
            continue

        rule = {
            'operator': operator['code'],
            'operator_text': operator['text'],
            'value': value,
            'scope_type': scope['type'],
            'meal_type': scope['meal_type'],
            'scope_label': scope['label'],
        }
        rules.append(rule)
        summaries.append(f"{operator['text'].capitalize()} {value} calories for {scope['label']}")

    unsupported = [r for r in rules if r['scope_type'] != 'per_meal']
    if unsupported:
        logging.warning(
            "Calorie goals for %s are not strictly enforced yet (totals not supported)",
            ", ".join({r['scope_label'] for r in unsupported})
        )

    return rules, summaries


def _calorie_value_violates(rule: dict, calories: float | int | None) -> bool:
    if calories is None:
        return False
    target = rule.get('value') or 0
    operator = rule.get('operator')
    if operator == 'about':
        tolerance = _calorie_tolerance(target)
        return abs(float(calories) - target) > tolerance
    if operator == 'at_least':
        return float(calories) < target
    if operator == 'under':
        return float(calories) > target
    return False


def _calorie_tolerance(target: float | int | None) -> int:
    if target in (None, 0):
        return _CALORIE_MIN_DELTA
    try:
        return max(int(round(float(target) * _CALORIE_ABOUT_TOLERANCE)), _CALORIE_MIN_DELTA)
    except (TypeError, ValueError):
        return _CALORIE_MIN_DELTA


def _enforce_calorie_rules(meals: list[dict], calorie_rules: list[dict]) -> tuple[list[dict], list[dict]]:
    if not meals or not calorie_rules:
        return meals, []

    kept: list[dict] = []
    violations: list[dict] = []

    for meal in meals:
        meal_type = (meal.get('mealType') or '').strip().lower()
        calories = meal.get('calories')
        violated = False
        for rule in calorie_rules:
            if rule.get('scope_type') != 'per_meal':
                continue
            scope_meal_type = rule.get('meal_type')
            if scope_meal_type and scope_meal_type != meal_type:
                continue
            if _calorie_value_violates(rule, calories):
                violations.append({
                    'meal': meal,
                    'meal_name': meal.get('name') or '(Unnamed)',
                    'calories': calories,
                    'rule': rule,
                })
                violated = True
                break

        if not violated:
            kept.append(meal)

    return kept, violations


def _missing_calorie_terms(ingredients, fact_cache: dict[str, IngredientFact] | None) -> list[str]:
    missing: list[str] = []
    if not ingredients:
        return missing

    for ingredient in ingredients:
        quantity, unit, name = _extract_ingredient_parts(ingredient)
        if unit != 'g' or quantity is None:
            continue

        term = _normalize_term(name)
        if not term or term in _CONDIMENT_TERMS:
            continue

        fact = _best_cached_fact(term, fact_cache or {})
        if not fact:
            missing.append(name or term)

    return missing


def apply_usda_macros(meals: list[dict], fact_cache: dict[str, IngredientFact] | None = None) -> None:
    if not meals or INGREDIENT_RETRIEVER is None:
        return

    cache: dict[str, object | None] = {}
    precomputed = {k: v for k, v in (fact_cache or {}).items() if v}
    if precomputed:
        for key, fact in list(precomputed.items()):
            norm = _normalize_term(key)
            if norm and norm not in precomputed:
                precomputed[norm] = fact

    for meal in meals:
        totals = {'calories': 0.0, 'protein': 0.0, 'carbs': 0.0, 'fats': 0.0}
        matched = False
        contributions: list[dict[str, float | str]] = []

        ingredients_list = meal.get('ingredients') or []
        for idx, ingredient in enumerate(ingredients_list):
            quantity, unit, name = _extract_ingredient_parts(ingredient)
            if unit != 'g' or quantity is None:
                continue

            term = _normalize_term(name)
            if not term or term in _CONDIMENT_TERMS:
                continue

            fact = cache.get(term)
            if fact is None:
                fact = _best_cached_fact(term, precomputed)
                if fact:
                    cache[term] = fact

            if fact is None:
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

            rounded_cal = round(cal, 1)
            contributions.append({
                'ingredient': term,
                'grams': round(quantity, 1),
                'calories': rounded_cal,
            })

            logging.debug(
                'Ingredient %s contributes %.1f kcal from %.1f g (serving %.1f g)',
                term,
                rounded_cal,
                round(quantity, 1),
                serving_size
            )

            if isinstance(ingredient, dict):
                ingredient['calories'] = rounded_cal
            else:
                existing = ingredients_list[idx]
                if isinstance(existing, str) and 'kcal' not in existing.lower():
                    ingredients_list[idx] = f"{existing} [{rounded_cal} kcal]"

        if matched:
            meal['calories'] = int(round(totals['calories']))
            meal['protein'] = int(round(totals['protein']))
            meal['carbs'] = int(round(totals['carbs']))
            meal['fats'] = int(round(totals['fats']))
            meal['_usda_contributions'] = contributions
            meal['_usda_macro_source'] = 'cached_lookup' if fact_cache else 'live_lookup'
        else:
            meal['_usda_macro_source'] = 'unverified'

# Initialize DB with app
db.init_app(app)

# Register routes
register_feed_routes(app)
register_auth_routes(app)


# Ensure tables are created
# Supabase kept truncating Werkzeug hashes at 50 chars, so I'm stretching that column on startup.
def _ensure_password_hash_column(min_length: int = 255) -> None:
    """Make sure users.password_hash can store long hashes."""
    try:
        current_len = db.session.execute(text(
            """
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'users'
              AND column_name = 'password_hash'
            """
        )).scalar()
        if current_len is not None and current_len < min_length:
            db.session.execute(text(
                f"ALTER TABLE users ALTER COLUMN password_hash TYPE VARCHAR({min_length})"
            ))
            db.session.commit()
            logging.info(
                "Upgraded users.password_hash length from %s to %s characters",
                current_len,
                min_length,
            )
    except Exception:
        logging.exception('Failed to ensure password_hash column length')


def _ensure_generated_recipes_calories_column() -> None:
    """Add calories column to generated_recipes if Supabase dropped it."""
    try:
        exists = db.session.execute(text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'generated_recipes'
              AND column_name = 'calories'
            LIMIT 1
            """
        )).scalar()
        if not exists:
            db.session.execute(text(
                "ALTER TABLE generated_recipes ADD COLUMN calories INTEGER"
            ))
            db.session.commit()
            logging.info("Added calories column to generated_recipes")
    except Exception:
        logging.exception('Failed to ensure generated_recipes.calories column')


def _ensure_collections_primary_key() -> None:
    """Allow multiple collections per user by enforcing composite primary key."""
    try:
        db.session.execute(text("ALTER TABLE collections DROP CONSTRAINT IF EXISTS collections_pkey"))
        db.session.execute(text(
            "ALTER TABLE collections ADD CONSTRAINT collections_pkey PRIMARY KEY (user_id, collection_name)"
        ))
        db.session.commit()
    except Exception:
        logging.exception('Failed to enforce collections composite primary key')


with app.app_context():
    # db.session.remove() # Uncomment this if you want to delete all data each time you run
    # db.drop_all()       # Uncomment this if you want to delete all data each time you run
    try:
        db.create_all()  # Ensure required tables (collections, etc.) exist before requests
        _ensure_password_hash_column()
        _ensure_generated_recipes_calories_column()
        _ensure_collections_primary_key()
    except Exception:
        logging.exception('Database initialization failed')

# Routes
@app.route("/")
def index():
    user_logged_in = 'user_id' in session
    return render_template('index.html', logged_in=user_logged_in)  

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

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
    uid = session.get('user_id')
    mealObjs: list[Meal] = []
    colObjs: dict[str, MealCollection] = {}

    if uid:
        saved_meals = getAllMeals(uid) or []
        collection_links = getCollectionMeals(uid) or []

        meal_lookup: dict[str, Meal] = {}
        for record in saved_meals:
            ingredients = _deserialize_list(record.ingredients)
            instructions = _deserialize_list(record.instructions)
            currMeal = Meal(
                record.meal_type,
                record.recipe_name,
                ingredients,
                record.calories or 0,
                instructions,
                record.carbs or 0,
                record.fats or 0,
                record.protein or 0,
            )
            setattr(currMeal, 'id', record.meal_id)
            mealObjs.append(currMeal)
            meal_lookup[record.meal_id] = currMeal

        for link in collection_links:
            collection = colObjs.setdefault(link.collection_name, MealCollection([], link.collection_name))
            meal_obj = meal_lookup.get(link.meal_id)
            if meal_obj and meal_obj not in collection.meals:
                collection.meals.append(meal_obj)

        session['shopping_meal_ids'] = [str(getattr(meal, 'id')) for meal in mealObjs if getattr(meal, 'id', None)]
    else:
        session.pop('shopping_meal_ids', None)

    return render_template("shopping_list.html", meals=mealObjs, cols=list(colObjs.values()))

@app.route("/calendar")
def calendar():
    uid = session.get('user_id')
    meals: list[Meal] = []
    collections: list[MealCollection] = []

    if uid:
        saved_meals = getAllMeals(uid) or []
        collection_links = getCollectionMeals(uid) or []

        meal_lookup: dict[str, Meal] = {}
        for record in saved_meals:
            ingredients = _deserialize_list(record.ingredients)
            instructions = _deserialize_list(record.instructions)
            curr_meal = Meal(
                record.meal_type,
                record.recipe_name,
                ingredients,
                record.calories or 0,
                instructions,
                record.carbs or 0,
                record.fats or 0,
                record.protein or 0,
            )
            setattr(curr_meal, 'id', record.meal_id)
            meals.append(curr_meal)
            meal_lookup[record.meal_id] = curr_meal

        collection_map: dict[str, MealCollection] = {}
        for link in collection_links:
            collection = collection_map.setdefault(link.collection_name, MealCollection([], link.collection_name))
            meal_obj = meal_lookup.get(link.meal_id)
            if meal_obj and meal_obj not in collection.meals:
                collection.meals.append(meal_obj)
        collections = list(collection_map.values())

    return render_template("calendar.html", meals=meals, collections=collections)

@app.route("/user_meals", methods=["GET"], endpoint="user_meals")
def user_meals():
    uid = session.get('user_id')
    meals: list[Meal] = []
    collections: list[MealCollection] = []

    def _as_list(value):
        if value in (None, ''):
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
                return [parsed]
            except Exception:
                return [value]
        return [value]

    if uid:
        saved_meals = getAllMeals(uid) or []
        collection_links = getCollectionMeals(uid) or []

        meal_lookup: dict[str, Meal] = {}
        for record in saved_meals:
            ingredients = _as_list(record.ingredients)
            instructions = _as_list(record.instructions)
            curr_meal = Meal(
                record.meal_type,
                record.recipe_name,
                ingredients,
                record.calories or 0,
                instructions,
                record.carbs or 0,
                record.fats or 0,
                record.protein or 0,
            )
            setattr(curr_meal, 'id', record.meal_id)
            meals.append(curr_meal)
            meal_lookup[record.meal_id] = curr_meal

        collection_map: dict[str, MealCollection] = {}
        for link in collection_links:
            collection = collection_map.setdefault(link.collection_name, MealCollection([], link.collection_name))
            meal_obj = meal_lookup.get(link.meal_id)
            if meal_obj and meal_obj not in collection.meals:
                collection.meals.append(meal_obj)
        collections = list(collection_map.values())

    return render_template("user_meals.html", meals=meals, collections=collections)



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
    favorite_terms_input = [f.strip() for f in request.form.getlist("favorites[]") if f.strip()]
    manual_variety_terms = _dedupe_terms(favorite_terms_input)

    # Log the received form data
    form_prefs = request.form.to_dict(flat=True)
    activity_level = _normalize_activity_level(form_prefs.get('activity'))
    selected_diets = [d.strip().lower() for d in request.form.getlist("dietary") if d.strip()]
    if selected_diets:
        # store the first one for compatibility; remainder are handled when we build banned lists
        form_prefs["dietary_restrictions"] = selected_diets[0]
    logging.debug(f"Received form data: {form_prefs}")

    calorie_rules, calorie_rule_summaries = _parse_calorie_rules(request.form)
    if calorie_rules and not form_prefs.get('calories'):
        fallback = next((rule for rule in calorie_rules if rule.get('scope_type') == 'per_meal' and not rule.get('meal_type')), None)
        if fallback:
            form_prefs['calories'] = fallback['value']

    # Load stored global constraints and user-specific constraints (if logged in)
    global_constraints = cs.get() or {}
    user_constraints = {}
    user_id = session.get('user_id')
    numeric_user_id = None
    if user_id:
        try:
            numeric_user_id = int(user_id)
            user_constraints = cdb.get_user_constraints(numeric_user_id) or {}
        except Exception:
            logging.exception("Failed to load user constraints")
            numeric_user_id = None

    user_obj = _user_from_form(request.form)
    user_prompt_text = ""

    # Merge constraints (pure function; does not persist)
    merged_prefs = cs.merge_constraints(global_constraints, user_constraints, form_prefs)
    logging.debug("Merged preferences used for prompt: %s", merged_prefs)

    desired_counts = _requested_meal_counts(merged_prefs)
    total_needed = sum(desired_counts.values())
    distinct_dayparts = sum(1 for v in desired_counts.values() if v) > 1

    favorite_terms, variety_label, auto_variety = _select_variety_terms(favorite_terms_input, desired_counts)
    manual_terms_consumed = bool(manual_variety_terms) and manual_variety_terms == favorite_terms
    variety_context = None

    biometric_per_meal = None
    if user_obj:
        meals_for_target = total_needed or 3
        try:
            daily_target = user_obj.calorieTargetByGoal(activity_level)
            if daily_target > 0 and meals_for_target > 0:
                biometric_per_meal = int(max(0, round(daily_target / meals_for_target)))
        except Exception:
            logging.exception("Failed to compute calorie target from user metrics")
            biometric_per_meal = None

        try:
            user_prompt_text = user_obj.llmPromptText(activity_level)
        except Exception:
            logging.exception("Failed to build user prompt context")
            user_prompt_text = ""

    if biometric_per_meal and not merged_prefs.get('calories'):
        merged_prefs['calories'] = biometric_per_meal

    if biometric_per_meal and not calorie_rules:
        auto_rule = {
            'operator': 'about',
            'operator_text': 'about',
            'value': biometric_per_meal,
            'scope_type': 'per_meal',
            'meal_type': None,
            'scope_label': 'each meal',
            'source': 'biometric_profile',
        }
        calorie_rules.append(auto_rule)
        calorie_rule_summaries.append(f"About {biometric_per_meal} calories for each meal (auto from biometrics)")

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

    def _fetch_variety_facts(terms: list[str]) -> RetrievalBatch | None:  # type: ignore[name-defined]
        if not terms:
            return None
        fetch_terms = terms[:_AUTO_FAVORITE_LIMIT]
        try:
            batch = INGREDIENT_RETRIEVER.fetch(fetch_terms)
        except Exception:
            logging.exception("Ingredient retrieval failed for %s", fetch_terms)
            return None
        if batch and batch.facts:
            batch.facts = [fact for fact in batch.facts if fact]
        if batch and batch.facts:
            logging.debug("Retrieved ingredient facts for variety focus: %s", fetch_terms)
        else:
            logging.info("No ingredient facts found for variety focus terms: %s", fetch_terms)
        return batch

    retrieval_batch = _fetch_variety_facts(favorite_terms)
    if manual_terms_consumed and manual_variety_terms and (not retrieval_batch or not retrieval_batch.facts):
        logging.info("Falling back to auto variety presets because favorites lacked ingredient matches")
        favorite_terms, variety_label, auto_variety = _select_variety_terms([], desired_counts)
        manual_terms_consumed = False
        retrieval_batch = _fetch_variety_facts(favorite_terms)

    if favorite_terms:
        anchor_text = ', '.join(favorite_terms)
        if manual_terms_consumed:
            variety_context = f"User favorites to incorporate: {anchor_text}"
        elif auto_variety and variety_label:
            base = f"Flavor inspiration: {variety_label}. Highlight these pantry anchors: {anchor_text}"
            if manual_variety_terms:
                variety_context = f"User flavor cue: {', '.join(manual_variety_terms)}. {base}"
            else:
                variety_context = base
        else:
            base = f"Highlight these pantry anchors: {anchor_text}"
            if manual_variety_terms:
                variety_context = f"User flavor cue: {', '.join(manual_variety_terms)}. {base}"
            else:
                variety_context = base
    elif manual_variety_terms:
        variety_context = f"User flavor cue: {', '.join(manual_variety_terms)}"

    if variety_context and distinct_dayparts:
        variety_context = (
            f"{variety_context}. Make breakfast, lunch, and dinner feel distinct with different primary proteins or cuisines; avoid repeating the same entree twice."
        )

    tool_cache: dict[str, dict] = {}
    tool_fact_cache: dict[str, IngredientFact] = {}

    def _lookup_ingredient_tool(function_name: str, args: dict) -> dict:
        if function_name != 'lookupIngredient':
            return {"ok": False, "error": f"unsupported_tool:{function_name}"}

        term = str(args.get('ingredient') or '').strip()
        if not term:
            return {"ok": False, "error": "ingredient_required"}

        cache_key = term.lower()
        if cache_key in tool_cache:
            return tool_cache[cache_key]

        try:
            batch = INGREDIENT_RETRIEVER.fetch([term])
        except Exception as exc:
            logging.exception("lookupIngredient failed for %s", term)
            result = {"ok": False, "ingredient": term, "error": "lookup_failed"}
        else:
            fact = batch.facts[0] if batch and batch.facts else None
            if not fact:
                result = {"ok": False, "ingredient": term, "error": "not_found"}
                if batch and batch.warnings:
                    result["warnings"] = batch.warnings
            else:
                fact_payload = {
                    "canonical_name": fact.canonical_name,
                    "source_id": fact.source_id,
                    "summary": fact.summary,
                    "serving_size_g": fact.nutrition.serving_size_g,
                    "serving_size_oz": round(fact.nutrition.serving_size_g / _GRAMS_PER_OUNCE, 4),
                    "calories": fact.nutrition.calories,
                    "protein_g": fact.nutrition.protein_g,
                    "carbs_g": fact.nutrition.carbs_g,
                    "fats_g": fact.nutrition.fats_g,
                    "tags": fact.tags,
                }
                if batch and batch.warnings:
                    fact_payload["warnings"] = batch.warnings
                result = {"ok": True, "ingredient": term, "fact": fact_payload}
                tool_fact_cache[cache_key] = fact
                normalized_term = _normalize_term(term)
                if normalized_term:
                    tool_fact_cache.setdefault(normalized_term, fact)

        tool_cache[cache_key] = result
        return result

    # Generate the prompt and log it
    base_prompt = generate_prompt(
        merged_prefs,
        retrieval_batch=retrieval_batch,
        calorie_rules=calorie_rule_summaries,
        variety_context=variety_context,
    )
    prompt = f"{user_prompt_text}\n\n{base_prompt}".strip() if user_prompt_text else base_prompt
    logging.debug(f"Generated prompt: {prompt}")

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

    last_calorie_rule_violations: list[dict] = []

    while True:
        raw_data = call_model(prompt, tool_executor=_lookup_ingredient_tool)
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
        dropped_for_calorie = 0
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

            # Allow missing weights — USDA will fill in later
            missing_weight = next((ig for ig in new_ings if not _has_explicit_weight(ig)), None)


            banned_term, offending = _find_banned_hit(new_ings)
            if banned_term:
                logging.warning('Dropping %s because it contains banned ingredient "%s" (matched term "%s")', name, offending, banned_term)
                continue

            missing_calorie_terms = _missing_calorie_terms(new_ings, tool_fact_cache)
            if missing_calorie_terms:
                logging.warning(
                    '%s missing cached nutrition facts for: %s. Will fetch from USDA backend.',
                    name,
                    ", ".join(missing_calorie_terms)
                )
                m.setdefault('_missing_tool_facts', missing_calorie_terms)

            instr = m.get('instructions')
            if instr is None:
                m['instructions'] = []
            elif isinstance(instr, str):
                lines = [ln.strip() for ln in instr.splitlines() if ln.strip()]
                if len(lines) == 1:
                    numbered = [part.strip() for part in re.split(r'\s*(?:\d+\.)\s*', lines[0]) if part.strip()]
                    if numbered:
                        lines = numbered
                    else:
                        sentences = [part.strip() for part in re.split(r'(?<=\.)\s+(?=[A-Z])', lines[0]) if part.strip()]
                        if sentences:
                            lines = sentences
                m['instructions'] = lines
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

                # --- overwrite macros from USDA facts (single, authoritative pass) ---
        try:
            apply_usda_macros(meals, fact_cache=tool_fact_cache)
            for m in meals:
                m['_macro_source'] = m.get('_usda_macro_source', 'usda')
        except Exception:
            logging.exception("Failed to overwrite macros with USDA data")

        calorie_rule_violations: list[dict] = []
        if calorie_rules:
            meals, calorie_rule_violations = _enforce_calorie_rules(meals, calorie_rules)
            if calorie_rule_violations:
                dropped_for_calorie += len(calorie_rule_violations)
                details = ", ".join(
                    f"{v['meal_name']} ({v['calories']} kcal vs {v['rule']['operator_text']} {v['rule']['value']})"
                    for v in calorie_rule_violations
                )
                logging.warning('Dropped %d meals for calorie rules: %s', len(calorie_rule_violations), details)
            last_calorie_rule_violations = calorie_rule_violations or []


        need_retry = False
        if not meals and (dropped_for_weight or dropped_for_calorie) and attempt < (MAX_MODEL_ATTEMPTS - 1):
            reasons = []
            if dropped_for_weight:
                reasons.append('missing weights')
            if dropped_for_calorie:
                reasons.append('calorie rules')
            logging.warning(
                'All meals rejected for %s; retrying attempt %d/%d',
                ', '.join(reasons) or 'validation issues',
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
        if i < len(ids):
            meals[i]['id'] = ids[i]
        else:
            meals[i]['id'] = meals[i].get('id') or f"{uid or 0}_{i+1}"

    # keep what the model said (for transparency if you want to display it)
    for m in meals:
        m['_model_calories'] = m.get('calories', 0)
        m['_model_protein']  = m.get('protein', 0)
        m['_model_carbs']    = m.get('carbs', 0)
        m['_model_fats']     = m.get('fats', 0)

    # overwrite macros with verified USDA totals
    try:
        apply_usda_macros(meals, fact_cache=tool_fact_cache)
    except Exception:
        logging.exception('Failed to overwrite macros with USDA data')

    if total_needed and len(meals) < total_needed and last_calorie_rule_violations:
        deficit = total_needed - len(meals)
        logging.warning('Filling %d slots with closest calorie matches despite rule violations', deficit)
        sorted_rejects = sorted(
            last_calorie_rule_violations,
            key=lambda v: abs((v.get('calories') or 0) - (v.get('rule', {}).get('value') or 0))
        )
        for violation in sorted_rejects:
            if deficit <= 0:
                break
            meal = violation.get('meal')
            if not isinstance(meal, dict):
                continue
            meal_note = (
                f"{violation.get('calories')} kcal (goal {violation['rule']['operator_text']} "
                f"{violation['rule']['value']})"
            )
            meal['_calorie_warning'] = meal_note
            meals.append(meal)
            deficit -= 1
        data['meals'] = meals

    # tag source (e.g., 'live_lookup' or 'cached_lookup')
    for m in meals:
        m['_macro_source'] = m.get('_usda_macro_source', 'unverified')

    # commit the updated meals back into the payload passed to the template
    data['meals'] = meals


    # save if logged in
    print(meals)
    try:

        # --- generate unique IDs and attach them to meals ---
        uid = session.get('user_id')
        if uid and meals:
            try:
                ids = generatemealIDs(uid, len(meals))
            except Exception:
                logging.exception('generatemealIDs failed')
                ids = [f"{uid or 0}_{i+1}" for i in range(len(meals))]

            for i, meal in enumerate(meals):
                meal['id'] = meal.get('id') or ids[i]

            # extract ingredient quantities and units for saving
            ingrids, units = [], []
            for meal in meals:
                mealsIgrs, mealsUnits = [], []
                for ingredient in meal.get('ingredients', []):
                    if isinstance(ingredient, dict):
                        mealsIgrs.append(ingredient.get('quantity'))
                        mealsUnits.append(ingredient.get('unit'))
                    else:
                        mealsIgrs.append(None)
                        mealsUnits.append(None)
                ingrids.append(mealsIgrs)
                units.append(mealsUnits)

            # --- save meals with proper IDs ---
            saveNewMeals(uid, {"meals": meals}, units, ingrids)
    except Exception:
        logging.exception('Failed to save new meals')

    collections = getUserMeals(uid) if uid else []
    return render_template("results.html", data=data, collections=collections)

@app.route("/build_shopping_list", methods=["POST"])
def build_shopping_list():
    selected_ids = {value.strip() for value in request.form.getlist("selected_meals") if value.strip()}
    uid = session.get('user_id')
    allowed_ids = {str(mid) for mid in (session.get('shopping_meal_ids') or [])}

    def _coerce_float(value):
        try:
            if value in (None, ""):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    aggregated: dict[tuple[str, str], dict[str, float | str]] = {}
    uncounted: dict[str, int] = {}

    if uid:
        saved_meals = getAllMeals(uid) or []
        for record in saved_meals:
            meal_id = str(record.meal_id)
            if not meal_id:
                continue
            if selected_ids:
                if meal_id not in selected_ids and record.recipe_name not in selected_ids:
                    continue
            elif allowed_ids and meal_id not in allowed_ids:
                continue

            for entry in _deserialize_list(record.ingredients):
                if isinstance(entry, dict):
                    name = (
                        entry.get('name')
                        or entry.get('ingredient')
                        or entry.get('item')
                        or entry.get('raw')
                    )
                    qty = _coerce_float(entry.get('quantity') or entry.get('qty') or entry.get('amount'))
                    unit = (entry.get('unit') or entry.get('units') or '').strip()
                else:
                    name = str(entry).strip()
                    qty = None
                    unit = ''

                if not name:
                    continue

                if qty is None:
                    uncounted[name] = uncounted.get(name, 0) + 1
                    continue

                key = (name.strip().lower(), unit.lower())
                bucket = aggregated.setdefault(key, {
                    'name': name.strip(),
                    'unit': unit,
                    'quantity': 0.0,
                })
                bucket['quantity'] = float(bucket['quantity']) + qty

    items: list[tuple[str, str]] = []
    for entry in aggregated.values():
        qty = entry['quantity']
        unit = entry['unit']
        display = f"{qty:g} {unit}".strip()
        items.append((entry['name'], display or f"{qty:g}"))

    for name, count in uncounted.items():
        label = f"x{count}" if count > 1 else "as needed"
        items.append((name, label))

    items.sort(key=lambda pair: pair[0].lower())

    return render_template("shopping_list_result.html", items=items)


if __name__ == "__main__":
    app.run(debug=True)