import unittest
import numpy as np
import pandas as pd
from experimento_mortalidad import (nh3_desde_tan, parametros_corrida, riesgo_horario,
    simular_corrida, auditar, FEATURES, agrupar_alertas)


class ExperimentoTest(unittest.TestCase):
    def fichas(self):
        return pd.DataFrame([{'especie_nombre': 'Prueba', 'peso_gramos': 100.,
            'ph_min': 6.5, 'ph_max': 8., 'temp_min': 20., 'temp_max': 28., 'oxigeno_min': 4.}])

    def test_quimica_unidades_y_monotonia(self):
        bajo = float(nh3_desde_tan(1, 7, 20))
        self.assertTrue(0 < bajo < 1)
        self.assertGreater(float(nh3_desde_tan(1, 8, 20)), bajo)
        self.assertGreater(float(nh3_desde_tan(1, 7, 30)), bajo)
        self.assertEqual(float(nh3_desde_tan(0, 7, 25)), 0.)

    def test_hazard_acotado_y_creciente(self):
        p = parametros_corrida(42)
        riesgos = riesgo_horario(np.array([0, 1, 10, 1e6]), 0, 1, p)
        self.assertTrue(((riesgos >= 0) & (riesgos <= 1)).all())
        self.assertTrue((np.diff(riesgos) >= 0).all())

    def test_reproducibilidad_eventos_y_censura(self):
        a = simular_corrida(self.fichas(), 1, 42, 'combinado', 'train', horas=35, peces=4)
        b = simular_corrida(self.fichas(), 1, 42, 'combinado', 'train', horas=35, peces=4)
        self.assertEqual(a, b)
        d, ev, amb = [pd.DataFrame(x) for x in a[:3]]
        auditar(d, ev, amb)
        self.assertTrue(d.hora_sim.lt(35).all())
        self.assertEqual(len(ev), 12)  # cada pez muere o termina censurado
        self.assertFalse(set(FEATURES) & {'salud', 'carga', 'vulnerabilidad', 'escenario',
            'corrida_id', 'pez_id', 'particion', 'muere_siguiente_hora'})

    def test_agregacion_no_asume_independencia(self):
        d = pd.DataFrame({'corrida_id': [1, 1], 'pecera_id': [1, 1], 'hora_sim': [0, 0],
            'especie_nombre': ['A', 'A'], 'pez_id': [1, 2],
            'probabilidad_muerte_1h': [.3, .4], 'alerta': [True, True], 'muere_siguiente_hora': [0, 1]})
        self.assertAlmostEqual(agrupar_alertas(d).muertes_esperadas_1h.iloc[0], .7)


if __name__ == '__main__':
    unittest.main()
