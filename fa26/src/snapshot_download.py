"""Verified raw IATI snapshots. Standard library only; never writes to RAW_DIR.

See docs/raw-snapshots.md. A snapshot is complete only for its recorded selection.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import urllib.request
from urllib.parse import urlparse
import uuid
import xml.etree.ElementTree as ET

from config import PUBLISHERS, ROOT, HOTSPOTS, EXTRA_DATASETS
from download import BULK, UA, get_json, wanted

DEFAULT_STORE = ROOT / "data" / "snapshots"
SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
CHUNK = 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def safe_name(value):
    if not isinstance(value, str) or not SAFE.fullmatch(value):
        raise ValueError(f"Unsafe file identifier: {value!r}")
    return value


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


@contextmanager
def locked(store):
    store.mkdir(parents=True, exist_ok=True)
    lock = store / ".capture-lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise RuntimeError("Snapshot store is busy. If a process crashed, confirm it stopped before removing .capture-lock.") from None
    try:
        (lock / "owner.json").write_text(json.dumps({"pid": os.getpid(), "started_at": now()}))
        yield
    finally:
        shutil.rmtree(lock)


def validate_xml(path):
    """Reject malformed/non-IATI/DTD XML, count activities with bounded memory."""
    tail = b""
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            # Removing nulls also catches DTD declarations in UTF-16/32 XML.
            scan = (tail + chunk).replace(b"\x00", b"").upper()
            if b"<!DOCTYPE" in scan or b"<!ENTITY" in scan:
                raise ValueError("DTD/entity declarations are not accepted")
            tail = chunk[-64:]
    root = None
    count = 0
    for event, element in ET.iterparse(path, events=("start", "end")):
        if root is None:
            root = element
            if root.tag != "iati-activities" or not root.get("version", "").startswith("2."):
                raise ValueError("Expected an IATI 2.x iati-activities XML document")
        if event == "end" and element.tag == "iati-activity":
            count += 1
            root.clear()
    return count


def digest_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def object_path(store, digest):
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise ValueError("Invalid object hash")
    return store / "objects" / digest[:2] / (digest + ".xml")


def selection(publishers, all_files=False, index_file=None, local_dir=None):
    """Use the team's existing publisher/file-selection rules, with strict failures."""
    if not publishers or len(publishers) != len(set(publishers)):
        raise ValueError("Select one or more distinct publishers")
    if set(publishers) - set(PUBLISHERS):
        raise ValueError("Unknown publisher")
    entries = []
    if local_dir is not None:
        for pub in publishers:
            paths = sorted((Path(local_dir) / pub).glob("*.xml"))
            if not paths:
                raise ValueError(f"No local XML files for {pub}")
            for path in paths:
                entries.append({"publisher": pub, "dataset": safe_name(path.stem), "source": str(path.resolve()), "local": True})
    else:
        index = json.loads(Path(index_file).read_text()) if index_file else get_json(f"{BULK}/datasets-minimal")
        for pub in publishers:
            datasets = [d for d in index["datasets"] if d.get("reporting_org_short_name") == pub
                        and wanted(d.get("short_name", ""), all_files)]
            if not datasets:
                raise ValueError(f"No selected datasets for {pub}; refusing an empty refresh")
            for d in datasets:
                name = safe_name(d.get("short_name", ""))
                url = (d.get("last_known_good_dataset") or {}).get("cached_dataset_url_xml") or d.get("source_url")
                if not url or urlparse(url).scheme not in ("http", "https"):
                    raise ValueError(f"No usable HTTP(S) URL for {pub}/{name}")
                entries.append({"publisher": pub, "dataset": name, "source": url, "local": False})
    keys = [(e["publisher"], e["dataset"]) for e in entries]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate publisher/dataset in selection")
    return entries


def read_manifest(store, run_id="latest"):
    if run_id == "latest":
        run_id = json.loads((store / "latest.json").read_text())["run_id"]
    safe_name(run_id)
    manifest = json.loads((store / "runs" / f"{run_id}.json").read_text())
    if manifest["status"] != "complete" or manifest["run_id"] != run_id:
        raise ValueError("Not a complete snapshot")
    files = manifest["files"]
    if not files or len(files) != manifest["selected_files"]:
        raise ValueError("Incomplete snapshot manifest")
    identities = set()
    for entry in files:
        key = (safe_name(entry["publisher"]), safe_name(entry["dataset"]))
        if key in identities:
            raise ValueError("Duplicate snapshot entry")
        identities.add(key)
        object_path(store, entry["sha256"])
    content = [(e["publisher"], e["dataset"], e["sha256"]) for e in files]
    actual = hashlib.sha256(json.dumps(sorted(content)).encode()).hexdigest()
    if actual != manifest["content_id"]:
        raise ValueError("Snapshot content identity mismatch")
    return manifest


def verify(store, run_id="latest"):
    manifest = read_manifest(store, run_id)
    for e in manifest["files"]:
        p = object_path(store, e["sha256"])
        if p.stat().st_size != e["bytes"] or digest_file(p) != e["sha256"]:
            raise ValueError(f"Checksum mismatch: {e['publisher']}/{e['dataset']}")
    return manifest


def capture(store, publishers, *, all_files=False, index_file=None, local_dir=None,
            max_bytes=512 * 1024 * 1024, opener=urllib.request.urlopen):
    store = Path(store)
    with locked(store):
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
        manifest = {"format_version": 1, "run_id": run_id, "started_at": now(), "status": "running",
                    "scope": {"publishers": publishers, "mode": "local-import" if local_dir else "bulk-download",
                              "all_files": all_files, "hotspots": sorted(HOTSPOTS), "extra_datasets": sorted(EXTRA_DATASETS)},
                    "files": []}
        try:
            entries = selection(publishers, all_files, index_file, local_dir)
            manifest["selected_files"] = len(entries)
            manifest["selection"] = entries
            with tempfile.TemporaryDirectory(dir=store, prefix=".staging-") as tmp:
                for i, entry in enumerate(entries):
                    staged = Path(tmp) / str(i)
                    response = Path(entry["source"]).open("rb") if entry["local"] else opener(
                        urllib.request.Request(entry["source"], headers=UA), timeout=300)
                    size = 0
                    h = hashlib.sha256()
                    with response as source, staged.open("wb") as dest:
                        for chunk in iter(lambda: source.read(CHUNK), b""):
                            size += len(chunk)
                            if size > max_bytes:
                                raise ValueError(f"File exceeds {max_bytes} byte limit: {entry['dataset']}")
                            dest.write(chunk)
                            h.update(chunk)
                        dest.flush()
                        os.fsync(dest.fileno())
                    count = validate_xml(staged)
                    digest = h.hexdigest()
                    obj = object_path(store, digest)
                    reused = obj.exists()
                    if reused:
                        if digest_file(obj) != digest:
                            raise ValueError("Stored object is corrupt; refusing to reuse it")
                    else:
                        obj.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(staged, obj)
                    manifest["files"].append({**entry, "sha256": digest, "bytes": size,
                                              "activities": count, "retrieved_at": now(), "reused": reused})
            content = [(e["publisher"], e["dataset"], e["sha256"]) for e in manifest["files"]]
            manifest["content_id"] = hashlib.sha256(json.dumps(sorted(content)).encode()).hexdigest()
            manifest.update(status="complete", finished_at=now())
            atomic_json(store / "runs" / f"{run_id}.json", manifest)
            verify(store, run_id)
            atomic_json(store / "latest.json", {"run_id": run_id})
            return manifest
        except Exception as exc:
            manifest.update(status="failed", finished_at=now(), error=f"{type(exc).__name__}: {exc}")
            atomic_json(store / "runs" / f"{run_id}.json", manifest)
            raise


def export_snapshot(store, destination, run_id="latest"):
    """Verified independent copy in publisher folders. Never overwrites an existing directory."""
    store, destination = Path(store), Path(destination)
    manifest = verify(store, run_id)
    if destination.exists():
        raise FileExistsError(f"Choose a new export directory: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(dir=destination.parent, prefix=".export-"))
    try:
        for e in manifest["files"]:
            target = temp / e["publisher"] / (e["dataset"] + ".xml")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(object_path(store, e["sha256"]), target)
            if digest_file(target) != e["sha256"]:
                raise ValueError("Export checksum mismatch")
        atomic_json(temp / "snapshot.json", manifest)
        # Reserve the destination so a concurrent export cannot replace it.
        destination.mkdir()
        try:
            os.replace(temp, destination)
        except BaseException:
            shutil.rmtree(destination)
            raise
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--store", type=Path, default=DEFAULT_STORE)
    sub = ap.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--publisher", action="append", choices=sorted(PUBLISHERS))
    cap.add_argument("--all-files", action="store_true")
    sources = cap.add_mutually_exclusive_group()
    sources.add_argument("--index-file", type=Path)
    sources.add_argument("--local-dir", type=Path)
    cap.add_argument("--max-mib", type=int, default=512)
    for cmd in ("verify", "export"):
        p = sub.add_parser(cmd)
        p.add_argument("--run", default="latest")
        if cmd == "export":
            p.add_argument("destination", type=Path)
    sub.add_parser("list")
    args = ap.parse_args()
    try:
        if args.command == "capture":
            if args.max_mib <= 0:
                ap.error("--max-mib must be positive")
            result = capture(args.store, args.publisher or sorted(PUBLISHERS), all_files=args.all_files,
                             index_file=args.index_file, local_dir=args.local_dir, max_bytes=args.max_mib * 1024 * 1024)
        elif args.command == "verify":
            result = verify(args.store, args.run)
        elif args.command == "export":
            result = export_snapshot(args.store, args.destination, args.run)
        else:
            for path in sorted((args.store / "runs").glob("*.json")):
                r = json.loads(path.read_text())
                print(r["run_id"], r["status"], len(r["files"]), r.get("error", ""))
            return
        print(json.dumps({k: result[k] for k in ("run_id", "status", "content_id", "selected_files")}, indent=2))
    except (OSError, ValueError, RuntimeError, ET.ParseError, KeyError) as exc:
        ap.exit(1, f"Snapshot operation failed: {exc}\n")


if __name__ == "__main__":
    main()
