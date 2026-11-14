from .labels import LABELS
from .paths import ROOT, DATA, SEED, MODELS, EXPORTS
"""Informe XLSX por corrida: datos completos, cortes y evaluación."""
from io import BytesIO
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.formatting.rule import ColorScaleRule
from .service import get_run, snapshot_data, evaluate, metrics, models, conditions
from . import analysis

def excel(rid,hour,horizon):
    r,d=get_run(rid); snap=snapshot_data(r,d,hour,horizon)
    out=BytesIO()
    risk=f'riesgo_{horizon}h'
    current=d[d.hora_sim.eq(hour)].sort_values(risk,ascending=False).copy()
    current['condiciones_observadas']=current.apply(lambda row:'; '.join(conditions(row)),axis=1)
    stats=analysis.statistics_data(r,d,hour)
    track=analysis.tracking_data(r,d,hour,horizon)
    model_metrics=metrics()
    # Los resultados futuros se mantienen identificados; no se usan para inferencia.
    guide=pd.DataFrame([
        ['Informe','Pisciber BSF · Mortalidad simulada'],['Corrida',r['nombre']],['Escenario',LABELS.get(r['escenario'],r['escenario'])],
        ['Semilla',r['semilla']],['Corte (hora de simulación)',hour],['Horizonte (horas)',horizon],
        ['Modelo',f"XGBoost calibrado · {r.get('vivo',{}).get('modelo_version','v3')}"],['Peces vivos en el corte',snap['peces']],
        ['Muertes esperadas en el corte',snap['esperadas']],['Peces con alerta',snap['alertas']],
        ['Probabilidad individual','riesgo_12h=0.60 se muestra como 60 %. Es una estimación, no una muerte segura.'],
        ['Muertes esperadas','Suma de probabilidades de peces vivos de una pecera en una misma hora. No sumar horas.'],
        ['Alertas','Umbral elegido previamente en validación: F2 para v3; F1 con recall mínimo de 65 % en validación para v4. No equivale a 50 % ni 60 %.'],
        ['Pecera','El riesgo medio es un promedio individual; no es la probabilidad de que muera al menos un pez.'],
        ['Condiciones','Valores observados y desvíos del agua. No prueban la causa de muerte.'],
        ['Desenlaces','observado_*h y hora_evento son resultados futuros SOLO para evaluación. No son predictores.'],
        ['Seguimiento','Un resultado observado vacío significa horizonte incompleto al finalizar la simulación.'],
        ['Historial','Una fila es un pez vivo en una hora. Un mismo pez aparece en varias horas.'],
        ['Actualización','Excel contiene resultados guardados; modificar el agua aquí no ejecuta el modelo.'],
        ['Origen','Simulación universitaria; predicción basada en mediciones e historia disponibles hasta cada hora.'],
        ['Cálculo en vivo',f"Hora calculada: {r.get('vivo',{}).get('hora','corrida completa')}. Las observaciones futuras no se generan por adelantado."],
        ['Resultados pendientes','observado_*h queda vacío hasta completar el plazo desde la observación. Las probabilidades emitidas se conservan.'],
    ],columns=['Concepto','Explicación / valor'])
    extra={}
    if r.get('vivo',{}).get('motor')=='incremental_v2':
        from .live import details
        import json
        info=details(rid,r['vivo']['hora'])
        extra={'Configuracion v2':pd.DataFrame([{'clave':k,'valor':json.dumps(v,ensure_ascii=False)} for k,v in info['configuracion'].items()]),
               'Bitacora v2':pd.DataFrame(info['bitacora'],columns=['hora','pecera_id','tipo','detalle']),
               'Intervenciones v2':pd.DataFrame(info['acciones'],columns=['id','pecera_id','accion','valor','duracion','solicitada_hora','efectiva_hora']),
               'Sensores v2':pd.DataFrame(r['agua_actual'])}
        path=ROOT/'resultados/entrenamiento_v4/informe.json'
        if path.exists():
            report=json.loads(path.read_text(encoding='utf-8'))
            extra['Comparacion modelos v4']=pd.DataFrame(report['comparacion'])
        guide.loc[len(guide)]=['Motor','incremental_v2: consulta la evaluación de la versión de modelo de esta corrida.']
        guide.loc[len(guide)]=['Datos ausentes','riesgo vacío = sin predicción; no es 0 %. Los porcentajes excluyen estos casos. Consultar calidad_prediccion.']
        guide.loc[len(guide)]=['Historia estimada','Se permite arrastrar hasta dos lecturas pasadas para las variables históricas; no se inventa una lectura actual. Un hueco mayor bloquea la inferencia restante de ese pez.']
        guide.loc[len(guide)]=['Intervenciones','Se aplican desde efectiva_hora. Una supervivencia tras intervenir no demuestra que la alerta fuera injustificada.']
    with pd.ExcelWriter(out,engine='openpyxl') as writer:
        body_font=Font(name='Calibri',size=11)
        body_alignment=Alignment(vertical='center')
        header_font=Font(name='Calibri',bold=True,color='FFFFFF')
        header_fill=PatternFill('solid',fgColor='1A3844')
        header_alignment=Alignment(wrap_text=True,vertical='center')
        sheets={'Leer primero':guide,'Peceras al corte':pd.DataFrame(snap['peceras']),
            'Peces al corte':current,'Historial completo':d,
            'Evaluacion de corrida':pd.DataFrame([{'horizonte_h':h,**evaluate(d,h)} for h in [1,6,12]]),
            'Modelo prueba reservada':pd.DataFrame(model_metrics['modelos']),
            'Intervalos modelo':pd.DataFrame(model_metrics['intervalos']),
            'Mortalidad al corte':pd.DataFrame(stats['grupos']),
            'Evolucion poblacion':pd.DataFrame(stats['evolucion']),
            'Seguimiento al corte':track[['pez_id','pecera_id','especie_nombre','hora_sim','hora_limite','probabilidad','alerta','resultado','atendida','hora_atencion','nota_atencion','intervencion_en_plazo']],
            'Sugerencias de revision':pd.DataFrame(analysis.recommendations(rid,hour,horizon),columns=['pecera_id','condicion','peces_afectados','especies','sugerencia','origen'])}
        sheets.update(extra)
        for name,df in sheets.items():
            df.to_excel(writer,sheet_name=name,index=False)
            ws=writer.sheets[name];ws.freeze_panes='D2' if len(df)>100 else 'A2';ws.sheet_view.showGridLines=False
            ws.auto_filter.ref=ws.dimensions;ws.row_dimensions[1].height=32
            for cell in ws[1]:
                cell.font=header_font;cell.fill=header_fill;cell.alignment=header_alignment
            for col in ws.columns:
                header=str(col[0].value)
                ws.column_dimensions[col[0].column_letter].width=min(38,max(16,len(header)+2))
                for c in col[1:]:
                    c.font=body_font;c.alignment=body_alignment
                    if header.startswith('riesgo_') or header in ['accuracy','precision','recall','f1','roc_auc','pr_auc_ap','prevalencia']:
                        c.number_format='0.00%'
                    elif isinstance(c.value,float):c.number_format='0.000'
                if header.startswith('riesgo_'):
                    letter=col[0].column_letter
                    ws.conditional_formatting.add(f'{letter}2:{letter}{ws.max_row}',ColorScaleRule(start_type='num',start_value=0,start_color='EAF3F0',end_type='num',end_value=1,end_color='DFA39A'))
            if name=='Leer primero':
                ws.column_dimensions['A'].width=32;ws.column_dimensions['B'].width=105
                for row in ws.iter_rows(min_row=2):
                    row[1].alignment=Alignment(wrap_text=True,vertical='center');ws.row_dimensions[row[0].row].height=34
    return out.getvalue()
