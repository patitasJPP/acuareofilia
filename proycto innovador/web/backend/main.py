from .paths import DATA, SEED, MODELS, EXPORTS
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from enum import IntEnum
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from . import service
from .storage import ROOT, Session, Run, as_dict, engine
from .export import excel
from . import live
from . import analysis

@asynccontextmanager
async def lifespan(app):
    # Una ejecución interrumpida queda explícitamente marcada y puede repetirse.
    with Session() as s:
        for r in s.query(Run).filter(Run.estado.in_(['pendiente','ejecutando'])):
            r.estado='error';r.error='La aplicación se cerró antes de terminar. Crea una prueba nueva.'
        s.commit()
    service.initialize()
    live.recover()
    yield
    live.shutdown()

app=FastAPI(title='Pisciber · Mortalidad',version='2.0.0',lifespan=lifespan)
class Horizon(IntEnum):
    una=1
    seis=6
    doce=12

@app.exception_handler(ValueError)
async def invalid(_,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=404,content={'detail':str(exc)})

@app.get('/api/health')
def health():return {'estado':'lista','modelo':'XGBoost local v3','base_datos':engine.dialect.name}

@app.get('/api/corridas')
def runs():
    states=live.statuses()
    with Session() as s:return [as_dict(r)|({'vivo':states[r.id]} if r.id in states else {}) for r in s.query(Run).order_by(Run.id.desc()).all()]

@app.get('/api/resumen/{rid}')
def overview(rid:int,hora:int=Query(48,ge=0,le=96),horizonte:Horizon=12):
    r,_=service.get_run(rid)
    if not r.get('vivo') and hora>84:raise HTTPException(422,'El corte máximo de las corridas completas es 84')
    return service.snapshot(rid,hora,horizonte)

@app.get('/api/historial/{rid}')
def history(rid:int,horizonte:Horizon=12,pecera:int|None=Query(None,ge=0,le=2)):
    return service.timeline(rid,horizonte,pecera)

@app.get('/api/pez/{rid}/{pez}')
def fish(rid:int,pez:int,hora:int=Query(48,ge=0,le=96),horizonte:Horizon=12):
    r,d=service.get_run(rid)
    if r.get('vivo') and hora>r['vivo']['hora']:raise HTTPException(409,'Esa hora todavía no ha ocurrido')
    x=d[d.pez_id.eq(pez)&d.hora_sim.le(hora)]
    if x.empty:raise HTTPException(404,'No hay observaciones del pez en este corte')
    x=x.copy()
    x['hora_evento']=x.hora_evento.where(x.hora_evento.le(hora))
    for h in service.HORIZONS:x[f'observado_{h}h']=x[f'observado_{h}h'].where(x.hora_sim+h<=hora)
    row=x.tail(1).iloc[0]
    return {'actual':service.clean(x.tail(1))[0],'condiciones':service.conditions(row),
        'historial':service.clean(x[['hora_sim',f'riesgo_{horizonte}h','ph','temperatura','oxigeno','nh3_mg_n_l']]),
        'nota':'Condiciones registradas hasta el corte; no identifican una causa confirmada.'}

@app.get('/api/metricas')
def metrics():return service.metrics()

@app.get('/api/comparacion')
def comparison():return service.comparison()

@app.get('/api/estadisticas/{rid}')
def statistics(rid:int,hora:int=Query(48,ge=0,le=96)):
    return analysis.statistics(rid,hora)

@app.get('/api/seguimiento/{rid}')
def tracking(rid:int,hora:int=Query(48,ge=0,le=96),horizonte:Horizon=12,solo_alertas:bool=True,
    resultado:Literal['todos','sin_prediccion','pendiente','aviso_correcto','falsa_alarma','muerte_sin_aviso','supervivencia_correcta']='todos',
    pagina:int=Query(0,ge=0),limite:int=Query(25,ge=1,le=100)):
    return analysis.tracking(rid,hora,horizonte,solo_alertas,resultado,pagina,limite)

@app.get('/api/recomendaciones/{rid}')
def recommendations(rid:int,hora:int=Query(48,ge=0,le=96),horizonte:Horizon=12):
    return analysis.recommendations(rid,hora,horizonte)

class AttentionRequest(BaseModel):
    pez_id:int=Field(ge=0,le=279)
    hora_alerta:int=Field(ge=0,le=96)
    horizonte:Horizon=12
    hora_atencion:int=Field(ge=0,le=96)
    nota:str=Field('',max_length=500)

@app.post('/api/atenciones/{rid}')
def attend(rid:int,body:AttentionRequest):
    try:return analysis.attend(rid,body.pez_id,body.hora_alerta,body.horizonte,body.hora_atencion,body.nota)
    except ValueError as exc:raise HTTPException(409,str(exc))

@app.get('/api/escenarios')
def scenarios(horizonte:Horizon=12):return analysis.scenarios(horizonte)

class TankConfig(BaseModel):
    especie:str=Field(max_length=80)
    peces:int=Field(16,ge=1,le=80)
    volumen_l:float=Field(1500,ge=100,le=10000)

class SimulationConfig(BaseModel):
    intensidad:Literal['leve','moderado','severo']='moderado'
    inicio:int=Field(24,ge=1,le=84)
    duracion:int=Field(18,ge=1,le=72)
    sensores:Literal['normal','intermitente']='normal'
    peceras:list[TankConfig]=Field(min_length=3,max_length=3)

    @model_validator(mode='after')
    def duration_within_run(self):
        if self.inicio+self.duracion>96:raise ValueError('El incidente debe terminar antes de la hora 97')
        return self

class Simulation(BaseModel):
    escenario:Literal['estable','amonio','hipoxia','termico','ph','combinado']='combinado'
    semilla:int=Field(100000001,ge=100000000,le=2000000000)
    repeticiones:int=Field(1,ge=1,le=5)
    motor:Literal['incremental_v1','incremental_v2']='incremental_v2'
    configuracion:SimulationConfig|None=None

class LiveSimulation(Simulation):
    segundos:float=Field(1.,ge=.5,le=10)
    iniciar_pausada:bool=False

class LiveControl(BaseModel):
    accion:Literal['pausar','reanudar','velocidad']
    segundos:float|None=Field(None,ge=.5,le=10)

@app.post('/api/vivo',status_code=201)
def create_live(body:LiveSimulation):
    if body.repeticiones!=1:raise HTTPException(422,'Inicia una corrida en vivo a la vez')
    try:
        row=live.create(body.escenario,body.semilla,body.segundos,
                        body.configuracion.model_dump() if body.configuracion else None,body.motor,require_idle=False)
        if not body.iniciar_pausada:row['vivo']=live.control(row['id'],'reanudar')
        return row
    except ValueError as exc:raise HTTPException(409,str(exc))

@app.post('/api/vivo/{rid}/control')
def control_live(rid:int,body:LiveControl):
    try:return live.control(rid,body.accion,body.segundos)
    except ValueError as exc:raise HTTPException(409,str(exc))

@app.get('/api/vivo/{rid}/vista')
def live_view(rid:int,horizonte:Horizon=12,hora:int|None=Query(None,ge=0,le=96)):
    r,d=service.get_run(rid)
    if not r.get('vivo'):raise HTTPException(409,'La corrida seleccionada no es incremental')
    state=r['vivo'];cut=state['hora'] if hora is None else hora
    return {'vivo':state,'resumen':service.snapshot_data(r,d,cut,horizonte),
        'historial':service.timeline_data(d,horizonte,maximum=state['hora'])}

@app.get('/api/configuracion-simulador')
def simulation_options():
    import pandas as pd
    from simulacion.motor.realistic_engine import DEFAULT_CONFIG
    return {'predeterminada':DEFAULT_CONFIG,'especies':service.clean(pd.read_csv(SEED/'fichas_origen.csv'))}

@app.get('/api/vivo/{rid}/detalle')
def live_details(rid:int,hora:int=Query(0,ge=0,le=96)):
    return live.details(rid,hora)

class Intervention(BaseModel):
    pecera_id:int=Field(ge=0,le=2)
    accion:Literal['aireacion','filtro','recambio','temperatura']
    valor:float=Field(0,ge=0,le=40,allow_inf_nan=False)
    duracion:int=Field(12,ge=1,le=48)
    hora_esperada:int=Field(ge=0,le=95)

@app.post('/api/vivo/{rid}/intervenciones',status_code=201)
def intervention(rid:int,body:Intervention):
    try:return live.intervene(rid,body.pecera_id,body.accion,body.valor,body.duracion,body.hora_esperada)
    except ValueError as exc:raise HTTPException(409,str(exc))

class Branch(BaseModel):
    hora:int=Field(ge=0,le=95)

@app.post('/api/vivo/{rid}/rama',status_code=201)
def create_branch(rid:int,body:Branch):
    try:return live.branch(rid,body.hora)
    except ValueError as exc:raise HTTPException(409,str(exc))

@app.post('/api/corridas/{rid}/reiniciar',status_code=201)
def restart_run(rid:int):
    try:return live.restart(rid)
    except ValueError as exc:raise HTTPException(409,str(exc))

@app.get('/api/vivo/{rid}/pareja/{other}')
def paired(rid:int,other:int):
    try:return live.paired(rid,other)
    except ValueError as exc:raise HTTPException(409,str(exc))

@app.get('/api/evaluacion-v2')
def evaluation_v2():
    import json
    from .paths import ROOT
    path=ROOT/'resultados/validacion_motor_v2/informe.json'
    if not path.exists():return {'estado':'pendiente','nota':'Todavía no hay una evaluación del modelo sobre el motor v2.'}
    return json.loads(path.read_text(encoding='utf-8'))

@app.post('/api/simulaciones',status_code=202)
def simulate(body:Simulation,tasks:BackgroundTasks):
    with Session() as s:
        if s.query(Run).filter(Run.estado.in_(['pendiente','ejecutando'])).count():
            raise HTTPException(409,'Espera a que terminen las simulaciones en curso')
    if body.motor=='incremental_v2':
        rows=[]
        for i in range(body.repeticiones):
            row=live.create(body.escenario,body.semilla+i*101,1.,body.configuracion.model_dump() if body.configuracion else None,require_idle=False)
            with Session() as s:
                run=s.get(Run,row['id']);run.estado='ejecutando';s.commit()
            row['estado']='ejecutando';rows.append(row);tasks.add_task(live.finish,row['id'])
    else:
        rows=service.create_runs(body.escenario,body.semilla,body.repeticiones)
        for r in rows:tasks.add_task(service.execute_run,r['id'])
    return rows

@app.get('/api/exportar/{rid}')
def export(rid:int,hora:int=Query(48,ge=0,le=96),horizonte:Horizon=12):
    blob=excel(rid,hora,horizonte)
    path=EXPORTS/f'Pisciber_corrida_{rid}_hora_{hora}_{horizonte}h.xlsx'
    path.write_bytes(blob)
    return Response(blob,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition':f'attachment; filename="{path.name}"'})

DIST=ROOT/'web/frontend/dist'
if DIST.exists():
    app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
    @app.get('/{path:path}',include_in_schema=False)
    def frontend(path:str):
        if path.startswith('api/'):raise HTTPException(404,'Ruta de API no encontrada')
        return FileResponse(DIST/'index.html')
