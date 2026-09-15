"""
LLM-judge scoring pipeline: feeds raw answers + fact sheet + competitors to Claude,
returns structured JSON (mentioned / position / sentiment / accuracy / citation).

Built out: Sep 15 catch-up session (Phase 1).

Usage:
    python -m src.scoring <client_slug>

Requires ANTHROPIC_API_KEY in .env (see .env.example). Requires
raw_responses.json to already exist for the client (run data_collection first).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.config import CLIENTS_DIR, load_fact_sheet

load_dotenv()

CLAUDE_MODEL = "claude-sonnet-4-5"

JUDGE_SYSTEM_PROMPT = """You are an impartial scoring judge for an AI-answer-engine \
visibility tool. You will be given a business's fact sheet, its known \
competitors, and one AI engine's answer to a prompt a potential customer \
might ask. Score how the business fared in that answer.

Respond with ONLY a JSON object (no markdown fences, no commentary) with \
exactly these keys:
{
  "mentioned": true|false,
  "position": <integer rank if the answer lists/ranks businesses and this \
business appears, else null>,
  "sentiment": "positive"|"neutral"|"negative"|"not_mentioned",
  "accuracy": "accurate"|"inaccurate"|"not_applicable",
  "accuracy_notes": "<short note only if inaccurate, else empty string>",
  "citation_present": true|false,
  "competitors_mentioned": ["<competitor name>", ...]
}

"accuracy" judges whether anything the answer states about the business \
itself (hours, pricing, location, services) is wrong, based on the fact \
sheet — not whether the business is a good recommendation. \
"citation_present" is true if the answer includes a source link/citation \
for the business itself. Use "not_mentioned" for sentiment and \
"not_applicable" for accuracy when the business does not appear at all."""


def _build_judge_prompt(fact_sheet: dict, prompt: str, answer: str) -> str:
    return f"""BUSINESS FACT SHEET:
Name: {fact_sheet['name']}
Type: {fact_sheet['business_type']}
Location: {fact_sheet['location']}
Hours: {fact_sheet['hours']}
Pricing: {fact_sheet['pricing']}
USPs: {', '.join(fact_sheet['usps'])}
Known competitors: {', '.join(fact_sheet['competitors'])}

PROMPT ASKED: {prompt}

AI ENGINE ANSWER:
{answer}

Score this answer for {fact_sheet['name']} per the JSON schema in your instructions."""


def _parse_judge_response(text: str) -> dict:
    """Strip stray markdown fences if the model adds them, then parse JSON."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned.strip())


def _judge(fact_sheet: dict, prompt: str, answer: str, api_key: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_judge_prompt(fact_sheet, prompt, answer)}],
    )
    text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
    return _parse_judge_response(text)


def score_snapshot(client_slug: str) -> Path:
    """
    Load clients/<client_slug>/raw_responses.json, score every engine answer
    with Claude as an LLM judge, and save results to
    clients/<client_slug>/scored_results.json.

    Per-item errors (API failure or unparseable JSON) are caught and logged
    into the results list rather than aborting the whole run.
    """
    fact_sheet = load_fact_sheet(client_slug)

    raw_path = CLIENTS_DIR / client_slug / "raw_responses.json"
    if not raw_path.exists():
        raise FileNotFoundError(
            f"No raw_responses.json for '{client_slug}' — run data_collection.py first (expected {raw_path})"
        )
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    scored_results = []
    for item in raw_data["results"]:
        prompt = item["prompt"]
        engines_scored = {}

        for engine_name, engine_data in item["engines"].items():
            if "error" in engine_data:
                engines_scored[engine_name] = {"error": f"skipped — collection failed: {engine_data['error']}"}
                continue

            if not anthropic_key:
                engines_scored[engine_name] = {"error": "ANTHROPIC_API_KEY not set"}
                continue

            try:
                score = _judge(fact_sheet, prompt, engine_data["answer"], anthropic_key)
                score["citation_present"] = score.get("citation_present", False) or bool(engine_data.get("citations"))
                engines_scored[engine_name] = score
            except json.JSONDecodeError as e:
                engines_scored[engine_name] = {"error": f"judge returned unparseable JSON: {e}"}
            except Exception as e:
                engines_scored[engine_name] = {"error": str(e)}

        scored_results.append({"prompt": prompt, "engines": engines_scored})

    output = {
        "client": client_slug,
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "results": scored_results,
    }

    out_path = CLIENTS_DIR / client_slug / "scored_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    return out_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m src.scoring <client_slug>")
        sys.exit(1)

    saved_to = score_snapshot(sys.argv[1])
    print(f"Saved scored results to {saved_to}")
