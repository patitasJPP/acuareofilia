from .paths import DATA, SEED, MODELS, EXPORTS
"""El motor no conoce futuros; RNG y pronósticos se preservan al reanudar."""
import pickle,time,threading,unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from .live_engine import LiveEngine
from . import live, service
from .storage import ROOT

class LiveTests(unittest.TestCase):
    def engine(self):return LiveEngine(pd.read_csv(SEED/'fichas_origen.csv'),9000,100000901,'combinado')
    def entry(self):return live.Entry({'rid':0,'engine':self.engine(),'raw':[],'scored':pd.DataFrame(),'estado':'activa','segundos':.05})

    def test_transition_occurs_only_on_next_step(self):
        e=self.engine();rows=e.step()
        self.assertEqual(e.hour,0);self.assertEqual(len(rows),48);self.assertEqual(e.events,[])
        self.assertEqual({r['hora_sim'] for r in rows},{0})
        for _ in range(24):
            rows=e.step()
            self.assertTrue(all(ev['hora_evento']<=e.hour for ev in e.events))
            self.assertTrue(all(r['hora_sim']==e.hour for r in rows))
            dead={ev['pez_id'] for ev in e.events}
            self.assertFalse(dead&{r['pez_id'] for r in rows})

    def test_checkpoint_preserves_random_state(self):
        a=self.engine()
        for _ in range(19):a.step()
        b=pickle.loads(pickle.dumps(a))
        for _ in range(30):
            pd.testing.assert_frame_equal(pd.DataFrame(a.step()),pd.DataFrame(b.step()))
            self.assertEqual(a.events,b.events)

    def test_predictions_frozen_and_labels_pending(self):
        e=self.entry()
        with patch.object(live,'save'):
            live.advance(e)
            first=e.payload['scored'].copy()
            self.assertTrue(first.observado_12h.isna().all())
            self.assertNotIn('muere_siguiente_hora',first)
            for _ in range(12):live.advance(e)
        d=e.payload['scored']
        old=d[d.hora_sim.eq(0)]
        for h in [1,6,12]:
            np.testing.assert_array_equal(old[f'riesgo_{h}h'],first[f'riesgo_{h}h'])
            self.assertTrue(d.loc[d.hora_sim+h>12,f'observado_{h}h'].isna().all())
        self.assertTrue(old.observado_12h.notna().all())
        self.assertEqual(d.hora_sim.max(),12)
        r={'vivo':{'hora':12},'agua_actual':e.payload['engine'].water}
        with self.assertRaises(ValueError):service.snapshot_data(r,d,13,12)

    def test_clock_runs_without_browser_and_stops_when_paused(self):
        e=self.entry();ticks=[]
        def tick(entry):ticks.append(time.monotonic())
        with patch.object(live,'advance',side_effect=tick):
            live.start(e)
            deadline=time.monotonic()+1
            while len(ticks)<2 and time.monotonic()<deadline:time.sleep(.01)
            with e.lock:e.payload['estado']='pausada';count=len(ticks)
            e.wake.set();e.thread.join(1)
            self.assertGreaterEqual(count,2)
            time.sleep(.1);self.assertEqual(count,len(ticks));self.assertFalse(e.thread.is_alive())

    def test_finish_at_96_and_no_future_events(self):
        e=self.engine()
        for _ in range(97):e.step()
        self.assertEqual(e.hour,96)
        self.assertTrue(all(ev['hora_evento']<=96 for ev in e.events))
        with self.assertRaises(ValueError):e.step()

    def test_empty_tank_snapshot_has_no_future_or_fake_fish(self):
        e=self.entry()
        with patch.object(live,'save'):live.advance(e)
        d=e.payload['scored'].iloc[:0].copy()
        r={'vivo':{'hora':1},'agua_actual':e.payload['engine'].water}
        snap=service.snapshot_data(r,d,1,12)
        self.assertEqual(snap['peces'],0);self.assertEqual(snap['detalle'],[])
        self.assertEqual(snap['esperadas'],0)
        self.assertEqual(len(snap['peceras']),3)

if __name__=='__main__':unittest.main()
