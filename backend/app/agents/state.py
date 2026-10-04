"""Shared LangGraph state for a research run."""
from typing import Annotated, TypedDict


def merge_dicts(left: dict, right: dict) -> dict:
    return {**(left or {}), **(right or {})}


class ResearchState(TypedDict):
    ticker: str
    company: str
    horizon: str  # short | medium | long
    concall_text: str
    annual_text: str
    # agent name -> report; parallel branches write distinct keys, merged by the reducer
    reports: Annotated[dict, merge_dicts]
