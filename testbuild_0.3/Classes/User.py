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

    DIETARY_RESTRICTIONS = [
        "Kosher",
        "Halal",
        "Carnivore",
        "Keto",
        "Pescatarian",
        "Gluten-Free",
        "Lactose-Free",
        "Paleo",
        "Vegetarian",
        "Vegan"
    ]

    ALLERGIES = [
        "Dairy",
        "Eggs",
        "Peanuts",
        "Tree Nuts",
        "Soy",
        "Gluten",
        "Wheat",
        "Shellfish"
    ]

    MEAL_PREFERENCES = [
        "Mostly Chicken",
        "Mostly Beef",
        "Mostly Fish"
    ]


    def __init__(self, name="", weight_lbs=0.0, height_ft=0, height_in=0,
                 age=0, sex="M", goal="maintain"):

        self._name = name
        self._weight_lbs = float(weight_lbs)
        self._height_ft = int(height_ft)
        self._height_in = int(height_in)
        self._age = int(age)
        self._sex = sex.upper()
        self._goal = goal.lower()
        self._currentMealPlan = [] # added storing of user meal plan as list of meal objects


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

    def setName(self, name): self._name = name
    def setWeightLbs(self, weight_lbs): self._weight_lbs = float(weight_lbs)
    def setHeight(self, feet, inches=0):
        self._height_ft = int(feet)
        self._height_in = int(inches)
    def setAge(self, age): self._age = int(age)
    def setSex(self, sex): self._sex = sex.upper()
    def setGoal(self, goal): self._goal = goal.lower()


    def calculateBMR(self):
        """Basal Metabolic Rate using Mifflin–St Jeor Equation"""
        w = self._to_kg()
        h = self._to_cm()
        a = self._age
        if self._sex == "M":
            return 88.362 + (13.397 * w) + (4.799 * h) - (5.677 * a)
        elif self._sex == "F":
            return 447.593 + (9.247 * w) + (3.098 * h) - (4.330 * a)
        else:
            raise ValueError("Sex must be 'M' or 'F'")

    def calculateBMI(self):
        """BMI = weight(kg) / height(m)^2"""
        h_m = self._to_cm() / 100.0
        w_kg = self._to_kg()
        return w_kg / (h_m ** 2)

    def bmiCategory(self):
        """Return BMI classification string"""
        bmi = self.calculateBMI()
        if bmi < 18.5:
            return "underweight"
        elif bmi < 25:
            return "normal"
        elif bmi < 30:
            return "overweight"
        else:
            return "obese"

    def dailyCalories(self, activity="moderate"):
        """Estimate Total Daily Energy Expenditure (TDEE)"""
        factors = {
            "sedentary" : 1.2,
            "light" : 1.375, 
            "moderate" : 1.55,
            "active" : 1.725,
            "very active" : 1.9,
        }
        factor = factor.get(activity, 1.55)
        return self.calculateBMR() * factor
    
    def calorieTargetByGoal(self, activity = "moderate"):
        """adjust calories based on weight goals"""
        tdee = self.dailyCalories(activity)
        if self._goal == "maintain" :
            return tdee
        elif self._goal == "lose" :
            return max(0.0, tdee - 500)
        elif self._goal == "gain" :
            return tdee + 500
        else: return tdee

    def UserData(self):
        """Return user data in organized form"""
        return{
            "name" : self._name,
            "weight_lbs" : self._weight_lbs,
            "height_ft" : self._height_ft,
            "height_in": self._height_in,
            "age" : self._age,
            "sex" : self._sex,
            "goal" : self._goal,
            "bmi" : round(self.calculateBMI(), 1),
            "bmi_category" : self.bmiCategory(),
            "bmr" : round(self.calculateBMR(), 0),
        }
    
    def llmPromptText(self, activity= "moderate") :
        """ChatGPT summary strings for user prompts"""
        bmi = self.calculateBMI()
        tdee = self.dailyCalories(activity)
        target = self.calculateTargetByGoal(activity)
        return(
            f"User: {self._name}, {self._sex}, {self._age}, years old. "
            f"Height: {self._height_ft} ft {self._height_in} in. "
            f"Weight: {self._weight_lbs} lbs. Goal: {self._goal}. "
            f"BMI: {bmi:.1f} ({self.bmiCategory()}). "
            f"BMR: {self.calculateBMR():.0f} kcal/day. "
            f"Maintenance calories (TDEE): {tdee:.0f} kcal/day. "
            f"Recommended daily calories for goal: {target:.0f} kcal/day."
        )

    def __str__(self):
        return (
        f"User({self._name}, {self._sex}, {self._age}y, "
        f"{self._height_ft}ft {self._height_in}in, "
        f"{self._weight_lbs}lbs, goal={self._goal})"
    )