import unittest
import pandas as pd
from mejorar_predicciones import historia, objetivo

class MejoraTest(unittest.TestCase):
    def datos(self):
        return pd.DataFrame({'corrida_id':[1]*5,'pez_id':[1]*5,'hora_sim':list(range(5)),
            'nh3_mg_n_l':[1.,2.,3.,4.,5.],'ox_deficit':[0.]*5,'temp_desvio':[0.]*5,
            'ph_desvio':[0.]*5,'muere_siguiente_hora':[0,0,0,0,1]})
    def test_historia_no_usa_futuro(self):
        d=self.datos(); a,_=historia(d)
        d.loc[4,'nh3_mg_n_l']=999
        b,_=historia(d)
        pd.testing.assert_frame_equal(a.iloc[:4],b.iloc[:4])
        self.assertEqual(a.nh3_mg_n_l_acumulado.iloc[2],6.)
    def test_horizontes_y_censura(self):
        d=self.datos()
        e=pd.DataFrame({'corrida_id':[1],'pez_id':[1],'hora_evento':[5],'evento':['muerte']})
        x=objetivo(d,e,1,fin=6)
        self.assertEqual(x.target.tolist(),[0,0,0,0,1])
        x=objetivo(d,e,3,fin=6)
        self.assertEqual(x.hora_sim.tolist(),[0,1,2,3])
        self.assertEqual(x.target.tolist(),[0,0,1,1])

if __name__=='__main__': unittest.main()
