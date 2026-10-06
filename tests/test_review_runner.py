from copy import deepcopy
import json
import time
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from app.llm_client import LLMClient, LLMError
from app.models import ArchitectureModel
from app.requirement_catalog import RequirementEntry
from app.review_runner import inspect_result, plan_review, run_review, task, source_parts, review_summary
import test_workspace_v2 as workspace_fixture
from test_workspace_v2 import example


def finding(title='Desteklenen gözlem', **fields):
    return dict(id='f', severity='low', type='ambiguous', title=title, description='Arayüz ayrıntısı açıklığa kavuşturulmalı.', evidence=[], related_component_ids=['A'], **fields)


class ReviewRunnerTests(unittest.TestCase):
    def setUp(self):
        self.arch = ArchitectureModel.model_validate(example()['architecture'])
        self.entries = [RequirementEntry('G-01', 'A birimi B birimine veri aktarır.')]

    def test_bad_quote_unknown_object_and_schema_do_not_discard_valid_sibling(self):
        good = finding()
        quote = finding('Yanlış alıntı'); quote['evidence'] = [dict(requirement_id='G-01', quote='belgede olmayan ifade')]
        obj = finding('Yanlış öğe'); obj['related_component_ids'] = ['ghost']
        result = dict(findings=[good, quote, obj, dict(title='Bozuk biçim')])
        accepted, excluded = inspect_result(result, self.entries, self.arch, lambda _: None)
        self.assertEqual([f['title'] for f in accepted['findings']], [good['title']])
        self.assertEqual([f['code'] for f in excluded], ['QUOTE_MISMATCH', 'OBJECT_UNKNOWN', 'FINDING_SCHEMA'])
        self.assertEqual(excluded[0]['finding'], quote)

    def test_summary_separates_rejected_output_from_incomplete_review(self):
        report = dict(analysis=dict(findings=[]), excluded=[{}, {}, {}],
                      sections=[dict(status='partial')], retry_tasks=[dict(feedback='QUOTE_MISMATCH')])
        self.assertEqual(review_summary(report),
                         'Planlanan bölümler incelendi. 0 bulgu kabul edildi; 3 bulgu veya öneri kabul edilmedi.')
        for changes in (
            dict(sections=[dict(status='failed')]),
            dict(retry_tasks=[dict(label='Henüz incelenmeyen bölüm')]),
            dict(sections=[dict(status='split', cross_review_incomplete=True)]),
            dict(remaining_tasks=[dict(label='Bekleyen bölüm')]),
        ):
            with self.subTest(changes=changes):
                self.assertTrue(review_summary({**report, **changes}).startswith('Bazı bölümlerin incelemesi tamamlanamadı.'))

    def test_invalid_executable_proposal_is_removed_but_observation_survives(self):
        result = finding(proposed_changes=[dict(action='update', kind='component', id='ghost', value={})])
        def check(_): raise ValueError('Öğe bulunamadı.')
        accepted, excluded = inspect_result(dict(findings=[result]), self.entries, self.arch, check)
        self.assertEqual(accepted['findings'][0]['proposed_changes'], [])
        self.assertEqual(excluded[0]['code'], 'PROPOSAL_INVALID')
        self.assertEqual(excluded[0]['detail'], 'Öğe bulunamadı.')

    def test_long_document_all_source_text_is_reviewed_and_global_phase_exists(self):
        entries = [RequirementEntry(f'R-{i}', 'a' * 1700) for i in range(14)]
        plan = plan_review(entries, self.arch)
        self.assertGreater(len(plan), 2)
        covered = [e['requirement_id'] for t in plan if t['scope']=='detail' for e in t['entries']]
        self.assertEqual(covered, [e.requirement_id for e in entries])
        self.assertEqual(plan[-1]['scope'], 'cross')
        self.assertEqual(len(plan[-1]['entries']), len(entries))

    def test_single_source_group_does_not_repeat_same_input_in_cross_review(self):
        from app.prompts import analysis_user_prompt
        arch=self.arch.model_copy(deep=True)
        arch.components[0].description='Context ' * 2400
        self.assertGreater(len(analysis_user_prompt(self.entries,arch,compact=True)),16000)
        plan=plan_review(self.entries,arch)
        self.assertEqual(len(plan),1)
        self.assertEqual(plan[0]['scope'],'full')
        self.assertEqual(plan[0]['entries'],[vars(e) for e in self.entries])

    def test_deadline_cancel_and_worker_failure_keep_completed_results_and_stop_calls(self):
        for code in ('TIME_BUDGET','CANCELLED','TLS_RUNTIME','WORKER_EXIT'):
            with self.subTest(code=code):
                client=Mock(calls=[])
                client.extract_json.side_effect=[dict(findings=[finding()]),LLMError(code,'stopped')]
                report=run_review(client,self.entries,self.arch,lambda _:None,lambda *args:None,tasks=[task(str(i),self.entries) for i in range(3)])
                self.assertEqual(client.extract_json.call_count,2)
                self.assertEqual(len(report['analysis']['findings']),1)
                self.assertEqual([t['label'] for t in report['retry_tasks']],['1','2'])
                self.assertIsNone(report['active_section'])

    def test_long_single_source_overlaps_and_preserves_original_id(self):
        entry = RequirementEntry('LONG', ''.join(str(i % 10) for i in range(20000)))
        groups = source_parts([entry])
        texts = [e.text for g in groups for e in g]
        self.assertEqual(texts[0][-400:], texts[1][:400])
        self.assertTrue(all(e.requirement_id=='LONG' for g in groups for e in g))
        self.assertEqual(texts[-1][-400:], entry.text[-400:])

    def test_truncation_splits_preserves_success_and_marks_cross_review_incomplete(self):
        entries = [RequirementEntry('R-1', 'a' * 2000), RequirementEntry('R-2', 'b' * 2000)]
        client = Mock(calls=[])
        client.extract_json.side_effect = [LLMError('TRUNCATED', 'length'), dict(findings=[finding()]), dict(findings=[finding()])]
        report = run_review(client, entries, self.arch, lambda _:None, lambda *args:None)
        self.assertEqual(client.extract_json.call_count, 3)
        self.assertEqual(len(report['analysis']['findings']), 1)
        self.assertEqual(report['sections'][0]['status'], 'split')
        self.assertTrue(report['sections'][0]['cross_review_incomplete'])
        self.assertEqual(len(report['retry_tasks']), 1)

    def test_quota_stops_remaining_calls_and_retry_keeps_completed_section(self):
        tasks = [task('Bir', self.entries), task('İki', self.entries), task('Üç', self.entries)]
        client = Mock(calls=[])
        client.extract_json.side_effect = [dict(findings=[finding()]), LLMError('RATE_LIMIT', 'quota')]
        report = run_review(client, self.entries, self.arch, lambda _:None, lambda *args:None, tasks=tasks)
        self.assertEqual(client.extract_json.call_count, 2)
        self.assertEqual([t['label'] for t in report['retry_tasks']], ['İki', 'Üç'])
        again = Mock(calls=[])
        again.extract_json.return_value = dict(findings=[])
        recovered = run_review(again, self.entries, self.arch, lambda _:None, lambda *args:None, tasks=report['retry_tasks'], seed=report['analysis'])
        self.assertEqual(again.extract_json.call_count, 2)
        self.assertEqual(len(recovered['analysis']['findings']), 1)
        self.assertFalse(recovered['retry_tasks'])

    def test_bounded_calls_leave_unreviewed_tasks_recoverable(self):
        client = Mock(calls=[]); client.extract_json.return_value = dict(findings=[])
        with patch('app.review_runner.MAX_CALLS', 2):
            report = run_review(client, self.entries, self.arch, lambda _:None, lambda *args:None, tasks=[task(str(i), self.entries) for i in range(4)])
        self.assertEqual(client.extract_json.call_count, 2)
        self.assertEqual(len(report['retry_tasks']), 2)

    def test_transport_diagnostics_preserve_usage_without_request_or_thinking(self):
        client = LLMClient('https://example.test', api_key='TEST_SECRET', model='test')
        response = Mock(status_code=200, ok=True)
        response.json.return_value = dict(choices=[dict(finish_reason='stop', message=dict(content=json.dumps(dict(findings=[])), reasoning='HIDDEN_THINKING'))], usage=dict(prompt_tokens=10, completion_tokens=20, completion_tokens_details=dict(reasoning_tokens=12)))
        with patch.object(client.session, 'post', return_value=response):
            report = run_review(client, self.entries, self.arch, lambda _:None, lambda *args:None)
        serialized = json.dumps(report)
        self.assertNotIn('TEST_SECRET', serialized)
        self.assertNotIn('HIDDEN_THINKING', serialized)
        self.assertNotIn('request', report['sections'][0]['transport'][0])
        self.assertEqual(report['sections'][0]['transport'][0]['usage']['completion_tokens'], 20)

    def test_provider_error_explanation_is_retained_without_credentials(self):
        client = LLMClient('https://example.test', api_key='TEST_SECRET', model='test', max_retries=0)
        response = Mock(status_code=400, ok=False)
        response.json.return_value = dict(error=dict(message='max_tokens exceeds limit. Bearer TEST_SECRET'))
        with patch.object(client.session, 'post', return_value=response):
            with self.assertRaises(LLMError): client.extract_json('system', 'user')
        self.assertIn('max_tokens exceeds limit', client.calls[0]['provider_message'])
        self.assertNotIn('TEST_SECRET', json.dumps(client.calls))


class RecoverableReviewApiTests(unittest.TestCase):
    setUp = workspace_fixture.WorkspaceApiTests.setUp
    tearDown = workspace_fixture.WorkspaceApiTests.tearDown
    def wait_job(self, jid):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            job = self.client.get('/api/jobs/' + jid).json()
            if job['status'] not in ('queued','running'):
                return job
            time.sleep(.02)
        self.fail('Job did not finish')

    def review(self, **fields):
        r = self.client.post(f"/api/projects/{self.p['id']}/review", json=dict(profile='openrouter_nemotron', **fields), headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        return self.wait_job(r.json()['id'])

    def test_partial_result_and_diagnostics_survive_restart_and_retry_only_missing(self):
        good = finding(); bad = finding('Yanlış kaynak'); bad['evidence'] = [dict(requirement_id='ghost', quote='x')]
        with patch('app.workbench.LLMClient') as client:
            client.return_value.calls = []
            client.return_value.extract_json.return_value = dict(findings=[good, bad])
            job = self.review(max_tokens=32768)
        self.assertEqual(job['status'], 'partial', job)
        self.assertTrue(job['can_retry_missing'])
        self.assertEqual(job['added_findings'], 1)
        self.assertIn('Planlanan bölümler incelendi.', job['message'])
        self.assertIn('1 bulgu kabul edildi; 1 bulgu veya öneri kabul edilmedi.', job['message'])
        self.assertNotIn('review_report', job)
        detail = self.client.get('/api/jobs/' + job['id'] + '/diagnostics').json()
        self.assertEqual(detail['review_report']['excluded'][0]['code'], 'SOURCE_UNKNOWN')
        self.assertEqual(self.client.get('/api/jobs/' + job['id'] + '/diagnostics?download=true').status_code, 200)
        self.client.__exit__(None, None, None)
        from app.workbench import create_app
        from fastapi.testclient import TestClient
        self.app = create_app(self.root / 'data')
        self.client = TestClient(self.app); self.client.__enter__()
        self.headers = {'X-Workbench-Token':self.client.get('/api/bootstrap').json()['token']}
        self.assertEqual(self.client.get('/api/jobs/' + job['id']).json()['status'], 'partial')
        with patch('app.workbench.LLMClient') as client:
            client.return_value.calls = []
            client.return_value.extract_json.return_value = dict(findings=[good, finding('Yeni desteklenen bulgu')])
            retried = self.review(retry_job_id=job['id'])
            self.assertIn('PREVIOUS OUTPUT REJECTED', client.return_value.extract_json.call_args.args[1])
        self.assertEqual(retried['status'], 'completed', retried)
        self.assertEqual(retried['added_findings'], 1)
        p = self.client.get('/api/projects/' + self.p['id']).json()
        self.assertEqual(len(p['topics']), 3)
        self.assertEqual(p['state']['architecture'], self.p['state']['architecture'])

    def test_all_quote_mismatches_report_zero_accepted_without_claiming_partial_design(self):
        rejected = [finding(f'Öneri {i}') for i in range(3)]
        for f in rejected:
            f['evidence'] = [dict(requirement_id=self.p['original']['source_catalog'][0]['requirement_id'], quote='Kaynakta bulunmayan alıntı')]
        with patch('app.workbench.LLMClient') as client:
            client.return_value.calls = []
            client.return_value.extract_json.return_value = dict(findings=rejected)
            job = self.review()
        self.assertEqual(job['status'], 'partial')
        self.assertEqual(job['message'], '0 yeni bulgu eklendi. Planlanan bölümler incelendi. 0 bulgu kabul edildi; 3 bulgu veya öneri kabul edilmedi.')
        detail = self.client.get('/api/jobs/' + job['id'] + '/diagnostics').json()
        self.assertEqual([e['code'] for e in detail['review_report']['excluded']], ['QUOTE_MISMATCH'] * 3)
        current = self.client.get('/api/projects/' + self.p['id']).json()
        self.assertEqual(current['state']['architecture'], self.p['state']['architecture'])

    def test_invalid_proposal_does_not_edit_design_and_is_not_executable(self):
        bad = finding(proposed_changes=[dict(action='add',kind='connection',id='bad_edge',value=dict(source='A',target='ghost'))])
        with patch('app.workbench.LLMClient') as client:
            client.return_value.calls=[]; client.return_value.extract_json.return_value=dict(findings=[bad])
            job=self.review()
        self.assertEqual(job['status'],'partial',job)
        p=self.client.get('/api/projects/'+self.p['id']).json()
        self.assertEqual(p['state']['architecture'],self.p['state']['architecture'])
        self.assertEqual(p['state']['analysis']['findings'][-1]['proposed_changes'],[])

    def test_retry_refuses_changed_architecture_and_uses_no_model_call(self):
        with patch('app.workbench.LLMClient') as client:
            client.return_value.calls=[];client.return_value.extract_json.side_effect=LLMError('RATE_LIMIT','quota')
            job=self.review()
        comp=deepcopy(self.p['state']['architecture']['components'][0]);comp['name']='Değişmiş'
        self.client.post(f"/api/projects/{self.p['id']}/changes",json=dict(version=0,action='upsert_component',id=comp['id'],value=comp,actor='Mühendis'),headers=self.headers)
        with patch('app.workbench.LLMClient') as client:
            response=self.client.post(f"/api/projects/{self.p['id']}/review",json=dict(retry_job_id=job['id']),headers=self.headers)
            self.assertEqual(response.status_code,409,response.text)
            client.assert_not_called()

    def test_interrupted_review_can_finalize_saved_results_without_another_model_call(self):
        from app.review_topics import fingerprint
        from app.review_store import now
        from app.workbench import create_app
        from fastapi.testclient import TestClient
        raw = dict(findings=[finding()])
        accepted, _ = inspect_result(raw, [], ArchitectureModel.model_validate(self.p['state']['architecture']), lambda _:None)
        job = dict(id='interrupted-test', created=now(), status='running', project_id=self.p['id'], mode='review', architecture_fingerprint=fingerprint(self.p['state']['architecture']), message='Working', review_report=dict(analysis=accepted, sections=[dict(label='Bütün tasarım',status='completed')], excluded=[], retry_tasks=[], remaining_tasks=[], calls=1))
        self.app.state.store.save_job(job)
        self.client.__exit__(None,None,None)
        self.app=create_app(self.root/'data');self.client=TestClient(self.app);self.client.__enter__()
        self.headers={'X-Workbench-Token':self.client.get('/api/bootstrap').json()['token']}
        self.assertEqual(self.client.get('/api/jobs/'+job['id']).json()['status'], 'interrupted')
        with patch('app.workbench.LLMClient') as client:
            client.return_value.calls=[]
            recovered=self.review(retry_job_id=job['id'])
            client.return_value.extract_json.assert_not_called()
        self.assertEqual(recovered['status'],'completed',recovered)
        self.assertEqual(recovered['added_findings'],1)


class PipelineRecoveryTests(unittest.TestCase):
    def test_first_document_analysis_keeps_valid_sibling_and_writes_diagnostics(self):
        from app.pipeline import run
        class Client:
            def __init__(self): self.calls=[];self.index=0
            def settings(self): return {'mode':'fixture', 'model':'OFFLINE_TEST'}
            def extract_json(self, system, user):
                result = example()['architecture'] if self.index==0 else dict(findings=[finding(), {**finding('Yanlış kimlik'), 'related_component_ids':['ghost']}])
                self.index+=1
                self.calls.append({'parsed':result,'seconds':0})
                return result
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'input.txt';source.write_text('G-01 '+example()['source_catalog'][0]['text'],encoding='utf-8')
            out=Path(directory)/'out'
            final=run(str(source),str(out),Client())
            self.assertEqual(final.review_status,'partial')
            self.assertEqual(len(final.analysis.findings),1)
            self.assertTrue((out/'architecture_pass1.json').exists())
            report=json.loads((out/'review_diagnostics.json').read_text(encoding='utf-8'))
            self.assertEqual(report['excluded'][0]['code'],'OBJECT_UNKNOWN')


if __name__=='__main__': unittest.main()
