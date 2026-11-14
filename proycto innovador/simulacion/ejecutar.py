"""Ejecución independiente del motor: python -m simulacion.ejecutar."""
import argparse,json
from pathlib import Path
from datetime import datetime
import pandas as pd
from .motor.live_engine import LiveEngine

def main():
    parser=argparse.ArgumentParser(description='Motor simulado independiente de la web')
    parser.add_argument('--semilla',type=int,default=100000001)
    parser.add_argument('--escenario',choices=['estable','amonio','hipoxia','termico','ph','combinado'],default='estable')
    parser.add_argument('--horas',type=int,choices=range(1,97),default=96)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    out=root/'resultados/simulaciones'/datetime.now().strftime('%Y%m%d_%H%M%S_%f');out.mkdir(parents=True)
    fichas=pd.read_csv(root/'simulacion/datos_base/fichas_origen.csv')
    engine=LiveEngine(fichas,0,args.semilla,args.escenario);rows=[];water=[]
    for _ in range(args.horas+1):
        rows.extend(engine.step());water.extend(dict(w,hora_sim=engine.hour) for w in engine.water)
    pd.DataFrame(rows).to_csv(out/'mediciones.csv',index=False)
    pd.DataFrame(engine.events,columns=['corrida_id','pez_id','pecera_id','hora_evento','evento']).to_csv(out/'eventos.csv',index=False)
    pd.DataFrame(water).to_csv(out/'agua.csv',index=False)
    (out/'metadatos.json').write_text(json.dumps({'motor':'incremental_v1','semilla':args.semilla,'escenario':args.escenario,
        'horas':args.horas,'nota':'Datos simulados del motor; no son predicciones de XGBoost.'},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Simulación guardada en',out)
if __name__=='__main__':main()
