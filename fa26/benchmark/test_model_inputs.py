import hashlib
from pathlib import Path
import tempfile
import unittest

from common import ROOT, verify_snapshot
from prepare_model_inputs import prepare


class ModelInputTests(unittest.TestCase):
    def test_export_has_only_public_inputs_and_identical_data(self):
        with tempfile.TemporaryDirectory() as temp:
            output = prepare(Path(temp) / 'inputs')
            expected = {'manifest.json', 'questions.json', 'submission_template.json', 'INSTRUCTIONS.txt'}
            expected |= {'snapshot/' + name for name in verify_snapshot()['files']}
            self.assertEqual({p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}, expected)
            for name, spec in verify_snapshot()['files'].items():
                self.assertEqual(hashlib.sha256((output/'snapshot'/name).read_bytes()).hexdigest(), spec['sha256'])
            with self.assertRaises(FileExistsError):
                prepare(output)

    def test_reject_evaluator_directory(self):
        with self.assertRaises(ValueError):
            prepare(ROOT/'model-inputs')


if __name__ == '__main__':
    unittest.main(verbosity=2)
