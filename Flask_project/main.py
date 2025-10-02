
from Classes.User import User
from Classes.Meal import Meal
from Classes.Ingredient import Ingredient
from Classes.MealPlan import MealPlan
from Classes.GroceryList import GroceryList
from Utility.recipeGen import generateRecipes

# main function 
# use for testing
# adjust user prefrences here
# if you add new preferences in the above classes
# be sure to add them here too

if __name__ == "__main__":
    
    # create dummy users after user constructor has been implemented to test different variations for testing

    testPrefs = User.MealPlanPrefs(3,2,4) # creating new meal plan preferences, 3 breakfast meals, 2 lunch, and 4 dinners
    AIrecipes = generateRecipes(testPrefs.getPrefs()) # passing the prefs to our process
    mealCtr  = 0
    for meal in AIrecipes.meals: # displaying the recipe for each meal returned by our process
        print(f"MEAL #{mealCtr}: ")
        meal.printRecipe()
        mealCtr+=1


