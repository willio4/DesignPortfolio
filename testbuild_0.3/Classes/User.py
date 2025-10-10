    # class to structure meal plan preferences from user inputs
    # this will be populated from the main loop for now but in production will be populated from the ui

    # toDO:
        # add more user inputs that we could use for stage 1 of our product
        # these will be what users see when we do our testing
        # add then add those new parameters to this class constructor,
    # if needed make lists for the parametrs to reduce the # of params in contructor
    # 

    # Omar
#    def MealPlanPrefs():
#
#       def __init__(self,bFast=None,lnch=None,dnr=None):
#            preferences={"nBreakFast":bFast,"nLunch":lnch,"nDnr" :dnr}
#            self.prefs=preferences

#        def getPrefs(self):
#            return self.prefs
        

class User:


    def __init__(self, name="", weight_lbs=0.0, height_ft=0, height_in=0,
                 age=0, sex="M", goal="maintain"):

        self._name = name
        self._weight_lbs = float(weight_lbs)
        self._height_ft = int(height_ft)
        self._height_in = int(height_in)
        self._age = int(age)
        self._sex = sex.upper()
        self._goal = goal.lower()
        self._currentMealPlan = [] # added storing of user meal plan

    def _to_kg(self):
        return self._weight_lbs * 0.45359237

    def _to_cm(self):
        total_inches = self._height_ft * 12 + self._height_in
        return total_inches * 2.54

    # getters
    def getName(self):
        return self._name

    def getWeightLbs(self):
        return self._weight_lbs

    def getHeightFeetInches(self):
        return (self._height_ft, self._height_in)

    def getAge(self):
        return self._age

    def getSex(self):
        return self._sex

    def getGoal(self):
        return self._goal

    