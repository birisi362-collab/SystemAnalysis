"""File-path entry shared by editor launchers; no Streamlit or upload required."""
from datetime import datetime
from pathlib import Path
import os
from .llm_client import from_environment
from .pipeline import run

ROOT = Path(__file__).resolve().parents[1]


def resolve_path(value):
    path = Path(os.path.expandvars(str(value))).expanduser()
    return path if path.is_absolute() else ROOT / path


def run_from_path(input_file, output_root='', profile_file='profiles/internal_example.json',
                  two_pass=True, overrides=None, client=None):
    if not str(input_file).strip():
        raise ValueError('INPUT_FILE boş. run_from_path.py içindeki INPUT_FILE alanına dokümanın tam yolunu yazın.')
    source = resolve_path(input_file)
    if not source.is_file():
        raise FileNotFoundError(f'Doküman bulunamadı: {source}')
    if source.suffix.lower() not in ('.txt', '.docx', '.pdf'):
        raise ValueError('Desteklenen dosyalar: .txt, .docx, .pdf')
    # Resolve relative paths against project, independent of VS Code terminal cwd.
    parent = resolve_path(output_root) if str(output_root).strip() else ROOT / 'outputs'
    if client is None:
        client = from_environment(resolve_path(profile_file))
        # Explicit Python settings take precedence over profile and environment.
        for name, value in (overrides or {}).items():
            if value is not None:
                if name not in {'base_url', 'model', 'api_key', 'ca_bundle', 'chat_completions_url',
                                'chat_completions_path', 'timeout', 'max_tokens', 'json_mode'}:
                    raise ValueError(f'Unsupported connection setting: {name}')
                setattr(client, name, value.rstrip('/') if name == 'base_url' else value)
        if 'YOUR-' in client.model or 'YOUR-' in client.base_url:
            raise ValueError('İç ağ bağlantısı henüz tanımlı değil. BASE_URL ve MODEL alanlarını veya seçilen profil dosyasını düzenleyin.')
    out = parent / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    print(f'Girdi: {source}\nÇıktı: {out}\nModel: {client.model}')
    try:
        result = run(str(source), str(out), client, two_pass=two_pass, progress=print)
    except Exception:
        print(f'Analiz tamamlanamadı. Varsa teşhis kaydı: {out / "run_record.json"}')
        raise
    print(f'\nRapor: {out / "report.html"}')
    print(f'JSON: {out / "analysis_result.json"}')
    print(f'İkinci tur: {result.review_status}; doğrulama kaydı: {len(result.validation_issues)}')
    return result, out
