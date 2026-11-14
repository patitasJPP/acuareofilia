from .labels import simulation_name
"""Registro persistente. SQLite local; PostgreSQL mediante DATABASE_URL."""
import os
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Integer, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .paths import ROOT, DATA
(DATA).mkdir(exist_ok=True)
# Variables locales opcionales; el archivo .env nunca se versiona.
if (ROOT/'.env').exists():
    for line in (ROOT/'.env').read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1)
            os.environ.setdefault(key.strip(),value.strip())
URL = os.getenv('DATABASE_URL', f"sqlite:///{(DATA/'pisciber.db').as_posix()}")
engine = create_engine(URL, connect_args={'check_same_thread': False} if URL.startswith('sqlite') else {})
Session = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
class Run(Base):
    __tablename__='pisciber_corridas'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120))
    escenario: Mapped[str] = mapped_column(String(30))
    semilla: Mapped[int] = mapped_column(Integer)
    origen: Mapped[str] = mapped_column(String(30), default='nueva')
    estado: Mapped[str] = mapped_column(String(20), default='pendiente')
    archivo: Mapped[str] = mapped_column(Text, default='')
    error: Mapped[str] = mapped_column(Text, default='')
    creado: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
Base.metadata.create_all(engine)

def as_dict(r):
    return {c:getattr(r,c) for c in ['id','nombre','escenario','semilla','origen','estado','error']} | {'creado':r.creado.isoformat(),'nombre':simulation_name(r.nombre,r.escenario)}
