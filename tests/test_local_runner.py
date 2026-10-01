import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.local_runner import ROOT,run_from_path
from app.llm_client import FixtureClient

class LocalRunnerTests(unittest.TestCase):
    def test_paths_independent_of_terminal_directory(self):
        original=Path.cwd()
        with tempfile.TemporaryDirectory() as d:
            try:
                os.chdir(d)
                final,out=run_from_path('evaluation/cases/dev_01.txt',Path(d)/'results',client=FixtureClient(ROOT/'evaluation/cases/dev_01.fixture.json'))
                self.assertTrue((out/'report.html').is_file())
                self.assertEqual(final.review_status,'completed')
                _,second=run_from_path('evaluation/cases/dev_01.txt',Path(d)/'results',client=FixtureClient(ROOT/'evaluation/cases/dev_01.fixture.json'))
                self.assertNotEqual(out,second)
            finally:os.chdir(original)
    def test_invalid_path_fails_before_client_creation(self):
        with patch('app.local_runner.from_environment') as factory:
            with self.assertRaises(ValueError):run_from_path('')
            with self.assertRaises(FileNotFoundError):run_from_path('not_a_real_document.docx')
            factory.assert_not_called()

if __name__=='__main__':unittest.main()
