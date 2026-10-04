"""One model request per child process; credentials travel through stdin only."""
import json
import sys

def main():
    payload=json.load(sys.stdin)
    if sys.platform=='win32' and not payload['settings'].get('ca_bundle'):
        import truststore
        truststore.inject_into_ssl()
    from .llm_client import LLMClient, LLMError
    client=LLMClient(**payload['settings'])
    try:
        result=client.extract_json(payload['system'],payload['user'])
        output={'result':result,'calls':client.calls}
    except Exception as exc:
        output={'error_code':getattr(exc,'code',type(exc).__name__),
                'message':str(exc) if isinstance(exc,LLMError) else 'Model yanıtı işlenemedi.',
                'calls':client.calls}
    json.dump(output,sys.stdout,ensure_ascii=True)


if __name__=='__main__':main()
