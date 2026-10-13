"""Versioned document and assumption records, independent of model transport."""
from copy import deepcopy
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from .review_topics import fingerprint, build_topics
from .decision_dependencies import dependency_snapshot, dependency_reason, normalized


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
    scope: Literal['linked', 'project'] = 'linked'
    status: Literal['pending', 'accepted', 'rejected', 'waiting'] = 'pending'
    note: str = ''
    alternative: str = ''
    actor: str = ''
    at: str = ''
    basis: str | None = None
    basis_version: int = 2
    basis_snapshot: dict | None = None
    stale: bool = False
    stale_reason: str = ''
    impact_review: dict = Field(default_factory=dict)


def upgrade_state(state, original, baseline_resolver=None):
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
            state['assumption_records'].append(record)
    for i, raw in enumerate(state['assumption_records']):
        record = AssumptionRecord.model_validate(raw).model_dump()
        present = assumption_snapshot(state, record)
        if record['basis_snapshot'] is None:
            baseline = baseline_resolver('assumption', record['id'], raw) if baseline_resolver else None
            if baseline:
                previous_state, previous_record = baseline
                record['basis_snapshot'] = assumption_snapshot(previous_state, previous_record)
            elif record['status'] == 'pending' or (not raw.get('basis') and not raw.get('stale')) or raw.get('basis') == legacy_assumption_basis(state, raw):
                record['basis_snapshot'] = present
            elif not any(raw.get(k) for k in ('source_ids', 'component_ids', 'connection_ids')) and record['scope'] == 'linked':
                # Old unlinked records hashed the entire project. Keep the
                # assumption itself as their scope, not the whole architecture.
                original_texts = original['architecture'].get('assumptions', [])
                original_text = original_texts[i] if i < len(original_texts) else None
                if normalized(original_text) == normalized(record['text']) and not record['rationale']:
                    record['basis_snapshot'] = present
        if record['basis_snapshot'] is not None:
            requested = record['impact_review'].get('action') == 'review'
            record.update(basis_version=2, basis=fingerprint(record['basis_snapshot']),
                          stale=record['status'] != 'pending' and (record['basis_snapshot'] != present or requested))
            record['stale_reason'] = ('Mühendis bu değişiklik sonrasında yeniden inceleme istedi.' if requested
                                      else dependency_reason(record['basis_snapshot'], present, state)) if record['stale'] else ''
        elif record['status'] != 'pending':
            record.update(stale=True, stale_reason='Eski kararın teknik dayanağı bulunamadı; ilgili öğeleri seçip kararı yeniden doğrulayın.')
        state['assumption_records'][i] = record
    upgrade_topic_decisions(state, original, baseline_resolver)
    return state


def current_document(original, state):
    return {**original, 'source_catalog': state.get('source_catalog', original['source_catalog'])}


def legacy_assumption_basis(state, record):
    """Old digest, used only to recover an existing decision's baseline."""
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


def assumption_snapshot(state, record):
    snapshot = dependency_snapshot(state, record.get('source_ids', []), record.get('component_ids', []),
                                   record.get('connection_ids', []), incident=True, project=record.get('scope') == 'project')
    return {**snapshot, 'assumption': normalized({'text':record['text'], 'rationale':record.get('rationale', '')})}


def accept_assumption_basis(state, record):
    record['basis_snapshot'] = assumption_snapshot(state, record)
    record.update(basis=fingerprint(record['basis_snapshot']), basis_version=2, stale=False, stale_reason='', impact_review={})


def assumption_basis(state, record):
    return fingerprint(assumption_snapshot(state, record))


def upgrade_topic_decisions(state, original, baseline_resolver):
    from .models import FinalModel
    final = FinalModel.model_validate({**current_document(original, state), 'architecture':state['architecture'], 'analysis':state['analysis']})
    for topic in build_topics(final, [], state.get('decisions', {})):
        key = 'topic:'+topic['id']
        decision = state['decisions'].get(key) or state['decisions'].get('finding:'+topic['finding_id'])
        if not decision:
            continue
        decision = deepcopy(decision)
        if decision.get('fingerprint_version') != 3:
            baseline = baseline_resolver('topic', key, decision) if baseline_resolver else None
            snapshot = None
            if baseline:
                previous, _ = baseline
                previous_final = FinalModel.model_validate({**current_document(original, previous), 'architecture':previous['architecture'], 'analysis':previous['analysis']})
                old_topic = next((t for t in build_topics(previous_final, [], previous.get('decisions', {})) if t['id'] == topic['id']), None)
                snapshot = old_topic['dependency_snapshot'] if old_topic else None
            elif (decision.get('fingerprint_version') == 2 and decision.get('fingerprint') == topic['legacy_fingerprint']) or (not decision.get('fingerprint') and not decision.get('stale')):
                snapshot = topic['dependency_snapshot']
            decision.update(fingerprint_version=3, dependency_snapshot=snapshot)
            if snapshot is not None:
                decision['fingerprint'] = fingerprint(snapshot)
            else:
                decision.update(stale=True, stale_reason='Eski kararın teknik dayanağı bulunamadı; kararı yeniden doğrulayın.')
        state['decisions'][key] = decision
    for topic in build_topics(final, [], state.get('decisions', {})):
        decision = state['decisions'].get('topic:'+topic['id'])
        if decision and topic['decision']:
            decision['stale'] = bool(topic['decision'].get('stale'))
            decision['stale_reason'] = topic['decision'].get('stale_reason', '')


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
    previous = {r['id']:r for r in before.get('assumption_records', [])}
    stale = [r for r in after.get('assumption_records', []) if r.get('stale') and
             (not previous.get(r['id'], {}).get('stale') or r.get('stale_reason') != previous.get(r['id'], {}).get('stale_reason'))]
    return dict(changes=changes, affected_source_ids=sorted(source_ids),
                stale_assumptions=[r['id'] for r in stale],
                stale_assumption_details=[dict(id=r['id'], text=r['text'], status=r['status'], reason=r['stale_reason']) for r in stale],
                stale_links={key:value for key,value in after.get('stale_links', {}).items() if value != before.get('stale_links', {}).get(key)},
                document_review_required=any(c['kind'] in ('component', 'connection') for c in changes))
