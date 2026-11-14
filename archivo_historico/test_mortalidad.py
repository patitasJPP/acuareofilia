"""Pruebas de horizonte, fugas y eventos con datos pequenos controlados."""
import contextlib
import io
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from entrenar_mortalidad import preparar_datos, SeleccionarColumnas, metricas


class PruebasTemporales(unittest.TestCase):
    def ejemplo(self):
        return pd.DataFrame([
            # El pez 1 muere entre t=2 y t=3; t=1 debe ser negativo.
            [1, 1, 1, 0, 90., 0.], [1, 1, 2, 0, 50., 1.], [1, 1, 3, 1, 0., 3.],
            # Salto de horas: nunca etiquetar t=1 como muerte en la hora 2.
            [2, 2, 1, 0, 80., 0.], [2, 2, 3, 1, 0., 4.],
            # Muerto en primera observacion, no sirve como predictor.
            [3, 3, 1, 1, 0., 9.],
        ], columns=['pez_id', 'pecera_id', 'hora_sim', 'murio', 'salud', 'danos_acumulados'])

    def test_horizonte_y_lags(self):
        d, features, a = preparar_datos(self.ejemplo())
        self.assertEqual(d.hora_sim.tolist(), [1, 2])
        self.assertEqual(d.muere_siguiente_hora.tolist(), [0, 1])
        self.assertTrue(np.isnan(d.salud_lag1.iloc[0]))
        self.assertEqual(d.salud_lag1.iloc[1], 90.)
        self.assertFalse(set(features) & {'murio', 'salud', 'danos_acumulados', 'pez_id'})
        self.assertEqual(a['saltos_no_consecutivos'], 1)

    def test_rechaza_identidad_duplicada(self):
        d = self.ejemplo()
        with self.assertRaises(ValueError):
            preparar_datos(pd.concat([d, d.iloc[[0]]]))

    def test_rechaza_resurreccion(self):
        d = self.ejemplo()
        d.loc[1, 'murio'] = 1
        d.loc[2, 'murio'] = 0
        with self.assertRaises(ValueError):
            preparar_datos(d)

    def test_seleccion_solo_aprende_train(self):
        train = pd.DataFrame({'a': [1, 2, 3], 'b': [2, 4, 6], 'c': [0, 0, 0]})
        s = SeleccionarColumnas().fit(train)
        test = pd.DataFrame({'a': [1], 'b': [999], 'c': [10]})
        self.assertEqual(s.transform(test).columns.tolist(), ['a'])

    def test_una_clase_auc_indefinida(self):
        m = metricas(pd.Series([0, 0]), [.1, .8])
        self.assertTrue(np.isnan(m['roc_auc']))
        self.assertEqual((m['tn'], m['fp'], m['fn'], m['tp']), (1, 1, 0, 0))

    def test_generador_eventos_y_censura(self):
        import generar_datos_limpios as gen
        esp = {'nombre': 'Prueba', 'consumo_o2': 1., 'ph_min': 6., 'ph_max': 8.,
               'temp_min': 20., 'temp_max': 30., 'oxigeno_min': 3., 'amoniaco_max': .1}
        pop = [{'id_pecera': 1, 'id_especie': e, 'cantidad': n, 'peso_g': 10.,
                'alimento_g_h': 1., 'amoniaco_mg_por_g': .1} for e, n in [(1, 2), (2, 1)]]
        agua = {1: {'ph': 7., 'temperatura_c': 25., 'oxigeno_mg_l': 7., 'amoniaco_mg_l': 0.}}
        datos = ({1: {'volumen_l': 1000.}}, agua, {}, {1: esp, 2: esp}, pop)
        tick = [0]
        conteos = []

        def evolucionar(a, equipo, poblaciones):
            tick[0] += 1
            conteos.append([p['vivos'] for p in poblaciones])
            return {**a, 'biomasa_kg': .03}

        def eventos(peces, *args):
            for p in peces:
                if (p['id'] == 2 and tick[0] == 1) or (p['id'] == 1 and tick[0] == 2):
                    p['vivo'] = False
                    p['salud'] = 0.
                    p['causa_muerte'] = 'Prueba'

        with patch.object(gen, 'HORAS_MAX', 3), patch.object(gen, 'consultar_datos', return_value=datos), \
             patch.object(gen, 'evolucionar_agua', side_effect=evolucionar), \
             patch.object(gen, 'evaluar_eventos_peces', side_effect=eventos), \
             patch.object(gen, 'exportar_excel_limpio', return_value=True):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                filas, n = gen.generar_datos_limpios()
        self.assertEqual(n, 3)
        self.assertEqual(conteos, [[2, 1], [1, 1], [0, 1]])
        self.assertEqual([(f['pez_id'], f['hora_sim'], f['muere_siguiente_hora']) for f in filas],
                         [(1, 1, 1), (3, 1, 0), (3, 2, 0)])
        self.assertIn('Total muertes: 2', out.getvalue())


if __name__ == '__main__':
    unittest.main()
