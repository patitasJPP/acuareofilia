"""
Simulación visual de TODAS las peceras con estanques animados y estadísticas.

Muestra cada pecera en una cuadrícula con su propio estanque visual y datos en tiempo real.
Diseño minimalista blanco, enfocado en la rapidez de la simulación.
"""

import tkinter as tk
import math
import random
import time
import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from database import conectar_bd
from simulacion import (
    calcular_dano_ph,
    calcular_dano_temp,
    calcular_dano_oxigeno,
    calcular_dano_amoniaco,
    calcular_dano_densidad,
    evolucionar_agua,
    evaluar_eventos_peces,
    get_nivel_estres,
    explicar_condiciones,
    explicar_causa_muerte,
)


# ============================================================
# Colores minimalistas blancos
# ============================================================
BG_WHITE = "#ffffff"
BG_LIGHT = "#f8f9fa"
BG_CARD = "#ffffff"
BG_SECTION = "#f0f0f0"
TEXT_DARK = "#2c3e50"
TEXT_GRAY = "#7f8c8d"
TEXT_LIGHT_GRAY = "#bdc3c7"
TEXT_GREEN = "#27ae60"
TEXT_YELLOW = "#f39c12"
TEXT_RED = "#e74c3c"
TEXT_BLUE = "#2980b9"
AQUA_BG = "#e8f4f8"
AQUA_WATER = "#d6eaf8"
AQUA_FLOOR = "#d5dbdb"
PEZERA_COLORES = ["#3498db", "#2ecc71", "#9b59b6", "#e67e22", "#1abc9c", "#e74c3c", "#34495e"]
PEZ_COLORES = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c", "#e67e22", "#34495e", "#e91e63", "#00bcd4"]


def consultar_datos_iniciales():
    """Carga datos desde PostgreSQL."""
    with conectar_bd() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id_pecera, nombre_pecera, volumen_l FROM peceras ORDER BY id_pecera")
            peceras = {row["id_pecera"]: {"nombre": row["nombre_pecera"], "volumen_l": float(row["volumen_l"])}
                       for row in cur.fetchall()}

            cur.execute("SELECT id_pecera, ph, temperatura_c, oxigeno_mg_l, amoniaco_mg_l FROM estado_pecera")
            estado = {}
            for row in cur.fetchall():
                estado[row["id_pecera"]] = {
                    "ph": float(row["ph"]),
                    "temperatura_c": float(row["temperatura_c"]),
                    "oxigeno_mg_l": float(row["oxigeno_mg_l"]),
                    "amoniaco_mg_l": float(row["amoniaco_mg_l"]),
                }

            cur.execute("SELECT id_pecera, filtro_remocion_mg_h, aireacion_mg_h FROM equipos_pecera")
            equipos = {}
            for row in cur.fetchall():
                equipos[row["id_pecera"]] = {
                    "filtro_remocion_mg_h": float(row["filtro_remocion_mg_h"]),
                    "aireacion_mg_h": float(row["aireacion_mg_h"]),
                }

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


class PezMini:
    """Pez miniatura - 1 solo canvas item para rendimiento."""

    def __init__(self, canvas, x, y, color, size=6):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.color = color
        self.size = size
        self.salud = 100.0
        self.vivo = True
        self.angle = random.uniform(0, 2 * math.pi)
        self.speed = random.uniform(0.5, 2.0)
        self.turn_timer = 0
        self.sinking = False
        self.sink_speed = 0

        # Un solo rectángulo redondeado simula el pez
        s = size
        self.id = canvas.create_rectangle(0, 0, 0, 0, fill=self.color, outline="", width=0)

    def update(self, tw, floor_y):
        s = self.size
        if self.sinking:
            self.y += self.sink_speed
            if self.y >= floor_y - s:
                self.y = floor_y - s
                self.sink_speed = 0
        else:
            self.turn_timer -= 1
            if self.turn_timer <= 0:
                self.angle += random.uniform(-1.0, 1.0)
                self.turn_timer = random.randint(5, 30)

            speed_mult = max(0.1, self.salud / 100.0)
            if self.salud < 30:
                speed_mult *= 0.3

            self.x += math.cos(self.angle) * self.speed * speed_mult
            self.y += math.sin(self.angle) * self.speed * speed_mult * 0.4

            margin = s
            if self.x < margin:
                self.x = margin
                self.angle = 0
            elif self.x > tw - margin:
                self.x = tw - margin
                self.angle = math.pi
            if self.y < margin:
                self.y = margin
                self.angle = math.pi / 2
            elif self.y > floor_y - margin:
                self.y = floor_y - margin
                self.angle = -math.pi / 2

        # Color según salud
        if not self.vivo:
            dc = "#95a5a6"
        elif self.salud > 70:
            dc = self.color
        elif self.salud > 30:
            dc = TEXT_YELLOW
        else:
            dc = TEXT_RED

        # Una sola llamada coords + itemconfig
        self.canvas.coords(self.id, self.x - s, self.y - s * 0.4, self.x + s, self.y + s * 0.4)
        self.canvas.itemconfig(self.id, fill=dc)


class PeceraCard:
    """Tarjeta de una pecera con estanque visual + estadísticas reutilizables."""

    def __init__(self, parent, pecera_id, pecera_data, sim_data, especies, color_accent, on_detail_click):
        self.pecera_id = pecera_id
        self.pecera_data = pecera_data
        self.sim_data = sim_data
        self.especies = especies
        self.color_accent = color_accent
        self.on_detail_click = on_detail_click

        self.peces = []
        self.needs_recreate = False

        # Frame principal de la tarjeta
        self.card = tk.Frame(parent, bg=BG_CARD, highlightbackground=color_accent, highlightthickness=2)

        # Header con nombre
        header = tk.Frame(self.card, bg=color_accent, padx=8, pady=4)
        header.pack(fill=tk.X)
        tk.Label(header, text=pecera_data["nombre"], font=("", 10, "bold"), fg="white", bg=color_accent).pack(side=tk.LEFT)
        tk.Label(header, text=f"{pecera_data['volumen_l']}L", font=("", 8), fg="white", bg=color_accent).pack(side=tk.RIGHT)

        # Canvas del estanque
        self.canvas = tk.Canvas(self.card, bg=AQUA_WATER, highlightthickness=0, height=100)
        self.canvas.pack(fill=tk.X)

        # Panel de estadísticas - labels reutilizables
        self.stats_frame = tk.Frame(self.card, bg=BG_CARD, padx=6, pady=4)
        self.stats_frame.pack(fill=tk.X)

        # Labels reutilizables para agua
        self.agua_labels = []
        self.agua_row = tk.Frame(self.stats_frame, bg=BG_CARD)
        self.agua_row.pack(fill=tk.X, pady=(0, 2))
        agua_keys = ["ph", "temperatura_c", "oxigeno_mg_l", "amoniaco_mg_l"]
        agua_nombres = ["pH", "Temp", "O₂", "NH₃"]
        agua_fmts = [".1f", ".0f", ".1f", ".3f"]
        agua_units = ["", "°C", "", ""]
        for i, (key, nombre, fmt, unit) in enumerate(zip(agua_keys, agua_nombres, agua_fmts, agua_units)):
            item_frame = tk.Frame(self.agua_row, bg=BG_SECTION, padx=4, pady=1)
            item_frame.pack(side=tk.LEFT, padx=2)
            tk.Label(item_frame, text=nombre, font=("", 7), fg=TEXT_GRAY, bg=BG_SECTION).pack()
            val_label = tk.Label(item_frame, text="0", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_SECTION)
            val_label.pack()
            self.agua_labels.append((val_label, key, fmt, unit))

        # Labels reutilizables para población
        self.pop_labels = []
        self.pop_bar_ids = []

        # Dibujar fondo del estanque
        self._draw_tank_bg()
        # Crear peces
        self._create_fish()
        # Construir estadísticas (solo una vez, crea los widgets)
        self._init_stats()

    def _draw_tank_bg(self):
        cw = self.canvas.winfo_width()
        if cw < 50:
            cw = 200
        ch = 100
        floor_y = ch - 10
        self.canvas.create_rectangle(0, 0, cw, ch, fill=AQUA_WATER, outline="")
        self.canvas.create_rectangle(0, floor_y, cw, ch, fill=AQUA_FLOOR, outline="")

    def _create_fish(self):
        cw = self.canvas.winfo_width()
        if cw < 50:
            cw = 200
        floor_y = 90
        pez_counter = 0

        for pop in self.sim_data["poblacion_sim"]:
            num_repr = min(8, pop.get("cantidad_original", pop.get("vivos", 0)))
            for _ in range(num_repr):
                x = random.randint(15, cw - 15)
                y = random.randint(10, floor_y - 10)
                color = PEZ_COLORES[pez_counter % len(PEZ_COLORES)]
                pez = PezMini(self.canvas, x, y, color, size=4)
                self.peces.append(pez)
                pez_counter += 1

    def _init_stats(self):
        """Crear los widgets de población una sola vez."""
        poblacion = self.sim_data["poblacion_sim"]
        pop_start_row = len(self.agua_labels)  # marker

        for pop in poblacion:
            esp = self.especies.get(pop["id_especie"], {})
            esp_name = esp.get('nombre', '?')
            total = pop.get("cantidad_original", pop.get("vivos", 0))

            pop_row = tk.Frame(self.stats_frame, bg=BG_CARD)
            pop_row.pack(fill=tk.X, pady=1)

            name_label = tk.Label(pop_row, text=esp_name, font=("", 8), fg=TEXT_BLUE, bg=BG_CARD, width=10, anchor="w")
            name_label.pack(side=tk.LEFT)

            count_label = tk.Label(pop_row, text=f"0/{total}", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_CARD)
            count_label.pack(side=tk.LEFT, padx=(5, 5))

            # Barra como canvas con un rect reutilizable
            bar_canvas = tk.Canvas(pop_row, width=80, height=5, bg=BG_SECTION, highlightthickness=0)
            bar_canvas.pack(side=tk.LEFT)
            bar_rect = bar_canvas.create_rectangle(0, 0, 0, 5, fill=TEXT_GREEN, outline="")

            self.pop_labels.append((count_label, total))
            self.pop_bar_ids.append((bar_canvas, bar_rect))

        # Botón de detalles
        btn = tk.Button(self.stats_frame, text="📊 Ver detalles", font=("", 7),
                        bg=BG_SECTION, fg=TEXT_GRAY, relief=tk.FLAT, cursor="hand2",
                        command=self.on_detail_click)
        btn.pack(pady=(2, 0))

    def update_stats(self):
        """Actualiza SOLO el texto de los labels existentes - sin destruir widgets."""
        agua = self.sim_data["agua"]
        for val_label, key, fmt, unit in self.agua_labels:
            val_label.config(text=f"{agua[key]:{fmt}}{unit}")

        poblacion = self.sim_data["poblacion_sim"]
        for i, pop in enumerate(poblacion):
            if i >= len(self.pop_labels):
                break
            count_label, total = self.pop_labels[i]
            bar_canvas, bar_rect = self.pop_bar_ids[i]
            vivos = pop["vivos"]
            count_label.config(text=f"{vivos}/{total}")
            ratio = vivos / max(total, 1)
            bar_color = TEXT_GREEN if ratio > 0.5 else TEXT_YELLOW if ratio > 0.25 else TEXT_RED
            bar_w = int(80 * ratio)
            bar_canvas.coords(bar_rect, 0, 0, bar_w, 5)
            bar_canvas.itemconfig(bar_rect, fill=bar_color)

    def animate(self):
        """Animar peces - sin burbujas."""
        cw = self.canvas.winfo_width()
        if cw < 10:
            cw = 200
        floor_y = 90

        for pez in self.peces:
            pez.update(cw, floor_y)

    def recreate_on_respawn(self):
        """Recrear peces visuales y barras de stats cuando hay respawn."""
        # Eliminar peces viejos del canvas
        for pez in self.peces:
            self.canvas.delete(pez.id)
        self.peces = []

        # Eliminar barras de población viejas
        # Las barras están dentro de stats_frame después de agua_row
        children = self.stats_frame.winfo_children()
        # agua_row es el primer hijo, el resto son filas de población + botón
        if len(children) > 1:
            for w in children[1:]:
                w.destroy()

        self.pop_labels = []
        self.pop_bar_ids = []

        # Recrear peces
        self._create_fish()
        # Recrear stats de población
        self._init_stats()
        self.needs_recreate = False


class SimulacionTodasPeceras:
    def __init__(self, root):
        self.root = root
        self.root.title("🐟 Todas las Peceras - Simulación de Mortalidad Acuícola")
        self.root.geometry("1600x1000")
        self.root.minsize(1400, 900)
        self.root.configure(bg=BG_WHITE)

        self.running = False
        self.tick_count = 0
        self.day = 0
        self.hour = 0

        # Cargar datos
        self.peceras, self.estado, self.equipos, self.especies, self.poblaciones = consultar_datos_iniciales()
        self.pecera_ids = list(self.peceras.keys())

        # Estado simulado por pecera
        self.sim_data = {}
        for pid in self.pecera_ids:
            self.sim_data[pid] = self._init_sim_data(pid)

        # Logs de muerte por pecera: {pecera_id: [ {causa, especie, cantidad, agua_snapshot, hora} ] }
        self.pecera_death_logs = {pid: [] for pid in self.pecera_ids}
        self.total_deaths = 0
        self.death_report_window = None  # Ventana separada de informes

        # Exportación Excel cada 6 horas
        self.last_export_hour = -1
        self.export_count = 0
        self.export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exportaciones")
        os.makedirs(self.export_dir, exist_ok=True)

        self._build_ui()

    def _export_excel(self):
        """Acumular datos en un solo archivo MEGA_DATOS_ML.xlsx cada 6 horas de simulación."""
        total_sim_hours = self.day * 24 + self.hour
        current_6h_block = total_sim_hours // 6

        if current_6h_block <= self.last_export_hour:
            return

        self.last_export_hour = current_6h_block
        self.export_count += 1

        mega_path = os.path.join(self.export_dir, "MEGA_DATOS_ML.xlsx")
        headers = [
            "Hora_simulacion", "Dia", "Hora", "ID_pecera", "Nombre_pecera",
            "ID_especie", "Nombre_especie", "Pez_ID", "murio", "Salud_estimada",
            "pH", "Temperatura", "Oxigeno", "Amoniaco",
            "Dano_pH", "Dano_temperatura", "Dano_oxigeno", "Dano_amoniaco", "Dano_sobrepoblacion",
            "Riesgo_muerte", "Punto_critico",
            "Filtro_remocion_mg_h", "Aireacion_mg_h",
            "Biomasa_kg", "Densidad_kg_m3", "Volumen_L"
        ]

        filas = []
        pez_id = 0
        for pid in self.pecera_ids:
            sim = self.sim_data[pid]
            pdata = self.peceras[pid]
            agua = sim["agua"]
            eq = sim["equipos"]
            poblacion = sim["poblacion_sim"]
            biomasa = sum(pop["vivos"] * pop["peso_g"] / 1000 for pop in poblacion)
            volumen = agua["volumen_l"]
            densidad = (biomasa / volumen) * 1000 if volumen > 0 else 0

            for pop in poblacion:
                esp = self.especies.get(pop["id_especie"], {})
                esp_nombre = esp.get("nombre", "?")
                dano_ph = calcular_dano_ph(agua["ph"], esp.get("ph_min", 6.5), esp.get("ph_max", 8.5))
                dano_temp = calcular_dano_temp(agua["temperatura_c"], esp.get("temp_min", 20), esp.get("temp_max", 30))
                dano_ox = calcular_dano_oxigeno(agua["oxigeno_mg_l"], esp.get("oxigeno_min", 5.0))
                dano_nh3 = calcular_dano_amoniaco(agua["amoniaco_mg_l"], esp.get("amoniaco_max", 0.5))
                dano_dens = calcular_dano_densidad(biomasa, volumen)
                dano_total = dano_ph + dano_temp + dano_ox + dano_nh3 + dano_dens
                total_orig = pop.get("cantidad_original", 0)
                vivos = pop["vivos"]
                muertos = total_orig - vivos

                for i in range(vivos):
                    pez_id += 1
                    salud = max(0, min(100, 100 - dano_total * 3 + random.uniform(-5, 5)))
                    riesgo = min(100, dano_total * 2)
                    filas.append([
                        total_sim_hours, self.day, self.hour, pid, pdata["nombre"],
                        pop["id_especie"], esp_nombre, f"{pid}-{pop['id_especie']}-{pez_id}",
                        0, round(salud, 2),
                        round(agua["ph"], 4), round(agua["temperatura_c"], 2),
                        round(agua["oxigeno_mg_l"], 4), round(agua["amoniaco_mg_l"], 6),
                        round(dano_ph, 4), round(dano_temp, 4), round(dano_ox, 4),
                        round(dano_nh3, 4), round(dano_dens, 4),
                        round(riesgo, 2), 1 if dano_total > 20 else 0,
                        eq.get("filtro_remocion_mg_h", 0), eq.get("aireacion_mg_h", 0),
                        round(biomasa, 4), round(densidad, 4), volumen
                    ])
                for i in range(muertos):
                    pez_id += 1
                    filas.append([
                        total_sim_hours, self.day, self.hour, pid, pdata["nombre"],
                        pop["id_especie"], esp_nombre, f"{pid}-{pop['id_especie']}-{pez_id}",
                        1, 0.0,
                        round(agua["ph"], 4), round(agua["temperatura_c"], 2),
                        round(agua["oxigeno_mg_l"], 4), round(agua["amoniaco_mg_l"], 6),
                        round(dano_ph, 4), round(dano_temp, 4), round(dano_ox, 4),
                        round(dano_nh3, 4), round(dano_dens, 4),
                        100.0, 1,
                        eq.get("filtro_remocion_mg_h", 0), eq.get("aireacion_mg_h", 0),
                        round(biomasa, 4), round(densidad, 4), volumen
                    ])

        # Escribir en el archivo MEGA
        try:
            from openpyxl import load_workbook
            wb = load_workbook(mega_path)
            ws = wb.active
        except Exception:
            # Primer archivo: crear con headers
            wb = Workbook()
            ws = wb.active
            ws.title = "MegaDatosML"
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_align = Alignment(horizontal="center")
            for ci, hn in enumerate(headers, 1):
                cell = ws.cell(row=1, column=ci, value=hn)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align

        for fila in filas:
            ws.append(fila)
        wb.save(mega_path)

        # CSV de respaldo
        csv_path = os.path.join(self.export_dir, "MEGA_DATOS_ML.csv")
        try:
            with open(csv_path, "a", encoding="utf-8") as f:
                for fila in filas:
                    f.write(",".join(str(v) for v in fila) + "\n")
        except Exception:
            pass

        print(f"[EXPORT] MEGA actualizado: {len(filas)} filas (hora {total_sim_hours}, export #{self.export_count})")
        if hasattr(self, "lbl_export"):
            self.lbl_export.config(
                text=f"📁 MEGA #{self.export_count} | Hora {total_sim_hours} | +{len(filas)} filas",
                fg=TEXT_GREEN
            )

    def _export_excel_manual(self):
        """Forzar exportación manual - agrega datos al archivo MEGA existente."""
        self._export_excel()
        if hasattr(self, "lbl_export"):
            self.lbl_export.config(
                text=f"📁 Manual export → MEGA actualizado",
                fg=TEXT_GREEN
            )

    def _init_sim_data(self, pecera_id):
        pdata = self.peceras[pecera_id]
        edata = self.estado.get(pecera_id, {"ph": 7.0, "temperatura_c": 25, "oxigeno_mg_l": 7.0, "amoniaco_mg_l": 0.0})
        eqdata = self.equipos.get(pecera_id, {"filtro_remocion_mg_h": 0, "aireacion_mg_h": 0})

        agua = {
            "ph": edata["ph"],
            "temperatura_c": edata["temperatura_c"],
            "oxigeno_mg_l": edata["oxigeno_mg_l"],
            "amoniaco_mg_l": edata["amoniaco_mg_l"],
            "volumen_l": pdata["volumen_l"],
        }

        poblacion_sim = []
        pecera_pops = [p for p in self.poblaciones if p["id_pecera"] == pecera_id]
        for pop in pecera_pops:
            poblacion_sim.append({
                "vivos": pop["cantidad"],
                "peso_g": pop["peso_g"],
                "alimento_g_h": pop["alimento_g_h"],
                "amoniaco_mg_por_g": pop["amoniaco_mg_por_g"],
                "consumo_o2": self.especies.get(pop["id_especie"], {}).get("consumo_o2", 0),
                "id_especie": pop["id_especie"],
                "cantidad_original": pop["cantidad"],
            })

        return {
            "agua": agua,
            "equipos": eqdata,
            "poblacion_sim": poblacion_sim,
            "respawn_count": 0,  # Cuántas veces se ha repoblado
        }

    def _open_death_report(self):
        """Abrir ventana con informe de cada muerte individual con circunstancias."""
        if self.death_report_window is not None and self.death_report_window.winfo_exists():
            self.death_report_window.destroy()

        win = tk.Toplevel(self.root)
        win.title("📊 Informe de Muertes - Cada Pez")
        win.geometry("950x650")
        win.configure(bg=BG_LIGHT)
        self.death_report_window = win

        main_frame = tk.Frame(win, bg=BG_LIGHT)
        main_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(main_frame, bg=BG_LIGHT, highlightthickness=0)
        scrollbar = tk.Scrollbar(main_frame, command=canvas.yview, bg=BG_SECTION, width=15)
        inner = tk.Frame(canvas, bg=BG_LIGHT)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        inner.bind("<MouseWheel>", _on_mousewheel)

        # === TÍTULO ===
        tk.Label(inner, text="📊 Informe de Muertes Individuales", font=("", 14, "bold"),
                 fg=TEXT_DARK, bg=BG_LIGHT, anchor="w").pack(fill=tk.X, padx=20, pady=(15, 5))
        tk.Label(inner, text="Cada pez que murió se reponió al instante. Aquí las circunstancias de cada muerte.",
                 font=("", 9), fg=TEXT_GRAY, bg=BG_LIGHT, anchor="w").pack(fill=tk.X, padx=20, pady=(0, 10))

        # === RESUMEN GLOBAL ===
        total_global = 0
        causa_global = {}
        pecera_global = {}
        for pid in self.pecera_ids:
            for l in self.pecera_death_logs[pid]:
                total_global += 1
                causa_global[l["causa"]] = causa_global.get(l["causa"], 0) + 1
                p = l.get("pecera", self.peceras[pid]["nombre"])
                pecera_global[p] = pecera_global.get(p, 0) + 1

        resumen_card = tk.Frame(inner, bg=BG_CARD, padx=15, pady=10,
                                highlightbackground=TEXT_BLUE, highlightthickness=2)
        resumen_card.pack(fill=tk.X, padx=20, pady=(0, 10))
        tk.Label(resumen_card, text="📋 Resumen", font=("", 11, "bold"),
                 fg=TEXT_BLUE, bg=BG_CARD).pack(anchor=tk.W, pady=(0, 6))

        if total_global > 0:
            tk.Label(resumen_card, text=f"  Total de muertes registradas: {total_global} peces",
                     font=("", 10, "bold"), fg=TEXT_DARK, bg=BG_CARD).pack(anchor=tk.W, pady=1)
            if pecera_global:
                mas_afectada = max(pecera_global, key=pecera_global.get)
                tk.Label(resumen_card, text=f"  Pecera más afectada: {mas_afectada} ({pecera_global[mas_afectada]} muertes)",
                         font=("", 10), fg=TEXT_RED, bg=BG_CARD).pack(anchor=tk.W, pady=1)
            if causa_global:
                dominante = max(causa_global, key=causa_global.get)
                tk.Label(resumen_card, text=f"  Causa dominante: {dominante} ({causa_global[dominante]} muertes)",
                         font=("", 10), fg=TEXT_YELLOW, bg=BG_CARD).pack(anchor=tk.W, pady=1)

            # Causas con barras
            tk.Label(resumen_card, text="  Causas:", font=("", 10, "bold"),
                     fg=TEXT_DARK, bg=BG_CARD).pack(anchor=tk.W, pady=(6, 3))
            for causa, cant in sorted(causa_global.items(), key=lambda x: x[1], reverse=True):
                pct = (cant / total_global) * 100
                row_f = tk.Frame(resumen_card, bg=BG_CARD)
                row_f.pack(fill=tk.X, pady=1)
                tk.Label(row_f, text=f"    {causa}:", font=("", 8), fg=TEXT_RED, bg=BG_CARD, width=30, anchor="w").pack(side=tk.LEFT)
                tk.Label(row_f, text=f"{cant} ({pct:.0f}%)", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_CARD).pack(side=tk.LEFT, padx=(4, 0))
                bar_c = tk.Canvas(row_f, width=100, height=6, bg=BG_SECTION, highlightthickness=0)
                bar_c.pack(side=tk.LEFT, padx=(6, 0))
                bar_c.create_rectangle(0, 0, int(100 * pct / 100), 6, fill=TEXT_RED, outline="")
        else:
            tk.Label(resumen_card, text="  No hay muertes aún.", font=("", 10), fg=TEXT_GREEN, bg=BG_CARD).pack(anchor=tk.W)

        # === TABLA DE MUERTES INDIVIDUALES POR PECERA ===
        # Encabezado de tabla
        header_bg = tk.Frame(inner, bg=BG_SECTION, padx=5, pady=3)
        header_bg.pack(fill=tk.X, padx=20, pady=(10, 2))
        tk.Label(header_bg, text="#", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_SECTION, width=4, anchor="w").pack(side=tk.LEFT)
        tk.Label(header_bg, text="Hora Sim", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_SECTION, width=8, anchor="w").pack(side=tk.LEFT, padx=2)
        tk.Label(header_bg, text="Pecera", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_SECTION, width=18, anchor="w").pack(side=tk.LEFT, padx=2)
        tk.Label(header_bg, text="Especie", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_SECTION, width=14, anchor="w").pack(side=tk.LEFT, padx=2)
        tk.Label(header_bg, text="Causa de muerte", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_SECTION, width=26, anchor="w").pack(side=tk.LEFT, padx=2)
        tk.Label(header_bg, text="pH", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_SECTION, width=5, anchor="w").pack(side=tk.LEFT, padx=2)
        tk.Label(header_bg, text="Temp", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_SECTION, width=5, anchor="w").pack(side=tk.LEFT, padx=2)
        tk.Label(header_bg, text="O2", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_SECTION, width=5, anchor="w").pack(side=tk.LEFT, padx=2)
        tk.Label(header_bg, text="NH3", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_SECTION, width=7, anchor="w").pack(side=tk.LEFT, padx=2)
        tk.Label(header_bg, text="Circunstancia", font=("", 8, "bold"), fg=TEXT_DARK, bg=BG_SECTION, width=22, anchor="w").pack(side=tk.LEFT, padx=2)

        # Separador
        tk.Frame(inner, bg=TEXT_LIGHT_GRAY, height=1).pack(fill=tk.X, padx=20)

        # Recopilar todas las muertes ordenadas por hora
        all_deaths = []
        for pid in self.pecera_ids:
            for idx, log in enumerate(self.pecera_death_logs[pid]):
                all_deaths.append((pid, idx, log))

        # Mostrar solo las últimas 500 muertes para no saturar la UI
        max_show = 500
        if len(all_deaths) > max_show:
            info_label = tk.Label(inner, text=f"  Mostrando las últimas {max_show} de {len(all_deaths)} muertes totales.",
                                  font=("", 8), fg=TEXT_YELLOW, bg=BG_LIGHT)
            info_label.pack(pady=(5, 2))
            deaths_to_show = all_deaths[-max_show:]
        else:
            deaths_to_show = all_deaths

        muerte_num = 0
        for pid, idx, log in deaths_to_show:
            muerte_num += 1
            agua_snap = log.get("agua_snapshot", {})
            ph = agua_snap.get("ph", 0)
            temp = agua_snap.get("temperatura_c", 0)
            o2 = agua_snap.get("oxigeno_mg_l", 0)
            nh3 = agua_snap.get("amoniaco_mg_l", 0)
            hora = log.get("hora_sim", "?")
            pecera_nombre = log.get("pecera", "?")
            especie = log.get("especie", "?")
            causa = log.get("causa", "?")

            # Determinar circunstancia
            circunstancia = ""
            if nh3 > 0.3:
                circunstancia = "Amoniaco toxico"
            elif o2 < 4.0:
                circunstancia = "Oxigeno critico"
            elif ph < 6.0 or ph > 9.0:
                circunstancia = "pH extremo"
            elif temp < 18 or temp > 32:
                circunstancia = "Temp inadecuada"
            else:
                circunstancia = "Estrés acumulado"

            # Color de fondo alternado
            row_bg = BG_CARD if muerte_num % 2 == 0 else BG_LIGHT

            row_f = tk.Frame(inner, bg=row_bg, padx=5, pady=2)
            row_f.pack(fill=tk.X, padx=20, pady=0)

            tk.Label(row_f, text=str(muerte_num), font=("", 7), fg=TEXT_GRAY, bg=row_bg, width=4, anchor="w").pack(side=tk.LEFT)
            tk.Label(row_f, text=str(hora), font=("", 7), fg=TEXT_DARK, bg=row_bg, width=8, anchor="w").pack(side=tk.LEFT, padx=2)
            tk.Label(row_f, text=pecera_nombre, font=("", 7), fg=TEXT_BLUE, bg=row_bg, width=18, anchor="w").pack(side=tk.LEFT, padx=2)
            tk.Label(row_f, text=especie, font=("", 7), fg=TEXT_DARK, bg=row_bg, width=14, anchor="w").pack(side=tk.LEFT, padx=2)

            # Causa con color
            tk.Label(row_f, text=causa, font=("", 7), fg=TEXT_RED, bg=row_bg, width=26, anchor="w").pack(side=tk.LEFT, padx=2)

            # pH con color
            ph_color = TEXT_DARK if 6.0 <= ph <= 9.0 else TEXT_RED
            tk.Label(row_f, text=f"{ph:.1f}", font=("", 7), fg=ph_color, bg=row_bg, width=5, anchor="w").pack(side=tk.LEFT, padx=2)

            # Temp con color
            temp_color = TEXT_DARK if 18 <= temp <= 32 else TEXT_RED
            tk.Label(row_f, text=f"{temp:.0f}", font=("", 7), fg=temp_color, bg=row_bg, width=5, anchor="w").pack(side=tk.LEFT, padx=2)

            # O2 con color
            o2_color = TEXT_DARK if o2 >= 4.0 else TEXT_RED
            tk.Label(row_f, text=f"{o2:.1f}", font=("", 7), fg=o2_color, bg=row_bg, width=5, anchor="w").pack(side=tk.LEFT, padx=2)

            # NH3 con color
            nh3_color = TEXT_DARK if nh3 <= 0.3 else TEXT_RED
            tk.Label(row_f, text=f"{nh3:.3f}", font=("", 7), fg=nh3_color, bg=row_bg, width=7, anchor="w").pack(side=tk.LEFT, padx=2)

            # Circunstancia
            tk.Label(row_f, text=circunstancia, font=("", 7, "italic"), fg=TEXT_YELLOW, bg=row_bg, width=22, anchor="w").pack(side=tk.LEFT, padx=2)

        # Separador final
        tk.Label(inner, text="", bg=BG_LIGHT, height=2).pack()

        # Botón cerrar
        btn_frame = tk.Frame(inner, bg=BG_LIGHT)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        btn_close = tk.Button(btn_frame, text="Cerrar", font=("", 10), bg=BG_SECTION, fg=TEXT_DARK,
                              relief=tk.FLAT, cursor="hand2",
                              command=lambda: (win.destroy(), setattr(self, 'death_report_window', None)))
        btn_close.pack(side=tk.RIGHT)

    def _respawn_pecera(self, pecera_id):
        """Cuando todos los peces mueren, repoblar con especies aleatorias."""
        sim = self.sim_data[pecera_id]
        pdata = self.peceras[pecera_id]
        volumen = pdata["volumen_l"]

        # Elegir especies al azar de las disponibles en la base de datos
        especies_ids = list(self.especies.keys())
        num_especies = random.randint(1, min(3, len(especies_ids)))
        especies_elegidas = random.sample(especies_ids, num_especies)

        nueva_poblacion = []
        for esp_id in especies_elegidas:
            esp = self.especies[esp_id]
            cantidad = random.randint(5, 20)
            peso_g = random.randint(10, 200)
            nueva_poblacion.append({
                "vivos": cantidad,
                "peso_g": peso_g,
                "alimento_g_h": random.uniform(0.1, 1.0),
                "amoniaco_mg_por_g": random.uniform(0.01, 0.1),
                "consumo_o2": esp.get("consumo_o2", 0.5),
                "id_especie": esp_id,
                "cantidad_original": cantidad,
            })

        sim["poblacion_sim"] = nueva_poblacion
        sim["respawn_count"] = sim.get("respawn_count", 0) + 1

        # Reiniciar agua a valores más saludables para dar chance a los nuevos peces
        sim["agua"] = {
            "ph": random.uniform(6.5, 8.0),
            "temperatura_c": random.uniform(22, 28),
            "oxigeno_mg_l": random.uniform(5.0, 8.0),
            "amoniaco_mg_l": random.uniform(0.0, 0.2),
            "volumen_l": volumen,
        }

        # Marcar que necesita recrear peces visuales y stats
        card = self.pecera_cards.get(pecera_id)
        if card:
            card.needs_recreate = True

        # NO limpiar logs de muertes: el informe acumula datos de todos los ciclos
        print(f"[RESPAWN] [{pdata['nombre']}] Todos los peces murieron! Repoblando con {num_especies} especie(s) (ciclo #{sim['respawn_count']})")

    def _build_ui(self):
        # === Layout principal con grid: fila 0=barra, fila 1=peceras ===
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # === Barra superior de controles (fila 0) ===
        top_bar = tk.Frame(self.root, bg=BG_SECTION, padx=15, pady=8)
        top_bar.grid(row=0, column=0, sticky="ew")

        tk.Label(top_bar, text="🐟 Simulación de Mortalidad Acuícola",
                 font=("", 14, "bold"), fg=TEXT_DARK, bg=BG_SECTION).pack(side=tk.LEFT, padx=10)

        self.lbl_tiempo = tk.Label(top_bar, text="Día 0 - Hora 0:00",
                                    font=("", 11, "bold"), fg=TEXT_BLUE, bg=BG_SECTION)
        self.lbl_tiempo.pack(side=tk.LEFT, padx=15)

        self.btn_iniciar = tk.Button(top_bar, text="▶ Iniciar", command=self.toggle_sim,
                                      bg=TEXT_GREEN, fg="white", font=("", 10, "bold"),
                                      relief=tk.FLAT, cursor="hand2", padx=15, pady=5)
        self.btn_iniciar.pack(side=tk.LEFT, padx=5)

        self.btn_reiniciar = tk.Button(top_bar, text="↻ Reiniciar", command=self.reiniciar,
                                        bg=TEXT_GRAY, fg="white", font=("", 10, "bold"),
                                        relief=tk.FLAT, cursor="hand2", padx=15, pady=5)
        self.btn_reiniciar.pack(side=tk.LEFT, padx=5)

        tk.Label(top_bar, text="Velocidad:", font=("", 10), fg=TEXT_GRAY, bg=BG_SECTION).pack(side=tk.LEFT, padx=(15, 5))
        self.vel_var = tk.StringVar(value="8x (rápido)")
        vel_menu = tk.OptionMenu(
            top_bar, self.vel_var, "1x", "2x", "4x", "8x (rápido)", "16x", "32x", "64x (ultra)",
            command=lambda v: None
        )
        vel_menu.config(font=("", 9), bg=BG_CARD, fg=TEXT_DARK, relief=tk.FLAT, cursor="hand2")
        vel_menu.pack(side=tk.LEFT, padx=5)

        # Resumen global
        self.lbl_resumen = tk.Label(top_bar, text="", font=("", 10), fg=TEXT_GREEN, bg=BG_SECTION)
        self.lbl_resumen.pack(side=tk.RIGHT, padx=15)

        # Botón para abrir informe de muertes
        self.btn_informe = tk.Button(top_bar, text="📊 Informe de Muertes", command=self._open_death_report,
                                      bg=TEXT_BLUE, fg="white", font=("", 10, "bold"),
                                      relief=tk.FLAT, cursor="hand2", padx=15, pady=5)
        self.btn_informe.pack(side=tk.LEFT, padx=5)

        # Botón para exportar manualmente a Excel
        self.btn_export = tk.Button(top_bar, text="📁 Exportar Excel", command=self._export_excel_manual,
                                     bg=TEXT_GREEN, fg="white", font=("", 10, "bold"),
                                     relief=tk.FLAT, cursor="hand2", padx=15, pady=5)
        self.btn_export.pack(side=tk.LEFT, padx=5)

        # Label de estado de exportación
        self.lbl_export = tk.Label(top_bar, text="📁 Export: esperando...",
                                    font=("", 9), fg=TEXT_GRAY, bg=BG_SECTION)
        self.lbl_export.pack(side=tk.RIGHT, padx=(0, 15))

        # === Área principal con peceras (fila 1) ===
        main_canvas = tk.Canvas(self.root, bg=BG_LIGHT, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.root, command=main_canvas.yview, bg=BG_SECTION, troughcolor=BG_LIGHT, width=15)
        self.scroll_frame = tk.Frame(main_canvas, bg=BG_LIGHT)

        self.scroll_frame.bind("<Configure>", lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")))
        main_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        main_canvas.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 5))
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(5, 5))

        def _on_mousewheel(event):
            main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        main_canvas.bind("<MouseWheel>", _on_mousewheel)
        self.scroll_frame.bind("<MouseWheel>", _on_mousewheel)

        # === Crear tarjetas de peceras ===
        self.pecera_cards = {}
        num_peceras = len(self.pecera_ids)

        # Calcular columnas según cantidad de peceras
        if num_peceras <= 4:
            cols = 2
        elif num_peceras <= 6:
            cols = 3
        else:
            cols = 4

        row = 0
        col = 0
        for i, pid in enumerate(self.pecera_ids):
            color_idx = i % len(PEZERA_COLORES)
            card = PeceraCard(
                self.scroll_frame, pid, self.peceras[pid], self.sim_data[pid],
                self.especies, PEZERA_COLORES[color_idx],
                lambda p=pid: self._show_detail(p)
            )
            card.card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            self.pecera_cards[pid] = card
            col += 1
            if col >= cols:
                col = 0
                row += 1

        # Configurar pesos de columnas
        for c in range(cols):
            self.scroll_frame.grid_columnconfigure(c, weight=1)
        for r in range(row + 1):
            self.scroll_frame.grid_rowconfigure(r, weight=0)

        # Iniciar animación
        self._animate_all()
        # Iniciar simulación automáticamente - nunca para
        self._tick()

    def _show_detail(self, pecera_id):
        """Muestra ventana con todos los detalles de una pecera."""
        detail_win = tk.Toplevel(self.root)
        detail_win.title(f"Detalles - {self.peceras[pecera_id]['nombre']}")
        detail_win.geometry("500x600")
        detail_win.configure(bg=BG_LIGHT)

        # Scroll
        d_canvas = tk.Canvas(detail_win, bg=BG_LIGHT, highlightthickness=0)
        d_scroll = tk.Scrollbar(detail_win, command=d_canvas.yview, bg=BG_SECTION, width=15)
        d_frame = tk.Frame(d_canvas, bg=BG_LIGHT)
        d_frame.bind("<Configure>", lambda e: d_canvas.configure(scrollregion=d_canvas.bbox("all")))
        d_canvas.create_window((0, 0), window=d_frame, anchor="nw")
        d_canvas.configure(yscrollcommand=d_scroll.set)
        d_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        d_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        sim = self.sim_data[pecera_id]
        agua = sim["agua"]
        eq = sim["equipos"]
        pdata = self.peceras[pecera_id]

        # Título
        tk.Label(d_frame, text=f"{pdata['nombre']}", font=("", 16, "bold"),
                 fg=TEXT_DARK, bg=BG_LIGHT).pack(pady=(15, 3))
        tk.Label(d_frame, text=f"Volumen: {pdata['volumen_l']}L", font=("", 10),
                 fg=TEXT_GRAY, bg=BG_LIGHT).pack(pady=(0, 15))

        # Agua
        tk.Label(d_frame, text="💧 Condiciones del Agua", font=("", 12, "bold"),
                 fg=TEXT_DARK, bg=BG_LIGHT).pack(pady=(10, 5))
        agua_card = tk.Frame(d_frame, bg=BG_CARD, padx=15, pady=10)
        agua_card.pack(fill=tk.X, padx=20)
        for label, val in [("pH:", f"{agua['ph']:.2f}"), ("Temperatura:", f"{agua['temperatura_c']:.1f} °C"),
                           ("Oxígeno:", f"{agua['oxigeno_mg_l']:.2f} mg/L"), ("Amoniaco:", f"{agua['amoniaco_mg_l']:.4f} mg/L")]:
            row_f = tk.Frame(agua_card, bg=BG_CARD)
            row_f.pack(fill=tk.X, pady=2)
            tk.Label(row_f, text=label, font=("", 10), fg=TEXT_GRAY, bg=BG_CARD, width=14, anchor="w").pack(side=tk.LEFT)
            tk.Label(row_f, text=val, font=("", 10, "bold"), fg=TEXT_DARK, bg=BG_CARD).pack(side=tk.LEFT)

        # Equipos
        tk.Label(d_frame, text="🔧 Equipos", font=("", 12, "bold"),
                 fg=TEXT_DARK, bg=BG_LIGHT).pack(pady=(15, 5))
        eq_card = tk.Frame(d_frame, bg=BG_CARD, padx=15, pady=10)
        eq_card.pack(fill=tk.X, padx=20)
        for label, val in [("Filtro:", f"{eq.get('filtro_remocion_mg_h', 0):.1f} mg/h"),
                           ("Aireación:", f"{eq.get('aireacion_mg_h', 0):.1f} mg/h")]:
            row_f = tk.Frame(eq_card, bg=BG_CARD)
            row_f.pack(fill=tk.X, pady=2)
            tk.Label(row_f, text=label, font=("", 10), fg=TEXT_GRAY, bg=BG_CARD, width=14, anchor="w").pack(side=tk.LEFT)
            tk.Label(row_f, text=val, font=("", 10, "bold"), fg=TEXT_DARK, bg=BG_CARD).pack(side=tk.LEFT)

        # Población
        tk.Label(d_frame, text="🐠 Población", font=("", 12, "bold"),
                 fg=TEXT_DARK, bg=BG_LIGHT).pack(pady=(15, 5))
        for pop in sim["poblacion_sim"]:
            esp = self.especies.get(pop["id_especie"], {})
            esp_name = esp.get('nombre', '?')
            pop_card = tk.Frame(d_frame, bg=BG_CARD, padx=15, pady=8)
            pop_card.pack(fill=tk.X, padx=20, pady=(0, 5))
            tk.Label(pop_card, text=esp_name, font=("", 11, "bold"), fg=TEXT_BLUE, bg=BG_CARD).pack(anchor=tk.W, pady=(0, 5))
            total = pop.get("cantidad_original", pop.get("vivos", 0))
            for label, val in [("Vivos:", f"{pop['vivos']}/{total}"), ("Muertos:", f"{total - pop['vivos']}",),
                               ("Peso:", f"{pop['peso_g']} g"), ("Alimento:", f"{pop['alimento_g_h']} g/h")]:
                row_f = tk.Frame(pop_card, bg=BG_CARD)
                row_f.pack(fill=tk.X, pady=1)
                tk.Label(row_f, text=f"  {label}", font=("", 9), fg=TEXT_GRAY, bg=BG_CARD, anchor="w").pack(side=tk.LEFT)
                tk.Label(row_f, text=val, font=("", 9, "bold"), fg=TEXT_DARK, bg=BG_CARD).pack(side=tk.LEFT)
            ratio = pop["vivos"] / max(total, 1)
            bar_canvas = tk.Canvas(pop_card, width=200, height=8, bg=BG_SECTION, highlightthickness=0)
            bar_canvas.pack(fill=tk.X, pady=(5, 0))
            bar_color = TEXT_GREEN if ratio > 0.5 else TEXT_YELLOW if ratio > 0.25 else TEXT_RED
            bar_w = int(200 * ratio)
            if bar_w > 0:
                bar_canvas.create_rectangle(0, 0, bar_w, 8, fill=bar_color, outline="")

        # Diagnóstico
        tk.Label(d_frame, text="🔍 Diagnóstico", font=("", 12, "bold"),
                 fg=TEXT_DARK, bg=BG_LIGHT).pack(pady=(15, 5))
        diag_card = tk.Frame(d_frame, bg=BG_CARD, padx=15, pady=10)
        diag_card.pack(fill=tk.X, padx=20)
        if sim["poblacion_sim"]:
            biomasa = sum(pop["vivos"] * pop["peso_g"] / 1000 for pop in sim["poblacion_sim"])
            volumen = agua["volumen_l"]
            densidad = (biomasa / volumen) * 1000 if volumen > 0 else 0
            first_esp = self.especies.get(sim["poblacion_sim"][0]["id_especie"], {})
            problemas = explicar_condiciones(agua, first_esp, eq, densidad)
            if problemas:
                tk.Label(diag_card, text="⚠️  Problemas detectados:", font=("", 10, "bold"),
                         fg=TEXT_RED, bg=BG_CARD).pack(anchor=tk.W, pady=(0, 5))
                for prob in problemas[:8]:
                    tk.Label(diag_card, text=f"  • {prob}", font=("", 9),
                             fg=TEXT_YELLOW, bg=BG_CARD).pack(anchor=tk.W, pady=1)
            else:
                tk.Label(diag_card, text="✅ Todo parece normal", font=("", 10),
                         fg=TEXT_GREEN, bg=BG_CARD).pack(anchor=tk.W, pady=5)

        tk.Label(d_frame, text="", bg=BG_LIGHT).pack(pady=30)

        def _on_mousewheel(event):
            d_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        d_canvas.bind("<MouseWheel>", _on_mousewheel)
        d_frame.bind("<MouseWheel>", _on_mousewheel)

    def toggle_sim(self):
        # La simulación nunca se detiene, el botón solo es visual
        pass

    def reiniciar(self):
        self.tick_count = 0
        self.day = 0
        self.hour = 0
        for pid in self.pecera_ids:
            self.sim_data[pid] = self._init_sim_data(pid)
            card = self.pecera_cards[pid]
            card.canvas.delete("all")
            card.peces = []
            card._draw_tank_bg()
            card._create_fish()
            card.update_stats()
        self.lbl_tiempo.config(text="Día 0 - Hora 0:00")
        self._update_resumen()
        # Limpiar logs de muertes por pecera
        for pid in self.pecera_ids:
            self.pecera_death_logs[pid] = []
        self.total_deaths = 0
        # Cerrar ventana de informe si está abierta
        if self.death_report_window is not None and self.death_report_window.winfo_exists():
            self.death_report_window.destroy()
            self.death_report_window = None
        # Resetear variables de exportación
        self.last_export_hour = -1
        self.export_count = 0
        if hasattr(self, "lbl_export"):
            self.lbl_export.config(text="📁 Export: esperando...", fg=TEXT_GRAY)

    def _get_sim_steps(self):
        """Cuántos pasos de simulación por tick."""
        val = self.vel_var.get()
        if "64x" in val: return 8
        elif "32x" in val: return 4
        elif "16x" in val: return 2
        elif "8x" in val: return 1
        elif "4x" in val: return 1
        elif "2x" in val: return 1
        else: return 1

    def _get_sim_interval(self):
        """Intervalo en ms entre ticks de simulación + update de datos."""
        val = self.vel_var.get()
        if "64x" in val: return 50
        elif "32x" in val: return 80
        elif "16x" in val: return 120
        elif "8x" in val: return 200
        elif "4x" in val: return 400
        elif "2x" in val: return 800
        else: return 1500

    def _update_resumen(self):
        """Actualiza el resumen global de supervivencia."""
        total_peces = 0
        total_vivos = 0
        for pid in self.pecera_ids:
            for pop in self.sim_data[pid]["poblacion_sim"]:
                total_peces += pop.get("cantidad_original", 0)
                total_vivos += pop["vivos"]
        pct = (total_vivos / max(total_peces, 1)) * 100
        color = TEXT_GREEN if pct > 50 else TEXT_YELLOW if pct > 25 else TEXT_RED
        self.lbl_resumen.config(text=f"Supervivencia global: {total_vivos}/{total_peces} ({pct:.0f}%)", fg=color)

    def _sim_step(self):
        """Un solo paso de simulación para todas las peceras (sin UI)."""
        for pid in self.pecera_ids:
            sim = self.sim_data[pid]
            agua = sim["agua"]
            eq = sim["equipos"]
            poblacion = sim["poblacion_sim"]

            # Evolucionar agua
            agua = evolucionar_agua(agua, eq, poblacion)
            sim["agua"] = agua

            biomasa = sum(pop["vivos"] * pop["peso_g"] / 1000 for pop in poblacion)
            volumen = agua["volumen_l"]
            densidad = (biomasa / volumen) * 1000 if volumen > 0 else 0

            # Evaluar eventos para cada especie
            for pop in poblacion:
                esp = self.especies.get(pop["id_especie"], {})
                if pop["vivos"] <= 0:
                    continue

                dano_ph = calcular_dano_ph(agua["ph"], esp.get("ph_min", 6.5), esp.get("ph_max", 8.5))
                dano_temp = calcular_dano_temp(agua["temperatura_c"], esp.get("temp_min", 20), esp.get("temp_max", 30))
                dano_ox = calcular_dano_oxigeno(agua["oxigeno_mg_l"], esp.get("oxigeno_min", 5.0))
                dano_nh3 = calcular_dano_amoniaco(agua["amoniaco_mg_l"], esp.get("amoniaco_max", 0.5))
                dano_dens = calcular_dano_densidad(biomasa, volumen)
                dano_total = dano_ph + dano_temp + dano_ox + dano_nh3 + dano_dens

                if pop["vivos"] > 0:
                    muertes = max(0, int(pop["vivos"] * dano_total / 100))
                    if muertes > 0:
                        # Determinar causa principal de muerte
                        danos = [
                            ("Envenenamiento por amoniaco", dano_nh3),
                            ("Falta de oxígeno", dano_ox),
                            ("pH fuera de rango", dano_ph),
                            ("Temperatura inadecuada", dano_temp),
                            ("Sobrepoblación", dano_dens),
                        ]
                        danos.sort(key=lambda x: x[1], reverse=True)
                        causa_principal = danos[0][0] if danos[0][1] > 0 else "Causas múltiples"

                        esp_nombre = esp.get("nombre", "?")
                        pdata = self.peceras[pid]

                        # Registrar CADA muerte individual y reponer al instante
                        for _ in range(muertes):
                            # Log de muerte individual
                            self.pecera_death_logs[pid].append({
                                "causa": causa_principal,
                                "especie": esp_nombre,
                                "cantidad": 1,
                                "agua_snapshot": dict(agua),
                                "hora_sim": self.day * 24 + self.hour,
                                "pecera": pdata["nombre"],
                            })
                            self.total_deaths += 1

                            # Reponer con un pez al azar de la misma especie
                            pop["vivos"] += 1  # mantener el conteo estable

            # Ya no verificar si todos murieron - cada muerte se repone al instante

    def _update_visuals(self):
        """Actualizar toda la UI una vez después de los pasos de simulación."""
        for pid in self.pecera_ids:
            sim = self.sim_data[pid]
            poblacion = sim["poblacion_sim"]
            agua = sim["agua"]
            card = self.pecera_cards.get(pid)
            if card is None:
                continue

            # Si hubo respawn, recrear todo
            if card.needs_recreate:
                card.recreate_on_respawn()

            total_anim = len(card.peces)
            total_vivos_sim = sum(pop["vivos"] for pop in poblacion)
            total_original = sum(pop.get("cantidad_original", 0) for pop in poblacion)

            if total_original > 0:
                ratio_vivos = total_vivos_sim / total_original
                peces_deberian_estar_vivos = max(0, int(total_anim * ratio_vivos))
                peces_vivos_actual = sum(1 for p in card.peces if p.vivo)

                if peces_vivos_actual > peces_deberian_estar_vivos:
                    for p in card.peces:
                        if peces_vivos_actual <= peces_deberian_estar_vivos:
                            break
                        if p.vivo and random.random() < 0.3:
                            p.vivo = False
                            p.sinking = True
                            p.sink_speed = random.uniform(0.2, 0.6)
                            p.salud = 0
                            peces_vivos_actual -= 1
                elif peces_vivos_actual < peces_deberian_estar_vivos:
                    for p in card.peces:
                        if peces_vivos_actual >= peces_deberian_estar_vivos:
                            break
                        if not p.vivo:
                            p.vivo = True
                            p.sinking = False
                            p.salud = 50
                            peces_vivos_actual += 1

            # Daño visual por condiciones extremas
            for pez in card.peces:
                if pez.vivo:
                    if agua["amoniaco_mg_l"] > 0.5:
                        pez.salud -= agua["amoniaco_mg_l"]
                    if agua["oxigeno_mg_l"] < 3:
                        pez.salud -= (3 - agua["oxigeno_mg_l"])
                    if pez.salud <= 0 and pez.vivo:
                        pez.salud = 0
                        pez.vivo = False
                        pez.sinking = True
                        pez.sink_speed = random.uniform(0.2, 0.6)

            card.update_stats()

        self.lbl_tiempo.config(text=f"Día {self.day} - Hora {self.hour}:00")
        self._update_resumen()

    def _tick(self):
        # La simulación nunca se detiene - siempre avanza
        # Ejecutar N pasos de simulación sin tocar la UI
        steps = self._get_sim_steps()
        for _ in range(steps):
            self._sim_step()
            self.tick_count += 1
            self.day = self.tick_count // 24
            self.hour = self.tick_count % 24

        # Exportar a Excel cada 6 horas de simulación
        self._export_excel()

        # Actualizar UI una sola vez al final
        self._update_visuals()

        # Programar siguiente tick - nunca para
        interval = self._get_sim_interval()
        self.root.after(interval, self._tick)

    def _animate_all(self):
        """Animación continua de todos los estanques - independiente de simulación."""
        for pid, card in self.pecera_cards.items():
            card.animate()
        self.root.after(30, self._animate_all)


def main():
    try:
        with conectar_bd() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        tk.messagebox.showerror("Error de conexión", f"No se pudo conectar a PostgreSQL:\n{e}")
        root.destroy()
        return 1

    root = tk.Tk()
    app = SimulacionTodasPeceras(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
