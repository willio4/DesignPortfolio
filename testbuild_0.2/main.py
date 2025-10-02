from flask import Flask, render_template
app = Flask(__name__)

from Classes.User import User
from Classes.Meal import Meal
from Classes.Ingredient import Ingredient
from Classes.MealPlan import MealPlan
from Classes.GroceryList import GroceryList
from Utility.recipeGen import generateRecipes

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
@app.route("/startMealPlan")
def startMealPlan():
    """
    # create dummy users after user constructor has been implemented to test different variations for testing
    testPrefs = User.MealPlanPrefs(3,2,4) # creating new meal plan preferences, 3 breakfast meals, 2 lunch, and 4 dinners
    AIrecipes = generateRecipes(testPrefs.getPrefs()) # passing the prefs to our process
    mealCtr  = 0
    for meal in AIrecipes.meals: # displaying the recipe for each meal returned by our process
        print(f"MEAL #{mealCtr}: ")
        meal.printRecipe()
        mealCtr+=1
    """
    return "Input user info here"

if __name__ == "__main__":
    app.run(debug=True)
    


