import React,{useEffect,useState} from 'react';
import './simulation.css';

export const defaultConfig={intensidad:'moderado',inicio:24,duracion:18,sensores:'normal',peceras:[
 {especie:'Tilapia',peces:16,volumen_l:1500},{especie:'Carpa',peces:16,volumen_l:1800},{especie:'Gamitana',peces:16,volumen_l:1800}]};
const pc=n=>n==null?'Sin casos':new Intl.NumberFormat('es-PE',{style:'percent',maximumFractionDigits:1}).format(n);
async function api(url,body){const response=await fetch('/api'+url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined);const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Revisa los valores ingresados');return data;}

export function Configuration({value,onChange,stable}){
 const [species,setSpecies]=useState([]);
 useEffect(()=>{let active=true;api('/configuracion-simulador').then(x=>{if(active)setSpecies(x.especies)}).catch(()=>{});return()=>{active=false}},[]);
 const update=(key,v)=>onChange({...value,[key]:v});
 const tank=(index,key,v)=>update('peceras',value.peceras.map((p,i)=>i===index?{...p,[key]:v}:p));
 return <fieldset className="lab-config"><legend>Condiciones de la prueba · motor v2</legend>
 <div className="form-grid"><label>Intensidad del incidente<select disabled={stable} value={value.intensidad} onChange={e=>update('intensidad',e.target.value)}><option value="leve">Leve</option><option value="moderado">Moderada</option><option value="severo">Severa</option></select></label>
 <label>Sensores<select value={value.sensores} onChange={e=>update('sensores',e.target.value)}><option value="normal">Con ruido de medición</option><option value="intermitente">Con ruido, deriva y cortes</option></select></label>
 <label>Inicio del incidente (hora)<input type="number" disabled={stable} min="1" max="84" required value={value.inicio} onChange={e=>update('inicio',Number(e.target.value))}/></label>
 <label>Duración del incidente (horas)<input type="number" disabled={stable} min="1" max={Math.min(72,96-value.inicio)} required value={value.duracion} onChange={e=>update('duracion',Number(e.target.value))}/></label></div>
 {value.peceras.map((p,i)=><div className="tank-config" key={i}><b>Pecera {i+1}</b><label>Especie<select value={p.especie} onChange={e=>tank(i,'especie',e.target.value)}>{(species.length?species:defaultConfig.peceras.map(p=>({especie_nombre:p.especie}))).map(s=><option key={s.especie_nombre}>{s.especie_nombre}</option>)}</select></label><div className="form-grid"><label>Peces<input type="number" min="1" max="80" required value={p.peces} onChange={e=>tank(i,'peces',Number(e.target.value))}/></label><label>Volumen (litros)<input type="number" min="100" max="10000" required value={p.volumen_l} onChange={e=>tank(i,'volumen_l',Number(e.target.value))}/></label></div></div>)}
 <p>Una especie por pecera. Su temperatura y pH iniciales se calculan con la ficha del proyecto. El ambiente estable no programa incidentes. Estos horarios corresponden al incidente; todas las simulaciones recorren 96 horas.</p></fieldset>;
}

export function EvaluationV2(){
 const [data,setData]=useState(null);
 useEffect(()=>{api('/evaluacion-v2').then(setData).catch(()=>{})},[]);
 return <section className="panel spaced"><div className="panel-heading"><div><h2>Evaluación del modelo en el motor v2</h2><p>{data?.nota??'Consulta de validación independiente del motor nuevo.'}</p></div></div>{data?.modelos?.length?<><div className="table-scroll"><table><thead><tr><th>Modelo</th><th>Horizonte</th><th>Casos</th><th>Cobertura</th><th>Muertes / casos</th><th>Recall</th><th>Alertas correctas</th><th>Falsas alarmas</th><th>Muertes sin aviso</th><th>ROC-AUC</th><th>AP</th></tr></thead><tbody>{(data.comparacion??data.modelos).map(m=><tr key={`${m.version??'v3'}-${m.horizonte_h}`}><td>{m.version??'v3'}</td><td>{m.horizonte_h} h</td><td>{m.n}</td><td>{pc(m.cobertura)}</td><td>{pc(m.prevalencia)}</td><td>{pc(m.recall)}</td><td>{pc(m.precision)}</td><td>{m.fp}</td><td>{m.fn}</td><td>{pc(m.roc_auc)}</td><td>{pc(m.pr_auc_ap)}</td></tr>)}</tbody></table></div><p className="panel-text">{data.conclusion}</p>{data.nota_despliegue&&<p className="panel-text">{data.nota_despliegue}</p>}</>:<p className="panel-text">{data?.nota??'Cargando evaluación…'}</p>}</section>;
}
