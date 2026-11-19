"""
live_updates.py -- keep data/raw/ in sync with the IATI Bulk Data Service on
a 1-2 week cadence, and rebuild the graph CSVs only when something changed.

Why a class: the updater carries state between runs (when it last ran, a
fingerprint of every file it downloaded), and the tests need to swap out the
network calls. A LiveUpdater instance holds that state and those hooks.

How a run works:
  1. Is an update due? (now - last successful run >= interval_days, 7 by
     default). If not, exit quietly. This makes it safe to schedule the script
     DAILY: it only does work every 7-14 days, and a missed day (laptop off)
     just means it runs on the next scheduled day instead of skipping a week.
  2. Fetch the dataset index, pick files with the same rules as download.py
     (download.wanted), so the live update and a manual download agree.
  3. Download each file to a temp path, SHA-256 it, and compare against the
     fingerprint from the previous run. Only changed or new files replace the
     copy in data/raw/<publisher>/ (atomic rename, so a failed download never
     leaves a half-written XML behind). The previous version can be archived.
  4. If anything changed: run parse -> resolve (and optionally sync) via the
     existing pipeline scripts. If nothing changed, skip the rebuild.
  5. Write a state file and append one JSON line per run to a log, recording
     new / changed / unchanged / failed / vanished files. That log feeds the
     data-quality catalog (e.g. a publisher dropping a dataset).

Usage:
    python src/live_updates.py                  # run if due (default 7 days)
    python src/live_updates.py --interval-days 14
    python src/live_updates.py --force          # run now regardless
    python src/live_updates.py --dry-run        # show what would change
    python src/live_updates.py --status         # last run + next due date
    python src/live_updates.py --no-rebuild     # refresh raw XML only
    python src/live_updates.py --sync           # also copy CSVs to spaces/data
    python src/pipeline.py update               # same as the first line

Standard library only, like the rest of the pipeline.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import download
from config import PUBLISHERS, RAW_DIR, ROOT

SRC = Path(__file__).resolve().parent
LIVE_DIR = ROOT / "data" / "live_updates"
ARCHIVE_DIR = ROOT / "data" / "raw_archive"

log = logging.getLogger("live_updates")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _http_get_to_file(url: str, dest: Path, timeout: int = 300) -> None:
    req = urllib.request.Request(url, headers=download.UA)
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


class LiveUpdater:
    """Periodic, change-aware refresh of the raw IATI XML for our publishers."""

    def __init__(
        self,
        publishers=None,
        interval_days: float = 7,
        raw_dir: Path = RAW_DIR,
        state_dir: Path = LIVE_DIR,
        archive_dir: Path | None = ARCHIVE_DIR,
        all_files: bool = False,
        retries: int = 3,
        fetch_index=None,
        fetch_file=None,
    ):
        if not 1 <= interval_days <= 31:
            raise ValueError("interval_days should be between 1 and 31")
        self.publishers = list(publishers or PUBLISHERS)
        self.interval = dt.timedelta(days=interval_days)
        self.raw_dir = Path(raw_dir)
        self.state_dir = Path(state_dir)
        self.archive_dir = Path(archive_dir) if archive_dir else None
        self.all_files = all_files
        self.retries = retries
        # Network hooks (swapped out in tests)
        self.fetch_index = fetch_index or (
            lambda: download.get_json(f"{download.BULK}/datasets-minimal"))
        self.fetch_file = fetch_file or _http_get_to_file

        self.state_path = self.state_dir / "state.json"
        self.log_path = self.state_dir / "update_log.jsonl"
        self.lock_path = self.state_dir / "update.lock"
        self.state = self._load_state()

    # ---- state ----------------------------------------------------------
    def _load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"last_success": None, "files": {}}

    def _save_state(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        os.replace(tmp, self.state_path)

    def last_success(self) -> dt.datetime | None:
        s = self.state.get("last_success")
        return dt.datetime.fromisoformat(s) if s else None

    def next_due(self) -> dt.datetime | None:
        last = self.last_success()
        return last + self.interval if last else None

    def is_due(self, now: dt.datetime | None = None) -> bool:
        due = self.next_due()
        return due is None or (now or _now()) >= due

    # ---- locking (stops two scheduled runs overlapping) -----------------
    def _acquire_lock(self) -> bool:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists():
            age = time.time() - self.lock_path.stat().st_mtime
            if age < 6 * 3600:
                return False
            log.warning("removing stale lock (%.1f h old)", age / 3600)
            self.lock_path.unlink()
        self.lock_path.write_text(str(os.getpid()))
        return True

    def _release_lock(self) -> None:
        self.lock_path.unlink(missing_ok=True)

    # ---- selection ------------------------------------------------------
    def select_datasets(self, index: dict) -> tuple[dict, list[str]]:
        """Return ({publisher: [dataset, ...]}, [warnings])."""
        datasets = index.get("datasets", [])
        picked, warnings = {}, []
        for pub in self.publishers:
            mine = [d for d in datasets if d.get("reporting_org_short_name") == pub]
            if not mine:
                warnings.append(f"publisher '{pub}' not found in index "
                                "(check slug with download.py --find-publisher)")
            picked[pub] = [d for d in mine
                           if download.wanted(d.get("short_name", ""), self.all_files)]
        return picked, warnings

    # ---- one file -------------------------------------------------------
    def _download_with_retry(self, url: str, dest: Path) -> None:
        for attempt in range(1, self.retries + 1):
            try:
                self.fetch_file(url, dest)
                return
            except Exception as e:  # noqa: BLE001 -- network errors vary
                if attempt == self.retries:
                    raise
                wait = 5 * attempt
                log.warning("  retry %d/%d for %s in %ss (%s)",
                            attempt, self.retries, url, wait, e)
                time.sleep(wait)

    def _update_file(self, pub: str, d: dict, stamp: str, dry_run: bool) -> str:
        """Returns 'new' | 'changed' | 'unchanged' | 'failed' | 'no_url'."""
        name = d.get("short_name", d.get("id", "unknown"))
        good = d.get("last_known_good_dataset") or {}
        url = good.get("cached_dataset_url_xml") or d.get("source_url")
        key = f"{pub}/{name}"
        if not url:
            log.info("  skip %s: no usable URL", name)
            return "no_url"

        outdir = self.raw_dir / pub
        outdir.mkdir(parents=True, exist_ok=True)
        dest = outdir / f"{name}.xml"
        tmp = outdir / f".{name}.xml.part"
        try:
            self._download_with_retry(url, tmp)
        except Exception as e:  # noqa: BLE001
            tmp.unlink(missing_ok=True)
            log.error("  FAIL %s: %s", name, e)
            return "failed"

        new_hash = _sha256(tmp)
        old = self.state["files"].get(key)
        old_hash = old["sha256"] if old else (_sha256(dest) if dest.exists() else None)

        if old_hash == new_hash:
            tmp.unlink()
            status = "unchanged"
        else:
            status = "new" if old_hash is None else "changed"
            if dry_run:
                tmp.unlink()
            else:
                if status == "changed" and dest.exists() and self.archive_dir:
                    arch = self.archive_dir / stamp / pub
                    arch.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, arch / dest.name)
                os.replace(tmp, dest)
        if not dry_run:
            self.state["files"][key] = {
                "sha256": new_hash, "url": url, "checked": stamp,
                "changed": stamp if status != "unchanged"
                else (old or {}).get("changed", stamp),
            }
        log.info("  %-9s %s", status, name)
        return status

    # ---- rebuild --------------------------------------------------------
    def rebuild(self, sync: bool = False) -> None:
        for script in ("parse_filter.py", "resolve_orgs.py"):
            log.info("[rebuild] %s", script)
            r = subprocess.run([sys.executable, str(SRC / script)], cwd=SRC)
            if r.returncode != 0:
                raise RuntimeError(f"{script} failed (exit {r.returncode})")
        if sync:
            subprocess.run([sys.executable, str(SRC / "pipeline.py"), "sync"],
                           cwd=SRC, check=True)

    # ---- main entry -----------------------------------------------------
    def run(self, force=False, dry_run=False, rebuild=True, sync=False) -> dict:
        if not force and not self.is_due():
            log.info("not due; next update after %s", self.next_due().isoformat())
            return {"status": "skipped_not_due", "next_due": self.next_due().isoformat()}
        if not dry_run and not self._acquire_lock():
            log.warning("another update is running; exiting")
            return {"status": "skipped_locked"}

        started = _now()
        stamp = started.strftime("%Y%m%dT%H%M%SZ")
        summary = {"started": started.isoformat(), "dry_run": dry_run,
                   "counts": {}, "files": {}, "warnings": []}
        try:
            log.info("fetching dataset index ...")
            picked, warnings = self.select_datasets(self.fetch_index())
            summary["warnings"] += warnings
            for w in warnings:
                log.warning(w)

            seen = set()
            for pub, items in picked.items():
                log.info("[%s] %d datasets selected", pub, len(items))
                for d in items:
                    key = f"{pub}/{d.get('short_name', d.get('id', 'unknown'))}"
                    seen.add(key)
                    status = self._update_file(pub, d, stamp, dry_run)
                    summary["files"].setdefault(status, []).append(key)
                    time.sleep(0.3)  # be polite to the bulk service

            # Files we tracked before that the publisher no longer lists.
            # Kept on disk (not deleted) but flagged for review.
            vanished = sorted(k for k in self.state["files"]
                              if k.split("/")[0] in self.publishers and k not in seen)
            if vanished:
                summary["files"]["vanished"] = vanished
                summary["warnings"].append(
                    f"{len(vanished)} dataset(s) no longer in index: {', '.join(vanished)}")

            summary["counts"] = {k: len(v) for k, v in summary["files"].items()}
            changed = summary["counts"].get("new", 0) + summary["counts"].get("changed", 0)
            failed = summary["counts"].get("failed", 0)

            if dry_run:
                summary["status"] = "dry_run"
            else:
                if changed and rebuild:
                    self.rebuild(sync=sync)
                    summary["rebuilt"] = True
                else:
                    summary["rebuilt"] = False
                # A run with some failed files still counts as done, so we
                # don't hammer the service daily; failures are in the log.
                self.state["last_success"] = started.isoformat()
                self.state["last_summary"] = summary["counts"]
                self._save_state()
                summary["status"] = "ok" if not failed else "ok_with_failures"
        except Exception as e:  # noqa: BLE001
            summary["status"] = "error"
            summary["error"] = repr(e)
            log.exception("live update failed")
        finally:
            summary["finished"] = _now().isoformat()
            if not dry_run:
                self._release_lock()
                self.state_dir.mkdir(parents=True, exist_ok=True)
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(summary) + "\n")
        log.info("result: %s %s", summary["status"], summary.get("counts", {}))
        return summary

    def status(self) -> str:
        last, due = self.last_success(), self.next_due()
        if not last:
            return "never run; an update is due now"
        return (f"last update: {last:%Y-%m-%d %H:%M} UTC  "
                f"({self.state.get('last_summary', {})})\n"
                f"next due:    {due:%Y-%m-%d %H:%M} UTC  "
                f"({'DUE' if self.is_due() else 'not yet'})\n"
                f"tracked files: {len(self.state['files'])}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--interval-days", type=float, default=7,
                    help="minimum days between updates (default 7; use 14 for biweekly)")
    ap.add_argument("--force", action="store_true", help="run even if not due")
    ap.add_argument("--dry-run", action="store_true", help="report changes, write nothing")
    ap.add_argument("--status", action="store_true", help="show last/next run and exit")
    ap.add_argument("--no-rebuild", action="store_true", help="update raw XML only")
    ap.add_argument("--sync", action="store_true", help="also copy CSVs to spaces/data")
    ap.add_argument("--publisher", help="limit to one publisher slug")
    ap.add_argument("--all-files", action="store_true",
                    help="download every activity file, not just hotspot/global")
    ap.add_argument("--no-archive", action="store_true",
                    help="don't keep previous versions of changed files")
    args = ap.parse_args(argv)

    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(LIVE_DIR / "live_updates.log", encoding="utf-8")])

    up = LiveUpdater(
        publishers=[args.publisher] if args.publisher else None,
        interval_days=args.interval_days, all_files=args.all_files,
        archive_dir=None if args.no_archive else ARCHIVE_DIR)
    if args.status:
        print(up.status())
        return 0
    res = up.run(force=args.force, dry_run=args.dry_run,
                 rebuild=not args.no_rebuild, sync=args.sync)
    return 1 if res["status"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
