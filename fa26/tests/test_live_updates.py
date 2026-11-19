"""LiveUpdater tests: offline (fake index + fake downloads), temp dirs only."""
import datetime as dt
import json
from pathlib import Path

import pytest

import live_updates
from live_updates import LiveUpdater

INDEX = json.loads((Path(__file__).parent / "fixture_datasets_minimal.json")
                   .read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(live_updates.time, "sleep", lambda s: None)


class FakeServer:
    """Serves '<xml>{url}{version}</xml>'; bump version[url] to 'publish' a change."""
    def __init__(self):
        self.version, self.fail, self.calls = {}, set(), 0

    def __call__(self, url, dest):
        self.calls += 1
        if url in self.fail:
            raise OSError("boom")
        Path(dest).write_text(f"<xml>{url}{self.version.get(url, 0)}</xml>")


def make(tmp_path, server, **kw):
    kw.setdefault("publishers", ["oxfamgb", "wfp"])
    return LiveUpdater(raw_dir=tmp_path / "raw", state_dir=tmp_path / "state",
                       archive_dir=tmp_path / "archive", fetch_index=lambda: INDEX,
                       fetch_file=server, **kw)


def test_first_run_downloads_selected_files(tmp_path):
    up = make(tmp_path, FakeServer())
    res = up.run(rebuild=False)
    assert res["status"] == "ok"
    # oxfamgb-ss (hotspot) + oxfamgb-998 (global); -ke and orgfile excluded.
    # wfp-sd hotspot (source_url fallback), wfp-menaeeca (not per-country naming)
    assert sorted(res["files"]["new"]) == [
        "oxfamgb/oxfamgb-998", "oxfamgb/oxfamgb-ss", "wfp/wfp-menaeeca", "wfp/wfp-sd"]
    assert (tmp_path / "raw" / "oxfamgb" / "oxfamgb-ss.xml").exists()
    assert not list((tmp_path / "raw").rglob("*.part"))


def test_not_due_skips_without_network(tmp_path):
    server = FakeServer()
    make(tmp_path, server).run(rebuild=False)
    calls = server.calls
    res = make(tmp_path, server).run(rebuild=False)   # fresh instance reads state
    assert res["status"] == "skipped_not_due"
    assert server.calls == calls


def test_due_after_interval(tmp_path):
    up = make(tmp_path, FakeServer(), interval_days=14)
    up.run(rebuild=False)
    last = up.last_success()
    assert not up.is_due(last + dt.timedelta(days=13))
    assert up.is_due(last + dt.timedelta(days=14))


def test_only_changed_files_replaced_and_rebuild_triggered(tmp_path, monkeypatch):
    server = FakeServer()
    up = make(tmp_path, server)
    up.run(rebuild=False)

    rebuilt = []
    monkeypatch.setattr(LiveUpdater, "rebuild", lambda self, sync=False: rebuilt.append(1))
    ss_url = "https://bulk-data.iatistandard.org/oxfamgb/oxfamgb-ss.xml"
    server.version[ss_url] = 1
    res = up.run(force=True)
    assert res["files"]["changed"] == ["oxfamgb/oxfamgb-ss"]
    assert res["counts"]["unchanged"] == 3
    assert rebuilt == [1]
    # previous version archived
    assert len(list((tmp_path / "archive").rglob("oxfamgb-ss.xml"))) == 1


def test_no_change_means_no_rebuild(tmp_path, monkeypatch):
    up = make(tmp_path, FakeServer())
    up.run(rebuild=False)
    monkeypatch.setattr(LiveUpdater, "rebuild",
                        lambda self, sync=False: pytest.fail("should not rebuild"))
    assert make(tmp_path, FakeServer()).run(force=True)["rebuilt"] is False


def test_failed_download_keeps_old_file(tmp_path):
    server = FakeServer()
    up = make(tmp_path, server, retries=2)
    up.run(rebuild=False)
    ss = tmp_path / "raw" / "oxfamgb" / "oxfamgb-ss.xml"
    before = ss.read_text()
    url = "https://bulk-data.iatistandard.org/oxfamgb/oxfamgb-ss.xml"
    server.fail.add(url)
    server.version[url] = 9
    res = up.run(force=True, rebuild=False)
    assert res["status"] == "ok_with_failures"
    assert ss.read_text() == before


def test_vanished_dataset_flagged_and_unknown_publisher_warned(tmp_path):
    up = make(tmp_path, FakeServer(), publishers=["oxfamgb", "oxfamus"])
    up.run(rebuild=False)
    smaller = {"datasets": [d for d in INDEX["datasets"] if d["short_name"] != "oxfamgb-998"]}
    up.fetch_index = lambda: smaller
    res = up.run(force=True, rebuild=False)
    assert res["files"]["vanished"] == ["oxfamgb/oxfamgb-998"]
    assert any("oxfamus" in w and "not found" in w for w in res["warnings"])


def test_dry_run_writes_nothing(tmp_path):
    up = make(tmp_path, FakeServer())
    res = up.run(dry_run=True)
    assert res["status"] == "dry_run"
    assert not (tmp_path / "state" / "state.json").exists()
    assert not list((tmp_path / "raw").rglob("*.xml"))


def test_log_appended_each_run(tmp_path):
    up = make(tmp_path, FakeServer())
    up.run(rebuild=False)
    up.run(force=True, rebuild=False)
    lines = (tmp_path / "state" / "update_log.jsonl").read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["status"] == "ok"
