"""Bounded, recoverable model review; unverified output never becomes a diagram edit."""
from copy import deepcopy
from dataclasses import replace
import json
import traceback
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .llm_client import LLMError
from .models import AnalysisResult, Finding, Component, Connection
from .prompts import ANALYSIS_SYSTEM_PROMPT, analysis_user_prompt
from .requirement_catalog import RequirementEntry
from .validator import normalize


MAX_CALLS = 8
PART_CHARS = 8000


def check_proposed_changes(architecture, entries, changes):
    """Side-effect-free proposal check for the initial document analysis."""
    objects = {o.id:(kind, o.model_dump()) for kind, items in (('component', architecture.components), ('connection', architecture.connections)) for o in items}
    sources = {e.requirement_id:e.text for e in entries}
    for change in changes:
        key, kind, action = change['id'], change['kind'], change['action']
        old = objects.get(key)
        if (action=='add' and old) or (action!='add' and (not old or old[0]!=kind)):
            raise ValueError('Önerinin işlem veya hedefi mevcut şemayla uyuşmuyor.')
        if action == 'remove':
            objects.pop(key)
            if kind=='component':
                objects = {oid:o for oid,o in objects.items() if o[0]!='connection' or key not in (o[1]['source'],o[1]['target'])}
            continue
        value = {**(old[1] if old else {}), **change['value'], 'id':key}
        value = (Component if kind=='component' else Connection).model_validate(value).model_dump()
        for ev in value['evidence']:
            if ev['requirement_id'] not in sources or not normalize(ev.get('quote')) or normalize(ev['quote']) not in normalize(sources[ev['requirement_id']]):
                raise ValueError('Önerideki alıntı kaynakla eşleşmiyor.')
        if kind=='connection':
            ids = {oid for oid,o in objects.items() if o[0]=='component'}
            if value['source'] not in ids or value['target'] not in ids or value['source']==value['target']:
                raise ValueError('Önerideki bağlantı uçları geçerli değil.')
        objects[key] = (kind,value)


def source_parts(entries, size=PART_CHARS):
    """Keep ordinary records whole; long records overlap without changing source IDs."""
    records = []
    for entry in entries:
        if len(entry.text) <= size:
            records.append(entry)
        else:
            for start in range(0, len(entry.text), size - 400):
                records.append(replace(entry, text=entry.text[start:start + size]))
    parts, current, chars = [], [], 0
    for entry in records:
        length = len(entry.formatted())
        if current and chars + length > size:
            parts.append(current)
            current, chars = [], 0
        current.append(entry)
        chars += length
    if current:
        parts.append(current)
    return parts


def task(label, entries, scope='detail', depth=0):
    return dict(label=label, entries=[vars(e) for e in entries], scope=scope, depth=depth)


def plan_review(entries, architecture):
    # Small reviews retain one call; larger reviews separate local and global questions.
    prompt = analysis_user_prompt(entries, architecture, compact=True)
    groups=source_parts(entries)
    if len(prompt) <= 16000 or (len(groups)<=1 and len(prompt)<=60000):
        return [task('Bütün tasarım', entries, 'full')]
    tasks = [task(f'Belge bölümü {i + 1}', group) for i, group in enumerate(groups)]
    if len(prompt) <= 60000:
        tasks.append(task('Bölümler arası ilişkiler', entries, 'cross'))
    else:
        # No silent excerpting: overlapping complete source groups support shared interfaces.
        by_id = {e.requirement_id: e for e in entries}
        for c in architecture.components:
            objects = [c] + [e for e in architecture.connections if c.id in (e.source, e.target)]
            peers = {e.source for e in objects[1:]} | {e.target for e in objects[1:]}
            objects += [o for o in architecture.components if o.id in peers and o.id != c.id]
            ids = {ev.requirement_id for o in objects for ev in o.evidence}
            related = [by_id[rid] for rid in by_id if rid in ids]
            if related:
                tasks.append(task(f'{c.name}: arayüz ilişkileri', related, 'cross'))
        # Explicitly report that a full-document cross review did not fit; never claim completeness.
        tasks.append(dict(label='Belgenin tamamında çapraz inceleme', scope='unavailable', entries=[], depth=0))
    return tasks


def finding_key(finding):
    return json.dumps([
        finding['type'], finding['severity'], normalize(finding['title']), normalize(finding['description']), finding.get('recommended_action'),
        sorted(finding['related_component_ids']), sorted(finding['related_connection_ids']),
        sorted({e['requirement_id'] for e in finding['evidence']}), finding['proposed_changes'],
    ], ensure_ascii=False, sort_keys=True)


def merge_analysis(target, incoming):
    keys = {finding_key(f) for f in target['findings']}
    for finding in incoming['findings']:
        key = finding_key(finding)
        if key not in keys:
            keys.add(key)
            target['findings'].append(finding)
    for field in ('missing_information', 'open_questions'):
        target[field] = list(dict.fromkeys(target[field] + incoming[field]))


def inspect_result(result, entries, architecture, check_proposal):
    """Quarantine invalid findings, preserve valid siblings, never invent repaired evidence."""
    if not isinstance(result, dict) or not isinstance(result.get('findings'), list):
        raise LLMError('SCHEMA', 'Model findings listesini döndürmedi.')
    sources = {e.requirement_id: e.text for e in entries}
    components = {c.id for c in architecture.components}
    connections = {c.id for c in architecture.connections}
    accepted = AnalysisResult().model_dump()
    excluded = []
    for raw in result['findings']:
        title = raw.get('title', 'Adsız bulgu') if isinstance(raw, dict) else 'Biçimi bozuk bulgu'
        problems = []
        try:
            f = Finding.model_validate(raw).model_dump()
        except ValidationError as exc:
            fields = [dict(field='.'.join(map(str, e['loc'])), type=e['type']) for e in exc.errors()]
            excluded.append(dict(code='FINDING_SCHEMA', title=title, message='Bulgu beklenen biçime uymuyor.', fields=fields, finding=raw))
            continue
        for ev in f['evidence']:
            if ev['requirement_id'] not in sources:
                problems.append(dict(code='SOURCE_UNKNOWN', message='Model belgede bulunmayan bir kaynak kullanmış.', source_id=ev['requirement_id']))
            elif not normalize(ev.get('quote')) or normalize(ev['quote']) not in normalize(sources[ev['requirement_id']]):
                problems.append(dict(code='QUOTE_MISMATCH', message='Modelin alıntısı belirtilen kaynakta bulunmuyor.', source_id=ev['requirement_id']))
        unknown = sorted((set(f['related_component_ids']) - components) | (set(f['related_connection_ids']) - connections))
        if unknown:
            problems.append(dict(code='OBJECT_UNKNOWN', message='Model şemada bulunmayan öğelerle ilişki kurmuş.', object_ids=unknown))
        if problems:
            excluded.append(dict(code=problems[0]['code'], title=title, message=problems[0]['message'], problems=problems, finding=raw))
            continue
        if f['proposed_changes']:
            try:
                check_proposal(f['proposed_changes'])
            except (ValueError, KeyError) as exc:
                # Keep a supported observation, but make the unsafe executable proposal unavailable.
                message = 'Değişiklik önerisi uygulanabilir biçimde değil; bulgu korundu, öneri devre dışı bırakıldı.'
                fields = []
                if isinstance(exc, ValidationError):
                    fields = [dict(field='.'.join(map(str, e['loc'])), type=e['type']) for e in exc.errors()]
                excluded.append(dict(code='PROPOSAL_INVALID', title=title, message=message, detail='Alan biçimi hatalı.' if isinstance(exc, ValidationError) else str(exc), fields=fields, finding=raw))
                f['proposed_changes'] = []
                f['open_details'].append(message)
        accepted['findings'].append(f)
    for field in ('missing_information', 'open_questions'):
        value = result.get(field, [])
        if isinstance(value, list) and all(isinstance(s, str) for s in value):
            accepted[field] = value
        else:
            excluded.append(dict(code='RESULT_SCHEMA', title=field, message='Bu bölüm metin listesi biçiminde değil.', finding={field: value}))
    return accepted, excluded


def run_review(client, entries, architecture, check_proposal, checkpoint, tasks=None, seed=None):
    pending = deepcopy(tasks if tasks is not None else plan_review(entries, architecture))
    report = dict(analysis=deepcopy(seed or AnalysisResult().model_dump()), sections=[], excluded=[], retry_tasks=[], remaining_tasks=[], calls=0)
    while pending:
        part = pending.pop(0)
        if report['calls'] >= MAX_CALLS:
            report['retry_tasks'].extend([part] + pending)
            report['sections'].append(dict(label=part['label'], status='failed', error_code='CALL_LIMIT', message='Bu değerlendirmedeki çağrı sınırına ulaşıldı. Kalan bölümler yeniden denenebilir.'))
            break
        if part['scope'] == 'unavailable':
            report['sections'].append(dict(label=part['label'], status='failed', error_code='CROSS_REVIEW_LIMIT', message='Belgenin tamamı tek isteğe sığmadı. Arayüzlere bağlı kaynaklar birlikte incelendi; bütün belge çapraz incelemesi tamamlanmış sayılmadı.'))
            continue
        report['calls'] += 1
        report['remaining_tasks'] = deepcopy([part] + pending)
        report['active_section']=dict(label=part['label'],started_at=datetime.now(timezone.utc).isoformat())
        report['total_sections']=len(report['sections'])+len(pending)+1
        checkpoint(report, f"{part['label']} inceleniyor · {report['calls']}. çağrı")
        group = [RequirementEntry(**e) for e in part['entries']]
        scope = {
            'full': 'Review the whole supplied design.',
            'detail': 'Review only issues supported by this source section. The complete architecture is provided for context; do not report omissions merely because another source section is absent.',
            'cross': 'Review ONLY contradictions and interface inconsistencies across source sections and connected units. Do not repeat local findings or propose a wholesale redesign.',
        }[part['scope']]
        prompt = analysis_user_prompt(group, architecture, compact=True) + '\nREVIEW SCOPE\n' + scope
        if part.get('feedback'):
            prompt += '\nPREVIOUS OUTPUT REJECTED\n' + part['feedback'] + '\nRe-read the sources and correct these output errors. Use exact source/object IDs and verbatim quotes. Omit unsupported findings instead of inventing evidence. Do not repeat already supported findings.'
        before = len(client.calls) if isinstance(client.calls, list) else 0
        section = dict(label=part['label'], source_ids=list(dict.fromkeys(e.requirement_id for e in group)))
        section_started=time.monotonic()
        try:
            result = client.extract_json(ANALYSIS_SYSTEM_PROMPT, prompt)
            valid, excluded = inspect_result(result, entries, architecture, check_proposal)
            merge_analysis(report['analysis'], valid)
            report['excluded'].extend([{**e, 'section':part['label']} for e in excluded])
            section.update(status='partial' if excluded else 'completed', accepted=len(valid['findings']), excluded=len(excluded))
            if excluded:
                report['retry_tasks'].append({**part, 'feedback':json.dumps([{'title':e['title'], 'code':e['code'], 'problems':e.get('problems'), 'fields':e.get('fields')} for e in excluded], ensure_ascii=False)[:6000]})
        except Exception as exc:
            code = getattr(exc, 'code', type(exc).__name__)
            section.update(status='failed', error_code=code)
            section['message'] = str(exc) if isinstance(exc, LLMError) else 'Model sonucu işlenirken uygulama hatası oluştu; teknik konum teşhis kaydında saklandı.'
            section['frames'] = [dict(file=Path(f.filename).name, line=f.lineno, function=f.name) for f in traceback.extract_tb(exc.__traceback__)]
            # Split only on a known output-budget failure. Never automatically repeat a timeout.
            if code == 'TRUNCATED' and part['depth'] < 2:
                split = source_parts(group, max(1200, sum(len(e.text) for e in group) // 2))
                if len(split) > 1:
                    section['status'] = 'split'
                    section['message'] = 'Yanıt kesildi; aynı bölüm daha küçük parçalara ayrıldı.'
                    pending = [task(f"{part['label']} / {i + 1}", g, 'detail', part['depth'] + 1) for i, g in enumerate(split)] + pending
                    if part['scope'] in ('full', 'cross'):
                        section['cross_review_incomplete'] = True
                        report['retry_tasks'].append(part)
                else:
                    report['retry_tasks'].append(part)
            else:
                report['retry_tasks'].append(part)
            if code in ('AUTHENTICATION', 'ACCESS_DENIED', 'ENDPOINT_OR_MODEL', 'RATE_LIMIT', 'NETWORK', 'TLS', 'TIMEOUT', 'SERVICE_UNAVAILABLE', 'REQUEST_FORMAT', 'INVALID_HEADER', 'TLS_RUNTIME', 'WORKER_EXIT', 'TIME_BUDGET', 'CANCELLED'):
                report['retry_tasks'].extend(pending)
                pending = []
        if isinstance(client.calls, list):
            section['transport'] = deepcopy(client.calls[before:])
            # Prompts are reconstructible from the stored tasks. Keep output, usage and safe settings.
            for call in section['transport']:
                call.pop('request', None)
        report['sections'].append(section)
        section['seconds']=round(time.monotonic()-section_started,2)
        report['active_section']=None
        report['remaining_tasks'] = deepcopy(pending)
        checkpoint(report, f"{part['label']} işlendi; sonuçlar korunuyor.")
    report['remaining_tasks'] = []
    return report
