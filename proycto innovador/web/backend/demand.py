"""Lectura de resultados comerciales persistidos; consultar no reentrena."""
from functools import lru_cache
from io import BytesIO
import json
from zipfile import ZipFile, ZIP_DEFLATED
import pandas as pd
from .paths import ROOT
from demanda.modelo import metricas

DATA = ROOT / 'datos/ventas'
RESULTS = ROOT / 'resultados/demanda'


@lru_cache(maxsize=2)
def _read(signature):
    return (json.loads((RESULTS / 'informe.json').read_text(encoding='utf-8')),
            pd.read_csv(DATA / 'ventas_semanales.csv'),
            pd.read_csv(RESULTS / 'pronostico.csv'),
            pd.read_csv(RESULTS / 'predicciones_test.csv'),
            pd.read_csv(RESULTS / 'predicciones_test_modelos.csv'))


def cargar():
    archivos = [RESULTS / 'informe.json', DATA / 'ventas_semanales.csv',
                RESULTS / 'pronostico.csv', RESULTS / 'predicciones_test.csv',
                RESULTS / 'predicciones_test_modelos.csv']
    if not all(p.exists() for p in archivos):
        raise FileNotFoundError('Faltan los datos de demanda. Ejecuta: .venv/Scripts/python.exe -m demanda.ejecutar')
    return _read(tuple(p.stat().st_mtime_ns for p in archivos))


def records(tabla):
    return json.loads(tabla.to_json(orient='records', date_format='iso'))


def resumen(especie=None, semanas=4, datos_vivos=None):
    info, historia, futuro, test, comparacion = cargar()
    if datos_vivos is not None:
        info, historia, futuro = datos_vivos
        info = {**info, 'fecha_corte_base': info['fecha_corte'],
                'fecha_corte': str(pd.Timestamp(historia.semana_fin.max()).date())}
    if especie and especie not in info['especies']:
        raise ValueError('La especie no pertenece al catálogo del proyecto.')
    if especie:
        historia = historia[historia.especie_nombre.eq(especie)]
        futuro = futuro[futuro.especie_nombre.eq(especie)]
        test = test[test.especie_nombre.eq(especie)]
        comparacion = comparacion[comparacion.especie_nombre.eq(especie)]
    futuro = futuro[futuro.horizonte_semanas.le(semanas)]
    test = test[test.horizonte_semanas.le(semanas)]
    comparacion = comparacion[comparacion.horizonte_semanas.le(semanas)]
    historico = historia.groupby(['semana_indice', 'semana_inicio', 'semana_fin'], as_index=False).agg(
        pedidos=('pedidos_solicitados', 'sum'), vendidos=('cantidad_vendida', 'sum'),
        no_atendidos=('pedidos_no_atendidos', 'sum'), ingresos=('ingreso_pen', 'sum'))
    pronostico = futuro.groupby(['horizonte_semanas', 'semana_inicio', 'semana_fin'], as_index=False).agg(
        prediccion=('prediccion', 'sum'))
    if especie:
        pronostico = pronostico.merge(futuro[['horizonte_semanas', 'limite_inferior', 'limite_superior']], on='horizonte_semanas')
    resultado = metricas(test)
    resultado['cobertura_intervalo'] = float(test.en_intervalo.mean())
    tabla_modelos = []
    for row in info['comparacion']:
        datos = comparacion[comparacion.modelo.eq(row['modelo'])]
        tabla_modelos.append({**row, **metricas(datos)})
    # Para la curva de prueba, suma de estimaciones centrales de la misma semana.
    curva_test = test.groupby(['semana_indice', 'semana_inicio', 'semana_fin'], as_index=False).agg(
        pedidos=('pedidos_solicitados', 'sum'), prediccion=('prediccion', 'sum'))
    actuales = historia[historia.semana_indice.eq(historia.semana_indice.max())]
    stock = actuales[['especie_nombre', 'stock_final']]
    especies_futuras = futuro.groupby('especie_nombre', as_index=False).prediccion.sum().merge(stock, on='especie_nombre')
    # Solo comparación orientativa, no compra sugerida: faltan plazos, lotes y mortalidad futura.
    especies_futuras['diferencia_demanda_stock'] = (especies_futuras.prediccion - especies_futuras.stock_final).clip(lower=0)
    anteriores = historia[historia.semana_indice.gt(historia.semana_indice.max()-semanas)]
    return {'informe': info, 'especie': especie, 'semanas': semanas, 'metricas': resultado,
        'comparacion': tabla_modelos, 'historial': records(historico.tail(26)),
        'pronostico': records(pronostico), 'detalle_pronostico': records(futuro),
        'por_especie': records(especies_futuras), 'prueba': records(curva_test),
        'errores': records(test.sort_values(['semana_indice', 'especie_nombre'])),
        'totales': {'demanda_prevista': float(futuro.prediccion.sum()),
                    'pedidos_recientes': int(anteriores.pedidos_solicitados.sum()),
                    'ventas_recientes': int(anteriores.cantidad_vendida.sum()),
                    'stock_actual': int(actuales.stock_final.sum()),
                    'no_atendidos': int(anteriores.pedidos_no_atendidos.sum())}}


def exportar():
    """CSV abiertos en Excel, junto con el protocolo y el modelo reproducible."""
    cargar()
    archivo = BytesIO()
    with ZipFile(archivo, 'w', ZIP_DEFLATED) as z:
        for p in [*DATA.glob('*.csv'), *RESULTS.glob('*.csv'), RESULTS / 'informe.json']:
            z.write(p, arcname=p.name)
        z.writestr('LEEME.txt',
            'PISCIBER · DATOS COMERCIALES SIMULADOS\n'
            'Los CSV usan UTF-8 con BOM y coma como separador. En Excel: Datos > Desde texto/CSV.\n'
            'Pedidos solicitados es la demanda; cantidad vendida depende del stock.\n'
            'Las predicciones futuras no son ventas confirmadas.\n'
            'predicciones_test.csv contiene la evaluación del método seleccionado.\n'
            'predicciones_test_modelos.csv compara los cuatro candidatos.\n'
            'El modelo se elige con validación, antes del test. Consulte informe.json.\n'
            'Los intervalos son individuales por especie/semana y no se suman para un total.\n')
    return archivo.getvalue()
