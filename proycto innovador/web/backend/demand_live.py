"""Reloj comercial del servidor. Un worker, predicciones congeladas y SQLite transaccional.

Solo carga checkpoints creados localmente por esta aplicación. Cada transacción
conserva juntos RNG, inventario, observaciones y pronósticos; no usa rename de Windows.
"""
from datetime import datetime, timezone
from contextlib import contextmanager
from io import BytesIO
import json
import logging
import pickle
import sqlite3
import threading
import time
from zipfile import ZipFile, ZIP_DEFLATED
import joblib
import pandas as pd
from demanda.generar import MercadoSemanal, semanal
from demanda.modelo import predecir, intervalos, metricas, NOMBRES
from .paths import ROOT
from . import demand

DB = ROOT / 'datos/ventas/en_vivo.db'
FIN = 52
_lock = threading.RLock()
_wake = threading.Event()
_thread = None
_payload = None
_closed = False


@contextmanager
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=10)
    try:
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS sesiones (id INTEGER PRIMARY KEY, creado TEXT, estado TEXT, paso INTEGER, datos BLOB)')
            yield db
    finally:
        db.close()


def save(p):
    blob = pickle.dumps(p, protocol=pickle.HIGHEST_PROTOCOL)
    with connect() as db:
        db.execute('UPDATE sesiones SET estado=?, paso=?, datos=? WHERE id=?',
                   (p['estado'], p['paso'], blob, p['id']))


def load(sesion=None):
    global _payload
    if _payload is not None and (sesion is None or sesion == _payload['id']):
        return _payload
    with connect() as db:
        row = db.execute('SELECT datos FROM sesiones WHERE id=?', (sesion,)).fetchone() if sesion is not None else db.execute('SELECT datos FROM sesiones ORDER BY id DESC LIMIT 1').fetchone()
    if not row:
        if sesion is not None:
            raise ValueError('La sesión comercial no existe.')
        return None
    p = pickle.loads(row[0])
    if sesion is None:
        _payload = p
        if p['estado'] == 'activa':
            p['estado'] = 'pausada'  # Recuperar nunca arranca el reloj sin intervención.
            save(p)
    return p


def forecast(p):
    b, hist = p['bundle'], p['historia']
    origen = int(hist.semana_indice.max())
    f = intervalos(predecir(b['algoritmo'], b['modelo'], hist, origen, b['especies']), b['radios'])
    fin = pd.Timestamp(hist.semana_fin.max())
    f['semana_inicio'] = f.horizonte_semanas.map(lambda h: fin + pd.Timedelta(days=1, weeks=int(h)-1))
    f['semana_fin'] = f.semana_inicio + pd.Timedelta(days=6)
    return f


def create(seconds=1.):
    global _payload, _closed
    with _lock:
        actual = load()
        if actual and actual['estado'] == 'activa':
            raise ValueError('Pausa la sesión comercial antes de crear otra.')
        bundle = joblib.load(ROOT / 'demanda/modelos/demanda_v1.joblib')
        info, hist, *_ = demand.cargar()
        if bundle['semilla'] != info['semilla']:
            raise ValueError('El modelo y los datos comerciales no pertenecen al mismo experimento.')
        motor = MercadoSemanal(bundle['especies'], bundle['semilla'])
        base = pd.concat([motor.step() for _ in range(info['semanas'])], ignore_index=True)
        pd.testing.assert_frame_equal(base, pd.read_csv(demand.DATA / 'ventas_diarias.csv'), check_dtype=False)
        history = semanal(base)
        if not bundle['historial_semanal'].equals(history):
            pd.testing.assert_frame_equal(bundle['historial_semanal'], history, check_dtype=False)
        p = {'id': None, 'creado': datetime.now(timezone.utc).isoformat(), 'estado': 'activa',
             'paso': 0, 'segundos': seconds, 'base_fin': int(history.semana_indice.max()),
             'bundle': bundle, 'informe': info, 'motor': motor, 'historia': history,
             'diario': base, 'emitidas': None, 'error': '', 'duracion_paso': 0.}
        # Se guarda la predicción inicial ANTES de producir la primera semana futura.
        p['emitidas'] = forecast(p)
        with connect() as db:
            p['id'] = db.execute('INSERT INTO sesiones (creado,estado,paso) VALUES (?,?,?)',
                (p['creado'], p['estado'], 0)).lastrowid
            db.execute('UPDATE sesiones SET datos=? WHERE id=?', (pickle.dumps(p), p['id']))
        _payload, _closed = p, False
        start_worker()
        _wake.set()
        return status(p)


def advance(p):
    """Paso transaccional invocado bajo lock; no vuelve a emitir predicciones pasadas."""
    start = time.monotonic()
    next_week = p['base_fin'] + p['paso'] + 1
    if not ((p['emitidas'].semana_indice == next_week) & (p['emitidas'].horizonte_semanas == 1)).any():
        raise ValueError('Falta la predicción emitida antes de esta semana.')
    diario = p['motor'].step()
    if int(diario.semana_indice.min()) != next_week:
        raise ValueError('El reloj comercial no coincide con el historial.')
    p['diario'] = pd.concat([p['diario'], diario], ignore_index=True)
    p['historia'] = pd.concat([p['historia'], semanal(diario)], ignore_index=True)
    p['paso'] += 1
    p['emitidas'] = pd.concat([p['emitidas'], forecast(p)], ignore_index=True)
    p['duracion_paso'] = time.monotonic() - start
    if p['paso'] == FIN:
        p['estado'] = 'terminada'
    save(p)


def worker():
    global _payload
    delay = None
    while True:
        with _lock:
            if _closed:
                return
            wait = (_payload['segundos'] if delay is None else delay) if _payload and _payload['estado'] == 'activa' else None
        if _wake.wait(wait):
            _wake.clear()
            delay = None
            continue
        start = time.monotonic()
        with _lock:
            if _closed:
                return
            if not _payload or _payload['estado'] != 'activa':
                continue
            before = pickle.dumps(_payload)
            try:
                advance(_payload)
            except Exception as exc:
                logging.exception('Error de simulación comercial')
                _payload = pickle.loads(before)
                _payload['estado'], _payload['error'] = 'error', str(exc)
                try:
                    save(_payload)
                except Exception:
                    logging.exception('No se pudo guardar el estado del error comercial')
        # El siguiente wait cuenta solo el tiempo restante para el ritmo solicitado.
        with _lock:
            delay = max(.02, _payload['segundos'] - (time.monotonic()-start)) if _payload and _payload['estado'] == 'activa' else None


def start_worker():
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=worker, daemon=True, name='pisciber-ventas')
        _thread.start()


def control(action, seconds=None, sesion=None):
    with _lock:
        p = load()
        if not p:
            raise ValueError('Inicia una simulación comercial primero.')
        if sesion is not None and p['id'] != sesion:
            raise ValueError('Esta sesión es histórica. Selecciona la sesión más reciente para controlarla.')
        if action == 'velocidad':
            if seconds is None or not .1 <= seconds <= 5:
                raise ValueError('El ritmo debe estar entre 0,1 y 5 segundos por semana.')
            p['segundos'] = seconds
        elif action == 'pausar':
            if p['estado'] != 'terminada':
                p['estado'] = 'pausada'
        elif action == 'reanudar':
            if p['paso'] >= FIN:
                raise ValueError('La simulación completó sus 52 semanas. Crea otra para repetirla.')
            p['estado'], p['error'] = 'activa', ''
        else:
            raise ValueError('Control comercial desconocido.')
        save(p)
        start_worker()
        _wake.set()
        return status(p)


def status(p):
    return {'id': p['id'], 'estado': p['estado'], 'paso': p['paso'], 'fin': FIN,
            'segundos': p['segundos'], 'fecha': str(pd.Timestamp(p['historia'].semana_fin.max()).date()),
            'semilla': p['bundle']['semilla'], 'modelo': NOMBRES[p['bundle']['algoritmo']],
            'error': p['error'], 'duracion_paso': p['duracion_paso']}


def sessions():
    with connect() as db:
        return [dict(zip(['id', 'creado', 'estado', 'paso'], r)) for r in db.execute(
            'SELECT id,creado,estado,paso FROM sesiones ORDER BY id DESC')]


def evaluation(p, cut):
    """No revisa resultados posteriores al corte consultado; conserva casos pendientes."""
    f = p['emitidas'][p['emitidas'].origen_indice.le(cut)].copy()
    observed = p['historia'][p['historia'].semana_indice.le(cut)][[
        'especie_nombre', 'semana_indice', 'pedidos_solicitados', 'cantidad_vendida']]
    f = f.merge(observed, on=['especie_nombre', 'semana_indice'], how='left', validate='many_to_one')
    f['error'] = f.prediccion - f.pedidos_solicitados
    f['en_intervalo'] = ((f.pedidos_solicitados >= f.limite_inferior) &
                          (f.pedidos_solicitados <= f.limite_superior)).where(f.pedidos_solicitados.notna())
    return f


def view(especie=None, semanas=4, paso=None, sesion=None):
    with _lock:
        current = load()
        p = load(sesion) if sesion is not None else current
        if p is None:
            v = demand.resumen(especie, semanas)
            v['en_vivo'] = {'estado': 'sin_iniciar', 'paso': 0, 'fin': FIN, 'segundos': 1., 'sesiones': []}
            return v
        if paso is not None and paso > p['paso']:
            raise ValueError('Esa semana todavía no ha ocurrido.')
        consulted = p['paso'] if paso is None else paso
        cut = p['base_fin'] + consulted
        hist = p['historia'][p['historia'].semana_indice.le(cut)].copy()
        future = p['emitidas'][p['emitidas'].origen_indice.eq(cut)].copy()
        ev = evaluation(p, cut)
        meta = {**status(p), 'consultado': consulted, 'historica': current['id'] != p['id'], 'sesiones': sessions()}
        info = dict(p['informe'])
    v = demand.resumen(especie, semanas, datos_vivos=(info, hist, future))
    if especie:
        ev = ev[ev.especie_nombre.eq(especie)]
    # Comparación en vivo para un plazo fijo: cada especie/semana se cuenta una sola vez.
    fixed = ev[ev.horizonte_semanas.eq(semanas)]
    complete = fixed[fixed.pedidos_solicitados.notna()]
    live_metrics = metricas(complete) if len(complete) else {'n': 0, 'mae': None, 'wape': None, 'sesgo': None, 'dentro_20pct': None}
    live_metrics['cobertura_intervalo'] = float(complete.en_intervalo.mean()) if len(complete) else None
    curve = complete.groupby(['semana_indice', 'semana_inicio'], as_index=False).agg(
        pedidos=('pedidos_solicitados', 'sum'), prediccion=('prediccion', 'sum'))
    weekly = hist[hist.semana_indice.gt(p['base_fin'])].copy()
    if especie:
        weekly = weekly[weekly.especie_nombre.eq(especie)]
    weekly = weekly.groupby(['semana_indice', 'semana_inicio', 'semana_fin'], as_index=False).agg(
        pedidos=('pedidos_solicitados', 'sum'), vendidos=('cantidad_vendida', 'sum'),
        no_atendidos=('pedidos_no_atendidos', 'sum'), ingresos=('ingreso_pen', 'sum'),
        mermas=('merma_simulada', 'sum'), stock=('stock_final', 'sum'))
    weekly['paso'] = weekly.semana_indice - p['base_fin']
    v['en_vivo'] = {**meta, 'metricas': live_metrics, 'plazo_evaluado': semanas,
        'pendientes': int(fixed.pedidos_solicitados.isna().sum()),
        'curva': demand.records(curve), 'semanas_observadas': demand.records(weekly),
        'comparaciones': demand.records(fixed.sort_values(['semana_indice', 'especie_nombre']))}
    return v


def export(sesion=None):
    with _lock:
        load()
        p = load(sesion)
        if p is None:
            return demand.exportar()
        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as z:
            for name, frame in [('ventas_diarias', p['diario']), ('ventas_semanales', p['historia']),
                ('pronosticos_emitidos', p['emitidas']), ('evaluacion_en_vivo', evaluation(p, p['base_fin']+p['paso']))]:
                z.writestr(name+'.csv', frame.to_csv(index=False).encode('utf-8-sig'))
            z.writestr('sesion.json', json.dumps(status(p), ensure_ascii=False, indent=2))
            z.writestr('LEEME.txt', 'Datos simulados. Cada pronóstico conserva su fecha de corte y plazo.\n'
                'Una misma semana puede tener pronósticos emitidos a 1, 2, 3 y 4 semanas.\n'
                'Compare un plazo fijo para no contar la misma especie/semana varias veces.\n'
                'Una celda vacía en pedidos_solicitados significa resultado pendiente, nunca cero.\n')
        return output.getvalue()


def recover():
    global _closed
    with _lock:
        _closed = False
        load()


def shutdown():
    global _closed
    with _lock:
        _closed = True
        if _payload and _payload['estado'] == 'activa':
            _payload['estado'] = 'pausada'
            save(_payload)
        _wake.set()
    if _thread:
        _thread.join(timeout=5)
