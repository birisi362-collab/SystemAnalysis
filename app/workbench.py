"""Loopback-only web API and packaged React application for engineering review."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
import io
import json
from pathlib import Path
import secrets
import tempfile
import threading
from urllib.parse import urlsplit
import uuid
import zipfile

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .llm_client import FixtureClient, LLMClient
from .models import FinalModel
from .pipeline import run
from .renderer import write_outputs
from .review_store import ReviewStore, ConflictError, now
from .settings import ROOT, load_settings


class ImportBody(BaseModel):
    path: str = Field(min_length=1)


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=0)
    action: str
    actor: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=5000)
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


def create_app(data_dir=None, dist_dir=None):
    store = ReviewStore(Path(data_dir or ROOT/'workbench_data')/'reviews.sqlite3')
    dist = Path(dist_dir or ROOT/'web/dist')
    token = secrets.token_urlsafe(32)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='architecture-analysis')
    job_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        for job in store.jobs():
            if job['status'] in ('queued', 'running'):
                job.update(status='interrupted', message='Uygulama kapanmış. Yeni analiz başlatabilirsiniz; önceki teşhis dosyaları korunuyor.')
                store.save_job(job)
        yield
        executor.shutdown(wait=False, cancel_futures=True)

    api = FastAPI(title='Mimari Atölyesi', docs_url=None, redoc_url=None, lifespan=lifespan)
    api.state.store = store
    api.state.token = token
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', 'testserver'])

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
        return dict(token=token, projects=store.list(), runs=runs, profiles=profiles(), jobs=store.jobs(), root=str(ROOT), version='1.2', demo_input=str(ROOT/'examples/iha_rad_sample.txt'))

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
        final.run_metadata['validation_error_count'] = sum(i.severity == 'error' for i in final.validation_issues)
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
            job = dict(id=jid, created=now(), status='queued', message='Analiz hazırlanıyor.', input_name=source.name, output_path=str(out), project_id=None, mode='fixture' if body.demo else 'live')
            store.save_job(job)

        def worker():
            try:
                job['status'] = 'running'
                store.save_job(job)
                def progress(message):
                    job['message'] = message
                    store.save_job(job)
                client = FixtureClient(ROOT/'evaluation/cases/dev_01.fixture.json') if body.demo else LLMClient(**cfg)
                final = run(str(source), str(out), client, two_pass=body.two_pass, progress=progress)
                project = store.import_run(out)
                job.update(status='completed' if final.review_status != 'failed' else 'partial', project_id=project['id'], message='İnceleme hazır.' if final.review_status != 'failed' else 'Mimari hazır; ikinci model incelemesi başarısız. İlk çıktı korunuyor.')
            except Exception as exc:
                job.update(status='failed', error_code=getattr(exc, 'code', type(exc).__name__), message='Analiz tamamlanamadı. Çıktı klasöründeki run_record.json kaydını kontrol edin.')
            finally:
                store.save_job(job)
                cfg.pop('api_key', None)
        executor.submit(worker)
        return job

    @api.get('/api/jobs/{jid}')
    def job(jid: str):
        found = next((j for j in store.jobs() if j['id'] == jid), None)
        if found is None:
            raise KeyError('Analiz kaydı bulunamadı.')
        return found

    if (dist/'assets').exists():
        api.mount('/assets', StaticFiles(directory=dist/'assets'), name='assets')

    @api.get('/')
    def index():
        if not (dist/'index.html').exists():
            return JSONResponse({'detail': 'Arayüz derlenmemiş. web klasöründe npm ci ve npm run build çalıştırın.'}, status_code=503)
        return FileResponse(dist/'index.html', headers={'Cache-Control': 'no-cache'})

    return api
