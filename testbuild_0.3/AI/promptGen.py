# toDO:------------------------ Tess -------------------------------
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

# remove extra indents from prompt string
from textwrap import dedent

# helper function that will return a bullet point line, aside for sections
# that are left blank - in these circumestances we will just leave the line blank
def bulletPointLine(label: str, value, suffix: str = "") -> str:
    if value is None or value == "":
        return ""
    
    if value:
        return f"• {label}: {value}{suffix}\n"

# build a custom prompt based on user preferences
# The output will be plain text that can be passed directly to the LLM
def generatePrompt(prefs):
    pass

# ======= Meal Counter =======
# convert value to int
# return integer if valid, else return None
    def parseMealCount(value):
        try:
            count = int(value)
            if count >= 0:
                return count
        except (ValueError, TypeError):
            pass
        return None

    # get the number of meals per day
    nBreakfast = parseMealCount(prefs.get("nBreakFast"))
    nLunch = parseMealCount(prefs.get("nLunch"))
    nDinner = parseMealCount(prefs.get("nDnr"))

    # sum the total number of meals
    totalMeals = (nBreakfast or 0) + (nLunch or 0) + (nDinner or 0)
    # if user didn't specify any meals, default to 3/day (1 of each)
    if totalMeals == 0:
        totalMeals = 3
        nBreakfast = 1
        nLunch = 1
        nDinner = 1

    # Build lines only for the meal typs that are requested
    mealLines = ""
    mealLines += bulletPointLine("Breakfasts", nBreakfast)
    mealLines += bulletPointLine("Lunches", nLunch)
    mealLines += bulletPointLine("Dinners", nDinner)        

    # if no meal types were specified, default to 1 of each
    if mealLines == "":
        mealLines = "• Breakfasts: 1\n• Lunches: 1\n• Dinners: 1\n"
        

    # ======= Dietary Preferences =======
    # making a condenced list for now. the current goal is to have a few options
    # for the demo and then expand on them later
    raw_diet = (prefs.get("diet") or "").strip().lower()
    diet_normalized = raw_diet.replace("-", " ")
    allowed_diets = {"keto", "paleo", "gluten free", "vegan", "vegetarian", "none"}
    diet_value = diet_normalized if diet_normalized in allowed_diets else ""
