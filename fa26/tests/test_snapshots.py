"""Offline snapshot acceptance tests: no real downloads, API keys or Neo4j."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import snapshot_download as s

XML = b'<iati-activities version="2.03"><iati-activity><iati-identifier>EXAMPLE-1</iati-identifier></iati-activity></iati-activities>'


class Snapshots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.store = self.base / 'store'
        self.raw = self.base / 'raw'
        for pub in ('wfp', 'oxfamgb', 'oxfamus'):
            (self.raw / pub).mkdir(parents=True)
            (self.raw / pub / 'activities.xml').write_bytes(XML)

    def capture(self, **kw):
        return s.capture(self.store, ['wfp', 'oxfamgb', 'oxfamus'], local_dir=self.raw, **kw)

    def latest(self):
        return (self.store / 'latest.json').read_bytes()

    def test_complete_version_and_verify(self):
        r = self.capture()
        self.assertEqual(r['selected_files'], 3)
        self.assertEqual(s.verify(self.store)['run_id'], r['run_id'])
        self.assertEqual(r['files'][0]['activities'], 1)

    def test_unchanged_downloads_deduplicate_across_versions_and_publishers(self):
        a, b = self.capture(), self.capture()
        self.assertNotEqual(a['run_id'], b['run_id'])
        self.assertEqual(a['content_id'], b['content_id'])
        self.assertTrue(all(e['reused'] for e in b['files']))
        self.assertEqual(len(list((self.store / 'objects').rglob('*.xml'))), 1)
        self.assertEqual(s.verify(self.store, a['run_id'])['content_id'], a['content_id'])

    def test_changed_content_keeps_old_bytes(self):
        a = self.capture()
        (self.raw / 'wfp' / 'activities.xml').write_bytes(XML.replace(b'EXAMPLE-1', b'EXAMPLE-2'))
        b = self.capture()
        self.assertNotEqual(a['content_id'], b['content_id'])
        self.assertEqual(s.object_path(self.store, a['files'][0]['sha256']).read_bytes(), XML)
        self.assertEqual(len(list((self.store / 'objects').rglob('*.xml'))), 2)

    def test_malformed_xml_preserves_latest_and_logs_failure(self):
        self.capture(); before = self.latest()
        (self.raw / 'oxfamus' / 'activities.xml').write_text('<broken')
        with self.assertRaises(s.ET.ParseError): self.capture()
        self.assertEqual(self.latest(), before)
        runs = [json.loads(p.read_text()) for p in (self.store / 'runs').glob('*.json')]
        self.assertEqual(sum(r['status'] == 'failed' for r in runs), 1)
        self.assertFalse(list(self.store.glob('.staging-*')))
        self.assertFalse((self.store / '.capture-lock').exists())

    def test_missing_publisher_preserves_latest(self):
        self.capture(); before = self.latest()
        (self.raw / 'wfp' / 'activities.xml').unlink()
        with self.assertRaisesRegex(ValueError, 'No local XML'): self.capture()
        self.assertEqual(self.latest(), before)

    def test_first_failure_does_not_create_latest(self):
        (self.raw / 'wfp' / 'activities.xml').write_bytes(b'')
        with self.assertRaises(s.ET.ParseError): self.capture()
        self.assertFalse((self.store / 'latest.json').exists())

    def test_non_iati_xml_rejected(self):
        (self.raw / 'wfp' / 'activities.xml').write_bytes(b'<html/>')
        with self.assertRaisesRegex(ValueError, 'IATI 2'): self.capture()

    def test_dtd_and_utf16_dtd_rejected(self):
        payload = '<!DOCTYPE iati-activities [<!ENTITY foo "bar">]><iati-activities version="2.03"/>'
        for encoding in ('utf-8', 'utf-16'):
            (self.raw / 'wfp' / 'activities.xml').write_bytes(payload.encode(encoding))
            with self.assertRaisesRegex(ValueError, 'DTD'): self.capture()

    def test_size_limit_preserves_latest(self):
        self.capture(); before = self.latest()
        with self.assertRaisesRegex(ValueError, 'limit'): self.capture(max_bytes=5)
        self.assertEqual(before, self.latest())

    def test_concurrent_capture_refused(self):
        with s.locked(self.store):
            with self.assertRaisesRegex(RuntimeError, 'busy'): self.capture()
        self.capture()

    def test_corrupt_object_detected_without_publishing(self):
        a = self.capture(); before = self.latest()
        s.object_path(self.store, a['files'][0]['sha256']).write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError, 'Checksum'): s.verify(self.store)
        with self.assertRaisesRegex(ValueError, 'corrupt'): self.capture()
        self.assertEqual(before, self.latest())

    def test_export_is_independent_and_refuses_overwrite(self):
        a = self.capture()
        dest = self.base / 'export'
        s.export_snapshot(self.store, dest)
        self.assertEqual((dest / 'wfp' / 'activities.xml').read_bytes(), XML)
        with self.assertRaises(FileExistsError): s.export_snapshot(self.store, dest)
        (dest / 'wfp' / 'activities.xml').write_bytes(b'changed')
        s.verify(self.store, a['run_id'])

    def test_corrupt_export_never_exposes_destination(self):
        self.capture(); dest = self.base / 'export'
        with patch.object(s.shutil, 'copyfile', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): s.export_snapshot(self.store, dest)
        self.assertFalse(dest.exists())
        self.assertFalse(list(self.base.glob('.export-*')))

    def index(self, datasets):
        path = self.base / 'index.json'
        path.write_text(json.dumps({'datasets': datasets}))
        return path

    def dataset(self, **kw):
        return dict(reporting_org_short_name='wfp', short_name='wfp-activities', source_url='https://example.org/data.xml', **kw)

    def test_network_success_uses_existing_selection(self):
        idx = self.index([self.dataset()])
        seen = []
        def opener(request, timeout):
            seen.append(request.full_url)
            return io.BytesIO(XML)
        a = s.capture(self.store, ['wfp'], index_file=idx, opener=opener)
        self.assertEqual(seen, ['https://example.org/data.xml'])
        self.assertEqual(a['scope']['mode'], 'bulk-download')

    def test_network_failure_keeps_previous_success(self):
        self.capture(); before = self.latest()
        idx = self.index([self.dataset()])
        def fail(*a, **k): raise TimeoutError('download timed out')
        with self.assertRaises(TimeoutError): s.capture(self.store, ['wfp'], index_file=idx, opener=fail)
        self.assertEqual(before, self.latest())

    def test_pointer_publication_failure_keeps_old_version(self):
        self.capture(); before = self.latest()
        original = s.atomic_json
        def fail_pointer(path, value):
            if path.name == 'latest.json':
                raise OSError('cannot publish pointer')
            return original(path, value)
        with patch.object(s, 'atomic_json', side_effect=fail_pointer):
            with self.assertRaises(OSError): self.capture()
        self.assertEqual(before, self.latest())
        s.verify(self.store)

    def test_mid_batch_timeout_does_not_publish_partial_run(self):
        self.capture(); before = self.latest()
        second = self.dataset(); second['short_name'] = 'wfp-other-activities'
        idx = self.index([self.dataset(), second])
        calls = 0
        def opener(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2: raise TimeoutError('second file failed')
            return io.BytesIO(XML.replace(b'EXAMPLE-1', b'NEW'))
        with self.assertRaises(TimeoutError):
            s.capture(self.store, ['wfp'], index_file=idx, opener=opener)
        self.assertEqual(before, self.latest())
        s.verify(self.store)

    def test_duplicate_index_entries_rejected(self):
        idx = self.index([self.dataset(), self.dataset()])
        with self.assertRaisesRegex(ValueError, 'Duplicate'): s.capture(self.store, ['wfp'], index_file=idx)

    def test_missing_url_and_unsafe_filename_rejected(self):
        for field, value in [('source_url', ''), ('short_name', '../escape')]:
            dataset = self.dataset(); dataset[field] = value
            idx = self.index([dataset])
            with self.assertRaises(ValueError): s.capture(self.store, ['wfp'], index_file=idx)

    def test_manifest_tampering_rejected(self):
        r = self.capture()
        path = self.store / 'runs' / (r['run_id'] + '.json')
        r['files'][0]['dataset'] = 'another-name'
        path.write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError, 'identity'): s.verify(self.store)

    def test_failed_run_cannot_be_exported(self):
        (self.raw / 'wfp' / 'activities.xml').write_bytes(b'')
        with self.assertRaises(s.ET.ParseError): self.capture()
        run = next((self.store / 'runs').glob('*.json')).stem
        with self.assertRaisesRegex(ValueError, 'complete'): s.export_snapshot(self.store, self.base / 'out', run)

    def test_export_old_version(self):
        a = self.capture()
        (self.raw / 'wfp' / 'activities.xml').write_bytes(XML.replace(b'EXAMPLE-1', b'EXAMPLE-2'))
        self.capture()
        dest = self.base / 'old'
        s.export_snapshot(self.store, dest, a['run_id'])
        self.assertEqual((dest / 'wfp' / 'activities.xml').read_bytes(), XML)


class ParserIntegration(unittest.TestCase):
    def test_exported_snapshot_feeds_existing_filter(self):
        import csv
        import parse_filter
        import review
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            raw = base / 'raw'
            (raw / 'oxfamgb').mkdir(parents=True)
            fixture = Path(__file__).parent / 'fixture_iati_2.03.xml'
            (raw / 'oxfamgb' / 'fixture.xml').write_bytes(fixture.read_bytes())
            store = base / 'store'
            s.capture(store, ['oxfamgb'], local_dir=raw)
            exported = base / 'export'
            s.export_snapshot(store, exported)
            with patch.object(parse_filter, 'RAW_DIR', exported), \
                 patch.object(parse_filter, 'GRAPH_DIR', base / 'graph'), \
                 patch.object(review, 'QUEUE', base / 'review' / 'queue.csv'), \
                 patch.object(review, 'DECISIONS', base / 'review' / 'decisions.csv'):
                parse_filter.run('oxfamgb')
            with (base / 'graph' / 'nodes_activities.csv').open() as f:
                ids = {r['iati_identifier'] for r in csv.DictReader(f)}
            self.assertEqual(ids, {'GB-CHC-202918-TEST001', 'US-EIN-237069110-TEST004',
                                   'XM-DAC-41140-TEST005', 'GB-CHC-202918-TEST006'})

    def test_raw_directory_override_is_honoured(self):
        import os
        import subprocess
        env = dict(os.environ, IATI_RAW_DIR='/tmp/iati-test-input', PYTHONPATH=str(Path(s.__file__).parent))
        value = subprocess.check_output([s.os.sys.executable, '-c', 'from config import RAW_DIR; print(RAW_DIR)'], env=env, text=True)
        self.assertEqual(value.strip(), '/tmp/iati-test-input')


if __name__ == '__main__': unittest.main()
