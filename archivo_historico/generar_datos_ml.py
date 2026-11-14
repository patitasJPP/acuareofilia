"""
Generador masivo de datos en crudo para Machine Learning.

Ejecuta la simulación de mortalidad acuícola sin interfaz visual a máxima velocidad,
registrando cada pez en cada hora de simulación. Cuando un pez muere, se repone
inmediatamente para mantener el ciclo infinito de datos.

Exporta un MEGA Excel con 50,000+ filas y 50+ columnas para entrenar
modelos de predicción de muerte de peces.
"""

from database import conectar_bd
import random
import os
import time

# ============================================================
# Importar funciones del motor de simulación
# ============================================================
from simulacion import (
    consultar_datos_iniciales,
    evolucionar_agua,
    evaluar_eventos_peces,
    get_nivel_estres,
    EFICACIA_FILTRO,
    FACTOR_ALIMENTO_NO_CONSUMIDO,
)

# ============================================================
# PARÁMETROS
# ============================================================
FILAS_OBJETIVO = 55000  # Meta mínima de filas (50k+)
HORAS_MAX = 5000        # Límite máximo de horas


def consultar_datos():
    """Carga datos desde PostgreSQL (misma lógica que consultar_datos_iniciales)."""
    return consultar_datos_iniciales()


def exportar_excel(filas, ruta):
    """Exporta las filas a Excel usando openpyxl (optimizado para grandes datasets)."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        print("ERROR: Instala openpyxl primero: pip install openpyxl")
        return False

    wb = Workbook()
    ws = wb.active
    ws.title = "MegaDatosML"

    # Columnas
    columnas = list(filas[0].keys()) if filas else []
    
    # Header con estilo
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_align = Alignment(horizontal="center")

    for col_idx, col_name in enumerate(columnas, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # Datos - usar append para mejor rendimiento
    for fila in filas:
        fila_vals = [fila.get(col, "") for col in columnas]
        ws.append(fila_vals)

    # Auto-adjust column width
    for col_idx, col_name in enumerate(columnas, 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = max(len(str(col_name)) + 2, 12)

    wb.save(ruta)
    return True


def generar_datos_ml():
    """Genera datos masivos de simulación para ML y exporta a un solo mega Excel."""
    random.seed(42)
    inicio = time.time()
    print("=" * 70)
    print("GENERADOR MASIVO DE DATOS PARA MACHINE LEARNING")
    print("=" * 70)
    print(f"Objetivo: {FILAS_OBJETIVO:,} filas mínimo")
    print(f"Horas máximo: {HORAS_MAX}")
    print()

    # Cargar datos
    peceras, estado, equipos, especies, poblaciones = consultar_datos()
    print(f"Peceras cargadas: {len(peceras)}")
    print(f"Especies cargadas: {len(especies)}")
    print(f"Poblaciones cargadas: {len(poblaciones)}")
    print()

    # Preparar peces individuales por pecera
    peces_por_pecera = {}
    poblacion_sim = {}
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
                "danos_acumulados": 0.0,
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

    # Estado inicial del agua
    agua = {}
    for pid in peces_por_pecera:
        agua[pid] = {
            "ph": estado[pid]["ph"],
            "temperatura_c": estado[pid]["temperatura_c"],
            "oxigeno_mg_l": estado[pid]["oxigeno_mg_l"],
            "amoniaco_mg_l": estado[pid]["amoniaco_mg_l"],
            "volumen_l": peceras[pid]["volumen_l"],
        }

    # Contadores
    todas_filas = []
    total_muertes = 0
    respawn_count = 0

    print("Iniciando simulación...")
    print("-" * 70)

    for hora in range(1, HORAS_MAX + 1):
        for pid in peces_por_pecera:
            eq = equipos.get(pid, {"filtro_remocion_mg_h": 0, "aireacion_mg_h": 0})
            eq_data = {
                "filtro_remocion_mg_h": eq["filtro_remocion_mg_h"],
                "aireacion_mg_h": eq["aireacion_mg_h"],
            }

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

            # Evaluar eventos por especie
            for ps in poblacion_sim[pid]:
                esp = especies[ps["id_especie"]]
                peces_especie = [p for p in peces if p["id_especie"] == ps["id_especie"]]

                eventos = evaluar_eventos_peces(peces_especie, agua[pid], esp, densidad, num_especies)

                # Actualizar muertos
                peces_especie_vivos = sum(1 for p in peces_especie if p["vivo"])
                ps["muertos"] = len(peces_especie) - peces_especie_vivos

            # Registrar datos de CADA pez vivo en esta hora
            for pez in peces:
                if not pez["vivo"]:
                    continue

                esp_id = pez["id_especie"]
                esp = especies[esp_id]
                a = agua[pid]
                estres = get_nivel_estres(a, esp, densidad)

                # Calcular daños individuales
                dano_ph = 0.0
                if a["ph"] < esp["ph_min"]:
                    dano_ph = esp["ph_min"] - a["ph"]
                elif a["ph"] > esp["ph_max"]:
                    dano_ph = a["ph"] - esp["ph_max"]

                dano_temp = 0.0
                if a["temperatura_c"] < esp["temp_min"]:
                    dano_temp = esp["temp_min"] - a["temperatura_c"]
                elif a["temperatura_c"] > esp["temp_max"]:
                    dano_temp = a["temperatura_c"] - esp["temp_max"]

                dano_ox = 0.0
                if a["oxigeno_mg_l"] < esp["oxigeno_min"]:
                    dano_ox = esp["oxigeno_min"] - a["oxigeno_mg_l"]

                dano_nh3 = 0.0
                if a["amoniaco_mg_l"] > esp["amoniaco_max"]:
                    dano_nh3 = a["amoniaco_mg_l"] - esp["amoniaco_max"]

                # Densidad daño
                dano_dens = 0.0
                if densidad > 5:
                    dano_dens = (densidad - 5) / 5.0

                dano_total = dano_ph + dano_temp + dano_ox + dano_nh3 + dano_dens

                # Riesgo de muerte
                riesgo_muerte = max(0, 100 - pez["salud"]) / 100.0

                # Flags binarios para ML
                ph_critico = 1 if (a["ph"] < esp["ph_min"] or a["ph"] > esp["ph_max"]) else 0
                temp_critico = 1 if (a["temperatura_c"] < esp["temp_min"] or a["temperatura_c"] > esp["temp_max"]) else 0
                ox_critico = 1 if a["oxigeno_mg_l"] < esp["oxigeno_min"] else 0
                nh3_critico = 1 if a["amoniaco_mg_l"] > esp["amoniaco_max"] else 0
                sobrepoblacion = 1 if densidad > 10 else 0

                # Nivel de estrés categórico
                if dano_total < 5:
                    estres_cat = "Bajo"
                elif dano_total < 15:
                    estres_cat = "Moderado"
                elif dano_total < 30:
                    estres_cat = "Alto"
                else:
                    estres_cat = "Critico"

                # Causa de riesgo principal
                danos_list = [
                    ("Envenenamiento_amoniaco", dano_nh3),
                    ("Falta_oxigeno", dano_ox),
                    ("pH_fuera_rango", dano_ph),
                    ("Temperatura_inadecuada", dano_temp),
                    ("Sobrepoblacion", dano_dens),
                ]
                danos_list.sort(key=lambda x: x[1], reverse=True)
                causa_riesgo = danos_list[0][0] if danos_list[0][1] > 0 else "Ninguna"

                # Biomasa y peso
                peso_pez_g = 0
                for ps in poblacion_sim[pid]:
                    if ps["id_especie"] == esp_id:
                        peso_pez_g = ps["peso_g"]
                        break

                fila = {
                    # Identificación
                    "hora_sim": hora,
                    "pecera_id": pid,
                    "pecera_nombre": peceras[pid]["nombre"],
                    "especie_id": esp_id,
                    "especie_nombre": esp["nombre"],
                    "pez_id": pez["id"],
                    # Estado del pez
                    "salud": round(pez["salud"], 2),
                    "vivo": 1,
                    "danos_acumulados": round(pez["danos_acumulados"], 2),
                    "peso_gramos": peso_pez_g,
                    # Condiciones del agua
                    "ph": round(a["ph"], 3),
                    "temperatura": round(a["temperatura_c"], 2),
                    "oxigeno": round(a["oxigeno_mg_l"], 3),
                    "amoniaco": round(a["amoniaco_mg_l"], 4),
                    "volumen_l": volumen,
                    # Rangos óptimos de la especie
                    "ph_min": esp["ph_min"],
                    "ph_max": esp["ph_max"],
                    "temp_min": esp["temp_min"],
                    "temp_max": esp["temp_max"],
                    "oxigeno_min": esp["oxigeno_min"],
                    "amoniaco_max": esp["amoniaco_max"],
                    "consumo_o2": esp["consumo_o2"],
                    # Desvíos de los rangos óptimos
                    "ph_desvio": round(dano_ph, 3),
                    "temp_desvio": round(dano_temp, 3),
                    "ox_desvio": round(dano_ox, 3),
                    "nh3_desvio": round(dano_nh3, 4),
                    # Daños calculados
                    "dano_ph": round(dano_ph, 3),
                    "dano_temp": round(dano_temp, 3),
                    "dano_oxigeno": round(dano_ox, 3),
                    "dano_amoniaco": round(dano_nh3, 4),
                    "dano_densidad": round(dano_dens, 3),
                    "dano_total": round(dano_total, 3),
                    # Flags críticos
                    "ph_critico": ph_critico,
                    "temp_critico": temp_critico,
                    "ox_critico": ox_critico,
                    "nh3_critico": nh3_critico,
                    "sobrepoblacion": sobrepoblacion,
                    "punto_critico": 1 if dano_total > 20 else 0,
                    # Equipos
                    "filtro_mg_h": eq_data["filtro_remocion_mg_h"],
                    "aireacion_mg_h": eq_data["aireacion_mg_h"],
                    "tiene_filtro": 1 if eq_data["filtro_remocion_mg_h"] > 0 else 0,
                    "tiene_aireacion": 1 if eq_data["aireacion_mg_h"] > 0 else 0,
                    # Densidad y biomasa
                    "densidad_kg_m3": round(densidad, 2),
                    "biomasa_kg": round(biomasa, 4),
                    # Estrés y riesgo
                    "nivel_estres": round(estres, 3),
                    "nivel_estres_cat": estres_cat,
                    "riesgo_muerte": round(riesgo_muerte, 3),
                    # Población
                    "num_vivos_pecera": num_vivos,
                    "num_especies_pecera": num_especies,
                    "causa_riesgo_principal": causa_riesgo,
                    # Variable objetivo
                    "murio": 0,  # Este pez está vivo en esta hora
                }
                todas_filas.append(fila)

            # Registrar muertes y reponer peces
            for ps in poblacion_sim[pid]:
                esp = especies[ps["id_especie"]]
                peces_especie = [p for p in peces if p["id_especie"] == ps["id_especie"]]

                for pez in peces_especie:
                    if not pez["vivo"] and pez["causa_muerte"] is not None:
                        # Registrar la muerte como fila de datos
                        a = agua[pid]
                        estres = get_nivel_estres(a, esp, densidad)

                        dano_ph = 0.0
                        if a["ph"] < esp["ph_min"]:
                            dano_ph = esp["ph_min"] - a["ph"]
                        elif a["ph"] > esp["ph_max"]:
                            dano_ph = a["ph"] - esp["ph_max"]

                        dano_temp = 0.0
                        if a["temperatura_c"] < esp["temp_min"]:
                            dano_temp = esp["temp_min"] - a["temperatura_c"]
                        elif a["temperatura_c"] > esp["temp_max"]:
                            dano_temp = a["temperatura_c"] - esp["temp_max"]

                        dano_ox = 0.0
                        if a["oxigeno_mg_l"] < esp["oxigeno_min"]:
                            dano_ox = esp["oxigeno_min"] - a["oxigeno_mg_l"]

                        dano_nh3 = 0.0
                        if a["amoniaco_mg_l"] > esp["amoniaco_max"]:
                            dano_nh3 = a["amoniaco_mg_l"] - esp["amoniaco_max"]

                        dano_dens = 0.0
                        if densidad > 5:
                            dano_dens = (densidad - 5) / 5.0

                        dano_total = dano_ph + dano_temp + dano_ox + dano_nh3 + dano_dens

                        ph_critico = 1 if (a["ph"] < esp["ph_min"] or a["ph"] > esp["ph_max"]) else 0
                        temp_critico = 1 if (a["temperatura_c"] < esp["temp_min"] or a["temperatura_c"] > esp["temp_max"]) else 0
                        ox_critico = 1 if a["oxigeno_mg_l"] < esp["oxigeno_min"] else 0
                        nh3_critico = 1 if a["amoniaco_mg_l"] > esp["amoniaco_max"] else 0
                        sobrepoblacion = 1 if densidad > 10 else 0

                        if dano_total < 5:
                            estres_cat = "Bajo"
                        elif dano_total < 15:
                            estres_cat = "Moderado"
                        elif dano_total < 30:
                            estres_cat = "Alto"
                        else:
                            estres_cat = "Critico"

                        danos_list = [
                            ("Envenenamiento_amoniaco", dano_nh3),
                            ("Falta_oxigeno", dano_ox),
                            ("pH_fuera_rango", dano_ph),
                            ("Temperatura_inadecuada", dano_temp),
                            ("Sobrepoblacion", dano_dens),
                        ]
                        danos_list.sort(key=lambda x: x[1], reverse=True)
                        causa_riesgo = danos_list[0][0] if danos_list[0][1] > 0 else "Ninguna"

                        peso_pez_g = ps["peso_g"]

                        fila_muerte = {
                            "hora_sim": hora,
                            "pecera_id": pid,
                            "pecera_nombre": peceras[pid]["nombre"],
                            "especie_id": ps["id_especie"],
                            "especie_nombre": esp["nombre"],
                            "pez_id": pez["id"],
                            "salud": 0.0,
                            "vivo": 0,
                            "danos_acumulados": round(pez["danos_acumulados"], 2),
                            "peso_gramos": peso_pez_g,
                            "ph": round(a["ph"], 3),
                            "temperatura": round(a["temperatura_c"], 2),
                            "oxigeno": round(a["oxigeno_mg_l"], 3),
                            "amoniaco": round(a["amoniaco_mg_l"], 4),
                            "volumen_l": volumen,
                            "ph_min": esp["ph_min"],
                            "ph_max": esp["ph_max"],
                            "temp_min": esp["temp_min"],
                            "temp_max": esp["temp_max"],
                            "oxigeno_min": esp["oxigeno_min"],
                            "amoniaco_max": esp["amoniaco_max"],
                            "consumo_o2": esp["consumo_o2"],
                            "ph_desvio": round(dano_ph, 3),
                            "temp_desvio": round(dano_temp, 3),
                            "ox_desvio": round(dano_ox, 3),
                            "nh3_desvio": round(dano_nh3, 4),
                            "dano_ph": round(dano_ph, 3),
                            "dano_temp": round(dano_temp, 3),
                            "dano_oxigeno": round(dano_ox, 3),
                            "dano_amoniaco": round(dano_nh3, 4),
                            "dano_densidad": round(dano_dens, 3),
                            "dano_total": round(dano_total, 3),
                            "ph_critico": ph_critico,
                            "temp_critico": temp_critico,
                            "ox_critico": ox_critico,
                            "nh3_critico": nh3_critico,
                            "sobrepoblacion": sobrepoblacion,
                            "punto_critico": 1,
                            "filtro_mg_h": eq_data["filtro_remocion_mg_h"],
                            "aireacion_mg_h": eq_data["aireacion_mg_h"],
                            "tiene_filtro": 1 if eq_data["filtro_remocion_mg_h"] > 0 else 0,
                            "tiene_aireacion": 1 if eq_data["aireacion_mg_h"] > 0 else 0,
                            "densidad_kg_m3": round(densidad, 2),
                            "biomasa_kg": round(biomasa, 4),
                            "nivel_estres": round(estres, 3),
                            "nivel_estres_cat": estres_cat,
                            "riesgo_muerte": 1.0,
                            "num_vivos_pecera": num_vivos,
                            "num_especies_pecera": num_especies,
                            "causa_riesgo_principal": causa_riesgo,
                            "murio": 1,
                            "causa_muerte": pez["causa_muerte"],
                        }
                        todas_filas.append(fila_muerte)
                        total_muertes += 1

                        # Reponer el pez inmediatamente
                        respawn_count += 1
                        pez_global_id += 1
                        pez["id"] = pez_global_id
                        pez["salud"] = 100.0
                        pez["vivo"] = True
                        pez["causa_muerte"] = None
                        pez["danos_acumulados"] = 0.0

        # Actualizar daños acumulados en peces vivos
        for pid in peces_por_pecera:
            for ps in poblacion_sim[pid]:
                esp = especies[ps["id_especie"]]
                peces_especie = [p for p in peces_por_pecera[pid] if p["id_especie"] == ps["id_especie"]]
                for pez in peces_especie:
                    if pez["vivo"]:
                        volumen_actual = agua[pid]["volumen_l"]
                        densidad_actual = agua[pid].get("biomasa_kg", 0) / volumen_actual * 1000 if volumen_actual > 0 else 0
                        estres = get_nivel_estres(agua[pid], esp, densidad_actual)
                        pez["danos_acumulados"] += estres * 2

        # Progreso cada 100 horas
        if hora % 100 == 0:
            elapsed = time.time() - inicio
            print(f"Hora {hora}: {len(todas_filas):,} filas | {total_muertes} muertes | {respawn_count} respawns | {elapsed:.1f}s")

        # Verificar si alcanzamos el objetivo
        if len(todas_filas) >= FILAS_OBJETIVO:
            print()
            print(f"[OK] Objetivo alcanzado en hora {hora}!")
            break

    # Resultados finales
    elapsed = time.time() - inicio
    print("-" * 70)
    print()
    print("=" * 70)
    print("RESULTADOS FINALES")
    print("=" * 70)
    print(f"Total filas generadas: {len(todas_filas):,}")
    print(f"Total muertes registradas: {total_muertes:,}")
    print(f"Total respawns: {respawn_count:,}")
    print(f"Horas simuladas: {hora}")
    print(f"Columnas por fila: {len(todas_filas[0].keys()) if todas_filas else 0}")
    print(f"Tiempo de ejecución: {elapsed:.1f} segundos")

    # Contar vivos vs muertos
    vivos = sum(1 for f in todas_filas if f["murio"] == 0)
    muertos = sum(1 for f in todas_filas if f["murio"] == 1)
    print(f"Filas de peces vivos: {vivos:,} ({vivos/len(todas_filas)*100:.1f}%)")
    print(f"Filas de peces muertos: {muertos:,} ({muertos/len(todas_filas)*100:.1f}%)")
    print()

    # Exportar a Excel
    os.makedirs("exportaciones", exist_ok=True)
    
    ruta = os.path.join("exportaciones", "MEGA_DATOS_ML.xlsx")
    # Conservar datos anteriores: una nueva simulacion no debe borrar otras exportaciones.
    if os.path.exists(ruta):
        ruta = os.path.join("exportaciones", f"MEGA_DATOS_ML_{time.time_ns()}.xlsx")
    print(f"Exportando a: {ruta}")
    print("(Esto puede tomar unos segundos para 50k+ filas...)")

    if exportar_excel(todas_filas, ruta):
        print(f"[OK] Excel guardado: {ruta}")
        print(f"  Filas: {len(todas_filas):,}")
        print(f"  Columnas: {len(todas_filas[0].keys()) if todas_filas else 0}")
    else:
        print("[ERROR] Error al exportar Excel")

    # Exportar también CSV como respaldo
    ruta_csv = os.path.join("exportaciones", "MEGA_DATOS_ML.csv")
    if todas_filas:
        columnas = list(todas_filas[0].keys())
        print(f"Exportando CSV: {ruta_csv}")
        with open(ruta_csv, "w", encoding="utf-8") as f:
            f.write(",".join(columnas) + "\n")
            for fila in todas_filas:
                vals = []
                for col in columnas:
                    v = fila.get(col, "")
                    if isinstance(v, str) and "," in v:
                        v = f'"{v}"'
                    vals.append(str(v))
                f.write(",".join(vals) + "\n")
        print(f"[OK] CSV guardado: {ruta_csv}")

    print()
    print("=" * 70)
    print("COLUMNAS DISPONIBLES PARA ML:")
    print("=" * 70)
    if todas_filas:
        for i, col in enumerate(todas_filas[0].keys(), 1):
            print(f"  {i:2d}. {col}")

    print()
    print("=" * 70)
    print("RESUMEN PARA MACHINE LEARNING")
    print("=" * 70)
    print("Variable objetivo: 'murio' (0 = vivo, 1 = murió)")
    print()
    print("Features numéricas clave:")
    print("  salud, ph, temperatura, oxigeno, amoniaco, densidad_kg_m3,")
    print("  nivel_estres, riesgo_muerte, dano_ph, dano_temp, dano_oxigeno,")
    print("  dano_amoniaco, dano_densidad, dano_total, danos_acumulados,")
    print("  biomasa_kg, peso_gramos, volumen_l, consumo_o2")
    print()
    print("Features binarias:")
    print("  ph_critico, temp_critico, ox_critico, nh3_critico,")
    print("  sobrepoblacion, punto_critico, tiene_filtro, tiene_aireacion")
    print()
    print("Features categóricas:")
    print("  pecera_nombre, especie_nombre, nivel_estres_cat,")
    print("  causa_riesgo_principal, causa_muerte")
    print()
    print(f"Tiempo total: {elapsed:.1f}s")


if __name__ == "__main__":
    generar_datos_ml()
