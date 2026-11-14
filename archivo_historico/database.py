"""Conexión histórica: reutiliza la configuración privada de la aplicación."""
import os
from pathlib import Path
from urllib.parse import urlsplit, unquote
import psycopg
from psycopg.rows import dict_row

url=os.getenv('DATABASE_URL','')
config=Path(__file__).resolve().parents[1]/'proycto innovador/.env'
if not url and config.exists():
    for line in config.read_text(encoding='utf-8').splitlines():
        if line.startswith('DATABASE_URL='):url=line.split('=',1)[1].strip()
parts=urlsplit(url.replace('postgresql+psycopg://','postgresql://'))
HOST=parts.hostname or os.getenv('PGHOST','localhost')
PUERTO=parts.port or int(os.getenv('PGPORT','5432'))
BASE_DATOS=unquote(parts.path.lstrip('/')) or os.getenv('PGDATABASE','Trabajo_innovador')
USUARIO=unquote(parts.username or '') or os.getenv('PGUSER','postgres')
CONTRASENA=unquote(parts.password or '') or os.getenv('PGPASSWORD','')

def conectar_bd():
    return psycopg.connect(host=HOST,port=PUERTO,dbname=BASE_DATOS,user=USUARIO,
        password=CONTRASENA,row_factory=dict_row)
