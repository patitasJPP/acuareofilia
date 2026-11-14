"""
Validaciones del archivo MEGA_DATOS_ML_LIMPIO.xlsx
"""

import pandas as pd
import numpy as np

print("=" * 70)
print("VALIDACIONES DE MEGA_DATOS_ML_LIMPIO.xlsx")
print("=" * 70)

df = pd.read_excel('exportaciones/MEGA_DATOS_ML_LIMPIO.xlsx', sheet_name='MegaDatosML')

# 1. Número de filas, columnas y peces únicos
print("\n--- 1. DIMENSIONES ---")
print(f"Filas: {len(df):,}")
print(f"Columnas: {df.shape[1]} (debe ser 28)")
print(f"Peces únicos (pez_id): {df['pez_id'].nunique()} (debe ser 343)")

columnas_esperadas = [
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
print(f"Columnas coinciden: {list(df.columns) == columnas_esperadas}")
if list(df.columns) != columnas_esperadas:
    print(f"  Esperadas: {columnas_esperadas}")
    print(f"  Obtenidas: {list(df.columns)}")

# 2. (pez_id, hora_sim) sin duplicados
print("\n--- 2. DUPLICADOS (pez_id, hora_sim) ---")
dups = df.duplicated(subset=['pez_id', 'hora_sim'], keep=False)
print(f"Filas duplicadas: {dups.sum()} (debe ser 0)")

# 3. Cada pez_id tiene una sola pecera y una sola especie
print("\n--- 3. CONSISTENCIA DE pez_id ---")
pez_pecera = df.groupby('pez_id')['pecera_id'].nunique()
pez_especie = df.groupby('pez_id')['especie_nombre'].nunique()
inconsistente_pecera = (pez_pecera > 1).sum()
inconsistente_especie = (pez_especie > 1).sum()
print(f"Peces con más de una pecera: {inconsistente_pecera} (debe ser 0)")
print(f"Peces con más de una especie: {inconsistente_especie} (debe ser 0)")

# 4. Horas consecutivas sin huecos
print("\n--- 4. HORAS CONSECUTIVAS ---")
huecos = 0
for pez_id, grupo in df.groupby('pez_id'):
    horas = sorted(grupo['hora_sim'].values)
    for i in range(1, len(horas)):
        if horas[i] - horas[i-1] != 1:
            huecos += 1
            print(f"  HUECO: pez {pez_id}, horas {horas[i-1]} -> {horas[i]}")
            if huecos > 10:
                print("  ... (más huecos)")
                break
    if huecos > 10:
        break
print(f"Huecos encontrados: {huecos} (debe ser 0)")

# Verificar que no hay filas después de la muerte
print("\n--- 4b. FILAS DESPUÉS DE LA MUERTE ---")
problemas_post_muerte = 0
for pez_id, grupo in df.groupby('pez_id'):
    filas = grupo.sort_values('hora_sim')
    for idx, fila in filas.iterrows():
        if fila['muere_siguiente_hora'] == 1:
            hora_actual = fila['hora_sim']
            # No debería haber filas después de esta hora para este pez
            posteriores = filas[filas['hora_sim'] > hora_actual]
            if len(posteriores) > 0:
                problemas_post_muerte += 1
                print(f"  PROBLEMA: pez {pez_id} muere en hora {hora_actual} pero tiene {len(posteriores)} filas después")
                break
print(f"Peces con filas después de muerte: {problemas_post_muerte} (debe ser 0)")

# 5. Cero nulos y cero columnas constantes
print("\n--- 5. NULOS Y COLUMNAS CONSTANTES ---")
nulos = df.isnull().sum().sum()
print(f"Valores nulos: {nulos} (debe ser 0)")
if nulos > 0:
    print("  Nulos por columna:")
    print(df.isnull().sum()[df.isnull().sum() > 0])

constantes = []
for col in df.columns:
    if df[col].nunique() == 1:
        constantes.append((col, df[col].iloc[0]))
print(f"Columnas constantes: {len(constantes)} (debe ser 0)")
for col, val in constantes:
    print(f"  {col} = {val}")

# 6. Porcentaje de muere_siguiente_hora = 1
print("\n--- 6. DISTRIBUCIÓN DE muere_siguiente_hora ---")
total_1 = (df['muere_siguiente_hora'] == 1).sum()
total_0 = (df['muere_siguiente_hora'] == 0).sum()
print(f"Total muere_siguiente_hora = 1: {total_1} ({total_1/len(df)*100:.1f}%)")
print(f"Total muere_siguiente_hora = 0: {total_0} ({total_0/len(df)*100:.1f}%)")

print("\nPor pecera:")
for pecera_id in sorted(df['pecera_id'].unique()):
    sub = df[df['pecera_id'] == pecera_id]
    muertes = (sub['muere_siguiente_hora'] == 1).sum()
    print(f"  Pecera {pecera_id}: {muertes} muertes de {len(sub)} filas ({muertes/len(sub)*100:.1f}%)")

# 7. Peces que murieron vs sobrevivieron
print("\n--- 7. PECES MUERTOS vs SOBREVIVIENTES ---")
peces_muertos = set()
peces_vivos_hasta_final = set()
for pez_id, grupo in df.groupby('pez_id'):
    max_hora = grupo['hora_sim'].max()
    tiene_muerte = (grupo['muere_siguiente_hora'] == 1).any()
    if tiene_muerte:
        peces_muertos.add(pez_id)
    if max_hora == 160:
        peces_vivos_hasta_final.add(pez_id)

print(f"Peces que murieron: {len(peces_muertos)}")
print(f"Peces vivos hasta hora 160: {len(peces_vivos_hasta_final)}")
print(f"Total peces: {len(peces_muertos) + len(peces_vivos_hasta_final)} (debe ser 343)")

# Hora de muerte por pecera
print("\nMuertes por pecera:")
for pecera_id in sorted(df['pecera_id'].unique()):
    sub = df[df['pecera_id'] == pecera_id]
    peces_en_pecera = sub['pez_id'].nunique()
    muertos_en_pecera = len(peces_muertos & set(sub['pez_id'].unique()))
    print(f"  Pecera {pecera_id}: {muertos_en_pecera} de {peces_en_pecera} peces ({muertos_en_pecera/peces_en_pecera*100:.1f}%)")

# 8. Porcentaje de amoniaco > amoniaco_max
print("\n--- 8. AMONIACO > AMONIACO_MAX ---")
supera = (df['amoniaco'] > df['amoniaco_max']).sum()
pct = supera / len(df) * 100
print(f"Filas con amoniaco > amoniaco_max: {supera} ({pct:.1f}%)")
if pct > 60:
    print("  [ALERTA] Más del 60%: hay que ajustar el modelo de amoníaco")
else:
    print("  [OK] Porcentaje aceptable")

# Resumen de horas
print("\n--- RESUMEN DE HORAS ---")
print(f"Hora mínima: {df['hora_sim'].min()}")
print(f"Hora máxima: {df['hora_sim'].max()} (debe ser 160)")

print("\n" + "=" * 70)
print("VALIDACIONES COMPLETADAS")
print("=" * 70)
