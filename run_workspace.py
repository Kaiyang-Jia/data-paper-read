"""Start the web workspace and Python API; stop only processes owned by this run.

Usage: python run_workspace.py [--no-browser] | python run_workspace.py --stop
Database availability is optional: the checked-in real paper snapshot is the fallback.
"""
import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / '.runtime'


def port_available(port):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    RUNTIME.mkdir(exist_ok=True)
    stop_file = RUNTIME / 'stop.request'
    if args.stop:
        stop_file.touch()
        print('Stop requested for the DataPaper workspace launcher.')
        return 0
    if not all(port_available(p) for p in (3000, 5000)):
        print('Port 3000 or 5000 is already in use. No process was stopped. See .runtime logs.')
        return 1
    node = shutil.which('node')
    cli = ROOT / 'site/node_modules/vinext/dist/cli.js'
    if not node or not cli.exists():
        print('Install Node.js and run npm install inside site before starting.')
        return 1
    stop_file.unlink(missing_ok=True)
    # Local-only, non-secret binding; keep the hosted configuration separate.
    dev_vars = ROOT / 'site/.dev.vars'
    if not dev_vars.exists():
        dev_vars.write_text('DATAPAPER_API_URL=http://127.0.0.1:5000\n', encoding='utf-8')
    env = dict(os.environ, USE_LOCAL_USER_DB='true', PYTHONUTF8='1')
    children, logs = [], []
    try:
        for name, command, cwd in (
            ('api', [sys.executable, '-X', 'utf8', str(ROOT / 'run_preview.py')], ROOT),
            ('web', [node, str(cli), 'dev', '--host', '127.0.0.1', '--port', '3000'], ROOT / 'site'),
        ):
            log = (RUNTIME / f'{name}.log').open('w', encoding='utf-8')
            logs.append(log)
            children.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
        ready = False
        for _ in range(60):
            if stop_file.exists() or any(child.poll() is not None for child in children):
                break
            try:
                with urllib.request.urlopen('http://127.0.0.1:3000/api/catalog', timeout=2) as response:
                    ready = response.status == 200
            except Exception:
                pass
            if ready:
                break
            time.sleep(1)
        if not ready:
            print('Workspace did not become ready. See .runtime/api.log and web.log.')
            return 1
        print('DataPaper ready: http://127.0.0.1:3000/')
        if not args.no_browser:
            webbrowser.open('http://127.0.0.1:3000/')
        while not stop_file.exists() and all(child.poll() is None for child in children):
            time.sleep(1)
        return 0
    finally:
        for child in reversed(children):
            if child.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], capture_output=True)
                else:
                    child.terminate()
                child.wait(timeout=15)
        for log in logs:
            log.close()
        stop_file.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
