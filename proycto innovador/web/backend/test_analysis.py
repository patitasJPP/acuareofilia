"""Seguimiento al corte, mortalidad y atención con una base de prueba aislada."""
import unittest
from unittest.mock import patch
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from . import analysis
from .storage import Base
from .storage import Run

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.db=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
        Base.metadata.create_all(self.db)
        self.session=sessionmaker(self.db,expire_on_commit=False)
        self.p=patch.object(analysis,'Session',self.session);self.p.start()
        self.r={'id':9999,'origen':'vivo','vivo':{'hora':3}}
        rows=[]
        for fish in range(3):
            for hour in range(2 if fish==0 else 4):
                rows.append({'pez_id':fish,'pecera_id':fish,'especie_nombre':f'Especie {fish}','hora_sim':hour,
                    'hora_evento':2 if fish==0 else None,'riesgo_1h':.8 if fish!=1 else .1,
                    'alerta_1h':fish!=1,'observado_1h':1,'ph':7,'temperatura':25,'oxigeno':6,'nh3_mg_n_l':.001})
        self.d=pd.DataFrame(rows)
    def tearDown(self):self.p.stop();self.db.dispose()

    def test_future_outcomes_are_not_used(self):
        x=analysis.tracking_data(self.r,self.d,1,1)
        first=x[x.pez_id.eq(0)&x.hora_sim.eq(0)].iloc[0]
        pending=x[x.pez_id.eq(0)&x.hora_sim.eq(1)].iloc[0]
        self.assertEqual(first.resultado,'falsa_alarma')
        self.assertEqual(pending.resultado,'pendiente')
        self.assertTrue(x.hora_evento.isna().all())
        self.assertEqual(x.hora_sim.max(),1)

    def test_dead_fish_counted_once(self):
        st=analysis.statistics_data(self.r,self.d,3)
        self.assertEqual(st['iniciales'],3);self.assertEqual(st['muertos'],1);self.assertEqual(st['vivos'],2)
        self.assertAlmostEqual(st['mortalidad'],1/3)
        self.assertEqual(sum(g['muertos'] for g in st['grupos'] if g['dimension']=='especie_nombre'),1)
        self.assertEqual(analysis.statistics_data(self.r,self.d,1)['muertos'],0)

    def test_completed_prediction_is_correct(self):
        x=analysis.tracking_data(self.r,self.d,2,1)
        row=x[x.pez_id.eq(0)&x.hora_sim.eq(1)].iloc[0]
        self.assertEqual(row.resultado,'aviso_correcto')
        self.assertEqual(row.hora_evento,2)

    def test_attention_is_idempotent_and_not_retroactive(self):
        with patch.object(analysis.service,'get_run',return_value=(self.r,self.d)):
            a=analysis.attend(9999,0,1,1,3,'Revisión de prueba')
            b=analysis.attend(9999,0,1,1,3,'Segundo clic')
        self.assertEqual(a,b);self.assertEqual(a['demora_h'],2)
        with self.session() as s:self.assertEqual(s.query(analysis.Attention).count(),1)
        past=analysis.tracking_data(self.r,self.d,2,1)
        self.assertFalse(past.atendida.any())
        present=analysis.tracking_data(self.r,self.d,3,1)
        self.assertEqual(present.atendida.sum(),1)

    def test_no_attention_for_nonexistent_or_negative_alert(self):
        with patch.object(analysis.service,'get_run',return_value=(self.r,self.d)):
            with self.assertRaises(ValueError):analysis.attend(9999,1,0,1,3,'')
            with self.assertRaises(ValueError):analysis.attend(9999,0,4,1,3,'')

    def test_no_fake_percent_when_denominator_missing(self):
        self.assertIsNone(analysis.safe_ratio(0,0))
        with patch.object(analysis.service,'get_run',return_value=(self.r,self.d)):
            result=analysis.tracking(9999,0,1)
        self.assertEqual(result['resumen']['evaluadas'],0)
        self.assertIsNone(result['resumen']['precision'])

    def test_scenario_rates_use_counts_and_exclude_duplicates_and_partial(self):
        with self.session() as s:
            for rid,seed,origin in [(1,101,'nueva'),(2,102,'nueva'),(3,101,'nueva'),(4,104,'vivo')]:
                s.add(Run(id=rid,nombre=f'Prueba {rid}',semilla=seed,escenario='estable',origen=origin,estado='lista'))
            s.commit()
        def get_run(rid):
            r={'id':rid,'origen':'vivo' if rid==4 else 'nueva'}
            if rid==4:r['vivo']={'hora':3}
            d=self.d.copy();d.attrs['rid']=rid
            return r,d
        def evaluate(d,h):return {'tp':1,'fp':1 if d.attrs['rid']==1 else 9,'fn':0,'tn':2}
        with patch.object(analysis.service,'get_run',side_effect=get_run),patch.object(analysis.service,'evaluate',side_effect=evaluate):
            result=analysis.scenarios(1)
        self.assertEqual(result['repetidas_excluidas'],1)
        self.assertEqual(result['excluidas_en_curso'],1)
        self.assertEqual(result['grupos'][0]['corridas'],2)
        self.assertAlmostEqual(result['grupos'][0]['precision'],2/12)

if __name__=='__main__':unittest.main()
