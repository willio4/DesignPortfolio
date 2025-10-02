class User:
    # class to structure meal plan preferences from user inputs
    # this will be populated from the main loop for now but in production will be populated from the ui

    # toDO:
        # add more user inputs that we could use for stage 1 of our product
        # these will be what users see when we do our testing
        # add then add those new parameters to this class constructor,
    # if needed make lists for the parametrs to reduce the # of params in contructor
    # 

    # Omar
    def MealPlanPrefs():

        def __init__(self,bFast=None,lnch=None,dnr=None):
            preferences={"nBreakFast":bFast,"nLunch":lnch,"nDnr" :dnr}
            self.prefs=preferences

        def getPrefs(self):
            return self.prefs
        