# AEO Tracker

AEO/GEO visibility tracking pipeline for agency clients. Sends a fixed panel of prompts to Perplexity and Claude, scores the answers for brand mentions/position/sentiment/accuracy, and generates a 1-page Snapshot report per client.

## Setup

1. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # on Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in your API keys:
   ```
   cp .env.example .env
   ```
3. Add a client fact sheet under `clients/<client-name>/fact_sheet.json` (see `src/config.py` for the expected fields).

## Pipeline

1. `src/data_collection.py` — sends the prompt panel to Perplexity + Claude, stores raw answers and citations
2. `src/scoring.py` — feeds raw answers + fact sheet + competitors to Claude as an LLM judge, returns structured scores (mentioned / position / sentiment / accuracy / citation)
3. `src/report.py` — generates the 1-page Snapshot PDF from the scored data

## Structure

```
aeo-tracker/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── src/
│   ├── config.py
│   ├── data_collection.py
│   ├── scoring.py
│   └── report.py
├── clients/
└── tests/
```
