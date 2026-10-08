import mimetypes
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.workbench import create_app


class StaticAssetTests(unittest.TestCase):
    def test_frontend_types_override_incorrect_os_mime_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / 'dist' / 'assets'
            assets.mkdir(parents=True)
            files = {
                'index.js': ('export const ready = true;', 'text/javascript'),
                'module.mjs': ('export const ready = true;', 'text/javascript'),
                'style.css': ('body { color: black; }', 'text/css'),
                'note.txt': ('Plain text', 'text/plain'),
            }
            for name, (content, _) in files.items():
                (assets / name).write_text(content, encoding='utf-8')
            app = create_app(root / 'data', root / 'dist')
            # Reproduce an incorrect Windows registry / OS MIME association.
            mimetypes.init()
            with patch.dict(mimetypes.types_map, {'.js': 'text/plain', '.mjs': 'text/plain', '.css': 'text/plain'}):
                with TestClient(app) as client:
                    for name, (content, expected_type) in files.items():
                        with self.subTest(asset=name):
                            response = client.get('/assets/' + name)
                            self.assertEqual(response.status_code, 200)
                            self.assertEqual(response.text, content)
                            self.assertEqual(response.headers['content-type'].split(';')[0], expected_type)
                            self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
                            head = client.head('/assets/' + name)
                            self.assertEqual(head.status_code, 200)
                            self.assertEqual(head.headers['content-type'].split(';')[0], expected_type)
                            self.assertEqual(head.content, b'')
                    missing = client.get('/assets/missing.js')
                    self.assertEqual(missing.status_code, 404)
                    self.assertEqual(missing.headers['content-type'].split(';')[0], 'application/json')


if __name__ == '__main__':
    unittest.main()
