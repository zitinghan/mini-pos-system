#!/usr/bin/env python3
"""Temporary isolated API/worker for Playwright. Never uses the production database."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
processes = []


def stop(*_):
    for process in processes:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    raise SystemExit(0)


with tempfile.TemporaryDirectory(prefix='keke-browser-') as directory:
    environment = {
        **os.environ,
        'DATABASE_URL': f'sqlite:///{directory}/pos.db',
        'PRINT_OUTPUT_DIR': f'{directory}/tickets',
        'SETUP_TOKEN': 'isolated-browser-test-setup-token',
        'CUSTOMER_DISPLAY_CONFIG': f'{directory}/customer-display.json',
    }
    windows_font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc'
    if windows_font.is_file():
        environment.setdefault('FONT_PATH', str(windows_font))
    subprocess.run([sys.executable, '-m', 'app.database.initialize'], cwd=ROOT / 'backend', env=environment, check=True)
    for module, args in [('uvicorn', ['app.main:app', '--host', '127.0.0.1', '--port', '8000']), ('app.printing.worker', [])]:
        processes.append(subprocess.Popen([sys.executable, '-m', module, *args], cwd=ROOT / 'backend', env=environment))
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while all(process.poll() is None for process in processes):
        time.sleep(1)
    stop()
