"""End-to-end contracts for TİD revisions, human decisions and assistant proposals."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from docx import Document
from fastapi.testclient import TestClient

from app.engineering_workspace import workspace_fingerprint
from app.review_store import ReviewStore, ConflictError
from app.validator_audit import baseline
from app.workbench import create_app
from app.workspace_assistant import validate_answer, assistant_prompt
from app.llm_client import LLMError


class EngineeringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        data = baseline(); data['architecture']['assumptions'] = ['İletişimin çift yönlü olduğu varsayılmıştır.']
        data['architecture']['components'].append(dict(id='C',name='Bağımsız',evidence=[]))
        self.path = self.root/'analysis_result.json'; self.path.write_text(json.dumps(data), encoding='utf-8')
        self.app = create_app(self.root/'data')
        self.client = TestClient(self.app); self.client.__enter__()
        self.store = self.app.state.store
        self.headers = {'X-Workbench-Token':self.app.state.token}
        self.p = self.store.import_run(self.path)
        self.url = f"/api/projects/{self.p['id']}"

    def tearDown(self):
        self.client.__exit__(None,None,None); self.temp.cleanup()

    def change(self, action, key='', value=None):
        self.p = self.store.mutate(self.p['id'], dict(version=self.p['version'], action=action,
            id=key,value=value or {},actor='Mühendis',reason='Deney gerekçesi'))
        return self.p

    def source(self, text='A, ölçümleri Ethernet üzerinden B’ye aktarır.'):
        return dict(action='upsert_source', id='G-01', value=dict(requirement_id='G-01',text=text,section=None,original_id=None))

    def preview(self, commands):
        return self.store.preview(self.p['id'], self.p['version'], commands, 'Mühendis', 'İncelenecek değişiklik')

    def apply(self, preview):
        return self.change('apply_change_set',value={'preview_id':preview['id']})

    def wait_job(self, jid):
        until = time.monotonic()+5
        while time.monotonic()<until:
            job = self.client.get('/api/jobs/'+jid).json()
            if job['status'] not in ('queued','running'): return job
            time.sleep(.01)
        self.fail('Job did not finish')

    def ask(self, result, **body):
        with patch('app.workbench.LLMClient') as client:
            client.return_value.extract_json.return_value=result
            response = self.client.post(self.url+'/assistant', headers=self.headers,
                json={'version':self.p['version'],'message':'Değişikliği öner','profile':'openrouter_nemotron',**body})
            self.assertEqual(response.status_code,200,response.text)
            job=self.wait_job(response.json()['id'])
            prompt=client.return_value.extract_json.call_args.args[1]
        return job, self.store.conversation(self.p['id'])[-1], prompt

    def test_old_project_migration_is_stable_and_read_only(self):
        before=self.path.read_bytes()
        self.assertEqual(self.p['version'],0)
        self.assertEqual(self.p['state'],ReviewStore(self.store.path).get(self.p['id'])['state'])
        self.assertEqual(before,self.path.read_bytes())
        self.assertTrue(self.p['state']['assumption_records'][0]['id'].startswith('ASM-'))

    def test_preview_never_mutates_and_tid_apply_undo_redo_is_atomic(self):
        before=deepcopy(self.p['state']); original=deepcopy(self.p['original'])
        proposal=self.preview([self.source()])
        self.assertEqual(self.store.get(self.p['id'])['state'],before)
        self.assertEqual(proposal['changes'][0]['kind'],'requirement')
        self.apply(proposal)
        after=deepcopy(self.p['state'])
        self.assertEqual(self.p['original'],original)
        self.assertIn('Ethernet',after['source_catalog'][0]['text'])
        self.assertEqual(after['stale_links']['connection:E1'],['G-01'])
        self.change('undo');self.assertEqual(self.p['state'],before)
        self.change('redo');self.assertEqual(self.p['state'],after)

    def test_failed_second_command_rolls_back_everything(self):
        before=deepcopy(self.p)
        edge=deepcopy(self.p['state']['architecture']['connections'][0]);edge['target']='ghost'
        with self.assertRaises(ValueError):
            self.preview([self.source(),dict(action='upsert_connection',id='E1',value=edge)])
        self.assertEqual(self.store.get(self.p['id'])['state'],before['state'])
        self.assertEqual(self.store.get(self.p['id'])['version'],0)

    def test_preview_cannot_apply_after_any_new_revision_or_to_other_project(self):
        proposal=self.preview([self.source()])
        self.change('layout',value={'A':dict(x=1,y=2)})
        with self.assertRaises(ConflictError): self.apply(proposal)
        other=self.store.restore_snapshot(self.p)
        with self.assertRaises(ConflictError):
            self.store.mutate(other['id'],dict(version=0,action='apply_change_set',value={'preview_id':proposal['id']},actor='X',reason='X'))

    def test_requirement_identity_is_stable_and_deleted_ids_are_not_reused(self):
        bad=self.source();bad['value']['requirement_id']='other'
        with self.assertRaises(ValueError):self.preview([bad])
        self.apply(self.preview([dict(action='delete_source',id='G-01',value={})]))
        self.assertEqual(self.p['state']['source_catalog'],[])
        self.assertEqual(len(self.p['state']['retired_sources']),1)
        add=self.source();add['id']=''
        with self.assertRaises(ValueError):self.preview([add])

    def test_source_then_new_evidence_can_be_applied_in_one_revision(self):
        source=self.source();edge=deepcopy(self.p['state']['architecture']['connections'][0])
        edge.update(protocol='Ethernet',evidence=[dict(requirement_id='G-01',quote=source['value']['text'])])
        self.apply(self.preview([source,dict(action='upsert_connection',id='E1',value=edge)]))
        self.assertEqual(self.p['version'],1)
        self.assertNotIn('connection:E1',self.p['state']['stale_links'])
        self.assertIn('component:A',self.p['state']['stale_links'])

    def test_assumption_decision_has_dependencies_and_reopens_only_when_relevant(self):
        record=deepcopy(self.p['state']['assumption_records'][0])
        record.update(status='accepted',note='Arayüz incelendi',connection_ids=['E1'])
        self.apply(self.preview([dict(action='upsert_assumption',id=record['id'],value=record)]))
        self.assertFalse(self.p['state']['assumption_records'][0]['stale'])
        comp=deepcopy(self.p['state']['architecture']['components'][-1]);comp['name']='Bağımsız değişiklik'
        self.change('upsert_component','C',comp)
        self.assertFalse(self.p['state']['assumption_records'][0]['stale'])
        edge=deepcopy(self.p['state']['architecture']['connections'][0]);edge['direction']='bidirectional'
        self.change('upsert_connection','E1',edge)
        self.assertTrue(self.p['state']['assumption_records'][0]['stale'])

    def test_rejection_alone_does_not_delete_objects(self):
        arch=deepcopy(self.p['state']['architecture']);record=deepcopy(self.p['state']['assumption_records'][0])
        record.update(status='rejected',note='Doğru yön henüz bilinmiyor')
        self.apply(self.preview([dict(action='upsert_assumption',id=record['id'],value=record)]))
        self.assertEqual(self.p['state']['architecture'],arch)
        self.assertEqual(self.p['state']['assumption_records'][0]['status'],'rejected')

    def test_assumption_and_related_design_change_are_one_current_decision(self):
        record=deepcopy(self.p['state']['assumption_records'][0]);record.update(status='accepted',note='İncelendi',connection_ids=['E1'])
        edge=deepcopy(self.p['state']['architecture']['connections'][0]);edge['direction']='bidirectional'
        self.apply(self.preview([dict(action='upsert_assumption',id=record['id'],value=record),dict(action='upsert_connection',id='E1',value=edge)]))
        self.assertFalse(self.p['state']['assumption_records'][0]['stale'])
        self.change('undo');self.assertEqual(self.p['state']['assumption_records'][0]['status'],'pending')

    def test_new_documents_and_zip_use_current_tid_and_restore_decisions(self):
        self.apply(self.preview([self.source()]))
        response=self.client.get(self.url+'/tid');self.assertEqual(response.status_code,200)
        doc=Document(io.BytesIO(response.content))
        self.assertIn('Ethernet','\n'.join(p.text for p in doc.paragraphs))
        text=self.client.get(self.url+'/tid?format=txt').content.decode('utf-8-sig');self.assertIn('Ethernet',text)
        archive=self.client.get(self.url+'/export').content
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            self.assertIn('TID_calisma.docx',z.namelist())
            self.assertIn('Ethernet',json.loads(z.read('analysis_result.json'))['source_catalog'][0]['text'])
        restored=self.client.post('/api/documents?name=review.zip',content=archive,headers=self.headers)
        self.assertEqual(restored.status_code,200,restored.text)
        self.assertEqual(restored.json()['project']['state'],self.p['state'])
        self.assertEqual(restored.json()['project']['original'],self.p['original'])

    def test_assistant_answer_and_proposal_do_not_mutate_until_preview_applied(self):
        job,turn,prompt=self.ask(dict(answer='TİD maddesi için bir öneri hazırladım.',commands=[self.source()],citations=[]))
        self.assertEqual(job['status'],'completed',job)
        self.assertEqual(self.store.get(self.p['id'])['version'],0)
        self.assertIn('original_tid',prompt);self.assertIn('engineering',prompt)
        self.apply(turn['result']['preview'])
        self.assertIn('Ethernet',self.p['state']['source_catalog'][0]['text'])

    def test_assistant_bad_quote_is_rejected_and_no_changes_apply(self):
        job,turn,_=self.ask(dict(answer='Belgede belirtiliyor.',citations=[dict(source_id='G-01',quote='Uydurulmuş alıntı')],commands=[self.source()]))
        self.assertEqual(job['error_code'],'QUOTE_MISMATCH')
        self.assertIsNone(turn['result'])
        self.assertEqual(self.store.get(self.p['id'])['version'],0)

    def test_tid_mode_rejects_architecture_commands(self):
        job,_,_=self.ask(dict(answer='Sil.',commands=[dict(action='delete_component',id='A',value={'cascade':True})]),mode='tid')
        self.assertEqual(job['status'],'failed')
        self.assertEqual(self.store.get(self.p['id'])['version'],0)

    def test_assistant_invalid_patch_preserves_explanation_without_applying(self):
        job,turn,_=self.ask(dict(answer='Öneri açıklaması',commands=[dict(action='delete_source',id='unknown',value={})]))
        self.assertEqual(job['status'],'completed')
        self.assertIn('proposal_error',turn['result']);self.assertNotIn('preview',turn['result'])
        self.assertEqual(self.store.get(self.p['id'])['version'],0)

    def test_pending_assumption_decision_and_model_edit_share_one_preview(self):
        record=deepcopy(self.p['state']['assumption_records'][0]);record.update(status='rejected',note='Tek yön kullanılacak',alternative='A → B',connection_ids=['E1'])
        pending=dict(action='upsert_assumption',id=record['id'],value=record)
        job,turn,prompt=self.ask(dict(answer='Kararı önizleyin.',commands=[]),mode='assumption',pending_commands=[pending])
        self.assertEqual(job['status'],'completed');self.assertIn('Tek yön kullanılacak',prompt)
        self.assertEqual(self.store.get(self.p['id'])['state']['assumption_records'][0]['status'],'pending')
        self.apply(turn['result']['preview'])
        self.assertEqual(self.p['state']['assumption_records'][0]['status'],'rejected')

    def test_rereview_reads_current_tid_and_engineer_decisions(self):
        self.apply(self.preview([self.source()]))
        with patch('app.workbench.LLMClient') as client:
            client.return_value.extract_json.return_value={'findings':[]}
            response=self.client.post(self.url+'/review',json={'profile':'openrouter_nemotron'},headers=self.headers)
            job=self.wait_job(response.json()['id'])
            self.assertEqual(job['status'],'completed',job)
            prompt=client.return_value.extract_json.call_args.args[1]
            self.assertIn('Ethernet',prompt);self.assertIn('ENGINEER DECISIONS',prompt)

    def test_async_reply_cannot_overwrite_new_tid_revision(self):
        started=threading.Event();release=threading.Event()
        def response(*_):
            started.set();release.wait(3)
            return dict(answer='Öneri',commands=[self.source()])
        with patch('app.workbench.LLMClient') as client:
            client.return_value.extract_json.side_effect=response
            request=self.client.post(self.url+'/assistant',headers=self.headers,json=dict(version=0,message='Öner',profile='openrouter_nemotron'))
            self.assertTrue(started.wait(2))
            self.apply(self.preview([self.source('Mühendisin yeni metni.')]))
            release.set();job=self.wait_job(request.json()['id'])
        self.assertEqual(job['status'],'completed')
        turn=self.store.conversation(self.p['id'])[-1]
        self.assertIn('proposal_error',turn['result'])
        self.assertEqual(self.store.get(self.p['id'])['state']['source_catalog'][0]['text'],'Mühendisin yeni metni.')

    def test_workspace_fingerprint_includes_document_and_decisions(self):
        old=workspace_fingerprint(self.p['state']);arch=deepcopy(self.p['state']['architecture'])
        self.apply(self.preview([self.source()]))
        self.assertEqual(arch,self.p['state']['architecture'])
        self.assertNotEqual(old,workspace_fingerprint(self.p['state']))

    def test_preview_requires_auth_and_forbids_nested_mutations(self):
        response=self.client.post(self.url+'/preview',json=dict(version=0,actor='X',commands=[self.source()]))
        self.assertEqual(response.status_code,403)
        with self.assertRaises(ValueError):self.preview([dict(action='undo',value={})])

    def test_budget_fails_explicitly_without_truncating_document(self):
        p=deepcopy(self.p);p['state']['source_catalog'][0]['text']='X'*120001
        with self.assertRaises(LLMError) as caught:assistant_prompt(p,'Sor','chat',[],{},[])
        self.assertEqual(caught.exception.code,'INPUT_BUDGET')

    def test_original_citation_is_explicit_after_tid_revision(self):
        quote=self.p['original']['source_catalog'][0]['text']
        self.apply(self.preview([self.source()]))
        raw=dict(answer='Özgün belgede RS-422 yazıyordu.',citations=[dict(source_id='G-01',document='original',quote=quote)])
        self.assertEqual(validate_answer(raw,self.p,'chat')['citations'][0]['document'],'original')
        raw['citations'][0]['document']='current'
        with self.assertRaises(LLMError):validate_answer(raw,self.p,'chat')

    def test_model_cannot_reverse_pending_engineer_decision(self):
        record=deepcopy(self.p['state']['assumption_records'][0]);record.update(status='rejected',note='Ret gerekçesi')
        pending=dict(action='upsert_assumption',id=record['id'],value=record)
        override=deepcopy(pending);override['value']['status']='accepted'
        job,turn,_=self.ask(dict(answer='Öneri',commands=[override]),mode='assumption',pending_commands=[pending])
        self.assertEqual(job['status'],'completed')
        self.assertIn('proposal_error',turn['result'])
        self.assertNotIn('preview',turn['result'])

    def test_conversation_export_restores_as_history_without_reusable_preview(self):
        _,turn,_=self.ask(dict(answer='Öneri',commands=[self.source()]),api_key='unit-test-secret')
        archive=self.client.get(self.url+'/export').content
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            snapshot=json.loads(z.read('engineering_review.json'))
            self.assertNotIn('unit-test-secret',json.dumps(snapshot))
        restored=self.store.restore_snapshot(snapshot)
        history=self.store.conversation(restored['id'])
        self.assertEqual(history[0]['result']['answer'],'Öneri')
        self.assertTrue(history[0]['imported'])
        self.assertNotIn('preview',history[0]['result'])

    def test_document_change_during_review_blocks_stale_results(self):
        started=threading.Event();release=threading.Event()
        def response(*_):started.set();release.wait(3);return {'findings':[]}
        with patch('app.workbench.LLMClient') as client:
            client.return_value.extract_json.side_effect=response
            r=self.client.post(self.url+'/review',json={'profile':'openrouter_nemotron'},headers=self.headers)
            self.assertTrue(started.wait(2));self.apply(self.preview([self.source()]))
            release.set();job=self.wait_job(r.json()['id'])
        self.assertEqual(job['status'],'failed')
        self.assertEqual(job['error_code'],'ConflictError')
        self.assertEqual(self.store.get(self.p['id'])['version'],1)


if __name__=='__main__': unittest.main()
