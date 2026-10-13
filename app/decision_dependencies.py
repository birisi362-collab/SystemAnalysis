"""Technical decision dependencies; presentation and proposal guards stay separate."""
import hashlib
import json
import unicodedata


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def normalized(value):
    if isinstance(value, str):
        return ' '.join(unicodedata.normalize('NFKC', value).split())
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items()}
    if isinstance(value, list):
        return sorted((normalized(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    return value


def technical_object(obj):
    if obj is None:
        return None
    # Labels/descriptions can carry signals, rates and technical obligations.
    # Only the component display name is excluded; identity is the stable ID.
    fields = ('source', 'target', 'direction', 'type', 'protocol', 'label', 'description', 'evidence') \
        if 'source' in obj else ('category', 'description', 'evidence')
    return {key: normalized(obj.get(key) or ([] if key == 'evidence' else '')) for key in fields}


def dependency_snapshot(state, source_ids=(), component_ids=(), connection_ids=(), *, incident=False, project=False):
    arch = state['architecture']
    sources = {s['requirement_id']: s for s in state.get('source_catalog', [])}
    components = {o['id']: o for o in arch['components']}
    connections = {o['id']: o for o in arch['connections']}
    cids, eids, sids = set(component_ids), set(connection_ids), set(source_ids)
    if project:
        cids, eids, sids = set(components), set(connections), set(sources)
    elif incident:
        eids.update(e['id'] for e in connections.values() if e['source'] in cids or e['target'] in cids)
    endpoints = set()
    for eid in eids:
        edge = connections.get(eid)
        if edge:
            endpoints.update((edge['source'], edge['target']))
    # A linked connection depends on endpoint existence, not all of the other
    # endpoint details or on its neighbours' connections and evidence.
    for obj in [components.get(cid) for cid in cids] + [connections.get(eid) for eid in eids]:
        sids.update(e['requirement_id'] for e in (obj or {}).get('evidence', []))
    return dict(
        sources={sid: normalized(sources[sid]['text']) if sid in sources else None for sid in sorted(sids)},
        components={cid: technical_object(components.get(cid)) for cid in sorted(cids)},
        connections={eid: technical_object(connections.get(eid)) for eid in sorted(eids)},
        endpoints={cid: cid in components for cid in sorted(endpoints - cids)},
    )


FIELD_NAMES = {'protocol': 'protokolü', 'direction': 'yönü', 'source': 'başlangıcı', 'target': 'hedefi',
               'type': 'türü', 'category': 'sınıfı', 'description': 'teknik açıklaması',
               'label': 'etiketi', 'evidence': 'kaynak dayanağı'}
VALUE_NAMES = {'unidirectional': 'tek yönlü', 'bidirectional': 'çift yönlü'}


def dependency_reason(before, after, state):
    """Explain only the changed dependencies, using readable object names."""
    reasons = []
    objects = {o['id']: o for o in state['architecture']['components'] + state['architecture']['connections']}
    def name(oid):
        obj = objects.get(oid, {})
        if 'source' in obj:
            return f"{objects.get(obj['source'], {}).get('name', 'Kaldırılmış öğe')} → {objects.get(obj['target'], {}).get('name', 'Kaldırılmış öğe')} bağlantısının"
        return f"{obj.get('name', 'İlgili bileşen')} bileşeninin"
    for kind in ('sources', 'components', 'connections', 'endpoints'):
        old, new = before.get(kind, {}), after.get(kind, {})
        for oid in sorted(old.keys() | new.keys()):
            a, b = old.get(oid), new.get(oid)
            if a == b:
                continue
            if kind == 'sources':
                label = next((s.get('original_id') for s in state.get('source_catalog', []) if s['requirement_id'] == oid), None)
                reasons.append(f"{label or 'İlgili TİD maddesi'} {'kaldırıldı veya dayanak ilişkisi değişti' if b is None else 'metni veya dayanak ilişkisi değişti'}.")
            elif kind == 'endpoints':
                reasons.append('İlgili bağlantının uç bileşeni kaldırıldı veya değişti.')
            elif not isinstance(a, dict) or not isinstance(b, dict):
                reasons.append(f"{name(oid)} varlığı veya karar kapsamındaki ilişkisi değişti.")
            else:
                for field in sorted(a.keys() | b.keys()):
                    if a.get(field) == b.get(field):
                        continue
                    detail = ''
                    if field in ('protocol', 'direction'):
                        start, end = a.get(field), b.get(field)
                        detail = f" ({VALUE_NAMES.get(start, start) or 'belirtilmemiş'} → {VALUE_NAMES.get(end, end) or 'belirtilmemiş'})"
                    reasons.append(f"{name(oid)} {FIELD_NAMES.get(field, field)} değişti{detail}.")
    if before.get('assumption') != after.get('assumption'):
        reasons.append('Varsayımın metni veya teknik gerekçesi değişti.')
    if before.get('finding') != after.get('finding'):
        reasons.append('İlgili bulgunun teknik içeriği veya önerisi değişti.')
    if before.get('merged') != after.get('merged'):
        reasons.append('Birleştirilen konunun teknik dayanağı değişti.')
    return ' '.join(dict.fromkeys(reasons)) or 'Kararın ilgili teknik dayanağı değişti.'
