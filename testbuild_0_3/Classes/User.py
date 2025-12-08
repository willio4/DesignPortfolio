from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class User:
    """Represents a user's personal information and provides health-related calculations."""
    name: Optional[str] = None
    weight_lbs: Optional[float] = None
    height_ft: Optional[int] = None
    height_in: Optional[int] = None
    age: Optional[int] = None
    sex: Optional[str] = None  # 'M' or 'F'
    goal: Optional[str] = None  # 'maintain'|'lose'|'gain'
    disliked_ingredients: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    prefs: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_user_model(cls, user_model: Any) -> "User":
        """Construct from an arbitrary user_model object (e.g. ORM model).

        This is defensive: it looks for common attributes and falls back to dict
        access where appropriate.
        """
        src = user_model
        def _get(attr, default=None):
            return getattr(src, attr, src.get(attr, default) if isinstance(src, dict) else default)

        return cls(
            name=_get("name"),
            weight_lbs=_get("weight_lbs"),
            height_ft=_get("height_ft"),
            height_in=_get("height_in"),
            age=_get("age"),
            sex=(_get("sex") or _get("gender")),
            goal=_get("goal"),
            disliked_ingredients=_get("disliked_ingredients") or _get("dislikes") or [],
            allergies=_get("allergies") or [],
            prefs=_get("prefs") or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    # internal conversions
    def _weight_kg(self) -> float:
        return (self.weight_lbs or 0.0) * 0.45359237

    def _height_cm(self) -> float:
        ft = int(self.height_ft or 0)
        inch = int(self.height_in or 0)
        total_inches = ft * 12 + inch
        return total_inches * 2.54

    # health calculations
    def calculateBMR(self) -> float:
        """Basal Metabolic Rate using Mifflin–St Jeor Equation.

        Returns float kcal/day. Sex must be 'M' or 'F' (case-insensitive).
        """
        w = self._weight_kg()
        h = self._height_cm()
        a = int(self.age or 0)
        s = (self.sex or "").upper()
        if s == "M":
            return 88.362 + (13.397 * w) + (4.799 * h) - (5.677 * a)
        elif s == "F":
            return 447.593 + (9.247 * w) + (3.098 * h) - (4.330 * a)
        else:
            # fall back to average formula if sex unknown
            return  (88.362 + 447.593) / 2 + (13.397 + 9.247) / 2 * w + (4.799 + 3.098) / 2 * h - (5.677 + 4.330) / 2 * a

    def calculateBMI(self) -> float:
        """Calculate and return the user's BMI using height in meters and weight in kilograms."""
        h_m = self._height_cm() / 100.0
        w_kg = self._weight_kg()
        if h_m <= 0:
            return 0.0
        return w_kg / (h_m ** 2)

    def bmiCategory(self) -> str:
        """Return a descriptive category (Underweight/Normal/Overweight/Obese) based on BMI."""
        bmi = self.calculateBMI()
        if bmi <= 0:
            return "unknown"
        if bmi < 18.5:
            return "underweight"
        if bmi < 25:
            return "normal"
        if bmi < 30:
            return "overweight"
        return "obese"

    def dailyCalories(self, activity: str = "moderate") -> float:
        """Estimate daily calorie needs based on activity level and BMR."""
        factors = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very active": 1.9,
        }
        key = (activity or "").lower()
        factor = factors.get(key, 1.55)
        return self.calculateBMR() * factor

    def calorieTargetByGoal(self, activity: str = "moderate") -> float:
        g = (self.goal or "").lower()
        s = (self.sex or "").strip().lower()  # normalize

        # Explicit neutral-gender cases
        neutral_options = {"gender neutral", "prefer not to say"}

        # Neutral diet option: fixed 2000 calories/day baseline
        if s in neutral_options:
            base = 2000.0
            if g == "maintain":
                return base
            if g == "lose":
                return max(0.0, base - 500)
            if g == "gain":
                return base + 500
            return base

        # Normal male/female flow
        if s in ("m", "male"):
            sex_normalized = "M"
        elif s in ("f", "female"):
            sex_normalized = "F"
        else:
            # Unknown or unsupported → fallback to TDEE calculation using average BMR
            sex_normalized = None

        tdee = self.dailyCalories(activity)

        if g == "maintain":
            return tdee
        if g == "lose":
            return max(0.0, tdee - 500)
        if g == "gain":
            return tdee + 500
        return tdee
    
    # compatibility helper similar to old code
    def UserData(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "weight_lbs": self.weight_lbs,
            "height_ft": self.height_ft,
            "height_in": self.height_in,
            "age": self.age,
            "sex": self.sex,
            "goal": self.goal,
            "bmi": round(self.calculateBMI(), 1),
            "bmi_category": self.bmiCategory(),
            "bmr": round(self.calculateBMR(), 0),
        }

    def llmPromptText(self, activity: str = "moderate") -> str:
        bmi = self.calculateBMI()
        tdee = self.dailyCalories(activity)
        target = self.calorieTargetByGoal(activity)
        s = (self.sex or "").strip().lower()

        neutral_options = {"gender neutral", "prefer not to say"}
        neutral_note = ""
        if s in neutral_options:
            neutral_note = " A neutral 2000 kcal/day plan was applied because the user selected a gender-neutral option."

        return (
            f"User: {self.name}, {self.sex}, {self.age} years old. "
            f"Height: {self.height_ft} ft {self.height_in} in. "
            f"Weight: {self.weight_lbs} lbs. Goal: {self.goal}. "
            f"BMI: {bmi:.1f} ({self.bmiCategory()}). "
            f"BMR: {self.calculateBMR():.0f} kcal/day. "
            f"Maintenance calories (TDEE): {tdee:.0f} kcal/day. "
            f"Recommended daily calories for goal: {target:.0f} kcal/day."
            f"{neutral_note}"
        )

    def heightInInches(self) -> int:
        """Return the user's height converted to total inches."""
        return (self.height_ft or 0) * 12 + (self.height_in or 0)
    
    # convenience getters/setters (small compatibility layer)
    def getName(self):
        return self.name

    def getWeightLbs(self):
        return self.weight_lbs

    def getHeightFeetInches(self):
        return (self.height_ft, self.height_in)

    def getAge(self):
        return self.age

    def getSex(self):
        return self.sex

    def getGoal(self):
        return self.goal

    def setName(self, name: str):
        self.name = name

    def setWeightLbs(self, weight_lbs: float):
        self.weight_lbs = float(weight_lbs)

    def setHeight(self, feet: int, inches: int = 0):
        self.height_ft = int(feet)
        self.height_in = int(inches)

    def setAge(self, age: int):
        self.age = int(age)

    def setSex(self, sex: str):
        self.sex = sex.upper() if sex else sex

    def setGoal(self, goal: str):
        self.goal = goal.lower() if goal else goal

    def __str__(self) -> str:
        return (
            f"User({self.name}, {self.sex}, {self.age}y, "
            f"{self.height_ft}ft {self.height_in}in, "
            f"{self.weight_lbs}lbs, goal={self.goal})"
        )
        
    def __repr__(self) -> str:
        return (
            f"<User name={self.name!r} age={self.age} sex={self.sex!r} "
            f"goal={self.goal!r}>"
        )

