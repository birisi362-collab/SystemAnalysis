"""Actionable topics and dependency-based decisions, independent of display order."""
from copy import deepcopy
import hashlib
import json
import re

from .source_relations import source_relations


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source_labels(catalog):
    labels = {}
    for n,s in enumerate(catalog,1):
        location = ', '.join(x.replace('line:', 'Satır ').replace('page:', 'Sayfa ') for x in s.get('locations', []))
        original = s.get('original_id')
        labels[s['requirement_id']] = ' · '.join(x for x in [original, location or f'Kaynak {n}'] if x)
    return labels


def readable(text, labels):
    # Replace only standalone known identifiers; the immutable original stays intact.
    if not text or not labels:
        return text or ''
    pattern = r'(?<![\w-])('+'|'.join(re.escape(x) for x in sorted(labels,key=len,reverse=True))+r')(?![\w-])'
    return re.sub(pattern, lambda m: labels[m[0]], text)


def build_topics(final, issues, decisions):
    a = final.architecture
    objects = {o.id:o for o in a.components+a.connections}
    sources = {s['requirement_id']:s for s in final.source_catalog}
    labels = source_labels(final.source_catalog)
    topics = {}
    def name(oid):
        obj = objects.get(oid)
        if not obj: return 'Kaldırılmış öğe'
        return obj.name if hasattr(obj,'name') else f'{name(obj.source)} → {name(obj.target)}'
    def make(key, kind, title, description, suggestion, ids, source_ids, finding_id=None):
        tid = fingerprint(key)[:20]
        topics.setdefault(tid, dict(id=tid, kind=kind, title=title, description=description,
            suggestion=suggestion, object_ids=sorted(set(ids)), source_ids=sorted(set(source_ids)),
            primary_source_ids=sorted(set(source_ids)), primary_object_ids=sorted(set(ids)),
            finding_id=finding_id, checks=[], priority='normal', dependency_kind=key[0], origin='automatic'))
        return topics[tid]
    for finding in final.analysis.findings:
        ids=finding.related_component_ids+finding.related_connection_ids
        display_labels={**labels,**{oid:name(oid) for oid in objects}}
        topic=make(('finding',finding.id), 'engineering', readable(finding.title,display_labels),
            readable(finding.description,display_labels), readable(finding.recommended_action,display_labels) or 'Kaynak ve mimariyi birlikte değerlendirin.',
            ids,[e.requirement_id for e in finding.evidence],finding.id)
        topic['priority']='high' if finding.severity in ('high','critical') else 'normal'
        topic['origin']='engineering'
    evidence_codes={'MISSING_EVIDENCE','MISSING_QUOTE','QUOTE_NOT_IN_SOURCE','UNKNOWN_EVIDENCE_REF'}
    coverage_codes={'COVERAGE_EVIDENCE_MISMATCH','COVERAGE_WITHOUT_LINKS','COVERAGE_CONTEXT_ONLY','PARTIAL_COVERAGE','UNMAPPED_REQUIREMENT','MISSING_COVERAGE','UNKNOWN_COVERAGE_REQUIREMENT'}
    for issue in issues:
        oid,sid,fid=issue.get('object_id'),issue.get('source_id'),issue.get('finding_id')
        if fid:
            topic=next((t for t in topics.values() if t['finding_id']==fid),None)
        else:
            topic=None
        if not topic:
            family='evidence' if issue['code'] in evidence_codes else 'coverage' if issue['code'] in coverage_codes else 'protocol' if 'PROTOCOL' in issue['code'] else 'integrity'
            anchor=sid if family=='coverage' else oid or sid or issue.get('related_id') or 'architecture'
            title={'evidence':'Doküman dayanağını düzenleyin','coverage':'Kaynağın mimari karşılığını inceleyin','protocol':'Bağlantının arayüzünü inceleyin','integrity':'Kayıt tutarlılığını inceleyin'}[family]
            topic=make((family,anchor),'record' if issue['severity']=='error' else 'review',title,
                issue['explanation'],issue['suggestion'],[oid] if oid else [],[sid] if sid else [])
            if oid: topic['object_ids']=sorted(set(topic['object_ids'])|{oid})
            if sid: topic['source_ids']=sorted(set(topic['source_ids'])|{sid})
        topic['checks'].append(issue)
        if issue['severity']=='error':
            topic['priority']='high'
            if not fid: topic['kind']='record'
    for topic in topics.values():
        # Include linked evidence, coverage, connection endpoints and source objects.
        ids=set(topic['object_ids']); sids=set(topic['source_ids'])
        for oid in list(ids):
            obj=objects.get(oid)
            if obj:
                sids.update(e.requirement_id for e in obj.evidence)
                if hasattr(obj,'source'): ids.update([obj.source,obj.target])
        for sid in list(sids):
            rel=source_relations(a,sid)
            ids.update(rel['evidence_ids']+rel['direct_ids']+rel['contextual_ids'])
        topic['object_ids']=sorted(ids)
        topic['source_ids']=sorted(sids)
        payload=dict(objects={oid:objects[oid].model_dump() if oid in objects else None for oid in sorted(ids)},
            sources={sid:sources.get(sid) for sid in sorted(sids)},
            coverage=[c.model_dump() for c in a.requirement_coverage if c.requirement_id in sids],
            finding=next((f.model_dump() for f in final.analysis.findings if f.id==topic['finding_id']),None),
            checks=sorted((i['key'] for i in topic['checks'])))
        if not ids and not sids and topic['dependency_kind'] in ('finding','integrity'):
            payload['architecture']=a.model_dump()
        topic['fingerprint']=fingerprint(payload)
        topic['context_label']=' · '.join([labels.get(s,s) for s in topic['primary_source_ids']]) or ' · '.join(name(x) for x in topic['primary_object_ids']) or 'Mimari kayıtları'
        decision=deepcopy(decisions.get('topic:'+topic['id']))
        if decision:
            decision['stale']=decision.get('fingerprint')!=topic['fingerprint']
            if decision['stale']: decision['stale_reason']='Bu konunun kaynak, nesne veya kontrol bilgisi değişti. Önceki gerekçeyi yeniden değerlendirin.'
        elif topic['finding_id']:
            decision=deepcopy(decisions.get('finding:'+topic['finding_id']))
        topic['decision']=decision
        topic['status']='reopened' if decision and decision.get('stale') else 'completed' if decision and decision.get('status') in ('resolved','accepted','rejected','merged','approved') else 'open'
        topic['active']=True
    base_fingerprints={tid:t['fingerprint'] for tid,t in topics.items()}
    def merged_fingerprint(tid,seen=None):
        seen=seen or set()
        if tid not in topics or tid in seen: return None
        seen=seen|{tid}
        d=topics[tid]['decision'] or {}
        target=d.get('merged_into')
        return fingerprint([base_fingerprints[tid],merged_fingerprint(target,seen)]) if target else base_fingerprints[tid]
    for topic in topics.values():
        decision=topic['decision']
        if decision and decision.get('merged_into'):
            # Editing a merge target also invalidates the source closure.
            topic['fingerprint']=merged_fingerprint(topic['id'])
            decision['stale']=decision.get('fingerprint')!=topic['fingerprint']
            topic['status']='reopened' if decision['stale'] else 'completed'
            if decision['stale']:
                decision['stale_reason']='Birleştirilen konu veya bu konunun dayanağı değişti; kararı yeniden inceleyin.'
    # Preserve closures after an automatic check disappears; never erase the reason.
    for key,decision in decisions.items():
        if not key.startswith('topic:') or key[6:] in topics or not decision.get('snapshot'):
            continue
        topic=deepcopy(decision['snapshot'])
        topic.update(decision=deepcopy(decision), status='completed', active=False)
        topic['decision'].pop('snapshot',None)
        topic['completion_note']='İlgili otomatik kontrol artık üretilmiyor. Düzeltme veya kapatma gerekçesi korunuyor; bu bir tasarım onayı değildir.'
        topics[topic['id']]=topic
    return sorted(topics.values(), key=lambda t:(t['status']=='completed',t['priority']!='high',t['id']))
