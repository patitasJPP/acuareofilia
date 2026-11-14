"""Estadísticas al corte, seguimiento verificable y reglas de revisión."""
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from sqlalchemy import ForeignKey, Integer, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .storage import Base, engine, Run, Session
from . import service

class Attention(Base):
    __tablename__='pisciber_atenciones'
    __table_args__=(UniqueConstraint('run_id','pez_id','hora_alerta','horizonte'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    run_id:Mapped[int]=mapped_column(ForeignKey('pisciber_corridas.id'))
    pez_id:Mapped[int]=mapped_column(Integer)
    hora_alerta:Mapped[int]=mapped_column(Integer)
    horizonte:Mapped[int]=mapped_column(Integer)
    hora_atencion:Mapped[int]=mapped_column(Integer)
    nota:Mapped[str]=mapped_column(Text,default='')
    fecha:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))
Base.metadata.create_all(engine)

def safe_ratio(a,b):return float(a/b) if b else None

def cutoff(r,d,hour=None):
    maximum=r.get('vivo',{}).get('hora',96)
    hour=maximum if hour is None else hour
    if not 0<=hour<=maximum:raise ValueError('La hora solicitada todavía no está disponible')
    return hour

def tracking_data(r,d,hour,horizon):
    """Recalcula el desenlace conocido al corte; nunca lee observado del futuro."""
    hour=cutoff(r,d,hour);x=d[d.hora_sim.le(hour)].copy()
    x['hora_evento']=x.hora_evento.where(x.hora_evento.le(hour))
    matured=x.hora_sim+horizon<=hour
    died=x.hora_evento.gt(x.hora_sim)&x.hora_evento.le(x.hora_sim+horizon)
    alert=x[f'alerta_{horizon}h'].astype(bool)
    x['resultado']=np.select([~matured,alert&died,alert&~died,~alert&died],
        ['pendiente','aviso_correcto','falsa_alarma','muerte_sin_aviso'],default='supervivencia_correcta')
    x['hora_limite']=x.hora_sim+horizon
    x['horizonte']=horizon;x['probabilidad']=x[f'riesgo_{horizon}h'];x['alerta']=alert
    with Session() as s:attentions=s.query(Attention).filter_by(run_id=r['id'],horizonte=horizon).all()
    known={(a.pez_id,a.hora_alerta):a for a in attentions if a.hora_atencion<=hour}
    x['atendida']=[(int(p),int(t)) in known for p,t in zip(x.pez_id,x.hora_sim)]
    x['hora_atencion']=[known[(int(p),int(t))].hora_atencion if (int(p),int(t)) in known else None for p,t in zip(x.pez_id,x.hora_sim)]
    x['nota_atencion']=[known[(int(p),int(t))].nota if (int(p),int(t)) in known else '' for p,t in zip(x.pez_id,x.hora_sim)]
    return x

def tracking(rid,hour,horizon,only_alerts=True,result='todos',page=0,limit=25):
    r,d=service.get_run(rid);x=tracking_data(r,d,hour,horizon)
    counts={k:int(x.resultado.eq(k).sum()) for k in ['pendiente','aviso_correcto','falsa_alarma','muerte_sin_aviso','supervivencia_correcta']}
    tp=counts['aviso_correcto'];fp=counts['falsa_alarma'];fn=counts['muerte_sin_aviso'];tn=counts['supervivencia_correcta']
    summary=counts|{'precision':safe_ratio(tp,tp+fp),'recall':safe_ratio(tp,tp+fn),'error':safe_ratio(fp+fn,tp+fp+fn+tn),
        'evaluadas':tp+fp+fn+tn,'alertas':int(x.alerta.sum()),'atendidas':int(x.atendida.sum()),
        'demora_media_h':float((x.hora_atencion-x.hora_sim).mean()) if x.atendida.any() else None}
    if only_alerts:x=x[x.alerta]
    if result!='todos':x=x[x.resultado.eq(result)]
    x=x.sort_values(['hora_sim','probabilidad','pez_id'],ascending=[False,False,True])
    cols=['pez_id','pecera_id','especie_nombre','hora_sim','hora_limite','horizonte','probabilidad','alerta','resultado','hora_evento','atendida','hora_atencion','nota_atencion']
    return {'resumen':summary,'total':len(x),'pagina':page,'filas':service.clean(x.iloc[page*limit:(page+1)*limit][cols])}

def statistics_data(r,d,hour):
    hour=cutoff(r,d,hour)
    first=d[d.hora_sim.eq(0)].drop_duplicates('pez_id')
    dead=d[d.hora_evento.le(hour)].drop_duplicates('pez_id')
    initial=len(first);deaths=len(dead)
    groups=[]
    for dim in ['pecera_id','especie_nombre']:
        for name,g in first.groupby(dim):
            n=len(g);m=int(dead.pez_id.isin(g.pez_id).sum())
            groups.append({'dimension':dim,'grupo':str(name),'iniciales':n,'muertos':m,'vivos':n-m,'mortalidad':safe_ratio(m,n)})
    curve=[]
    for t in range(hour+1):
        m=int(dead.hora_evento.le(t).sum())
        curve.append({'hora':t,'vivos':initial-m,'muertos':m,'mortalidad':safe_ratio(m,initial)})
    water=d[d.hora_sim.le(hour)].groupby(['pecera_id','hora_sim'],as_index=False)[['ph','temperatura','oxigeno','nh3_mg_n_l']].first()
    return {'hora':hour,'iniciales':initial,'muertos':deaths,'vivos':initial-deaths,'mortalidad':safe_ratio(deaths,initial),
        'grupos':groups,'evolucion':curve,'agua':service.clean(water),
        'motor':'incremental_v1' if r['origen']=='vivo' else 'lotes_v3'}

def statistics(rid,hour):
    r,d=service.get_run(rid);return statistics_data(r,d,hour)

def recommendations(rid,hour,horizon):
    r,d=service.get_run(rid);cutoff(r,d,hour)
    x=d[d.hora_sim.eq(hour)];out=[]
    rules=[('temp_desvio','TEMP','Temperatura fuera del rango de la especie','Confirmar la lectura y revisar el control de temperatura con la ficha de la especie.'),
        ('ph_desvio','PH','pH fuera del rango de la especie','Confirmar la lectura y revisar el rango de pH registrado para la especie.'),
        ('ox_deficit','OX','Oxígeno por debajo del mínimo de la especie','Revisar la lectura de oxígeno y el estado del sistema de aireación.')]
    for tid,g in x.groupby('pecera_id'):
        for col,code,title,action in rules:
            affected=g[g[col]>.05]
            if len(affected):out.append({'pecera_id':int(tid),'codigo':code,'condicion':title,'peces_afectados':len(affected),
                'especies':', '.join(sorted(affected.especie_nombre.unique())),'sugerencia':action,'origen':'Regla de revisión con rangos de la ficha simulada'})
        for col,code,title,action in [('filtro_activo','FILTRO','Filtro inactivo','Revisar el estado del filtro en la simulación.'),('aireacion_activa','AIRE','Aireación inactiva','Revisar el estado de la aireación en la simulación.')]:
            if not g[col].all():out.append({'pecera_id':int(tid),'codigo':code,'condicion':title,'peces_afectados':len(g),
                'especies':', '.join(sorted(g.especie_nombre.unique())),'sugerencia':action,'origen':'Estado simulado del equipo'})
        if g[f'alerta_{horizon}h'].any() and not any(a['pecera_id']==tid for a in out):
            out.append({'pecera_id':int(tid),'codigo':'MODELO','condicion':'Alerta del modelo sin desvío actual de rango detectado',
                'peces_afectados':int(g[f'alerta_{horizon}h'].sum()),'especies':', '.join(sorted(g.especie_nombre.unique())),
                'sugerencia':'Revisar la exposición acumulada y el historial de los peces con alerta.','origen':'Probabilidad del modelo; no diagnóstico de causa'})
    return out

def attend(rid,fish,issued,horizon,hour,note):
    r,d=service.get_run(rid)
    actual=cutoff(r,d,None) if r.get('vivo') else cutoff(r,d,hour)
    if actual<issued:raise ValueError('No se puede atender una alerta antes de que se emita')
    row=d[d.pez_id.eq(fish)&d.hora_sim.eq(issued)]
    if row.empty or not bool(row.iloc[0][f'alerta_{horizon}h']):raise ValueError('La observación seleccionada no tiene alerta del modelo')
    with Session() as s:
        a=s.query(Attention).filter_by(run_id=rid,pez_id=fish,hora_alerta=issued,horizonte=horizon).first()
        if not a:
            a=Attention(run_id=rid,pez_id=fish,hora_alerta=issued,horizonte=horizon,hora_atencion=actual,nota=note)
            s.add(a);s.commit()
        return {'registrada':True,'hora_atencion':a.hora_atencion,'demora_h':a.hora_atencion-issued}

def scenarios(horizon):
    with Session() as s:runs=s.query(Run).filter(Run.estado=='lista').order_by(Run.id).all()
    groups={};seen=set();duplicates=0;partial=0
    for run in runs:
        r,d=service.get_run(run.id)
        if r.get('vivo',{}).get('hora',96)<96:partial+=1;continue
        motor='incremental_v1' if run.origen=='vivo' else 'lotes_v3'
        seedkey=(motor,run.escenario,run.semilla)
        if seedkey in seen:duplicates+=1;continue
        seen.add(seedkey);k=(motor,run.escenario)
        g=groups.setdefault(k,{'motor':motor,'escenario':run.escenario,'corridas':0,'iniciales':0,'muertos':0,'tp':0,'fp':0,'fn':0,'tn':0})
        m=service.evaluate(d,horizon);st=statistics_data(r,d,96)
        g['corridas']+=1;g['iniciales']+=st['iniciales'];g['muertos']+=st['muertos']
        for c in ['tp','fp','fn','tn']:g[c]+=m[c] or 0
    for g in groups.values():
        g['mortalidad']=safe_ratio(g['muertos'],g['iniciales']);g['precision']=safe_ratio(g['tp'],g['tp']+g['fp'])
        g['recall']=safe_ratio(g['tp'],g['tp']+g['fn']);g['error']=safe_ratio(g['fp']+g['fn'],sum(g[c] for c in ['tp','fp','fn','tn']))
    return {'grupos':list(groups.values()),'excluidas_en_curso':partial,'repetidas_excluidas':duplicates,
        'nota':'Solo corridas completas de 96 h; una semilla por ambiente y motor. Tasas calculadas desde sus conteos, sin promediar porcentajes.'}
