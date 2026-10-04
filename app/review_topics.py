"""Engineering findings only; unlinked document text never creates work."""
from copy import deepcopy
import hashlib
import json
import re


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source_labels(catalog):
    labels = {}
    for n, source in enumerate(catalog, 1):
        location = ', '.join(x.replace('line:', 'Satır ').replace('page:', 'Sayfa ').replace('paragraph:', 'Paragraf ').replace('table:', 'Tablo ').replace('row:', 'Satır ').replace('/', ' · ') for x in source.get('locations', []))
        labels[source['requirement_id']] = ' · '.join(x for x in [source.get('original_id'), location or f'Kaynak {n}'] if x)
    return labels


def readable(text, labels):
    if not text or not labels:
        return text or ''
    pattern = r'(?<![\w-])('+'|'.join(re.escape(x) for x in sorted(labels,key=len,reverse=True))+r')(?![\w-])'
    return re.sub(pattern, lambda m: labels[m[0]], text)


def proposal_context(architecture, finding):
    objects = {o['id']: o for o in architecture['components'] + architecture['connections']}
    ids = set(finding.get('related_component_ids', []) + finding.get('related_connection_ids', []))
    for change in finding.get('proposed_changes', []):
        ids.add(change['id'])
        if change['kind'] == 'connection':
            ids.update(change.get('value', {}).get(k) for k in ('source', 'target'))
        if change['kind'] == 'component' and change['action'] == 'remove':
            ids.update(e['id'] for e in architecture['connections'] if change['id'] in (e['source'], e['target']))
    for oid in list(ids):
        obj = objects.get(oid, {}) or {}
        if 'source' in obj:
            ids.update([obj['source'], obj['target']])
    return {oid: objects.get(oid) for oid in sorted(x for x in ids if x)}


def build_topics(final, issues, decisions):
    # Compatibility argument: automatic checks no longer create engineering tasks.
    architecture = final.architecture.model_dump()
    objects = {o['id']: o for o in architecture['components'] + architecture['connections']}
    labels = source_labels(final.source_catalog)
    def name(oid):
        obj = objects.get(oid, {})
        return obj.get('name') or (f"{objects.get(obj.get('source'), {}).get('name', 'Kaldırılmış öğe')} → {objects.get(obj.get('target'), {}).get('name', 'Kaldırılmış öğe')}" if 'source' in obj else 'Kaldırılmış öğe')
    display = {**labels, **{oid: name(oid) for oid in objects}}
    topics = []
    for finding in final.analysis.findings:
        f = finding.model_dump()
        tid = fingerprint(('finding', finding.id))[:20]
        context = proposal_context(architecture, f)
        source_ids = sorted({e.requirement_id for e in finding.evidence})
        fp = fingerprint({'finding': f, 'objects': context, 'sources': [s for s in final.source_catalog if s['requirement_id'] in source_ids]})
        decision = deepcopy(decisions.get('topic:'+tid) or decisions.get('finding:'+finding.id))
        if decision:
            decision['stale'] = bool(decision.get('stale')) or (decision.get('fingerprint_version') == 2 and decision.get('fingerprint') != fp)
            if decision['stale']:
                decision['stale_reason'] = 'Bu konuyla ilgili bilgi değişti. Önceki kararınızı yeniden değerlendirebilirsiniz.'
        topics.append(dict(id=tid, finding_id=finding.id, kind='engineering', origin='engineering', active=True,
            title=readable(finding.title, display), description=readable(finding.description, display),
            suggestion=readable(finding.recommended_action, display), object_ids=list(context),
            primary_object_ids=finding.related_component_ids+finding.related_connection_ids,
            source_ids=source_ids, primary_source_ids=source_ids, checks=[], dependency_kind='finding',
            context_label=' · '.join(labels.get(s, s) for s in source_ids), fingerprint=fp,
            priority='high' if finding.severity in ('high','critical') else 'normal', decision=decision,
            status='reopened' if decision and decision.get('stale') else 'completed' if decision and decision.get('status') in ('resolved','accepted','rejected','merged','approved','applied') else 'open'))
    by_id = {t['id']: t for t in topics}
    def merged_fp(tid, seen):
        if tid not in by_id or tid in seen: return None
        t = by_id[tid]; target = (t['decision'] or {}).get('merged_into')
        return fingerprint([t['fingerprint'], merged_fp(target, seen | {tid})]) if target else t['fingerprint']
    merged = {t['id']: merged_fp(t['id'], set()) for t in topics}
    for t in topics:
        d = t['decision']
        if d and d.get('merged_into'):
            t['fingerprint'] = merged[t['id']]
            if d.get('fingerprint_version') == 2:
                d['stale'] = d.get('fingerprint') != t['fingerprint']
                t['status'] = 'reopened' if d['stale'] else 'completed'
    return sorted(topics, key=lambda t: (t['status']=='completed', t['priority']!='high', t['id']))
