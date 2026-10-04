"""Start the packaged web workbench. Run from VS Code or run_app.bat."""
import argparse
import json
from http.client import HTTPConnection
from pathlib import Path
import socket
import subprocess
import sys
import threading
from urllib.parse import urlsplit
import webbrowser


def instance_json(url, path, limit=4096):
    # Direct loopback HTTP avoids proxy and certificate-store initialization.
    target=urlsplit(url)
    if target.scheme!='http' or target.hostname!='127.0.0.1':
        raise ValueError('Yalnızca yerel servis sorgulanabilir.')
    connection=HTTPConnection(target.hostname,target.port,timeout=2)
    try:
        connection.request('GET',path)
        response=connection.getresponse()
        if response.status!=200:
            return response.status,None
        data=response.read(limit+1)
        if len(data)>limit:
            raise ValueError('Servis yanıtı sınırı aşıyor.')
        return response.status,json.loads(data)
    finally:
        connection.close()


def legacy_workbench(url, data_dir):
    """Recognize old Windows launchers without assuming their data directory."""
    root=Path(__file__).parent.resolve()
    if sys.platform!='win32' or data_dir != root/'workbench_data':
        return False
    try:
        status,info=instance_json(url,'/api/bootstrap',512000)
        if status!=200 or not isinstance(info,dict) or Path(info.get('root','')).resolve()!=root or not all(k in info for k in ('projects','profiles','jobs','version')):
            return False
        port=urlsplit(url).port
        command=f"Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort {int(port)} -State Listen | ForEach-Object {{ (Get-CimInstance Win32_Process -Filter ('ProcessId=' + $_.OwningProcess)).CommandLine }} | ConvertTo-Json -Compress"
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=8,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode!=0:
            return False
        process_command=json.loads(result.stdout)
        if not isinstance(process_command,str):
            return False
        normalized=process_command.replace('\\','/').casefold()
        return (root.as_posix().casefold() in normalized
                and 'run_workbench.py' in normalized and '--data-dir' not in normalized)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return False


def existing_workbench(url, data_dir):
    try:
        status,info=instance_json(url,'/api/instance')
        if status==404:
            return legacy_workbench(url,data_dir)
        if status!=200 or not isinstance(info,dict):
            return False
        return (info.get('app')=='system-architecture-analyzer-workbench'
                and Path(info.get('root', '')).resolve()==Path(__file__).parent.resolve()
                and Path(info.get('data_dir', '')).resolve()==data_dir)
    except (OSError, ValueError, TypeError):
        return False


def port_in_use(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=1):
            return True
    except OSError:
        return False


def ensure_runtime():
    root=Path(__file__).parent.resolve()
    preferred=root/'.venv-workbench'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    if preferred.is_file() and Path(sys.prefix).resolve()!=preferred.parent.parent.resolve():
        print('Uygulamanın doğrulanmış Python ortamına geçiliyor.',flush=True)
        raise SystemExit(subprocess.call([str(preferred),str(Path(__file__).resolve()),*sys.argv[1:]]))
    # Probe in a child: a native OpenSSL abort must not kill a running workbench.
    try:
        result=subprocess.run([sys.executable,'-c',"import ssl; ssl.create_default_context(); print('TLS_READY')"],capture_output=True,text=True,timeout=15)
    except (OSError,subprocess.TimeoutExpired):
        result=None
    if result is None or result.returncode!=0 or 'TLS_READY' not in result.stdout:
        raise SystemExit('Python ortamının güvenli bağlantı kontrolü başarısız. Sunucu başlatılmadı. Resmî Python ile .venv-workbench ortamını kurun; docs/DEGERLENDIRME_TEHSISI_TR.md dosyasındaki adımları izleyin.')


def main():
    parser = argparse.ArgumentParser(description='Mimari Atölyesi yerel uygulaması')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--data-dir', type=Path)
    args = parser.parse_args()
    url = f'http://127.0.0.1:{args.port}'
    data_dir = (args.data_dir or Path(__file__).parent/'workbench_data').resolve()
    if port_in_use(args.port):
        if existing_workbench(url, data_dir):
            print(f'Uygulama zaten çalışıyor. Mevcut uygulama: {url}\nVeriler: {data_dir}')
            if not args.no_browser:
                webbrowser.open(url)
            return
        raise SystemExit(f'{args.port} portu başka bir servis veya farklı bir çalışma tarafından kullanılıyor.\nBaşka port seçin: python run_workbench.py --port {args.port+1}')
    ensure_runtime()
    try:
        import uvicorn
        from app.workbench import create_app
    except ImportError:
        raise SystemExit('Web bağımlılıkları eksik. python -m pip install -r requirements-workbench.txt çalıştırın.')
    if not (Path(__file__).parent/'web/dist/index.html').exists():
        raise SystemExit('Arayüz derlenmemiş. web klasöründe npm ci ve npm run build çalıştırın.')
    print(f'Mimari Atölyesi: {url}\nDurdurmak için Ctrl+C. Veriler: {data_dir}')
    if not args.no_browser:
        timer = threading.Timer(1.5, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    uvicorn.run(create_app(args.data_dir), host='127.0.0.1', port=args.port, log_level='info')


if __name__ == '__main__':
    main()
