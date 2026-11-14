"""Pronóstico directo a 1–4 semanas con separación temporal explícita.

Los pedidos futuros son exclusivamente etiquetas. Las variables se calculan
con información disponible hasta el domingo de la fecha de corte.
"""
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor

NOMBRES = {'ultima': 'Última semana', 'media4': 'Promedio de 4 semanas',
           'rf': 'Random Forest', 'boosting': 'Gradient Boosting'}


def variables(historia, especie, origen, horizonte, especies):
    s = historia[historia.especie_nombre.eq(especie)].set_index('semana_indice').sort_index()
    y = s.loc[:origen, 'pedidos_solicitados'].astype(float)
    if len(y) < 12:
        raise ValueError('Se necesitan al menos 12 semanas pasadas por especie.')
    fecha = pd.Timestamp(s.loc[origen, 'semana_fin']) + pd.Timedelta(weeks=horizonte)
    datos = {f'especie_{n}': float(especie == n) for n in especies}
    datos.update({f'pedidos_lag_{lag}': float(y.iloc[-lag]) for lag in [1, 2, 3, 4, 8, 12]})
    for ventana in [4, 8, 12]:
        datos[f'promedio_{ventana}'] = float(y.tail(ventana).mean())
        datos[f'desviacion_{ventana}'] = float(y.tail(ventana).std(ddof=0))
    datos.update(horizonte=horizonte, tendencia_4=float(y.tail(4).mean() - y.iloc[-8:-4].mean()),
                 calendario_seno=float(np.sin(2 * np.pi * fecha.dayofyear / 365.25)),
                 calendario_coseno=float(np.cos(2 * np.pi * fecha.dayofyear / 365.25)))
    return datos


def aprendizaje(historia, corte, especies):
    xs, ys, auditoria = [], [], []
    lookup = historia.set_index(['especie_nombre', 'semana_indice']).pedidos_solicitados
    for origen in range(11, corte):
        for especie in especies:
            for h in range(1, 5):
                if origen + h > corte:
                    continue  # Purga: ninguna etiqueta sobrepasa el corte de entrenamiento.
                xs.append(variables(historia, especie, origen, h, especies))
                ys.append(lookup.loc[(especie, origen + h)])
                auditoria.append({'origen': origen, 'objetivo': origen + h, 'especie': especie})
    return pd.DataFrame(xs), np.asarray(ys), pd.DataFrame(auditoria)


def entrenar(nombre, historia, corte, especies):
    if nombre in ['ultima', 'media4']:
        return None
    x, y, _ = aprendizaje(historia, corte, especies)
    if nombre == 'rf':
        modelo = RandomForestRegressor(n_estimators=180, min_samples_leaf=6,
            max_features=.85, n_jobs=2, random_state=721)
    else:
        modelo = HistGradientBoostingRegressor(loss='poisson', max_iter=160,
            max_leaf_nodes=12, min_samples_leaf=18, l2_regularization=5,
            early_stopping=False, random_state=721)
    modelo.fit(x, y)
    return modelo


def predecir(nombre, modelo, historia, origen, especies):
    filas, xs = [], []
    for especie in especies:
        for h in range(1, 5):
            x = variables(historia, especie, origen, h, especies)
            xs.append(x)
            filas.append({'especie_nombre': especie, 'origen_indice': origen,
                          'semana_indice': origen + h, 'horizonte_semanas': h,
                          'fecha_corte': str(pd.Timestamp(historia.loc[historia.semana_indice.eq(origen), 'semana_fin'].max()).date()),
                          'prediccion': x['pedidos_lag_1'] if nombre == 'ultima' else x['promedio_4']})
    if modelo is not None:
        valores = np.maximum(0, modelo.predict(pd.DataFrame(xs)))
        for fila, valor in zip(filas, valores):
            fila['prediccion'] = float(valor)
    return pd.DataFrame(filas)


def evaluar(nombre, modelo, historia, origenes, especies):
    resultados = pd.concat([predecir(nombre, modelo, historia, o, especies) for o in origenes], ignore_index=True)
    verdad = historia[['especie_nombre', 'semana_indice', 'semana_inicio', 'semana_fin', 'pedidos_solicitados']]
    resultados = resultados.merge(verdad, on=['especie_nombre', 'semana_indice'], validate='many_to_one')
    resultados['modelo'] = nombre
    resultados['error'] = resultados.prediccion - resultados.pedidos_solicitados
    return resultados


def metricas(tabla):
    if tabla.empty:
        return {'n': 0, 'mae': None, 'rmse': None, 'wape': None, 'sesgo': None, 'dentro_20pct': None}
    real = tabla.pedidos_solicitados.to_numpy()
    error = tabla.prediccion.to_numpy() - real
    total = float(real.sum())
    return {'n': len(tabla), 'mae': float(np.abs(error).mean()),
        'rmse': float(np.sqrt(np.mean(error ** 2))),
        'wape': float(np.abs(error).sum() / total) if total else None,
        'sesgo': float(error.sum() / total) if total else None,
        'dentro_20pct': float((np.abs(error) <= .2 * np.maximum(real, 1)).mean())}


def radios_calibracion(tabla, cobertura=.9):
    """Radio relativo calibrado por horizonte; el test no interviene aquí."""
    radios = {}
    for h, grupo in tabla.groupby('horizonte_semanas'):
        scores = np.sort(np.abs(grupo.error) / np.maximum(grupo.prediccion, 5))
        indice = min(len(scores), math.ceil((len(scores) + 1) * cobertura)) - 1
        radios[int(h)] = float(scores[indice])
    return radios


def intervalos(tabla, radios):
    tabla = tabla.copy()
    radio = tabla.horizonte_semanas.map(radios).to_numpy() * np.maximum(tabla.prediccion, 5)
    tabla['limite_inferior'] = np.maximum(0, tabla.prediccion - radio)
    tabla['limite_superior'] = tabla.prediccion + radio
    return tabla
