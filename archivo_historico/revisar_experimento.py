"""Verifica archivos guardados y genera resumen exportable, sin reentrenar."""
import json
import joblib
import numpy as np
import pandas as pd
from experimento_mortalidad import BASE, FEATURES, auditar, predecir, metricas, agrupar_alertas


def revisar():
    out = BASE/'experimento_v2'
    d = pd.read_csv(out/'datos.csv')
    auditar(d, pd.read_csv(out/'eventos.csv'), pd.read_csv(out/'ambientes.csv'))
    assert len(d) > 100000
    bundle = joblib.load(out/'modelo_calibrado.joblib')
    te = d[d.particion.eq('test')].copy()
    p = predecir(bundle['pipeline'], bundle['calibrador'], te[FEATURES])
    guardado = pd.read_csv(out/'predicciones_test.csv')
    np.testing.assert_allclose(p, guardado.probabilidad_muerte_1h, atol=1e-12)
    r = json.loads((out/'evaluacion_test.json').read_text(encoding='utf-8'))
    obtenido = metricas(te.muere_siguiente_hora, p, bundle['umbral'])
    for k, v in obtenido.items():
        assert np.isclose(v, r['test'][k]), k
    assert set(bundle['pipeline']['seleccion'].columnas_) <= set(FEATURES)
    resumen = [['Indicador', 'Valor'], ['Filas simuladas', len(d)], ['Corridas independientes', d.corrida_id.nunique()],
        ['Peceras nuevas', len(d[['corrida_id', 'pecera_id']].drop_duplicates())],
        ['Modelo', r['modelo']], ['Recall test', r['test']['recall']], ['Precision test', r['test']['precision']],
        ['ROC-AUC test', r['test']['roc_auc']], ['AP test', r['test']['pr_auc_ap']],
        ['Prevalencia test', r['prevalencia_test']], ['Umbral elegido en validacion', r['umbral']],
        ['Uso', 'Exploracion universitaria; muchas falsas alarmas y muertes no detectadas'],
        ['Datos completos', 'datos.csv; sin informacion real de mortalidad'],
        ['Quimica', 'TAN y NH3-N en mg nitrogeno/L; agua dulce'],
        ['Supuestos', '../SUPUESTOS_SIMULACION.md'],
        ['Fuente quimica', 'https://www.epa.gov/wqc/aquatic-life-criteria-ammonia']]
    tablas = {'Resumen': resumen}
    for sheet, archivo in [('Corridas', 'corridas.csv'), ('Validacion', 'comparativa_validacion.csv'),
        ('Test_escenarios', 'test_por_escenario.csv'), ('Calibracion', 'calibracion_test.csv'),
        ('Importancias', 'importancias_validacion.csv')]:
        x = pd.read_csv(out/archivo)
        tablas[sheet] = [x.columns.tolist()] + x.astype(object).where(x.notna(), None).values.tolist()
    (out/'resumen_excel.json').write_text(json.dumps(tablas, ensure_ascii=False), encoding='utf-8')
    texto = ['# Evaluacion operativa', '',
        'El modelo se entrega como experimento, no como sistema de alerta confiable.',
        f"En prueba: {r['test']['tp']} muertes detectadas, {r['test']['fn']} omitidas, {r['test']['fp']} falsas alarmas.",
        'La exactitud de siempre predecir supervivencia es mayor que la del modelo: '
        'los eventos son raros, por eso accuracy no sirve como criterio principal.',
        'La calibracion no garantizo mejora: Brier antes '
        f"{r['brier_sin_calibrar']:.6f}, despues {r['test']['brier']:.6f}. Se informa sin elegir con test.",
        'No se modificaron coeficientes ni umbral tras observar test. Para investigar otro horizonte '
        'o politica de alertas se debe fijar el nuevo protocolo y reservar semillas finales nuevas.',
        'La incertidumbre individual y la falta de validacion biologica no quedan resueltas por generar mas filas.', '']
    (out/'EVALUACION_OPERATIVA.md').write_text('\n'.join(texto), encoding='utf-8')
    print(f'OK: {len(d):,} filas, {d.corrida_id.nunique()} corridas; etiquetas, particiones y modelo verificados.')


if __name__ == '__main__':
    revisar()
