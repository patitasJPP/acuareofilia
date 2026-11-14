"""Reconciliar resultados persistidos sin repetir entrenamiento.

Comprueba matrices, cobertura fuera de muestra y predicciones del modelo
guardado. Regenera solo el informe y metadatos con la logica vigente.
"""
from pathlib import Path
import hashlib
import json
import joblib
import numpy as np
import pandas as pd
from entrenar_mortalidad import (BASE, preparar_datos, metricas, generar_informe, guardar_json)


def verificar():
    salida = BASE / 'resultados_ml'
    a = json.loads((salida / 'auditoria_datos.json').read_text(encoding='utf-8'))
    origen = Path(a['archivo'])
    assert hashlib.sha256(origen.read_bytes()).hexdigest() == a['sha256'], 'Cambio el Excel original'
    df = pd.read_excel(origen, sheet_name='MegaDatosML')
    d, features, actualizado = preparar_datos(df)
    a.update(actualizado)
    m = joblib.load(salida / 'modelo_exploratorio.joblib')
    assert m['columnas_entrada'] == features
    preds = pd.read_csv(salida / 'predicciones_fuera_muestra.csv')
    tabla = pd.read_csv(salida / 'comparativa_modelos.csv')
    for (esquema, nombre), sub in preds.groupby(['esquema', 'modelo']):
        assert len(sub) == len(d) and sub.fila.nunique() == len(d)
        assert np.array_equal(d.muere_siguiente_hora.iloc[sub.fila], sub.real)
        for _, grupo in sub.groupby('fila'):
            assert len(grupo) == 1
        identidad = d.iloc[sub.fila][['pez_id', 'pecera_id']].reset_index(drop=True)
        identidad['fold'] = sub.fold.to_numpy()
        assert identidad.groupby('pez_id').fold.nunique().max() == 1
        if esquema == 'pecera_fuera':
            assert identidad.groupby('pecera_id').fold.nunique().max() == 1
        obtenido = metricas(sub.real, sub.probabilidad)
        guardado = tabla[tabla.esquema.eq(esquema) & tabla.modelo.eq(nombre)].iloc[0]
        for k, v in obtenido.items():
            assert np.isclose(v, guardado[k], equal_nan=True), (esquema, nombre, k)
    prob = m['pipeline'].predict_proba(d[features])[:, 1]
    assert len(prob) == len(d) and np.isfinite(prob).all() and ((prob >= 0) & (prob <= 1)).all()
    guardar_json(salida / 'auditoria_datos.json', a)
    eliminadas = list(a['exclusiones_fijas'].items()) + list(m['pipeline']['seleccion'].eliminadas_.items())
    pd.DataFrame(eliminadas, columns=['columna', 'motivo']).to_csv(salida / 'columnas_eliminadas.csv', index=False)
    res = pd.read_csv(salida / 'metricas_por_fold.csv')
    assert len(res) == 51
    res.groupby(['esquema', 'modelo'])[['accuracy', 'precision', 'recall', 'f1', 'roc_auc', 'pr_auc_ap']].agg(
        ['mean', 'std']).to_csv(salida / 'promedios_y_dispersion_por_fold.csv')
    diferencias = pd.read_csv(salida / 'efecto_identificar_pecera.csv', index_col='modelo')
    imp = pd.read_csv(salida / 'importancia_variables.csv')
    alertas = json.loads((salida / 'alertas.json').read_text(encoding='utf-8'))
    generar_informe(salida, a, tabla, diferencias, imp, m['pipeline'], m['modelo'], alertas)
    print(f'OK: 51 ajustes, 9 comparaciones y {len(preds):,} predicciones fuera de muestra reconciliadas.')
    print(f'Modelo cargable: {m["modelo"]}; {len(m["pipeline"]["seleccion"].columnas_)} predictores antes de one-hot, '
          f'{len(m["pipeline"]["preparar"].get_feature_names_out())} columnas codificadas.')


if __name__ == '__main__':
    verificar()
