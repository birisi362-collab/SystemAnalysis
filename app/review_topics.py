"""Engineering findings only; unlinked document text never creates work."""
from copy import deepcopy
import re
from .decision_dependencies import fingerprint, dependency_snapshot, dependency_reason, normalized


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
        legacy_fp = fingerprint({'finding': f, 'objects': context, 'sources': [s for s in final.source_catalog if s['requirement_id'] in source_ids]})
        component_ids = set(finding.related_component_ids)
        connection_ids = set(finding.related_connection_ids)
        for change in finding.proposed_changes:
            (component_ids if change.kind == 'component' else connection_ids).add(change.id)
            if change.kind == 'component' and change.action == 'remove':
                connection_ids.update(e['id'] for e in architecture['connections'] if change.id in (e['source'], e['target']))
        snapshot = dependency_snapshot({'architecture':architecture, 'source_catalog':final.source_catalog}, source_ids, component_ids, connection_ids)
        content = normalized({k:v for k,v in f.items() if k not in ('id', 'title', 'proposed_changes')})
        content['proposed_changes'] = [normalized(c) for c in f['proposed_changes']]
        snapshot['finding'] = content
        decision = deepcopy(decisions.get('topic:'+tid) or decisions.get('finding:'+finding.id))
        topics.append(dict(id=tid, finding_id=finding.id, kind='engineering', origin='engineering', active=True,
            title=readable(finding.title, display), description=readable(finding.description, display),
            suggestion=readable(finding.recommended_action, display), object_ids=list(context),
            primary_object_ids=finding.related_component_ids+finding.related_connection_ids,
            source_ids=source_ids, primary_source_ids=source_ids, checks=[], dependency_kind='finding',
            context_label=' · '.join(labels.get(s, s) for s in source_ids), fingerprint=fingerprint(snapshot),
            dependency_snapshot=snapshot, legacy_fingerprint=legacy_fp,
            priority='high' if finding.severity in ('high','critical') else 'normal', decision=decision,
            status='open'))
    by_id = {t['id']: t for t in topics}
    def merged_basis(tid, seen, legacy=False):
        if tid not in by_id or tid in seen: return None
        t = by_id[tid]; target = (t['decision'] or {}).get('merged_into')
        if legacy:
            return fingerprint([t['legacy_fingerprint'], merged_basis(target, seen | {tid}, True)]) if target else t['legacy_fingerprint']
        return {**t['dependency_snapshot'], 'merged':merged_basis(target, seen | {tid})} if target else t['dependency_snapshot']
    merged = {t['id']: merged_basis(t['id'], set()) for t in topics}
    legacy = {t['id']: merged_basis(t['id'], set(), True) for t in topics}
    for t in topics:
        t['dependency_snapshot'] = merged[t['id']]
        t['fingerprint'] = fingerprint(t['dependency_snapshot'])
        t['legacy_fingerprint'] = legacy[t['id']]
        d = t['decision']
        if d:
            if d.get('fingerprint_version') == 3 and d.get('dependency_snapshot') is not None:
                d['stale'] = d['dependency_snapshot'] != t['dependency_snapshot']
                d['stale_reason'] = dependency_reason(d['dependency_snapshot'], t['dependency_snapshot'],
                    {'architecture':architecture, 'source_catalog':final.source_catalog}) if d['stale'] else ''
            elif d.get('fingerprint_version') == 2:
                d['stale'] = bool(d.get('stale')) or d.get('fingerprint') != t['legacy_fingerprint']
            if d.get('stale') and not d.get('stale_reason'):
                d['stale_reason'] = 'Bu konuyla ilgili teknik bilgi değişti. Önceki kararınızı yeniden değerlendirebilirsiniz.'
            t['status'] = 'reopened' if d.get('stale') else 'completed' if d.get('status') in ('resolved','accepted','rejected','merged','approved','applied') else 'open'
    return sorted(topics, key=lambda t: (t['status']=='completed', t['priority']!='high', t['id']))
