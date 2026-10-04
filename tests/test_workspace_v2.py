"""Workspace contracts: optional sources, atomic proposals and portable projects."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import time
import zipfile

from fastapi.testclient import TestClient

from app.models import FinalModel
from app.review_store import ReviewStore, ConflictError
from app.review_topics import fingerprint
from app.validator_audit import baseline
from app.workbench import create_app
from app.workbench import review_failure
from app.llm_client import LLMClient, LLMError


def example():
    data = baseline()
    data['architecture'].pop('requirement_coverage')
    data['architecture']['components'].append(dict(id='C', name='Bağımsız', evidence=[]))
    data['analysis']['findings'] = [dict(
        id='P1', severity='medium', type='missing_connection', title='Gözlem birimini ekleyin',
        description='Test önerisi', evidence=[], related_component_ids=['A'],
        proposed_changes=[
            dict(action='add',kind='component',id='D',value=dict(name='Gözlem birimi',evidence=[])),
            dict(action='add',kind='connection',id='E2',value=dict(source='A',target='D',type='data',evidence=[])),
        ], open_details=['Arayüz protokolü mühendis tarafından belirlenmeli.'])]
    return data


class ReviewFailureTests(unittest.TestCase):
    def test_provider_error_keeps_specific_code_and_action(self):
        code, message=review_failure(LLMError('PROVIDER_ERROR','Provider error'))
        self.assertEqual(code,'PROVIDER_ERROR')
        self.assertIn('sağlayıcısı',message)
        self.assertIn('korundu',message)

    def test_invalid_key_is_explained_before_network_without_disclosure(self):
        client=LLMClient('https://example.com',api_key='secret-ş-key',model='model')
        with patch.object(client.session,'post') as post:
            with self.assertRaises(LLMError) as caught:client.extract_json('system','user')
            post.assert_not_called()
        self.assertEqual(caught.exception.code,'INVALID_HEADER')
        self.assertIn('API anahtarı',str(caught.exception))
        self.assertNotIn('secret',str(caught.exception))

    def test_key_outer_whitespace_is_removed_without_changing_value(self):
        client=LLMClient(' https://example.com/ ',api_key='  secret-key  ',model=' model ')
        self.assertEqual(client.api_key,'secret-key')
        self.assertEqual(client.base_url,'https://example.com')


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.path=self.root/'analysis_result.json'
        self.path.write_text(json.dumps(example()),encoding='utf-8')
        self.store=ReviewStore(self.root/'reviews.sqlite3')
        self.p=self.store.import_run(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def change(self,action,key='',value=None):
        self.p=self.store.mutate(self.p['id'],dict(action=action,id=key,value=value or {},actor='Mühendis',reason='İnceledim',version=self.p['version']))
        return self.p

    def apply(self,changes=None):
        value=dict(fingerprint=self.p['proposals']['P1']['fingerprint'])
        if changes is not None:value['changes']=changes
        return self.change('apply_proposal','P1',value)

    def test_optional_coverage_and_unlinked_text_produce_no_tasks(self):
        self.assertEqual(self.p['state']['architecture']['requirement_coverage'],[])
        self.assertEqual(self.p['issues'],[])
        self.assertEqual(len(self.p['topics']),1)

    def test_multi_change_proposal_is_one_undoable_revision(self):
        before=deepcopy(self.p['state'])
        self.apply()
        self.assertEqual(self.p['version'],1)
        self.assertTrue(any(c['id']=='D' for c in self.p['state']['architecture']['components']))
        self.assertTrue(any(e['id']=='E2' for e in self.p['state']['architecture']['connections']))
        self.assertEqual(self.p['topics'][0]['decision']['status'],'applied')
        after=deepcopy(self.p['state'])
        with self.assertRaises(ValueError):self.apply()
        self.change('undo');self.assertEqual(self.p['state'],before)
        self.change('redo');self.assertEqual(self.p['state'],after)

    def test_bad_second_change_rolls_back_entire_proposal(self):
        before=deepcopy(self.p)
        changes=deepcopy(self.p['state']['analysis']['findings'][0]['proposed_changes'])
        changes[1]['value']['target']='ghost'
        with self.assertRaises(ValueError):self.apply(changes)
        actual=self.store.get(self.p['id'])
        self.assertEqual(actual['state'],before['state'])
        self.assertEqual(actual['history'],before['history'])

    def test_engineer_can_edit_values_but_not_hidden_targets(self):
        changes=deepcopy(self.p['state']['analysis']['findings'][0]['proposed_changes'])
        changes[0]['value']['name']='Mühendisin seçtiği ad'
        changes[1]['value']['protocol']='Özel arayüz'
        self.apply(changes)
        self.assertEqual(self.p['state']['architecture']['components'][-1]['name'],'Mühendisin seçtiği ad')
        self.change('undo')
        changes[0]['id']='secret_target'
        with self.assertRaises(ValueError):self.apply(changes)

    def test_relevant_changes_block_old_proposal_but_unrelated_edits_do_not(self):
        c=deepcopy(self.p['state']['architecture']['components'][-1]);c['name']='Bağımsız yeni ad'
        self.change('upsert_component','C',c)
        self.change('layout',value={'A':{'x':10,'y':20}})
        self.assertFalse(self.p['proposals']['P1']['stale'])
        self.apply();self.change('undo')
        c=deepcopy(self.p['state']['architecture']['components'][0]);c['description']='Yeni bilgi'
        self.change('upsert_component','A',c)
        self.assertTrue(self.p['proposals']['P1']['stale'])
        with self.assertRaises(ConflictError):self.apply()

    def test_rereview_keeps_edits_and_decisions_and_suppresses_exact_duplicates(self):
        topic=self.p['topics'][0]
        self.change('set_topic_decision',topic['id'],{'status':'rejected'})
        arch=deepcopy(self.p['state']['architecture'])
        finding=dict(id='new',severity='low',type='other',title='Yeni not',description='İncele',evidence=[],related_component_ids=['A'])
        value=dict(analysis={'findings':[finding]},architecture_fingerprint=fingerprint(arch))
        self.change('append_review',value=value)
        self.change('append_review',value=value)
        self.assertEqual(len(self.p['topics']),2)
        self.assertEqual(self.p['state']['architecture'],arch)
        self.assertEqual(next(t for t in self.p['topics'] if t['id']==topic['id'])['decision']['status'],'rejected')
        c=deepcopy(arch['components'][0]);c['name']='Değişti'
        self.change('upsert_component','A',c)
        with self.assertRaises(ConflictError):self.change('append_review',value=value)

    def test_rereview_rejects_unknown_references(self):
        finding=dict(id='bad',severity='low',type='other',title='Not',description='Not',related_component_ids=['ghost'])
        with self.assertRaises(ValueError):
            self.change('append_review',value=dict(analysis={'findings':[finding]},architecture_fingerprint=fingerprint(self.p['state']['architecture'])))
        self.assertEqual(self.store.get(self.p['id'])['version'],0)

    def test_legacy_decision_migration_preserves_closed_and_automatic_history(self):
        state=deepcopy(self.p['state'])
        state['decisions']={'finding:P1':dict(status='accepted',note='Eski karar',stale=False), 'topic:old_check':dict(status='resolved',note='Eski otomatik kayıt')}
        with self.store.db() as db:
            db.execute('UPDATE revisions SET state=? WHERE project_id=? AND seq=0',(json.dumps(state),self.p['id']))
        self.p=self.store.get(self.p['id'])
        self.assertEqual(self.p['topics'][0]['status'],'completed')
        self.change('layout',value={'A':{'x':10,'y':20}})
        self.assertEqual(self.p['topics'][0]['status'],'completed')
        self.assertEqual(len(self.p['topics']),1)
        self.assertIn('topic:old_check',self.p['state']['decisions'])
        self.assertEqual(self.p['topics'][0]['decision']['note'],'Eski karar')


class WorkspaceApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.path=self.root/'analysis_result.json'
        self.path.write_text(json.dumps(example()),encoding='utf-8')
        self.app=create_app(self.root/'data');self.client=TestClient(self.app);self.client.__enter__()
        self.headers={'X-Workbench-Token':self.client.get('/api/bootstrap').json()['token']}
        self.p=self.client.post('/api/projects/import',json={'path':str(self.path)},headers=self.headers).json()

    def tearDown(self):
        self.client.__exit__(None,None,None);self.temp.cleanup()

    def test_two_way_direction_is_saved_reopened_exported_and_undoable(self):
        edge=deepcopy(self.p['state']['architecture']['connections'][0]);edge['direction']='bidirectional'
        endpoint=f"/api/projects/{self.p['id']}/changes"
        response=self.client.post(endpoint,json=dict(version=self.p['version'],action='upsert_connection',id=edge['id'],value=edge,actor='Mühendis'),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        p=self.client.get('/api/projects/'+self.p['id']).json()
        self.assertEqual(p['state']['architecture']['connections'][0]['direction'],'bidirectional')
        archive=self.client.get('/api/projects/'+self.p['id']+'/export').content
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            self.assertIn('<-->',z.read('system_diagram.mmd').decode('utf-8'))
        response=self.client.post(endpoint,json=dict(version=p['version'],action='undo',actor='Mühendis'),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['state']['architecture']['connections'][0]['direction'],'unidirectional')

    def test_file_upload_validates_content_and_keeps_filename_out_of_path_traversal(self):
        response=self.client.post('/api/documents',params={'name':'../../Belge.txt'},content='Gereksinim'.encode(),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        path=Path(response.json()['path']).resolve()
        self.assertTrue(path.is_relative_to(self.root/'data'/'documents'))
        self.assertEqual(path.read_text(encoding='utf-8'),'Gereksinim')
        for name, content in [('empty.txt',b''),('app.exe',b'not executable'),('bad.zip',b'not zip')]:
            self.assertEqual(self.client.post('/api/documents',params={'name':name},content=content,headers=self.headers).status_code,422)

    def test_export_import_preserves_original_layout_decisions_and_history(self):
        endpoint=f"/api/projects/{self.p['id']}/changes"
        command=dict(version=0,action='apply_proposal',id='P1',actor='Mühendis',reason='İncelenerek eklendi',value={'fingerprint':self.p['proposals']['P1']['fingerprint']})
        response=self.client.post(endpoint,json=command,headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        current=response.json()
        archive=self.client.get(f"/api/projects/{self.p['id']}/export").content
        restored=self.client.post('/api/documents',params={'name':'çalışma.zip'},content=archive,headers=self.headers)
        self.assertEqual(restored.status_code,200,restored.text)
        p=restored.json()['project']
        self.assertNotEqual(p['id'],current['id'])
        self.assertEqual(p['state'],current['state'])
        self.assertEqual(p['original'],current['original'])
        self.assertEqual(p['topics'][0]['decision']['status'],'applied')
        self.assertEqual(len(p['history']),len(current['history'])+1)

    def test_rereview_api_uses_current_architecture_and_does_not_replace_it(self):
        result={'findings':[dict(id='fresh',severity='low',type='ambiguous',title='Yeni soru',description='İncele',evidence=[],related_component_ids=['A'])]}
        with patch('app.workbench.LLMClient') as client:
            client.return_value.extract_json.return_value=result
            response=self.client.post(f"/api/projects/{self.p['id']}/review",json={'profile':'openrouter_nemotron'},headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
            jid=response.json()['id']
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                job=self.client.get('/api/jobs/'+jid).json()
                if job['status'] not in ('queued','running'):break
                time.sleep(.02)
            self.assertEqual(job['status'],'completed',job)
            client.return_value.extract_json.assert_called_once()
        p=self.client.get('/api/projects/'+self.p['id']).json()
        self.assertEqual(p['state']['architecture'],self.p['state']['architecture'])
        self.assertEqual(len(p['topics']),2)

    def test_rereview_failure_retains_transport_code_and_project(self):
        with patch('app.workbench.LLMClient') as client:
            client.return_value.extract_json.side_effect=LLMError('RATE_LIMIT','quota')
            response=self.client.post(f"/api/projects/{self.p['id']}/review",json={'profile':'openrouter_nemotron'},headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
            jid=response.json()['id'];deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                job=self.client.get('/api/jobs/'+jid).json()
                if job['status'] not in ('queued','running'):break
                time.sleep(.02)
            self.assertEqual(job['error_code'],'RATE_LIMIT')
            self.assertIn('kota',job['message'])
        self.assertEqual(self.client.get('/api/projects/'+self.p['id']).json()['state'],self.p['state'])

    def test_truncation_records_selected_budget_and_retains_work(self):
        with patch('app.workbench.LLMClient') as client:
            client.return_value.extract_json.side_effect=LLMError('TRUNCATED','length')
            client.return_value.calls=[dict(finish_reason='length',usage={'prompt_tokens':2000,'completion_tokens':16384,'total_tokens':18384})]
            response=self.client.post(f"/api/projects/{self.p['id']}/review",json={'profile':'openrouter_nemotron','max_tokens':16384,'timeout':900},headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
            jid=response.json()['id'];deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                job=self.client.get('/api/jobs/'+jid).json()
                if job['status'] not in ('queued','running'):break
                time.sleep(.02)
            self.assertEqual(job['error_code'],'TRUNCATED')
            self.assertEqual(job['max_tokens'],16384)
            self.assertEqual(job['timeout'],900)
            self.assertEqual(job['finish_reason'],'length')
            self.assertEqual(job['token_usage']['completion_tokens'],16384)
            self.assertIn('16,384',job['message'])
            self.assertEqual(client.call_args.kwargs['max_tokens'],16384)
        self.assertEqual(self.client.get('/api/projects/'+self.p['id']).json()['state'],self.p['state'])


if __name__=='__main__':unittest.main()
