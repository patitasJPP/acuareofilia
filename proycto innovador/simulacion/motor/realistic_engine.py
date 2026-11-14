"""Motor v2 de agua dulce, reproducible y con intervenciones auditables.

Las relaciones físicas son simplificadas; los coeficientes y la mortalidad
son supuestos de un experimento universitario, no parámetros calibrados.
El motor v1 permanece intacto para poder abrir sus checkpoints.
"""
from copy import deepcopy
import numpy as np
import pandas as pd
from .live_engine import parametros_corrida, riesgo_horario, nh3_desde_tan

VERSION = 'incremental_v2'
LEVELS = {'leve': .35, 'moderado': .8, 'severo': 1.5}
DEFAULT_CONFIG = {
    'intensidad': 'moderado', 'inicio': 24, 'duracion': 18,
    'sensores': 'normal', 'peceras': [
        {'especie': 'Tilapia', 'peces': 16, 'volumen_l': 1500},
        {'especie': 'Carpa', 'peces': 16, 'volumen_l': 1800},
        {'especie': 'Gamitana', 'peces': 16, 'volumen_l': 1800}],
}


def configuration(value=None, fichas=None):
    config = deepcopy(DEFAULT_CONFIG)
    config.update(deepcopy(value or {}))
    if config['intensidad'] not in LEVELS or config['sensores'] not in ['normal', 'intermitente']:
        raise ValueError('Intensidad o perfil de sensores desconocido')
    if not 1 <= config['inicio'] <= 84 or not 1 <= config['duracion'] <= 72 or config['inicio'] + config['duracion'] > 96:
        raise ValueError('El incidente debe empezar y terminar dentro de las 96 horas')
    if len(config['peceras']) != 3:
        raise ValueError('Configura exactamente tres peceras')
    for tank in config['peceras']:
        if not 1 <= tank['peces'] <= 80 or not 100 <= tank['volumen_l'] <= 10000:
            raise ValueError('Usa de 1 a 80 peces y de 100 a 10000 litros por pecera')
        if fichas is not None and tank['especie'] not in set(fichas.especie_nombre):
            raise ValueError('La especie no tiene una ficha en este proyecto')
    return config


def saturation(temp):
    """Aproximación de saturación O2, mg/L, agua dulce a nivel del mar."""
    return float(14.652 - .41022*temp + .007991*temp**2 - .000077774*temp**3)


class RealisticTank:
    def __init__(self, fichas, tid, seed, params, scenario, config):
        streams = seed.spawn(4)
        init = np.random.default_rng(streams[0])
        self.water_rng = np.random.default_rng(streams[1])
        self.sensor_rng = np.random.default_rng(streams[2])
        self.death_rng = np.random.default_rng(streams[3])
        self.tid, self.params, self.scenario = tid, params, scenario
        self.config = config
        cfg = config['peceras'][tid]
        self.spec = fichas[fichas.especie_nombre.eq(cfg['especie'])].iloc[0]
        self.count = int(cfg['peces'])
        self.weights = self.spec.peso_gramos * init.lognormal(0, .12, self.count)
        self.vulnerability = init.lognormal(-.08, .4, self.count)
        self.alive = np.ones(self.count, dtype=bool)
        self.load = np.zeros(self.count)
        self.volume = float(cfg['volumen_l'])
        self.basetemp = float((self.spec.temp_min + self.spec.temp_max)/2 + init.uniform(-.4, .4))
        self.baseph = float((self.spec.ph_min + self.spec.ph_max)/2 + init.uniform(-.04, .04))
        self.temp, self.ph = self.basetemp, self.baseph
        self.ox, self.tan = saturation(self.temp)*.94, float(init.uniform(.05, .12))
        self.filter_efficiency = 1.
        self.air, self.filtr = True, True
        self.active = {}
        self.history, self.previous = [], None
        self.stress = 0.
        self.sensor_bias = np.zeros(4)
        self.missing_until = -1

    def incident(self, hour):
        start, duration = self.config['inicio'], self.config['duracion']
        if self.scenario == 'estable' or not start <= hour < start + duration:
            return 0.
        # Arranque gradual durante tres horas; la recuperación viene del balance.
        return LEVELS[self.config['intensidad']] * min(1., (hour-start+1)/3)

    def action(self, event, hour):
        kind = event['accion']
        if kind == 'recambio':
            fraction = event['valor']/100
            self.tan *= 1-fraction  # Agua de entrada con TAN=0, mismo volumen.
            self.ox = (1-fraction)*self.ox + fraction*saturation(self.basetemp)*.95
            self.temp += np.clip(fraction*(self.basetemp-self.temp), -.6, .6)
            # Relajación de pH: aproximación; no es una ecuación de alcalinidad.
            self.ph += np.clip(fraction*(self.baseph-self.ph), -.12, .12)
        else:
            self.active[kind] = (hour+event['duracion'], event['valor'])

    def evolve(self, hour):
        r, p = self.water_rng, self.params
        # Siempre las mismas extracciones por hora, aunque cambien las muertes.
        noise = r.normal(0, [ .06, .008, .015 ])
        respiration = r.uniform(150, 250)
        self.active = {k:v for k,v in self.active.items() if v[0] > hour}
        severity = self.incident(hour)
        heat = severity if self.scenario in ['termico', 'combinado'] else 0.
        ammonia = severity if self.scenario in ['amonio', 'combinado'] else 0.
        hypoxia = severity if self.scenario in ['hipoxia', 'combinado'] else 0.
        ph_shift = severity if self.scenario in ['ph', 'combinado'] else 0.
        self.air = not bool(hypoxia) or 'aireacion' in self.active
        self.filtr = not bool(ammonia) or 'filtro' in self.active
        biomass = float(self.weights[self.alive].sum()/1000)
        day = np.sin(2*np.pi*(hour-6)/24)
        target = self.basetemp + .6*day + 6*heat
        if 'temperatura' in self.active:
            target = self.active['temperatura'][1]
        self.temp = float(np.clip(self.temp+np.clip(.14*(target-self.temp)+noise[0], -.6, .6), 4, 40))
        target_ph = self.baseph + .06*day + .7*ph_shift
        self.ph = float(np.clip(self.ph+np.clip(.12*(target_ph-self.ph)+noise[1], -.12, .12), 4.5, 10))
        # Balance mg N/L: excreción, residuo de alimento, eliminación del filtro.
        feed = 1.6 if hour % 24 in [8, 17] else 1.
        nitrogen = biomass*p['excrecion_mg_n_kg_h']*feed/self.volume + .055*ammonia
        self.filter_efficiency += (.12 if self.filtr else .3)*((1. if self.filtr else .05)-self.filter_efficiency)
        removal = (self.tan+nitrogen)*p['filtracion_fraccion_h']*self.filter_efficiency*min(1., self.ox/4)
        self.tan = max(0., self.tan+nitrogen-removal)
        # Oxígeno: intercambio gaseoso - respiración - nitrificación - residuos.
        demand = biomass*respiration*1.06**(self.temp-self.basetemp)/self.volume
        exchange = (.4 if self.air else .025)*(saturation(self.temp)-self.ox)
        self.ox = float(np.clip(self.ox+exchange-demand-4.57*removal-.14*hypoxia+.025*day+noise[2], .05, saturation(self.temp)))

    def mortality(self, hour, rid):
        p, s = self.params, self.spec
        phdev = max(0., s.ph_min-self.ph, self.ph-s.ph_max)
        tempdev = max(0., s.temp_min-self.temp, self.temp-s.temp_max)
        oxygen = max(0., s.oxigeno_min-self.ox)
        nh3 = float(nh3_desde_tan(self.tan, self.ph, self.temp))
        stress = min(phdev/2+tempdev/4+oxygen/2+max(0., nh3/p['escala_nh3_n']-1), 15)
        shared, shock_size = self.death_rng.random(), self.death_rng.uniform(.5, 2)
        uniforms = self.death_rng.random(self.count)  # Incluye los peces ya muertos.
        hazard = riesgo_horario((stress+self.stress)/2, self.load,
                                self.vulnerability*(shock_size if shared < .02 else 1.), p)
        dead = self.alive & (uniforms < hazard)
        self.load[self.alive] = np.minimum(30, self.load[self.alive]*p['recuperacion']+stress*.12)
        self.alive[dead] = False
        self.stress = stress
        return [{'corrida_id':rid, 'pez_id':self.tid*100+int(i), 'pecera_id':self.tid,
                 'hora_evento':hour, 'evento':'muerte'} for i in np.flatnonzero(dead)]

    def observe(self, hour, rid):
        r, s = self.sensor_rng, self.spec
        # El ruido, la deriva y los cortes son independientes de las muertes.
        noise = r.normal(0, [.025, .12, .08, .015])
        drift = r.normal(0, [.001, .008, .005, .001])
        failure, duration = r.random(), int(r.integers(1, 4))
        intermittent = self.config['sensores'] == 'intermitente'
        if intermittent:
            self.sensor_bias = np.clip(self.sensor_bias+drift, [-.08,-.5,-.3,-.05], [.08,.5,.3,.05])
            if hour > 0 and failure < .025:
                self.missing_until = max(self.missing_until, hour+duration-1)
        measured = np.array([self.ph, self.temp, self.ox, self.tan])+noise+self.sensor_bias
        measured[2:] = np.maximum(measured[2:], 0.)
        available = not (intermittent and hour <= self.missing_until)
        if not available:
            measured[:] = np.nan
        nh3 = float(nh3_desde_tan(measured[3], measured[0], measured[1]))
        self.history.append([nh3, measured[2]])
        changes = np.zeros(4) if self.previous is None else measured-self.previous
        self.previous = measured.copy()
        recent = np.array(self.history[-6:])
        # Los faltantes se conservan, nunca se publican como ceros.
        def mean(x): return float(np.mean(x)) if np.isfinite(x).all() else np.nan
        rows = []
        for i in np.flatnonzero(self.alive):
            rows.append({'corrida_id':rid, 'pez_id':self.tid*100+int(i), 'pecera_id':self.tid,
                'hora_sim':hour, 'escenario':self.scenario, 'especie_nombre':s.especie_nombre,
                'peso_gramos':float(self.weights[i]), 'ph':measured[0], 'temperatura':measured[1],
                'oxigeno':measured[2], 'tan_mg_n_l':measured[3], 'nh3_mg_n_l':nh3,
                'densidad_kg_m3':float(self.weights[self.alive].sum()/self.volume), 'volumen_l':self.volume,
                'ph_desvio':max(0., s.ph_min-measured[0], measured[0]-s.ph_max) if available else np.nan,
                'temp_desvio':max(0., s.temp_min-measured[1], measured[1]-s.temp_max) if available else np.nan,
                'ox_deficit':max(0., s.oxigeno_min-measured[2]) if available else np.nan,
                'exposicion_nh3_6h':mean(recent[:,0]), 'exposicion_ox_6h':mean(np.maximum(s.oxigeno_min-recent[:,1],0)),
                'cambio_ph_1h':changes[0], 'cambio_temp_1h':changes[1], 'cambio_ox_1h':changes[2], 'cambio_tan_1h':changes[3],
                'aireacion_activa':int(self.air), 'filtro_activo':int(self.filtr), 'sensor_disponible':available,
                'version_motor':VERSION})
        water = {'id':self.tid, 'hora_lectura':hour, 'vivos':int(self.alive.sum()),
                 'ph':float(measured[0]), 'temperatura':float(measured[1]), 'oxigeno':float(measured[2]),
                 'tan_mg_n_l':float(measured[3]), 'nh3':nh3, 'sensor_disponible':available,
                 'aireacion_activa':self.air, 'filtro_activo':self.filtr}
        return rows, water


class RealisticEngine:
    version = VERSION

    def __init__(self, fichas, rid, seed, scenario, config=None):
        self.config = configuration(config, fichas)
        self.rid, self.seed, self.scenario = rid, seed, scenario
        self.hour = -1
        self.events, self.water, self.water_history, self.actions, self.log = [], [], [], [], []
        params = parametros_corrida(seed+100000)
        streams = np.random.SeedSequence(seed).spawn(3)
        self.tanks = [RealisticTank(fichas, i, streams[i], params, scenario, self.config) for i in range(3)]

    def schedule(self, tid, kind, value=0, duration=12):
        if not 0 <= self.hour < 96: raise ValueError('La corrida no admite más acciones')
        if tid not in [0,1,2]: raise ValueError('Pecera desconocida')
        if kind not in ['aireacion','filtro','recambio','temperatura']: raise ValueError('Acción desconocida')
        if not 1 <= duration <= 48: raise ValueError('Duración fuera de rango')
        if kind == 'recambio' and not 5 <= value <= 30: raise ValueError('El recambio debe ser de 5 a 30 %')
        if kind == 'temperatura':
            s = self.tanks[tid].spec
            if not s.temp_min <= value <= s.temp_max: raise ValueError(f'Usa una temperatura entre {s.temp_min} y {s.temp_max} °C para esta especie')
        if any(a['solicitada_hora']==self.hour and a['pecera_id']==tid and a['accion']==kind for a in self.actions):
            raise ValueError('Esa acción ya está programada para esta hora y pecera')
        event = {'id':len(self.actions)+1, 'pecera_id':tid, 'accion':kind, 'valor':float(value),
                 'duracion':duration, 'solicitada_hora':self.hour, 'efectiva_hora':self.hour+1}
        self.actions.append(event)
        self.log.append({'hora':self.hour,'pecera_id':tid,'tipo':'accion_programada',
                         'detalle':f'{kind}; valor {value}; efectiva en h {self.hour+1}; duración {duration} h'})
        return event

    def step(self):
        if self.hour >= 96: raise ValueError('La simulación ya terminó')
        hour = self.hour+1
        rows, water = [], []
        if self.scenario != 'estable' and hour in [self.config['inicio'], self.config['inicio']+self.config['duracion']]:
            self.log.append({'hora':hour,'pecera_id':None,'tipo':'incidente',
                             'detalle':'Inicio del incidente' if hour == self.config['inicio'] else 'Fin del incidente; recuperación progresiva'})
        for tank in self.tanks:
            if hour:
                for action in self.actions:
                    if action['pecera_id'] == tank.tid and action['efectiva_hora'] == hour:
                        tank.action(action, hour)
                        self.log.append({'hora':hour,'pecera_id':tank.tid,'tipo':'accion_aplicada','detalle':action['accion']})
                tank.evolve(hour)
                deaths = tank.mortality(hour, self.rid)
                self.events.extend(deaths)
                if deaths:
                    self.log.append({'hora':hour,'pecera_id':tank.tid,'tipo':'mortalidad','detalle':f'{len(deaths)} muertes observadas'})
            current, readings = tank.observe(hour, self.rid)
            rows.extend(current); water.append(readings)
            if not readings['sensor_disponible']:
                self.log.append({'hora':hour,'pecera_id':tank.tid,'tipo':'sensor','detalle':'Lectura ausente; sin predicción nueva'})
        self.hour, self.water = hour, water
        self.water_history.extend(deepcopy(water))
        return rows
