from .paths import DATA, SEED, MODELS, EXPORTS
"""Pruebas de contratos, causalidad temporal, reproducibilidad y exportación."""
import unittest
from io import BytesIO
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from .main import app
from . import service
from .storage import ROOT

class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx=TestClient(app);cls.client=cls.ctx.__enter__()
        cls.runs=cls.client.get('/api/corridas').json()
        cls.rid=next(r['id'] for r in cls.runs if r['origen']=='test_v3' and r['escenario']=='combinado')
    @classmethod
    def tearDownClass(cls):cls.ctx.__exit__(None,None,None)

    def test_snapshot_aggregation(self):
        s=self.client.get(f'/api/resumen/{self.rid}?hora=48&horizonte=12').json()
        self.assertEqual(sum(t['peces'] for t in s['peceras']),s['peces'])
        self.assertAlmostEqual(sum(f['riesgo_12h'] for f in s['detalle']),s['esperadas'],places=7)
        self.assertEqual(sum(t['alertas'] for t in s['peceras']),s['alertas'])
        self.assertEqual(len(s['detalle']),len({f['pez_id'] for f in s['detalle']}))
        self.assertTrue(all(0<=f['riesgo_12h']<=1 for f in s['detalle']))

    def test_limits_and_missing(self):
        self.assertEqual(self.client.get(f'/api/resumen/{self.rid}?hora=85').status_code,422)
        self.assertEqual(self.client.get(f'/api/resumen/{self.rid}?horizonte=24').status_code,422)
        self.assertEqual(self.client.get('/api/resumen/999999').status_code,404)
        self.assertEqual(self.client.post('/api/simulaciones',json={'semilla':1}).status_code,422)

    def test_model_protocol(self):
        forbidden={'target','hora_evento','corrida_id','pez_id','pecera_id','semilla','escenario','particion'}
        for b in service.models().values():self.assertFalse(forbidden&set(b['features']))
        _,d=service.get_run(self.rid)
        for h in service.HORIZONS:
            self.assertTrue(d.loc[d.hora_sim+h>96,f'observado_{h}h'].isna().all())

    def test_history_uses_no_future(self):
        fichas=pd.read_csv(SEED/'fichas_origen.csv')
        f,_,_,_=service.simular_corrida(fichas,888,100000401,'combinado','nueva',horas=96)
        d=pd.DataFrame(f)
        a,features=service.historia(d)
        b,_=service.historia(d[d.hora_sim.le(24)])
        keys=['corrida_id','pez_id','hora_sim']
        a=a[a.hora_sim.le(24)].sort_values(keys).reset_index(drop=True)
        b=b.sort_values(keys).reset_index(drop=True)
        pd.testing.assert_frame_equal(a[features],b[features])

    def test_new_seed_is_reproducible(self):
        fichas=pd.read_csv(SEED/'fichas_origen.csv')
        a=service.simular_corrida(fichas,999,100000501,'hipoxia','nueva',horas=96)
        b=service.simular_corrida(fichas,999,100000501,'hipoxia','nueva',horas=96)
        pd.testing.assert_frame_equal(pd.DataFrame(a[0]),pd.DataFrame(b[0]))
        d=service.score(pd.DataFrame(a[0]),pd.DataFrame(a[1]))
        self.assertEqual(len(d),len(a[0]))
        self.assertTrue(d.riesgo_12h.between(0,1).all())

    def test_excel_contains_all_rows(self):
        r=self.client.get(f'/api/exportar/{self.rid}?hora=48&horizonte=12')
        self.assertEqual(r.status_code,200)
        wb=load_workbook(BytesIO(r.content),read_only=True,data_only=True)
        self.assertIn('Historial completo',wb.sheetnames)
        for name in ['Mortalidad al corte','Seguimiento al corte','Sugerencias de revision']:
            self.assertIn(name,wb.sheetnames)
        _,d=service.get_run(self.rid)
        self.assertEqual(wb['Historial completo'].max_row,len(d)+1)
        values=list(wb['Peces al corte'].values)
        col=values[0].index('riesgo_12h')
        self.assertTrue(all(isinstance(row[col],float) and 0<=row[col]<=1 for row in values[1:]))
        track=list(wb['Seguimiento al corte'].values)
        hourcol=track[0].index('hora_sim')
        self.assertTrue(all(row[hourcol]<=48 for row in track[1:]))
        wb.close()

if __name__=='__main__':unittest.main()
