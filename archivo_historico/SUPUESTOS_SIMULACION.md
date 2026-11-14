# Supuestos del experimento v2

Experimento universitario, sin mortalidad real ni validación biológica. Se mejoran coherencia, trazabilidad y evaluación. No se ajustan coeficientes para mejorar las métricas.

## Diseño

Seis escenarios y ocho réplicas por escenario: cuatro de entrenamiento, una de calibración, una de validación y dos de prueba. Cada corrida tiene tres peceras nuevas con 16 peces cada una, 96 transiciones horarias y observación desde hora cero. No se reponen muertos. Semillas y parámetros se registran en `experimento_v2/corridas.csv`.

El CSV histórico aporta solo nombres, pesos y rangos por especie. No se reutilizan sus etiquetas. Las fichas locales tampoco tienen validación externa. No se consulta PostgreSQL en este experimento.

## Química y ambiente

- Volumen en litros, peso en gramos, biomasa en kg y densidad en kg/m³. La biomasa se calcula con los pesos de los peces vivos.
- TAN y NH3-N se expresan ambos como mg de nitrógeno/L. No equivalen a mg de molécula NH3/L. La fracción no ionizada es `1/(1+10^(pKa-pH))`, con `pKa=0.09018+2729.92/(273.2+T)`, para agua dulce. [Fuente EPA 1998](https://www.epa.gov/sites/default/files/2019-02/documents/update-wqc-ammonia-1998.pdf).
- Excreción: 15–45 mg N/kg/h; filtración: fracción 0,025–0,12 por hora; recambio: 20 % cada 24 h con TAN de entrada cero. Todos son supuestos exploratorios.
- Oxígeno en mg O₂/L; consumo supuesto de 150–250 mg O₂/kg/h. Intercambio gaseoso y concentración objetivo son simplificaciones, no un modelo validado de solubilidad.
- El pH sigue un objetivo con ruido; no se modela el balance completo de alcalinidad y carbono. Hay ciclo diario de temperatura, incidentes de duración aleatoria y recuperación posterior.

## Mortalidad supuesta

Tasa base 0,00003–0,0003/h; coeficiente agudo 0,002–0,008/h por unidad del índice elevado a 1,4; coeficiente crónico 0,001–0,004/h por unidad del índice. La carga crónica retiene 0,92–0,98 por hora y aumenta 0,12 × estrés. Probabilidad `1-exp(-tasa)`, siempre acotada.

La escala de sensibilidad NH3-N de 0,02–0,06 mg N/L NO es un límite universal de seguridad. Índices, tasas y vulnerabilidad individual son construcciones didácticas. La fuente química NO valida la ecuación de mortalidad. Nitritos, salinidad, enfermedades transmisibles y depredación no se simulan sin parámetros trazables.

## Mediciones y aprendizaje

Ruido normal supuesto: desviación estándar de pH 0,025; temperatura 0,12 °C; oxígeno 0,08 mg/L; TAN 0,025 mg N/L. No corresponde a un sensor comercial validado.

La lista positiva de predictores incluye ambiente medido, historia pasada, equipo, especie y tamaño. Excluye salud, carga interna, vulnerabilidad, tasa generadora, muerte, causas, IDs, escenario, semilla y parámetros ocultos. Se verifican etiquetas mediante eventos, no por ausencia de registros. Los sobrevivientes al final quedan censurados.

Las cuatro particiones contienen corridas completas y disjuntas. Se calibra con corridas reservadas y se eligen modelo y umbral en validación antes de abrir test. F2 prioriza recall. Los intervalos por corrida reflejan incertidumbre Monte Carlo, no certeza biológica. Las alertas agregadas suman riesgos para estimar muertes esperadas sin asumir independencia.

Las frecuencias deliberadas de escenarios no representan una empresa. Las probabilidades calibradas solo describen esa mezcla sintética. Dos peces observacionalmente iguales pueden recibir igual riesgo y morir de forma distinta por factores ocultos y azar. No es posible resolver esa incertidumbre mediante más algoritmos.
