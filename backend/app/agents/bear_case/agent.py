from app.agents.debate import DebaterAgent


class BearCaseAgent(DebaterAgent):
    name = "bear_case"
    side = "bearish"
    fixed_rating = "bearish"
    ratings = ("bearish",)
