import io
from pathlib import Path
import unittest
from unittest.mock import patch

import run_workbench


class LauncherTests(unittest.TestCase):
    def test_bad_tls_runtime_is_rejected_before_server_start(self):
        with patch.object(run_workbench.Path,'is_file',return_value=False), patch.object(run_workbench.subprocess,'run') as probe:
            probe.return_value.returncode=1
            with self.assertRaises(SystemExit) as caught: run_workbench.ensure_runtime()
        self.assertIn('güvenli bağlantı kontrolü başarısız',str(caught.exception))

    def test_healthy_runtime_passes_child_preflight(self):
        with patch.object(run_workbench.Path,'is_file',return_value=False), patch.object(run_workbench.subprocess,'run') as probe:
            probe.return_value.returncode=0;probe.return_value.stdout='TLS_READY'
            run_workbench.ensure_runtime()
        self.assertEqual(probe.call_count,1)

    def test_second_launch_opens_existing_app_without_starting_another_server(self):
        with patch('sys.argv',['run_workbench.py']), patch.object(run_workbench,'port_in_use',return_value=True), patch.object(run_workbench,'existing_workbench',return_value=True), patch.object(run_workbench.webbrowser,'open') as browser, patch('uvicorn.run') as server, patch('sys.stdout',new_callable=io.StringIO) as output:
            run_workbench.main()
        browser.assert_called_once_with('http://127.0.0.1:8766')
        server.assert_not_called()
        self.assertIn('zaten çalışıyor',output.getvalue())

    def test_other_service_is_not_opened_or_stopped(self):
        with patch('sys.argv',['run_workbench.py','--no-browser']), patch.object(run_workbench,'port_in_use',return_value=True), patch.object(run_workbench,'existing_workbench',return_value=False), patch.object(run_workbench.webbrowser,'open') as browser, patch('uvicorn.run') as server:
            with self.assertRaises(SystemExit) as error: run_workbench.main()
        self.assertIn('--port 8767',str(error.exception))
        browser.assert_not_called();server.assert_not_called()

    def test_identity_requires_matching_workspace_and_data_folder(self):
        import json
        root=Path(run_workbench.__file__).parent.resolve()
        info=dict(app='system-architecture-analyzer-workbench',root=str(root),data_dir=str(root/'other_data'))
        with patch.object(run_workbench,'instance_json',return_value=(200,info)):
            self.assertFalse(run_workbench.existing_workbench('http://127.0.0.1:8766',root/'workbench_data'))

    def test_legacy_server_requires_verified_default_data_process(self):
        import json
        from types import SimpleNamespace
        root=Path(run_workbench.__file__).parent.resolve()
        info=dict(root=str(root),projects=[],profiles=[],jobs=[],version='2.0')
        process=f'"{root}/venv/Scripts/python.exe" run_workbench.py --port 8766 --no-browser'
        with patch.object(run_workbench.sys,'platform','win32'), patch.object(run_workbench,'instance_json',return_value=(200,info)), patch.object(run_workbench.subprocess,'run') as probe:
            probe.return_value=SimpleNamespace(returncode=0,stdout=json.dumps(process))
            self.assertTrue(run_workbench.legacy_workbench('http://127.0.0.1:8766',root/'workbench_data'))
            probe.return_value=SimpleNamespace(returncode=0,stdout=json.dumps(process+' --data-dir other_data'))
            self.assertFalse(run_workbench.legacy_workbench('http://127.0.0.1:8766',root/'workbench_data'))


if __name__=='__main__':unittest.main()
