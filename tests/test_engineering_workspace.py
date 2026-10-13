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

from app.engineering_workspace import workspace_fingerprint, legacy_assumption_basis, upgrade_state
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

    def decide_linked(self, linked=True):
        record = deepcopy(self.p['state']['assumption_records'][0])
        record.update(status='accepted', note='Mühendis tarafından doğrulandı', connection_ids=['E1'] if linked else [])
        self.apply(self.preview([dict(action='upsert_assumption', id=record['id'], value=record)]))
        return self.p['state']['assumption_records'][0]

    def review_preview(self, commands, choices):
        response = self.client.post(self.url+'/preview', headers=self.headers, json=dict(
            version=self.p['version'],commands=commands,actor='Denetleyen',reason='Teknik değişiklik',assumption_reviews=choices))
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_old_preview_database_migrates_without_losing_saved_preview(self):
        preview = self.preview([self.source()])
        with self.store.db() as db:
            db.execute('ALTER TABLE change_previews DROP COLUMN assumption_reviews')
        migrated = ReviewStore(self.store.path)
        self.assertEqual(migrated.get(self.p['id'])['version'], self.p['version'])
        updated = migrated.mutate(self.p['id'], dict(version=self.p['version'],action='apply_change_set',actor='Mühendis',reason='Eski önizleme',value={'preview_id':preview['id']}))
        self.assertIn('Ethernet',updated['state']['source_catalog'][0]['text'])

    def test_manual_keep_preserves_decision_but_future_technical_change_reopens(self):
        old = self.decide_linked()
        commands = [self.source()]
        auto = self.preview(commands)
        self.assertEqual(auto['assumption_review_candidates'][0]['suggested'], 'review')
        selected = self.review_preview(commands, {old['id']:'keep'})
        self.assertFalse(selected['stale_assumptions'])
        self.assertEqual(self.store.get(self.p['id'])['state']['assumption_records'][0], old)
        self.apply(selected)
        record = self.store.get(self.p['id'])['state']['assumption_records'][0]
        for field in ('status', 'note', 'actor', 'at'):
            self.assertEqual(record[field], old[field])
        self.assertFalse(record['stale'])
        self.assertEqual(record['impact_review']['action'], 'keep')
        self.assertEqual(record['impact_review']['actor'], 'Denetleyen')
        self.apply(self.preview([self.source('A ölçümleri fiber bağlantı üzerinden B’ye aktarır.')]))
        self.assertTrue(self.p['state']['assumption_records'][0]['stale'])

    def test_schema_protocol_change_can_keep_decision_without_changing_tid(self):
        old = self.decide_linked()
        source_before = deepcopy(self.p['state']['source_catalog'])
        connection = deepcopy(self.p['state']['architecture']['connections'][0])
        connection['protocol'] = 'Ethernet'
        commands = [dict(action='upsert_connection', id=connection['id'], value=connection)]
        automatic = self.preview(commands)
        self.assertTrue(automatic['document_review_required'])
        self.assertEqual(automatic['assumption_review_candidates'][0]['suggested'], 'review')
        self.apply(self.review_preview(commands, {old['id']:'keep'}))
        self.assertFalse(self.p['state']['assumption_records'][0]['stale'])
        self.assertEqual(self.p['state']['assumption_records'][0]['status'],'accepted')
        self.assertEqual(self.p['state']['source_catalog'], source_before)

    def test_force_review_unlinked_persists_and_new_decision_completes_review(self):
        old = self.decide_linked(linked=False)
        preview = self.review_preview([self.source()], {old['id']:'review'})
        self.assertEqual(preview['assumption_review_candidates'][0]['suggested'], 'keep')
        self.apply(preview)
        record = self.store.get(self.p['id'])['state']['assumption_records'][0]
        self.assertEqual(record['status'], 'accepted')
        self.assertTrue(record['stale'])
        self.assertIn('Mühendis', record['stale_reason'])
        self.apply(self.preview([self.source('Bağımsız bir kaynak değişikliği.')]))
        self.assertTrue(self.p['state']['assumption_records'][0]['stale'])
        record = deepcopy(self.p['state']['assumption_records'][0])
        record.update(status='rejected', note='Yeni bilgi ile reddedildi')
        self.apply(self.preview([dict(action='upsert_assumption',id=record['id'],value=record)]))
        self.assertFalse(self.p['state']['assumption_records'][0]['stale'])
        self.assertEqual(self.p['state']['assumption_records'][0]['impact_review'], {})

    def test_review_choice_undo_redo_and_export_import_preserve_prior_decision(self):
        record = self.decide_linked(linked=False)
        before = deepcopy(self.p['state'])
        self.apply(self.review_preview([self.source()], {record['id']:'review'}))
        after = deepcopy(self.p['state'])
        self.change('undo'); self.assertEqual(self.p['state'],before)
        self.change('redo'); self.assertEqual(self.p['state'],after)
        package = self.client.get(self.url+'/export')
        imported = self.client.post('/api/documents?name=review.zip', content=package.content, headers=self.headers)
        self.assertEqual(imported.status_code,200,imported.text)
        self.assertEqual(imported.json()['project']['state']['assumption_records'][0]['impact_review'],after['assumption_records'][0]['impact_review'])

    def test_preview_rejects_unknown_pending_and_invalid_review_choices(self):
        pending = self.p['state']['assumption_records'][0]
        for choices in ({pending['id']:'keep'}, {'missing':'review'}, {pending['id']:'accept'}):
            response=self.client.post(self.url+'/preview',headers=self.headers,json=dict(version=self.p['version'],commands=[self.source()],actor='Mühendis',assumption_reviews=choices))
            self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.store.get(self.p['id'])['version'],self.p['version'])

    def test_preview_choice_cannot_be_applied_after_new_version(self):
        record=self.decide_linked()
        preview=self.review_preview([self.source()],{record['id']:'keep'})
        self.apply(self.preview([self.source('Yeni bir teknik gereksinim.')]))
        with self.assertRaises(ConflictError):
            self.apply(preview)
        self.assertTrue(self.p['state']['assumption_records'][0]['stale'])

    def test_original_document_download_ignores_working_edits(self):
        original=self.p['original']['source_catalog'][0]['text']
        self.apply(self.preview([self.source('Yeni çalışma metni.')]))
        for ext in ('txt', 'docx'):
            response=self.client.get(self.url+'/tid',params={'format':ext,'original':'true'})
            self.assertEqual(response.status_code,200)
            text=response.content.decode('utf-8-sig') if ext=='txt' else '\n'.join(p.text for p in Document(io.BytesIO(response.content)).paragraphs)
            self.assertIn(original,text)
            self.assertNotIn('Yeni çalışma metni.',text)
            self.assertIn('TID_orijinal',response.headers['content-disposition'])

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

    def decide_assumption(self, **links):
        record=deepcopy(self.p['state']['assumption_records'][0])
        record.update(status='accepted',note='İncelenen teknik karar',**links)
        self.apply(self.preview([dict(action='upsert_assumption',id=record['id'],value=record)]))
        return deepcopy(self.p['state']['assumption_records'][0])

    def test_unlinked_decision_does_not_follow_the_whole_project(self):
        self.decide_assumption()
        comp=deepcopy(self.p['state']['architecture']['components'][0]);comp['description']='Yeni teknik görev'
        self.change('upsert_component','A',comp)
        edge=deepcopy(self.p['state']['architecture']['connections'][0]);edge['direction']='bidirectional'
        self.change('upsert_connection','E1',edge)
        self.apply(self.preview([self.source()]))
        r=self.p['state']['assumption_records'][0]
        self.assertEqual(r['status'],'accepted');self.assertFalse(r['stale'])

    def test_connection_decision_does_not_follow_other_endpoint_details_or_interfaces(self):
        self.decide_assumption(connection_ids=['E1'])
        comp=deepcopy(self.p['state']['architecture']['components'][1]);comp['description']='Bağlantıdan bağımsız yeni görev'
        self.change('upsert_component','B',comp)
        edge=deepcopy(self.p['state']['architecture']['connections'][0]);edge.update(id='E2',target='C')
        self.change('upsert_connection','',edge)
        self.assertFalse(self.p['state']['assumption_records'][0]['stale'])

    def test_cosmetic_changes_keep_decision_and_evidence_current(self):
        self.decide_assumption(connection_ids=['E1'])
        comp=deepcopy(self.p['state']['architecture']['components'][0]);comp['name']='Okunaklı ad'
        self.change('upsert_component','A',comp)
        source=self.source('  '+self.p['state']['source_catalog'][0]['text']+'  ')
        source['value'].update(section='Yeni bölüm başlığı',original_id='SYS-1')
        self.apply(self.preview([source]))
        self.change('layout',value={'A':dict(x=20,y=40)})
        restarted=ReviewStore(self.store.path).get(self.p['id'])
        self.assertFalse(restarted['state']['assumption_records'][0]['stale'])
        self.assertEqual(restarted['state']['stale_links'],{})

    def test_source_only_decision_tracks_source_text_not_supported_objects(self):
        self.decide_assumption(source_ids=['G-01'])
        edge=deepcopy(self.p['state']['architecture']['connections'][0]);edge['direction']='bidirectional'
        self.change('upsert_connection','E1',edge)
        self.assertFalse(self.p['state']['assumption_records'][0]['stale'])
        self.apply(self.preview([self.source()]))
        self.assertTrue(self.p['state']['assumption_records'][0]['stale'])

    def test_component_decision_tracks_its_incident_interfaces(self):
        self.decide_assumption(component_ids=['A'])
        edge=deepcopy(self.p['state']['architecture']['connections'][0]);edge['direction']='bidirectional'
        self.change('upsert_connection','E1',edge)
        self.assertTrue(self.p['state']['assumption_records'][0]['stale'])

    def test_explicit_project_scope_tracks_technical_changes_but_not_names(self):
        self.decide_assumption(scope='project')
        comp=deepcopy(self.p['state']['architecture']['components'][-1]);comp['name']='Yeni ad'
        self.change('upsert_component','C',comp)
        self.assertFalse(self.p['state']['assumption_records'][0]['stale'])
        comp['description']='Yeni teknik işlev'
        self.change('upsert_component','C',comp)
        self.assertTrue(self.p['state']['assumption_records'][0]['stale'])

    def test_direction_change_preserves_decision_explains_impact_and_undo_redo(self):
        record=self.decide_assumption(connection_ids=['E1'])
        edge=deepcopy(self.p['state']['architecture']['connections'][0]);edge['direction']='bidirectional'
        proposal=self.preview([dict(action='upsert_connection',id='E1',value=edge)])
        self.assertEqual(proposal['stale_assumptions'],[record['id']])
        self.assertIn('tek yönlü → çift yönlü',proposal['stale_assumption_details'][0]['reason'])
        self.apply(proposal)
        r=self.p['state']['assumption_records'][0]
        self.assertTrue(r['stale']);self.assertEqual(r['status'],'accepted');self.assertEqual(r['note'],record['note'])
        self.change('undo');self.assertFalse(self.p['state']['assumption_records'][0]['stale'])
        self.change('redo');self.assertTrue(self.p['state']['assumption_records'][0]['stale'])

    def test_endpoint_deletion_reopens_linked_decision(self):
        self.decide_assumption(connection_ids=['E1'])
        self.change('delete_component','B',{'cascade':True})
        self.assertTrue(self.p['state']['assumption_records'][0]['stale'])
        self.assertTrue(self.p['state']['assumption_records'][0]['stale_reason'])

    def test_existing_stale_decision_is_not_reported_again_in_unrelated_preview(self):
        self.decide_assumption(connection_ids=['E1'])
        edge=deepcopy(self.p['state']['architecture']['connections'][0]);edge['direction']='bidirectional'
        self.change('upsert_connection','E1',edge)
        comp=deepcopy(self.p['state']['architecture']['components'][-1]);comp['description']='Yeni bağımsız görev'
        proposal=self.preview([dict(action='upsert_component',id='C',value=comp)])
        self.assertEqual(proposal['stale_assumptions'],[])
        self.assertTrue(self.p['state']['assumption_records'][0]['stale'])

    def test_order_and_evidence_whitespace_do_not_reopen(self):
        self.decide_assumption(scope='project')
        state=deepcopy(self.p['state']);state['architecture']['components'].reverse()
        state['architecture']['connections'][0]['evidence'][0]['quote']='  '+state['architecture']['connections'][0]['evidence'][0]['quote']+'  '
        self.assertFalse(upgrade_state(state,self.p['original'])['assumption_records'][0]['stale'])

    def simulate_old_revision(self, baseline, changed):
        # Reproduce snapshots written by the previous release, including a
        # false stale flag. Production migration must read, never rewrite them.
        with self.store.db() as db:
            seq=self.p['current_revision']
            db.execute('UPDATE revisions SET state=? WHERE project_id=? AND seq=?',(json.dumps(baseline),self.p['id'],seq))
            db.execute('INSERT INTO revisions VALUES(?,?,?,?)',(self.p['id'],seq+1,seq,json.dumps(changed)))
            db.execute('UPDATE projects SET current=?,version=version+1 WHERE id=?',(seq+1,self.p['id']))
        self.p=self.store.get(self.p['id'])
        with self.store.db() as db:
            raw=json.loads(db.execute('SELECT state FROM revisions WHERE project_id=? AND seq=?',(self.p['id'],seq+1)).fetchone()['state'])
            self.assertEqual(raw,changed)

    def legacy_decision_states(self, **links):
        self.decide_assumption(**links)
        baseline=deepcopy(self.p['state']);r=baseline['assumption_records'][0]
        r['basis']=legacy_assumption_basis(baseline,r)
        for key in ('basis_version','basis_snapshot','scope','stale_reason'):r.pop(key,None)
        changed=deepcopy(baseline);changed['assumption_records'][0]['stale']=True
        return baseline,changed

    def test_old_unlinked_false_stale_decision_is_recovered_read_only(self):
        baseline,changed=self.legacy_decision_states()
        changed['architecture']['connections'][0]['direction']='bidirectional'
        self.simulate_old_revision(baseline,changed)
        self.assertFalse(self.p['state']['assumption_records'][0]['stale'])
        self.assertEqual(self.p['state']['assumption_records'][0]['basis_version'],2)

    def test_old_linked_cosmetic_change_is_recovered_but_technical_change_is_preserved(self):
        baseline,changed=self.legacy_decision_states(connection_ids=['E1'])
        changed['architecture']['components'][0]['name']='Yeni ad'
        self.simulate_old_revision(baseline,changed)
        self.assertFalse(self.p['state']['assumption_records'][0]['stale'])
        technical=deepcopy(changed);technical['architecture']['connections'][0]['direction']='bidirectional'
        self.simulate_old_revision(changed,technical)
        self.assertTrue(self.p['state']['assumption_records'][0]['stale'])
        self.assertIn('yönü',self.p['state']['assumption_records'][0]['stale_reason'])

    def test_old_snapshot_without_baseline_does_not_silently_clear_real_change(self):
        baseline,changed=self.legacy_decision_states(connection_ids=['E1'])
        changed['architecture']['connections'][0]['direction']='bidirectional'
        restored=self.store.restore_snapshot({**self.p,'state':changed})
        self.assertTrue(restored['state']['assumption_records'][0]['stale'])
        self.assertIn('Eski kararın teknik dayanağı bulunamadı',restored['state']['assumption_records'][0]['stale_reason'])

    def test_old_finding_decision_migrates_cosmetic_change_and_preserves_real_change(self):
        edge=self.p['state']['architecture']['connections'][0]
        self.change('add_finding',value=dict(id='F1',type='ambiguous',severity='medium',title='Yönü inceleyin',
            description='Arayüzün yönü belirsiz.',evidence=edge['evidence'],related_connection_ids=['E1']))
        topic=self.p['topics'][0];key='topic:'+topic['id']
        self.change('set_topic_decision',topic['id'],{'status':'accepted'})
        baseline=deepcopy(self.p['state']);d=baseline['decisions'][key]
        d.update(fingerprint_version=2,fingerprint=self.p['topics'][0]['legacy_fingerprint'])
        d.pop('dependency_snapshot',None)
        changed=deepcopy(baseline);changed['architecture']['components'][0]['name']='Yeni ad'
        changed['source_catalog'][0]['section']='Yeni bölüm başlığı';changed['decisions'][key]['stale']=True
        self.simulate_old_revision(baseline,changed)
        self.assertEqual(self.p['topics'][0]['status'],'completed')
        self.assertFalse(self.p['state']['decisions'][key]['stale'])
        technical=deepcopy(changed);technical['architecture']['connections'][0]['direction']='bidirectional'
        self.simulate_old_revision(changed,technical)
        self.assertEqual(self.p['topics'][0]['status'],'reopened')
        self.assertIn('yönü',self.p['topics'][0]['decision']['stale_reason'])

    def test_change_package_compares_final_state_not_intermediate_steps(self):
        self.decide_assumption(connection_ids=['E1'])
        edge=deepcopy(self.p['state']['architecture']['connections'][0]);changed=deepcopy(edge);changed['direction']='bidirectional'
        proposal=self.preview([dict(action='upsert_connection',id='E1',value=changed),dict(action='upsert_connection',id='E1',value=edge)])
        self.assertEqual(proposal['stale_assumptions'],[])
        self.apply(proposal)
        self.assertFalse(self.p['state']['assumption_records'][0]['stale'])

    def test_pre_workspace_assumption_text_change_keeps_its_previous_decision_stale(self):
        record=self.decide_assumption()
        baseline=deepcopy(self.p['state']);baseline.pop('assumption_records')
        baseline['decisions']['assumption:0']=dict(status='approved',note=record['note'],actor=record['actor'],at=record['at'],stale=False)
        changed=deepcopy(baseline);changed['architecture']['assumptions'][0]='Yeni bir teknik varsayım.'
        changed['decisions']['assumption:0']['stale']=True
        self.simulate_old_revision(baseline,changed)
        r=self.p['state']['assumption_records'][0]
        self.assertEqual(r['status'],'accepted');self.assertTrue(r['stale'])
        self.assertIn('Varsayımın metni',r['stale_reason'])
        restored=self.store.restore_snapshot({**self.p,'state':changed})
        self.assertTrue(restored['state']['assumption_records'][0]['stale'])

    def test_rejection_alone_does_not_delete_objects(self):
        arch=deepcopy(self.p['state']['architecture']);record=deepcopy(self.p['state']['assumption_records'][0])
        record.update(status='rejected',note='Doğru yön henüz bilinmiyor')
        self.apply(self.preview([dict(action='upsert_assumption',id=record['id'],value=record)]))
        self.assertEqual(self.p['state']['architecture'],arch)
        self.assertEqual(self.p['state']['assumption_records'][0]['status'],'rejected')

    def test_explicit_decision_survives_api_apply_restart_export_and_undo_redo(self):
        for status in ('accepted','rejected'):
            with self.subTest(status=status):
                previous_status=self.p['state']['assumption_records'][0]['status']
                record=deepcopy(self.p['state']['assumption_records'][0])
                record.update(status=status,note='Açıkça seçilen mühendis kararı',connection_ids=['E1'])
                response=self.client.post(self.url+'/preview',headers=self.headers,json=dict(
                    version=self.p['version'],actor='Mühendis',reason='Kararı önizle',
                    commands=[dict(action='upsert_assumption',id=record['id'],value=record)]))
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(self.client.get(self.url).json()['state']['assumption_records'][0]['status'],previous_status)
                response=self.client.post(self.url+'/changes',headers=self.headers,json=dict(
                    version=self.p['version'],action='apply_change_set',value={'preview_id':response.json()['id']},actor='Mühendis',reason='Kararı uygula'))
                self.assertEqual(response.status_code,200,response.text)
                self.p=response.json()
                self.assertEqual(self.p['state']['assumption_records'][0]['status'],status)
                self.assertEqual(ReviewStore(self.store.path).get(self.p['id'])['state']['assumption_records'][0]['status'],status)
                with zipfile.ZipFile(io.BytesIO(self.client.get(self.url+'/export').content)) as z:
                    saved=json.loads(z.read('engineering_review.json'))
                self.assertEqual(saved['state']['assumption_records'][0]['status'],status)
                self.change('undo');self.assertEqual(self.p['state']['assumption_records'][0]['status'],previous_status)
                self.change('redo');self.assertEqual(self.p['state']['assumption_records'][0]['status'],status)

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
