"""
Client fact sheet and prompt panel templates.

A client fact sheet (clients/<client-name>/fact_sheet.json) should contain:
{
  "name": "Business name",
  "niche": "fitness" | "dental",
  "location": "Suburb, City",
  "hours": "...",
  "pricing": "...",
  "usps": ["...", "..."],
  "competitors": ["Competitor A", "Competitor B"]
}
"""

# Generic 10-prompt panel template — usable for either niche by filling in
# {business_type} and {area}. Extend to 20/35 prompts for Growth/Pro tiers.
GENERIC_PROMPT_PANEL = [
    "What is the best {business_type} in {area}?",
    "Recommend a {business_type} near {area}.",
    "Who are the top-rated {business_type} businesses in {area}?",
    # TODO: fill remaining prompts during Week 1, Wed Sep 9 session
]
