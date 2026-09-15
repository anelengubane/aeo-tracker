"""
Client fact sheet and prompt panel templates.

A client fact sheet (clients/<client-name>/fact_sheet.json) should contain:
{
  "name": "Business name",
  "niche": "fitness" | "dental",
  "business_type": "gym" | "dental clinic" | ...,
  "location": "Suburb, City",
  "hours": "...",
  "pricing": "...",
  "usps": ["...", "..."],
  "competitors": ["Competitor A", "Competitor B"]
}
"""

import json
from pathlib import Path

REQUIRED_FACT_SHEET_FIELDS = [
    "name",
    "niche",
    "business_type",
    "location",
    "hours",
    "pricing",
    "usps",
    "competitors",
]

CLIENTS_DIR = Path(__file__).resolve().parent.parent / "clients"

# Generic 10-prompt panel template — usable for either niche by filling in
# {business_type} and {area}. Extend to 20/35 prompts for Growth/Pro tiers.
# area is the suburb/area portion of the fact sheet's "location" field.
GENERIC_PROMPT_PANEL = [
    "What is the best {business_type} in {area}?",
    "Recommend a {business_type} near {area}.",
    "Who are the top-rated {business_type} businesses in {area}?",
    "I'm looking for a good {business_type} in {area}, what would you suggest?",
    "What are the most popular {business_type} options in {area}?",
    "Can you list some highly reviewed {business_type} in {area}?",
    "Which {business_type} in {area} has the best reputation?",
    "What {business_type} would you recommend for someone new to {area}?",
    "Compare the top {business_type} choices in {area}.",
    "Where should I go for a {business_type} in {area}?",
]


class FactSheetError(ValueError):
    """Raised when a client fact sheet is missing or malformed."""


def load_fact_sheet(client_slug: str) -> dict:
    """
    Load and validate clients/<client_slug>/fact_sheet.json.

    Raises FactSheetError with a plain-language message if the file is
    missing or a required field is absent, rather than a raw exception.
    """
    path = CLIENTS_DIR / client_slug / "fact_sheet.json"
    if not path.exists():
        raise FactSheetError(
            f"No fact sheet found for '{client_slug}' — expected {path}"
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            fact_sheet = json.load(f)
    except json.JSONDecodeError as e:
        raise FactSheetError(f"{path} is not valid JSON: {e}") from e

    missing = [field for field in REQUIRED_FACT_SHEET_FIELDS if not fact_sheet.get(field)]
    if missing:
        raise FactSheetError(
            f"{path} is missing required field(s): {', '.join(missing)}"
        )

    return fact_sheet


def area_from_location(location: str) -> str:
    """
    Take the suburb/area portion of a "Suburb, City" location string.
    Falls back to the full string if there's no comma.
    """
    return location.split(",")[0].strip()


def build_prompt_panel(fact_sheet: dict) -> list[str]:
    """
    Fill GENERIC_PROMPT_PANEL with this client's business_type and area.
    """
    area = area_from_location(fact_sheet["location"])
    return [
        prompt.format(business_type=fact_sheet["business_type"], area=area)
        for prompt in GENERIC_PROMPT_PANEL
    ]
