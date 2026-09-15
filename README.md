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
3. Add a client fact sheet under `clients/<client-name>/fact_sheet.json` (see `clients/README.md` or `src/config.py` for the expected fields — `clients/_example/` has a working template to copy).

## Pipeline

Run in order for a client:

```
python -m src.data_collection <client_slug>
python -m src.scoring <client_slug>
python -m src.report <client_slug>
```

1. `src/data_collection.py` — sends the prompt panel to Perplexity + Claude, stores raw answers and citations
2. `src/scoring.py` — feeds raw answers + fact sheet + competitors to Claude as an LLM judge, returns structured scores (mentioned / position / sentiment / accuracy / citation)
3. `src/report.py` — generates the 1-page Snapshot PDF from the scored data

## Testing

`tests/test_pipeline.py` runs the full pipeline against a copy of the
`_example` client with Perplexity and Claude both mocked — no API keys or
network calls needed, no real quota spent. Useful for checking the pipeline
still works after a code change, before spending real API calls on it.

```
pip install -r requirements-dev.txt
python tests/test_pipeline.py
```

## Structure

```
aeo-tracker/
├── .env.example
├── .gitignore
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── src/
│   ├── config.py
│   ├── data_collection.py
│   ├── scoring.py
│   └── report.py
├── clients/
│   ├── README.md
│   └── _example/
│       └── fact_sheet.json
└── tests/
    └── test_pipeline.py
```
