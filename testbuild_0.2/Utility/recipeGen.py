def generateRecipes(prefs):
    prompt=generatePrompt(prefs)
    recipes=callModel(prompt)
    return recipes


