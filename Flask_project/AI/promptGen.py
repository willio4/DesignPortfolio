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
def generatePrompt(prefs):
    pass