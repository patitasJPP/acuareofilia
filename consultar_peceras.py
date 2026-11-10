import tkinter as tk
from tkinter import messagebox, ttk

import psycopg
from database import conectar_bd


CONSULTA = """
SELECT
    p.id_pecera,
    p.nombre_pecera,
    p.volumen_l,
    s.ph,
    s.temperatura_c,
    s.oxigeno_mg_l,
    s.amoniaco_mg_l,
    q.filtro_remocion_mg_h,
    q.aireacion_mg_h,
    e.id_especie,
    e.nombre_comun,
    pe.cantidad_peces,
    pe.peso_promedio_g,
    ROUND(pe.cantidad_peces * pe.peso_promedio_g / 1000.0, 3) AS biomasa_kg,
    e.ph_min,
    e.ph_max,
    e.temp_min_c,
    e.temp_max_c,
    e.oxigeno_min_mg_l,
    e.amoniaco_max_mg_l,
    e.consumo_o2_mg_kg_h,
    a.nombre_alimento,
    a.amoniaco_mg_por_g,
    pe.alimento_g_por_hora
FROM peceras p
LEFT JOIN estado_pecera s ON s.id_pecera = p.id_pecera
LEFT JOIN equipos_pecera q ON q.id_pecera = p.id_pecera
LEFT JOIN pecera_especie pe ON pe.id_pecera = p.id_pecera
LEFT JOIN especies e ON e.id_especie = pe.id_especie
LEFT JOIN alimentos a ON a.id_alimento = pe.id_alimento
ORDER BY p.id_pecera, e.nombre_comun;
"""


def main():
    try:
        with conectar_bd() as connection:
            with connection.cursor() as cursor:
                cursor.execute(CONSULTA)
                columns = [column.name for column in cursor.description]
                rows = cursor.fetchall()
    except psycopg.Error as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Error de PostgreSQL",
            f"No se pudo conectar o ejecutar la consulta:\n{error}",
            parent=root,
        )
        root.destroy()
        return 1

    root = tk.Tk()
    root.title("Datos de peceras")
    root.geometry("1200x650")
    root.minsize(800, 400)

    frame = ttk.Frame(root, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(1, weight=1)

    ttk.Label(frame, text="Consulta de peceras", font=("", 14, "bold")).grid(
        row=0, column=0, sticky="w", pady=(0, 10)
    )

    table_frame = ttk.Frame(frame)
    table_frame.grid(row=1, column=0, sticky="nsew")
    table_frame.columnconfigure(0, weight=1)
    table_frame.rowconfigure(0, weight=1)

    table = ttk.Treeview(
        table_frame,
        columns=columns,
        show="headings",
        style="Data.Treeview",
    )
    vertical_scrollbar = ttk.Scrollbar(
        table_frame, orient=tk.VERTICAL, command=table.yview
    )
    horizontal_scrollbar = ttk.Scrollbar(
        table_frame, orient=tk.HORIZONTAL, command=table.xview
    )
    table.configure(
        yscrollcommand=vertical_scrollbar.set,
        xscrollcommand=horizontal_scrollbar.set,
    )

    table.grid(row=0, column=0, sticky="nsew")
    vertical_scrollbar.grid(row=0, column=1, sticky="ns")
    horizontal_scrollbar.grid(row=1, column=0, sticky="ew")

    style = ttk.Style(root)
    style.configure("Data.Treeview", rowheight=26)
    style.configure("Data.Treeview.Heading", font=("", 9, "bold"))

    for column in columns:
        table.heading(column, text=column.replace("_", " ").title())
        table.column(column, width=145, minwidth=90, stretch=False, anchor=tk.CENTER)

    table.tag_configure("even", background="#f2f6fa")
    for index, row in enumerate(rows):
        table.insert(
            "",
            tk.END,
            values=tuple("—" if value is None else value for value in row.values()),
            tags=("even" if index % 2 == 0 else "odd",),
        )

    status = (
        f"Todo correcto — {len(rows)} registros"
        if rows
        else "Consulta ejecutada correctamente; no se encontraron registros."
    )
    ttk.Label(frame, text=status).grid(row=2, column=0, sticky="w", pady=(10, 0))

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
