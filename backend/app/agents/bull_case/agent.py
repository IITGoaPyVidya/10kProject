from app.agents.debate import DebaterAgent


class BullCaseAgent(DebaterAgent):
    name = "bull_case"
    side = "bullish"
    fixed_rating = "bullish"
    ratings = ("bullish",)
