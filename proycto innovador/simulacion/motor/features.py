"""Variables observables para v2; imputación causal explícita, sin valores internos."""
import numpy as np
import pandas as pd
from .live_engine import nh3_desde_tan
from mejorar_predicciones import historia


class IncrementalFeatures:
    """Mismas variables de prepare, actualizando solo la hora nueva.

    El estado se guarda en el checkpoint junto al RNG del motor.
    """
    source = ['ph','temperatura','oxigeno','tan_mg_n_l','ph_desvio','temp_desvio','ox_deficit']

    def __init__(self):self.fish={}

    def update(self, rows):
        originals=[];features=[]
        for raw in rows:
            row=dict(raw);key=(row['corrida_id'],row['pez_id'])
            state=self.fish.setdefault(key,{'last':{},'gaps':{},'blocked':False,'estimated':False,'previous':None,
                                          'nh3':[],'ox':[],'history':{c:[] for c in ['nh3_mg_n_l','ox_deficit','temp_desvio','ph_desvio']}})
            work=dict(row)
            for col in self.source:
                v=work[col]
                if pd.isna(v):
                    state['gaps'][col]=state['gaps'].get(col,0)+1
                    if state['gaps'][col]<=2:v=state['last'].get(col,np.nan)
                else:
                    state['gaps'][col]=0;state['last'][col]=v
                work[col]=v
                if pd.isna(v):state['blocked']=True
            state['estimated'] |= not bool(row['sensor_disponible'])
            row['prediccion_disponible']=bool(row['sensor_disponible']) and not state['blocked']
            row['calidad_prediccion']='sin_lectura' if not row['sensor_disponible'] else 'historial_incompleto' if state['blocked'] else 'historia_estimada' if state['estimated'] else 'observada'
            work['nh3_mg_n_l']=float(nh3_desde_tan(work['tan_mg_n_l'],work['ph'],work['temperatura']))
            previous=state['previous']
            for col,delta in [('ph','cambio_ph_1h'),('temperatura','cambio_temp_1h'),('oxigeno','cambio_ox_1h'),('tan_mg_n_l','cambio_tan_1h')]:
                work[delta]=0. if row['hora_sim']==0 else work[col]-previous[col] if previous else np.nan
            state['previous']={col:work[col] for col in self.source}
            for col,values in [('nh3_mg_n_l',state['nh3']),('ox_deficit',state['ox'])]:
                values.append(work[col]);del values[:-6]
                finite=[v for v in values if pd.notna(v)]
                work['exposicion_nh3_6h' if col=='nh3_mg_n_l' else 'exposicion_ox_6h']=float(np.mean(finite)) if finite else np.nan
            for col,values in state['history'].items():
                values.append(work[col])
                for window in [6,12,24]:
                    finite=[v for v in values[-window:] if pd.notna(v)]
                    work[f'{col}_media_{window}h']=float(np.mean(finite)) if finite else np.nan
                work[col+'_acumulado']=float(np.nansum(values)) if pd.notna(work[col]) else np.nan
                finite=[v for v in values[-24:] if pd.notna(v)]
                work[col+'_max24h']=float(max(finite)) if finite else np.nan
            originals.append(row);features.append(work)
        return pd.DataFrame(originals),pd.DataFrame(features)


def prepare(raw):
    d = raw.sort_values(['corrida_id','pez_id','hora_sim']).reset_index(drop=True).copy()
    keys = ['corrida_id','pez_id']
    # Se conserva el original para mostrar/exportar la ausencia de sensores.
    work = d.copy()
    source = ['ph','temperatura','oxigeno','tan_mg_n_l','ph_desvio','temp_desvio','ox_deficit']
    work[source] = work.groupby(keys, sort=False)[source].ffill(limit=2)
    gap = work[source].isna().any(axis=1)
    work['_gap'] = gap
    work['_missing'] = ~d.sensor_disponible.astype(bool)
    blocked = work.groupby(keys, sort=False)._gap.cummax()
    estimated = work.groupby(keys, sort=False)._missing.cummax()
    work['nh3_mg_n_l'] = nh3_desde_tan(work.tan_mg_n_l,work.ph,work.temperatura)
    g = work.groupby(keys, sort=False)
    for col, delta in [('ph','cambio_ph_1h'),('temperatura','cambio_temp_1h'),('oxigeno','cambio_ox_1h'),('tan_mg_n_l','cambio_tan_1h')]:
        work[delta] = g[col].diff()
        work.loc[work.hora_sim.eq(0), delta] = 0.
    work['exposicion_nh3_6h'] = g.nh3_mg_n_l.transform(lambda s:s.rolling(6,min_periods=1).mean())
    work['exposicion_ox_6h'] = g.ox_deficit.transform(lambda s:s.rolling(6,min_periods=1).mean())
    features, names = historia(work)
    d['prediccion_disponible'] = d.sensor_disponible.astype(bool) & ~blocked
    d['calidad_prediccion'] = np.select([~d.sensor_disponible.astype(bool),blocked,estimated],
        ['sin_lectura','historial_incompleto','historia_estimada'], default='observada')
    return d, features[names], names
