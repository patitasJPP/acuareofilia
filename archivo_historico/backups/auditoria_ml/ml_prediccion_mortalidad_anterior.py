# =============================================================================
# Predicción de Mortalidad de Peces - Modelo de Machine Learning
# =============================================================================
# Dataset: MEGA_DATOS_ML.xlsx (simulación de peces en peceras/estanques)
# Objetivo: Predecir si un pez muere en la SIGUIENTE hora de simulación
# =============================================================================

import pandas as pd
import numpy as np
from sklearn.model_selection import GroupShuffleSplit, GroupKFold, cross_validate
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    confusion_matrix, classification_report, accuracy_score,
    precision_score, recall_score, f1_score, roc_auc_score,
    average_precision_score
)
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import lightgbm as lgb
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# 1. CARGA DE DATOS
# =============================================================================
print("=" * 80)
print("1. CARGA DE DATOS")
print("=" * 80)

df = pd.read_excel(
    'exportaciones/MEGA_DATOS_ML.xlsx',
    sheet_name='MegaDatosML'
)
print(f"Dimensiones originales: {df.shape[0]:,} filas x {df.shape[1]} columnas")
print(f"Columnas: {df.columns.tolist()}")

# =============================================================================
# 2. ELIMINACIÓN DE COLUMNAS POR FUGA DE DATOS
# =============================================================================
print("\n" + "=" * 80)
print("2. ELIMINACIÓN DE COLUMNAS CON FUGA DE DATOS")
print("=" * 80)

# Diccionario con columnas eliminadas y motivo
columnas_eliminadas = {}

# --- Fuga directa de la respuesta ---
columnas_fuga = {
    'vivo': 'Es exactamente 1 - murio (inverso directo de la variable objetivo)',
    'salud': 'Es 0.0 en TODOS los peces muertos (100% correlación con murio=1)',
    'riesgo_muerte': 'Es 1.0 en TODOS los peces muertos (delata la respuesta)',
    'punto_critico': 'Es 1 en TODOS los peces muertos (delata la respuesta)',
    'danos_acumulados': 'Se calcula a partir del estado de muerte del pez',
    'nivel_estres': 'Se deriva del estado de salud/muerte del pez',
    'nivel_estres_cat': 'Categorización de nivel_estres (también fuga)',
    'dano_total': 'Suma de daños que incluye información de la muerte',
}
for col, motivo in columnas_fuga.items():
    if col in df.columns:
        columnas_eliminadas[col] = f"FUGA: {motivo}"
        print(f"  Eliminando '{col}': {motivo}")

# --- Columnas constantes (sin varianza) ---
columnas_constantes = {
    'ox_desvio': 'Siempre 0 (sin varianza)',
    'dano_oxigeno': 'Siempre 0 (sin varianza)',
    'ox_critico': 'Siempre 0 (sin varianza)',
    'sobrepoblacion': 'Siempre 0 (sin varianza)',
    'tiene_filtro': 'Siempre 1 (sin varianza)',
    'tiene_aireacion': 'Siempre 1 (sin varianza)',
}
for col, motivo in columnas_constantes.items():
    if col in df.columns:
        columnas_eliminadas[col] = f"CONSTANTE: {motivo}"
        print(f"  Eliminando '{col}': {motivo}")

# --- Columnas redundantes (correlación perfecta 1.0) ---
# ph_desvio = dano_ph, temp_desvio = dano_temp, nh3_desvio = dano_amoniaco
# Se deja la columna "dano_*" como representante de cada par
columnas_redundantes = {
    'ph_desvio': 'Correlación 1.0 con dano_ph (se conserva dano_ph)',
    'temp_desvio': 'Correlación 1.0 con dano_temp (se conserva dano_temp)',
    'nh3_desvio': 'Correlación 1.0 con dano_amoniaco (se conserva dano_amoniaco)',
}
for col, motivo in columnas_redundantes.items():
    if col in df.columns:
        columnas_eliminadas[col] = f"REDUNDANTE: {motivo}"
        print(f"  Eliminando '{col}': {motivo}")

# --- causa_riesgo_principal: verificar si es fuga ---
# En el dataset, "Envenenamiento_amoniaco" domina (44,967 filas).
# Esta columna parece calcularse a partir de las condiciones ambientales
# que causan la muerte, por lo que puede ser fuga. Sin embargo, representa
# la causa de riesgo, no la causa de muerte confirmada. Se mantiene pero
# se monitorea su importancia.

# Eliminar todas las columnas identificadas
cols_to_drop = list(columnas_eliminadas.keys())
df_clean = df.drop(columns=cols_to_drop, errors='ignore')
print(f"\nColumnas eliminadas: {len(cols_to_drop)}")
print(f"Dimensiones después de eliminar columnas: {df_clean.shape[0]:,} filas x {df_clean.shape[1]} columnas")

# =============================================================================
# 3. VERIFICACIÓN DE CORRELACIÓN ALTA ENTRE COLUMNAS RESTANTES
# =============================================================================
print("\n" + "=" * 80)
print("3. VERIFICACIÓN DE CORRELACIÓN ALTA (>0.95)")
print("=" * 80)

# Solo columnas numéricas
# Proteger columnas esenciales que NO deben eliminarse por correlación
protected_cols = {
    'pez_id', 'pecera_id', 'especie_id', 'hora_sim', 'murio',
    'pecera_nombre', 'especie_nombre'
}

num_cols = df_clean.select_dtypes(include=[np.number]).columns
corr_matrix = df_clean[num_cols].corr().abs()
# Triangular superior para evitar duplicados
upper = corr_matrix.where(
    np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
)
high_corr_pairs = []
for col in upper.columns:
    found = upper[col][upper[col] > 0.95]
    for idx, val in found.items():
        high_corr_pairs.append((idx, col, val))

if high_corr_pairs:
    print("Pares con correlación > 0.95:")
    cols_to_drop_corr = []
    for c1, c2, corr in high_corr_pairs:
        print(f"  {c1} <-> {c2}: {corr:.4f}")
        # No eliminar columnas protegidas
        if c2 in protected_cols or c1 in protected_cols:
            print(f"    -> PROTEGIDO: no eliminar '{c1}' ni '{c2}'")
            continue
        # Solo eliminar la segunda columna si no es protegida
        if c2 not in columnas_eliminadas and c2 not in protected_cols:
            columnas_eliminadas[c2] = f"ALTA CORRELACIÓN: {corr:.4f} con {c1}"
            cols_to_drop_corr.append(c2)
            print(f"    -> Eliminando '{c2}'")
    if cols_to_drop_corr:
        df_clean = df_clean.drop(columns=cols_to_drop_corr)
else:
    print("No se encontraron pares con correlación > 0.95 entre columnas restantes.")

print(f"Dimensiones después de verificar correlación: {df_clean.shape[0]:,} filas x {df_clean.shape[1]} columnas")

# =============================================================================
# 4. CONSTRUCCIÓN DEL OBJETIVO: "¿Muere en la siguiente hora?"
# =============================================================================
print("\n" + "=" * 80)
print("4. CONSTRUCCIÓN DEL OBJETIVO TEMPORAL")
print("=" * 80)

# Ordenar por pez y hora
df_clean = df_clean.sort_values(['pez_id', 'hora_sim']).reset_index(drop=True)

# Para cada pez, crear el target: murio en la SIGUIENTE hora
# Shift -1 dentro de cada grupo para obtener el murio de la siguiente fila
df_clean['murio_siguiente_hora'] = df_clean.groupby('pez_id')['murio'].shift(-1)

# Marcar si el pez estaba VIVO en la hora actual (solo usamos filas de peces vivos)
# Un pez vivo en la hora actual es aquel donde murio=0 en esa fila
df_clean['pez_vivo_actual'] = (df_clean['murio'] == 0).astype(int)

# Filtrar: solo filas donde el pez está vivo en la hora actual
# y tiene una siguiente observación (no NaN en murio_siguiente_hora)
df_target = df_clean[
    (df_clean['pez_vivo_actual'] == 1) &
    (df_clean['murio_siguiente_hora'].notna())
].copy()

print(f"Filas originales: {df.shape[0]:,}")
print(f"Filas con pez vivo y siguiente observación: {df_target.shape[0]:,}")
print(f"Filas eliminadas (pez ya muerto o sin siguiente obs): {df.shape[0] - df_target.shape[0]:,}")

# Verificar distribución del nuevo target
target_counts = df_target['murio_siguiente_hora'].value_counts()
print(f"\nDistribución del target (murio_siguiente_hora):")
for val, count in target_counts.items():
    pct = count / len(df_target) * 100
    label = "Murió" if val == 1 else "Sobrevivió"
    print(f"  {label} ({val}): {count:,} ({pct:.1f}%)")

# =============================================================================
# 5. SEPARACIÓN DE VARIABLES
# =============================================================================
print("\n" + "=" * 80)
print("5. SEPARACIÓN DE VARIABLES")
print("=" * 80)

# Columnas a usar como features
# Eliminar columnas de identificación y el target
id_cols = ['pez_id', 'pecera_id', 'pecera_nombre', 'hora_sim']
target_col = 'murio_siguiente_hora'
helper_cols = ['murio', 'pez_vivo_actual']  # columnas auxiliares

feature_cols = [
    c for c in df_target.columns
    if c not in id_cols and c not in [target_col] and c not in helper_cols
]

print(f"Columnas de features: {len(feature_cols)}")
print(f"Features: {feature_cols}")

# Separar X y y
X = df_target[feature_cols].copy()
y = df_target['murio_siguiente_hora'].astype(int)
groups_pez = df_target['pez_id'].values
groups_pecera = df_target['pecera_id'].values

# =============================================================================
# 6. CODIFICACIÓN DE VARIABLES CATEGÓRICAS
# =============================================================================
print("\n" + "=" * 80)
print("6. CODIFICACIÓN DE VARIABLES CATEGÓRICAS")
print("=" * 80)

# Identificar columnas categóricas
cat_cols = X.select_dtypes(include=['object', 'category']).columns
print(f"Columnas categóricas: {cat_cols.tolist()}")

# Codificar con LabelEncoder
label_encoders = {}
for col in cat_cols:
    le = LabelEncoder()
    X[col] = le.fit_transform(X[col].astype(str))
    label_encoders[col] = le
    print(f"  '{col}': {X[col].nunique()} categorías codificadas")

print(f"\nDimensiones finales de X: {X.shape[0]:,} filas x {X.shape[1]} columnas")
print(f"Distribución de y: {y.value_counts().to_dict()}")

# =============================================================================
# 7. VALIDACIÓN CRUZADA CON GROUPS
# =============================================================================
print("\n" + "=" * 80)
print("7. ENTRENAMIENTO Y EVALUACIÓN DE MODELOS")
print("=" * 80)

# Métricas a calcular
def calcular_metricas(y_true, y_pred, y_prob, model_name):
    """Calcula y muestra todas las métricas solicitadas."""
    metrics = {
        'Modelo': model_name,
        'Accuracy': accuracy_score(y_true, y_pred),
        'Precision': precision_score(y_true, y_pred, zero_division=0),
        'Recall': recall_score(y_true, y_pred, zero_division=0),
        'F1': f1_score(y_true, y_pred, zero_division=0),
        'ROC-AUC': roc_auc_score(y_true, y_prob),
        'PR-AUC': average_precision_score(y_true, y_prob),
    }
    cm = confusion_matrix(y_true, y_pred)
    metrics['TN'] = cm[0, 0]
    metrics['FP'] = cm[0, 1]
    metrics['FN'] = cm[1, 0]
    metrics['TP'] = cm[1, 1]
    return metrics

# --- 7a. GroupShuffleSplit por pez_id ---
print("\n--- Validación con GroupShuffleSplit (por pez_id) ---")
gss = GroupShuffleSplit(n_splits=5, test_size=0.2, random_state=42)

# Definir modelos
modelos = {
    'Regresión Logística': LogisticRegression(
        max_iter=1000, random_state=42, class_weight='balanced', C=1.0
    ),
    'Random Forest': RandomForestClassifier(
        n_estimators=200, max_depth=10, random_state=42,
        class_weight='balanced', n_jobs=-1
    ),
    'XGBoost': xgb.XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42,
        eval_metric='logloss', use_label_encoder=False,
        scale_pos_weight=y.value_counts()[0] / y.value_counts()[1]
    ),
    'LightGBM': lgb.LGBMClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42,
        class_weight='balanced', verbose=-1
    ),
}

resultados_gss = []
for nombre, modelo in modelos.items():
    print(f"\nEntrenando {nombre}...")
    scoring = {
        'accuracy': 'accuracy',
        'precision': 'precision',
        'recall': 'recall',
        'f1': 'f1',
        'roc_auc': 'roc_auc',
        'pr_auc': 'average_precision',
    }
    cv_results = cross_validate(
        modelo, X, y, groups=groups_pez,
        cv=gss.split(X, y, groups=groups_pez),
        scoring=scoring,
        return_train_score=False,
        n_jobs=1
    )
    row = {'Modelo': nombre}
    for key, val in scoring.items():
        mean_val = cv_results[f'test_{key}'].mean()
        std_val = cv_results[f'test_{key}'].std()
        row[f'{key}_mean'] = mean_val
        row[f'{key}_std'] = std_val
        print(f"  {key}: {mean_val:.4f} (+/- {std_val:.4f})")
    resultados_gss.append(row)

# Tabla resumen GSS
print("\n" + "-" * 80)
print("TABLA COMPARATIVA - GroupShuffleSplit por pez_id")
print("-" * 80)
tabla_gss = pd.DataFrame(resultados_gss)
cols_display = ['Modelo', 'accuracy_mean', 'precision_mean', 'recall_mean',
                'f1_mean', 'roc_auc_mean', 'pr_auc_mean']
print(tabla_gss[cols_display].to_string(index=False))

# =============================================================================
# 7b. Leave-One-Group-Out por pecera_id (validación extra)
# =============================================================================
print("\n" + "=" * 80)
print("7b. VALIDACIÓN Leave-One-Group-Out (por pecera_id)")
print("=" * 80)

# Identificar peceras únicas
peceras_unicas = np.unique(groups_pecera)
print(f"Peceras únicas: {peceras_unicas}")

resultados_log = []
for nombre, modelo in modelos.items():
    print(f"\nEntrenando {nombre} con LOG por pecera...")
    scores = {m: [] for m in scoring.keys()}

    for pecera_test in peceras_unicas:
        # Crear mask: pecera_test = test, resto = train
        mask_test = groups_pecera == pecera_test
        mask_train = ~mask_test

        X_train, X_test = X[mask_train], X[mask_test]
        y_train, y_test = y[mask_train], y[mask_test]

        modelo_clone = type(modelo)(**modelo.get_params())
        modelo_clone.fit(X_train, y_train)
        y_pred = modelo_clone.predict(X_test)
        y_prob = modelo_clone.predict_proba(X_test)[:, 1]

        scores['accuracy'].append(accuracy_score(y_test, y_pred))
        scores['precision'].append(precision_score(y_test, y_pred, zero_division=0))
        scores['recall'].append(recall_score(y_test, y_pred, zero_division=0))
        scores['f1'].append(f1_score(y_test, y_pred, zero_division=0))
        scores['roc_auc'].append(roc_auc_score(y_test, y_prob))
        scores['pr_auc'].append(average_precision_score(y_test, y_prob))

    row = {'Modelo': nombre}
    for key in scoring.keys():
        mean_val = np.mean(scores[key])
        std_val = np.std(scores[key])
        row[f'{key}_mean'] = mean_val
        row[f'{key}_std'] = std_val
        print(f"  {key}: {mean_val:.4f} (+/- {std_val:.4f})")
    resultados_log.append(row)

# Tabla resumen LOG
print("\n" + "-" * 80)
print("TABLA COMPARATIVA - Leave-One-Group-Out por pecera_id")
print("-" * 80)
tabla_log = pd.DataFrame(resultados_log)
print(tabla_log[cols_display].to_string(index=False))

# =============================================================================
# 7c. Comparación: con y sin pecera_id/pecera_nombre
# =============================================================================
print("\n" + "=" * 80)
print("7c. COMPARACIÓN: CON vs SIN pecera_id")
print("=" * 80)

# Verificar si pecera_id está en las features
if 'pecera_id' in feature_cols:
    # Entrenar el mejor modelo SIN pecera_id
    X_sin_pecera = X.drop(columns=['pecera_id'], errors='ignore')
    print(f"\nFeatures sin pecera_id: {X_sin_pecera.shape[1]}")

    # Usar el mejor modelo (XGBoost) para comparar
    best_model_name = 'XGBoost'
    best_model = xgb.XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42,
        eval_metric='logloss', use_label_encoder=False,
        scale_pos_weight=y.value_counts()[0] / y.value_counts()[1]
    )

    # Con pecera_id
    cv_con = cross_validate(
        best_model, X, y, groups=groups_pez,
        cv=gss.split(X, y, groups=groups_pez),
        scoring=['roc_auc', 'f1', 'accuracy'],
        return_train_score=False, n_jobs=1
    )
    print("\nCon pecera_id:")
    for metric in ['roc_auc', 'f1', 'accuracy']:
        print(f"  test_{metric}: {cv_con[f'test_{metric}'].mean():.4f}")

    # Sin pecera_id
    best_model_sin = xgb.XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42,
        eval_metric='logloss', use_label_encoder=False,
        scale_pos_weight=y.value_counts()[0] / y.value_counts()[1]
    )
    cv_sin = cross_validate(
        best_model_sin, X_sin_pecera, y, groups=groups_pez,
        cv=gss.split(X_sin_pecera, y, groups=groups_pez),
        scoring=['roc_auc', 'f1', 'accuracy'],
        return_train_score=False, n_jobs=1
    )
    print("\nSin pecera_id:")
    for metric in ['roc_auc', 'f1', 'accuracy']:
        print(f"  test_{metric}: {cv_sin[f'test_{metric}'].mean():.4f}")

    diff_auc = cv_con['test_roc_auc'].mean() - cv_sin['test_roc_auc'].mean()
    diff_f1 = cv_con['test_f1'].mean() - cv_sin['test_f1'].mean()
    print(f"\nDiferencia ROC-AUC: {diff_auc:.4f}")
    print(f"Diferencia F1: {diff_f1:.4f}")
    if abs(diff_auc) > 0.05:
        print("[ALERTA]  La diferencia es significativa: el modelo podría estar memorizando la pecera.")
    else:
        print("[OK] La diferencia es pequeña: el modelo no depende excesivamente de la pecera.")
else:
    print("pecera_id no está en las features (ya fue eliminado o no se incluyó).")

# =============================================================================
# 8. MATRIZ DE CONFUSIÓN Y REPORTES DETALLADOS DEL MEJOR MODELO
# =============================================================================
print("\n" + "=" * 80)
print("8. ANÁLISIS DETALLADO DEL MEJOR MODELO")
print("=" * 80)

# Entrenar el mejor modelo en todo el train y evaluar con un split final
gss_final = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, test_idx = next(gss_final.split(X, y, groups=groups_pez))

X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

# XGBoost como mejor modelo
best_model_final = xgb.XGBClassifier(
    n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42,
    eval_metric='logloss', use_label_encoder=False,
    scale_pos_weight=y_train.value_counts()[0] / y_train.value_counts()[1]
)
best_model_final.fit(X_train, y_train)
y_pred_final = best_model_final.predict(X_test)
y_prob_final = best_model_final.predict_proba(X_test)[:, 1]

print("\n--- Matriz de Confusión ---")
cm_final = confusion_matrix(y_test, y_pred_final)
print(f"TN: {cm_final[0, 0]:>6}  FP: {cm_final[0, 1]:>6}")
print(f"FN: {cm_final[1, 0]:>6}  TP: {cm_final[1, 1]:>6}")

print("\n--- Classification Report ---")
print(classification_report(y_test, y_pred_final, target_names=['Sobrevive', 'Muere']))

print("\n--- Métricas Finales ---")
print(f"Accuracy:  {accuracy_score(y_test, y_pred_final):.4f}")
print(f"Precision: {precision_score(y_test, y_pred_final):.4f}")
print(f"Recall:    {recall_score(y_test, y_pred_final):.4f}")
print(f"F1:        {f1_score(y_test, y_pred_final):.4f}")
print(f"ROC-AUC:   {roc_auc_score(y_test, y_prob_final):.4f}")
print(f"PR-AUC:    {average_precision_score(y_test, y_prob_final):.4f}")

# =============================================================================
# 9. IMPORTANCIA DE VARIABLES
# =============================================================================
print("\n" + "=" * 80)
print("9. IMPORTANCIA DE VARIABLES")
print("=" * 80)

importancias = best_model_final.feature_importances_
importancia_df = pd.DataFrame({
    'feature': feature_cols,
    'importance': importancias
}).sort_values('importance', ascending=False)

print("\nTop 20 variables más importantes:")
print(importancia_df.head(20).to_string(index=False))

# Verificar si una sola variable domina
max_importance = importancias.max()
total_importance = importancias.sum()
dominance = max_importance / total_importance * 100
top_var = importancia_df.iloc[0]['feature']
print(f"\nVariable más importante: '{top_var}' con {dominance:.1f}% del total")

if dominance > 30:
    print(f"[ALERTA]  ALERTA: '{top_var}' domina con {dominance:.1f}% del total.")
    print("    Esto podría indicar fuga de datos no detectada.")
elif dominance > 20:
    print(f"  [NOTA] Nota: '{top_var}' tiene {dominance:.1f}% del total.")
    print("    Es significativa pero no anormalmente dominante.")
else:
    print("  [OK] La importancia está bien distribuida entre las variables.")

# =============================================================================
# 10. VERIFICACIÓN DE FUGA: Si AUC > 0.98, buscar fuga
# =============================================================================
print("\n" + "=" * 80)
print("10. VERIFICACIÓN DE FUGA DE DATOS")
print("=" * 80)

auc_final = roc_auc_score(y_test, y_prob_final)
if auc_final > 0.98:
    print(f"[ALERTA]  ALERTA: ROC-AUC = {auc_final:.4f} (> 0.98)")
    print("    Rendimiento casi perfecto. Buscando posible fuga...")

    # Verificar cada variable individualmente
    for feat in feature_cols:
        simple_model = LogisticRegression(max_iter=1000, random_state=42)
        simple_model.fit(X_train[[feat]], y_train)
        simple_auc = roc_auc_score(y_test, simple_model.predict_proba(X_test[[feat]])[:, 1])
        if simple_auc > 0.9:
            print(f"    [ALERTA]  '{feat}' sola alcanza AUC = {simple_auc:.4f} (posible fuga)")
else:
    print(f"[OK] ROC-AUC = {auc_final:.4f} (<= 0.98). No se detecta fuga evidente.")

# =============================================================================
# 11. RESUMEN FINAL
# =============================================================================
print("\n" + "=" * 80)
print("11. RESUMEN FINAL")
print("=" * 80)

print(f"\n--- Columnas eliminadas ({len(columnas_eliminadas)}) ---")
for col, motivo in columnas_eliminadas.items():
    print(f"  {col}: {motivo}")

print(f"\n--- Dimensiones ---")
print(f"  Dataset original: {df.shape[0]:,} filas x {df.shape[1]} columnas")
print(f"  Dataset final (X): {X.shape[0]:,} filas x {X.shape[1]} columnas")

print(f"\n--- Tabla comparativa de modelos (GroupShuffleSplit) ---")
print(tabla_gss[cols_display].to_string(index=False))

print(f"\n--- Tabla comparativa (Leave-One-Group-Out por pecera) ---")
print(tabla_log[cols_display].to_string(index=False))

print(f"\n--- Métricas finales del mejor modelo (XGBoost) ---")
print(f"  Accuracy:  {accuracy_score(y_test, y_pred_final):.4f}")
print(f"  Precision: {precision_score(y_test, y_pred_final):.4f}")
print(f"  Recall:    {recall_score(y_test, y_pred_final):.4f}")
print(f"  F1:        {f1_score(y_test, y_pred_final):.4f}")
print(f"  ROC-AUC:   {auc_final:.4f}")
print(f"  PR-AUC:    {average_precision_score(y_test, y_prob_final):.4f}")

print("\n" + "=" * 80)
print("PROCESO COMPLETADO")
print("=" * 80)
