import json
import subprocess
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from app.llm_client import LLMClient, LLMError
import test_workspace_v2 as workspace_fixture


class ModelIsolationTests(unittest.TestCase):
    def setUp(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(handler):
                handler.rfile.read(int(handler.headers['Content-Length']))
                self.request_started.set()
                time.sleep(self.delay)
                data=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'{"findings":[]}'}}],'usage':{'completion_tokens':5}}).encode()
                try:
                    handler.send_response(200);handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data)
                except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): pass
            def log_message(self,*args): pass
        self.delay=0
        self.request_started=threading.Event()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self): self.server.shutdown();self.server.server_close();self.thread.join()

    def test_model_request_returns_result_and_usage_through_isolated_worker(self):
        client=LLMClient(self.url,api_key='TEST_SECRET',model='fixture',isolate=True,timeout=5)
        self.assertEqual(client.extract_json('system','user'),{'findings':[]})
        self.assertEqual(client.calls[0]['usage']['completion_tokens'],5)
        self.assertNotIn('TEST_SECRET',json.dumps(client.calls))

    def test_native_worker_abort_becomes_error_instead_of_killing_parent(self):
        original=subprocess.Popen
        def crashed_worker(args,**kwargs):
            return original([getattr(sys,'_base_executable',sys.executable),'-c',"import sys,os; sys.stderr.write('OPENSSL_Uplink: no OPENSSL_Applink'); sys.stderr.flush(); os._exit(1)"],**kwargs)
        client=LLMClient(self.url,isolate=True,timeout=5)
        with patch('app.llm_client.subprocess.Popen',side_effect=crashed_worker):
            with self.assertRaises(LLMError) as caught: client.extract_json('s','u')
        self.assertEqual(caught.exception.code,'TLS_RUNTIME')
        self.assertEqual(client.calls[-1]['error_code'],'TLS_RUNTIME')

    def test_cancel_terminates_inflight_request_promptly(self):
        self.delay=3; cancel=threading.Event();timer=threading.Timer(.6,cancel.set);timer.start()
        client=LLMClient(self.url,isolate=True,timeout=10,cancel_event=cancel)
        start=time.monotonic()
        with self.assertRaises(LLMError) as caught: client.extract_json('s','u')
        timer.join();self.assertEqual(caught.exception.code,'CANCELLED');self.assertLess(time.monotonic()-start,2)

    def test_total_deadline_stops_request_even_if_call_timeout_is_large(self):
        self.delay=3
        client=LLMClient(self.url,isolate=True,timeout=1000,deadline=time.monotonic()+.6)
        start=time.monotonic()
        with self.assertRaises(LLMError) as caught: client.extract_json('s','u')
        self.assertEqual(caught.exception.code,'TIME_BUDGET');self.assertLess(time.monotonic()-start,2)


class ModelIsolationApiTests(unittest.TestCase):
    def setUp(self):
        ModelIsolationTests.setUp(self)
        workspace_fixture.WorkspaceApiTests.setUp(self)

    def tearDown(self):
        workspace_fixture.WorkspaceApiTests.tearDown(self)
        ModelIsolationTests.tearDown(self)

    def start_review(self):
        response=self.client.post(f"/api/projects/{self.p['id']}/review",json=dict(base_url=self.url,model='fixture',api_key='TEST_SECRET',timeout=10),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['id']

    def wait_job(self,jid):
        end=time.monotonic()+5
        while time.monotonic()<end:
            job=self.client.get('/api/jobs/'+jid).json()
            if job['status'] not in ('running','queued'): return job
            time.sleep(.02)
        self.fail('Job did not finish')

    def test_api_survives_native_abort_and_preserves_design_and_retry(self):
        original=subprocess.Popen
        def crash(args,**kwargs):
            return original([getattr(sys,'_base_executable',sys.executable),'-c',"import sys,os; sys.stderr.write('OPENSSL_Uplink: no OPENSSL_Applink'); sys.stderr.flush(); os._exit(1)"],**kwargs)
        with patch('app.llm_client.subprocess.Popen',side_effect=crash):
            job=self.wait_job(self.start_review())
        self.assertEqual(job['status'],'failed',job)
        self.assertEqual(job['error_code'],'TLS_RUNTIME')
        self.assertTrue(job['can_retry_missing'])
        self.assertEqual(self.client.get('/api/instance').status_code,200)
        self.assertEqual(self.client.get('/api/projects/'+self.p['id']).json()['state'],self.p['state'])
        self.assertNotIn('TEST_SECRET',self.client.get('/api/jobs/'+job['id']+'/diagnostics').text)

    def test_authenticated_cancel_stops_request_and_next_review_can_complete(self):
        self.delay=3
        jid=self.start_review()
        self.assertTrue(self.request_started.wait(5))
        self.assertEqual(self.client.post('/api/jobs/'+jid+'/cancel',json={}).status_code,403)
        started=time.monotonic()
        cancelled=self.client.post('/api/jobs/'+jid+'/cancel',json={},headers=self.headers)
        self.assertTrue(cancelled.json()['cancel_requested'])
        job=self.wait_job(jid)
        self.assertLess(time.monotonic()-started,2)
        self.assertEqual(job['status'],'cancelled',job)
        self.assertTrue(job['can_retry_missing'])
        self.assertEqual(self.client.get('/api/projects/'+self.p['id']).json()['state'],self.p['state'])
        self.delay=0
        next_job=self.wait_job(self.start_review())
        self.assertEqual(next_job['status'],'completed',next_job)
        self.assertEqual(next_job['completed_sections'],1)
