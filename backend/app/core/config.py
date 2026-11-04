import os
from pathlib import Path

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./data/pos.db')
OUTPUT_DIR = Path(os.getenv('PRINT_OUTPUT_DIR', './data/tickets'))
FONT_PATH = os.getenv('FONT_PATH', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
SETUP_TOKEN = os.getenv('SETUP_TOKEN', '')
SESSION_HOURS = int(os.getenv('SESSION_HOURS', '12'))
