"""Regresiones de reloj, reinicio, ramas, sensores y causalidad del motor v2."""
import pickle
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from . import live, service, analysis
from .main import app
from .storage import Base
from .paths import SEED
from simulacion.motor.realistic_engine import RealisticEngine, DEFAULT_CONFIG
from simulacion.motor.features import prepare


class PhysicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.fichas=pd.read_csv(SEED/'fichas_origen.csv')
    def engine(self,**config):return RealisticEngine(self.fichas,800,183114001,'combinado',config)

    def test_initial_conditions_and_unique_configurable_ids(self):
        config=deepcopy(DEFAULT_CONFIG);config['peceras'][0]['peces']=80
        engine=self.engine(**config);rows=engine.step()
        self.assertEqual(len(rows),112);self.assertEqual(len({r['pez_id'] for r in rows}),112)
        self.assertTrue(all(r['temp_desvio']==0 and r['ph_desvio']==0 for r in rows))
        self.assertEqual(engine.events,[])

    def test_reproducibility_checkpoint_and_no_future(self):
        engine=self.engine(sensores='intermitente')
        for _ in range(31):engine.step()
        restored=pickle.loads(pickle.dumps(engine))
        for _ in range(20):
            pd.testing.assert_frame_equal(pd.DataFrame(engine.step()),pd.DataFrame(restored.step()))
            self.assertEqual(engine.events,restored.events)
            self.assertTrue(all(e['hora_evento']<=engine.hour for e in engine.events))

    def test_actions_change_water_without_changing_other_tank_randomness(self):
        base=self.engine(intensidad='severo',inicio=8,duracion=60)
        for _ in range(25):base.step()
        altered=pickle.loads(pickle.dumps(base))
        altered.schedule(0,'aireacion',0,24);altered.schedule(0,'filtro',0,24);altered.schedule(0,'recambio',25,1)
        old=base.tanks[0].tan
        self.assertEqual(altered.tanks[0].tan,old)
        for _ in range(8):
            a,b=pd.DataFrame(base.step()),pd.DataFrame(altered.step())
            pd.testing.assert_frame_equal(a[a.pecera_id.ne(0)].reset_index(drop=True),b[b.pecera_id.ne(0)].reset_index(drop=True))
        self.assertGreater(altered.tanks[0].ox,base.tanks[0].ox)
        self.assertLess(altered.tanks[0].tan,base.tanks[0].tan)

    def test_missing_measurement_is_not_zero_or_future_imputation(self):
        engine=self.engine();raw=[]
        for _ in range(7):raw.extend(engine.step())
        df=pd.DataFrame(raw)
        missing=df.pecera_id.eq(0)&df.hora_sim.eq(3)
        df.loc[missing,'sensor_disponible']=False
        columns=['ph','temperatura','oxigeno','tan_mg_n_l','nh3_mg_n_l','ph_desvio','temp_desvio','ox_deficit']
        df.loc[missing,columns]=np.nan
        result,features,names=prepare(df)
        past,past_features,_=prepare(df[df.hora_sim.le(4)])
        self.assertFalse(result.loc[result.pecera_id.eq(0)&result.hora_sim.eq(3),'prediccion_disponible'].any())
        self.assertTrue(result.loc[result.pecera_id.eq(0)&result.hora_sim.eq(4),'calidad_prediccion'].eq('historia_estimada').all())
        pd.testing.assert_frame_equal(features[result.hora_sim.le(4)].reset_index(drop=True),past_features)
        self.assertFalse({'hora_evento','pez_id','pecera_id','escenario','sensor_disponible'}&set(names))

    def test_balances_and_gradual_temperature(self):
        engine=self.engine(intensidad='severo',inicio=6,duracion=65)
        engine.step();previous=[t.temp for t in engine.tanks]
        for _ in range(96):
            engine.step()
            for i,tank in enumerate(engine.tanks):
                self.assertLessEqual(abs(tank.temp-previous[i]),.60000001)
                self.assertGreaterEqual(tank.tan,0);self.assertGreaterEqual(tank.ox,0)
                previous[i]=tank.temp
        with self.assertRaises(ValueError):engine.step()


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
        Base.metadata.create_all(self.db)
        session=sessionmaker(self.db,expire_on_commit=False)
        self.patches=[patch.object(m,'Session',session) for m in [live,service,analysis]]
        self.patches += [patch.object(live,'DATA',Path(self.tmp.name)),patch.object(live,'_entries',{})]
        for p in self.patches:p.start()
        self.client=TestClient(app)
    def tearDown(self):
        live.shutdown()
        for p in reversed(self.patches):p.stop()
        self.db.dispose();self.tmp.cleanup()
    def create(self):return live.create('combinado',183114111,.05)
    def await_hour(self,rid,minimum):
        limit=time.monotonic()+15
        while time.monotonic()<limit:
            _,state,_=live.read(rid)
            if state['hora']>=minimum:return state
            time.sleep(.03)
        self.fail('El reloj no avanzó después de reanudar')

    def test_pause_resume_repeated_and_switch_runs(self):
        a,b=self.create(),self.create()
        for _ in range(3):
            _,state,_=live.read(a['id']);target=state['hora']+1
            live.control(a['id'],'reanudar');self.await_hour(a['id'],target)
            paused=live.control(a['id'],'pausar')
            time.sleep(.12);self.assertEqual(live.read(a['id'])[1]['hora'],paused['hora'])
        live.control(a['id'],'reanudar');live.control(b['id'],'reanudar')
        self.assertEqual(live.read(a['id'])[1]['estado'],'pausada')
        self.await_hour(b['id'],1)

    def test_restart_finished_and_paused_preserves_original(self):
        row=self.create();rid=row['id'];live.finish(rid)
        before,state,_=live.read(rid);self.assertEqual(state['estado'],'terminada')
        denied=self.client.post(f'/api/vivo/{rid}/control',json={'accion':'reanudar'})
        self.assertEqual(denied.status_code,409)
        response=self.client.post(f'/api/corridas/{rid}/reiniciar')
        self.assertEqual(response.status_code,201,response.text)
        new=response.json();self.assertNotEqual(rid,new['id']);self.assertEqual(new['vivo']['hora'],0)
        self.assertEqual(new['vivo']['estado'],'pausada')
        pd.testing.assert_frame_equal(before,live.read(rid)[0])
        live.control(new['id'],'reanudar');self.await_hour(new['id'],1)

    def test_branch_history_and_predictions_frozen(self):
        row=self.create();rid=row['id'];live.finish(rid)
        source,_,_=live.read(rid)
        branch=live.branch(rid,12);d,state,_=live.read(branch['id'])
        self.assertEqual(state['hora'],12)
        self.assertTrue(d.loc[d.hora_sim.gt(0),'observado_12h'].isna().all())
        self.assertTrue(d.hora_evento.dropna().le(12).all())
        for h in [1,6,12]:
            np.testing.assert_array_equal(d[f'riesgo_{h}h'],source.loc[source.hora_sim.le(12),f'riesgo_{h}h'])
        live.finish(branch['id'])
        self.assertEqual(live.paired(rid,branch['id'])['diferencia_muertes'],0)

    def test_intervention_stale_hour_rejected_and_logs_persist(self):
        rid=self.create()['id']
        with self.assertRaises(ValueError):live.intervene(rid,0,'aireacion',0,12,1)
        event=live.intervene(rid,0,'recambio',20,1,0)
        self.assertEqual(event['efectiva_hora'],1)
        with self.assertRaises(ValueError):live.intervene(rid,0,'recambio',20,1,0)
        live._entries.pop(rid)
        self.assertEqual(live.details(rid,0)['acciones'][0],event)

    def test_failed_tick_rolls_back_and_retry_restarts_worker(self):
        rid=self.create()['id'];original=live.advance
        def fail_after_tick(entry):
            original(entry)
            raise RuntimeError('Fallo de prueba después del avance')
        with patch.object(live,'advance',side_effect=fail_after_tick), self.assertLogs(level='ERROR'):
            live.control(rid,'reanudar')
            limit=time.monotonic()+15
            while live.read(rid)[1]['estado']!='error' and time.monotonic()<limit:time.sleep(.02)
            frame,state,_=live.read(rid)
            self.assertEqual(state['estado'],'error');self.assertEqual(state['hora'],0)
            self.assertEqual(set(frame.hora_sim),{0})
        live.control(rid,'reanudar');self.await_hour(rid,1)

    def test_history_after_extinction_returns_water_at_requested_hour(self):
        rid=self.create()['id'];e=live.entry_for(rid)
        with e.lock:
            for tank in e.payload['engine'].tanks:tank.alive[:]=False
            live.advance(e);live.advance(e)
        r,d=service.get_run(rid);s=service.snapshot_data(r,d,1,12)
        self.assertEqual(s['peces'],0)
        self.assertTrue(all(t['hora_lectura']==1 for t in s['peceras']))
        self.assertNotIn('agua_actual',s['corrida'])

    def test_missing_sensor_api_and_excel_keep_unknown_values(self):
        from io import BytesIO
        from openpyxl import load_workbook
        from .export import excel
        rid=self.create()['id'];e=live.entry_for(rid)
        with e.lock:
            e.payload['engine'].config['sensores']='intermitente'
            e.payload['engine'].tanks[0].missing_until=2
            live.advance(e)
        response=self.client.get(f'/api/vivo/{rid}/vista?hora=1')
        self.assertEqual(response.status_code,200,response.text)
        snap=response.json()['resumen']
        self.assertEqual(snap['sin_prediccion'],16)
        self.assertIsNone(snap['peceras'][0]['ph']);self.assertIsNone(snap['peceras'][0]['esperadas'])
        track=analysis.tracking(rid,1,1,False)
        self.assertEqual(track['resumen']['sin_prediccion'],16)
        wb=load_workbook(BytesIO(excel(rid,1,12)),read_only=True)
        self.assertTrue({'Configuracion v2','Bitacora v2','Intervenciones v2','Sensores v2'}<=set(wb.sheetnames))
        self.assertEqual(wb['Sensores v2'].max_row,7)
        wb.close()


if __name__=='__main__':unittest.main()
