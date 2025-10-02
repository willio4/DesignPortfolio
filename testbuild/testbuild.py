from flask import Flask, render_template
app = Flask(__name__)

# Route to the homepage
# Returns the index template
@app.route("/")
def index():
    return render_template("index.html")


#class to structure meal plan preferences from user inputs
# this will be populated from the main loop for now but in production will be populated from the ui

# toDO:
    # add more user inputs that we could use for stage 1 of our product
    # these will be what users see when we do our testing
    # add then add those new parameters to this class constructor,
# if needed make lists for the parametrs to reduce the # of params in contructor
    # 
class MealPlanPrefs:

    def __init__(self,bFast=None,lnch=None,dnr=None):
        preferences={"nBreakFast":bFast,"nLunch":lnch,"nDnr" :dnr}
        self.prefs=preferences

    def getPrefs(self):
        return self.prefs
    
# --------------------------------------Pat-----------------------------------------------
# toDO:
# set constructor , see UML diagram for more
# no need to implment methods yet from UML
# just implement a get mealplan method which returns all the meals set in constructor
class MealPlan:
    def __init__(self, planID: int, approved: bool, user, meals):
        self.planID = planID
        self.approved = approved
        self.user = user
        self.meals = meals

    def getMealPlan(self):
        return self.meals

# Pat
# toDO:
# set constructor , see UML diagram for more
# for toString method just return a string the format '<nOfIngredient> <IngredientName> (s)'
class Ingredient:
    def __init__(self, ingredientID: int, name: str, quantity: float, unit: str):
        self.ingredientID = ingredientID
        self.name = name
        self.quantity = quantity
        self.unit = unit
    
    def toString(self):
        return f"{self.ingredientID} {self.name}"

# toDO:
# set constructor , see UML diagram for more
# main focus is display recipe method, ensure each Ingredient is printed line by line using the toString method
# from the Ingredient class
# besure to print the meal name as well

# use the get nutriotional info method to return the calroies of the meal as an integer and any other health realted info if we have it
class Meal:
    def __init__():
        pass



    

# toDO:
# set constructor and methods, see UML diagram for more
# for the generate meal list method: return the Ingredient names with their quantities 
# for the display method, call the generate meal list method,
#  and print the result out to the console in a readable manner
class GroceryList:
    def __init__():
        pass





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
def parseModelResults(recipes):
    pass


#toDo:
#   find an LLM 
# call the LLm from this function by intaking the prompt param and passing it to the model
# return the models results from this function
def callModel(prompt):

    #recipesFromModel= #call model here pass to the parse function below
    #modelResults=parseModelResults(recipesFromModel)
    #return modelResults
    pass




# toDO:
# return a string that is the prompt we are passing to the AI model
# tells the model what kind of recipes we want for this user
# once an LLm is decided upon and some basic preferences are decided upon for the first demo
# experient with different prompts for the LLM to see what generates the best results for our product
# then create a parameterized string that will extract each value from the prefs in the parameter
# the paramer will be a dict from the user prefs class

# add the prefs to the prompt string, 
# # note not every pref will be used by our testers and in production
# # for example: someone may not insert any value for calories in their meals they want
# in that case we need the model to not take into account calories
# but we still want the model to return calories
# because it is a requirement for our class fields
# and its good just to show that to the user even if they aren trying to set a goal with cals
# # so we must adjust the prompt string accordingly
# # work out logic to parse the preference param and
# # ultimately return a prompt we can pass directly to a CHAT GPT like LLM 
def generatePrompt(prefs):
    pass




def generateRecipes(prefs):
    prompt=generatePrompt(prefs)
    recipes=callModel(prompt)
    return recipes
    





# main function 
# use for testing
# adjust user prefrences here
# if you add new preferences in the above classes
# be sure to add them here too
@app.route("/startMealPlan")
def startMealPlan():
    """
    testPrefs= MealPlanPrefs(3,2,4) # creating new meal plan preferences, 3 breakfast meals, 2 lunch, and 4 dinners
    AIrecipes=generateRecipes(testPrefs.getPrefs()) # passing the prefs to our process
    mealCtr=0
    for meal in AIrecipes.meals: # displaying the recipe for each meal returned by our process
        print(f"MEAL #{mealCtr}: ")
        meal.printRecipe()
        mealCtr+=1
        """
    return "Input your info here!"

if __name__ == "__main__":
    app.run(debug=True)
    