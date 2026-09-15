"""
Sends the prompt panel to Perplexity + Claude APIs and stores raw answers + citations.

Built out: Sep 15 catch-up session (Phase 1).

Usage:
    python -m src.data_collection <client_slug>

Requires ANTHROPIC_API_KEY and PERPLEXITY_API_KEY in .env (see .env.example).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from src.config import CLIENTS_DIR, build_prompt_panel, load_fact_sheet

load_dotenv()

# Check docs.claude.com / Perplexity's model list before running if much
# time has passed since Sep 2026 — these get retired/renamed.
PERPLEXITY_MODEL = "sonar"
CLAUDE_MODEL = "claude-sonnet-4-5"
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


def _query_perplexity(prompt: str, api_key: str) -> dict:
    """Send one prompt to Perplexity, return {answer, citations}."""
    resp = requests.post(
        PERPLEXITY_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": PERPLEXITY_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    answer = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])
    return {"answer": answer, "citations": citations}


def _query_claude(prompt: str, api_key: str) -> dict:
    """Send one prompt to Claude with web search enabled, return {answer, citations}."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    answer_parts = []
    citations = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            answer_parts.append(block.text)
            for citation in getattr(block, "citations", None) or []:
                url = getattr(citation, "url", None)
                if url:
                    citations.append(url)

    return {"answer": "".join(answer_parts), "citations": citations}


def run_snapshot(client_slug: str) -> Path:
    """
    Load the client's fact sheet, fill the prompt panel, query Perplexity
    and Claude for every prompt, and save results to
    clients/<client_slug>/raw_responses.json.

    Per-prompt errors are caught and logged into the results list rather
    than aborting the whole run. Returns the path the results were saved to.
    """
    fact_sheet = load_fact_sheet(client_slug)
    prompts = build_prompt_panel(fact_sheet)

    perplexity_key = os.environ.get("PERPLEXITY_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    results = []
    for prompt in prompts:
        prompt_result = {"prompt": prompt, "engines": {}}

        if perplexity_key:
            try:
                prompt_result["engines"]["perplexity"] = _query_perplexity(prompt, perplexity_key)
            except Exception as e:
                prompt_result["engines"]["perplexity"] = {"error": str(e)}
        else:
            prompt_result["engines"]["perplexity"] = {"error": "PERPLEXITY_API_KEY not set"}

        if anthropic_key:
            try:
                prompt_result["engines"]["claude"] = _query_claude(prompt, anthropic_key)
            except Exception as e:
                prompt_result["engines"]["claude"] = {"error": str(e)}
        else:
            prompt_result["engines"]["claude"] = {"error": "ANTHROPIC_API_KEY not set"}

        results.append(prompt_result)

    output = {
        "client": client_slug,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }

    out_path = CLIENTS_DIR / client_slug / "raw_responses.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    return out_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m src.data_collection <client_slug>")
        sys.exit(1)

    saved_to = run_snapshot(sys.argv[1])
    print(f"Saved raw responses to {saved_to}")
