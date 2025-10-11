# toDO:------------------------ Tess -------------------------------
# return a string that is the prompt we are passing to the AI model
# tells the model what kind of recipes we want for this user
# then create a parameterized string that will extract each value from the prefs in the parameter

# add the prefs to the prompt string, 
# # note not every pref will be used by our testers and in production
# # for example: someone may not insert any value for calories in their meals they want
# in that case we need the model to not take into account calories
# but we still want the model to return calories
# # work out logic to parse the preference param and

"""from textwrap import dedent

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
"""

# Creating a default prompt to test that data is being
# passed correctly to the model before jumping into unnecessary complexity

DEFAULT_PROMPT = """ 
You are a recipe generator that focuses on healthy meal creation.
Return ONLY a valid JSON following this format:
{"meals":[{"mealType":"dinner","name":"string","ingredients":["string"],
"calories":0,"instructions":"string","carbs":0,"fats":0,"protein":0}]}
Constraints: generate 1 dinner (~600 kcal), <=14 ingredients, <=6 steps.
No prose; JSON only.
""".strip()

def generate_prompt(preferences: dict | None = None) -> str:
    # For now, we are just returning the default prompt
    # In the future, a custom prompt will be implemented based on user preferences
    return DEFAULT_PROMPT
