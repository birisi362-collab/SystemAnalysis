"""Loopback-only web API and packaged React application for engineering review."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
import io
import json
from pathlib import Path
import secrets
import tempfile
import threading
import time
from urllib.parse import urlsplit
import uuid
import zipfile

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .llm_client import FixtureClient, LLMClient, LLMError
from .models import FinalModel, AnalysisResult, ArchitectureModel
from .requirement_catalog import RequirementEntry
from .review_topics import fingerprint
from .pipeline import run
from .renderer import write_outputs
from .review_store import ReviewStore, ConflictError, ReviewIntakeError, now
from .settings import ROOT, load_settings
from .review_runner import run_review


class ImportBody(BaseModel):
    path: str = Field(min_length=1)


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=0)
    action: str
    actor: str = Field(min_length=1, max_length=120)
    reason: str = Field(default='', max_length=5000)
    id: str = ''
    value: dict = Field(default_factory=dict)


class AnalysisBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_path: str = ''
    profile: str = 'openrouter_nemotron'
    demo: bool = False
    two_pass: bool = True
    timeout: int = Field(default=600, ge=10, le=1800)
    max_tokens: int = Field(default=8192, ge=512, le=65536)
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    retry_job_id: str | None = None

def review_failure(exc):
    code = getattr(exc, 'code', type(exc).__name__)
    messages = {
        'PROVIDER_ERROR':'Model sağlayıcısı inceleme çağrısında hata döndürdü. Bir süre sonra yeniden deneyin veya farklı model profili seçin.',
        'RATE_LIMIT':'Model hizmetinin kota veya istek sınırına ulaşıldı. Bir süre bekleyin ya da hesabınızdaki kotayı kontrol edin.',
        'SERVICE_UNAVAILABLE':'Model hizmeti şu anda isteği tamamlayamıyor. Daha sonra yeniden deneyin veya farklı profil seçin.',
        'AUTHENTICATION':'API anahtarı kabul edilmedi. Seçtiğiniz sağlayıcının geçerli anahtarını girin.',
        'ACCESS_DENIED':'Hesabınızın seçilen modele erişimi yok. Model erişimini kontrol edin veya başka profil seçin.',
        'ENDPOINT_OR_MODEL':'Model veya servis adresi bulunamadı. Profildeki model adını ve adresi kontrol edin.',
        'TRUNCATED':'Model yanıtı çıktı sınırına ulaştığı için yarıda kesildi. Gelişmiş seçeneklerde çıktı token sınırını artırın.',
        'TIMEOUT':'Model incelemesi süre sınırını aştı. Gelişmiş seçeneklerde süreyi artırıp yeniden deneyin.',
        'TIME_BUDGET':'Toplam değerlendirme süresi doldu. Tamamlanan sonuçlar saklandı; eksik bölümleri yeniden deneyebilirsiniz.',
        'CANCELLED':'Değerlendirme durduruldu. Tamamlanan sonuçlar ve kalan bölümler saklandı.',
        'TLS_RUNTIME':'Python güvenli bağlantı ortamı durdu. Uygulama korunuyor; run_app.bat ile doğrulanmış ortamda yeniden açın.',
        'WORKER_EXIT':'Model bağlantı işlemi beklenmedik biçimde durdu. Uygulama korunuyor; teşhis ayrıntılarını kontrol edin.',
        'NETWORK':'Model hizmetine ulaşılamadı. İnternet veya kurum ağı bağlantısını kontrol edin.',
        'TLS':'Model hizmetinin güvenli bağlantısı doğrulanamadı. Kurumunuzun onaylı sertifika ayarlarını kontrol edin.',
        'INVALID_JSON':'Model geçerli JSON üretmedi. İncelemeyi yeniden deneyin veya farklı profil seçin.',
        'REQUEST_FORMAT':'Model hizmeti gönderilen ayarları kabul etmedi. Değerlendirme ayrıntılarında sağlayıcının yanıtını kontrol edin.',
        'HTTP_ERROR':'Model hizmeti HTTP hatası döndürdü. Değerlendirme ayrıntılarını kontrol edin.',
        'RESPONSE_FORMAT':'Model hizmeti beklenen yanıt biçimini döndürmedi.',
        'QUOTE_MISMATCH':'Modelin alıntısı kaynakla eşleşmedi. Kullanılamayan sonuç teşhis kaydında saklandı.',
        'OBJECT_UNKNOWN':'Model şemada bulunmayan bir öğeye başvurdu. Kullanılamayan sonuç teşhis kaydında saklandı.',
        'CALL_LIMIT':'Kalan bölümler çağrı sınırı nedeniyle incelenmedi. Eksik bölümleri yeniden deneyebilirsiniz.',
        'EMPTY_CONTENT':'Model kullanılabilir bir sonuç döndürmedi. Yeniden deneyin veya başka profil seçin.',
        'SCHEMA':'Model yanıtı beklenen inceleme biçimine uymuyor. Yeniden deneyin veya farklı profil seçin.',
        'ValidationError':'Model yanıtı beklenen inceleme biçimine uymuyor. Yeniden deneyin veya farklı profil seçin.',
        'UnicodeEncodeError':'İstek ayarlarında kodlanamayan bir karakter var. API anahtarını, model adını ve servis adresini yeniden kontrol edin.',
    }
    message = str(exc) if isinstance(exc, (ConflictError, ReviewIntakeError)) or (isinstance(exc, LLMError) and code == 'INVALID_HEADER') else messages.get(code,'Model sonucu uygulamada işlenirken hata oluştu. Değerlendirme ayrıntılarındaki teşhis kaydını kontrol edin.')
    return code, message + ' Mevcut tasarım ve mühendis kararları korundu.'


def job_view(job):
    # Full prompts and quarantined model output are available only in the detail view.
    return {k:v for k,v in job.items() if k != 'review_report'}


def create_app(data_dir=None, dist_dir=None):
    store = ReviewStore(Path(data_dir or ROOT/'workbench_data')/'reviews.sqlite3')
    dist = Path(dist_dir or ROOT/'web/dist')
    token = secrets.token_urlsafe(32)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='architecture-analysis')
    job_lock = threading.Lock()
    controls = {}

    @asynccontextmanager
    async def lifespan(app):
        for job in store.jobs():
            if job['status'] in ('queued', 'running'):
                job.update(status='interrupted', message='Uygulama kapanmış. Yeni analiz başlatabilirsiniz; önceki teşhis dosyaları korunuyor.')
                if job.get('review_report'):
                    report = job['review_report']
                    report['retry_tasks'] += report.get('remaining_tasks', [])
                    report['remaining_tasks'] = []
                    report['finalization_pending'] = True
                    job['can_retry_missing'] = True
                    job['message'] = 'Değerlendirme uygulama kapanınca durdu. Tamamlanan bölüm sonuçları saklandı; eksik bölümleri yeniden deneyebilirsiniz.'
                store.save_job(job)
        yield
        for event in list(controls.values()):
            event.set()
        executor.shutdown(wait=False, cancel_futures=True)

    api = FastAPI(title='Mimari Atölyesi', docs_url=None, redoc_url=None, lifespan=lifespan)
    api.state.store = store
    api.state.token = token
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', 'testserver'])

    @api.get('/api/instance')
    def instance():
        return dict(app='system-architecture-analyzer-workbench', root=str(ROOT.resolve()), data_dir=str(store.path.parent.resolve()))

    @api.middleware('http')
    async def local_requests(request: Request, call_next):
        if request.url.path.startswith('/api/'):
            if request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail': 'Yalnızca yerel uygulamadan erişim kabul edilir.'}, status_code=403)
            origin = request.headers.get('origin')
            if origin and urlsplit(origin).netloc != request.headers.get('host'):
                return JSONResponse({'detail': 'İstek aynı uygulama adresinden gelmeli.'}, status_code=403)
            if request.method not in ('GET', 'HEAD', 'OPTIONS') and not secrets.compare_digest(request.headers.get('x-workbench-token', ''), token):
                return JSONResponse({'detail': 'Uygulama oturumu yenilenmiş. Sayfayı yenileyin.'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @api.exception_handler(ConflictError)
    async def conflict(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @api.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({'detail': str(exc).strip("'")}, status_code=404)

    @api.exception_handler(ValueError)
    async def invalid(request, exc):
        message = 'Dosya veya alanlar beklenen biçimde değil.' if isinstance(exc, ValidationError) else str(exc)
        return JSONResponse({'detail': message}, status_code=422)

    @api.exception_handler(OSError)
    async def file_error(request, exc):
        return JSONResponse({'detail': 'Dosya okunamadı veya yazılamadı. Yolu ve erişim iznini kontrol edin.'}, status_code=422)

    def profiles():
        result = []
        for path in sorted((ROOT/'profiles').glob('*.json')):
            cfg = load_settings(path)
            result.append(dict(id=path.stem, model=cfg.get('model', ''), base_url=cfg.get('base_url', ''), has_key=bool(cfg.get('api_key')), timeout=cfg.get('timeout', 180)))
        return result

    @api.get('/api/bootstrap')
    def bootstrap():
        runs = []
        for path in sorted((ROOT/'outputs').glob('*/analysis_result.json'), reverse=True):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                runs.append(dict(path=str(path.parent), name=data['architecture']['system_name'], run=path.parent.name, model=data.get('run_metadata', {}).get('settings', {}).get('model', 'Bilinmiyor')))
            except (OSError, ValueError, KeyError):
                continue
        return dict(token=token, projects=store.list(), runs=runs, profiles=profiles(), jobs=[job_view(j) for j in store.jobs()], root=str(ROOT), version='2.0', demo_input=str(ROOT/'examples/iha_rad_sample.txt'))

    @api.get('/api/projects')
    def projects():
        return store.list()

    @api.post('/api/projects/import')
    def import_project(body: ImportBody):
        path = Path(body.path.strip().strip('"')).expanduser()
        if not path.is_absolute():
            path = ROOT/path
        return store.import_run(path)

    @api.get('/api/projects/{pid}')
    def project(pid: str):
        return store.get(pid)

    @api.post('/api/projects/{pid}/changes')
    def change(pid: str, body: Command):
        return store.mutate(pid, body.model_dump())

    @api.get('/api/projects/{pid}/export')
    def export(pid: str):
        project = store.get(pid)
        state = project['state']
        final = FinalModel.model_validate({**project['original'], 'architecture': state['architecture'], 'analysis': state['analysis'], 'validation_issues': [{k:v for k,v in i.items() if k in {'severity','code','message','related_id','source_id','object_id','finding_id'}} for i in project['issues']]})
        final.run_metadata.update(engineering_review_version=project['version'], original_sha256=project['origin_hash'], human_review_required=True)
        final.run_metadata.pop('validation_error_count', None)
        final.run_metadata['validation_mode'] = 'editing_integrity_only'
        content = io.BytesIO()
        with tempfile.TemporaryDirectory() as directory:
            write_outputs(final, directory)
            root = Path(directory)
            (root/'original_analysis_result.json').write_text(json.dumps(project['original'], ensure_ascii=False, indent=2), encoding='utf-8')
            (root/'engineering_review.json').write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding='utf-8')
            (root/'OKU.txt').write_text('analysis_result ve şema dosyaları mühendis çalışma kopyasıdır. original_analysis_result değişmez model çıktısıdır. Kararlar, varsayımlar, yerleşim ve değişiklik geçmişi engineering_review.json içindedir. Onaylar alan bazındadır; dışa aktarma mühendis onayı anlamına gelmez.', encoding='utf-8')
            with zipfile.ZipFile(content, 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in root.iterdir():
                    archive.writestr(path.name, path.read_bytes())
        return Response(content.getvalue(), media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="architecture_review_v{project["version"]}.zip"'})

    @api.post('/api/analysis')
    def analysis(body: AnalysisBody):
        valid_profiles = {p['id'] for p in profiles()}
        if body.profile not in valid_profiles:
            raise ValueError('Profil bulunamadı.')
        source = ROOT/'evaluation/cases/dev_01.txt' if body.demo else Path(body.input_path.strip().strip('"')).expanduser()
        if not source.is_absolute():
            source = ROOT/source
        if not source.is_file() or source.suffix.lower() not in {'.txt', '.docx', '.pdf'}:
            raise ValueError('Okunabilir bir TXT, DOCX veya PDF dosya yolu gerekli.')
        # Credentials live only in this worker closure, never in the job database or browser response.
        cfg = load_settings(ROOT/f'profiles/{body.profile}.json')
        cfg.update(timeout=body.timeout, max_tokens=body.max_tokens)
        for key in ('base_url', 'model', 'api_key'):
            supplied = getattr(body, key)
            if supplied:
                cfg[key] = supplied
        if not body.demo and ('YOUR-' in cfg.get('model', '') or 'YOUR-' in cfg.get('base_url', '')):
            raise ValueError('İç ağ profili için gerçek sunucu ve model bilgisini girin.')
        with job_lock:
            if any(j['status'] in ('queued', 'running') for j in store.jobs()):
                raise HTTPException(409, 'Bir analiz zaten çalışıyor. Tamamlanmasını bekleyin.')
            jid = uuid.uuid4().hex
            out = ROOT/'outputs'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            job = dict(id=jid, created=now(), status='queued', message='Analiz hazırlanıyor.', input_name=source.name, output_path=str(out), project_id=None, mode='fixture' if body.demo else 'live', max_tokens=cfg['max_tokens'], timeout=cfg['timeout'])
            controls[jid]=threading.Event()
            store.save_job(job)

        def worker():
            try:
                job['status'] = 'running'
                job['started_at']=now()
                store.save_job(job)
                def progress(message):
                    job['message'] = message
                    report_path=out/'review_diagnostics.json'
                    if report_path.exists():
                        report=json.loads(report_path.read_text(encoding='utf-8'))
                        job.update(active_section=report.get('active_section'), completed_sections=sum(s['status'] in ('completed','partial') for s in report['sections']), total_sections=report.get('total_sections'))
                    store.save_job(job)
                client = FixtureClient(ROOT/'evaluation/cases/dev_01.fixture.json') if body.demo else LLMClient(**cfg,isolate=True,cancel_event=controls[jid],deadline=time.monotonic()+cfg['timeout'])
                final = run(str(source), str(out), client, two_pass=body.two_pass, progress=progress)
                project = store.import_run(out)
                job.update(status='partial' if final.review_status in ('failed','partial') else 'completed', project_id=project['id'], message='İnceleme hazır.' if final.review_status not in ('failed','partial') else 'Mimari hazır; değerlendirme kısmen tamamlandı. Kullanılabilir bulgular korundu; ayrıntıları inceleyebilirsiniz.')
                report_path=out/'review_diagnostics.json'
                if report_path.exists():
                    report=json.loads(report_path.read_text(encoding='utf-8'))
                    job.update(review_report=report, calls=report['calls'], accepted_findings=len(report['analysis']['findings']), excluded_findings=len(report['excluded']), added_findings=len(report['analysis']['findings']), can_retry_missing=bool(report['retry_tasks']), architecture_fingerprint=fingerprint(project['state']['architecture']))
                    calls=[c for s in report['sections'] for c in s.get('transport',[])]
                    job['token_usage']={k:sum((c.get('usage') or {}).get(k,0) or 0 for c in calls) for k in ('prompt_tokens','completion_tokens','total_tokens')}
                    failure=next((s for s in reversed(report['sections']) if s.get('error_code')),None)
                    if failure:
                        code, explanation=review_failure(LLMError(failure['error_code'],'Review incomplete'))
                        job.update(error_code=code,message='Mimari hazır. '+explanation)
            except Exception as exc:
                code = getattr(exc, 'code', type(exc).__name__)
                fallback=review_failure(exc)[1] if isinstance(exc,LLMError) else 'Analiz tamamlanamadı. Belgeyi ve model bağlantısını kontrol edip Belge aç ile yeniden deneyin.'
                message = {'EMPTY_DOCUMENT':'Belgede okunabilir metin bulunamadı. Metin içeren bir TXT, DOCX veya PDF seçin.', 'INPUT_BUDGET':'Belge bu analiz için çok uzun. Anlamlı bölümlere ayırıp yeniden yükleyin.'}.get(code, fallback)
                if code=='CANCELLED':
                    message='Analiz durduruldu. Mimari çıkarımı tamamlanmadı; Belge aç ile yeniden başlatabilirsiniz.'
                job.update(status='cancelled' if code=='CANCELLED' else 'failed', error_code=code, message=message)
            finally:
                job['finished_at']=now()
                job['active_section']=None
                controls.pop(jid,None)
                store.save_job(job)
                cfg.pop('api_key', None)
        executor.submit(worker)
        return job

    @api.post('/api/documents')
    async def upload_document(request: Request, name: str):
        suffix = Path(name).suffix.lower()
        if suffix not in {'.txt', '.docx', '.pdf', '.zip'}:
            raise ValueError('TXT, DOCX, PDF veya çalışma paketi ZIP seçin.')
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 25 * 1024 * 1024:
                raise ValueError('Dosya en fazla 25 MB olabilir.')
        if not data:
            raise ValueError('Seçilen dosya boş.')
        folder = store.path.parent/'documents'/uuid.uuid4().hex
        folder.mkdir(parents=True)
        # Keep a readable name inside a unique owned directory; never use a supplied path.
        label = Path(name.replace('\\','/')).name
        label = ''.join(c for c in label if c not in '<>:"/\\|?*' and ord(c) >= 32).strip('. ')[:160]
        if not label or Path(label).stem.upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
            label = 'document'+suffix
        if Path(label).suffix.lower() != suffix: label = Path(label).stem+suffix
        destination = folder/label
        destination.write_bytes(data)
        if suffix == '.zip':
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    info = z.getinfo('engineering_review.json')
                    if info.file_size > 50 * 1024 * 1024:
                        raise ValueError('Çalışma paketi çok büyük.')
                    snapshot = json.loads(z.read(info))
            except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
                raise ValueError('Bu dosya geçerli bir çalışma paketi değil.') from exc
            return dict(project=store.restore_snapshot(snapshot))
        return dict(path=str(destination), name=Path(name.replace('\\','/')).name)

    @api.post('/api/projects/{pid}/review')
    def review_project(pid: str, body: AnalysisBody):
        project = store.get(pid)
        if body.profile not in {p['id'] for p in profiles()}:
            raise ValueError('Profil bulunamadı.')
        cfg = load_settings(ROOT/f'profiles/{body.profile}.json')
        cfg.update(timeout=body.timeout, max_tokens=body.max_tokens)
        for key in ('base_url','model','api_key'):
            if getattr(body,key): cfg[key] = getattr(body,key)
        entries = [RequirementEntry(**s) for s in project['original']['source_catalog']]
        architecture = ArchitectureModel.model_validate(project['state']['architecture'])
        base_fingerprint = fingerprint(project['state']['architecture'])
        previous = None
        if body.retry_job_id:
            previous = next((j for j in store.jobs() if j['id'] == body.retry_job_id), None)
            if not previous or previous.get('project_id') != pid or not (previous.get('review_report', {}).get('retry_tasks') or previous.get('review_report', {}).get('finalization_pending')):
                raise ValueError('Yeniden denenebilecek eksik değerlendirme bulunamadı.')
            if previous.get('architecture_fingerprint') != base_fingerprint:
                raise ConflictError('Tasarım değişti. Eksik bölümler yerine güncel tasarım için yeni değerlendirme başlatın.')
        with job_lock:
            if any(j['status'] in ('queued','running') for j in store.jobs()):
                raise HTTPException(409, 'Bir analiz zaten çalışıyor.')
            job = dict(id=uuid.uuid4().hex, created=now(), status='queued', project_id=pid, message='Güncel tasarım değerlendiriliyor.', mode='review', max_tokens=cfg['max_tokens'], timeout=cfg['timeout'], architecture_fingerprint=base_fingerprint, previous_job_id=body.retry_job_id, profile=body.profile, model=cfg.get('model'))
            controls[job['id']]=threading.Event()
            store.save_job(job)
        def worker_review():
            client = None
            report = None
            def checkpoint(value, message):
                job.update(review_report=deepcopy(value), message=message, calls=value['calls'], accepted_findings=len(value['analysis']['findings']), excluded_findings=len(value['excluded']),active_section=value.get('active_section'),completed_sections=sum(s['status'] in ('completed','partial') for s in value['sections']),total_sections=value.get('total_sections'))
                store.save_job(job)
            def check_proposal(changes):
                state = deepcopy(project['state'])
                for change in changes:
                    field = 'components' if change['kind'] == 'component' else 'connections'
                    old = next((o for o in state['architecture'][field] if o['id'] == change['id']), None)
                    if (change['action'] == 'add' and old) or (change['action'] != 'add' and not old):
                        raise ValueError('Önerideki işlem mevcut öğelerle uyuşmuyor.')
                    obj = {**(old or {}), **change['value'], 'id':change['id']}
                    state = store.apply(state, project['original'], dict(action=('delete_' if change['action']=='remove' else 'upsert_')+change['kind'], id=change['id'] if old else '', actor='Yapay zekâ', reason='Öneri ön kontrolü', value={'cascade':True} if change['action']=='remove' else obj))
            try:
                job.update(status='running',started_at=now()); store.save_job(job)
                client = LLMClient(**cfg,isolate=True,cancel_event=controls[job['id']],deadline=time.monotonic()+cfg['timeout'])
                prior = previous.get('review_report') if previous else None
                # No saved section means a crash happened before any result: use the current compact plan.
                retry_tasks=prior['retry_tasks'] if prior and prior['sections'] else None
                report = run_review(client, entries, architecture, check_proposal, checkpoint, tasks=retry_tasks, seed=prior['analysis'] if prior else None)
                if prior:
                    report['sections'].extend(s for s in prior['sections'] if s.get('error_code') == 'CROSS_REVIEW_LIMIT')
                checkpoint(report, 'Kullanılabilir bulgular kaydediliyor.')
                answered = any(s['status'] in ('completed', 'partial') for s in report['sections']) or bool(prior and prior.get('finalization_pending') and not prior['retry_tasks'])
                if answered:
                    current = store.get(pid)
                    updated = store.mutate(pid, dict(action='append_review', id='', actor='Yapay zekâ', reason='Mühendisin başlattığı değerlendirme', version=current['version'], value={'analysis':report['analysis'], 'architecture_fingerprint':base_fingerprint}))
                    job['added_findings'] = len(updated['state']['analysis']['findings']) - len(current['state']['analysis']['findings'])
                incomplete = bool(report['retry_tasks'] or report['excluded'] or any(s.get('cross_review_incomplete') or s['status']=='failed' for s in report['sections']))
                if not answered:
                    failure = next((s for s in reversed(report['sections']) if s.get('error_code')), {})
                    code, message = review_failure(LLMError(failure.get('error_code', 'SCHEMA'), 'Review failed'))
                    job.update(status='failed', error_code=code, message=message)
                    if code == 'TRUNCATED':
                        job['message'] = f"İnceleme yanıtı {cfg['max_tokens']:,} token sınırında yarıda kesildi. Küçük bölüm de tamamlanamadı; çıktı sınırını veya model profilini değiştirip eksik bölümleri yeniden deneyin. Mevcut tasarım ve mühendis kararları korundu."
                else:
                    count = job.get('added_findings', 0)
                    message = f'{count} yeni bulgu eklendi. '
                    message += 'Değerlendirme kısmen tamamlandı; ayrıntılarda eksik veya kullanılamayan sonuçları görebilirsiniz.' if incomplete else 'Değerlendirme tamamlandı.'
                    job.update(status='partial' if incomplete else 'completed', message=message)
                job['can_retry_missing'] = bool(report['retry_tasks'])
                if any(s.get('error_code')=='CANCELLED' for s in report['sections']):
                    job.update(status='partial' if answered else 'cancelled',message=f"Değerlendirme durduruldu. {job.get('added_findings',0)} yeni bulgu kaydedildi; kalan bölümler yeniden denenebilir.")
            except Exception as exc:
                code, message = review_failure(exc)
                if code == 'TRUNCATED':
                    message = f"İnceleme yanıtı {cfg['max_tokens']:,} token sınırında yarıda kesildi. Gelişmiş seçeneklerde çıktı token sınırını artırıp yeniden deneyin. Mevcut tasarım ve mühendis kararları korundu."
                job.update(status='failed', error_code=code, message=message)
                job['failure_detail'] = dict(code=code, message=str(exc) if isinstance(exc, (ConflictError, ReviewIntakeError, LLMError)) else 'Sonuç uygulamada işlenirken hata oluştu.', frames=[dict(file=Path(f.filename).name, line=f.lineno, function=f.name) for f in traceback.extract_tb(exc.__traceback__)])
            finally:
                job['finished_at']=now()
                job['active_section']=None
                controls.pop(job['id'],None)
                if client and client.calls:
                    last = client.calls[-1]
                    if isinstance(last, dict):
                        job['finish_reason'] = last.get('finish_reason')
                        usage = last.get('usage') or {}
                        calls = [c for c in client.calls if isinstance(c, dict)]
                        job['token_usage'] = {k:sum((c.get('usage') or {}).get(k, 0) or 0 for c in calls) for k in ('prompt_tokens','completion_tokens','total_tokens')}
                        job['reasoning_tokens'] = sum(((c.get('usage') or {}).get('completion_tokens_details') or {}).get('reasoning_tokens', 0) or 0 for c in calls)
                store.save_job(job); cfg.pop('api_key',None)
        executor.submit(worker_review)
        return job_view(job)

    @api.get('/api/jobs/{jid}')
    def job(jid: str):
        found = next((j for j in store.jobs() if j['id'] == jid), None)
        if found is None:
            raise KeyError('Analiz kaydı bulunamadı.')
        return job_view(found)

    @api.post('/api/jobs/{jid}/cancel')
    def cancel_job(jid: str):
        found=next((j for j in store.jobs() if j['id']==jid),None)
        if found is None:
            raise KeyError('Analiz kaydı bulunamadı.')
        event=controls.get(jid)
        if event:
            event.set()
        return dict(id=jid,cancel_requested=event is not None,status=found['status'])

    @api.get('/api/jobs/{jid}/diagnostics')
    def job_diagnostics(jid: str, download: bool = False):
        found = next((j for j in store.jobs() if j['id'] == jid), None)
        if found is None:
            raise KeyError('Analiz kaydı bulunamadı.')
        if download:
            return Response(json.dumps(found, ensure_ascii=False, indent=2), media_type='application/json', headers={'Content-Disposition':f'attachment; filename="review-{jid}.json"'})
        return found

    if (dist/'assets').exists():
        api.mount('/assets', StaticFiles(directory=dist/'assets'), name='assets')

    @api.get('/')
    def index():
        if not (dist/'index.html').exists():
            return JSONResponse({'detail': 'Arayüz derlenmemiş. web klasöründe npm ci ve npm run build çalıştırın.'}, status_code=503)
        return FileResponse(dist/'index.html', headers={'Cache-Control': 'no-cache'})

    return api
