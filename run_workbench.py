"""Start the packaged web workbench. Run from VS Code or run_app.bat."""
import argparse
from pathlib import Path
import threading
import webbrowser


def main():
    parser = argparse.ArgumentParser(description='Mimari Atölyesi yerel uygulaması')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--data-dir', type=Path)
    args = parser.parse_args()
    try:
        import uvicorn
        from app.workbench import create_app
    except ImportError:
        raise SystemExit('Web bağımlılıkları eksik. python -m pip install -r requirements-workbench.txt çalıştırın.')
    if not (Path(__file__).parent/'web/dist/index.html').exists():
        raise SystemExit('Arayüz derlenmemiş. web klasöründe npm ci ve npm run build çalıştırın.')
    url = f'http://127.0.0.1:{args.port}'
    data_dir = (args.data_dir or Path(__file__).parent/'workbench_data').resolve()
    print(f'Mimari Atölyesi: {url}\nDurdurmak için Ctrl+C. Veriler: {data_dir}')
    if not args.no_browser:
        timer = threading.Timer(1.5, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    uvicorn.run(create_app(args.data_dir), host='127.0.0.1', port=args.port, log_level='info')


if __name__ == '__main__':
    main()
