"""Entrenamiento sin interfaz. Ejecutar: py entrenar_mortalidad.py.

Cada ejemplo describe un pez vivo al cierre de t y su muerte en t+1.
No se rellenan objetivos censurados ni se mezclan filas de un pez entre folds.
"""
from pathlib import Path
import argparse
import hashlib
import json
import platform

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

BASE = Path(__file__).resolve().parent
FUGA = ['vivo', 'salud', 'riesgo_muerte', 'punto_critico', 'danos_acumulados',
        'nivel_estres', 'nivel_estres_cat', 'dano_total', 'causa_muerte']
CONSTANTES_SOLICITADAS = ['ox_desvio', 'dano_oxigeno', 'ox_critico',
                        'sobrepoblacion', 'tiene_filtro', 'tiene_aireacion']
REDUNDANTES = {'ph_desvio': 'dano_ph', 'temp_desvio': 'dano_temp',
               'nh3_desvio': 'dano_amoniaco'}


class SeleccionarColumnas(BaseEstimator, TransformerMixin):
    """Aprende constantes y correlaciones SOLO en entrenamiento de cada fold."""
    def __init__(self, umbral=0.95):
        self.umbral = umbral

    def fit(self, X, y=None):
        self.eliminadas_ = {c: 'Constante en entrenamiento' for c in X
                            if X[c].nunique(dropna=False) <= 1}
        self.columnas_ = []
        numericas = X.select_dtypes(include='number').columns
        corr = X[numericas].corr().abs()
        for c in X:
            if c in self.eliminadas_:
                continue
            previas = [p for p in self.columnas_ if p in numericas]
            iguales = [p for p in previas if c in numericas and corr.loc[p, c] > self.umbral]
            if iguales:
                self.eliminadas_[c] = f'Correlacion > {self.umbral} con {iguales[0]} en entrenamiento'
            else:
                self.columnas_.append(c)
        return self

    def transform(self, X):
        return X.loc[:, self.columnas_].copy()


def preparar_datos(df):
    """Valida identidad/tiempo y construye target antes de retirar muertos."""
    requeridas = {'pez_id', 'pecera_id', 'hora_sim', 'murio'}
    if not requeridas <= set(df):
        raise ValueError(f'Faltan columnas: {requeridas - set(df)}. Use el Excel ORIGINAL.')
    if df[list(requeridas)].isna().any().any():
        raise ValueError('Identidad, hora u objetivo contienen nulos.')
    if not df.murio.isin([0, 1]).all():
        raise ValueError('murio debe ser binaria.')
    if not np.isfinite(df.hora_sim).all() or not df.hora_sim.eq(df.hora_sim.round()).all():
        raise ValueError('hora_sim debe contener horas enteras finitas.')
    claves = ['corrida_id', 'pez_id'] if 'corrida_id' in df else ['pez_id']
    if df.duplicated(claves + ['hora_sim']).any():
        raise ValueError('Identidad/hora duplicada: no concatene corridas sin corrida_id.')
    d = df.sort_values(claves + ['hora_sim']).reset_index(drop=True).copy()
    g = d.groupby(claves, sort=False)
    for col in ['pecera_id', 'especie_nombre']:
        if col in d and g[col].nunique().gt(1).any():
            raise ValueError(f'Un pez cambia de {col}; revise IDs y corridas.')
    if (g.murio.cumsum().gt(0) & d.murio.eq(0)).any():
        raise ValueError('Un mismo pez vuelve a estar vivo despues de morir.')
    siguiente_hora = g.hora_sim.shift(-1)
    siguiente_muerte = g.murio.shift(-1)
    valido = d.murio.eq(0) & siguiente_hora.eq(d.hora_sim + 1)
    # Los lags exigen una hora previa consecutiva. No se imputan con datos futuros.
    anterior_hora = g.hora_sim.shift(1)
    for c in ['salud', 'danos_acumulados']:
        if c in d:
            d[c + '_lag1'] = g[c].shift(1).where(anterior_hora.eq(d.hora_sim - 1))
    d['muere_siguiente_hora'] = siguiente_muerte
    temporal = d.loc[valido].copy().reset_index(drop=True)
    temporal['muere_siguiente_hora'] = temporal.muere_siguiente_hora.astype(int)
    if temporal.empty or temporal.muere_siguiente_hora.nunique() != 2:
        raise ValueError('No hay suficientes ejemplos de ambas clases con horizonte de una hora.')
    motivos_fuga = {
        'vivo': 'Inverso de murio; solo se usa murio para elegibilidad',
        'salud': 'Estado contemporaneo excluido por el prompt; se conserva solo salud_lag1',
        'riesgo_muerte': 'Derivado de salud y forzado a 1 en registros de muerte',
        'punto_critico': 'El generador fuerza 1 en filas de muerte',
        'danos_acumulados': 'Estado contemporaneo excluido; se conserva solo danos_acumulados_lag1',
        'nivel_estres': 'Resumen ambiental derivado; exclusion conservadora solicitada, no fuga futura demostrada',
        'nivel_estres_cat': 'Categoria del dano ambiental; exclusion conservadora solicitada',
        'dano_total': 'Suma de desvios ambientales; exclusion conservadora solicitada',
        'causa_muerte': 'Informacion posterior al evento que se quiere predecir',
    }
    razones = {c: motivos_fuga[c] for c in FUGA if c in df}
    razones.update({c: 'Exclusion solicitada; su constancia se informa en auditoria'
                    for c in CONSTANTES_SOLICITADAS if c in df})
    razones.update({c: f'Redundante con {otro}' for c, otro in REDUNDANTES.items() if c in df})
    razones.update({c: 'Identificador/metadato, no predictor' for c in
                    ['pez_id', 'pecera_id', 'pecera_nombre', 'especie_id', 'hora_sim', 'corrida_id'] if c in df})
    razones['murio'] = 'Se usa para elegibilidad y etiqueta futura, no como predictor'
    # Causa de riesgo se calcula con desvíos ambientales, no con causa de muerte.
    # Se excluye por ser resumen redundante y para reducir dependencia del simulador.
    if 'causa_riesgo_principal' in df:
        razones['causa_riesgo_principal'] = 'Resumen ambiental redundante; no fuga directa segun generador'
    features = [c for c in temporal if c not in razones and c != 'muere_siguiente_hora']
    auditoria = {
        'filas_originales': len(df), 'columnas_originales': len(df.columns),
        'peces_originales': g.ngroups, 'peceras': int(df.pecera_id.nunique()),
        'peces_muertos_primera_fila': int(g.head(1).murio.sum()),
        'filas_muertas_excluidas': int(d.murio.eq(1).sum()),
        'filas_vivas_sin_hora_siguiente': int((d.murio.eq(0) & ~valido).sum()),
        'saltos_no_consecutivos': int((siguiente_hora.notna() & ~siguiente_hora.eq(d.hora_sim+1)).sum()),
        'filas_modelables': len(temporal), 'predictores_candidatos': len(features),
        'objetivo_positivo': int(temporal.muere_siguiente_hora.sum()),
        'prevalencia_objetivo': float(temporal.muere_siguiente_hora.mean()),
        'constantes_observadas_original': [c for c in df if df[c].nunique(dropna=False) == 1],
        'exclusiones_fijas': razones,
    }
    return temporal, features, auditoria


def pipeline(modelo, X):
    # Selectores por tipo se ejecutan DESPUES de la seleccion de columnas.
    from sklearn.compose import make_column_selector
    prep = ColumnTransformer([
        ('numericas', Pipeline([('imputar', SimpleImputer(strategy='median', add_indicator=True)),
                                 ('escalar', StandardScaler())]),
         make_column_selector(dtype_include=np.number)),
        ('categoricas', Pipeline([('imputar', SimpleImputer(strategy='most_frequent')),
                                   ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))]),
         make_column_selector(dtype_exclude=np.number)),
    ], sparse_threshold=0)
    return Pipeline([('seleccion', SeleccionarColumnas()), ('preparar', prep), ('modelo', modelo)])


def modelos(y):
    # Los pesos de clase dependen exclusivamente del fold de entrenamiento.
    return {
        'Logistica': LogisticRegression(max_iter=2000, class_weight='balanced', random_state=42),
        'RandomForest': RandomForestClassifier(n_estimators=120, max_depth=10,
            min_samples_leaf=5, class_weight='balanced', n_jobs=4, random_state=42),
        'XGBoost': XGBClassifier(n_estimators=140, max_depth=4, learning_rate=0.07,
            subsample=0.9, colsample_bytree=0.9, tree_method='hist', n_jobs=4,
            eval_metric='logloss', random_state=42, scale_pos_weight=float((y == 0).sum() / (y == 1).sum())),
    }


def metricas(y, prob):
    pred = np.asarray(prob) >= 0.5  # Umbral fijo; no se optimiza con test.
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    ambas = len(np.unique(y)) == 2
    return {'accuracy': accuracy_score(y, pred),
            'precision': precision_score(y, pred, zero_division=0),
            'recall': recall_score(y, pred, zero_division=0),
            'f1': f1_score(y, pred, zero_division=0),
            'roc_auc': roc_auc_score(y, prob) if ambas else np.nan,
            'pr_auc_ap': average_precision_score(y, prob) if ambas else np.nan,
            'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp),
            'n_test': len(y), 'positivos_test': int(np.sum(y))}


def guardar_json(path, datos):
    path.write_text(json.dumps(datos, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def ejecutar(entrada, salida, folds=5):
    salida.mkdir(parents=True, exist_ok=True)
    df = pd.read_excel(entrada, sheet_name='MegaDatosML')
    d, features, auditoria = preparar_datos(df)
    auditoria.update({'archivo': str(entrada.resolve()),
        'sha256': hashlib.sha256(entrada.read_bytes()).hexdigest(),
        'versiones': {'python': platform.python_version(), 'pandas': pd.__version__, 'sklearn': sklearn.__version__}})
    guardar_json(salida / 'auditoria_datos.json', auditoria)
    d[['pez_id', 'pecera_id', 'hora_sim'] + features + ['muere_siguiente_hora']].to_csv(
        salida / 'datos_modelables.csv', index=False)
    pd.DataFrame(list(auditoria['exclusiones_fijas'].items()), columns=['columna', 'motivo']).to_csv(
        salida / 'columnas_eliminadas.csv', index=False)
    y = d.muere_siguiente_hora
    grupos = d.groupby(['corrida_id', 'pez_id'] if 'corrida_id' in d else ['pez_id']).ngroup()
    planes = list(GroupKFold(n_splits=folds).split(d, y, grupos))
    resultados, predicciones, importancias, selecciones, alertas, revisiones = [], [], [], [], [], []
    auditados = set()
    # Mismos folds por pez para comparar con/sin identificacion de pecera.
    esquemas = [('por_pez_sin_pecera', planes, False), ('por_pez_con_pecera', planes, True),
                ('pecera_fuera', list(LeaveOneGroupOut().split(d, y, d.pecera_id)), False)]
    for esquema, particiones, con_pecera in esquemas:
        columnas = features + ([c for c in ['pecera_id', 'pecera_nombre'] if c in d] if con_pecera else [])
        X = d[columnas].copy()
        if con_pecera:
            X['pecera_id'] = X.pecera_id.astype(str)
        for fold, (train, test) in enumerate(particiones, 1):
            assert not set(grupos.iloc[train]) & set(grupos.iloc[test])
            if esquema == 'pecera_fuera':
                assert not set(d.pecera_id.iloc[train]) & set(d.pecera_id.iloc[test])
            if y.iloc[train].nunique() < 2:
                raise ValueError(f'{esquema}/{fold}: entrenamiento con una sola clase.')
            for nombre, modelo in modelos(y.iloc[train]).items():
                print(f'{esquema} fold {fold}/{len(particiones)} {nombre}', flush=True)
                p = pipeline(modelo, X)
                p.fit(X.iloc[train], y.iloc[train])
                prob = p.predict_proba(X.iloc[test])[:, 1]
                m = metricas(y.iloc[test], prob)
                resultados.append({'esquema': esquema, 'fold': fold, 'modelo': nombre, **m})
                selecciones.append({'esquema': esquema, 'fold': fold, 'modelo': nombre,
                    'conservadas': p['seleccion'].columnas_, 'eliminadas': p['seleccion'].eliminadas_})
                predicciones.extend({'esquema': esquema, 'modelo': nombre, 'fold': fold,
                    'fila': int(idx), 'real': int(y.iloc[idx]), 'probabilidad': float(pr)}
                    for idx, pr in zip(test, prob))
                sospecha = m['accuracy'] > .98 or m['roc_auc'] > .98
                if sospecha:
                    alertas.append(f'{esquema}/{fold}/{nombre}: resultado >0.98, revisar antes de usar.')
                    # Auditoria univariable inmediata; no proclamar ausencia de fuga por una AUC baja.
                    if (esquema, fold) not in auditados:
                        auditados.add((esquema, fold))
                        for c in X:
                            univ = pipeline(LogisticRegression(max_iter=1000, class_weight='balanced'), X[[c]])
                            if X.iloc[train][c].nunique() <= 1:
                                continue
                            univ.fit(X.iloc[train][[c]], y.iloc[train])
                            um = metricas(y.iloc[test], univ.predict_proba(X.iloc[test][[c]])[:, 1])
                            revisiones.append({'esquema': esquema, 'fold': fold, 'variable': c, **um})
                if esquema == 'por_pez_sin_pecera':
                    # Permutar la columna original incluye todas sus categorias conjuntamente.
                    imp = permutation_importance(p, X.iloc[test], y.iloc[test],
                        scoring='average_precision', n_repeats=3, random_state=42, n_jobs=1,
                        max_samples=min(2000, len(test)))
                    importancias.extend({'modelo': nombre, 'fold': fold, 'variable': c,
                        'caida_ap': float(v)} for c, v in zip(columnas, imp.importances_mean))
    res = pd.DataFrame(resultados)
    res.to_csv(salida / 'metricas_por_fold.csv', index=False)
    res.groupby(['esquema', 'modelo'])[['accuracy', 'precision', 'recall', 'f1', 'roc_auc', 'pr_auc_ap']].agg(
        ['mean', 'std']).to_csv(salida / 'promedios_y_dispersion_por_fold.csv')
    preds = pd.DataFrame(predicciones)
    preds.to_csv(salida / 'predicciones_fuera_muestra.csv', index=False)
    # Cada fila se predice una vez por modelo/esquema; matrices OOF sin duplicar muestras.
    resumen = []
    for (esquema, nombre), sub in preds.groupby(['esquema', 'modelo']):
        assert not sub.fila.duplicated().any()
        resumen.append({'esquema': esquema, 'modelo': nombre, **metricas(sub.real, sub.probabilidad)})
    tabla = pd.DataFrame(resumen)
    tabla.to_csv(salida / 'comparativa_modelos.csv', index=False)
    imp = pd.DataFrame(importancias).groupby(['modelo', 'variable']).caida_ap.agg(['mean', 'std']).reset_index()
    imp.to_csv(salida / 'importancia_variables.csv', index=False)
    for nombre, sub in imp.groupby('modelo'):
        positivas = sub['mean'].clip(lower=0)
        if positivas.sum() and positivas.max() / positivas.sum() > .5:
            top = sub.loc[sub['mean'].idxmax(), 'variable']
            alertas.append(f'{nombre}: {top} concentra >50% de importancia positiva; es una señal para revisar, no prueba de fuga.')
    guardar_json(salida / 'seleccion_por_fold.json', selecciones)
    if revisiones:
        pd.DataFrame(revisiones).to_csv(salida / 'auditoria_univariable.csv', index=False)
    base = tabla[tabla.esquema.eq('por_pez_sin_pecera')].set_index('modelo')
    con = tabla[tabla.esquema.eq('por_pez_con_pecera')].set_index('modelo')
    diferencias = con[['roc_auc', 'pr_auc_ap', 'f1']] - base[['roc_auc', 'pr_auc_ap', 'f1']]
    diferencias.to_csv(salida / 'efecto_identificar_pecera.csv')
    if diferencias.abs().max().max() > .05:
        alertas.append('Incluir pecera cambia al menos una metrica >0.05; posible dependencia del ambiente.')
    # Seleccion exploratoria por AP agrupada; no se declara una prueba final independiente.
    mejor = base.pr_auc_ap.idxmax()
    final = pipeline(modelos(y)[mejor], d[features]).fit(d[features], y)
    pd.DataFrame(list(auditoria['exclusiones_fijas'].items()) + list(final['seleccion'].eliminadas_.items()),
        columns=['columna', 'motivo']).to_csv(salida / 'columnas_eliminadas.csv', index=False)
    joblib.dump({'pipeline': final, 'columnas_entrada': features, 'modelo': mejor,
                 'objetivo': 'P(muerte en t+1 | vivo al cierre de t)', 'umbral': .5}, salida / 'modelo_exploratorio.joblib')
    guardar_json(salida / 'alertas.json', alertas)
    generar_informe(salida, auditoria, tabla, diferencias, imp, final, mejor, alertas)
    print(tabla.to_string(index=False), flush=True)
    print(f'Resultados guardados en {salida.resolve()}', flush=True)


def generar_informe(salida, a, tabla, diferencias, imp, final, mejor, alertas):
    lineas = ['# Revision y entrenamiento de mortalidad', '',
        f"Entrada: {a['filas_originales']:,} filas y {a['columnas_originales']} columnas.",
        f"Peces unicos observados: {a['peces_originales']:,}; el prompt indicaba 14,516. "
        f"Muertos desde la primera observacion: {a['peces_muertos_primera_fila']:,}.",
        f"Quedan {a['filas_modelables']:,} ejemplos de peces vivos con hora siguiente observada, "
        f"{a['objetivo_positivo']:,} positivos ({a['prevalencia_objetivo']:.2%}).",
        f"Se proponen {a['predictores_candidatos']} predictores; el ajuste final conserva "
        f"{len(final['seleccion'].columnas_)} antes de one-hot. Cada fold selecciona independientemente.", '',
        '## Lo que estaba bien',
        'IDs nuevos al reponer peces, registros horarios y motor estocastico separado del entrenamiento. '
        'Agrupar por pez es necesario. Los lags permiten conservar historia previa sin usar el estado de muerte.', '',
        '## Errores encontrados y decisiones',
        '- El script anterior hacia shift sin comprobar una hora exacta y preprocesaba antes de validar.',
        '- La comparacion con pecera nunca se ejecutaba porque ya habia retirado su ID.',
        '- Elegia XGBoost como mejor de antemano y reutilizaba un split de evaluacion.',
        '- El generador asignaba el total de vivos del tanque a CADA especie, inflando biomasa y consumo de oxigeno.',
        '- El generador limpio acumulaba las mismas muertes cada hora y etiquetaba el final desconocido como supervivencia.',
        '- causa_riesgo_principal se obtiene de desvios ambientales, no de la muerte confirmada. Se excluye por redundancia.',
        '- dano_total y estres no son necesariamente fuga futura segun su formula; se excluyen siguiendo la politica conservadora solicitada.',
        '- Una proporcion 74/26 NO es balance perfecto. La prevalencia que importa es la del objetivo futuro reconstruido.',
        '- No se altera el Excel original. Corregir el generador no corrige retroactivamente su biomasa exportada.', '',
        '## Comparacion de modelos',
        'Metricas fuera de muestra agrupadas. Umbral 0.5; precision/recall/F1 para muerte. '
        'PR-AUC se informa como average precision (AP), no integracion trapezoidal. '
        'TN/FP/FN/TP forman la matriz [[TN, FP], [FN, TP]].', '']
    for r in tabla.to_dict('records'):
        lineas.append(f"- {r['esquema']} / {r['modelo']}: precision={r['precision']:.3f}, "
            f"recall={r['recall']:.3f}, F1={r['f1']:.3f}, ROC-AUC={r['roc_auc']:.3f}, "
            f"AP={r['pr_auc_ap']:.3f}, accuracy={r['accuracy']:.3f}; "
            f"matriz=[[{r['tn']}, {r['fp']}], [{r['fn']}, {r['tp']}]].")
    lineas += ['', '## Efecto de identificar la pecera']
    for nombre, r in diferencias.iterrows():
        lineas.append(f"- {nombre}: cambio ROC-AUC={r.roc_auc:+.3f}, AP={r.pr_auc_ap:+.3f}, F1={r.f1:+.3f}.")
    lineas += ['', 'Una diferencia pequena no descarta memorizacion: volumen, equipos y limites de especie tambien identifican ambientes.',
        '', '## Variables importantes', 'Importancia por permutacion en validacion, medida como caida de AP. Las correlaciones pueden repartir u ocultar importancia.']
    for nombre, sub in imp.groupby('modelo'):
        top = sub.nlargest(5, 'mean')
        lineas.append(f"- {nombre}: " + ', '.join(f"{r.variable} ({r.mean:.4f})" for r in top.itertuples()))
    lineas += ['', '## Alertas'] + (['- '+x for x in alertas] or ['Sin resultados >0.98 ni dominancia >50%; esto no demuestra ausencia de fuga.'])
    lineas += ['', '## Columnas eliminadas y motivo']
    lineas += [f'- {c}: {m}.' for c, m in a['exclusiones_fijas'].items()]
    lineas += [f'- {c}: {m} (ajuste final).' for c, m in final['seleccion'].eliminadas_.items()]
    lineas += ['', '## Conclusiones y limites',
        f'Modelo exploratorio seleccionado por AP agrupada: {mejor}. Se guarda para reproducir, no como modelo validado en granja.',
        'El modelo aprende este simulador. Hay solo siete ambientes, una trayectoria compartida por pecera '
        'y parametros biologicos supuestos. Separar peces deja condiciones de agua compartidas entre train/test; '
        'dejar peceras fuera es la prueba mas exigente de estas salidas.',
        'La seleccion del modelo usa la misma validacion comparativa: no es una estimacion final independiente ni prospectiva. '
        'Para eso hacen falta corridas nuevas con semillas, ambientes y equipos variados y una prueba temporal independiente.',
        'Los peces que mueren antes de su primera observacion quedan fuera: el resultado es condicional a estar vivo y observado. '
        'No deducir muerte de una fila ausente. No usar datos del final como supervivencia sin observar t+1.',
        'Los pesos de clase mejoran sensibilidad pero las probabilidades no estan calibradas. '
        'Se necesita calibracion y elegir el umbral en validacion interna segun el costo de falsas alarmas y muertes omitidas.',
        'Las probabilidades, unidades de amoniaco, filtro, alimento y mecanismos biologicos requieren validacion externa. '
        'No se cambiaron coeficientes para obtener mejores metricas. Los resultados no se trasladan automaticamente a una granja real.', '']
    (salida / 'INFORME.md').write_text('\n'.join(lineas), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada', type=Path, default=BASE / 'exportaciones/MEGA_DATOS_ML.xlsx')
    parser.add_argument('--salida', type=Path, default=BASE / 'resultados_ml')
    parser.add_argument('--folds', type=int, default=5)
    args = parser.parse_args()
    # Importacion canonica para que joblib no guarde clases como __main__.
    from entrenar_mortalidad import ejecutar as entrenar
    entrenar(args.entrada, args.salida, args.folds)
