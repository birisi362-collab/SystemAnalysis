"""Local, revisioned engineering workspace. Imported LLM results remain immutable."""
from contextlib import contextmanager, closing
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import uuid

from .models import Component, Connection, Finding, FinalModel, RequirementCoverage, ProposedChange, AnalysisResult
from .requirement_catalog import RequirementEntry
from .validator import validate_architecture, normalize
from .source_relations import source_relations
from .review_topics import build_topics, source_labels, proposal_context, fingerprint
from .review_runner import finding_key
from .engineering_workspace import (upgrade_state, current_document, SourceEdit, AssumptionRecord,
                                    accept_assumption_basis, legacy_assumption_basis, impact_summary, workspace_fingerprint)
from .decision_dependencies import technical_object, normalized


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


class ConflictError(ValueError):
    pass


class ReviewIntakeError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


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
        backup = self.path.with_name('reviews.before_workspace_v2.sqlite3')
        if self.path.exists() and not backup.exists():
            with closing(sqlite3.connect(self.path)) as src, closing(sqlite3.connect(backup)) as dst:
                src.backup(dst)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, origin_path TEXT NOT NULL, origin_hash TEXT NOT NULL, original TEXT NOT NULL, current INTEGER NOT NULL, version INTEGER NOT NULL, redo TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS revisions(project_id TEXT NOT NULL, seq INTEGER NOT NULL, parent INTEGER, state TEXT NOT NULL, PRIMARY KEY(project_id,seq));
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS change_previews(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, version INTEGER NOT NULL, commands TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversations(project_id TEXT NOT NULL, id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            ''')
            if 'assumption_reviews' not in {r['name'] for r in db.execute('PRAGMA table_info(change_previews)')}:
                db.execute("ALTER TABLE change_previews ADD COLUMN assumption_reviews TEXT NOT NULL DEFAULT '{}'")

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
        if len({x['requirement_id'] for x in original['source_catalog']}) != len(original['source_catalog']):
            raise ValueError('Kaynak kimlikleri benzersiz olmalı.')
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

    def restore_snapshot(self, snapshot):
        original = FinalModel.model_validate(snapshot['original']).model_dump()
        state = upgrade_state(snapshot['state'], original)
        current = FinalModel.model_validate({**current_document(original, state), 'architecture':state['architecture'], 'analysis':state['analysis']})
        state['architecture'] = current.architecture.model_dump()
        state['analysis'] = current.analysis.model_dump()
        for key in ('positions','decisions','provenance'):
            if not isinstance(state.get(key), dict): state[key] = {}
        pid = uuid.uuid4().hex; timestamp = now()
        with self.db() as db:
            db.execute('INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?,?)', (pid, current.architecture.system_name, 'restored:'+pid, snapshot.get('origin_hash',fingerprint(original)), dump(original), 0, 0, '[]', timestamp, timestamp))
            db.execute('INSERT INTO revisions VALUES(?,?,?,?)', (pid, 0, None, dump(state)))
            for event in reversed(snapshot.get('history', [])):
                db.execute('INSERT INTO events(project_id,action,actor,reason,at,revision) VALUES(?,?,?,?,?,?)', (pid,event.get('action','import'),event.get('actor','Mühendis'),event.get('reason',''),event.get('at',timestamp),0))
            db.execute('INSERT INTO events(project_id,action,actor,reason,at,revision) VALUES(?,?,?,?,?,?)', (pid,'import','Mühendis','Çalışma paketi açıldı; önceki işlemler geçmişte korunur.',timestamp,0))
        for turn in snapshot.get('conversation', []):
            turn = {**deepcopy(turn), 'id':uuid.uuid4().hex, 'imported':True}
            if turn.get('result'): turn['result'].pop('preview', None)
            self.save_conversation(pid, turn)
        return self.get(pid)

    def upgrade_revision(self, db, pid, revision, original):
        """Recover old decision baselines along this revision's active ancestry.

        Lazy and read-only: no revisions are rewritten, and undone branches are
        never used as the baseline for the current decision.
        """
        ancestors = None
        current_state = json.loads(revision['state'])
        def resolve(kind, key, record):
            nonlocal ancestors
            if not record.get('at'):
                return None
            if ancestors is None:
                ancestors = []
                cursor = revision
                while cursor is not None:
                    ancestors.append(json.loads(cursor['state']))
                    cursor = db.execute('SELECT * FROM revisions WHERE project_id=? AND seq=?', (pid, cursor['parent'])).fetchone() if cursor['parent'] is not None else None
                ancestors.reverse()
            for previous in ancestors:
                if kind == 'assumption':
                    candidates = previous.get('assumption_records', [])
                    if not candidates:
                        candidates = []
                        current_records = current_state.get('assumption_records', [])
                        index = next((i for i,r in enumerate(current_records) if r['id'] == key), None)
                        if index is None:
                            index = next((i for i,t in enumerate(current_state['architecture'].get('assumptions', [])) if 'ASM-'+uuid.uuid5(uuid.NAMESPACE_URL, str(i)+':'+t).hex[:12] == key), None)
                        for i, text in enumerate(previous['architecture'].get('assumptions', [])):
                            old = previous.get('decisions', {}).get('assumption:'+str(i), {})
                            candidates.append({**old, 'id':key if i == index else 'ASM-'+uuid.uuid5(uuid.NAMESPACE_URL, str(i)+':'+text).hex[:12], 'text':text})
                    candidate = next((r for r in candidates if r['id'] == key), None)
                    marker = 'basis'
                else:
                    candidate = previous.get('decisions', {}).get(key)
                    if not candidate:
                        finding = next((f for f in previous['analysis']['findings'] if 'topic:'+fingerprint(('finding', f['id']))[:20] == key), None)
                        candidate = previous.get('decisions', {}).get('finding:'+finding['id']) if finding else None
                    marker = 'fingerprint'
                if not candidate or candidate.get('stale') or candidate.get('at') != record['at'] or candidate.get('actor') != record.get('actor'):
                    continue
                if candidate.get(marker) and candidate.get(marker) != record.get(marker):
                    continue
                if kind == 'assumption' and candidate.get('basis') and candidate['basis'] != legacy_assumption_basis(previous, candidate):
                    continue
                if kind == 'topic' and candidate.get('fingerprint_version') == 2:
                    previous_final = FinalModel.model_validate({**current_document(original, previous), 'architecture':previous['architecture'], 'analysis':previous['analysis']})
                    topic = next((t for t in build_topics(previous_final, [], previous.get('decisions', {})) if 'topic:'+t['id'] == key), None)
                    if not topic or topic['legacy_fingerprint'] != candidate.get('fingerprint'):
                        continue
                return previous, candidate
            return None
        return upgrade_state(current_state, original, resolve)

    def get(self, pid):
        with self.db() as db:
            row = db.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
            if row is None:
                raise KeyError('İnceleme bulunamadı.')
            revision = db.execute('SELECT * FROM revisions WHERE project_id=? AND seq=?', (pid, row['current'])).fetchone()
            original = json.loads(row['original'])
            state = self.upgrade_revision(db, pid, revision, original)
            events = [dict(r) for r in db.execute('SELECT action,actor,reason,at,revision FROM events WHERE project_id=? ORDER BY id DESC', (pid,))]
        final = FinalModel.model_validate({**current_document(original, state), 'architecture': state['architecture'], 'analysis': state['analysis']})
        issues = []
        topics = build_topics(final, issues, state['decisions'])
        proposals = {}
        for f in state['analysis']['findings']:
            if f.get('proposed_changes'):
                current = fingerprint(proposal_context(state['architecture'], f))
                base = state.get('proposal_bases', {}).get(f['id'], fingerprint(proposal_context(original['architecture'], f)))
                previous = state.get('proposal_contexts', {}).get(f['id'], proposal_context(original['architecture'], f))
                present = proposal_context(state['architecture'], f)
                changed = [dict(id=oid, before=previous.get(oid), after=present.get(oid)) for oid in sorted(set(previous) | set(present)) if previous.get(oid) != present.get(oid)]
                proposals[f['id']] = dict(fingerprint=current, stale=current != base or bool(state['stale_links'].get('finding:'+f['id'])), changed_objects=changed)
        return dict(id=pid, name=row['name'], origin_path=row['origin_path'], origin_hash=row['origin_hash'], version=row['version'], current_revision=row['current'], created=row['created'], updated=row['updated'], original=original, state=state, issues=issues, topics=topics, proposals=proposals, source_labels=source_labels(final.source_catalog), history=events, can_undo=revision['parent'] is not None, can_redo=bool(json.loads(row['redo'])), changes=changes_between(original, state))

    def mutate(self, pid, command):
        actor = command.get('actor', '').strip()
        reason = command.get('reason', '').strip()
        action = command.get('action')
        defaults = {'upsert_component':'Bileşen düzenlendi', 'upsert_connection':'Bağlantı düzenlendi', 'layout':'Şema yerleşimi değişti', 'undo':'Son işlem geri alındı', 'redo':'İşlem yinelendi', 'set_assumption':'Varsayım düzenlendi', 'delete_component':'Bileşen kaldırıldı', 'delete_connection':'Bağlantı kaldırıldı', 'add_finding':'Mühendis notu eklendi', 'edit_finding':'İnceleme notu düzenlendi', 'append_review':'Yeni yapay zekâ değerlendirmesi eklendi', 'apply_change_set':'Önizlenen değişiklik paketi uygulandı', 'upsert_source':'TİD maddesi düzenlendi', 'delete_source':'TİD maddesi kaldırıldı', 'upsert_assumption':'Varsayım ve mühendis kararı düzenlendi'}
        reason = reason or defaults.get(action, '')
        command = {**command, 'reason':reason}
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
                original = json.loads(row['original'])
                state = self.upgrade_revision(db, pid, rev, original)
                if action == 'apply_change_set':
                    preview = db.execute('SELECT * FROM change_previews WHERE id=? AND project_id=?', (command.get('value', {}).get('preview_id'), pid)).fetchone()
                    if not preview or preview['version'] != row['version']:
                        raise ConflictError('Önizleme güncel değil. Değişiklikleri yeniden önizleyin.')
                    state = self.apply_commands(state, original, json.loads(preview['commands']), preview['actor'], preview['reason'], json.loads(preview['assumption_reviews']))
                    actor, reason = preview['actor'], preview['reason']
                else:
                    state = self.apply(state, original, command)
                current = db.execute('SELECT MAX(seq)+1 FROM revisions WHERE project_id=?', (pid,)).fetchone()[0]
                db.execute('INSERT INTO revisions VALUES(?,?,?,?)', (pid, current, row['current'], dump(state)))
                redo = []
            timestamp = now()
            db.execute('UPDATE projects SET current=?,version=version+1,redo=?,updated=? WHERE id=?', (current, dump(redo), timestamp, pid))
            db.execute('INSERT INTO events(project_id,action,actor,reason,at,revision) VALUES(?,?,?,?,?,?)', (pid, action, actor, reason, timestamp, current))
        return self.get(pid)

    def apply(self, state, original, command):
        state = upgrade_state(state, original)
        incoming_workspace = workspace_fingerprint(state)
        action = command['action']
        value = command.get('value', {})
        key = command.get('id', '')
        arch = state['architecture']
        before_final = FinalModel.model_validate({**current_document(original, state),'architecture':arch,'analysis':state['analysis']})
        before_topics = build_topics(before_final,[],state['decisions'])
        sources = {s['requirement_id']: s for s in state['source_catalog']}
        components = {x['id'] for x in arch['components']}
        connections = {x['id'] for x in arch['connections']}
        affected = set()

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
            if technical_object(old) != technical_object(obj):
                affected.add(f"{kind}:{obj['id']}")
                for ev in (old or {}).get('evidence', []) + obj.get('evidence', []):
                    affected.add('source:' + ev['requirement_id'])
            state['stale_links'].pop(f"{kind}:{obj['id']}", None)
            state['provenance'][f"{kind}:{obj['id']}"] = dict(origin='engineer_edit' if any(o['id'] == obj['id'] for o in original['architecture'][field]) else 'engineer_added', actor=command['actor'], reason=command['reason'], at=now())

        if action in ('upsert_source', 'delete_source'):
            old = sources.get(key)
            if action == 'delete_source':
                if old is None:
                    raise ValueError('Kaldırılacak TİD maddesi bulunamadı.')
                state['source_catalog'] = [s for s in state['source_catalog'] if s['requirement_id'] != key]
                state['retired_sources'].append({**old, 'retired_at':now(), 'actor':command['actor']})
            else:
                item = SourceEdit.model_validate(value).model_dump()
                if not item['text'].strip():
                    raise ValueError('TİD metni boş olamaz.')
                if key and (not old or item['requirement_id'] != key):
                    raise ValueError('Kalıcı ister kimliği değiştirilemez.')
                if not key and (item['requirement_id'] in sources or any(s['requirement_id']==item['requirement_id'] for s in state['retired_sources'])):
                    raise ValueError('İster kimliği daha önce kullanılmış.')
                key = item['requirement_id']
                item['locations'] = old.get('locations', []) if old else ['engineer:'+key]
                state['source_catalog'] = [item if s['requirement_id']==key else s for s in state['source_catalog']] if old else state['source_catalog']+[item]
            state['document_revision'] += 1
            technical_change = action == 'delete_source' or old is None or normalized(old['text']) != normalized(item['text'])
            if technical_change:
                affected.add('source:'+key)
            for kind, objects in [('component', arch['components']), ('connection', arch['connections']), ('finding', state['analysis']['findings'])]:
                for obj in objects:
                    if technical_change and any(e['requirement_id']==key for e in obj.get('evidence', [])):
                        oid = kind+':'+obj['id']
                        state['stale_links'][oid] = sorted(set(state['stale_links'].get(oid, [])+[key]))
                        affected.add(oid)
            state['provenance']['source:'+key] = dict(origin='engineer_edit' if old else 'engineer_added', actor=command['actor'], reason=command['reason'], at=now())
        elif action == 'upsert_assumption':
            record = AssumptionRecord.model_validate(value).model_dump()
            existing = next((r for r in state['assumption_records'] if r['id']==key), None)
            if key and (not existing or record['id'] != key):
                raise ValueError('Varsayım kimliği bulunamadı veya değiştirildi.')
            if not key and any(r['id']==record['id'] for r in state['assumption_records']):
                raise ValueError('Varsayım kimliği zaten kullanılıyor.')
            if not record['text'].strip():
                raise ValueError('Varsayım metni boş olamaz.')
            for field, valid in [('source_ids', set(sources)), ('component_ids', components), ('connection_ids', connections)]:
                if set(record[field])-valid:
                    raise ValueError('Varsayım mevcut olmayan kayda bağlanamaz.')
            if record['status'] != 'pending' and not record['note'].strip():
                raise ValueError('Varsayım kararı için açıklama gerekli.')
            record.update(actor=command['actor'], at=now())
            accept_assumption_basis(state, record)
            state['assumption_records'] = [record if r['id']==key else r for r in state['assumption_records']] if existing else state['assumption_records']+[record]
            arch['assumptions'] = [r['text'] for r in state['assumption_records']]
        elif action in ('upsert_component', 'upsert_connection'):
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
                if technical_object(old) != technical_object(obj):
                    affected.update('component:' + x for x in [obj['source'], obj['target'], old.get('source', ''), old.get('target', '')] if x)
            put('components' if action == 'upsert_component' else 'connections', obj)
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
        elif action == 'apply_proposal':
            finding = next((f for f in state['analysis']['findings'] if f['id'] == key), None)
            if not finding or not finding.get('proposed_changes'):
                raise ValueError('Bu konuda uygulanabilir değişiklik önerisi yok.')
            topic = next(t for t in before_topics if t['finding_id'] == key)
            if (topic['decision'] or {}).get('status') == 'applied':
                raise ValueError('Bu öneri zaten uygulandı. Geri alarak yeniden düzenleyebilirsiniz.')
            current = fingerprint(proposal_context(arch, finding))
            base = state.get('proposal_bases', {}).get(key, fingerprint(proposal_context(original['architecture'], finding)))
            if current != base or value.get('fingerprint') != current or state['stale_links'].get('finding:'+key):
                raise ConflictError('Önerinin dayandığı öğeler değişti. Güncel tasarımı yeniden değerlendirin veya öğeyi elle düzenleyin.')
            changes = [ProposedChange.model_validate(c).model_dump() for c in value.get('changes', finding['proposed_changes'])]
            expected = [(c['action'], c['kind'], c['id']) for c in finding['proposed_changes']]
            if [(c['action'], c['kind'], c['id']) for c in changes] != expected:
                raise ValueError('Önerinin işlem ve hedefleri değiştirilemez; öğe alanlarını düzenleyebilirsiniz.')
            for c in changes:
                field = 'components' if c['kind'] == 'component' else 'connections'
                old = next((o for o in state['architecture'][field] if o['id'] == c['id']), None)
                if (c['action'] == 'add' and old) or (c['action'] != 'add' and not old):
                    raise ValueError('Önerideki öğe artık beklenen durumda değil.')
                obj = {**(old or {}), **c['value'], 'id':c['id']}
                state = self.apply(state, original, {**command, 'action':('delete_' if c['action']=='remove' else 'upsert_')+c['kind'], 'id':c['id'] if old else '', 'value':{'cascade':True} if c['action']=='remove' else obj})
            final = FinalModel.model_validate({**current_document(original, state), 'architecture':state['architecture'], 'analysis':state['analysis']})
            updated = next(t for t in build_topics(final, [], state['decisions']) if t['finding_id'] == key)
            state['decisions']['topic:'+topic['id']] = dict(status='applied', note=command['reason'], actor=command['actor'], at=now(), stale=False, fingerprint=updated['fingerprint'], fingerprint_version=3, dependency_snapshot=updated['dependency_snapshot'])
            return upgrade_state(state, original)
        elif action == 'append_review':
            analysis = AnalysisResult.model_validate(value['analysis']).model_dump()
            if value.get('workspace_fingerprint') and value['workspace_fingerprint'] != incoming_workspace:
                raise ConflictError('Değerlendirme sırasında TİD veya mühendis kararları değişti. Yeniden değerlendirin.')
            if value.get('architecture_fingerprint') != fingerprint(arch):
                raise ConflictError('Değerlendirme sırasında tasarım değişti. Önerileri güncel tasarımla yeniden isteyin.')
            for f in analysis['findings']:
                f['id'] = 'review_'+uuid.uuid4().hex[:16]
                try:
                    verify_evidence(f)
                except ValueError as exc:
                    raise ReviewIntakeError('QUOTE_MISMATCH', 'Model bulgusundaki alıntı kaynakla eşleşmiyor. Ayrıntılı model çıktısı teşhis kaydında korunuyor.') from exc
                if set(f['related_component_ids']) - components or set(f['related_connection_ids']) - connections:
                    raise ReviewIntakeError('OBJECT_UNKNOWN', 'Model bulgusu şemada bulunmayan bir öğeye başvuruyor. Mevcut çalışma korundu.')
                if any(finding_key(old) == finding_key(f) for old in state['analysis']['findings']):
                    continue
                state['analysis']['findings'].append(f)
                state.setdefault('proposal_bases', {})[f['id']] = fingerprint(proposal_context(arch, f))
                state.setdefault('proposal_contexts', {})[f['id']] = proposal_context(arch, f)
            for field in ('missing_information','open_questions'):
                state['analysis'][field] = list(dict.fromkeys(state['analysis'].get(field, [])+analysis[field]))
            state['last_review_at'] = now()
        elif action == 'set_topic_decision':
            final = FinalModel.model_validate({**current_document(original, state), 'architecture':arch, 'analysis':state['analysis']})
            topics = build_topics(final, [], state['decisions'])
            topic = next((t for t in topics if t['id']==key), None)
            if not topic:
                raise ValueError('İncelenecek konu bulunamadı. Listeyi yenileyin.')
            status = value.get('status')
            if status not in ('resolved','accepted','rejected','needs_review','merged','waiting'):
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
            state['decisions']['topic:'+key]=dict(status=status, note=command['reason'], actor=command['actor'], at=now(), stale=False, fingerprint=topic['fingerprint'], fingerprint_version=3, dependency_snapshot=topic['dependency_snapshot'], snapshot=snapshot, merged_into=target)
            # Calculate the newly selected merge dependency, including any target chain.
            updated=next(t for t in build_topics(final,[],state['decisions']) if t['id']==key)
            state['decisions']['topic:'+key]['fingerprint']=updated['fingerprint']
            state['decisions']['topic:'+key]['dependency_snapshot']=updated['dependency_snapshot']
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
            if kind == 'assumption':
                record = state['assumption_records'][int(oid)]
                record.update(status={'approved':'accepted','rejected':'rejected','needs_review':'pending'}[status],note=command['reason'],actor=command['actor'],at=now())
                accept_assumption_basis(state, record)
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
            state['assumption_records'][index]['text'] = text
            affected.add('assumption:' + key)
        elif action == 'layout':
            if set(value) - components:
                raise ValueError('Yerleşimde bulunmayan bileşen var.')
            for point in value.values():
                if not isinstance(point, dict) or set(point) != {'x', 'y'} or any(not isinstance(n, (float, int)) or not math.isfinite(n) or abs(n) > 100000 for n in point.values()):
                    raise ValueError('Geçersiz şema konumu.')
            state['positions'].update(value)
        else:
            raise ValueError('Desteklenmeyen işlem.')
        for decision_key in affected:
            if decision_key in state['decisions']:
                state['decisions'][decision_key]['stale'] = True
                state['decisions'][decision_key]['stale_reason'] = 'İlişkili mimari veya dayanak değişti; önceki kararı yeniden değerlendirin.'
        # Topic decisions track only their own dependencies; unrelated edits do not reopen them.
        final = FinalModel.model_validate({**current_document(original, state),'architecture':arch,'analysis':state['analysis']})
        for topic in build_topics(final,[],state['decisions']):
            decision_key='topic:'+topic['id']
            if decision_key in state['decisions']:
                state['decisions'][decision_key]['stale']=bool(topic['decision'].get('stale')) if topic['active'] else False
                if topic['active'] and topic['decision'].get('stale'):
                    state['decisions'][decision_key]['stale_reason']=topic['decision']['stale_reason']
        return upgrade_state(state, original)

    def apply_commands(self, state, original, commands, actor, reason, assumption_reviews=None):
        allowed = {'upsert_component', 'upsert_connection', 'delete_component', 'delete_connection',
                   'upsert_source', 'delete_source', 'upsert_assumption', 'set_assumption',
                   'set_topic_decision', 'set_decision', 'apply_proposal', 'add_finding', 'edit_finding'}
        if not isinstance(commands, list) or not 1 <= len(commands) <= 40:
            raise ValueError('Bir pakette 1–40 değişiklik olmalı.')
        for command in commands:
            if not isinstance(command, dict) or command.get('action') not in allowed:
                raise ValueError('Bu işlem değişiklik paketinde desteklenmiyor.')
            if set(command) - {'action', 'id', 'value', 'reason'}:
                raise ValueError('Değişiklikte beklenmeyen alan var.')
            state = self.apply(state, original, {**command, 'actor':actor, 'reason':command.get('reason') or reason})
        # An explicit decision in this package is based on the final previewed design.
        decided = {c.get('value', {}).get('id') for c in commands if c['action']=='upsert_assumption'}
        for record in state.get('assumption_records', []):
            if record['id'] in decided:
                for field, valid in [('source_ids', {s['requirement_id'] for s in state['source_catalog']}), ('component_ids', {o['id'] for o in state['architecture']['components']}), ('connection_ids', {o['id'] for o in state['architecture']['connections']})]:
                    if set(record[field])-valid:
                        raise ValueError('Kararın bağlı olduğu kayıt pakette kaldırılıyor. Varsayım bağlantılarını da düzenleyin.')
                accept_assumption_basis(state, record)
        choices = assumption_reviews or {}
        records = {r['id']: r for r in state.get('assumption_records', [])}
        if not isinstance(choices, dict) or any(key not in records or choice not in ('review', 'keep') for key, choice in choices.items()):
            raise ValueError('Yeniden inceleme seçiminde geçersiz varsayım veya seçenek var.')
        for key, choice in choices.items():
            record = records[key]
            if record['status'] == 'pending':
                raise ValueError('Henüz karar verilmemiş varsayım zaten inceleme bekliyor.')
            if choice == 'keep':
                accept_assumption_basis(state, record)
            record['impact_review'] = dict(action=choice, actor=actor, at=now(), reason=reason)
        return upgrade_state(state, original)

    def preview(self, pid, version, commands, actor, reason, assumption_reviews=None):
        project = self.get(pid)
        if project['version'] != version:
            raise ConflictError('Çalışma değişti. Güncel sürümü açıp yeniden önizleyin.')
        if not actor.strip() or not reason.strip():
            raise ValueError('Mühendis ve değişiklik açıklaması gerekli.')
        automatic = self.apply_commands(project['state'], project['original'], commands, actor, reason)
        after = self.apply_commands(project['state'], project['original'], commands, actor, reason, assumption_reviews) if assumption_reviews else automatic
        previous = {r['id']: r for r in project['state']['assumption_records']}
        design_changed = any(c['kind'] in ('component', 'connection', 'requirement') for c in impact_summary(project['state'], automatic)['changes'])
        candidates = [dict(id=r['id'], text=r['text'], status=r['status'],
                           suggested='review' if r['stale'] else 'keep', reason=r['stale_reason'],
                           affected=r['stale'] or r != previous.get(r['id']))
                      for r in automatic['assumption_records'] if r['status'] != 'pending' and design_changed]
        preview_id = uuid.uuid4().hex
        with self.db() as db:
            db.execute('INSERT INTO change_previews(id,project_id,version,commands,actor,reason,created,assumption_reviews) VALUES(?,?,?,?,?,?,?,?)',
                       (preview_id, pid, version, dump(commands), actor, reason, now(), dump(assumption_reviews or {})))
            db.execute('DELETE FROM change_previews WHERE project_id=? AND id NOT IN (SELECT id FROM change_previews WHERE project_id=? ORDER BY created DESC LIMIT 30)', (pid,pid))
        return dict(id=preview_id, version=version, reason=reason, commands=commands,
                    assumption_reviews=assumption_reviews or {}, assumption_review_candidates=candidates,
                    **impact_summary(project['state'], after))

    def save_conversation(self, pid, turn):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO conversations VALUES(?,?,?)', (pid, turn['id'], dump(turn)))

    def conversation(self, pid):
        with self.db() as db:
            return [json.loads(r['payload']) for r in db.execute('SELECT payload FROM conversations WHERE project_id=? ORDER BY rowid', (pid,))]

    def save_job(self, payload):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?)', (payload['id'], dump(payload)))

    def jobs(self):
        with self.db() as db:
            return sorted([json.loads(r['payload']) for r in db.execute('SELECT payload FROM jobs')], key=lambda x: x['created'], reverse=True)
