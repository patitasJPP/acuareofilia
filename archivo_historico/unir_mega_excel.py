"""
Unificador de datos - Mega Excel para Machine Learning.

Combina todos los archivos Excel y CSV de la carpeta exportaciones/ en un solo
archivo mega con todas las filas juntas para entrenar modelos de ML.
"""

import os
import glob


def leer_excel_filas(ruta):
    """Lee todas las filas de un archivo Excel y devuelve (columnas, filas)."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        print("ERROR: Instala openpyxl: pip install openpyxl")
        return [], []

    wb = load_workbook(ruta, read_only=True, data_only=True)
    ws = wb.active
    columnas = []
    filas = []

    for row in ws.iter_rows(values_only=True):
        row_list = list(row)
        if not any(row_list):  # saltar filas vacías
            continue
        if not columnas:
            columnas = row_list
        else:
            fila_dict = {}
            for i, col in enumerate(columnas):
                if i < len(row_list):
                    fila_dict[col] = row_list[i]
            filas.append(fila_dict)

    wb.close()
    return columnas, filas


def leer_csv_filas(ruta):
    """Lee todas las filas de un archivo CSV y devuelve (columnas, filas)."""
    columnas = []
    filas = []
    with open(ruta, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if i == 0:
                columnas = parts
            else:
                fila_dict = {}
                for j, col in enumerate(columnas):
                    if j < len(parts):
                        fila_dict[col] = parts[j]
                filas.append(fila_dict)
    return columnas, filas


def exportar_mega_excel(todas_filas, ruta):
    """Exporta todas las filas a un solo Excel con formato profesional."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        print("ERROR: Instala openpyxl: pip install openpyxl")
        return False

    if not todas_filas:
        print("No hay filas para exportar.")
        return False

    wb = Workbook()
    ws = wb.active
    ws.title = "MegaDatosML"

    columnas = list(todas_filas[0].keys())

    # Header con estilo
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_align = Alignment(horizontal="center")

    for col_idx, col_name in enumerate(columnas, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # Escribir todas las filas
    print(f"  Escribiendo {len(todas_filas):,} filas...")
    for fila_idx, fila in enumerate(todas_filas, 2):
        for col_idx, col_name in enumerate(columnas, 1):
            val = fila.get(col_name, "")
            ws.cell(row=fila_idx, column=col_idx, value=val)

    # Ajustar ancho de columnas
    for col_idx, col_name in enumerate(columnas, 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = max(len(str(col_name)) + 2, 12)

    wb.save(ruta)
    return True


def unir_todo():
    """Une todos los archivos de exportaciones/ en un mega Excel."""
    print("=" * 70)
    print("UNIFICADOR DE DATOS - MEGA EXCEL PARA MACHINE LEARNING")
    print("=" * 70)
    print()

    export_dir = "exportaciones"
    if not os.path.exists(export_dir):
        print("ERROR: No existe la carpeta 'exportaciones/'")
        return

    # Buscar todos los archivos
    xlsx_files = sorted(glob.glob(os.path.join(export_dir, "*.xlsx")))
    csv_files = sorted(glob.glob(os.path.join(export_dir, "*.csv")))

    print(f"Archivos Excel encontrados: {len(xlsx_files)}")
    print(f"Archivos CSV encontrados: {len(csv_files)}")
    print()

    todas_filas = []
    total_archivos = 0
    columnas_detectadas = []

    # Procesar Excel
    for f in xlsx_files:
        nombre = os.path.basename(f)
        col, filas = leer_excel_filas(f)
        if filas:
            if not columnas_detectadas:
                columnas_detectadas = col
            todas_filas.extend(filas)
            total_archivos += 1
            print(f"  [OK] {nombre}: {len(filas):,} filas")

    # Procesar CSV
    for f in csv_files:
        nombre = os.path.basename(f)
        col, filas = leer_csv_filas(f)
        if filas:
            if not columnas_detectadas:
                columnas_detectadas = col
            todas_filas.extend(filas)
            total_archivos += 1
            print(f"  [OK] {nombre}: {len(filas):,} filas")

    print()
    print("-" * 70)
    print(f"Archivos procesados: {total_archivos}")
    print(f"Total filas combinadas: {len(todas_filas):,}")
    print(f"Columnas: {len(columnas_detectadas)}")
    print()

    if not todas_filas:
        print("No se encontraron datos para unir.")
        return

    # Contar vivos vs muertos
    vivos = sum(1 for f in todas_filas if str(f.get("murio", "")).strip() == "0")
    muertos = sum(1 for f in todas_filas if str(f.get("murio", "")).strip() == "1")
    print(f"Peces vivos (murio=0): {vivos:,}")
    print(f"Peces muertos (murio=1): {muertos:,}")
    print()

    # Exportar mega Excel
    ruta_mega = os.path.join(export_dir, "MEGA_DATOS_ML.xlsx")
    print(f"Exportando mega Excel: {ruta_mega}")

    if exportar_mega_excel(todas_filas, ruta_mega):
        print(f"[OK] Mega Excel guardado: {ruta_mega}")
        print(f"  Filas totales: {len(todas_filas):,}")
        print(f"  Columnas: {len(columnas_detectadas)}")
    else:
        print("[ERROR] No se pudo exportar")

    # Exportar también CSV como respaldo
    ruta_csv = os.path.join(export_dir, "MEGA_DATOS_ML.csv")
    print(f"\nExportando mega CSV: {ruta_csv}")
    columnas = list(todas_filas[0].keys())
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
    print(f"[OK] Mega CSV guardado: {ruta_csv}")

    print()
    print("=" * 70)
    print("LISTO - Mega Excel unificado creado exitosamente")
    print("=" * 70)
    print()
    print("Archivo principal:")
    print(f"  {ruta_mega}")
    print(f"  {len(todas_filas):,} filas x {len(columnas)} columnas")
    print()
    print("Variable objetivo: 'murio' (0 = vivo, 1 = murió)")


if __name__ == "__main__":
    unir_todo()
