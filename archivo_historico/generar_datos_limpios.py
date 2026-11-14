"""
Generador de datos limpios para Machine Learning.

Ejecuta la simulación de mortalidad acuícola con 343 peces fijos,
sin reposición de muertos, y exporta un Excel limpio con 28 columnas.

Cada pez tiene un pez_id único que NO cambia nunca.
Un pez muerto deja de aparecer en las filas.
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
HORAS_MAX = 160  # Llegamos hasta hora 160 (no 161)


def consultar_datos():
    """Carga datos desde PostgreSQL."""
    return consultar_datos_iniciales()


def exportar_excel_limpio(filas, ruta):
    """Exporta las filas a Excel con solo las 28 columnas requeridas."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        print("ERROR: Instala openpyxl primero: pip install openpyxl")
        return False

    # Orden exacto de las 28 columnas
    columnas = [
        'pez_id', 'pecera_id', 'hora_sim',
        'especie_nombre',
        'peso_gramos', 'salud',
        'ph', 'temperatura', 'oxigeno', 'amoniaco',
        'ph_desvio', 'temp_desvio', 'nh3_desvio',
        'volumen_l', 'filtro_mg_h', 'aireacion_mg_h',
        'biomasa_kg', 'densidad_kg_m3',
        'num_vivos_pecera', 'num_especies_pecera',
        'ph_min', 'ph_max', 'temp_min', 'temp_max',
        'oxigeno_min', 'amoniaco_max', 'consumo_o2',
        'muere_siguiente_hora',
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "MegaDatosML"

    # Header con estilo
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_align = Alignment(horizontal="center")

    for col_idx, col_name in enumerate(columnas, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # Datos
    for fila in filas:
        fila_vals = [fila.get(col, "") for col in columnas]
        ws.append(fila_vals)

    # Auto-adjust column width
    for col_idx, col_name in enumerate(columnas, 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = max(len(str(col_name)) + 2, 12)

    wb.save(ruta)
    return True


def generar_datos_limpios():
    """Genera datos limpios de simulación para ML y exporta a Excel."""
    random.seed(42)  # Reproducibilidad
    inicio = time.time()
    print("=" * 70)
    print("GENERADOR DE DATOS LIMPIOS PARA MACHINE LEARNING")
    print("=" * 70)
    print(f"Horas simuladas: 1 a {HORAS_MAX}")
    print("343 peces con ID fijo, sin reposición")
    print()

    # Cargar datos
    peceras, estado, equipos, especies, poblaciones = consultar_datos()
    print(f"Peceras cargadas: {len(peceras)}")
    print(f"Especies cargadas: {len(especies)}")
    print(f"Poblaciones cargadas: {len(poblaciones)}")
    print()

    # Preparar peces individuales por pecera
    # Cada pez obtiene un ID único que NO cambia nunca
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

    total_peces = pez_global_id
    print(f"Total de peces creados: {total_peces}")
    print()

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

    # Almacenar filas por (pez_id, hora) para calcular muere_siguiente_hora después
    # Guardamos el estado de cada pez en cada hora
    historial = {}  # (pez_id, hora) -> dict con datos de la fila

    print("Iniciando simulación...")
    print("-" * 70)

    total_muertes = 0
    hora_muerte = {}

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

            # Evaluar eventos por especie (esto puede matar peces)
            for ps in poblacion_sim[pid]:
                esp = especies[ps["id_especie"]]
                peces_especie = [p for p in peces if p["id_especie"] == ps["id_especie"]]
                evaluar_eventos_peces(peces_especie, agua[pid], esp, densidad, num_especies)

                # Actualizar muertos
                peces_especie_vivos = sum(1 for p in peces_especie if p["vivo"])
                ps["muertos"] = len(peces_especie) - peces_especie_vivos

            # Contar muertes nuevas en esta hora
            muertes_en_esta_hora = 0
            for pez in peces:
                if not pez["vivo"] and pez["id"] not in hora_muerte:
                    hora_muerte[pez["id"]] = hora
                    muertes_en_esta_hora += 1
            total_muertes += muertes_en_esta_hora

            # Registrar datos de CADA pez VIVO en esta hora
            for pez in peces:
                if not pez["vivo"]:
                    continue

                esp_id = pez["id_especie"]
                esp = especies[esp_id]
                a = agua[pid]

                # Calcular desvíos
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

                dano_nh3 = 0.0
                if a["amoniaco_mg_l"] > esp["amoniaco_max"]:
                    dano_nh3 = a["amoniaco_mg_l"] - esp["amoniaco_max"]

                # Peso del pez
                peso_pez_g = 0
                for ps in poblacion_sim[pid]:
                    if ps["id_especie"] == esp_id:
                        peso_pez_g = ps["peso_g"]
                        break

                fila = {
                    "pez_id": int(pez["id"]),
                    "pecera_id": int(pid),
                    "hora_sim": int(hora),
                    "especie_nombre": str(esp["nombre"]).strip(),
                    "peso_gramos": round(peso_pez_g, 3),
                    "salud": round(pez["salud"], 3),
                    "ph": round(a["ph"], 3),
                    "temperatura": round(a["temperatura_c"], 3),
                    "oxigeno": round(a["oxigeno_mg_l"], 3),
                    "amoniaco": round(a["amoniaco_mg_l"], 3),
                    "ph_desvio": round(dano_ph, 3),
                    "temp_desvio": round(dano_temp, 3),
                    "nh3_desvio": round(dano_nh3, 3),
                    "volumen_l": round(volumen, 3),
                    "filtro_mg_h": round(eq_data["filtro_remocion_mg_h"], 3),
                    "aireacion_mg_h": round(eq_data["aireacion_mg_h"], 3),
                    "biomasa_kg": round(biomasa, 3),
                    "densidad_kg_m3": round(densidad, 3),
                    "num_vivos_pecera": int(num_vivos),
                    "num_especies_pecera": int(num_especies),
                    "ph_min": round(esp["ph_min"], 3),
                    "ph_max": round(esp["ph_max"], 3),
                    "temp_min": round(esp["temp_min"], 3),
                    "temp_max": round(esp["temp_max"], 3),
                    "oxigeno_min": round(esp["oxigeno_min"], 3),
                    "amoniaco_max": round(esp["amoniaco_max"], 3),
                    "consumo_o2": round(esp["consumo_o2"], 3),
                    "muere_siguiente_hora": 0,  # Se calculará después
                }
                historial[(pez["id"], hora)] = fila

        # Progreso cada 40 horas
        if hora % 40 == 0:
            elapsed = time.time() - inicio
            print(f"Hora {hora}: {len(historial):,} filas registradas | {total_muertes} muertes | {elapsed:.1f}s")

    print()
    print(f"Simulación completada: {HORAS_MAX} horas")
    print(f"Total muertes: {total_muertes}")
    print()

    # ============================================================
    # CALCULAR muere_siguiente_hora
    # ============================================================
    print("Calculando muere_siguiente_hora...")

    # La ausencia de una fila NO prueba muerte. Usar el evento observado o
    # supervivencia confirmada en t+1; excluir el final censurado del seguimiento.
    muertes_count = 0
    etiquetadas = {}
    for (pez_id, hora), fila in historial.items():
        if hora_muerte.get(pez_id) == hora + 1:
            fila["muere_siguiente_hora"] = 1
            muertes_count += 1
        elif (pez_id, hora + 1) in historial:
            fila["muere_siguiente_hora"] = 0
        else:
            continue
        etiquetadas[(pez_id, hora)] = fila
    historial = etiquetadas

    print(f"Filas con muere_siguiente_hora = 1: {muertes_count}")
    print()

    # ============================================================
    # ORDENAR Y EXPORTAR
    # ============================================================
    todas_filas = sorted(historial.values(), key=lambda f: (f["pez_id"], f["hora_sim"]))

    # Resultados finales
    elapsed = time.time() - inicio
    print("=" * 70)
    print("RESULTADOS FINALES")
    print("=" * 70)
    print(f"Total filas: {len(todas_filas):,}")
    print(f"Total peces únicos: {total_peces}")
    print(f"Horas simuladas: {HORAS_MAX}")
    print(f"Columnas: 28")
    print(f"Tiempo de ejecución: {elapsed:.1f} segundos")

    vivos_final = sum(1 for f in todas_filas if f["muere_siguiente_hora"] == 0)
    muertos_final = sum(1 for f in todas_filas if f["muere_siguiente_hora"] == 1)
    print(f"Filas con muere_siguiente_hora = 0: {vivos_final:,} ({vivos_final/len(todas_filas)*100:.1f}%)")
    print(f"Filas con muere_siguiente_hora = 1: {muertos_final:,} ({muertos_final/len(todas_filas)*100:.1f}%)")
    print()

    # Exportar a Excel
    os.makedirs("exportaciones", exist_ok=True)

    ruta = os.path.join("exportaciones", "MEGA_DATOS_ML_LIMPIO.xlsx")
    if os.path.exists(ruta):
        ruta = os.path.join("exportaciones", f"MEGA_DATOS_ML_LIMPIO_{time.time_ns()}.xlsx")
    print(f"Exportando a: {ruta}")

    if exportar_excel_limpio(todas_filas, ruta):
        print(f"[OK] Excel guardado: {ruta}")
        print(f"  Filas: {len(todas_filas):,}")
        print(f"  Columnas: 28")
    else:
        print("[ERROR] Error al exportar Excel")

    print()
    print(f"Tiempo total: {elapsed:.1f}s")

    return todas_filas, total_peces


if __name__ == "__main__":
    generar_datos_limpios()
