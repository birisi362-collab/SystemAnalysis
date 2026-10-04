from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from pydantic import ValidationError
from .document_reader import read_blocks
from .requirement_catalog import build_catalog_blocks
from .llm_client import LLMError, prompt_hash
from .models import AnalysisResult, ArchitectureModel, FinalModel
from .prompts import EXTRACTION_SYSTEM_PROMPT, extraction_user_prompt
from .renderer import write_outputs
from .review_runner import run_review, check_proposed_changes

PROMPT_VERSION='v7.1'

def run(input_path,output_dir,llm,two_pass=True,progress=None,max_input_chars=60000):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()): raise ValueError('Output directory must be empty. Use a new run directory to avoid mixing results.')
    start=time.monotonic();exchanges=[]
    metadata={'app_version':'7.0','prompt_version':PROMPT_VERSION,
              'started_at':datetime.now(timezone.utc).isoformat(), 'settings':llm.settings(),
              'input_name':Path(input_path).name,'input_sha256':hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),
              'two_pass':two_pass,'run_status':'running'}
    def save():
        metadata['elapsed_seconds']=round(time.monotonic()-start,3)
        (out/'run_record.json').write_text(json.dumps({'metadata':metadata,'exchanges':exchanges,'transport_calls':llm.calls},ensure_ascii=False,indent=2),encoding='utf-8')
    def note(s):
        if progress: progress(s)
    def call(system,user):
        record={'prompt_hash':prompt_hash(system,user),'system_prompt':system,'user_prompt':user}
        exchanges.append(record)
        try:
            result=llm.extract_json(system,user);record['parsed']=result;return result
        except Exception as exc:
            record['error_code']=getattr(exc,'code',type(exc).__name__);raise
        finally: save()
    try:
        note('Doküman okunuyor; kaynak konumları korunuyor.')
        entries=build_catalog_blocks(read_blocks(input_path))
        if not entries: raise LLMError('EMPTY_DOCUMENT','Belgede okunabilir metin bulunamadı. Metin içeren bir TXT, DOCX veya PDF seçin.')
        catalog=[asdict(e) for e in entries]
        (out/'source_catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
        metadata['catalog_sha256']=hashlib.sha256(json.dumps(catalog,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        user=extraction_user_prompt(entries)
        if len(user)>max_input_chars: raise LLMError('INPUT_BUDGET','Document exceeds the configured character budget. Split by coherent sections; V6 does not silently truncate input.')
        note(f'{len(entries)} kaynak kaydı. Mimari çıkarılıyor...')
        arch=ArchitectureModel.model_validate(call(EXTRACTION_SYSTEM_PROMPT,user))
        analysis=AnalysisResult();review_status='skipped'
        # Preserve pass 1 even if pass 2 fails.
        (out/'architecture_pass1.json').write_text(arch.model_dump_json(indent=2),encoding='utf-8')
        if two_pass:
            note('Mimari kaynak metne karşı inceleniyor...')
            try:
                class RecordedReviewClient:
                    @property
                    def calls(self): return llm.calls
                    def extract_json(self, system, user): return call(system, user)
                def checkpoint(report, message):
                    (out/'review_diagnostics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                    note(message)
                report=run_review(RecordedReviewClient(),entries,arch,lambda changes:check_proposed_changes(arch,entries,changes),checkpoint)
                checkpoint(report,'Model değerlendirmesinin kullanılabilir sonuçları korunuyor.')
                analysis=AnalysisResult.model_validate(report['analysis'])
                answered=any(s['status'] in ('completed','partial') for s in report['sections'])
                incomplete=bool(report['retry_tasks'] or report['excluded'] or any(s.get('cross_review_incomplete') or s['status']=='failed' for s in report['sections']))
                review_status=('partial' if incomplete else 'completed') if answered else 'failed'
                if review_status=='failed':
                    metadata['review_error_code']=next((s['error_code'] for s in reversed(report['sections']) if s.get('error_code')), 'SCHEMA')
                    metadata['review_error']='Review did not produce a usable result; inspect review_diagnostics.json.'
            except (LLMError,ValidationError) as exc:
                review_status='failed';metadata['review_error_code']=getattr(exc,'code','SCHEMA')
                metadata['review_error']=str(exc) if isinstance(exc,LLMError) else 'Review schema validation failed; inspect recorded response.'
        issues=[]
        metadata['run_status']='partial' if review_status in ('failed','partial') else 'completed'
        metadata['validation_mode']='editing_integrity_only'
        metadata['human_review_required']=True
        metadata['elapsed_seconds']=round(time.monotonic()-start,3)
        final=FinalModel(architecture=arch,analysis=analysis,validation_issues=issues,
                         source_catalog=catalog,run_metadata=metadata,review_status=review_status)
        write_outputs(final,str(out));note('Tamamlandı. Sonuç mühendis incelemesi gerektirir.')
        return final
    except Exception as exc:
        metadata['run_status']='failed';metadata['error_code']=getattr(exc,'code',type(exc).__name__)
        raise
    finally: save()
