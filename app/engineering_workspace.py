"""Versioned document and assumption records, independent of model transport."""
from copy import deepcopy
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from .review_topics import fingerprint


class SourceEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requirement_id: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=50000)
    section: str | None = None
    original_id: str | None = None


class SourceRecord(SourceEdit):
    locations: list[str] = Field(default_factory=list)


class AssumptionRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=10000)
    rationale: str = ''
    source_ids: list[str] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list)
    connection_ids: list[str] = Field(default_factory=list)
    status: Literal['pending', 'accepted', 'rejected', 'waiting'] = 'pending'
    note: str = ''
    alternative: str = ''
    actor: str = ''
    at: str = ''
    basis: str | None = None
    stale: bool = False


def upgrade_state(state, original):
    """Lazy, deterministic migration: opening an old project does not write a revision."""
    state = deepcopy(state)
    state.setdefault('source_catalog', deepcopy(original['source_catalog']))
    for source in state['source_catalog']:
        SourceRecord.model_validate(source)
    if len({s['requirement_id'] for s in state['source_catalog']}) != len(state['source_catalog']):
        raise ValueError('TİD kayıtlarının kimlikleri benzersiz olmalı.')
    state.setdefault('document_revision', 0)
    state.setdefault('retired_sources', [])
    state.setdefault('stale_links', {})
    if 'assumption_records' not in state:
        state['assumption_records'] = []
        for i, text in enumerate(state['architecture'].get('assumptions', [])):
            old = state.get('decisions', {}).get('assumption:'+str(i), {})
            record = AssumptionRecord(
                id='ASM-'+uuid.uuid5(uuid.NAMESPACE_URL, str(i)+':'+text).hex[:12], text=text,
                status={'approved':'accepted', 'rejected':'rejected'}.get(old.get('status'), 'pending'),
                note=old.get('note', ''), actor=old.get('actor', ''), at=old.get('at', ''),
                stale=old.get('stale', False),
            ).model_dump()
            record['basis'] = assumption_basis(state, record)
            state['assumption_records'].append(record)
    for record in state['assumption_records']:
        AssumptionRecord.model_validate(record)
        if record['status'] != 'pending' and record.get('basis') != assumption_basis(state, record):
            record['stale'] = True
    return state


def current_document(original, state):
    return {**original, 'source_catalog': state.get('source_catalog', original['source_catalog'])}


def assumption_basis(state, record):
    arch = state['architecture']
    linked = any(record.get(k) for k in ('source_ids', 'component_ids', 'connection_ids'))
    sources = state.get('source_catalog', [])
    component_ids = set(record.get('component_ids', []))
    connections = [o for o in arch['connections'] if not linked or o['id'] in record.get('connection_ids', [])
                   or o['source'] in component_ids or o['target'] in component_ids]
    for connection in connections:
        component_ids.update([connection['source'], connection['target']])
    components = [o for o in arch['components'] if not linked or o['id'] in component_ids]
    source_ids = set(record.get('source_ids', []))
    source_ids.update(e['requirement_id'] for o in components+connections for e in o.get('evidence', []))
    return fingerprint({
        'text': record['text'], 'rationale': record.get('rationale', ''),
        'sources': [s for s in sources if not linked or s['requirement_id'] in source_ids],
        'components': components,
        'connections': connections,
    })


def engineering_context(state):
    return {'assumptions': state.get('assumption_records', []),
            'decisions': state.get('decisions', {}), 'provenance': state.get('provenance', {}),
            'stale_links': state.get('stale_links', {}), 'document_revision': state.get('document_revision', 0)}


def workspace_fingerprint(state):
    return fingerprint({'architecture': state['architecture'], 'sources': state.get('source_catalog', []),
                        'context': engineering_context(state)})


def state_diff(before, after):
    result = []
    groups = [('component', before['architecture']['components'], after['architecture']['components'], 'id'),
              ('connection', before['architecture']['connections'], after['architecture']['connections'], 'id'),
              ('requirement', before.get('source_catalog', []), after.get('source_catalog', []), 'requirement_id'),
              ('assumption', before.get('assumption_records', []), after.get('assumption_records', []), 'id')]
    for kind, a, b, key in groups:
        old = {x[key]: x for x in a}; new = {x[key]: x for x in b}
        for oid in sorted(old.keys() | new.keys()):
            if old.get(oid) != new.get(oid):
                result.append(dict(kind=kind, id=oid, before=old.get(oid), after=new.get(oid)))
    for key in sorted(before.get('decisions', {}).keys() | after.get('decisions', {}).keys()):
        a = before.get('decisions', {}).get(key); b = after.get('decisions', {}).get(key)
        if a != b:
            result.append(dict(kind='decision', id=key, before=a, after=b))
    return result


def impact_summary(before, after):
    changes = state_diff(before, after)
    source_ids = {c['id'] for c in changes if c['kind'] == 'requirement'}
    for change in changes:
        if change['kind'] in ('component', 'connection'):
            for obj in (change['before'], change['after']):
                source_ids.update(e['requirement_id'] for e in (obj or {}).get('evidence', []))
    return dict(changes=changes, affected_source_ids=sorted(source_ids),
                stale_assumptions=[r['id'] for r in after.get('assumption_records', []) if r.get('stale')],
                stale_links=after.get('stale_links', {}),
                document_review_required=any(c['kind'] in ('component', 'connection') for c in changes))
