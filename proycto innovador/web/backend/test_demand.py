"""Reproducibilidad comercial, ausencia de información futura y API."""
from io import BytesIO
import json
import unittest
from zipfile import ZipFile
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from demanda.generar import generar, semanal
from demanda.modelo import variables, aprendizaje, predecir, metricas, radios_calibracion, intervalos
from . import demand


class DemandDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diario, _ = generar(['Tilapia', 'Guppy'], 531)
        cls.historia = semanal(cls.diario)

    def test_reproducible_and_balanced_stock(self):
        repetido, _ = generar(['Tilapia', 'Guppy'], 531)
        pd.testing.assert_frame_equal(self.diario, repetido)
        d = self.diario
        np.testing.assert_array_equal(d.stock_inicial + d.reposicion - d.merma_simulada - d.cantidad_vendida, d.stock_final)
        np.testing.assert_array_equal(d.cantidad_vendida + d.pedidos_no_atendidos, d.pedidos_solicitados)
        self.assertTrue((d.stock_final >= 0).all())
        for _, g in d.groupby('especie_nombre'):
            np.testing.assert_array_equal(g.stock_final.to_numpy()[:-1], g.stock_inicial.to_numpy()[1:])
        self.assertEqual(len(d), 728 * 2)
        self.assertEqual(self.historia.semana_indice.nunique(), 104)

    def test_future_changes_do_not_change_features_or_forecast(self):
        s = self.historia.copy()
        especies = ['Tilapia', 'Guppy']
        antes = variables(s, 'Tilapia', 30, 4, especies)
        pred = predecir('media4', None, s, 30, especies)
        s.loc[s.semana_indice > 30, 'pedidos_solicitados'] = 999999
        self.assertEqual(antes, variables(s, 'Tilapia', 30, 4, especies))
        pd.testing.assert_frame_equal(pred, predecir('media4', None, s, 30, especies))
        _, y, audit = aprendizaje(s, 30, especies)
        self.assertLessEqual(audit.objetivo.max(), 30)
        self.assertTrue((audit.origen < audit.objetivo).all())
        self.assertTrue((y < 999999).all())

    def test_interval_and_error_definitions(self):
        x = pd.DataFrame({'horizonte_semanas': [1]*10, 'prediccion': [100.]*10,
                          'pedidos_solicitados': [80.]*10, 'error': [20.]*10})
        self.assertAlmostEqual(metricas(x)['wape'], .25)
        self.assertAlmostEqual(metricas(x)['mae'], 20.)
        self.assertAlmostEqual(metricas(x)['sesgo'], .25)
        r = radios_calibracion(x)
        out = intervalos(x, r)
        self.assertTrue((out.limite_inferior == 80.).all())
        self.assertTrue((out.limite_superior == 120.).all())


class DemandIntegrationTests(unittest.TestCase):
    def test_aggregates_and_individual_filters(self):
        full = demand.resumen()
        self.assertEqual(full['metricas']['n'], 112)
        self.assertEqual(len(full['detalle_pronostico']), 28)
        self.assertAlmostEqual(full['totales']['demanda_prevista'], sum(r['prediccion'] for r in full['por_especie']))
        self.assertTrue(all('limite_inferior' not in r for r in full['pronostico']))
        one = demand.resumen('Guppy', 1)
        self.assertEqual(one['metricas']['n'], 4)
        self.assertEqual(len(one['detalle_pronostico']), 1)
        self.assertTrue(all(r['especie_nombre'] == 'Guppy' for r in one['errores']))
        self.assertIn('limite_inferior', one['pronostico'][0])
        self.assertTrue(all(r['semana_inicio'] > r['fecha_corte'] for r in one['errores']))
        with self.assertRaises(ValueError):
            demand.resumen('Especie inexistente')

    def test_zip_contains_data_and_protocol(self):
        with ZipFile(BytesIO(demand.exportar())) as z:
            self.assertIn('ventas_diarias.csv', z.namelist())
            self.assertIn('pronostico.csv', z.namelist())
            self.assertIn('predicciones_test_modelos.csv', z.namelist())
            self.assertEqual(json.loads(z.read('informe.json'))['origen'], 'simulado')
            self.assertTrue(z.read('ventas_diarias.csv').startswith(b'\xef\xbb\xbf'))

    def test_api_validates_filters_and_returns_download(self):
        from .main import app
        # Sin lifespan: no altera ni recupera las corridas del usuario.
        client = TestClient(app)
        self.assertEqual(client.get('/api/demanda/resumen?semanas=0').status_code, 422)
        self.assertEqual(client.get('/api/demanda/resumen?semanas=5').status_code, 422)
        self.assertEqual(client.get('/api/demanda/resumen?especie=NoExiste').status_code, 404)
        r = client.get('/api/demanda/resumen', params={'especie': 'Trucha arcoíris', 'semanas': 2})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['metricas']['n'], 8)
        self.assertEqual(client.get('/api/demanda/exportar').headers['content-type'], 'application/zip')


if __name__ == '__main__':
    unittest.main()
