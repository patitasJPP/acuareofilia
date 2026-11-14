"""Variables observables para v2; imputación causal explícita, sin valores internos."""
import numpy as np
import pandas as pd
from .live_engine import nh3_desde_tan
from mejorar_predicciones import historia


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
