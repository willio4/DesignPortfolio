# ---------------------------------Pat-----------------------------------------
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