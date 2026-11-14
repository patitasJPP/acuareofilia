"""Uso: .venv/Scripts/python.exe -m demanda.ejecutar --semilla 20261114."""
import argparse
import json
import os
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '2')
import joblib
import numpy as np
import pandas as pd
from .generar import generar, semanal
from .modelo import NOMBRES, entrenar, evaluar, metricas, radios_calibracion, intervalos, predecir

ROOT = Path(__file__).resolve().parents[1]


def ejecutar(semilla=20261114):
    datos = ROOT / 'datos/ventas'
    salida = ROOT / 'resultados/demanda'
    modelos = ROOT / 'demanda/modelos'
    for p in [datos, salida, modelos]:
        p.mkdir(parents=True, exist_ok=True)
    especies = pd.read_csv(ROOT / 'simulacion/datos_base/fichas_origen.csv').especie_nombre.tolist()
    diario, supuestos = generar(especies, semilla)
    historia = semanal(diario)
    diario.to_csv(datos / 'ventas_diarias.csv', index=False, encoding='utf-8-sig')
    historia.to_csv(datos / 'ventas_semanales.csv', index=False, encoding='utf-8-sig')
    validacion, modelos_prueba = [], {}
    # 0–55 entrenamiento, 56–71 selección, 72–87 intervalos, 88–103 test.
    for nombre in NOMBRES:
        m = entrenar(nombre, historia, 55, especies)
        v = evaluar(nombre, m, historia, range(55, 71, 4), especies)
        validacion.append({'modelo': nombre, 'nombre': NOMBRES[nombre], **metricas(v)})
    ganador = min(validacion, key=lambda r: r['wape'])['modelo']
    pruebas = []
    for nombre in NOMBRES:
        m = entrenar(nombre, historia, 71, especies)
        modelos_prueba[nombre] = m
        if m is not None:
            joblib.dump({'modelo': m, 'algoritmo': nombre, 'especies': especies,
                         'entrenado_hasta_semana': 71}, modelos / f'comparado_{nombre}.joblib')
        pruebas.append(evaluar(nombre, m, historia, range(87, 103, 4), especies))
    test_todos = pd.concat(pruebas, ignore_index=True)
    calibracion = evaluar(ganador, modelos_prueba[ganador], historia, range(71, 87, 4), especies)
    radios = radios_calibracion(calibracion)
    test = intervalos(test_todos[test_todos.modelo.eq(ganador)], radios)
    test['en_intervalo'] = (test.pedidos_solicitados >= test.limite_inferior) & (test.pedidos_solicitados <= test.limite_superior)
    comparacion = []
    for v in validacion:
        nombre = v['modelo']
        comparacion.append({'modelo': nombre, 'nombre': NOMBRES[nombre],
            'wape_validacion': v['wape'], 'seleccionado': nombre == ganador,
            **metricas(test_todos[test_todos.modelo.eq(nombre)])})
    # Modelo de uso: se reajusta con todo el historial DESPUÉS de cerrar la evaluación.
    final = entrenar(ganador, historia, 103, especies)
    futuro = intervalos(predecir(ganador, final, historia, 103, especies), radios)
    fin = pd.Timestamp(historia.semana_fin.max())
    futuro['semana_inicio'] = futuro.horizonte_semanas.map(lambda h: fin + pd.Timedelta(days=1, weeks=int(h)-1))
    futuro['semana_fin'] = futuro.semana_inicio + pd.Timedelta(days=6)
    por_especie = [{'especie_nombre': e, **metricas(g), 'cobertura_intervalo': float(g.en_intervalo.mean())}
                   for e, g in test.groupby('especie_nombre')]
    por_horizonte = [{'horizonte_semanas': int(h), **metricas(g), 'cobertura_intervalo': float(g.en_intervalo.mean())}
                     for h, g in test.groupby('horizonte_semanas')]
    protocolo = []
    for nombre, inicio, fin_idx, uso in [('Entrenamiento', 0, 55, 'Ajustar candidatos'),
        ('Validación', 56, 71, 'Elegir por menor WAPE'), ('Calibración', 72, 87, 'Estimar amplitud de intervalos'),
        ('Prueba reservada', 88, 103, 'Medir errores después de fijar modelo e intervalos')]:
        sub = historia[historia.semana_indice.between(inicio, fin_idx)]
        protocolo.append({'etapa': nombre, 'inicio': str(sub.semana_inicio.min().date()),
            'fin': str(sub.semana_fin.max().date()), 'semanas': fin_idx-inicio+1, 'uso': uso})
    informe = {'version': 'demanda_v1', 'semilla': semilla, 'origen': 'simulado',
        'objetivo': 'Peces solicitados por especie y semana, incluyendo pedidos no atendidos por falta de stock.',
        'modelo': ganador, 'nombre_modelo': NOMBRES[ganador], 'especies': especies,
        'filas_diarias': len(diario), 'semanas': 104, 'fecha_corte': str(fin.date()),
        'comparacion': comparacion, 'por_especie': por_especie, 'por_horizonte': por_horizonte,
        'test': {**metricas(test), 'cobertura_intervalo': float(test.en_intervalo.mean())},
        'protocolo': protocolo, 'cobertura_objetivo': .9, 'radios': radios, 'supuestos': supuestos,
        'limitaciones': [
            'Todos los pedidos, ventas, precios, reposiciones y mermas son simulados.',
            'La demanda se mide con pedidos registrados, incluidos los no atendidos; las ventas pueden quedar limitadas por el stock.',
            'Los cortes avanzan cada cuatro semanas: cada semana objetivo se evalúa una sola vez por especie.',
            'La selección usa validación; la calibración de intervalos usa otro período; el test se conserva separado.',
            'Durante la prueba el modelo permanece fijo y recibe solo el historial ya observado en cada corte.',
            'Los intervalos son empíricos por especie y semana. Su cobertura futura no está garantizada en series temporales.',
            'El modelo de uso se reajusta con las 104 semanas. Las métricas mostradas corresponden al modelo congelado de evaluación.',
            'No se suman intervalos individuales para afirmar cobertura de un total; los totales muestran únicamente estimaciones centrales.',
            'El stock comercial es independiente de las corridas de mortalidad, que representan otros períodos y poblaciones.',
            'Las cantidades futuras son estimaciones de demanda, no compras confirmadas ni promesas de venta.'
        ]}
    for nombre, tabla in [('predicciones_test', test), ('predicciones_test_modelos', test_todos),
                          ('calibracion', calibracion), ('pronostico', futuro)]:
        tabla.to_csv(salida / f'{nombre}.csv', index=False, encoding='utf-8-sig')
    (salida / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding='utf-8')
    joblib.dump({'modelo': final, 'algoritmo': ganador, 'especies': especies, 'radios': radios,
                 'historial_semanal': historia,
                 'fecha_corte': informe['fecha_corte'], 'semilla': semilla}, modelos / 'demanda_v1.joblib')
    print(json.dumps({'modelo': informe['nombre_modelo'], 'filas': len(diario), 'test': informe['test']}, ensure_ascii=False))
    return informe


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--semilla', type=int, default=20261114)
    ejecutar(parser.parse_args().semilla)
