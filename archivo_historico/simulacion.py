"""
Motor de simulación de mortalidad acuícola con eventos estocásticos.

Cada pez comienza con 100 puntos de salud. En cada tick (1 hora), se evalúan
eventos aleatorios que pueden afectar a los peces: enfermedades, ataques,
asfixia, envenenamiento, shock térmico, parásitos, etc.

La probabilidad de cada evento depende de las condiciones del agua, la densidad,
la especie y la suerte. Los peces mueren por causas diversas, no por un daño
lineal predecible.
"""

from database import conectar_bd
import random


# ============================================================
# PARÁMETROS DEL AMBIENTE
# ============================================================

# El filtro no es 100% efectivo
EFICACIA_FILTRO = 0.8

# El alimento no consumido genera amoniaco extra
FACTOR_ALIMENTO_NO_CONSUMIDO = 1.2


# ============================================================
# SISTEMA DE EVENTOS ESTOCÁSTICOS
# ============================================================
# Cada evento tiene:
# - nombre: descripción del evento
# - probabilidad_base: probabilidad por pez por hora (0.0 a 1.0)
# - multiplicadores: función que ajusta la probabilidad según condiciones
# - efecto: función que aplica el efecto al pez (daño o muerte)
# - es_colectivo: si afecta a múltiples peces a la vez

def explicar_condiciones(agua, esp, equipos, densidad_kg_m3):
    """
    Genera una lista de explicaciones sobre por qué las condiciones del tanque
    son peligrosas para los peces. Cada explicación indica qué falta o qué está mal.
    
    Args:
        agua: dict con ph, temperatura_c, oxigeno_mg_l, amoniaco_mg_l, volumen_l
        esp: dict con rangos de la especie
        equipos: dict con filtro_remocion_mg_h, aireacion_mg_h
        densidad_kg_m3: densidad de biomasa
    
    Returns:
        lista de strings con explicaciones de los problemas detectados
    """
    problemas = []
    
    ph = agua["ph"]
    temp = agua["temperatura_c"]
    ox = agua["oxigeno_mg_l"]
    am = agua["amoniaco_mg_l"]
    filtro = equipos.get("filtro_remocion_mg_h", 0)
    aireacion = equipos.get("aireacion_mg_h", 0)
    
    # --- pH ---
    if ph < esp["ph_min"]:
        desvio = esp["ph_min"] - ph
        severidad = "⚠️ Leve" if desvio < 1 else "🔴 Crítico" if desvio > 2 else "🟡 Moderado"
        problemas.append(f"🧪 pH muy bajo ({ph:.2f}, necesita {esp['ph_min']}-{esp['ph_max']}): {severidad}")
        if aireacion == 0:
            problemas.append(f"   → Sin aireación: el amoniaco acidifica el agua sin control")
        if filtro == 0:
            problemas.append(f"   → Sin filtro: no hay equipo para estabilizar el pH")
    elif ph > esp["ph_max"]:
        desvio = ph - esp["ph_max"]
        severidad = "⚠️ Leve" if desvio < 1 else "🔴 Crítico" if desvio > 2 else "🟡 Moderado"
        problemas.append(f"🧪 pH muy alto ({ph:.2f}, necesita {esp['ph_min']}-{esp['ph_max']}): {severidad}")
        if filtro == 0:
            problemas.append(f"   → Sin filtro: el pH se descontrola sin equipo de filtración")
    
    # --- Temperatura ---
    if temp < esp["temp_min"]:
        desvio = esp["temp_min"] - temp
        severidad = "⚠️ Leve" if desvio < 2 else "🔴 Crítico" if desvio > 5 else "🟡 Moderado"
        problemas.append(f"🌡️ Temperatura muy baja ({temp:.1f}°C, necesita {esp['temp_min']}-{esp['temp_max']}°C): {severidad}")
        if aireacion == 0:
            problemas.append(f"   → Sin aireación: no hay equipo para estabilizar la temperatura")
    elif temp > esp["temp_max"]:
        desvio = temp - esp["temp_max"]
        severidad = "⚠️ Leve" if desvio < 2 else "🔴 Crítico" if desvio > 5 else "🟡 Moderado"
        problemas.append(f"🌡️ Temperatura muy alta ({temp:.1f}°C, necesita {esp['temp_min']}-{esp['temp_max']}°C): {severidad}")
        if aireacion == 0:
            problemas.append(f"   → Sin aireación: la temperatura no se regula")
    
    # --- Oxígeno ---
    if ox < esp["oxigeno_min"]:
        desvio = esp["oxigeno_min"] - ox
        severidad = "⚠️ Leve" if desvio < 1 else "🔴 Crítico" if desvio > 3 else "🟡 Moderado"
        problemas.append(f"💨 Oxígeno muy bajo ({ox:.2f} mg/L, mínimo {esp['oxigeno_min']} mg/L): {severidad}")
        if aireacion == 0:
            problemas.append(f"   → Sin aireador: los peces no tienen suficiente oxígeno para respirar")
        else:
            problemas.append(f"   → Aireador insuficiente ({aireacion:.1f} mg/h): no compensa el consumo de {desvio:.1f} mg/L faltante")
        if densidad_kg_m3 > 10:
            problemas.append(f"   → Alta densidad ({densidad_kg_m3:.1f} kg/m³): muchos peces consumen más oxígeno")
    elif ox < esp["oxigeno_min"] * 1.15:
        problemas.append(f"💨 Oxígeno cerca del mínimo ({ox:.2f} mg/L, mínimo {esp['oxigeno_min']} mg/L): riesgo de asfixia")
        if aireacion == 0:
            problemas.append(f"   → Sin aireador: cualquier bajada más puede causar asfixia")
    
    # --- Amoniaco ---
    if am > esp["amoniaco_max"] and esp["amoniaco_max"] > 0:
        ratio = am / esp["amoniaco_max"]
        severidad = "⚠️ Leve" if ratio < 1.5 else "🔴 Crítico" if ratio > 3 else "🟡 Moderado"
        problemas.append(f"☠️ Amoniaco tóxico ({am:.4f} mg/L, máximo {esp['amoniaco_max']} mg/L): {severidad}")
        if filtro == 0:
            problemas.append(f"   → Sin filtro: el amoniaco se acumula sin control en el tanque")
        else:
            problemas.append(f"   → Filtro insuficiente ({filtro:.1f} mg/h): no remueve todo el amoniaco generado")
    elif am > esp["amoniaco_max"] * 0.5 and esp["amoniaco_max"] > 0:
        problemas.append(f"☠️ Amoniaco alto ({am:.4f} mg/L, máximo {esp['amoniaco_max']} mg/L): estrés crónico")
        if filtro == 0:
            problemas.append(f"   → Sin filtro: el amoniaco se acumula gradualmente")
    elif am > esp["amoniaco_max"] and esp["amoniaco_max"] == 0:
        problemas.append(f"☠️ Amoniaco presente ({am:.4f} mg/L): esta especie no tolera amoniaco")
        if filtro == 0:
            problemas.append(f"   → Sin filtro: cualquier amoniaco es letal para esta especie")
    
    # --- Densidad ---
    if densidad_kg_m3 > 15:
        problemas.append(f"📦 Sobrepoblación extrema ({densidad_kg_m3:.1f} kg/m³): los peces no tienen espacio")
    elif densidad_kg_m3 > 10:
        problemas.append(f"📦 Alta densidad ({densidad_kg_m3:.1f} kg/m³): estrés por hacinamiento")
    elif densidad_kg_m3 > 5:
        problemas.append(f"📦 Densidad moderada ({densidad_kg_m3:.1f} kg/m³): puede causar estrés a largo plazo")
    
    # --- Equipos faltantes ---
    if filtro == 0:
        problemas.append(f"🔧 Sin filtro: el tanque no tiene sistema de filtración")
    if aireacion == 0:
        problemas.append(f"🔧 Sin aireador: el tanque no tiene sistema de aireación")
    
    return problemas


def explicar_causa_muerte(causa_evento, agua, esp, equipos, densidad_kg_m3):
    """
    Genera una explicación detallada de por qué un pez murió, basada en la causa
    del evento y las condiciones del tanque.
    
    Args:
        causa_evento: string con el tipo de evento que mató al pez
        agua: dict con condiciones actuales
        esp: dict con rangos de la especie
        equipos: dict con equipos del tanque
        densidad_kg_m3: densidad de biomasa
    
    Returns:
        string con la explicación completa de la muerte
    """
    explicaciones = {
        "Enfermedad bacteriana": [
            "El pez contrajo una infección bacteriana.",
        ],
        "Parásitos": [
            "Parásitos atacaron al pez debilitando su sistema inmune.",
        ],
        "Asfixia súbita": [
            f"El oxígeno ({agua['oxigeno_mg_l']:.2f} mg/L) estaba por debajo del mínimo ({esp['oxigeno_min']} mg/L).",
            "El pez no pudo respirar y murió ahogado.",
        ],
        "Envenenamiento por amoniaco": [
            f"El amoniaco ({agua['amoniaco_mg_l']:.4f} mg/L) superó el nivel tóxico ({esp['amoniaco_max']} mg/L).",
            "El pez sufrió toxicidad aguda por el amoniaco acumulado.",
        ],
        "Shock térmico": [
            f"La temperatura ({agua['temperatura_c']:.1f}°C) estaba fuera del rango ({esp['temp_min']}-{esp['temp_max']}°C).",
            "El pez no pudo adaptarse al cambio de temperatura.",
        ],
        "Shock por pH": [
            f"El pH ({agua['ph']:.2f}) estaba fuera del rango ({esp['ph_min']}-{esp['ph_max']}).",
            "El pez sufrió shock químico por el pH extremo.",
        ],
        "Fallo orgánico": [
            "El pez estaba debilitado por estrés crónico prolongado.",
            "Sus órganos fallaron por la acumulación de daño.",
        ],
        "Muerte natural": [
            "El pez murió de causas naturales (vejez o genética).",
        ],
        "Agresión entre peces": [
            "Otro pez atacó a este pez.",
            "Las heridas causadas por la agresión fueron mortales.",
        ],
        "Depredación": [
            "Un pez depredador atacó y mató a este pez.",
        ],
        "Brote epidémico": [
            "Una enfermedad se propagó por todo el tanque.",
            "El pez fue infectado por el brote epidémico.",
        ],
    }
    
    base = explicaciones.get(causa_evento, [f"El pez murió por: {causa_evento}"])
    
    # Agregar contexto de las condiciones del tanque
    condiciones = explicar_condiciones(agua, esp, equipos, densidad_kg_m3)
    
    if condiciones:
        base.append("")
        base.append("🔍 Condiciones del tanque que contribuyeron:")
        for cond in condiciones[:5]:  # Máximo 5 condiciones para no saturar
            base.append(f"  • {cond}")
    
    return "\n".join(base)


def get_nivel_estres(agua, esp, densidad_kg_m3):
    """Calcula un nivel de estrés general (0.0 a 1.0+) basado en todas las condiciones."""
    estres = 0.0
    
    # Estrés por pH
    ph = agua["ph"]
    if ph < esp["ph_min"]:
        estres += (esp["ph_min"] - ph) / 2.0
    elif ph > esp["ph_max"]:
        estres += (ph - esp["ph_max"]) / 2.0
    else:
        # Cerca de los límites
        rango = esp["ph_max"] - esp["ph_min"]
        dist_min = ph - esp["ph_min"]
        dist_max = esp["ph_max"] - ph
        if dist_min < rango * 0.2:
            estres += 0.1 * (1 - dist_min / (rango * 0.2))
        if dist_max < rango * 0.2:
            estres += 0.1 * (1 - dist_max / (rango * 0.2))
    
    # Estrés por temperatura
    temp = agua["temperatura_c"]
    if temp < esp["temp_min"]:
        estres += (esp["temp_min"] - temp) / 3.0
    elif temp > esp["temp_max"]:
        estres += (temp - esp["temp_max"]) / 3.0
    
    # Estrés por oxígeno bajo
    ox = agua["oxigeno_mg_l"]
    if ox < esp["oxigeno_min"]:
        estres += (esp["oxigeno_min"] - ox) / 2.0
    elif ox < esp["oxigeno_min"] * 1.15:
        estres += 0.1
    
    # Estrés por amoniaco
    am = agua["amoniaco_mg_l"]
    if esp["amoniaco_max"] > 0:
        ratio = am / esp["amoniaco_max"]
        if ratio > 1.0:
            estres += (ratio - 1.0) * 2.0
        elif ratio > 0.5:
            estres += 0.15 * (ratio - 0.5) * 2.0
    
    # Estrés por densidad
    if densidad_kg_m3 > 10:
        estres += (densidad_kg_m3 - 10) / 10.0
    elif densidad_kg_m3 > 5:
        estres += 0.05 * (densidad_kg_m3 - 5) / 5.0
    
    return estres


def evaluar_eventos_peces(peces, agua, esp, densidad_kg_m3, num_especies_en_pecera=1):
    """
    Evalúa eventos estocásticos para cada pez en un tick.
    
    Args:
        peces: lista de dicts con "salud", "vivo", "id"
        agua: dict con ph, temperatura_c, oxigeno_mg_l, amoniaco_mg_l, volumen_l
        esp: dict con rangos de la especie
        densidad_kg_m3: densidad de biomasa
        num_especies_en_pecera: cuántas especies comparten la pecera
    
    Returns:
        lista de eventos ocurridos: [{"pez_id": X, "evento": "nombre", "daño": Y, "matio": Z}]
    """
    eventos_ocurridos = []
    estres = get_nivel_estres(agua, esp, densidad_kg_m3)
    
    # --- EVENTOS INDIVIDUALES ---
    for pez in peces:
        if not pez["vivo"]:
            continue
        
        pez_id = pez.get("id", 0)
        eventos_pez = []
        
        # 1. ENFERMEDAD BACTERIANA
        # Más probable con amoniaco alto y estrés
        prob_enfermedad = 0.002 * (1 + estres * 3.0)
        if agua["amoniaco_mg_l"] > esp["amoniaco_max"] * 0.5:
            prob_enfermedad *= 1.5
        if random.random() < prob_enfermedad:
            # El pez contrae una enfermedad: pierde salud progresivamente
            dano = random.uniform(5, 15)
            pez["salud"] -= dano
            eventos_pez.append({
                "tipo": "Enfermedad bacteriana",
                "daño": dano,
                "detalle": f"El pez contrajo una infección bacteriana (-{dano:.1f} salud)"
            })
        
        # 2. PARÁSITOS
        # Más probable con agua cálida y mala calidad
        prob_parasitos = 0.001 * (1 + estres * 2.0)
        if agua["temperatura_c"] > esp["temp_max"] * 0.9:
            prob_parasitos *= 1.3
        if random.random() < prob_parasitos:
            dano = random.uniform(3, 10)
            pez["salud"] -= dano
            eventos_pez.append({
                "tipo": "Parásitos",
                "daño": dano,
                "detalle": f"Parásitos atacaron al pez (-{dano:.1f} salud)"
            })
        
        # 3. ASFIXIA SÚBITA
        # Cuando el oxígeno está muy bajo, un pez puede ahogarse de golpe
        if agua["oxigeno_mg_l"] < esp["oxigeno_min"]:
            prob_asfixia = 0.05 * (esp["oxigeno_min"] - agua["oxigeno_mg_l"]) / esp["oxigeno_min"]
            if agua["oxigeno_mg_l"] < 2.0:
                prob_asfixia *= 2.0
            if random.random() < prob_asfixia:
                dano = random.uniform(20, 40)
                pez["salud"] -= dano
                eventos_pez.append({
                    "tipo": "Asfixia súbita",
                    "daño": dano,
                    "detalle": f"El pez tuvo un episodio de asfixia (-{dano:.1f} salud)"
                })
        
        # 4. ENVENENAMIENTO POR AMONIACO
        # Golpe agudo de toxicidad por picos de amoniaco
        if agua["amoniaco_mg_l"] > esp["amoniaco_max"]:
            ratio = agua["amoniaco_mg_l"] / esp["amoniaco_max"]
            prob_veneno = 0.03 * (ratio - 1.0)
            if random.random() < prob_veneno:
                dano = random.uniform(10, 25)
                pez["salud"] -= dano
                eventos_pez.append({
                    "tipo": "Envenenamiento por amoniaco",
                    "daño": dano,
                    "detalle": f"Toxicidad aguda por amoniaco (-{dano:.1f} salud)"
                })
        
        # 5. SHOCK TÉRMICO
        # Si la temperatura cambia bruscamente o está fuera de rango
        temp_desvio = 0
        if agua["temperatura_c"] < esp["temp_min"]:
            temp_desvio = esp["temp_min"] - agua["temperatura_c"]
        elif agua["temperatura_c"] > esp["temp_max"]:
            temp_desvio = agua["temperatura_c"] - esp["temp_max"]
        
        if temp_desvio > 0:
            prob_shock = 0.01 * (temp_desvio / 3.0)
            if random.random() < prob_shock:
                dano = random.uniform(8, 20)
                pez["salud"] -= dano
                eventos_pez.append({
                    "tipo": "Shock térmico",
                    "daño": dano,
                    "detalle": f"El pez sufrió shock por temperatura (-{dano:.1f} salud)"
                })
        
        # 6. SHOCK POR pH
        # pH fuera de rango puede causar shock químico
        ph_desvio = 0
        if agua["ph"] < esp["ph_min"]:
            ph_desvio = esp["ph_min"] - agua["ph"]
        elif agua["ph"] > esp["ph_max"]:
            ph_desvio = agua["ph"] - esp["ph_max"]
        
        if ph_desvio > 0:
            prob_shock_ph = 0.01 * (ph_desvio / 2.0)
            if random.random() < prob_shock_ph:
                dano = random.uniform(5, 15)
                pez["salud"] -= dano
                eventos_pez.append({
                    "tipo": "Shock por pH",
                    "daño": dano,
                    "detalle": f"Shock químico por pH extremo (-{dano:.1f} salud)"
                })
        
        # 7. FALLO ORGÁNICO POR ESTRÉS CRÓNICO
        # Peces debilitados pueden tener fallos orgánicos
        if pez["salud"] < 50:
            prob_fallo = 0.02 * (1 - pez["salud"] / 100) * (1 + estres)
            if random.random() < prob_fallo:
                dano = random.uniform(10, 30)
                pez["salud"] -= dano
                eventos_pez.append({
                    "tipo": "Fallo orgánico",
                    "daño": dano,
                    "detalle": f"Fallo orgánico por estrés crónico (-{dano:.1f} salud)"
                })
        
        # 8. MUERTE NATURAL (muy rara, pero puede pasar)
        prob_natural = 0.0005 * (1 + estres * 0.5)
        if random.random() < prob_natural:
            pez["salud"] = 0
            eventos_pez.append({
                "tipo": "Muerte natural",
                "daño": pez["salud"] + 100,
                "detalle": "El pez murió de causas naturales"
            })
        
        # Verificar si el pez murió
        if pez["salud"] <= 0 and pez["vivo"]:
            pez["salud"] = 0
            pez["vivo"] = False
            if eventos_pez:
                pez["causa_muerte"] = eventos_pez[-1]["tipo"]
            else:
                pez["causa_muerte"] = "Causas desconocidas"
        
        # Registrar eventos
        for ev in eventos_pez:
            eventos_ocurridos.append({
                "pez_id": pez_id,
                "evento": ev["tipo"],
                "daño": ev["daño"],
                "detalle": ev["detalle"],
                "matio": "muerto" if not pez["vivo"] else "dañado"
            })
    
    # --- EVENTOS COLECTIVOS ---
    
    # 9. AGRESIÓN ENTRE PECES
    # Más probable con alta densidad y múltiples especies
    if densidad_kg_m3 > 5 or num_especies_en_pecera > 1:
        prob_agresion = 0.01 * (densidad_kg_m3 / 10.0)
        if num_especies_en_pecera > 1:
            prob_agresion *= 2.0
        if random.random() < prob_agresion:
            # Un pez ataca a otro
            peces_vivos = [p for p in peces if p["vivo"]]
            if len(peces_vivos) >= 2:
                victima = random.choice(peces_vivos)
                dano = random.uniform(5, 20)
                victima["salud"] -= dano
                eventos_ocurridos.append({
                    "pez_id": victima.get("id", 0),
                    "evento": "Agresión entre peces",
                    "daño": dano,
                    "detalle": f"Un pez fue atacado por otro (-{dano:.1f} salud)",
                    "matio": "muerto" if not victima["vivo"] else "dañado"
                })
                if victima["salud"] <= 0 and victima["vivo"]:
                    victima["salud"] = 0
                    victima["vivo"] = False
                    victima["causa_muerte"] = "Agresión entre peces"
    
    # 10. DEPENDACIÓN (si hay especies depredadoras)
    # Simulado: si hay múltiples especies, una puede intentar comer a otra
    if num_especies_en_pecera > 1 and random.random() < 0.005:
        peces_vivos = [p for p in peces if p["vivo"]]
        if peces_vivos:
            victima = random.choice(peces_vivos)
            dano = random.uniform(15, 35)
            victima["salud"] -= dano
            eventos_ocurridos.append({
                "pez_id": victima.get("id", 0),
                "evento": "Depredación",
                "daño": dano,
                "detalle": f"Un pez fue atacado por un depredador (-{dano:.1f} salud)",
                "matio": "muerto" if not victima["vivo"] else "dañado"
            })
            if victima["salud"] <= 0 and victima["vivo"]:
                victima["salud"] = 0
                victima["vivo"] = False
                victima["causa_muerte"] = "Depredación"
    
    # 11. BROTE DE ENFERMEDAD (afecta a múltiples peces)
    # Epidemia que se propaga
    prob_brote = 0.003 * (1 + estres * 2.0)
    if densidad_kg_m3 > 10:
        prob_brote *= 1.5
    if random.random() < prob_brote:
        peces_vivos = [p for p in peces if p["vivo"]]
        # Infecta a un porcentaje de los peces
        num_infectados = max(1, int(len(peces_vivos) * random.uniform(0.2, 0.5)))
        infectados = random.sample(peces_vivos, min(num_infectados, len(peces_vivos)))
        for victima in infectados:
            dano = random.uniform(8, 20)
            victima["salud"] -= dano
            eventos_ocurridos.append({
                "pez_id": victima.get("id", 0),
                "evento": "Brote epidémico",
                "daño": dano,
                "detalle": f"Brote de enfermedad afectó al pez (-{dano:.1f} salud)",
                "matio": "muerto" if not victima["vivo"] else "dañado"
            })
            if victima["salud"] <= 0 and victima["vivo"]:
                victima["salud"] = 0
                victima["vivo"] = False
                victima["causa_muerte"] = "Brote epidémico"
    
    return eventos_ocurridos


def consultar_datos_iniciales():
    """Carga todos los datos necesarios desde PostgreSQL."""
    with conectar_bd() as conn:
        with conn.cursor() as cur:
            # Pecerias
            cur.execute("SELECT id_pecera, nombre_pecera, volumen_l FROM peceras ORDER BY id_pecera")
            peceras = {row["id_pecera"]: {"nombre": row["nombre_pecera"], "volumen_l": float(row["volumen_l"])}
                       for row in cur.fetchall()}

            # Estado del agua
            cur.execute("SELECT id_pecera, ph, temperatura_c, oxigeno_mg_l, amoniaco_mg_l FROM estado_pecera")
            estado = {}
            for row in cur.fetchall():
                estado[row["id_pecera"]] = {
                    "ph": float(row["ph"]),
                    "temperatura_c": float(row["temperatura_c"]),
                    "oxigeno_mg_l": float(row["oxigeno_mg_l"]),
                    "amoniaco_mg_l": float(row["amoniaco_mg_l"]),
                }

            # Equipos
            cur.execute("SELECT id_pecera, filtro_remocion_mg_h, aireacion_mg_h FROM equipos_pecera")
            equipos = {}
            for row in cur.fetchall():
                equipos[row["id_pecera"]] = {
                    "filtro_remocion_mg_h": float(row["filtro_remocion_mg_h"]),
                    "aireacion_mg_h": float(row["aireacion_mg_h"]),
                }

            # Especies
            cur.execute("""
                SELECT id_especie, nombre_comun, ph_min, ph_max, temp_min_c, temp_max_c,
                       oxigeno_min_mg_l, amoniaco_max_mg_l, consumo_o2_mg_kg_h
                FROM especies
            """)
            especies = {}
            for row in cur.fetchall():
                especies[row["id_especie"]] = {
                    "nombre": row["nombre_comun"],
                    "ph_min": float(row["ph_min"]),
                    "ph_max": float(row["ph_max"]),
                    "temp_min": float(row["temp_min_c"]),
                    "temp_max": float(row["temp_max_c"]),
                    "oxigeno_min": float(row["oxigeno_min_mg_l"]),
                    "amoniaco_max": float(row["amoniaco_max_mg_l"]),
                    "consumo_o2": float(row["consumo_o2_mg_kg_h"]),
                }

            # Poblaciones (pecera_especie)
            cur.execute("""
                SELECT pe.id_pecera, pe.id_especie, pe.cantidad_peces, pe.peso_promedio_g,
                       pe.alimento_g_por_hora, a.amoniaco_mg_por_g
                FROM pecera_especie pe
                JOIN alimentos a ON a.id_alimento = pe.id_alimento
            """)
            poblaciones = []
            for row in cur.fetchall():
                poblaciones.append({
                    "id_pecera": row["id_pecera"],
                    "id_especie": row["id_especie"],
                    "cantidad": int(row["cantidad_peces"]),
                    "peso_g": float(row["peso_promedio_g"]),
                    "alimento_g_h": float(row["alimento_g_por_hora"]),
                    "amoniaco_mg_por_g": float(row["amoniaco_mg_por_g"]),
                })

    return peceras, estado, equipos, especies, poblaciones


# ============================================================
# FUNCIONES DE COMPATIBILIDAD (para simulacion_visual.py)
# ============================================================
# Estas funciones se mantienen para compatibilidad con la interfaz visual,
# pero el motor principal usa eventos estocásticos.

def calcular_dano_ph(valor_actual, ph_min, ph_max):
    """Calcula un índice de riesgo por pH (no daño directo)."""
    if ph_min <= valor_actual <= ph_max:
        return 0.0
    if valor_actual < ph_min:
        return ph_min - valor_actual
    return valor_actual - ph_max


def calcular_dano_temp(valor_actual, temp_min, temp_max):
    """Calcula un índice de riesgo por temperatura."""
    if temp_min <= valor_actual <= temp_max:
        return 0.0
    if valor_actual < temp_min:
        return temp_min - valor_actual
    return valor_actual - temp_max


def calcular_dano_oxigeno(valor_actual, oxigeno_min):
    """Calcula un índice de riesgo por oxígeno bajo."""
    if valor_actual >= oxigeno_min:
        return 0.0
    return oxigeno_min - valor_actual


def calcular_dano_amoniaco(valor_actual, amoniaco_max):
    """Calcula un índice de riesgo por amoniaco alto."""
    if valor_actual <= amoniaco_max:
        return 0.0
    return valor_actual - amoniaco_max


def calcular_dano_densidad(biomasa_kg, volumen_l):
    """Calcula un índice de riesgo por densidad."""
    if volumen_l <= 0:
        return 3.0
    densidad_kg_m3 = (biomasa_kg / volumen_l) * 1000
    if densidad_kg_m3 <= 5:
        return 0.0
    return (densidad_kg_m3 - 5) / 5.0


# Compatibilidad: DAÑO_FATIGA_CONFINAMIENTO se usa en simulacion_visual.py
DAÑO_FATIGA_CONFINAMIENTO = 0.0


def evolucionar_agua(estado_pecera, equipos_pecera, poblaciones_pecera, ph_ideal=None, temp_ideal=None):
    """
    Evoluciona las condiciones del agua en 1 hora (similar a simular_tick()).
    Calcula amoniaco generado, oxígeno consumido, y variación de pH y temperatura.
    
    Los equipos (filtro y aireación) ayudan a estabilizar el agua hacia los valores ideales.
    Si no hay equipos, las condiciones se desvían más con el tiempo.
    
    ph_ideal: valor objetivo de pH hacia donde tiende el agua (por defecto 7.0)
    temp_ideal: valor objetivo de temperatura (por defecto 25.0)
    """
    ph = estado_pecera["ph"]
    temp = estado_pecera["temperatura_c"]
    oxigeno = estado_pecera["oxigeno_mg_l"]
    amoniaco = estado_pecera["amoniaco_mg_l"]
    volumen = estado_pecera.get("volumen_l", 1000)

    filtro = equipos_pecera.get("filtro_remocion_mg_h", 0)
    aireacion = equipos_pecera.get("aireacion_mg_h", 0)

    # Valores ideales hacia donde tiende el agua
    if ph_ideal is None:
        ph_ideal = 7.0
    if temp_ideal is None:
        temp_ideal = 25.0

    # Calcular amoniaco generado y O2 consumido por todas las especies en esta pecera
    nh3_total = 0.0
    o2_total = 0.0
    biomasa_total = 0.0

    for pop in poblaciones_pecera:
        vivos = pop["vivos"]
        if vivos <= 0:
            continue
        peso_kg = pop["peso_g"] / 1000.0 * vivos
        biomasa_total += peso_kg
        # Amoniaco generado por el alimento (con factor de alimento no consumido)
        nh3_total += pop["alimento_g_h"] * pop["amoniaco_mg_por_g"] * FACTOR_ALIMENTO_NO_CONSUMIDO
        # Oxígeno consumido
        o2_total += vivos * (pop["peso_g"] / 1000.0) * pop["consumo_o2"]

    # Actualizar amoniaco: el filtro solo es parcialmente efectivo
    # El filtro remueve un porcentaje del amoniaco generado, no del total
    nh3_neto = nh3_total - (nh3_total * EFICACIA_FILTRO * min(filtro / max(nh3_total, 0.01), 1.0))
    amoniaco += nh3_neto / volumen
    amoniaco = max(0, amoniaco)

    # Actualizar oxígeno
    oxigeno += (aireacion - o2_total) / volumen
    oxigeno = max(0, min(9.0, oxigeno))

    # --- Variación del pH ---
    # El pH tiende a desviarse naturalmente (acidificación por amoniaco)
    # El amoniaco alto acidifica el agua (baja el pH)
    ph_desviacion_amoniaco = -0.005 * amoniaco  # El amoniaco baja el pH
    
    # Variación aleatoria natural (muy pequeña por hora)
    import random
    ph_ruido = random.uniform(-0.02, 0.02)
    
    # El filtro ayuda a estabilizar el pH hacia el valor ideal
    if filtro > 0:
        # Con filtro: el pH se recupera hacia el ideal (velocidad proporcional al filtro)
        ph_recuperacion = (ph_ideal - ph) * min(filtro / volumen * 0.01, 0.05)
    else:
        # Sin filtro: el pH se desvía más del ideal
        ph_recuperacion = 0.0
    
    ph += ph_desviacion_amoniaco + ph_ruido + ph_recuperacion
    ph = max(4.0, min(10.0, ph))  # Límites biológicos

    # --- Variación de la temperatura ---
    # La temperatura fluctúa ligeramente (simula cambios ambientales)
    temp_ruido = random.uniform(-0.1, 0.1)
    
    # La biomasa genera calor (muy leve)
    temp_biomasa = biomasa_total * 0.001
    
    # Sin equipo de control térmico, la temperatura se desvía del ideal
    # Con equipos, se mantiene más estable
    if aireacion > 0:
        # La aireación ayuda a mantener la temperatura estable
        temp_estabilizacion = (temp_ideal - temp) * min(aireacion / volumen * 0.005, 0.03)
    else:
        temp_estabilizacion = 0.0
    
    temp += temp_ruido + temp_biomasa + temp_estabilizacion
    temp = max(10.0, min(40.0, temp))  # Límites biológicos

    return {
        "ph": ph,
        "temperatura_c": temp,
        "oxigeno_mg_l": oxigeno,
        "amoniaco_mg_l": amoniaco,
        "volumen_l": volumen,
        "biomasa_kg": biomasa_total,
    }


def simular(num_horas=48, mostrar_progreso=True):
    """
    Ejecuta la simulación con eventos estocásticos por el número de horas indicado.
    Cada pez se simula individualmente con eventos aleatorios.
    Retorna los resultados por pecera y especie.
    """
    peceras, estado, equipos, especies, poblaciones = consultar_datos_iniciales()

    # Preparar peces individuales por pecera
    # Cada pecera tiene una lista de peces individuales
    peces_por_pecera = {}  # id_pecera -> lista de peces
    poblacion_sim = {}  # id_pecera -> lista de pops para evolucionar_agua
    
    pez_global_id = 0
    for pop in poblaciones:
        pid = pop["id_pecera"]
        if pid not in peces_por_pecera:
            peces_por_pecera[pid] = []
            poblacion_sim[pid] = []
        
        esp_data = especies[pop["id_especie"]]
        for _ in range(pop["cantidad"]):
            pez_global_id += 1
            peces_por_pecera[pid].append({
                "id": pez_global_id,
                "id_especie": pop["id_especie"],
                "salud": 100.0,
                "vivo": True,
                "causa_muerte": None,
            })
        
        poblacion_sim[pid].append({
            "id_especie": pop["id_especie"],
            "cantidad": pop["cantidad"],
            "vivos": pop["cantidad"],
            "muertos": 0,
            "peso_g": pop["peso_g"],
            "alimento_g_h": pop["alimento_g_h"],
            "amoniaco_mg_por_g": pop["amoniaco_mg_por_g"],
            "consumo_o2": esp_data["consumo_o2"],
        })

    # Estado inicial del agua por pecera
    agua = {}
    for pid in peces_por_pecera:
        agua[pid] = {
            "ph": estado[pid]["ph"],
            "temperatura_c": estado[pid]["temperatura_c"],
            "oxigeno_mg_l": estado[pid]["oxigeno_mg_l"],
            "amoniaco_mg_l": estado[pid]["amoniaco_mg_l"],
            "volumen_l": peceras[pid]["volumen_l"],
        }

    # Historial
    historial = []
    eventos_totales = []  # Todos los eventos ocurridos

    if mostrar_progreso:
        print("=" * 80)
        print("SIMULACIÓN DE MORTALIDAD ACUÍCOLA - EVENTOS ESTOCÁSTICOS")
        print("=" * 80)
        print(f"Duración: {num_horas} horas")
        print("-" * 80)

    for hora in range(1, num_horas + 1):
        for pid in peces_por_pecera:
            eq = equipos.get(pid, {"filtro_remocion_mg_h": 0, "aireacion_mg_h": 0})
            eq_data = {"filtro_remocion_mg_h": eq["filtro_remocion_mg_h"],
                       "aireacion_mg_h": eq["aireacion_mg_h"]}

            # Actualizar vivos en poblacion_sim
            peces = peces_por_pecera[pid]
            num_vivos = sum(1 for p in peces if p["vivo"])
            for ps in poblacion_sim[pid]:
                ps["vivos"] = sum(1 for p in peces if p["vivo"] and p["id_especie"] == ps["id_especie"])

            # Evolucionar agua
            agua[pid] = evolucionar_agua(agua[pid], eq_data, poblacion_sim[pid])
            
            biomasa = agua[pid].get("biomasa_kg", 0)
            volumen = agua[pid]["volumen_l"]
            densidad = (biomasa / volumen) * 1000 if volumen > 0 else 0
            
            num_especies = len(poblacion_sim[pid])

            # Evaluar eventos estocásticos para cada especie en esta pecera
            for ps in poblacion_sim[pid]:
                esp = especies[ps["id_especie"]]
                # Filtrar peces de esta especie
                peces_especie = [p for p in peces if p["id_especie"] == ps["id_especie"]]
                
                eventos = evaluar_eventos_peces(peces_especie, agua[pid], esp, densidad, num_especies)
                
                # Actualizar conteo de muertos
                peces_especie_vivos = sum(1 for p in peces_especie if p["vivo"])
                ps["muertos"] = len(peces_especie) - peces_especie_vivos
                
                for ev in eventos:
                    eventos_totales.append({
                        "hora": hora,
                        "pecera": peceras[pid]["nombre"],
                        **ev
                    })
                
                # Mostrar eventos de muerte en consola
                if mostrar_progreso:
                    for ev in eventos:
                        if ev["matio"] == "muerto":
                            print(f"  [Hora {hora}] {peceras[pid]['nombre']}: "
                                  f"Pez #{ev['pez_id']} murió por {ev['evento']}")

        # Registrar historial cada 6 horas o al final
        if hora % 6 == 0 or hora == num_horas:
            registro = {"hora": hora}
            for pid in peces_por_pecera:
                registro[pid] = {
                    "pecera": peceras[pid]["nombre"],
                    "oxigeno": round(agua[pid]["oxigeno_mg_l"], 3),
                    "amoniaco": round(agua[pid]["amoniaco_mg_l"], 4),
                    "ph": round(agua[pid]["ph"], 2),
                    "temp": round(agua[pid]["temperatura_c"], 1),
                    "especies": [],
                }
                for ps in poblacion_sim[pid]:
                    esp = especies[ps["id_especie"]]
                    peces_especie = [p for p in peces_por_pecera[pid] if p["id_especie"] == ps["id_especie"]]
                    vivos = sum(1 for p in peces_especie if p["vivo"])
                    salud_prom = sum(p["salud"] for p in peces_especie if p["vivo"]) / max(vivos, 1)
                    registro[pid]["especies"].append({
                        "especie": esp["nombre"],
                        "vivos": vivos,
                        "muertos": len(peces_especie) - vivos,
                        "salud_promedio": round(salud_prom, 1),
                    })
            historial.append(registro)

    # Imprimir resultados
    if mostrar_progreso:
        print("\n" + "=" * 80)
        print("RESULTADOS FINALES")
        print("=" * 80)

        for pid in peces_por_pecera:
            print(f"\n--- {peceras[pid]['nombre']} ---")
            for ps in poblacion_sim[pid]:
                esp = especies[ps["id_especie"]]
                peces_especie = [p for p in peces_por_pecera[pid] if p["id_especie"] == ps["id_especie"]]
                vivos = sum(1 for p in peces_especie if p["vivo"])
                muertos = len(peces_especie) - vivos
                pct = (muertos / len(peces_especie) * 100) if peces_especie else 0
                print(f"  {esp['nombre']}: {vivos} vivos / {len(peces_especie)} iniciales "
                      f"({muertos} muertos, {pct:.1f}%)")
                
                # Causas de muerte
                if muertos > 0:
                    causas = {}
                    for p in peces_especie:
                        if not p["vivo"] and p["causa_muerte"]:
                            causas[p["causa_muerte"]] = causas.get(p["causa_muerte"], 0) + 1
                    print(f"    Causas de muerte:")
                    for causa, count in sorted(causas.items(), key=lambda x: -x[1]):
                        print(f"      - {causa}: {count} peces")

        # Resumen de eventos
        print("\n" + "=" * 80)
        print("RESUMEN DE EVENTOS")
        print("=" * 80)
        causas_resumen = {}
        for ev in eventos_totales:
            causa = ev["evento"]
            if causa not in causas_resumen:
                causas_resumen[causa] = {"dañados": 0, "muertos": 0}
            if ev["matio"] == "muerto":
                causas_resumen[causa]["muertos"] += 1
            else:
                causas_resumen[causa]["dañados"] += 1
        
        for causa, stats in sorted(causas_resumen.items(), key=lambda x: -(x[1]["muertos"] + x[1]["dañados"])):
            print(f"  {causa}: {stats['dañados']} eventos de daño, {stats['muertos']} muertes")

        # Historial resumido
        print("\n" + "=" * 80)
        print("HISTORIAL (cada 6 horas)")
        print("=" * 80)
        for reg in historial:
            print(f"\nHora {reg['hora']}:")
            for pid in reg:
                if pid == "hora":
                    continue
                info = reg[pid]
                print(f"  {info['pecera']} (O2: {info['oxigeno']}, NH3: {info['amoniaco']}, "
                      f"pH: {info['ph']}, Temp: {info['temp']}°C)")
                for esp_info in info["especies"]:
                    print(f"    -> {esp_info['especie']}: {esp_info['vivos']} vivos, "
                          f"{esp_info['muertos']} muertos, salud prom: {esp_info['salud_promedio']:.1f}")

    return peces_por_pecera, poblacion_sim, peceras, especies, historial, eventos_totales


if __name__ == "__main__":
    simular(num_horas=48)
