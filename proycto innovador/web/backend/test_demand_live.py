"""Reloj comercial, persistencia, continuidad y evaluación sin datos futuros."""
from io import BytesIO
from pathlib import Path
import pickle
import tempfile
import time
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import joblib
import pandas as pd
from fastapi.testclient import TestClient
from demanda.generar import MercadoSemanal, semanal
from . import demand_live as dl, demand


class CommercialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bundle = joblib.load(dl.ROOT / 'demanda/modelos/demanda_v1.joblib')
        motor = MercadoSemanal(bundle['especies'], bundle['semilla'])
        diario = pd.concat([motor.step() for _ in range(104)], ignore_index=True)
        p = {'id': 1, 'creado': '2026-11-14', 'estado': 'pausada', 'paso': 0, 'segundos': .1,
             'base_fin': 103, 'bundle': bundle, 'informe': demand.cargar()[0], 'motor': motor,
             'historia': semanal(diario), 'diario': diario, 'emitidas': None, 'error': '', 'duracion_paso': 0.}
        p['emitidas'] = dl.forecast(p)
        cls.original = pickle.dumps(p)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dbpatch = patch.object(dl, 'DB', Path(self.temp.name) / 'comercial.db'); self.dbpatch.start()
        dl._payload, dl._thread, dl._closed = pickle.loads(self.original), None, False
        dl._wake.clear()
        with dl.connect() as db:
            db.execute('INSERT INTO sesiones VALUES (?,?,?,?,?)', (1, '2026-11-14', 'pausada', 0, self.original))

    def tearDown(self):
        dl.shutdown()
        dl._payload, dl._thread = None, None
        dl._wake.clear()
        self.dbpatch.stop(); self.temp.cleanup()

    def step(self):
        with dl._lock:
            dl.advance(dl._payload)

    def test_forecasts_frozen_before_outcome_and_inventory_continues(self):
        before = dl._payload['emitidas'].copy(deep=True)
        prior = dl._payload['diario'].groupby('especie_nombre').tail(1).set_index('especie_nombre').stock_final
        self.step()
        p = dl._payload
        pd.testing.assert_frame_equal(p['emitidas'].head(len(before)), before)
        first = p['diario'][p['diario'].semana_indice.eq(104)].groupby('especie_nombre').head(1).set_index('especie_nombre').stock_inicial
        pd.testing.assert_series_equal(prior.sort_index(), first.sort_index(), check_names=False)
        ev = dl.evaluation(p, 104)
        self.assertEqual(int(ev.pedidos_solicitados.notna().sum()), 7)
        self.assertTrue(ev.loc[ev.semana_indice.gt(104), 'pedidos_solicitados'].isna().all())
        f = p['emitidas']; self.assertFalse(f.duplicated(['especie_nombre', 'origen_indice', 'horizonte_semanas']).any())
        self.assertTrue((f.origen_indice < f.semana_indice).all())

    def test_recovery_preserves_rng_and_forecasts(self):
        self.step()
        saved = pickle.loads(pickle.dumps(dl._payload))
        self.step()
        expected = dl._payload['diario'].copy()
        dl._payload = saved
        self.step()
        pd.testing.assert_frame_equal(expected, dl._payload['diario'])
        dl._payload = None
        dl.recover()
        self.assertEqual(dl._payload['paso'], 2)
        self.assertEqual(dl._payload['estado'], 'pausada')

    def test_history_view_excludes_future_and_fixed_horizon_counts_once(self):
        for _ in range(4): self.step()
        past = dl.view('Guppy', 1, paso=1)
        self.assertEqual(past['en_vivo']['consultado'], 1)
        self.assertEqual(past['en_vivo']['paso'], 4)
        self.assertEqual(past['en_vivo']['metricas']['n'], 1)
        self.assertTrue(all(r['pedidos_solicitados'] is None for r in past['en_vivo']['comparaciones'] if r['semana_indice'] > 104))
        self.assertEqual(len(past['en_vivo']['semanas_observadas']), 1)
        now = dl.view(semanas=4)
        self.assertEqual(now['en_vivo']['metricas']['n'], 7)
        self.assertEqual(now['en_vivo']['pendientes'], 28)
        with self.assertRaises(ValueError): dl.view(paso=5)

    def test_server_clock_pause_speed_and_resume_without_browser(self):
        dl.control('reanudar', sesion=1)
        deadline = time.monotonic() + 5
        while dl._payload['paso'] < 2 and time.monotonic() < deadline:
            time.sleep(.02)
        dl.control('pausar', sesion=1)
        count = dl._payload['paso']
        self.assertGreaterEqual(count, 2)
        time.sleep(.2)
        self.assertEqual(dl._payload['paso'], count)
        dl.control('velocidad', .2, sesion=1)
        dl.control('reanudar', sesion=1)
        deadline = time.monotonic() + 5
        while dl._payload['paso'] == count and time.monotonic() < deadline: time.sleep(.02)
        dl.control('pausar', sesion=1)
        self.assertGreater(dl._payload['paso'], count)

    def test_failed_save_rolls_back_week_and_retry(self):
        real_save = dl.save
        with patch.object(dl, 'save', side_effect=OSError('disco ocupado')):
            # Worker handles a failed transaction and restores RNG plus issued forecasts.
            dl._payload['estado'] = 'activa'; dl.start_worker()
            deadline = time.monotonic() + 5
            while dl._payload['estado'] != 'error' and time.monotonic() < deadline: time.sleep(.02)
            self.assertEqual(dl._payload['estado'], 'error')
            self.assertEqual(dl._payload['paso'], 0)
        real_save(dl._payload)
        dl.control('reanudar', sesion=1)
        deadline = time.monotonic() + 5
        while dl._payload['paso'] == 0 and time.monotonic() < deadline: time.sleep(.02)
        dl.control('pausar', sesion=1)
        self.assertGreater(dl._payload['paso'], 0)

    def test_completes_all_52_weeks_and_retains_pending_predictions(self):
        for _ in range(52): self.step()
        p = dl._payload
        self.assertEqual(p['estado'], 'terminada')
        self.assertEqual(p['paso'], 52)
        self.assertEqual(len(p['diario']), 156 * 7 * 7)
        out = dl.view(semanas=1)
        self.assertEqual(out['en_vivo']['metricas']['n'], 52*7)
        self.assertEqual(out['en_vivo']['pendientes'], 7)
        with self.assertRaises(ValueError): dl.control('reanudar', sesion=1)
        with ZipFile(BytesIO(dl.export())) as z:
            self.assertIn('pronosticos_emitidos.csv', z.namelist())
            frame = pd.read_csv(BytesIO(z.read('evaluacion_en_vivo.csv')))
            self.assertTrue(frame.loc[frame.semana_indice.gt(155), 'pedidos_solicitados'].isna().all())

    def test_api_validation_and_no_future_results(self):
        from .main import app
        client = TestClient(app)
        self.assertEqual(client.post('/api/demanda/vivo', json={'segundos':0}).status_code, 422)
        self.assertEqual(client.post('/api/demanda/vivo/control', json={'sesion':1,'accion':'velocidad','segundos':.01}).status_code, 422)
        self.assertEqual(client.get('/api/demanda/vivo/vista?paso=1').status_code, 404)
        v = client.get('/api/demanda/vivo/vista').json()
        self.assertEqual(v['en_vivo']['metricas']['n'], 0)
        self.assertIsNone(v['en_vivo']['metricas']['mae'])
        self.assertEqual(client.get('/api/demanda/vivo/exportar').headers['content-type'], 'application/zip')


if __name__ == '__main__': unittest.main()
