# Verified raw IATI snapshots

## Goal and scope

Preserve reproducible versions of raw XML from Oxfam GB, Oxfam America and WFP,
reuse unchanged file contents, and keep the last successful snapshot available
when a refresh fails. This supports the project's recurring ingestion,
raw/cleaned separation and reproducibility requirements, and the client's
request to retain earlier reports.

This first increment does not change the graph schema, run models, write to
Neo4j, schedule downloads, compare individual transactions, or publish cloud
archives. It does not make the existing `download.py` command transactional.
Use this new command explicitly to get snapshot protection.

## Quick start

Run from `fa26/`, using Python 3.10 or newer. Runtime uses only the standard library.

```bash
# Offline first: archive existing local publisher folders.
python src/snapshot_download.py capture --local-dir /absolute/path/to/raw

# Or fetch selected datasets for all three configured publishers.
python src/snapshot_download.py capture

# Inspect and verify the newest successful snapshot.
python src/snapshot_download.py list
python src/snapshot_download.py verify

# Export an independent copy into a NEW directory for processing.
python src/snapshot_download.py export /absolute/path/to/run-input
IATI_RAW_DIR=/absolute/path/to/run-input python src/pipeline.py refresh
```

The final command runs the existing parser and resolver and writes their normal
cleaned outputs. Those outputs are **not** transactional in this increment.
The original parser remains unchanged; `config.py` accepts the optional
`IATI_RAW_DIR` environment variable, otherwise retaining its original default.
Do not run the old downloader with that override pointing at a historical export.

Use `--store /absolute/path` **before** the subcommand to choose storage outside
`fa26/data/snapshots`. `capture --publisher wfp` selects one publisher;
repeat `--publisher` to select several. `--all-files` disables the existing
hotspot filename heuristic. `--index-file` supplies a saved Bulk Data index;
it still downloads the XML files from the recorded URLs. `--local-dir` instead
imports every `.xml` file under each selected publisher's directory, without
network calls. Local imports cannot reconstruct the original download date or
URL: their source is the local file and their timestamp is the import time.

To verify or export an older version, use the run ID printed by `list`:

```bash
python src/snapshot_download.py verify --run RUN_ID
python src/snapshot_download.py export /absolute/path/to/old-input --run RUN_ID
```

## What is stored

- `objects/<hash-prefix>/<sha256>.xml`: one copy of each unique file content.
- `runs/<UTC-time-and-unique-id>.json`: per-run selection, status, provenance,
  hashes, byte counts, activity counts and errors. A new run is recorded even
  when every file is unchanged.
- `latest.json`: pointer to the most recently completed selected batch.

A run records publishers, hotspot codes, forced datasets, selection mode,
source paths/URLs, retrieval times, and a content identity derived from the
sorted publisher/dataset/hash list. The identity does not change simply because
another download happened later. It identifies content and file membership,
not the hunger-filter rules or cleaned graph version.

`latest` means latest **recorded selection**, not necessarily all three
publishers. A single-publisher run advances it too. Use explicit run IDs or a
separate store for different scopes. An entirely empty selection, missing
publisher, duplicate dataset, missing URL, malformed XML, wrong root/version,
DTD declaration, download failure or oversized file fails the batch. Valid
IATI files with zero activities are allowed and recorded as zero.

Files stream to temporary storage, are parsed as IATI 2.x XML, hashed and then
stored by content. Existing objects are verified before reuse. The manifest
is verified before the latest pointer is atomically replaced. XML structural
validation is not full IATI XSD or business-rule validation; the existing
cleaning and hunger filtering still run separately.

## Failure and recovery

A failed capture returns a nonzero exit code, records a failed run, and leaves
`latest.json` unchanged. Successfully staged objects from a partially failed
run may remain in storage and be reused later. No automatic deletion or
retention policy is applied. File-level checks do not guarantee the publisher
has supplied all real-world activities or that upstream files were updated
at the same instant.

Capture uses an exclusive store lock. If the machine/process is forcibly
terminated, confirm no capture is running before removing `.capture-lock`.
Abandoned `.staging-*` folders can then be removed. Keep `objects`, `runs` and
`latest.json`. A forced interruption may leave no failed-run report, but does
not publish a partial new snapshot. Atomic replacement targets a local
filesystem; full power-loss durability and shared/network filesystem locking
are not claimed.

Exports check hashes, create independent copies, and refuse an existing
destination. Treat exported inputs as read-only by convention. This is not a
filesystem permission or tamper-proof archive. Re-verify archived objects to
detect modification. Back up the store separately; deduplication is not a backup.

A file defaults to a 512 MiB limit (`capture --max-mib 1024` to change it).
Unchanged files are downloaded and verified again but not stored twice.
No conditional HTTP caching, automatic retries, or background schedules yet.

## Tests and demo

```bash
# Existing pipeline tests plus the new tests (pytest is a development dependency).
python -m pytest -q

# New snapshot tests alone, without third-party packages.
PYTHONPATH=src python -m unittest discover -s tests -p test_snapshots.py -v

# Generates synthetic versions, simulates a failure, restores version one.
python scripts/demo_snapshots.py /tmp/iati-snapshot-demo
```

Use a new demo directory. `summary.json` states that fixtures are synthetic.
Tests cover reuse, changed bytes, bad/empty XML, DTDs, missing publishers,
duplicate entries, timeouts, corruption, size limits, concurrent captures,
export failures, restore and compatibility with the existing hunger parser.

## Next increment

After team review, connect verified snapshots to a staging directory for cleaned
outputs and validate those outputs before promoting a complete pipeline run.
Only then add scheduled refreshes and database publication. Activity-level
change reports can follow once matching rules are agreed. Start with these
three publishers, not the optional whole-IATI archive.
