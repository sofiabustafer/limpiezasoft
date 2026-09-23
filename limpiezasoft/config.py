import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def database_settings():
    load_dotenv(ROOT / '.env')
    return dict(host=os.getenv('DB_HOST', 'localhost'),
                port=int(os.getenv('DB_PORT', '5432')),
                dbname=os.getenv('DB_NAME', 'proyecto'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', ''),
                connect_timeout=5,
                options='-c statement_timeout=10000 -c timezone=America/Asuncion')
