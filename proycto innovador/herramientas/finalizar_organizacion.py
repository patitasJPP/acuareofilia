from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'README.md';s=p.read_text(encoding='utf-8')
for a,b in [('`cd frontend`','`cd web/frontend`'),('`models/`','`simulacion/modelos/`'),('`ml/`','`simulacion/ml/`'),('`seed/`','`simulacion/datos_base/`'),('`data/','`datos/corridas/'),('`exports/`','`resultados/exportaciones/`')]:s=s.replace(a,b)
s=s.replace('`.venv\\Scripts\\python.exe -m unittest backend.test_live backend.test_app -v`','`powershell -File verificar.ps1`')
s+='''

## Estadísticas, seguimiento y atención

Estadísticas de corrida presenta población inicial, vivos, muertes únicas y mortalidad acumulada al corte por especie y pecera, además de la evolución y lecturas del agua.

Seguimiento de alertas conserva cada observación, riesgo emitido, hora límite y resultado conocido al corte. Se puede filtrar por pendientes, avisos correctos, falsas alarmas, muertes sin aviso y supervivencias correctas. La atención se registra una vez por pez/hora/horizonte con nota opcional y demora en horas simuladas. No cambia las condiciones ni convierte el aviso en acierto.

La comparación de escenarios usa corridas completas de 96 h, separadas por motor y ambiente. Excluye repeticiones con igual semilla/ambiente/motor. Las tasas se calculan sumando conteos; las corridas en curso no se mezclan con las completas.

El Excel añade mortalidad por grupo, evolución poblacional, seguimiento al corte y sugerencias basadas en reglas de revisión. Los desenlaces siguen pendientes hasta completar el horizonte.

Consulta [la estructura](documentacion/ESTRUCTURA.md) y [la guía de presentación](documentacion/GUIA_PRESENTACION.md). El motor puede ejecutarse sin la web con `python -m simulacion.ejecutar`.
'''
p.write_text(s,encoding='utf-8')
config=root/'configurar_postgres.py'
s=config.read_text(encoding='utf-8').replace("Path(__file__).resolve().parent/'web'","Path(__file__).resolve().parents[1]/'web'")
(root/'herramientas/configurar_postgres.py').write_text(s,encoding='utf-8')
