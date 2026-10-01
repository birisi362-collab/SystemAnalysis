import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load_settings(profile_path=None):
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env',override=False)
    profile_path=profile_path or os.getenv('LLM_PROFILE') or str(ROOT/'profiles/nvidia_deepseek.json')
    config=json.loads(Path(profile_path).read_text(encoding='utf-8'))
    key_env=config.pop('api_key_env','LLM_API_KEY')
    config.pop('description',None)
    config['api_key']=os.getenv('LLM_API_KEY') or os.getenv(key_env,'')
    mapping={'base_url':'LLM_BASE_URL','model':'LLM_MODEL','ca_bundle':'LLM_CA_BUNDLE',
             'chat_completions_path':'LLM_CHAT_COMPLETIONS_PATH','chat_completions_url':'LLM_CHAT_COMPLETIONS_URL'}
    for key,env in mapping.items():
        if os.getenv(env):config[key]=os.environ[env]
    if not config.get('ca_bundle') and os.getenv('REQUESTS_CA_BUNDLE'):config['ca_bundle']=os.environ['REQUESTS_CA_BUNDLE']
    for key,env in {'timeout':'LLM_TIMEOUT','max_tokens':'LLM_MAX_TOKENS','max_retries':'LLM_MAX_RETRIES'}.items():
        if os.getenv(env):config[key]=int(os.environ[env])
    for key,env in {'json_mode':'LLM_JSON_MODE','verify_ssl':'LLM_VERIFY_SSL','include_reasoning':'LLM_INCLUDE_REASONING'}.items():
        if os.getenv(env): config[key]=os.environ[env].lower()=='true'
    return config
