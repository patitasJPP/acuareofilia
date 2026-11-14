"""Motor incremental v1: observa t; la transición t→t+1 solo ocurre al avanzar.

Conserva las ecuaciones del simulador de entrenamiento. Cada pecera tiene su
propio flujo aleatorio, necesario para avanzarlas a la vez y reanudar exactamente.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ml'))
from experimento_mortalidad import parametros_corrida, riesgo_horario, nh3_desde_tan

class Tank:
    def __init__(self,fichas,tid,seed,params,scenario,fish=16):
        self.rng=np.random.default_rng(seed);r=self.rng
        self.tid=tid;self.params=params;self.scenario=scenario
        self.species=fichas.iloc[r.integers(0,len(fichas),size=fish)].reset_index(drop=True)
        self.weights=self.species.peso_gramos.to_numpy()*r.lognormal(0,.12,fish)
        self.vulnerability=r.lognormal(-.08,.4,fish)
        self.alive=np.ones(fish,dtype=bool);self.load=np.zeros(fish)
        self.volume=float(r.uniform(600,7000));self.baseph=float(r.uniform(6.7,8))
        self.basetemp=float(r.uniform(22,28));self.ph=self.baseph;self.temp=self.basetemp
        self.ox=float(r.uniform(6,8));self.tan=float(r.uniform(.05,.4))
        self.start=int(r.integers(12,30));self.end=int(r.integers(55,78))
        self.severity=float(r.uniform(.7,1.8));self.history=[];self.previous=None;self.stress=None

    def transition(self,hour,rid):
        r=self.rng;p=self.params;events=[]
        shock=r.uniform(.5,2) if r.random()<.02 else 1.
        for i in np.flatnonzero(self.alive):
            probability=float(riesgo_horario(self.stress[i],self.load[i],self.vulnerability[i]*shock,p))
            died=bool(r.random()<probability)
            self.load[i]=min(30,self.load[i]*p['recuperacion']+self.stress[i]*.12)
            if died:
                self.alive[i]=False
                events.append({'corrida_id':rid,'pez_id':self.tid*16+int(i),'pecera_id':self.tid,'hora_evento':hour,'evento':'muerte'})
        return events

    def observe(self,hour,rid):
        r=self.rng;p=self.params;s=self.species;sc=self.scenario
        biomass=float(self.weights[self.alive].sum()/1000);density=biomass/self.volume*1000
        crisis=self.start<=hour<self.end
        filtr=not(crisis and sc in ['amonio','combinado']);air=not(crisis and sc in ['hipoxia','combinado'])
        if hour:
            temp_goal=self.basetemp+np.sin(2*np.pi*hour/24)
            if crisis and sc in ['termico','combinado']:temp_goal+=8*self.severity
            self.temp=float(np.clip(self.temp+.15*(temp_goal-self.temp)+r.normal(0,.1),10,42))
            ph_goal=self.baseph+(.95*self.severity if crisis and sc in ['ph','combinado'] else 0)
            self.ph=float(np.clip(self.ph+.12*(ph_goal-self.ph)+r.normal(0,.015),4.5,10))
            nitrogen=biomass*p['excrecion_mg_n_kg_h']/self.volume
            if crisis and sc in ['amonio','combinado']:nitrogen+=.10*self.severity
            self.tan=max(0.,(self.tan+nitrogen)*(1-p['filtracion_fraccion_h']*filtr))
            if hour%24==0:self.tan*=.8
            consumption=biomass*float(r.uniform(150,250))/self.volume
            self.ox+=(.35 if air else .025)*(max(1.,8.5-.12*(self.temp-20))-self.ox)-consumption
            if crisis and sc in ['hipoxia','combinado']:self.ox-=.35*self.severity
            self.ox=float(np.clip(self.ox+r.normal(0,.025),.1,10))
        nh3=float(nh3_desde_tan(self.tan,self.ph,self.temp))
        measured=np.array([self.ph,self.temp,self.ox,self.tan])+r.normal(0,[.025,.12,.08,.025])
        measured[2:]=np.maximum(measured[2:],0)
        nh3m=float(nh3_desde_tan(measured[3],measured[0],measured[1]))
        self.history.append([nh3m,measured[2]])
        changes=np.zeros(4) if self.previous is None else measured-self.previous
        self.previous=measured.copy()
        phdev=np.maximum(s.ph_min.to_numpy()-self.ph,0)+np.maximum(self.ph-s.ph_max.to_numpy(),0)
        tdev=np.maximum(s.temp_min.to_numpy()-self.temp,0)+np.maximum(self.temp-s.temp_max.to_numpy(),0)
        odef=np.maximum(s.oxigeno_min.to_numpy()-self.ox,0)
        self.stress=np.minimum(phdev/2+tdev/4+odef/2+max(0,nh3/p['escala_nh3_n']-1),15)
        recent=np.array(self.history[-6:]);rows=[]
        for i in np.flatnonzero(self.alive):
            rows.append({'corrida_id':rid,'pez_id':self.tid*16+int(i),'pecera_id':self.tid,'hora_sim':hour,
                'escenario':sc,'especie_nombre':s.especie_nombre.iloc[i],'peso_gramos':float(self.weights[i]),
                'ph':measured[0],'temperatura':measured[1],'oxigeno':measured[2],'tan_mg_n_l':measured[3],
                'nh3_mg_n_l':nh3m,'densidad_kg_m3':density,'volumen_l':self.volume,
                'ph_desvio':max(0,s.ph_min.iloc[i]-measured[0])+max(0,measured[0]-s.ph_max.iloc[i]),
                'temp_desvio':max(0,s.temp_min.iloc[i]-measured[1])+max(0,measured[1]-s.temp_max.iloc[i]),
                'ox_deficit':max(0,s.oxigeno_min.iloc[i]-measured[2]),'exposicion_nh3_6h':float(recent[:,0].mean()),
                'exposicion_ox_6h':float(np.maximum(s.oxigeno_min.iloc[i]-recent[:,1],0).mean()),
                'cambio_ph_1h':changes[0],'cambio_temp_1h':changes[1],'cambio_ox_1h':changes[2],
                'cambio_tan_1h':changes[3],'aireacion_activa':int(air),'filtro_activo':int(filtr)})
        water={'id':self.tid,'ph':float(measured[0]),'temperatura':float(measured[1]),'oxigeno':float(measured[2]),
            'nh3':nh3m,'hora_lectura':hour,'vivos':int(self.alive.sum())}
        return rows,water

class LiveEngine:
    def __init__(self,fichas,rid,seed,scenario):
        self.rid=rid;self.hour=-1;self.events=[];self.water=[]
        params=parametros_corrida(seed+100000)
        streams=np.random.SeedSequence(seed).spawn(3)
        self.tanks=[Tank(fichas,i,streams[i],params,scenario) for i in range(3)]

    def step(self):
        if self.hour>=96:raise ValueError('La simulación ya terminó')
        hour=self.hour+1;rows=[];self.water=[]
        for tank in self.tanks:
            if hour:self.events.extend(tank.transition(hour,self.rid))
            current,water=tank.observe(hour,self.rid)
            rows.extend(current);self.water.append(water)
        self.hour=hour
        return rows
