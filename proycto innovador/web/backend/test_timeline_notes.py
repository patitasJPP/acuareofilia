import unittest
from copy import deepcopy
from .timeline_notes import annotate


class TimelineNotesTests(unittest.TestCase):
    def points(self):
        return [{'hora':h,'esperadas':p,'riesgo_medio':.05,'vivos':n,'sin_prediccion':0}
                for h,p,n in [(0,.1,10),(1,.5,10),(2,.2,4)]]

    def test_population_drop_is_not_described_as_cleaning(self):
        result=annotate(self.points())
        self.assertEqual(result[2]['tendencia'],'Baja la predicción')
        self.assertIn('6 peces vivos menos',' '.join(result[2]['explicaciones']))
        self.assertNotIn('limpi',' '.join(result[2]['explicaciones']))

    def test_actual_events_and_water_changes_are_reported(self):
        water=[{'id':0,'hora_lectura':h,'oxigeno':o,'nh3':n} for h,o,n in [(0,6,.01),(1,2,.04),(2,5,.02)]]
        log=[{'hora':2,'tipo':'accion_aplicada','pecera_id':0,'detalle':'recambio'}]
        result=annotate(self.points(),water,log)
        self.assertIn('Oxígeno disminuyó',' '.join(result[1]['explicaciones']))
        self.assertIn('Acción del usuario aplicada',' '.join(result[2]['explicaciones']))
        self.assertIn('recambio parcial',' '.join(result[2]['explicaciones']))

    def test_future_incident_end_does_not_explain_a_past_drop(self):
        points=self.points();original=deepcopy(points)
        log=[{'hora':3,'tipo':'incidente','detalle':'Fin del incidente; recuperación progresiva'}]
        full=annotate(points,log=log)
        prefix=annotate(original[:2],log=log)
        self.assertEqual(full[:2],prefix)
        self.assertNotIn('restablece',' '.join(full[2]['explicaciones']))
        end=annotate(self.points(),log=[{'hora':2,'tipo':'incidente','detalle':'Fin del incidente; recuperación progresiva'}])
        self.assertIn('funcionamiento automático',' '.join(end[2]['explicaciones']))

    def test_unavailable_prediction_is_not_marked_as_zero_risk(self):
        points=self.points();points[2].update(esperadas=None,sin_prediccion=4)
        result=annotate(points)
        self.assertEqual(result[2]['tendencia'],'Predicción no disponible')
        self.assertIn('4 peces sin predicción',' '.join(result[2]['explicaciones']))


if __name__=='__main__':unittest.main()
