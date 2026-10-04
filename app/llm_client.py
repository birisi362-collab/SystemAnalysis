"""Bounded OpenAI-compatible transport. No automatic model/provider substitution."""
import hashlib
import json
import os
import re
import time
import subprocess
import sys
import sysconfig
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import requests

class LLMError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)

class LLMClient:
    def __init__(self, base_url, api_key='', model='', timeout=180, json_mode=False,
                 extra_headers=None, ca_bundle=None, verify_ssl=True, max_tokens=8192,
                 include_reasoning=None, chat_completions_path='/chat/completions',
                 chat_completions_url=None, max_retries=1, isolate=False, cancel_event=None, deadline=None, **kwargs):
        self.base_url=base_url.strip().rstrip('/'); self.api_key=api_key.strip(); self.model=model.strip()
        self.timeout=timeout; self.json_mode=json_mode; self.max_tokens=max_tokens
        self.extra_headers={k:v for k,v in (extra_headers or {}).items() if v}
        self.ca_bundle=ca_bundle; self.verify_ssl=verify_ssl; self.include_reasoning=include_reasoning
        self.chat_completions_path=chat_completions_path; self.chat_completions_url=chat_completions_url
        self.max_retries=max_retries; self.calls=[]
        self.isolate=isolate; self.cancel_event=cancel_event; self.deadline=deadline
        self.session=requests.Session()

    @property
    def verify(self):
        return self.ca_bundle or True if self.verify_ssl else False

    @property
    def chat_url(self):
        return self.chat_completions_url or self.base_url + '/' + self.chat_completions_path.lstrip('/')

    def settings(self):
        url=urlsplit(self.chat_url)
        return dict(model=self.model, endpoint=urlunsplit((url.scheme,url.hostname or '',url.path,'','')),
                    timeout=self.timeout, json_mode=self.json_mode, max_tokens=self.max_tokens,
                    max_retries=self.max_retries, temperature=0, include_reasoning=self.include_reasoning,
                    tls_verified=self.verify_ssl)

    def extract_json(self, system_prompt, user_prompt):
        if self.isolate:
            return self._isolated_json(system_prompt,user_prompt)
        payload=dict(model=self.model,temperature=0,max_tokens=self.max_tokens,
                     messages=[dict(role='system',content=system_prompt),dict(role='user',content=user_prompt)],stream=False)
        if self.json_mode: payload['response_format']={'type':'json_object'}
        if self.include_reasoning is not None: payload['reasoning']={'enabled':self.include_reasoning}
        headers={'Content-Type':'application/json',**self.extra_headers}
        if self.api_key: headers['Authorization']='Bearer '+self.api_key
        # Explain invalid copied settings without disclosing header values or credentials.
        for name, value in headers.items():
            label = 'API anahtarı' if name.lower() == 'authorization' else 'Ek HTTP başlığı'
            try:
                name.encode('ascii')
                value.encode('ascii' if name.lower() == 'authorization' else 'latin-1')
            except (UnicodeEncodeError, AttributeError) as exc:
                raise LLMError('INVALID_HEADER',label+' geçersiz karakter içeriyor. Değeri sağlayıcıdan yeniden kopyalayın; açıklama metni eklemeyin.') from exc
            if any(c in name+value for c in '\r\n'):
                raise LLMError('INVALID_HEADER',label+' satır sonu içeriyor. Tek satırlık değeri yeniden girin.')
        for attempt in range(self.max_retries+1):
            record={'attempt':attempt+1,'settings':self.settings(), 'request':payload.copy()}
            self.calls.append(record); start=time.monotonic()
            try:
                response=self.session.post(self.chat_url,headers=headers,json=payload,timeout=self.timeout,verify=self.verify)
                record['http_status']=response.status_code
                try: data=response.json()
                except ValueError: data=None
                if isinstance(data, dict) and data.get('error'):
                    error = data['error']
                    explanation = error.get('message', '') if isinstance(error, dict) else str(error)
                    if isinstance(explanation, str):
                        if self.api_key:
                            explanation = explanation.replace(self.api_key, '[gizlendi]')
                        explanation = re.sub(r'(?i)(bearer\s+|sk-[a-z0-9_-]*)\S*', '[gizlendi]', explanation)
                        record['provider_message'] = explanation[:1000]
                if response.status_code in (429,500,502,503,504):
                    if attempt < self.max_retries:
                        try: delay=float(response.headers.get('Retry-After',2**attempt))
                        except ValueError: delay=2**attempt
                        if delay <= 30:
                            record['error_code']='RETRYABLE_HTTP'; time.sleep(max(0,delay)); continue
                    raise LLMError('RATE_LIMIT' if response.status_code==429 else 'SERVICE_UNAVAILABLE',f'HTTP {response.status_code}: quota/capacity error; model quality was not evaluated.')
                if response.status_code in (400,422) and 'response_format' in payload and attempt < self.max_retries:
                    body=response.text.lower()
                    if 'response_format' in body or 'json_object' in body:
                        record['error_code']='JSON_MODE_UNSUPPORTED'; payload=dict(payload);payload.pop('response_format');continue
                if not response.ok:
                    code={401:'AUTHENTICATION',403:'ACCESS_DENIED',404:'ENDPOINT_OR_MODEL',400:'REQUEST_FORMAT',422:'REQUEST_FORMAT'}.get(response.status_code,'HTTP_ERROR')
                    raise LLMError(code,f'HTTP {response.status_code} ({code}); check endpoint, model, account permissions and request settings.')
                if not isinstance(data,dict): raise LLMError('RESPONSE_FORMAT','Provider response is not a JSON object.')
                if data.get('error'): raise LLMError('PROVIDER_ERROR','Provider returned an error inside a successful HTTP response.')
                # Never record headers, credentials, or hidden reasoning. Keep final output + usage.
                choices=data.get('choices') or []
                choice=choices[0] if choices else {}
                record.update(usage=data.get('usage'),served_model=data.get('model'),provider=data.get('provider'),finish_reason=choice.get('finish_reason'))
                message=choice.get('message') or {}
                record['response']={'content':message.get('content'),'tool_calls':message.get('tool_calls')}
                if choice.get('finish_reason')=='length': raise LLMError('TRUNCATED','Output token limit reached; increase max_tokens or reduce document size.')
                content=self._extract_content(data)
                return self._parse_json(content)
            except requests.exceptions.SSLError as exc:
                record['error_code']='TLS'; raise LLMError('TLS','Certificate verification failed. Configure approved CA bundle.') from exc
            except requests.exceptions.Timeout as exc:
                record['error_code']='TIMEOUT'; raise LLMError('TIMEOUT','Request timed out. No automatic retry to avoid duplicate inference.') from exc
            except requests.exceptions.RequestException as exc:
                record['error_code']='NETWORK'; raise LLMError('NETWORK','Network request failed.') from exc
            except LLMError as exc:
                record['error_code']=exc.code; raise
            finally:
                record['seconds']=round(time.monotonic()-start,3)

    def _isolated_json(self, system, user):
        start=time.monotonic()
        remaining=min(self.timeout, self.deadline-start) if self.deadline is not None else self.timeout
        if self.cancel_event and self.cancel_event.is_set():
            raise LLMError('CANCELLED','Değerlendirme durduruldu.')
        if remaining<=0:
            raise LLMError('TIME_BUDGET','Toplam değerlendirme süresi doldu; kalan bölümler saklandı.')
        config=dict(base_url=self.base_url,api_key=self.api_key,model=self.model,timeout=remaining,
                    max_tokens=self.max_tokens,json_mode=self.json_mode,extra_headers=self.extra_headers,
                    ca_bundle=self.ca_bundle,verify_ssl=self.verify_ssl,include_reasoning=self.include_reasoning,
                    chat_completions_path=self.chat_completions_path,chat_completions_url=self.chat_completions_url,max_retries=self.max_retries)
        payload=json.dumps(dict(settings=config,system=system,user=user),ensure_ascii=True)
        env=os.environ.copy()
        # Use the base executable directly so terminating a Windows venv redirector cannot leave its child running.
        root=Path(__file__).resolve().parents[1]
        env['PYTHONPATH']=os.pathsep.join([str(root),sysconfig.get_path('purelib'),sysconfig.get_path('platlib')])
        process=subprocess.Popen([getattr(sys,'_base_executable',sys.executable),'-s','-m','app.llm_worker'],
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                                 encoding='utf-8',cwd=root,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            first=True
            while True:
                if self.cancel_event and self.cancel_event.is_set():
                    raise LLMError('CANCELLED','Değerlendirme durduruldu. Tamamlanan bölüm sonuçları korundu.')
                if time.monotonic()-start>=remaining:
                    code='TIME_BUDGET' if self.deadline is not None else 'TIMEOUT'
                    raise LLMError(code,'Değerlendirme süre sınırına ulaştı; kalan bölümler saklandı.')
                try:
                    output,errors=process.communicate(payload if first else None,timeout=min(.25,max(.01,remaining-(time.monotonic()-start))))
                    break
                except subprocess.TimeoutExpired:
                    first=False
            if process.returncode!=0 or not output.strip():
                code='TLS_RUNTIME' if 'OPENSSL_' in errors else 'WORKER_EXIT'
                raise LLMError(code,'Model bağlantısını yürüten işlem durdu. Uygulama ve kayıtlar korunuyor; Python bağlantı ortamını kontrol edin.')
            try: result=json.loads(output)
            except ValueError as exc: raise LLMError('WORKER_EXIT','Model bağlantı işlemi geçerli sonuç döndürmedi.') from exc
            self.calls.extend(result.get('calls',[]))
            if result.get('error_code'):
                raise LLMError(result['error_code'],result.get('message','Model isteği tamamlanamadı.'))
            return result['result']
        except LLMError as exc:
            if not self.calls or self.calls[-1].get('error_code')!=exc.code:
                self.calls.append(dict(settings=self.settings(),error_code=exc.code,seconds=round(time.monotonic()-start,3)))
            raise
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            for pipe in (process.stdin,process.stdout,process.stderr):
                if pipe: pipe.close()

    def test_connection(self):
        # Tests actual JSON output, not merely HTTP 200; shares model settings.
        result=self.extract_json('Return a JSON object only.', 'Return exactly {"ok": true}.')
        if result.get('ok') is not True: raise LLMError('PROBE_CONTENT','Endpoint responded, but the JSON probe did not match.')
        return {'ok':True,'model':self.model,'seconds':self.calls[-1]['seconds']}

    def probe_routes(self):
        return {'chat_completions':self.test_connection()}

    @staticmethod
    def _extract_content(data):
        choices=data.get('choices') or []
        msg=choices[0].get('message',{}) if choices else {}
        content=msg.get('content')
        if isinstance(content,list): content=''.join(str(x.get('text','')) for x in content if isinstance(x,dict))
        if content and str(content).strip(): return str(content).strip()
        for call in msg.get('tool_calls') or []:
            args=call.get('function',{}).get('arguments')
            if args: return args
        raise LLMError('EMPTY_CONTENT','No final answer. Reasoning-only content is not a result; inspect output budget/provider configuration.')

    @staticmethod
    def _parse_json(content):
        content=content.strip()
        if content.startswith('```'):
            lines=content.splitlines()
            if lines[-1].strip()=='```': content='\n'.join(lines[1:-1]).strip()
        try: parsed=json.loads(content)
        except (ValueError,TypeError) as exc:
            raise LLMError('INVALID_JSON','Final answer is not valid JSON. Raw final output is retained for inspection.') from exc
        if not isinstance(parsed,dict): raise LLMError('INVALID_JSON','Top-level result must be an object.')
        return parsed


def prompt_hash(system,user):
    return hashlib.sha256(json.dumps([system,user],ensure_ascii=False).encode()).hexdigest()

class FixtureClient:
    """Explicit test double; fixture results are NEVER labeled live model scores."""
    def __init__(self,path):
        self.payload=json.loads(Path(path).read_text(encoding='utf-8'));self.index=0;self.calls=[];self.model='OFFLINE_FIXTURE'
    def settings(self): return {'model':self.model,'mode':'fixture'}
    def extract_json(self,system,user):
        key=['architecture','analysis'][self.index];self.index+=1
        result=self.payload[key]
        self.calls.append({'prompt_hash':prompt_hash(system,user),'parsed':result,'seconds':0})
        return result

class ReplayClient:
    def __init__(self,path):
        payload=json.loads(Path(path).read_text(encoding='utf-8'))
        self.records=payload['exchanges'];self.index=0;self.calls=[];self.model='RECORDED_REPLAY'
    def settings(self): return {'model':self.model,'mode':'replay'}
    def extract_json(self,system,user):
        if self.index>=len(self.records): raise LLMError('REPLAY_EXHAUSTED','No recorded response left.')
        record=self.records[self.index];self.index+=1
        if record['prompt_hash']!=prompt_hash(system,user): raise LLMError('REPLAY_MISMATCH','Prompt differs from the recording; use live mode to evaluate a changed prompt.')
        if 'parsed' not in record: raise LLMError(record.get('error_code','REPLAY_FAILURE'),'Recorded call failed.')
        self.calls.append(record)
        return record['parsed']


def from_environment(profile_path=None):
    from .settings import load_settings
    return LLMClient(**load_settings(profile_path))
