"""Migración inicial del registro local a PostgreSQL, sin alterar tablas ajenas."""
from pathlib import Path
import importlib.util
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'web'))
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
from backend.storage import Base, Run, ROOT

def configure():
    config=ROOT.parent/'archivo_historico/database.py'
    spec=importlib.util.spec_from_file_location('conexion_existente',config)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    url=URL.create('postgresql+psycopg',username=module.USUARIO,password=module.CONTRASENA,
        host=module.HOST,port=module.PUERTO,database=module.BASE_DATOS)
    target=create_engine(url,connect_args={'connect_timeout':5})
    Base.metadata.create_all(target)
    Target=sessionmaker(target)
    source=create_engine(f"sqlite:///{(ROOT/'datos/corridas/pisciber.db').as_posix()}")
    Source=sessionmaker(source)
    with Source() as old,Target() as new:
        if not new.query(Run).first():
            for r in old.query(Run).order_by(Run.id):
                new.add(Run(nombre=r.nombre,escenario=r.escenario,semilla=r.semilla,origen=r.origen,
                    estado=r.estado,archivo=r.archivo,error=r.error,creado=r.creado))
            new.commit()
    (ROOT/'.env').write_text('DATABASE_URL='+url.render_as_string(hide_password=False)+'\n',encoding='utf-8')
    print('PostgreSQL configurado; registro de corridas migrado. Datos completos conservados en data/.')

if __name__=='__main__':configure()
