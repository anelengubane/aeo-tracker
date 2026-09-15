"""
Dry-run end-to-end test — no real API calls (Perplexity + Claude are both
mocked). Run with a dummy client to confirm the full pipeline works:
prompt filling -> data collection -> LLM-judge scoring -> PDF report.

Usage:
    python tests/test_pipeline.py
"""

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import CLIENTS_DIR, load_fact_sheet, build_prompt_panel, FactSheetError

DRYRUN_SLUG = "_dryrun_test"


def _make_perplexity_response():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [{"message": {"content": "Example Business is a well-reviewed gym in Umhlanga."}}],
        "citations": ["https://example.com/example-business"],
    }
    return resp


def _make_claude_text_block(text, citations=None):
    block = MagicMock()
    block.type = "text"
    block.text = text
    block.citations = citations or []
    return block


def setup_dryrun_client():
    src_dir = CLIENTS_DIR / "_example"
    dst_dir = CLIENTS_DIR / DRYRUN_SLUG
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)
    return dst_dir


def test_config_loading_and_panel():
    fact_sheet = load_fact_sheet(DRYRUN_SLUG)
    panel = build_prompt_panel(fact_sheet)
    assert len(panel) == 10, f"expected 10 prompts, got {len(panel)}"
    assert "Umhlanga" in panel[0]
    assert "gym" in panel[0]
    print(f"  config: {len(panel)} prompts built OK, e.g. {panel[0]!r}")


def test_fact_sheet_error_on_missing_client():
    try:
        load_fact_sheet("_does_not_exist")
        raise AssertionError("expected FactSheetError")
    except FactSheetError:
        pass
    print("  config: missing-client error handling OK")


def test_data_collection_mocked():
    from src import data_collection

    with patch.object(data_collection, "requests") as mock_requests, \
         patch("anthropic.Anthropic") as mock_anthropic_cls, \
         patch.dict("os.environ", {"PERPLEXITY_API_KEY": "fake", "ANTHROPIC_API_KEY": "fake"}):

        mock_requests.post.return_value = _make_perplexity_response()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [_make_claude_text_block(
            "Example Business is a solid pick for a gym in Umhlanga.",
        )]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_cls.return_value = mock_client

        out_path = data_collection.run_snapshot(DRYRUN_SLUG)
        assert out_path.exists()
        with open(out_path) as f:
            data = json.load(f)
        assert len(data["results"]) == 10
        assert data["results"][0]["engines"]["perplexity"]["answer"]
        assert data["results"][0]["engines"]["claude"]["answer"]
        assert mock_requests.post.call_count == 10
        assert mock_client.messages.create.call_count == 10
    print("  data_collection: 10 prompts x 2 engines, mocked calls OK, raw_responses.json written")


def test_data_collection_handles_per_prompt_errors():
    from src import data_collection

    with patch.object(data_collection, "requests") as mock_requests, \
         patch("anthropic.Anthropic") as mock_anthropic_cls, \
         patch.dict("os.environ", {"PERPLEXITY_API_KEY": "fake", "ANTHROPIC_API_KEY": "fake"}):

        mock_requests.post.side_effect = Exception("simulated network error")
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[_make_claude_text_block("fine")]
        )
        mock_anthropic_cls.return_value = mock_client

        out_path = data_collection.run_snapshot(DRYRUN_SLUG)
        with open(out_path) as f:
            data = json.load(f)
        assert "error" in data["results"][0]["engines"]["perplexity"]
        assert "error" not in data["results"][0]["engines"]["claude"]
    print("  data_collection: per-prompt error isolation OK (one engine failing doesn't kill the run)")


def test_scoring_mocked():
    from src import data_collection, scoring

    with patch.object(data_collection, "requests") as mock_requests, \
         patch("anthropic.Anthropic") as mock_anthropic_cls, \
         patch.dict("os.environ", {"PERPLEXITY_API_KEY": "fake", "ANTHROPIC_API_KEY": "fake"}):
        mock_requests.post.return_value = _make_perplexity_response()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[_make_claude_text_block("Example Business is a solid pick for a gym in Umhlanga.")]
        )
        mock_anthropic_cls.return_value = mock_client
        data_collection.run_snapshot(DRYRUN_SLUG)

    judge_json = json.dumps({
        "mentioned": True,
        "position": 1,
        "sentiment": "positive",
        "accuracy": "accurate",
        "accuracy_notes": "",
        "citation_present": True,
        "competitors_mentioned": ["Virgin Active Umhlanga"],
    })

    with patch("anthropic.Anthropic") as mock_anthropic_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake"}):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[_make_claude_text_block(judge_json)]
        )
        mock_anthropic_cls.return_value = mock_client

        out_path = scoring.score_snapshot(DRYRUN_SLUG)
        assert out_path.exists()
        with open(out_path) as f:
            scored = json.load(f)
        assert scored["results"][0]["engines"]["perplexity"]["mentioned"] is True
        assert scored["results"][0]["engines"]["perplexity"]["sentiment"] == "positive"
    print("  scoring: LLM-judge JSON parsing OK, scored_results.json written")


def test_scoring_handles_bad_json_from_judge():
    from src import scoring

    with patch("anthropic.Anthropic") as mock_anthropic_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake"}):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[_make_claude_text_block("not valid json at all")]
        )
        mock_anthropic_cls.return_value = mock_client

        out_path = scoring.score_snapshot(DRYRUN_SLUG)
        with open(out_path) as f:
            scored = json.load(f)
        assert "error" in scored["results"][0]["engines"]["perplexity"]
    print("  scoring: unparseable judge output is caught, not fatal")


def test_report_generation():
    from src import report
    from pypdf import PdfReader

    out_path = report.generate_report(DRYRUN_SLUG)
    assert out_path.exists()
    assert out_path.stat().st_size > 1000, "PDF looks suspiciously small/empty"

    page_count = len(PdfReader(str(out_path)).pages)
    assert page_count == 1, f"Snapshot report must be 1 page, got {page_count} (full 10-prompt panel scenario)"
    print(f"  report: PDF written to {out_path} ({out_path.stat().st_size} bytes, {page_count} page)")

    # Keep a copy outside the client dir (which gets cleaned up) so it can
    # be inspected/shared after the test run finishes.
    sample_dir = Path(__file__).resolve().parent.parent / "sample_output"
    sample_dir.mkdir(exist_ok=True)
    shutil.copy(out_path, sample_dir / "example_business_snapshot_sample.pdf")
    print(f"  report: sample copied to {sample_dir / 'example_business_snapshot_sample.pdf'}")


def run_all():
    tests = [
        test_config_loading_and_panel,
        test_fact_sheet_error_on_missing_client,
        test_data_collection_mocked,
        test_data_collection_handles_per_prompt_errors,
        test_scoring_mocked,
        test_report_generation,  # must follow test_scoring_mocked directly — it reads that run's good scores
        test_scoring_handles_bad_json_from_judge,
    ]
    setup_dryrun_client()
    try:
        for t in tests:
            print(f"Running {t.__name__}...")
            t()
        print("\nAll dry-run tests passed. No real API calls were made.")
    finally:
        dryrun_dir = CLIENTS_DIR / DRYRUN_SLUG
        if dryrun_dir.exists():
            shutil.rmtree(dryrun_dir)


if __name__ == "__main__":
    run_all()
