"""Local, revisioned engineering workspace. Imported LLM results remain immutable."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import uuid

from .models import Component, Connection, Finding, FinalModel, RequirementCoverage
from .requirement_catalog import RequirementEntry
from .validator import validate_architecture, normalize
from .source_relations import source_relations
from .review_topics import build_topics, source_labels


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


class ConflictError(ValueError):
    pass


ISSUE_TEXT = {
    'DUPLICATE_SOURCE_ID': ('Kaynak numarası tekrarlanmış', 'Aynı kaynak numarası birden fazla kayıtta bulunuyor.', 'Özgün belge numaralarını ve çıkarılan kayıtları kontrol edin.'),
    'DUPLICATE_COMPONENT_ID': ('Bileşen kimliği tekrarlanmış', 'İki bileşen aynı kalıcı kimlikle kaydedilmiş.', 'İçe aktarılan modelde bileşen kimliklerini benzersiz yapın.'),
    'DUPLICATE_CONNECTION_ID': ('Bağlantı kimliği tekrarlanmış', 'İki bağlantı aynı kalıcı kimlikle kaydedilmiş.', 'İçe aktarılan modelde bağlantı kimliklerini benzersiz yapın.'),
    'DUPLICATE_FINDING_ID': ('Konu kimliği tekrarlanmış', 'İki mühendislik konusu aynı kalıcı kimlikle kaydedilmiş.', 'İçe aktarılan bulgu kimliklerini benzersiz yapın.'),
    'DUPLICATE_COVERAGE': ('Kaynak sınıflandırması tekrarlanmış', 'Aynı kaynak için birden fazla kapsama kaydı bulunuyor.', 'Kaynağın sınıflandırmasını tek kayıtta birleştirin.'),
    'COVERAGE_CONTEXT_ONLY': ('Yalnız bağlam ilişkisi seçilmiş', 'Kaynağa ilgili nesneler eklenmiş ancak doğrudan doküman dayanağı yok.', 'Doğrudan destek varsa kanıt ekleyin; aksi halde kapsama durumunu yeniden değerlendirin.'),
    'COVERAGE_EVIDENCE_MISMATCH': ('Eşleştirme kanıt listesinde yok', 'Kaynak bu nesneyle ilişkilendirilmiş; nesnenin kanıt listesinde aynı kaynak bulunmuyor.', 'Gerçek destek varsa kanıt ekleyin; yalnızca bağlamsal bir ilişkiyse doğrudan eşleştirmeden çıkarın.'),
    'COVERAGE_WITHOUT_LINKS': ('Karşılık var denmiş, nesne seçilmemiş', 'Bu kaynağın şemada karşılığı olduğu belirtilmiş, ancak bileşen veya bağlantı seçilmemiş.', 'İlgili nesneyi seçin veya kaydı bağlam / eşleştirilmemiş olarak değerlendirin.'),
    'QUOTE_NOT_IN_SOURCE': ('Alıntı kaynakta bulunamadı', 'Gösterilen alıntı belirtilen kaynak metniyle eşleşmiyor.', 'Kaynak panelinden doğru cümleyi seçin; kendi kararınızı belge alıntısı gibi kaydetmeyin.'),
    'MISSING_EVIDENCE': ('Doküman dayanağı yok', 'Nesne için kaynak cümlesi seçilmemiş.', 'Dayanak ekleyin. Yeni bir mühendislik kararıysa gerekçesini kaydedin; doküman desteği olmadığı görünür kalır.'),
    'MISSING_QUOTE': ('Alıntı boş', 'Kaynak kimliği var, destekleyen alıntı yok.', 'Kaynak cümlesini veya ilgili bölümünü seçin.'),
    'UNKNOWN_EVIDENCE_REF': ('Kaynak bulunamadı', 'Kanıt listesi katalogda olmayan bir kaynağa işaret ediyor.', 'Mevcut katalogdan kaynak seçin.'),
    'PROTOCOL_MISMATCH': ('Arayüz ile alıntı uyuşmuyor', 'Kaynakta belirtilen arayüz, bağlantıdaki değerle uyuşmuyor.', 'Bağlantının arayüzünü ve doğru kaynak cümlesini birlikte kontrol edin.'),
    'PROTOCOL_NOT_SUPPORTED': ('Eklenen arayüz kanıtlanmıyor', 'Bağlantıda yazan teknolojilerden biri doğrulanmış alıntılarda bulunmuyor.', 'Arayüz değerini düzeltin veya destekleyen doğru alıntıyı ekleyin.'),
    'EXPLICIT_PROTOCOL_NOT_CAPTURED': ('Kaynakta arayüz var, bağlantıda yok', 'Alıntıda teknoloji adı belirtilmiş ama bağlantı alanı boş.', 'Kaynakta belirtilen arayüzü bağlantıya işleyin.'),
    'PROTOCOL_REVIEW_REQUIRED': ('Arayüz ayrıntısını kontrol edin', 'Alıntıda bağlantıya işlenmemiş başka teknolojiler bulunuyor.', 'Bu teknolojinin aynı bağlantıya ait olup olmadığını değerlendirin.'),
    'PROTOCOL_SOURCE_REVIEW': ('Alıntı arayüz bağlamını dışarıda bırakıyor', 'Kaynağın tamamında teknoloji adı var, seçilen alıntıda yok.', 'Alıntıyı yeterli bağlamı içerecek şekilde düzenleyin.'),
    'PROTOCOL_UNVERIFIED': ('Arayüz değeri doğrulanamadı', 'Arayüz değeri kaynak metniyle eşleştirilemedi.', 'Özel bir arayüz veya mühendis kararı olup olmadığını belirtin.'),
    'UNKNOWN_SOURCE': ('Bağlantının başlangıcı yok', 'Kaynak bileşen modelde bulunmuyor.', 'Mevcut bir başlangıç bileşeni seçin.'),
    'UNKNOWN_TARGET': ('Bağlantının hedefi yok', 'Hedef bileşen modelde bulunmuyor.', 'Mevcut bir hedef bileşen seçin.'),
    'UNKNOWN_COMPONENT_REF': ('İlişkili bileşen kaldırılmış veya bulunamıyor', 'Bir kapsama veya bulgu kaydı mevcut olmayan bir bileşene işaret ediyor.', 'Kaydı yeniden inceleyin; eski bulgular tarihsel bağlamını korur.'),
    'UNKNOWN_CONNECTION_REF': ('İlişkili bağlantı kaldırılmış veya bulunamıyor', 'Bir kapsama veya bulgu kaydı mevcut olmayan bir bağlantıya işaret ediyor.', 'Bulgunun hâlâ geçerli olup olmadığını değerlendirin.'),
    'MISSING_COVERAGE': ('Kaynak sınıflandırılmamış', 'Bu kaynağın şemayla ilişkisi henüz belirtilmemiş.', 'Kaynak panelinde eşleştirmeyi değerlendirin.'),
    'UNMAPPED_REQUIREMENT': ('Şemayla eşleştirilmemiş', 'Kaynak için mimari karşılık seçilmemiş.', 'Eksik öğe olup olmadığını kontrol edin; bağlamsa bunu belirtin.'),
    'PARTIAL_COVERAGE': ('Kısmen temsil edilmiş', 'Kaynağın yalnız bir bölümünün temsil edildiği belirtilmiş.', 'Kalan işlevi veya arayüzü not edin ve ilgili öğeleri ekleyin.'),
    'ORPHAN_COMPONENT': ('Bağlantısı olmayan bileşen', 'Bu bileşen şemadaki hiçbir bağlantının ucu değil.', 'Gerçekten bağımsız mı, yoksa eksik bir bağlantı mı var? Kaynakla kontrol edin.'),
    'EMPTY_ARCHITECTURE': ('Şema boş', 'Henüz mimari bileşen yok.', 'Belgenin mimari içerip içermediğini değerlendirin.'),
}


def enrich_issues(final):
    entries = [RequirementEntry(**s) for s in final.source_catalog]
    base = validate_architecture(final.architecture, entries, final.analysis)
    issues = [i.model_dump() for i in base]
    objects = final.architecture.components + final.architecture.connections
    object_ids = {o.id for o in objects}
    finding_ids = {f.id for f in final.analysis.findings}
    sources = {s['requirement_id']: s for s in final.source_catalog}
    for issue in issues:
        issue['finding_id'] = issue.get('finding_id') or (issue.get('related_id') if issue.get('related_id') in finding_ids else None)
        issue['source_id'] = issue.get('source_id') or (issue.get('related_id') if issue.get('related_id') in sources else None)
        issue['object_id'] = issue.get('object_id') or (issue.get('related_id') if issue.get('related_id') in object_ids else None)
        identity = {k:issue.get(k) for k in ('code','source_id','object_id','finding_id','related_id','message')}
        issue['key'] = hashlib.sha256(dump(identity).encode()).hexdigest()[:24]
        text = ISSUE_TEXT.get(issue['code'], ('Kayıt bütünlüğünü kontrol edin', issue.get('message', ''), 'İlişkili kaynak ve nesne kimliklerini inceleyin.'))
        issue.update(title=text[0], explanation=text[1], suggestion=text[2])
    return sorted(issues, key=lambda i:i['key'])


def changes_between(original, state):
    changes = []
    for field, kind in [('components', 'component'), ('connections', 'connection')]:
        before = {o['id']: o for o in original['architecture'][field]}
        after = {o['id']: o for o in state['architecture'][field]}
        for key in sorted(before.keys() | after.keys()):
            if before.get(key) != after.get(key):
                changes.append(dict(kind=kind, id=key, change='added' if key not in before else 'removed' if key not in after else 'modified', before=before.get(key), after=after.get(key)))
    before = {c['requirement_id']: c for c in original['architecture']['requirement_coverage']}
    for c in state['architecture']['requirement_coverage']:
        if before.get(c['requirement_id']) != c:
            changes.append(dict(kind='source', id=c['requirement_id'], change='modified', before=before.get(c['requirement_id']), after=c))
    return changes


class ReviewStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, origin_path TEXT NOT NULL, origin_hash TEXT NOT NULL, original TEXT NOT NULL, current INTEGER NOT NULL, version INTEGER NOT NULL, redo TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS revisions(project_id TEXT NOT NULL, seq INTEGER NOT NULL, parent INTEGER, state TEXT NOT NULL, PRIMARY KEY(project_id,seq));
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def import_run(self, path):
        path = Path(path).expanduser().resolve()
        if path.is_dir():
            path = path / 'analysis_result.json'
        raw = path.read_bytes()
        final = FinalModel.model_validate_json(raw)
        original = final.model_dump()
        if len({x.id for x in final.architecture.components + final.architecture.connections}) != len(final.architecture.components + final.architecture.connections):
            raise ValueError('Şemada yinelenen nesne kimliği var. İçe aktarmadan önce kimliklerin benzersiz olması gerekir.')
        pid = uuid.uuid4().hex
        state = dict(architecture=original['architecture'], analysis=original['analysis'], positions={}, decisions={}, provenance={})
        with self.db() as db:
            # Reopening a run returns its existing review rather than losing edits.
            found = db.execute('SELECT id FROM projects WHERE origin_path=? AND origin_hash=?', (str(path), hashlib.sha256(raw).hexdigest())).fetchone()
            if found:
                return self.get(found['id'])
            timestamp = now()
            db.execute('INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?,?)', (pid, final.architecture.system_name, str(path), hashlib.sha256(raw).hexdigest(), dump(original), 0, 0, '[]', timestamp, timestamp))
            db.execute('INSERT INTO revisions VALUES(?,?,?,?)', (pid, 0, None, dump(state)))
            db.execute('INSERT INTO events(project_id,action,actor,reason,at,revision) VALUES(?,?,?,?,?,?)', (pid, 'import', 'Sistem', 'Model çıktısı değişmez başlangıç olarak alındı.', timestamp, 0))
        return self.get(pid)

    def list(self):
        with self.db() as db:
            return [dict(r) for r in db.execute('SELECT id,name,origin_path,version,created,updated FROM projects ORDER BY updated DESC')]

    def get(self, pid):
        with self.db() as db:
            row = db.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
            if row is None:
                raise KeyError('İnceleme bulunamadı.')
            revision = db.execute('SELECT * FROM revisions WHERE project_id=? AND seq=?', (pid, row['current'])).fetchone()
            state = json.loads(revision['state'])
            events = [dict(r) for r in db.execute('SELECT action,actor,reason,at,revision FROM events WHERE project_id=? ORDER BY id DESC', (pid,))]
        original = json.loads(row['original'])
        final = FinalModel.model_validate({**original, 'architecture': state['architecture'], 'analysis': state['analysis']})
        issues = enrich_issues(final)
        topics = build_topics(final, issues, state['decisions'])
        relations = {s['requirement_id']:source_relations(final.architecture,s['requirement_id']) for s in final.source_catalog}
        return dict(id=pid, name=row['name'], origin_path=row['origin_path'], origin_hash=row['origin_hash'], version=row['version'], current_revision=row['current'], created=row['created'], updated=row['updated'], original=original, state=state, issues=issues, topics=topics, source_labels=source_labels(final.source_catalog), source_relations=relations, history=events, can_undo=revision['parent'] is not None, can_redo=bool(json.loads(row['redo'])), changes=changes_between(original, state))

    def mutate(self, pid, command):
        actor = command.get('actor', '').strip()
        reason = command.get('reason', '').strip()
        action = command.get('action')
        if not actor or not reason:
            raise ValueError('Mühendis adı ve işlem gerekçesi zorunludur.')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
            if row is None:
                raise KeyError('İnceleme bulunamadı.')
            if row['version'] != command.get('version'):
                raise ConflictError('İnceleme başka bir sekmede değişti. Son durumu yükleyip düzenlemenizi tekrar uygulayın.')
            rev = db.execute('SELECT * FROM revisions WHERE project_id=? AND seq=?', (pid, row['current'])).fetchone()
            redo = json.loads(row['redo'])
            if action == 'undo':
                if rev['parent'] is None:
                    raise ValueError('Geri alınacak değişiklik yok.')
                current = rev['parent']
                redo.append(row['current'])
            elif action == 'redo':
                if not redo:
                    raise ValueError('Yinelenecek değişiklik yok.')
                current = redo.pop()
            else:
                state = json.loads(rev['state'])
                original = json.loads(row['original'])
                state = self.apply(state, original, command)
                current = db.execute('SELECT MAX(seq)+1 FROM revisions WHERE project_id=?', (pid,)).fetchone()[0]
                db.execute('INSERT INTO revisions VALUES(?,?,?,?)', (pid, current, row['current'], dump(state)))
                redo = []
            timestamp = now()
            db.execute('UPDATE projects SET current=?,version=version+1,redo=?,updated=? WHERE id=?', (current, dump(redo), timestamp, pid))
            db.execute('INSERT INTO events(project_id,action,actor,reason,at,revision) VALUES(?,?,?,?,?,?)', (pid, action, actor, reason, timestamp, current))
        return self.get(pid)

    def apply(self, state, original, command):
        state = deepcopy(state)
        action = command['action']
        value = command.get('value', {})
        key = command.get('id', '')
        arch = state['architecture']
        before_final = FinalModel.model_validate({**original,'architecture':arch,'analysis':state['analysis']})
        before_topics = build_topics(before_final,enrich_issues(before_final),state['decisions'])
        sources = {s['requirement_id']: s for s in original['source_catalog']}
        components = {x['id'] for x in arch['components']}
        connections = {x['id'] for x in arch['connections']}
        affected = set()
        semantic = False

        def verify_evidence(obj):
            for ev in obj.get('evidence', []):
                src = sources.get(ev['requirement_id'])
                quote = normalize(ev.get('quote'))
                if not src or not quote or quote not in normalize(src['text']):
                    raise ValueError('Alıntı seçilen kaynakta bulunmuyor. Kaynak metinden bir bölüm seçin.')

        def put(field, obj):
            items = arch[field]
            old = next((x for x in items if x['id'] == obj['id']), None)
            if not old and obj['id'] in components | connections:
                raise ValueError('Bu nesne kimliği zaten kullanılıyor.')
            arch[field] = [obj if x['id'] == obj['id'] else x for x in items] if old else items + [obj]
            kind = 'component' if field == 'components' else 'connection'
            affected.add(f"{kind}:{obj['id']}")
            for ev in (old or {}).get('evidence', []) + obj.get('evidence', []):
                affected.add('source:' + ev['requirement_id'])
            state['provenance'][f"{kind}:{obj['id']}"] = dict(origin='engineer_edit' if any(o['id'] == obj['id'] for o in original['architecture'][field]) else 'engineer_added', actor=command['actor'], reason=command['reason'], at=now())

        if action in ('upsert_component', 'upsert_connection'):
            obj = (Component if action == 'upsert_component' else Connection).model_validate(value).model_dump()
            if key and obj['id'] != key:
                raise ValueError('Kalıcı nesne kimliği değiştirilemez.')
            verify_evidence(obj)
            if action == 'upsert_connection':
                if obj['source'] not in components or obj['target'] not in components:
                    raise ValueError('Bağlantının iki ucu da mevcut bileşen olmalı.')
                if obj['source'] == obj['target']:
                    raise ValueError('Bu sürümde aynı bileşene dönen bağlantı desteklenmiyor.')
                old = next((x for x in arch['connections'] if x['id'] == obj['id']), {})
                affected.update('component:' + x for x in [obj['source'], obj['target'], old.get('source', ''), old.get('target', '')] if x)
            put('components' if action == 'upsert_component' else 'connections', obj)
            semantic = True
        elif action in ('delete_component', 'delete_connection'):
            if key not in (components if action == 'delete_component' else connections):
                raise ValueError('Kaldırılacak nesne bulunamadı.')
            removed_edges = {key} if action == 'delete_connection' else {e['id'] for e in arch['connections'] if key in (e['source'], e['target'])}
            if action == 'delete_component' and removed_edges and not value.get('cascade'):
                raise ValueError('Bileşenin bağlantıları var. Bağlantılarıyla kaldırma seçimini onaylayın.')
            for edge in arch['connections']:
                if edge['id'] in removed_edges:
                    affected.update(['component:' + edge['source'], 'component:' + edge['target'], 'connection:' + edge['id']])
            arch['connections'] = [e for e in arch['connections'] if e['id'] not in removed_edges]
            if action == 'delete_component':
                arch['components'] = [c for c in arch['components'] if c['id'] != key]
                state['positions'].pop(key, None)
                affected.add('component:' + key)
            for cov in arch['requirement_coverage']:
                before = deepcopy(cov)
                cov['related_connection_ids'] = [x for x in cov['related_connection_ids'] if x not in removed_edges]
                if action == 'delete_component':
                    cov['related_component_ids'] = [x for x in cov['related_component_ids'] if x != key]
                cov['contextual_connection_ids'] = [x for x in cov.get('contextual_connection_ids', []) if x not in removed_edges]
                cov['contextual_component_ids'] = [x for x in cov.get('contextual_component_ids', []) if x != key or action != 'delete_component']
                if cov != before:
                    affected.add('source:' + cov['requirement_id'])
                    if cov['status'] in ('covered', 'partially_covered') and not cov['related_component_ids'] + cov['related_connection_ids']:
                        cov['status'] = 'unmapped'
                        cov['notes'] = 'İlişkili nesne mühendis tarafından kaldırıldı; yeniden değerlendirin.'
            semantic = True
        elif action == 'set_coverage':
            cov = RequirementCoverage.model_validate(value).model_dump()
            if cov['requirement_id'] not in sources:
                raise ValueError('Kaynak katalogda bulunmuyor.')
            if set(cov['related_component_ids'] + cov['contextual_component_ids']) - components or set(cov['related_connection_ids'] + cov['contextual_connection_ids']) - connections:
                raise ValueError('Eşleştirmede bulunmayan nesne seçilmiş.')
            if any(len(set(cov[f])) != len(cov[f]) for f in ('related_component_ids','related_connection_ids','contextual_component_ids','contextual_connection_ids')):
                raise ValueError('Aynı nesne bir kez seçilmeli.')
            if set(cov['related_component_ids']) & set(cov['contextual_component_ids']) or set(cov['related_connection_ids']) & set(cov['contextual_connection_ids']):
                raise ValueError('Bir öğe için doğrudan dayanak veya bağlam ilişkilerinden birini seçin.')
            arch['requirement_coverage'] = [c for c in arch['requirement_coverage'] if c['requirement_id'] != cov['requirement_id']] + [cov]
            affected.add('source:' + cov['requirement_id'])
        elif action == 'set_topic_decision':
            final = FinalModel.model_validate({**original, 'architecture':arch, 'analysis':state['analysis']})
            topics = build_topics(final, enrich_issues(final), state['decisions'])
            topic = next((t for t in topics if t['id']==key), None)
            if not topic:
                raise ValueError('İncelenecek konu bulunamadı. Listeyi yenileyin.')
            status = value.get('status')
            if status not in ('resolved','accepted','needs_review','merged','waiting'):
                raise ValueError('Geçersiz konu kararı.')
            target = value.get('merged_into') if status=='merged' else None
            if status=='merged':
                if not topic['finding_id']:
                    raise ValueError('Otomatik kayıt kontrolü başka bulguyla birleştirilemez.')
                other=next((t for t in topics if t['id']==target and t['finding_id']),None)
                if not other or target==key:
                    raise ValueError('Başka bir mühendislik konusu seçin.')
                seen={key}; cursor=target
                while cursor:
                    if cursor in seen: raise ValueError('Döngüsel konu birleştirme yapılamaz.')
                    seen.add(cursor)
                    cursor=state['decisions'].get('topic:'+cursor,{}).get('merged_into')
            snapshot={k:v for k,v in topic.items() if k not in ('decision',)}
            state['decisions']['topic:'+key]=dict(status=status, note=command['reason'], actor=command['actor'], at=now(), stale=False, fingerprint=topic['fingerprint'], snapshot=snapshot, merged_into=target)
            # Calculate the newly selected merge dependency, including any target chain.
            updated=next(t for t in build_topics(final,enrich_issues(final),state['decisions']) if t['id']==key)
            state['decisions']['topic:'+key]['fingerprint']=updated['fingerprint']
        elif action == 'set_decision':
            kind, _, oid = key.partition(':')
            valid = {'component': components, 'connection': connections, 'source': set(sources), 'finding': {f['id'] for f in state['analysis']['findings']}, 'assumption': {str(i) for i, _ in enumerate(arch['assumptions'])}}
            if oid not in valid.get(kind, set()):
                raise ValueError('Karar verilecek kayıt bulunamadı.')
            status = value.get('status')
            allowed = {'finding': {'accepted', 'rejected', 'resolved', 'merged', 'needs_review'}}.get(kind, {'approved', 'rejected', 'needs_review'})
            if status not in allowed:
                raise ValueError('Geçersiz inceleme kararı.')
            target = value.get('merged_into') if status == 'merged' else None
            if status == 'merged':
                if target not in valid['finding'] or target == oid:
                    raise ValueError('Birleştirilecek başka bir bulgu seçin.')
                seen = {oid}
                cursor = target
                while cursor:
                    if cursor in seen:
                        raise ValueError('Bulgular arasında döngüsel birleştirme yapılamaz.')
                    seen.add(cursor)
                    cursor = state['decisions'].get('finding:' + cursor, {}).get('merged_into')
            state['decisions'][key] = dict(status=status, note=command['reason'], actor=command['actor'], at=now(), stale=False, merged_into=target)
        elif action in ('add_finding', 'edit_finding'):
            obj = Finding.model_validate(value).model_dump()
            exists = any(f['id'] == obj['id'] for f in state['analysis']['findings'])
            if action == 'add_finding' and exists:
                raise ValueError('Bulgu kimliği zaten kullanılıyor.')
            if action == 'edit_finding' and (not exists or key != obj['id']):
                raise ValueError('Mevcut bulgunun kalıcı kimliği korunmalı.')
            verify_evidence(obj)
            if set(obj['related_component_ids']) - components or set(obj['related_connection_ids']) - connections:
                raise ValueError('Bulguda bulunmayan bir nesne seçilmiş.')
            if exists:
                state['analysis']['findings'] = [obj if f['id'] == key else f for f in state['analysis']['findings']]
                affected.add('finding:' + key)
                affected.update(k for k, d in state['decisions'].items() if d.get('merged_into') == key)
            else:
                state['analysis']['findings'].append(obj)
            origin = 'engineer_edit' if any(f['id'] == obj['id'] for f in original['analysis']['findings']) else 'engineer_added'
            state['provenance']['finding:' + obj['id']] = dict(origin=origin, actor=command['actor'], reason=command['reason'], at=now())
        elif action == 'set_assumption':
            index = int(key)
            text = str(value.get('text', '')).strip()
            if not text or not 0 <= index < len(arch['assumptions']):
                raise ValueError('Geçerli varsayım ve açıklama gerekli.')
            arch['assumptions'][index] = text
            affected.add('assumption:' + key)
            semantic = True
        elif action == 'layout':
            if set(value) - components:
                raise ValueError('Yerleşimde bulunmayan bileşen var.')
            for point in value.values():
                if not isinstance(point, dict) or set(point) != {'x', 'y'} or any(not isinstance(n, (float, int)) or not math.isfinite(n) or abs(n) > 100000 for n in point.values()):
                    raise ValueError('Geçersiz şema konumu.')
            state['positions'].update(value)
        else:
            raise ValueError('Desteklenmeyen işlem.')
        if semantic:
            # Any architecture change can affect a missing-interface finding. Never auto-resolve it.
            affected.update('finding:' + f['id'] for f in state['analysis']['findings'])
        for decision_key in affected:
            if decision_key in state['decisions']:
                state['decisions'][decision_key]['stale'] = True
                state['decisions'][decision_key]['stale_reason'] = 'İlişkili mimari veya dayanak değişti; önceki kararı yeniden değerlendirin.'
        # Topic decisions track only their own dependencies; unrelated edits do not reopen them.
        final = FinalModel.model_validate({**original,'architecture':arch,'analysis':state['analysis']})
        current_topics = build_topics(final,enrich_issues(final),state['decisions'])
        active_ids = {t['id'] for t in current_topics if t['active']}
        for previous in before_topics:
            key_for_topic = 'topic:'+previous['id']
            if previous['active'] and previous['kind'] != 'engineering' and previous['id'] not in active_ids and key_for_topic not in state['decisions']:
                # A fix clears a check; retain the engineering edit reason in completed work.
                snapshot={k:v for k,v in previous.items() if k != 'decision'}
                state['decisions'][key_for_topic]=dict(status='resolved', note=command['reason'], actor=command['actor'], at=now(), stale=False, fingerprint=previous['fingerprint'], snapshot=snapshot, auto_completed=True, merged_into=None)
        for topic in build_topics(final,enrich_issues(final),state['decisions']):
            decision_key='topic:'+topic['id']
            if decision_key in state['decisions']:
                state['decisions'][decision_key]['stale']=bool(topic['decision'].get('stale')) if topic['active'] else False
                if topic['active'] and topic['decision'].get('stale'):
                    state['decisions'][decision_key]['stale_reason']=topic['decision']['stale_reason']
        return state

    def save_job(self, payload):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?)', (payload['id'], dump(payload)))

    def jobs(self):
        with self.db() as db:
            return sorted([json.loads(r['payload']) for r in db.execute('SELECT payload FROM jobs')], key=lambda x: x['created'], reverse=True)
