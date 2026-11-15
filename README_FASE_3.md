# Fase 3: infraestructura y fundamentos de inteligencia artificial

Este archivo organiza el trabajo pendiente de la Fase 3 de la plantilla del curso para el proyecto universitario Pisciber BSF. Se actualizará conforme se complete y verifique cada punto.

Los datos de peces y ventas del proyecto son **simulados**. Las propuestas y las funciones implementadas se distinguen para no atribuir al proyecto resultados que todavía no se han comprobado.

**Puntuación por confirmar:** el índice de la plantilla indica 5 puntos para esta fase, mientras que el cuerpo indica 6 y sus criterios detallados suman 6.

Estados: **[x]** disponible; **[~]** parcial o falta documentarlo; **[ ]** pendiente.

## 1. Infraestructura Cloud

- [~] Describir la arquitectura actual: React/Vite, API en Python/FastAPI y almacenamiento SQLite o PostgreSQL. La aplicación comprobada funciona localmente.
- [x] Elegir proveedor y servicio cloud: **Amazon Web Services (AWS), Amazon Lightsail**, con una instancia de servidor virtual como propuesta de IaaS.
- [~] Diseñar el alojamiento: inicialmente se propone una sola instancia con frontend React compilado, backend FastAPI, motores de simulación, modelos, bases de datos y archivos. Los relojes actuales requieren una sola instancia coordinada del backend.
- [ ] Definir configuración de servidor, dominio, DNS y HTTPS según el despliegue elegido.
- [ ] Confirmar si el docente exige un despliegue funcionando o acepta una propuesta documentada; reunir la evidencia correspondiente.

**Evidencia existente:** [README principal](README.md) y [estructura del proyecto](proycto%20innovador/documentacion/ESTRUCTURA.md).

### Arquitectura propuesta en AWS

```text
Usuario y navegador
       │ HTTPS
       ▼
Amazon Lightsail: una instancia virtual
├── Frontend React compilado
├── Backend Python / FastAPI
├── Simulación de peces y modelo XGBoost
├── Simulación de ventas y pronóstico de demanda
├── SQLite o PostgreSQL, según configuración
└── CSV, modelos guardados, exportaciones y checkpoints
```

Las partes mantienen carpetas y responsabilidades diferentes aunque compartan servidor. FastAPI puede entregar la página React compilada y atender las peticiones de la interfaz. Las simulaciones se ejecutan en el servidor mientras esté encendido y se recuperan en pausa al reiniciarlo, de acuerdo con el diseño actual.

**Justificación:** Lightsail proporciona una instancia virtual donde podemos instalar el sistema completo de una manera cercana a su ejecución local. Una sola instancia simplifica la demostración y evita ejecutar varios relojes independientes sin coordinación. Se considera una propuesta de infraestructura como servicio (IaaS): el equipo configuraría el sistema y la aplicación dentro de la máquina virtual. [Documentación de instancias Lightsail](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-instances.html).

**Estado: propuesto, todavía no desplegado.** Falta elegir y comprobar el sistema operativo, la capacidad y el presupuesto; validar las versiones de los modelos en ese entorno; configurar DNS, HTTPS y copias de seguridad; y comprobar el funcionamiento después del despliegue. Algunas versiones de modelos guardadas en Windows podrían necesitar adaptación o reentrenamiento. Deben respaldarse tanto las bases como los CSV, checkpoints y demás archivos persistentes. Más adelante se podrían estudiar RDS para PostgreSQL y S3 para archivos, con las adaptaciones y migraciones necesarias.

## 2. DevOps e integración y despliegue continuos

- [x] Uso de Git, commits, rama de trabajo y punto de respaldo.
- [x] Script local de verificación para pruebas Python y build de React. La última verificación registrada completó 54 pruebas.
- [ ] Definir el repositorio compartido y el flujo de trabajo del equipo, según lo que realmente utilicen.
- [ ] Automatizar pruebas y build mediante integración continua (CI).
- [ ] Definir e implementar despliegue continuo (CD) si se realiza el despliegue cloud.
- [ ] Capturar evidencia de una ejecución automática y explicar cómo se detectan fallos.

**Evidencia existente:** [informe de limpieza y verificación](proycto%20innovador/documentacion/LIMPIEZA_REFACTOR.md) y `proycto innovador/verificar.ps1`.

### Flujo de trabajo propuesto para el equipo

Cada integrante desarrollará sus cambios en una rama propia del repositorio. Cuando termine una mejora o corrección, abrirá una solicitud de integración (*pull request*) para que otro integrante revise los cambios antes de incorporarlos a la rama principal, `main`.

Se propone proteger `main` para impedir modificaciones directas y exigir al menos **una aprobación de otro integrante del equipo**. Además, la solicitud deberá superar las verificaciones automáticas configuradas en el repositorio remoto: pruebas del backend y construcción del frontend. Si alguna verificación falla, el equipo revisará y corregirá el problema antes de integrar el cambio.

Para el despliegue se propone un flujo de integración y despliegue continuos (**CI/CD**). La integración continua ejecutará las comprobaciones sobre cada cambio propuesto; el proceso de despliegue se definirá junto con la configuración del servidor en AWS y estará condicionado a que las verificaciones correspondientes se completen correctamente.

El objetivo de este proceso es detectar errores antes de incorporarlos a la rama principal o publicar una nueva versión, facilitar la revisión entre compañeros y reducir el riesgo de afectar el funcionamiento de Pisciber. Las pruebas y revisiones disminuyen ese riesgo, pero no pueden garantizar que nunca aparezca un fallo.

**Estado:** el proyecto ya usa Git, ramas, commits y un script local de verificación. La protección de `main`, las aprobaciones obligatorias y los flujos automáticos CI/CD son acuerdos propuestos; todavía falta configurarlos y comprobarlos en el repositorio remoto y, para el despliegue, en AWS.

## 3. Espacio de búsqueda y resolución de problemas

- [~] Disponemos de un simulador de peceras con condiciones de agua y escenarios.
- [ ] Elegir un problema concreto de búsqueda y definir su objetivo.
- [ ] Describir estado inicial, estado objetivo, acciones posibles, restricciones y criterio de costo.
- [ ] Preparar un ejemplo pequeño y reproducible para explicar el problema.

**Posible problema, aún no implementado:** explorar secuencias de acciones simuladas para mejorar condiciones de una pecera. Antes hay que definir cómo se representan los estados, las acciones y los criterios para considerar alcanzado el objetivo.

## 4. Algoritmo de búsqueda

- [ ] Elegir y justificar un algoritmo clásico solicitado en la plantilla: BFS, DFS, Hill Climbing o A*.
- [ ] Implementarlo sobre el problema definido en el punto 3.
- [ ] Comprobar el resultado y documentar un caso de entrada, la secuencia encontrada y sus limitaciones.
- [ ] Preparar evidencia de ejecución para el informe.

**Opción para estudiar:** BFS en un espacio pequeño con acciones discretas y costos iguales. Es una propuesta, no una funcionalidad existente ni una decisión definitiva.

## 5. Definición del problema de machine learning

- [x] **Mortalidad:** clasificación binaria; se estima si un pez muere o no dentro de 1, 6 o 12 horas simuladas.
- [x] **Demanda:** pronóstico de una cantidad numérica de peces solicitados por especie y semana.
- [ ] Redactar para cada problema su variable objetivo, datos de entrada, horizonte, unidad y justificación de la elección.
- [ ] Explicar la separación de datos de entrenamiento y evaluación y que los datos son simulados.

**Evidencia existente:** [explicación de mortalidad](EXPLICACION_MACHINE_LEARNING.md) y [guía de demanda](proycto%20innovador/documentacion/DEMANDA.md).

## 6. Resultados de los primeros modelos

- [~] Existe un experimento histórico de regresión logística para mortalidad, con matriz de confusión y métricas.
- [ ] Explicar preparación de datos, objetivo, separación por grupos y significado de las métricas del experimento histórico.
- [ ] Verificar si el docente acepta un experimento anterior o exige aplicar el modelo inicial a los datos y protocolo actuales.
- [ ] Si se exige el protocolo actual, entrenar y evaluar una regresión logística con ese protocolo antes de presentar sus resultados.
- [ ] No mezclar los resultados históricos con los del XGBoost actual como si provinieran de la misma prueba.

**Evidencia existente:** [informe histórico](archivo_historico/resultados_ml/INFORME.md) y [comparación histórica](archivo_historico/resultados_ml/comparativa_modelos.csv).

## Orden de trabajo

1. Infraestructura Cloud: revisar requisitos y documentar arquitectura actual y propuesta.
2. DevOps: preparar la automatización y evidencias que correspondan.
3. Definir el problema de búsqueda.
4. Implementar y evaluar un algoritmo de búsqueda.
5. Redactar clasificación y pronóstico numérico.
6. Documentar o repetir el modelo inicial, según el requisito del docente.
7. Reunir capturas y resultados y revisar que cada afirmación tenga evidencia.

## Seguimiento

| Punto | Estado | Próximo paso |
|---|---|---|
| Infraestructura Cloud | Parcial | Propuesta Lightsail definida; concretar capacidad, seguridad, respaldo y alcance del despliegue. |
| DevOps y CI/CD | Parcial | Definir repositorio compartido y automatizar verificaciones. |
| Espacio de búsqueda | Parcial | Formular el problema y sus estados. |
| Algoritmo de búsqueda | Pendiente | Elegir, implementar y comprobar un algoritmo. |
| Problema de machine learning | Parcial | Redactar la justificación y las variables. |
| Primeros modelos | Parcial | Revisar si se acepta la regresión logística histórica. |

La aplicación de mortalidad usa XGBoost; en demanda se compararon varios métodos y se seleccionó el promedio de cuatro semanas en validación. No se debe describir este promedio como un modelo de machine learning.
