# Reorganización y limpieza aprobadas

Rama: `refactor/limpieza-y-orden`.

Punto seguro: commit `fd6fcdc21d8d2a712650cf8d1c840fc2cbcde821`, con el mensaje `chore: punto seguro antes de reorganización y limpieza`, y tag `punto-seguro-pre-refactor`. Se comprobó que ambos apuntaban al mismo estado antes de empezar. El usuario aprobó los movimientos, las ocho eliminaciones y la actualización de documentación tras el análisis de solo lectura.

## Organización por funcionalidad

Los movimientos se realizaron con `git mv`. Rutas relativas a `web/frontend/src`:

- `Insights.jsx` → `features/mortalidad/Insights.jsx`.
- `insights.css` → `features/mortalidad/insights.css`.
- `Laboratory.jsx` → `features/simulacion/SimulationPanels.jsx`.
- `laboratory.css` → `features/simulacion/simulation.css`.
- `Demand.jsx` → `features/demanda/Demand.jsx`.
- `DemandLive.jsx` → `features/demanda/DemandLive.jsx`.
- `demand.css` → `features/demanda/demand.css`.
- `style.css` → `styles/global.css`.
- `live.css` → `styles/live.css`.

Se ajustaron los imports de `main.jsx` y del CSS de `SimulationPanels.jsx`, además de las rutas documentadas. La configuración y la evaluación que antes estaban en `Laboratory.jsx` se conservan: siguen en uso. No se extrajeron funciones ni se cambió la lógica de los componentes.

Commit de este bloque: `4073725`, `refactor: organizar componentes React por funcionalidad`.

## Eliminaciones

Antes de borrar, se repitió la búsqueda por nombre de archivo entre los archivos de texto versionados, incluyendo código, scripts, documentación y configuraciones no sensibles. No se encontraron referencias externas al conjunto aprobado. Se usó `git rm` exclusivamente para estos ocho archivos:

- `herramientas/actualizar_ui_vivo.py`: parche de la interfaz anterior; su referencia desde `ordenar_proyecto.ps1` pertenece al mismo conjunto retirado.
- `herramientas/migrar_rutas.py`: transformación puntual de rutas de una reorganización anterior.
- `herramientas/organizar_cierre.py`: generador puntual de estructura y documentación anteriores.
- `herramientas/finalizar_organizacion.py`: finalizador de aquella migración, con una ubicación anterior de la utilidad de PostgreSQL.
- `herramientas/ordenar_proyecto.ps1`: migración de una estructura que ya está organizada.
- `herramientas/organizar_raiz.ps1`: traslado histórico ya realizado.
- `herramientas/limpiar_proyecto.ps1`: limpieza antigua condicionada a un commit específico anterior.
- `../../archivo_historico/experimento_v2/RESULTADOS.xlsx.inspect.ndjson`: archivo auxiliar de inspección; el Excel original se conserva. La ruta de este punto se expresa desde esta carpeta `documentacion`.

Las siete rutas de herramientas anteriores se expresan desde la carpeta de la aplicación. Las ocho eliminaciones retiran 260.530 bytes del árbol de trabajo; Git conserva las versiones anteriores, por lo que esa cifra no representa espacio neto liberado en disco.

Commit de este bloque: `19764d7`, `chore: retirar utilidades antiguas y archivo auxiliar aprobados`.

## Conservado y pendiente

- Se conservan motores Python, modelos de todas las versiones, CSV, notebooks, experimentos, checkpoints y bases de datos.
- Se conserva `web/backend/live_engine.py` por compatibilidad con checkpoints existentes.
- Se conservan las copias históricas idénticas que tienen imports o rutas relativos propios.
- Se conservan capturas, vistas previas, logs, cachés y dependencias instaladas. Su eliminación no formó parte de la aprobación.
- Se conserva `herramientas/configurar_postgres.py`.
- No se cambiaron `.env`, credenciales, archivos de despliegue, requisitos ni configuraciones de Vite. No se renombró la carpeta de la aplicación.
- No se encontraron dependencias declaradas que se pudieran retirar con seguridad. Los `.gitignore` existentes ya cubren dependencias instaladas, cachés, logs, temporales y bases locales; no necesitaron cambios.
- El README interno se actualizó para describir mortalidad y ventas vigentes y enlazar la instalación y explicaciones principales.

## Verificación

- Se ejecutó `verificar.ps1` con `DATABASE_URL=sqlite:///logs/verificacion_v2.db`, una base de verificación independiente de las simulaciones del usuario.
- Pasaron las **54 pruebas Python** de estadísticas, alertas, API, exportación, motor, checkpoints, demanda y reloj comercial. La prueba que provoca `disco ocupado` confirmó la recuperación esperada y también pasó.
- El build React/Vite terminó correctamente. Los archivos de `dist` son idénticos a los del tag de respaldo: conservan los mismos nombres y contenido.
- Se compararon los nueve archivos movidos contra el tag. Su contenido se conserva, excepto el cambio previsto del import de `laboratory.css` a `simulation.css`.
- Se revisaron referencias antiguas y `git diff --check`. No quedaron errores de espacios ni imports a las ubicaciones anteriores.
- No se ejecutó un linter porque no existe una configuración ni un comando de lint en el repositorio. No se instalaron herramientas adicionales.
- No se cambiaron módulos Python ni reglas de simulación o predicción. La comprobación de interfaz de esta reorganización consiste en el build y la igualdad de sus archivos; no se repitió una sesión manual de navegador.

## Volver al punto seguro

Desde la raíz del repositorio:

```powershell
git reset --hard punto-seguro-pre-refactor
```

Este comando descarta los cambios locales en archivos versionados y sitúa la rama actual en el respaldo. El tag conserva el código versionado anterior a la limpieza; no respalda bases ignoradas ni `.env`. El comando no es necesario para consultar el historial de los commits.
