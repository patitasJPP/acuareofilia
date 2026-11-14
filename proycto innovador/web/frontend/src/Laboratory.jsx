import React,{useEffect,useState} from 'react';
import {Info,GitBranch,SlidersHorizontal} from 'lucide-react';
import './laboratory.css';

export const defaultConfig={intensidad:'moderado',inicio:24,duracion:18,sensores:'normal',peceras:[
 {especie:'Tilapia',peces:16,volumen_l:1500},{especie:'Carpa',peces:16,volumen_l:1800},{especie:'Gamitana',peces:16,volumen_l:1800}]};
const actions={aireacion:'Activar aireación',filtro:'Restablecer filtro',recambio:'Recambio parcial de agua',temperatura:'Regular temperatura'};
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
 <label>Duración (horas)<input type="number" disabled={stable} min="1" max={Math.min(72,96-value.inicio)} required value={value.duracion} onChange={e=>update('duracion',Number(e.target.value))}/></label></div>
 {value.peceras.map((p,i)=><div className="tank-config" key={i}><b>Pecera {i+1}</b><label>Especie<select value={p.especie} onChange={e=>tank(i,'especie',e.target.value)}>{(species.length?species:defaultConfig.peceras.map(p=>({especie_nombre:p.especie}))).map(s=><option key={s.especie_nombre}>{s.especie_nombre}</option>)}</select></label><div className="form-grid"><label>Peces<input type="number" min="1" max="80" required value={p.peces} onChange={e=>tank(i,'peces',Number(e.target.value))}/></label><label>Volumen (litros)<input type="number" min="100" max="10000" required value={p.volumen_l} onChange={e=>tank(i,'volumen_l',Number(e.target.value))}/></label></div></div>)}
 <p>Una especie por pecera. Su temperatura y pH iniciales se calculan con la ficha del proyecto. El ambiente estable no programa incidentes.</p></fieldset>;
}

export function Laboratory({rid,hour,state,following,runs,onBranch}){
 const [info,setInfo]=useState(null),[error,setError]=useState(''),[message,setMessage]=useState(''),[saving,setSaving]=useState(false),[revision,setRevision]=useState(0);
 const [tid,setTid]=useState(0),[kind,setKind]=useState('aireacion'),[value,setValue]=useState(20),[duration,setDuration]=useState(12),[other,setOther]=useState(''),[pair,setPair]=useState(null);
 useEffect(()=>{let active=true;api(`/vivo/${rid}/detalle?hora=${hour}`).then(x=>{if(active)setInfo(x)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[rid,hour,revision]);
 useEffect(()=>{setInfo(null);setMessage('');setError('');setPair(null);setOther('')},[rid]);
 const allowed=state?.estado==='pausada'&&following&&hour===state.hora&&hour<96;
 async function apply(e){e.preventDefault();setSaving(true);setError('');try{const a=await api(`/vivo/${rid}/intervenciones`,{pecera_id:tid,accion:kind,valor:['aireacion','filtro'].includes(kind)?0:value,duracion:duration,hora_esperada:hour});setMessage(`Acción guardada. Se aplicará al avanzar a la hora ${a.efectiva_hora}.`);setRevision(v=>v+1)}catch(e){setError(e.message)}finally{setSaving(false)}}
 async function fork(){setSaving(true);setError('');try{const row=await api(`/vivo/${rid}/rama`,{hora:hour});await onBranch(row)}catch(e){setError(e.message)}finally{setSaving(false)}}
 async function compare(){setSaving(true);setError('');setPair(null);try{setPair(await api(`/vivo/${rid}/pareja/${other}`))}catch(e){setError(e.message)}finally{setSaving(false)}}
 return <section className="panel laboratory spaced"><div className="panel-heading"><div><h2><SlidersHorizontal size={17}/> Laboratorio de decisiones</h2><p>Hora consultada: {hour}. Las acciones modifican el agua desde la próxima hora.</p></div><button className="button" disabled={saving||hour>=96} onClick={fork}><GitBranch size={16}/> Crear copia desde h {hour}</button></div>
 {error&&<div className="error" role="alert">{error}</div>}{message&&<p className="lab-message" role="status">{message}</p>}
 <div className="lab-body"><form onSubmit={apply} className="sim-form"><h3>Aplicar una acción</h3><p>{allowed?'Corrida pausada: prepara la acción y pulsa Reanudar.':'Para intervenir, pausa la corrida y pulsa Volver al presente. Para cambiar el pasado, crea una copia.'}</p>
 <div className="form-grid"><label>Pecera<select value={tid} onChange={e=>setTid(Number(e.target.value))}>{[0,1,2].map(n=><option value={n} key={n}>Pecera {n+1} · {info?.configuracion?.peceras[n].especie}</option>)}</select></label><label>Acción<select value={kind} onChange={e=>{setKind(e.target.value);setValue(e.target.value==='temperatura'?26:20)}}>{Object.entries(actions).map(([k,v])=><option value={k} key={k}>{v}</option>)}</select></label>
 {['recambio','temperatura'].includes(kind)&&<label>{kind==='recambio'?'Porcentaje de recambio':'Temperatura objetivo (°C)'}<input type="number" required min={kind==='recambio'?5:4} max={kind==='recambio'?30:40} step="0.5" value={value} onChange={e=>setValue(Number(e.target.value))}/></label>}
 {kind!=='recambio'&&<label>Duración de la acción (h)<input type="number" required min="1" max="48" value={duration} onChange={e=>setDuration(Number(e.target.value))}/></label>}</div>
 <button className="button primary" disabled={!allowed||saving}>Programar acción</button></form>
 <div className="lab-comparison"><h3>Comparar dos decisiones</h3><p>Selecciona otra corrida con la misma semilla y configuración. Se comparan hasta la última hora disponible en ambas.</p><select aria-label="Corrida para comparación pareada" value={other} onChange={e=>setOther(e.target.value)}><option value="">Selecciona una corrida</option>{runs.filter(r=>r.origen==='vivo'&&r.id!==rid&&r.estado==='lista').map(r=><option key={r.id} value={r.id}>{r.nombre} · #{r.id}</option>)}</select><button className="button" disabled={!other||saving} onClick={compare}>Comparar resultados</button>
 {pair&&<div className="pair-result" role="status"><b>Comparación hasta la hora {pair.hora}</b><p>Corrida #{pair.base.id}: {pair.base.muertos} muertes, {pair.base.vivos} vivos.<br/>Corrida #{pair.alternativa.id}: {pair.alternativa.muertos} muertes, {pair.alternativa.vivos} vivos.</p><p>Diferencia (alternativa − actual): <b>{pair.diferencia_muertes} muertes</b>.</p><small>{pair.nota}</small></div>}</div></div>
 <details className="lab-log" open><summary>Bitácora hasta la hora {hour} · {info?.bitacora.length??0} registros</summary><div className="table-scroll"><table><thead><tr><th>Hora</th><th>Pecera</th><th>Evento</th><th>Detalle</th></tr></thead><tbody>{info?.bitacora.slice().reverse().map((e,i)=><tr key={i}><td>{e.hora}</td><td>{e.pecera_id==null?'Todas':e.pecera_id+1}</td><td>{e.tipo.replaceAll('_',' ')}</td><td>{e.detalle}</td></tr>)}</tbody></table></div>{!info?.bitacora.length&&<p>Aún no hay incidentes, acciones ni muertes registrados.</p>}</details>
 <div className="inline-note"><Info size={16}/>La copia conserva el pasado y los mismos números aleatorios por pez y hora. No se borran observaciones ni se reviven peces en la corrida original.</div></section>;
}

export function EvaluationV2(){
 const [data,setData]=useState(null);
 useEffect(()=>{api('/evaluacion-v2').then(setData).catch(()=>{})},[]);
 return <section className="panel spaced"><div className="panel-heading"><div><h2>Modelo original frente al nuevo motor v2</h2><p>{data?.nota??'Consulta de validación independiente del motor nuevo.'}</p></div></div>{data?.modelos?.length?<><div className="table-scroll"><table><thead><tr><th>Horizonte</th><th>Casos</th><th>Cobertura</th><th>Muertes / casos</th><th>Recall</th><th>Alertas correctas</th><th>Falsas alarmas</th><th>ROC-AUC</th><th>AP</th></tr></thead><tbody>{data.modelos.map(m=><tr key={m.horizonte_h}><td>{m.horizonte_h} h</td><td>{m.n}</td><td>{pc(m.cobertura)}</td><td>{pc(m.prevalencia)}</td><td>{pc(m.recall)}</td><td>{pc(m.precision)}</td><td>{m.fp}</td><td>{pc(m.roc_auc)}</td><td>{pc(m.pr_auc_ap)}</td></tr>)}</tbody></table></div><p className="panel-text">{data.conclusion}</p></>:<p className="panel-text">{data?.nota??'Cargando evaluación…'}</p>}</section>;
}
