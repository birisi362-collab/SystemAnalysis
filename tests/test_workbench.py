import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from fastapi.testclient import TestClient

from app.models import FinalModel
from app.pipeline import run
from app.llm_client import FixtureClient
from app.review_store import ReviewStore, ConflictError, enrich_issues
from app.workbench import create_app

ROOT = Path(__file__).resolve().parents[1]
NEMOTRON = ROOT/'outputs/20260930_182611_214350'


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root/'source'
        run(str(ROOT/'evaluation/cases/dev_01.txt'), str(self.source), FixtureClient(ROOT/'evaluation/cases/dev_01.fixture.json'))
        self.before = (self.source/'analysis_result.json').read_bytes()
        self.store = ReviewStore(self.root/'reviews.sqlite3')
        self.p = self.store.import_run(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def apply(self, action, key='', value=None, reason='Mühendislik test gerekçesi'):
        self.p = self.store.mutate(self.p['id'], dict(version=self.p['version'], action=action, id=key, value=value or {}, actor='Test mühendisi', reason=reason))
        return self.p

    def test_edit_persists_restart_and_preserves_original_bytes(self):
        component = copy.deepcopy(self.p['state']['architecture']['components'][0])
        component['name'] = 'Düzeltilmiş bileşen'
        self.apply('upsert_component', component['id'], component)
        reopened = ReviewStore(self.root/'reviews.sqlite3').get(self.p['id'])
        self.assertEqual(reopened['state']['architecture']['components'][0]['name'], component['name'])
        self.assertNotEqual(reopened['original']['architecture']['components'][0]['name'], component['name'])
        self.assertEqual(self.before, (self.source/'analysis_result.json').read_bytes())
        self.assertEqual(self.store.import_run(self.source)['id'], self.p['id'])

    def test_undo_redo_restore_full_snapshot_and_keep_history(self):
        initial = copy.deepcopy(self.p['state'])
        c = copy.deepcopy(initial['architecture']['components'][0]); c['name'] = 'Changed'
        self.apply('upsert_component', c['id'], c)
        changed = copy.deepcopy(self.p['state'])
        self.apply('undo'); self.assertEqual(self.p['state'], initial)
        self.assertTrue(self.p['can_redo'])
        self.apply('redo'); self.assertEqual(self.p['state'], changed)
        self.assertEqual(len(self.p['history']), 4)
        self.apply('undo')
        self.apply('set_decision', 'component:'+c['id'], {'status':'approved'})
        self.assertFalse(self.p['can_redo'])
        self.assertEqual(len(self.p['history']), 6)

    def test_stale_version_rejected_without_lost_update(self):
        c = self.p['state']['architecture']['components'][0]
        self.apply('set_decision', 'component:'+c['id'], {'status':'approved'})
        with self.assertRaises(ConflictError):
            self.store.mutate(self.p['id'], dict(version=0, action='set_decision', id='component:'+c['id'], value={'status':'rejected'}, actor='Other', reason='Stale'))
        self.assertEqual(self.store.get(self.p['id'])['state']['decisions']['component:'+c['id']]['status'], 'approved')

    def test_changed_evidence_invalidates_source_and_object_approval(self):
        c = copy.deepcopy(self.p['state']['architecture']['components'][0]); rid=c['evidence'][0]['requirement_id']
        self.apply('set_decision', 'component:'+c['id'], {'status':'approved'})
        self.apply('set_decision', 'source:'+rid, {'status':'approved'})
        c['description'] = 'Yeni açıklama'
        self.apply('upsert_component', c['id'], c)
        self.assertTrue(self.p['state']['decisions']['component:'+c['id']]['stale'])
        self.assertTrue(self.p['state']['decisions']['source:'+rid]['stale'])

    def test_layout_does_not_invalidate_engineering_approval(self):
        c = self.p['state']['architecture']['components'][0]
        self.apply('set_decision', 'component:'+c['id'], {'status':'approved'})
        self.apply('layout', value={c['id']:{'x':54,'y':120}})
        self.assertFalse(self.p['state']['decisions']['component:'+c['id']]['stale'])
        self.assertEqual(self.p['state']['positions'][c['id']]['x'], 54)

    def test_bad_quote_rejected_without_partial_save(self):
        c=copy.deepcopy(self.p['state']['architecture']['components'][0]);c['evidence'][0]['quote']='Alakasız alıntı'
        with self.assertRaisesRegex(ValueError,'Alıntı'):
            self.apply('upsert_component',c['id'],c)
        self.assertEqual(self.store.get(self.p['id'])['version'],0)

    def test_engineering_addition_without_evidence_is_visible(self):
        self.apply('upsert_component', value=dict(id='manual',name='Yeni tasarım',category='component',description='',evidence=[]))
        self.assertEqual(self.p['state']['provenance']['component:manual']['origin'],'engineer_added')
        self.assertTrue(any(i['code']=='MISSING_EVIDENCE' and i['object_id']=='manual' for i in self.p['issues']))
        self.assertNotIn('component:manual',self.p['state']['decisions'])

    def test_invalid_endpoint_rejected(self):
        edge=copy.deepcopy(self.p['state']['architecture']['connections'][0]);edge['target']='ghost'
        with self.assertRaises(ValueError):self.apply('upsert_connection',edge['id'],edge)

    def test_delete_connected_component_requires_explicit_cascade_and_undo(self):
        edge=self.p['state']['architecture']['connections'][0]
        with self.assertRaises(ValueError):self.apply('delete_component',edge['source'])
        initial=copy.deepcopy(self.p['state'])
        self.apply('delete_component',edge['source'],{'cascade':True})
        self.assertFalse(any(e['source']==edge['source'] or e['target']==edge['source'] for e in self.p['state']['architecture']['connections']))
        self.assertTrue(all(edge['source'] not in c['related_component_ids'] for c in self.p['state']['architecture']['requirement_coverage']))
        self.apply('undo');self.assertEqual(self.p['state'],initial)

    def test_false_extra_protocol_is_reported(self):
        edge=copy.deepcopy(self.p['state']['architecture']['connections'][0]);edge['protocol'] += ' / UDP'
        self.apply('upsert_connection',edge['id'],edge)
        self.assertTrue(any(i['code']=='PROTOCOL_NOT_SUPPORTED' for i in self.p['issues']))

    def test_merge_cycle_rejected_and_findings_become_stale(self):
        for fid in ['f_a','f_b']:
            self.apply('add_finding',value=dict(id=fid,severity='medium',type='other',title='Test',description='Test',evidence=[],related_component_ids=[],related_connection_ids=[]))
        self.apply('set_decision','finding:f_a',{'status':'merged','merged_into':'f_b'})
        with self.assertRaises(ValueError):self.apply('set_decision','finding:f_b',{'status':'merged','merged_into':'f_a'})
        c=copy.deepcopy(self.p['state']['architecture']['components'][0]);c['name']='Değişti'
        self.apply('upsert_component',c['id'],c)
        self.assertTrue(self.p['state']['decisions']['finding:f_a']['stale'])

    def test_coverage_edit_is_independent_of_human_approval(self):
        c=copy.deepcopy(self.p['state']['architecture']['requirement_coverage'][0]);c['status']='partially_covered'
        self.apply('set_coverage',value=c)
        self.assertTrue(any(i['code']=='PARTIAL_COVERAGE' for i in self.p['issues']))
        self.assertNotIn('source:'+c['requirement_id'],self.p['state']['decisions'])

    def test_reason_and_author_required(self):
        with self.assertRaises(ValueError):self.apply('layout',value={},reason=' ')

    def test_finding_can_be_repaired_after_related_component_removed(self):
        component=self.p['state']['architecture']['components'][0]
        finding=dict(id='f_repair',severity='medium',type='other',title='Review',description='Review',evidence=component['evidence'],related_component_ids=[component['id']],related_connection_ids=[])
        self.apply('add_finding',value=finding)
        self.apply('set_decision','finding:f_repair',{'status':'accepted'})
        self.apply('delete_component',component['id'],{'cascade':True})
        issue=next(i for i in self.p['issues'] if i['code']=='UNKNOWN_COMPONENT_REF')
        self.assertEqual(issue['finding_id'],'f_repair')
        finding['related_component_ids']=[]
        finding['title']='Updated review'
        self.apply('edit_finding','f_repair',finding)
        self.assertFalse(any(i['code']=='UNKNOWN_COMPONENT_REF' for i in self.p['issues']))
        self.assertTrue(self.p['state']['decisions']['finding:f_repair']['stale'])
        self.assertEqual(self.p['state']['analysis']['findings'][0]['title'],'Updated review')
        self.apply('undo')
        self.assertTrue(any(i['code']=='UNKNOWN_COMPONENT_REF' for i in self.p['issues']))

    def test_finding_missing_evidence_points_to_editable_finding(self):
        self.apply('add_finding',value=dict(id='f_note',severity='low',type='other',title='Observation',description='Observation',evidence=[]))
        issue=next(i for i in self.p['issues'] if i['code']=='MISSING_EVIDENCE')
        self.assertEqual(issue['finding_id'],'f_note')
        self.assertIsNone(issue['object_id'])
        changed=copy.deepcopy(self.p['state']['analysis']['findings'][0]);changed['id']='wrong'
        with self.assertRaises(ValueError):self.apply('edit_finding','f_note',changed)

    @unittest.skipUnless(NEMOTRON.exists(),'Recorded Nemotron run is not in this checkout')
    def test_nemotron_mismatches_are_expanded_without_hiding_errors(self):
        final=FinalModel.model_validate_json((NEMOTRON/'analysis_result.json').read_bytes())
        issues=enrich_issues(final)
        mismatches=[i for i in issues if i['code']=='COVERAGE_EVIDENCE_MISMATCH']
        self.assertEqual(len(mismatches),19)
        self.assertEqual(len(issues),20)
        self.assertTrue(all(i['object_id'] and i['source_id'] for i in mismatches))
        self.assertTrue(all(not i['object_id'].startswith('if_') for i in mismatches))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=self.root/'source'
        run(str(ROOT/'evaluation/cases/dev_01.txt'),str(self.source),FixtureClient(ROOT/'evaluation/cases/dev_01.fixture.json'))
        self.app=create_app(self.root/'data')
        self.client=TestClient(self.app);self.client.__enter__()
        self.token=self.client.get('/api/bootstrap').json()['token']
        self.headers={'X-Workbench-Token':self.token}

    def tearDown(self):
        self.client.__exit__(None,None,None);self.temp.cleanup()

    def test_cross_origin_and_missing_token_rejected(self):
        body={'path':str(self.source)}
        self.assertEqual(self.client.post('/api/projects/import',json=body).status_code,403)
        self.assertEqual(self.client.post('/api/projects/import',json=body,headers={**self.headers,'Origin':'https://untrusted.example'}).status_code,403)
        self.assertEqual(self.client.get('/api/bootstrap',headers={'Host':'untrusted.example'}).status_code,400)
        self.assertEqual(self.client.get('/api/bootstrap',headers={'Sec-Fetch-Site':'cross-site'}).status_code,403)

    def test_import_edit_export_contains_original_and_review(self):
        p=self.client.post('/api/projects/import',json={'path':str(self.source)},headers=self.headers).json()
        c=copy.deepcopy(p['state']['architecture']['components'][0]);c['name']='API düzenlemesi'
        response=self.client.post('/api/projects/'+p['id']+'/changes',json=dict(version=0,action='upsert_component',id=c['id'],value=c,actor='Mühendis',reason='Ad düzeltmesi'),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        exported=self.client.get('/api/projects/'+p['id']+'/export')
        self.assertEqual(exported.status_code,200)
        with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
            final=json.loads(z.read('analysis_result.json'));original=json.loads(z.read('original_analysis_result.json'));review=json.loads(z.read('engineering_review.json'))
            self.assertEqual(final['architecture']['components'][0]['name'],'API düzenlemesi')
            self.assertNotEqual(final['architecture'],original['architecture'])
            self.assertEqual(len(review['history']),2)
            self.assertIn('system_diagram.mmd',z.namelist())

    def test_invalid_import_returns_readable_error(self):
        response=self.client.post('/api/projects/import',json={'path':str(self.root/'missing')},headers=self.headers)
        self.assertEqual(response.status_code,422)
        self.assertIn('Dosya',response.json()['detail'])

    def test_api_conflict_is_409(self):
        p=self.client.post('/api/projects/import',json={'path':str(self.source)},headers=self.headers).json()
        c=p['state']['architecture']['components'][0]
        cmd=dict(version=0,action='set_decision',id='component:'+c['id'],value={'status':'approved'},actor='Mühendis',reason='İncelendi')
        self.assertEqual(self.client.post('/api/projects/'+p['id']+'/changes',json=cmd,headers=self.headers).status_code,200)
        self.assertEqual(self.client.post('/api/projects/'+p['id']+'/changes',json=cmd,headers=self.headers).status_code,409)


if __name__=='__main__':unittest.main()
