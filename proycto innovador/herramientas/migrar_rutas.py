"""Actualiza referencias de la reorganización sin cambiar datos ni modelos."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
backend=root/'web/backend'
for p in backend.glob('*.py'):
    if p.name in ['paths.py','__init__.py']:continue
    s=p.read_text(encoding='utf-8')
    s=s.replace("ROOT/'data'","DATA").replace("ROOT/f'data/","DATA/f'")
    s=s.replace("ROOT/'seed'","SEED").replace("ROOT/'seed/","SEED/'")
    s=s.replace("ROOT/f'models/","MODELS/f'")
    s=s.replace("ROOT/f'exports/","EXPORTS/f'")
    s=s.replace("ROOT/'frontend/dist'","ROOT/'web/frontend/dist'")
    if p.name=='storage.py':
        s=s.replace('ROOT = Path(__file__).resolve().parents[1]','from .paths import ROOT, DATA')
        s=s.replace("ROOT/'data/pisciber.db'","DATA/'pisciber.db'")
    else:
        s='from .paths import DATA, SEED, MODELS, EXPORTS\n'+s
    if p.name=='service.py':s=s.replace("ML=ROOT/'ml'","from .paths import ML")
    p.write_text(s,encoding='utf-8')
init=root/'iniciar.ps1'
s=init.read_text(encoding='utf-8').replace("'frontend\\dist\\index.html'","'web\\frontend\\dist\\index.html'").replace('Push-Location frontend','Push-Location web/frontend').replace('uvicorn backend.main:app --host','uvicorn backend.main:app --app-dir web --host')
init.write_text(s,encoding='utf-8')
