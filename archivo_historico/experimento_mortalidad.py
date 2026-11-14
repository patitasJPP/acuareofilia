"""Experimento universitario reproducible, sin datos ni credenciales externos.

py experimento_mortalidad.py
Los parametros no ajustados con observaciones son supuestos, no constantes
biologicas validadas. El CSV anterior aporta solo fichas de especie y pesos.
"""
from pathlib import Path
import argparse
import hashlib
import json
import platform

import joblib
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from sklearn.calibration import calibration_curve
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
    precision_recall_curve, precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix, accuracy_score)
from xgboost import XGBClassifier
from entrenar_mortalidad import pipeline

BASE = Path(__file__).resolve().parent
ESCENARIOS = ['estable', 'amonio', 'hipoxia', 'termico', 'ph', 'combinado']
# Lista positiva: ni salud, probabilidad generadora, causa de muerte, IDs,
# semilla, escenario o parametros ocultos pueden entrar al modelo.
FEATURES = ['especie_nombre', 'peso_gramos', 'ph', 'temperatura', 'oxigeno',
    'tan_mg_n_l', 'nh3_mg_n_l', 'densidad_kg_m3', 'volumen_l',
    'ph_desvio', 'temp_desvio', 'ox_deficit', 'exposicion_nh3_6h',
    'exposicion_ox_6h', 'cambio_ph_1h', 'cambio_temp_1h',
    'cambio_ox_1h', 'cambio_tan_1h', 'aireacion_activa', 'filtro_activo']
FUENTES = {
    'amoniaco': 'https://www.epa.gov/wqc/aquatic-life-criteria-ammonia',
    'especiacion': 'https://www.epa.gov/sites/default/files/2019-02/documents/update-wqc-ammonia-1998.pdf',
    'calibracion': 'https://scikit-learn.org/stable/modules/calibration.html',
}


def nh3_desde_tan(tan, ph, temp):
    """TAN y NH3 se expresan ambos como mg de nitrogeno/L, agua dulce.

    EPA 1998 / Emerson: pKa=0.09018+2729.92/(273.2+T).
    No confundir NH3-N con mg de molecula NH3/L (factor 17/14).
    """
    return np.asarray(tan) / (1 + 10 ** (0.09018 + 2729.92 / (273.2 + np.asarray(temp)) - np.asarray(ph)))


def parametros_corrida(semilla):
    rng = np.random.default_rng(semilla)
    return {'tasa_base_h': float(rng.uniform(.00003, .0003)),
        'escala_nh3_n': float(rng.uniform(.02, .06)),
        'coef_agudo': float(rng.uniform(.002, .008)),
        'coef_cronico': float(rng.uniform(.001, .004)),
        'recuperacion': float(rng.uniform(.92, .98)),
        'excrecion_mg_n_kg_h': float(rng.uniform(15, 45)),
        'filtracion_fraccion_h': float(rng.uniform(.025, .12))}


def riesgo_horario(estres, carga, vulnerabilidad, p):
    # Una tasa no negativa se transforma en probabilidad acotada en [0,1].
    tasa = (p['tasa_base_h'] + p['coef_agudo'] * np.asarray(estres) ** 1.4
            + p['coef_cronico'] * np.asarray(carga)) * vulnerabilidad
    return -np.expm1(-np.clip(tasa, 0, 30))


def simular_corrida(fichas, corrida, semilla, escenario, particion, horas=96, peces=16):
    rng = np.random.default_rng(semilla)
    p = parametros_corrida(semilla + 100000)
    filas, eventos, ambientes = [], [], []
    for tanque in range(3):
        seleccion = rng.integers(0, len(fichas), size=peces)
        especie = fichas.iloc[seleccion].reset_index(drop=True)
        pesos = especie.peso_gramos.to_numpy() * rng.lognormal(0, .12, peces)
        vulnerabilidad = rng.lognormal(-.08, .4, peces)  # heterogeneidad no observable
        vivos = np.ones(peces, dtype=bool)
        carga = np.zeros(peces)
        volumen = float(rng.uniform(600, 7000))
        ph_base = float(rng.uniform(6.7, 8.0))
        temp_base = float(rng.uniform(22, 28))
        ph, temp, ox, tan = ph_base, temp_base, float(rng.uniform(6, 8)), float(rng.uniform(.05, .4))
        inicio, fin = int(rng.integers(12, 30)), int(rng.integers(55, 78))
        severidad = float(rng.uniform(.7, 1.8))
        historial = []
        ultimo = None
        for hora in range(horas + 1):
            biomasa = float(pesos[vivos].sum() / 1000)
            densidad = biomasa / volumen * 1000
            crisis = inicio <= hora < fin
            filtro = not (crisis and escenario in ['amonio', 'combinado'])
            aire = not (crisis and escenario in ['hipoxia', 'combinado'])
            # Estado de agua al cierre de t. Variacion temporal autocorrelada,
            # ciclo diario y balances simplificados con unidades explicitas.
            if hora:
                temp_obj = temp_base + 1.0*np.sin(2*np.pi*hora/24)
                if crisis and escenario in ['termico', 'combinado']:
                    temp_obj += 8 * severidad
                temp = float(np.clip(temp + .15*(temp_obj-temp) + rng.normal(0, .1), 10, 42))
                ph_obj = ph_base + (.95*severidad if crisis and escenario in ['ph', 'combinado'] else 0)
                ph = float(np.clip(ph + .12*(ph_obj-ph) + rng.normal(0, .015), 4.5, 10))
                carga_n = biomasa * p['excrecion_mg_n_kg_h'] / volumen
                if crisis and escenario in ['amonio', 'combinado']:
                    carga_n += .10 * severidad  # aporte hipotetico de N por alimento/residuos
                tan = max(0., (tan+carga_n) * (1-p['filtracion_fraccion_h']*filtro))
                if hora % 24 == 0:
                    tan *= .8  # recambio de agua 20%, N de entrada supuesto cero
                consumo = biomasa * float(rng.uniform(150, 250)) / volumen
                ox_obj = max(1., 8.5 - .12*(temp-20))
                ox += (.35 if aire else .025)*(ox_obj-ox) - consumo
                if crisis and escenario in ['hipoxia', 'combinado']:
                    ox -= .35*severidad
                ox = float(np.clip(ox+rng.normal(0, .025), .1, 10))
            nh3 = float(nh3_desde_tan(tan, ph, temp))
            verdadero = np.array([ph, temp, ox, tan])
            # Mediciones sinteticas con ruido: el modelo nunca recibe el valor
            # exacto usado internamente para decidir muertes.
            medido = verdadero + rng.normal(0, [.025, .12, .08, .025])
            medido[2:] = np.maximum(medido[2:], 0)
            nh3_m = float(nh3_desde_tan(medido[3], medido[0], medido[1]))
            historial.append([nh3_m, medido[2]])
            cambios = np.zeros(4) if ultimo is None else medido - ultimo
            ultimo = medido.copy()
            phdev = np.maximum(especie.ph_min.to_numpy()-ph, 0) + np.maximum(ph-especie.ph_max.to_numpy(), 0)
            tdev = np.maximum(especie.temp_min.to_numpy()-temp, 0) + np.maximum(temp-especie.temp_max.to_numpy(), 0)
            odef = np.maximum(especie.oxigeno_min.to_numpy()-ox, 0)
            estres = phdev/2 + tdev/4 + odef/2 + max(0, nh3/p['escala_nh3_n']-1)
            estres = np.minimum(estres, 15)
            ambientes.append({'corrida_id': corrida, 'pecera_id': tanque, 'hora_sim': hora,
                'particion': particion, 'escenario': escenario, 'ph_real': ph, 'temperatura_real': temp,
                'oxigeno_real': ox, 'tan_mg_n_l_real': tan, 'nh3_mg_n_l_real': nh3,
                'vivos': int(vivos.sum()), 'biomasa_kg': biomasa, 'volumen_l': volumen,
                'balance_biomasa_error': biomasa - float(pesos[vivos].sum()/1000)})
            shock = rng.uniform(.5, 2) if rng.random() < .02 else 1.
            for i in np.flatnonzero(vivos):
                ultimas = np.array(historial[-6:])
                fila = {'corrida_id': corrida, 'pez_id': tanque*peces+int(i), 'pecera_id': tanque,
                    'hora_sim': hora, 'particion': particion, 'escenario': escenario,
                    'especie_nombre': especie.especie_nombre.iloc[i], 'peso_gramos': float(pesos[i]),
                    'ph': medido[0], 'temperatura': medido[1], 'oxigeno': medido[2],
                    'tan_mg_n_l': medido[3], 'nh3_mg_n_l': nh3_m,
                    'densidad_kg_m3': densidad, 'volumen_l': volumen,
                    'ph_desvio': max(0, especie.ph_min.iloc[i]-medido[0])+max(0, medido[0]-especie.ph_max.iloc[i]),
                    'temp_desvio': max(0, especie.temp_min.iloc[i]-medido[1])+max(0, medido[1]-especie.temp_max.iloc[i]),
                    'ox_deficit': max(0, especie.oxigeno_min.iloc[i]-medido[2]),
                    'exposicion_nh3_6h': float(ultimas[:, 0].mean()),
                    'exposicion_ox_6h': float(np.maximum(especie.oxigeno_min.iloc[i]-ultimas[:, 1], 0).mean()),
                    'cambio_ph_1h': cambios[0], 'cambio_temp_1h': cambios[1],
                    'cambio_ox_1h': cambios[2], 'cambio_tan_1h': cambios[3],
                    'aireacion_activa': int(aire), 'filtro_activo': int(filtro)}
                if hora == horas:
                    eventos.append({'corrida_id': corrida, 'pez_id': fila['pez_id'],
                        'pecera_id': tanque, 'hora_evento': hora, 'evento': 'censura_fin'})
                    continue  # Sin t+1 observado no se crea ejemplo etiquetado.
                # Transicion t -> t+1. Incluye dano cronico y posibilidad de
                # shock compartido del tanque. No se exporta probabilidad oracle.
                proba = float(riesgo_horario(estres[i], carga[i], vulnerabilidad[i]*shock, p))
                muerte = bool(rng.random() < proba)
                fila['muere_siguiente_hora'] = int(muerte)
                filas.append(fila)
                carga[i] = min(30, carga[i]*p['recuperacion'] + estres[i]*.12)
                if muerte:
                    vivos[i] = False
                    eventos.append({'corrida_id': corrida, 'pez_id': fila['pez_id'], 'pecera_id': tanque,
                        'hora_evento': hora+1, 'evento': 'muerte'})
    return filas, eventos, ambientes, p


def generar(entrada, salida, replicas=8, horas=96, semilla_base=20261113):
    origen = pd.read_csv(entrada)
    fichas = origen[['especie_nombre', 'peso_gramos', 'ph_min', 'ph_max', 'temp_min', 'temp_max', 'oxigeno_min']].drop_duplicates('especie_nombre')
    filas, eventos, ambientes, corridas = [], [], [], []
    for escenario_id, escenario in enumerate(ESCENARIOS):
        # Particion fijada antes de generar y observar los desenlaces.
        roles = ['train']*(replicas-4) + ['calibracion', 'validacion', 'test', 'test']
        for replica, rol in enumerate(roles):
            corrida = escenario_id*replicas+replica
            semilla = semilla_base+corrida*101
            f, e, amb, parametros = simular_corrida(fichas, corrida, semilla, escenario, rol, horas)
            filas.extend(f); eventos.extend(e); ambientes.extend(amb)
            corridas.append({'corrida_id': corrida, 'semilla': semilla, 'escenario': escenario,
                            'particion': rol, **parametros})
            print(f'Corrida {corrida+1}/{replicas*6}: {escenario}, {rol}, {len(filas):,} filas acumuladas', flush=True)
    salida.mkdir(parents=True, exist_ok=True)
    d = pd.DataFrame(filas)
    d.to_csv(salida/'datos.csv', index=False)
    pd.DataFrame(eventos).to_csv(salida/'eventos.csv', index=False)
    pd.DataFrame(ambientes).to_csv(salida/'ambientes.csv', index=False)
    pd.DataFrame(corridas).to_csv(salida/'corridas.csv', index=False)
    fichas.to_csv(salida/'fichas_origen.csv', index=False)
    escribir_json(salida/'metadatos.json', {'version': 'experimento_v2', 'fuente_fichas': str(entrada.resolve()),
        'sha256_fichas_origen': hashlib.sha256(entrada.read_bytes()).hexdigest(),
        'sha256_codigo': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'filas': len(d), 'horas_por_corrida': horas, 'replicas_por_escenario': replicas, 'semilla_base': semilla_base,
        'python': platform.python_version(), 'numpy': np.__version__, 'fuentes': FUENTES,
        'advertencia': 'Datos simulados; todos los parametros de mortalidad y escenario son supuestos universitarios.'})
    auditar(d, pd.DataFrame(eventos), pd.DataFrame(ambientes))
    return d


def escribir_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def auditar(d, eventos, ambientes):
    assert not d.duplicated(['corrida_id', 'pez_id', 'hora_sim']).any()
    assert d[FEATURES].notna().all().all()
    assert d.groupby('corrida_id').particion.nunique().eq(1).all()
    assert d.groupby(['corrida_id', 'pez_id']).pecera_id.nunique().eq(1).all()
    for _, g in d.groupby(['corrida_id', 'pez_id']):
        g = g.sort_values('hora_sim')
        assert g.hora_sim.iloc[0] == 0 and g.hora_sim.diff().dropna().eq(1).all()
        assert g.muere_siguiente_hora.sum() <= 1
        if g.muere_siguiente_hora.sum():
            assert g.muere_siguiente_hora.iloc[-1] == 1
    muertes = eventos[eventos.evento.eq('muerte')]
    positivos = d[d.muere_siguiente_hora.eq(1)]
    ver = positivos.merge(muertes, on=['corrida_id', 'pez_id', 'pecera_id'], validate='one_to_one')
    assert len(ver) == len(muertes) == len(positivos)
    assert ver.hora_evento.eq(ver.hora_sim+1).all()
    assert ambientes.balance_biomasa_error.abs().max() < 1e-10
    assert ambientes[['tan_mg_n_l_real', 'nh3_mg_n_l_real', 'oxigeno_real']].ge(0).all().all()
    assert ambientes.nh3_mg_n_l_real.le(ambientes.tan_mg_n_l_real+1e-12).all()


def metricas(y, prob, umbral):
    pred = prob >= umbral
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {'accuracy': float(accuracy_score(y, pred)), 'precision': float(precision_score(y, pred, zero_division=0)),
        'recall': float(recall_score(y, pred, zero_division=0)), 'f1': float(f1_score(y, pred, zero_division=0)),
        'roc_auc': float(roc_auc_score(y, prob)) if len(np.unique(y)) == 2 else None,
        'pr_auc_ap': float(average_precision_score(y, prob)) if np.sum(y) else None,
        'brier': float(brier_score_loss(y, prob)), 'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)}


def elegir_umbral(y, p):
    precision, recall, th = precision_recall_curve(y, p)
    f2 = 5*precision[:-1]*recall[:-1] / np.maximum(4*precision[:-1]+recall[:-1], 1e-12)
    return float(th[np.argmax(f2)])


def entrenar(d, salida):
    partes = {rol: d[d.particion.eq(rol)].copy() for rol in ['train', 'calibracion', 'validacion', 'test']}
    for a, da in partes.items():
        assert da.muere_siguiente_hora.nunique() == 2, f'{a} no tiene ambas clases'
        for b, db in partes.items():
            if a != b:
                assert not set(da.corrida_id) & set(db.corrida_id)
    tr, ca, va, te = [partes[x] for x in ['train', 'calibracion', 'validacion', 'test']]
    candidatos = {
        'Logistica': LogisticRegression(max_iter=1500, class_weight='balanced', random_state=42),
        'RandomForest': RandomForestClassifier(n_estimators=140, max_depth=12, min_samples_leaf=15,
            class_weight='balanced', n_jobs=4, random_state=42),
        'XGBoost': XGBClassifier(n_estimators=180, max_depth=4, learning_rate=.06, n_jobs=4,
            tree_method='hist', subsample=.85, colsample_bytree=.85, random_state=42, eval_metric='logloss'),
    }
    modelos, validacion = {}, []
    for nombre, candidato in candidatos.items():
        print('Entrenando', nombre, flush=True)
        modelo = pipeline(candidato, tr[FEATURES]).fit(tr[FEATURES], tr.muere_siguiente_hora)
        # Platt sobre corridas distintas. NO reajustar modelo tras calibrar.
        calibrador = LogisticRegression(C=1e6)
        pc = modelo.predict_proba(ca[FEATURES])[:, 1]
        calibrador.fit(logit(np.clip(pc, 1e-6, 1-1e-6)).reshape(-1, 1), ca.muere_siguiente_hora)
        pv = predecir(modelo, calibrador, va[FEATURES])
        umbral = elegir_umbral(va.muere_siguiente_hora, pv)
        validacion.append({'modelo': nombre, 'umbral_f2': umbral, **metricas(va.muere_siguiente_hora, pv, umbral)})
        modelos[nombre] = (modelo, calibrador, umbral)
    pd.DataFrame(validacion).to_csv(salida/'comparativa_validacion.csv', index=False)
    # Elegir por AP ANTES de tocar test.
    mejor = max(validacion, key=lambda r: r['pr_auc_ap'])['modelo']
    modelo, calibrador, umbral = modelos[mejor]
    prob = predecir(modelo, calibrador, te[FEATURES])
    bruto = modelo.predict_proba(te[FEATURES])[:, 1]
    resultado = {'modelo': mejor, 'umbral': umbral,
        'test': metricas(te.muere_siguiente_hora, prob, umbral),
        'brier_sin_calibrar': float(brier_score_loss(te.muere_siguiente_hora, bruto)),
        'prevalencia_test': float(te.muere_siguiente_hora.mean()),
        'baseline_brier': float(brier_score_loss(te.muere_siguiente_hora, np.full(len(te), tr.muere_siguiente_hora.mean()))),
        'baseline_accuracy_siempre_vivo': float(1-te.muere_siguiente_hora.mean()),
        'particiones': {r: {'filas': len(x), 'corridas': int(x.corrida_id.nunique()),
            'muertes': int(x.muere_siguiente_hora.sum())} for r, x in partes.items()}}
    # IC bootstrap por CORRIDA, no por fila. Variacion Monte Carlo, no IC biologico.
    rng = np.random.default_rng(42)
    muestra = te[['corrida_id', 'muere_siguiente_hora']].copy()
    muestra['p'] = prob
    bloques = {k: g for k, g in muestra.groupby('corrida_id')}
    valores = []
    for _ in range(150):
        sub = pd.concat([bloques[k] for k in rng.choice(list(bloques), len(bloques), replace=True)])
        valores.append(metricas(sub.muere_siguiente_hora, sub.p.to_numpy(), umbral))
    resultado['intervalos_bootstrap_corrida_95'] = {c: [float(np.quantile([v[c] for v in valores], q))
        for q in [.025, .975]] for c in ['recall', 'precision', 'f1', 'pr_auc_ap', 'brier']}
    escribir_json(salida/'evaluacion_test.json', resultado)
    joblib.dump({'pipeline': modelo, 'calibrador': calibrador, 'umbral': umbral,
        'features': FEATURES, 'modelo': mejor, 'horizonte_h': 1}, salida/'modelo_calibrado.joblib')
    obs, estimada = calibration_curve(te.muere_siguiente_hora, prob, n_bins=10, strategy='quantile')
    pd.DataFrame({'probabilidad_media': estimada, 'frecuencia_muerte_observada': obs}).to_csv(salida/'calibracion_test.csv', index=False)
    te['probabilidad_muerte_1h'] = prob
    te['alerta'] = prob >= umbral
    te.to_csv(salida/'predicciones_test.csv', index=False)
    agrupar_alertas(te).to_csv(salida/'alertas_por_pecera.csv', index=False)
    # Permutacion en VALIDACION, no reutilizar test para ajustar variables.
    imp = permutation_importance(modelo, va[FEATURES], va.muere_siguiente_hora,
        scoring='average_precision', n_repeats=3, max_samples=min(4000, len(va)), random_state=42)
    pd.DataFrame({'variable': FEATURES, 'caida_ap': imp.importances_mean,
        'desviacion': imp.importances_std}).sort_values('caida_ap', ascending=False).to_csv(salida/'importancias_validacion.csv', index=False)
    # Control negativo: entrenamiento con etiquetas mezcladas, validacion intacta.
    negativo = pipeline(LogisticRegression(max_iter=1000), tr[FEATURES]).fit(tr[FEATURES], rng.permutation(tr.muere_siguiente_hora))
    pn = negativo.predict_proba(va[FEATURES])[:, 1]
    resultado['control_negativo_ap_validacion'] = float(average_precision_score(va.muere_siguiente_hora, pn))
    resultado['control_negativo_prevalencia_validacion'] = float(va.muere_siguiente_hora.mean())
    # Desglose test cerrado: diagnostico, nunca usado para escoger parametros.
    desgloses = []
    for escenario, sub in te.groupby('escenario'):
        desgloses.append({'escenario': escenario, 'n': len(sub), **metricas(sub.muere_siguiente_hora,
            sub.probabilidad_muerte_1h.to_numpy(), umbral)})
    pd.DataFrame(desgloses).to_csv(salida/'test_por_escenario.csv', index=False)
    resultado['revision_necesaria'] = resultado['test']['roc_auc'] > .98
    resultado['nota_accuracy'] = 'En eventos raros accuracy >0.98 puede deberse a predecir siempre vivo; se compara con baseline.'
    escribir_json(salida/'evaluacion_test.json', resultado)
    informe(salida, resultado, validacion)
    print(json.dumps(resultado, indent=2, ensure_ascii=False), flush=True)


def predecir(modelo, calibrador, X):
    p = modelo.predict_proba(X)[:, 1]
    return calibrador.predict_proba(logit(np.clip(p, 1e-6, 1-1e-6)).reshape(-1, 1))[:, 1]


def agrupar_alertas(d):
    # Sumar probabilidades da el numero esperado, incluso con dependencia.
    # No usar 1-producto(1-p): requeriria independencia para prob. >=1 muerte.
    return d.groupby(['corrida_id', 'pecera_id', 'hora_sim', 'especie_nombre']).agg(
        peces_evaluados=('pez_id', 'size'), muertes_esperadas_1h=('probabilidad_muerte_1h', 'sum'),
        riesgo_medio=('probabilidad_muerte_1h', 'mean'), peces_en_alerta=('alerta', 'sum'),
        muertes_observadas=('muere_siguiente_hora', 'sum')).reset_index()


def informe(salida, r, comparativa):
    lineas = ['# Experimento universitario de alerta de mortalidad', '',
        'Objetivo: riesgo de muerte en la siguiente hora, condicionado a estar vivo y observado en t.',
        'Seis escenarios; multiples semillas, peceras nuevas, volumen, peso, ambiente, equipos y parametros inciertos. '
        'Ningun dato real de mortalidad fue utilizado ni se accedio a cuentas externas.', '',
        '## Correcciones aplicadas',
        '- Identidad compuesta corrida/pez; eventos explicitos de muerte y censura; seguimiento desde hora cero.',
        '- Sin reposicion: cada pez aporta como maximo una muerte. La diversidad procede de corridas independientes.',
        '- TAN y NH3-N separados, ambos mg N/L; dependencia de pH y temperatura segun fuente EPA.',
        '- Biomasa calculada a partir del peso de los peces vivos; probabilidad 1-exp(-tasa), siempre acotada.',
        '- Ruido de medicion e historia ambiental; variabilidad individual latente no observable. '
        'Peces con observaciones iguales pueden tener igual riesgo, aunque su desenlace difiera.',
        '- Lista explicita de predictores: se excluyen salud, carga interna, tasa generadora, muerte, '
        'causa, IDs, escenario, semilla, particion y parametros ocultos.',
        '- Corridas completas disjuntas para entrenamiento, calibracion, seleccion/umbral y prueba final.',
        '- Seleccion y one-hot ajustados solo en train; calibracion sigmoid en corridas reservadas; '
        'umbral que maximiza F2 en validacion (prioriza recall).',
        '- Importancias en validacion, control negativo e intervalos Monte Carlo por corrida. '
        'Las correlaciones no permiten inferir causalidad.', '', '## Resultados de prueba independiente',
        f"Modelo elegido antes de test: {r['modelo']}; umbral={r['umbral']:.4f}."]
    lineas += [f'- {k}: {v:.4f}' for k, v in r['test'].items() if k not in ['tn', 'fp', 'fn', 'tp'] and v is not None]
    m = r['test']
    lineas += [f"Matriz [[TN, FP], [FN, TP]]: [[{m['tn']}, {m['fp']}], [{m['fn']}, {m['tp']}]].",
        f"Brier antes de calibrar: {r['brier_sin_calibrar']:.5f}; despues: {m['brier']:.5f}; baseline: {r['baseline_brier']:.5f}.",
        f"Prevalencia test / AP de referencia: {r['prevalencia_test']:.4%}.",
        f"Control negativo AP={r['control_negativo_ap_validacion']:.4f}, prevalencia validacion={r['control_negativo_prevalencia_validacion']:.4f}.",
        '', '## Lo que sigue siendo un supuesto',
        'Las tasas base, respuesta al estres, recuperacion, sensibilidad por individuo, escenarios, '
        'excrecion, intercambio gaseoso y filtracion son supuestos exploratorios, registrados por corrida. '
        'Los limites por especie proceden de las fichas locales, sin validacion externa. '
        'El rango .02-.06 mg NH3-N/L es una escala de sensibilidad del simulador, no un umbral seguro universal.',
        'Los escenarios estables, averias, deterioro y recuperacion se muestrean deliberadamente; '
        'su proporcion no estima la frecuencia de incidentes de una empresa. Las probabilidades '
        'solo estan calibradas para esta mezcla sintetica.',
        'No se simulan nitritos, salinidad, enfermedad transmisible ni depredacion sin fichas fiables. '
        'No se presentan como mecanismos resueltos. La formula quimica no valida la tasa de mortalidad.',
        'No es posible afirmar que el simulador es realista en sentido predictivo sin contrastarlo '
        'con observaciones. Se ha mejorado coherencia, trazabilidad y evaluacion, no demostrado validez biologica.',
        'El test permanece como prueba cerrada. No ajustar parametros tras ver su rendimiento. '
        'Las alertas agregadas indican numero esperado de muertes, no certeza de muerte ni probabilidad de al menos una.',
        '', '## Reproduccion', '`py experimento_mortalidad.py`',
        'El archivo datos.csv es la fuente completa. El Excel del experimento se genera aparte para consulta. '
        'Los resultados anteriores corresponden al motor historico y no describen este experimento.', '', '## Fuentes']
    lineas += [f'- [{k}]({v})' for k, v in FUENTES.items()]
    (salida/'INFORME.md').write_text('\n'.join(lineas)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada', type=Path, default=BASE/'exportaciones/MEGA_DATOS_ML.csv')
    parser.add_argument('--salida', type=Path, default=BASE/'experimento_v2')
    parser.add_argument('--replicas', type=int, default=8)
    parser.add_argument('--horas', type=int, default=96)
    args = parser.parse_args()
    if args.replicas < 5:
        parser.error('Se necesitan al menos 5 replicas por escenario para separar cuatro particiones.')
    from experimento_mortalidad import generar, entrenar
    datos = generar(args.entrada, args.salida, args.replicas, args.horas)
    entrenar(datos, args.salida)
