# Clients

Each client gets a folder named with a slug (e.g. `clients/tidal-fitness/`)
containing:

- `fact_sheet.json` — required before running the pipeline. See
  `_example/fact_sheet.json` for the format, or `src/config.py` for the
  field list.
- `raw_responses.json` — written by `src/data_collection.py`.
- `scored_results.json` — written by `src/scoring.py`.
- `reports/<slug>_snapshot_<date>.pdf` — written by `src/report.py`.

Run the pipeline in order for a client:

```
python -m src.data_collection <client_slug>
python -m src.scoring <client_slug>
python -m src.report <client_slug>
```

`_example/` is a template, not a real client — copy it to start a new one:

```
cp -r clients/_example clients/<new-client-slug>
```
