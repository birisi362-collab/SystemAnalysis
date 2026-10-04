import copy
import json
from pathlib import Path
import tempfile
import unittest

from app.models import FinalModel
from app.review_store import ReviewStore, enrich_issues
from app.source_relations import source_relations
from app.validator_audit import baseline
from app.review_topics import source_labels, readable


class TopicWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        data=baseline()
        data['architecture']['components'].append(dict(id='C',name='Bağımsız sistem',category='system',evidence=[]))
        data['analysis']['findings']=[dict(id='F1',severity='medium',type='ambiguous',title='Yönü inceleyin',description='G-01 yönünü kontrol edin.',evidence=copy.deepcopy(data['architecture']['connections'][0]['evidence']),related_component_ids=['A'],related_connection_ids=['E1'])]
        self.path=self.root/'analysis_result.json'
        self.path.write_text(json.dumps(data),encoding='utf-8')
        self.original=self.path.read_bytes()
        self.store=ReviewStore(self.root/'reviews.sqlite3')
        self.p=self.store.import_run(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def change(self,action,id='',value=None,reason='Gerekçeli mühendis kararı'):
        self.p=self.store.mutate(self.p['id'],dict(action=action,id=id,value=value or {},reason=reason,actor='Mühendis',version=self.p['version']))
        return self.p

    def finding_topic(self):
        return next(t for t in self.p['topics'] if t['finding_id']=='F1')

    def close(self):
        self.change('set_topic_decision',self.finding_topic()['id'],{'status':'accepted'})

    def test_closure_persists_restart_and_keeps_original(self):
        self.close()
        self.assertEqual(self.finding_topic()['status'],'completed')
        self.assertIn('Gerekçeli',self.finding_topic()['decision']['note'])
        self.p=ReviewStore(self.root/'reviews.sqlite3').get(self.p['id'])
        self.assertEqual(self.finding_topic()['status'],'completed')
        self.assertEqual(self.path.read_bytes(),self.original)

    def test_relevant_edit_reopens_and_preserves_previous_reason(self):
        self.close()
        c=copy.deepcopy(self.p['state']['architecture']['components'][0]);c['name']='Yeni A'
        self.change('upsert_component','A',c)
        self.assertEqual(self.finding_topic()['status'],'reopened')
        self.assertIn('Gerekçeli',self.finding_topic()['decision']['note'])
        self.change('set_topic_decision',self.finding_topic()['id'],{'status':'resolved'},'Yeni adı kontrol ettim')
        self.assertEqual(self.finding_topic()['status'],'completed')

    def test_waiting_persists_without_completing_topic(self):
        self.change('set_topic_decision',self.finding_topic()['id'],{'status':'waiting'},'Arayüz belgesini bekliyoruz')
        self.p=ReviewStore(self.root/'reviews.sqlite3').get(self.p['id'])
        self.assertEqual(self.finding_topic()['status'],'open')
        self.assertEqual(self.finding_topic()['decision']['status'],'waiting')
        self.assertEqual(self.finding_topic()['decision']['note'],'Arayüz belgesini bekliyoruz')
        self.assertEqual(self.path.read_bytes(),self.original)

    def test_relevant_change_reopens_waiting_topic(self):
        self.change('set_topic_decision',self.finding_topic()['id'],{'status':'waiting'},'Arayüz belgesini bekliyoruz')
        edge=copy.deepcopy(self.p['state']['architecture']['connections'][0]);edge['description']='Yeni arayüz bilgisi'
        self.change('upsert_connection',edge['id'],edge)
        self.assertEqual(self.finding_topic()['status'],'reopened')
        self.assertEqual(self.finding_topic()['decision']['note'],'Arayüz belgesini bekliyoruz')

    def test_unrelated_edit_and_layout_do_not_reopen(self):
        self.close()
        c=copy.deepcopy(self.p['state']['architecture']['components'][-1]);c['name']='Bağımsız yeni ad'
        self.change('upsert_component','C',c)
        self.assertEqual(self.finding_topic()['status'],'completed')
        self.change('layout',value={'A':{'x':50,'y':20}})
        self.assertEqual(self.finding_topic()['status'],'completed')

    def test_undo_redo_restore_closure(self):
        self.close()
        self.change('undo');self.assertEqual(self.finding_topic()['status'],'open')
        self.change('redo');self.assertEqual(self.finding_topic()['status'],'completed')

    def test_blank_reason_and_unknown_topic_rejected(self):
        with self.assertRaises(ValueError):self.change('set_topic_decision',self.finding_topic()['id'],{'status':'resolved'},' ')
        with self.assertRaises(ValueError):self.change('set_topic_decision','ghost',{'status':'resolved'})

    def test_optional_sources_do_not_create_engineering_tasks(self):
        self.assertEqual(self.p['issues'],[])
        self.assertEqual([t['finding_id'] for t in self.p['topics']],['F1'])

    def test_adding_and_removing_unrelated_source_keeps_closed_finding(self):
        self.close()
        c=copy.deepcopy(self.p['state']['architecture']['components'][-1]);c['evidence']=copy.deepcopy(self.p['state']['architecture']['components'][0]['evidence'])
        self.change('upsert_component','C',c)
        self.assertEqual(self.finding_topic()['status'],'completed')
        c['evidence']=[];c['description']='Yeni kanıtsız durum'
        self.change('upsert_component','C',c)
        self.assertEqual(self.finding_topic()['status'],'completed')
        self.assertEqual(len(self.p['topics']),1)

    def test_source_edit_has_history_without_creating_a_task(self):
        c=copy.deepcopy(self.p['state']['architecture']['components'][-1]);c['evidence']=copy.deepcopy(self.p['state']['architecture']['components'][0]['evidence'])
        self.change('upsert_component','C',c,'Doğru kaynak alıntısını ekledim')
        self.assertEqual(len(self.p['topics']),1)
        self.assertEqual(self.p['history'][0]['reason'],'Doğru kaynak alıntısını ekledim')

    def test_topic_ids_do_not_depend_on_list_order(self):
        before={t['id'] for t in self.p['topics']}
        self.change('layout',value={'A':{'x':10,'y':20}})
        self.assertEqual(before,{t['id'] for t in self.p['topics']})

    def test_legacy_coverage_does_not_create_tasks_or_reopen_findings(self):
        self.close()
        cov=dict(requirement_id='G-01',status='covered',related_component_ids=[],related_connection_ids=[],contextual_component_ids=['C'])
        self.change('set_coverage',value=cov)
        self.assertNotIn('source_relations',self.p)
        self.assertEqual(self.finding_topic()['status'],'completed')
        self.assertEqual(self.p['issues'],[])

    def test_duplicate_findings_merge_and_target_edit_reopens(self):
        f=copy.deepcopy(self.p['state']['analysis']['findings'][0]);f['id']='F2'
        self.change('add_finding',value=f)
        t1=self.finding_topic();t2=next(t for t in self.p['topics'] if t['finding_id']=='F2')
        self.change('set_topic_decision',t1['id'],{'status':'merged','merged_into':t2['id']})
        self.assertEqual(self.finding_topic()['status'],'completed')
        with self.assertRaises(ValueError):self.change('set_topic_decision',t2['id'],{'status':'merged','merged_into':t1['id']})
        f['title']='Düzeltilmiş konu'
        self.change('edit_finding','F2',f)
        self.assertEqual(self.finding_topic()['status'],'reopened')


class RelationRulesTests(unittest.TestCase):
    def test_legacy_endpoint_links_are_context_but_unrelated_links_stay_flagged(self):
        d=baseline()
        d['architecture']['components'][0]['evidence']=[]
        f=FinalModel.model_validate(d)
        self.assertIn('A',source_relations(f.architecture,'G-01')['inferred_ids'])
        self.assertNotIn('COVERAGE_EVIDENCE_MISMATCH',{i['code'] for i in enrich_issues(f)})
        d['architecture']['components'].append(dict(id='C',name='İlgisiz',evidence=[]))
        d['architecture']['requirement_coverage'][0]['related_component_ids'].append('C')
        self.assertTrue(any(i['code']=='COVERAGE_EVIDENCE_MISMATCH' and i['object_id']=='C' for i in enrich_issues(FinalModel.model_validate(d))))

    def test_legacy_coverage_checks_never_become_workspace_tasks(self):
        d=baseline()
        d['architecture']['components'].append(dict(id='C',name='C',category='system',evidence=[]))
        d['architecture']['connections']=[]
        for c in d['architecture']['components']:c['evidence']=[]
        d['architecture']['requirement_coverage'][0].update(related_component_ids=['A','B','C'],related_connection_ids=[])
        f=FinalModel.model_validate(d)
        from app.review_topics import build_topics
        self.assertEqual(build_topics(f,enrich_issues(f),{}),[])

    def test_readable_label_retains_explicit_number_and_location(self):
        labels=source_labels([dict(requirement_id='R-abc',original_id='REQ-12',locations=['page:3'])])
        self.assertEqual(labels['R-abc'],'REQ-12 · Sayfa 3')
        self.assertEqual(readable('R-abc gereği',labels),'REQ-12 · Sayfa 3 gereği')
