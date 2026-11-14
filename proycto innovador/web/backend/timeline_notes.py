"""Explicaciones descriptivas al corte; no atribuyen causalidad al modelo."""
import math


def annotate(points, readings=None, log=None):
    water={}
    for row in readings or []:
        hour=row.get('hora_lectura',row.get('hora_sim'))
        tid=row.get('id',row.get('pecera_id'))
        water.setdefault(hour,{})[tid]=row
    events={}
    for event in log or []:
        if event['tipo'] in ['incidente','accion_aplicada']:
            events.setdefault(event['hora'],[]).append(event)
    past_max=0.
    for i,point in enumerate(points):
        previous=points[i-1] if i else None
        current=point['esperadas'];before=previous['esperadas'] if previous else None
        notes=[];trend='Sin cambio importante';mark=False
        if current is None:
            trend='Predicción no disponible'
        elif not previous:
            trend='Inicio del seguimiento'
        elif before is not None:
            delta=current-before
            if abs(delta)>=max(.03,abs(before)*.1):
                trend='Sube la predicción' if delta>0 else 'Baja la predicción';mark=True
            if current>max(.2,past_max*1.1):
                trend='Máximo observado hasta esta hora';mark=True
            fewer=previous['vivos']-point['vivos']
            if fewer>0:
                notes.append(f'Hay {fewer} peces vivos menos que en la hora anterior; esto también afecta la suma de riesgos.')
        if point.get('sin_prediccion',0):
            notes.append(f"{point['sin_prediccion']} peces sin predicción: el total representa solo a los evaluados.")
        if previous:
            now=water.get(point['hora'],{});old=water.get(previous['hora'],{})
            for key,title,minimum in [('oxigeno','Oxígeno',.15),('nh3_mg_n_l','Amoníaco NH₃-N',.005),('temperatura','Temperatura',.3),('ph','pH',.04)]:
                changes=[]
                for tid in now.keys() & old.keys():
                    a=now[tid].get(key,now[tid].get('nh3') if key=='nh3_mg_n_l' else None)
                    b=old[tid].get(key,old[tid].get('nh3') if key=='nh3_mg_n_l' else None)
                    if a is not None and b is not None and math.isfinite(a) and math.isfinite(b):changes.append(a-b)
                up=sum(v>=minimum for v in changes);down=sum(v<=-minimum for v in changes)
                if up:notes.append(f'{title} aumentó en {up} pecera(s).')
                if down:notes.append(f'{title} disminuyó en {down} pecera(s).')
        for event in events.get(point['hora'],[]):
            mark=True
            if event['tipo']=='incidente':
                text=event['detalle']
                if text.startswith('Fin del incidente'):
                    text='Terminó el incidente programado: se restablece el funcionamiento automático de los equipos afectados. La recuperación del agua es gradual.'
                notes.insert(0,text)
            else:
                action={'aireacion':'activar la aireación','filtro':'restablecer el filtro','recambio':'realizar un recambio parcial de agua','temperatura':'regular la temperatura'}.get(event['detalle'],event['detalle'])
                notes.insert(0,f"Acción del usuario aplicada en pecera {event['pecera_id']+1}: {action}.")
        if not notes:notes=['Sin cambios de agua o acciones registrados que permitan explicar por sí solos esta variación. El modelo también utiliza la exposición previa.']
        point.update(tendencia=trend,explicaciones=notes,marcar=mark)
        if current is not None:past_max=max(past_max,current)
    return points
