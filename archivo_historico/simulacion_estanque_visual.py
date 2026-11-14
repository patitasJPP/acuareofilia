"""
Simulación visual del estanque con peces animados y panel de datos.

Muestra el estanque con peces nadando a un lado y los datos en tiempo real al otro.
Diseño minimalista blanco, enfocado en la rapidez de la simulación.
"""

import tkinter as tk
import math
import random
import time

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


class PezAnimado:
    """Pez animado que nada en el estanque."""
    
    def __init__(self, canvas, x, y, color, especie_nombre, size=12):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.color = color
        self.size = size
        self.especie = especie_nombre
        self.salud = 100.0
        self.vivo = True
        self.angle = random.uniform(0, 2 * math.pi)
        self.speed = random.uniform(0.5, 2.0)
        self.turn_speed = random.uniform(0.02, 0.06)
        self.wiggle = 0
        self.wiggle_speed = random.uniform(0.1, 0.3)
        self.sinking = False
        self.sink_speed = 0
        self.id = id(self)
        
        # Dibujar el pez
        self.body_id = canvas.create_oval(0, 0, 0, 0, fill=self.color, outline="", tags=f"pez_{self.id}")
        self.tail_id = canvas.create_polygon(0, 0, 0, 0, 0, 0, fill=self.color, outline="", tags=f"pez_{self.id}")
        self.eye_id = canvas.create_oval(0, 0, 0, 0, fill="white", outline="", tags=f"pez_{self.id}")
        self.pupil_id = canvas.create_oval(0, 0, 0, 0, fill="black", outline="", tags=f"pez_{self.id}")
    
    def update_position(self, tank_width, tank_height, floor_y):
        """Actualiza posición y redibuja el pez."""
        if self.sinking:
            # Pez muerto hundido
            self.y += self.sink_speed
            if self.y >= floor_y - self.size:
                self.y = floor_y - self.size
                self.sink_speed = 0
            self.angle = math.pi / 2  # boca arriba
        else:
            # Movimiento natural
            self.wiggle += self.wiggle_speed
            self.angle += random.uniform(-self.turn_speed, self.turn_speed)
            
            # Cambiar dirección aleatoriamente
            if random.random() < 0.02:
                self.angle += random.uniform(0.5, 1.5)
            
            # Velocidad según salud
            speed_mult = self.salud / 100.0
            if self.salud < 30:
                speed_mult *= 0.3  # muy lento si está enfermo
            
            dx = math.cos(self.angle) * self.speed * speed_mult
            dy = math.sin(self.angle) * self.speed * speed_mult * 0.5  # menos movimiento vertical
            
            self.x += dx
            self.y += dy
            
            # Límites del tanque
            margin = self.size
            if self.x < margin:
                self.x = margin
                self.angle = 0
            elif self.x > tank_width - margin:
                self.x = tank_width - margin
                self.angle = math.pi
            
            if self.y < margin:
                self.y = margin
                self.angle = math.pi / 2
            elif self.y > floor_y - margin:
                self.y = floor_y - margin
                self.angle = -math.pi / 2
        
        # Color según salud
        if not self.vivo:
            display_color = "#95a5a6"  # gris muerto
        elif self.salud > 70:
            display_color = self.color
        elif self.salud > 30:
            display_color = TEXT_YELLOW
        else:
            display_color = TEXT_RED
        
        # Dibujar cuerpo
        s = self.size
        wiggle_offset = math.sin(self.wiggle) * 2 if self.vivo else 0
        
        body_x1 = self.x - s
        body_y1 = self.y - s * 0.5 + wiggle_offset
        body_x2 = self.x + s
        body_y2 = self.y + s * 0.5 + wiggle_offset
        
        self.canvas.coords(self.body_id, body_x1, body_y1, body_x2, body_y2)
        self.canvas.itemconfig(self.body_id, fill=display_color)
        
        # Dibujar cola
        tail_dir = -1 if self.angle > math.pi / 2 or self.angle < -math.pi / 2 else 1
        tail_x = self.x - tail_dir * s * 1.2
        tail_y_base = self.y + wiggle_offset
        tail_wiggle = math.sin(self.wiggle * 2) * 4 if self.vivo else 0
        
        tail_points = [
            self.x - tail_dir * s * 0.5, tail_y_base - s * 0.2,
            tail_x, tail_y_base - s * 0.7 + tail_wiggle,
            tail_x, tail_y_base + s * 0.7 + tail_wiggle,
            self.x - tail_dir * s * 0.5, tail_y_base + s * 0.2,
        ]
        self.canvas.coords(self.tail_id, *tail_points)
        self.canvas.itemconfig(self.tail_id, fill=display_color)
        
        # Dibujar ojo
        eye_dir = tail_dir
        eye_x = self.x + eye_dir * s * 0.4
        eye_y = self.y - s * 0.15 + wiggle_offset
        eye_size = 3
        
        self.canvas.coords(self.eye_id, eye_x - eye_size, eye_y - eye_size, eye_x + eye_size, eye_y + eye_size)
        self.canvas.coords(self.pupil_id, eye_x - 1.5 + eye_dir * 1, eye_y - 1.5, eye_x + 1.5 + eye_dir * 1, eye_y + 1.5)
        
        if not self.vivo:
            # X en lugar de ojo
            self.canvas.itemconfig(self.eye_id, fill=display_color)
            self.canvas.itemconfig(self.pupil_id, fill=TEXT_RED)


class Burbuja:
    """Burbuja de aireación animada."""
    
    def __init__(self, canvas, x, y):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.speed = random.uniform(0.5, 1.5)
        self.size = random.uniform(2, 5)
        self.wobble = random.uniform(0, 2 * math.pi)
        self.id = canvas.create_oval(0, 0, 0, 0, outline="#aed6f1", fill="", width=1)
    
    def update(self, floor_y):
        self.y -= self.speed
        self.wobble += 0.05
        wobble_x = self.x + math.sin(self.wobble) * 3
        
        s = self.size
        self.canvas.coords(self.id, wobble_x - s, self.y - s, wobble_x + s, self.y + s)
        
        return self.y > 0  # sigue viva si está arriba del agua


class SimulacionEstanque:
    def __init__(self, root):
        self.root = root
        self.root.title("🐟 Simulación de Estanque - Mortalidad Acuícola")
        self.root.geometry("1400x800")
        self.root.minsize(1200, 700)
        self.root.configure(bg=BG_WHITE)
        
        # Estado
        self.running = False
        self.tick_count = 0
        self.day = 0
        self.hour = 0
        
        # Cargar datos
        self.peceras, self.estado, self.equipos, self.especies, self.poblaciones = consultar_datos_iniciales()
        
        # Pecera seleccionada
        self.selected_pecera_id = list(self.peceras.keys())[0]
        
        # Estado simulado por pecera
        self.sim_data = {}
        for pid in self.peceras:
            self.sim_data[pid] = self._init_sim_data(pid)
        
        self._build_ui()
    
    def _init_sim_data(self, pecera_id):
        """Inicializa los datos de simulación para una pecera."""
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
        }
    
    def _build_ui(self):
        """Construye la interfaz dividida: estanque + panel de datos."""
        
        # Frame principal dividido
        main_frame = tk.Frame(self.root, bg=BG_WHITE)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # === IZQUIERDA: Estanque visual ===
        tank_frame = tk.Frame(main_frame, bg=BG_WHITE)
        tank_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Título del estanque
        tk.Label(tank_frame, text="🐟 Vista del Estanque",
                 font=("", 12, "bold"), fg=TEXT_DARK, bg=BG_WHITE).pack(pady=(0, 5))
        
        # Canvas del estanque
        self.tank_canvas = tk.Canvas(tank_frame, bg=AQUA_WATER, highlightthickness=1, highlightbackground=TEXT_LIGHT_GRAY)
        self.tank_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Selector de pecera debajo del estanque
        selector_frame = tk.Frame(tank_frame, bg=BG_WHITE, pady=5)
        selector_frame.pack(fill=tk.X)
        
        tk.Label(selector_frame, text="Pecera:", font=("", 9), fg=TEXT_GRAY, bg=BG_WHITE).pack(side=tk.LEFT, padx=5)
        
        self.pecera_var = tk.StringVar(value=self.selected_pecera_id)
        pecera_menu = tk.OptionMenu(
            selector_frame, self.pecera_var, *self.peceras.keys(),
            command=self._on_pecera_changed
        )
        pecera_menu.config(font=("", 9), bg=BG_CARD, fg=TEXT_DARK, relief=tk.FLAT, cursor="hand2")
        pecera_menu.pack(side=tk.LEFT, padx=5)
        
        # === DERECHA: Panel de datos ===
        data_frame = tk.Frame(main_frame, bg=BG_LIGHT, width=380)
        data_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        data_frame.pack_propagate(False)
        
        # Título del panel
        tk.Label(data_frame, text="📊 Datos en Tiempo Real",
                 font=("", 12, "bold"), fg=TEXT_DARK, bg=BG_LIGHT).pack(pady=(10, 5))
        
        # Scroll para datos
        data_canvas = tk.Canvas(data_frame, bg=BG_LIGHT, highlightthickness=0)
        data_scrollbar = tk.Scrollbar(data_frame, command=data_canvas.yview, bg=BG_SECTION,
                                      troughcolor=BG_LIGHT, width=15)
        self.scroll_data_frame = tk.Frame(data_canvas, bg=BG_LIGHT)
        
        self.scroll_data_frame.bind("<Configure>", lambda e: data_canvas.configure(scrollregion=data_canvas.bbox("all")))
        data_canvas.create_window((0, 0), window=self.scroll_data_frame, anchor="nw")
        data_canvas.configure(yscrollcommand=data_scrollbar.set)
        data_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        data_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5))
        
        def _on_mousewheel(event):
            data_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        data_canvas.bind("<MouseWheel>", _on_mousewheel)
        self.scroll_data_frame.bind("<MouseWheel>", _on_mousewheel)
        
        # Controles
        self._build_controls(data_frame)
        
        # Construir contenido del panel de datos
        self._build_data_panel()
        
        # Inicializar peces y burbujas
        self.peces_animados = []
        self.burbujas = []
        self._init_tank_visuals()
        
        # Iniciar animación del canvas
        self._animate_tank()
    
    def _build_controls(self, parent):
        """Barra de controles."""
        ctrl_frame = tk.Frame(parent, bg=BG_SECTION, padx=10, pady=8)
        ctrl_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        # Tiempo
        self.lbl_tiempo = tk.Label(ctrl_frame, text="Día 0 - Hora 0:00",
                                    font=("", 10, "bold"), fg=TEXT_BLUE, bg=BG_SECTION)
        self.lbl_tiempo.pack(side=tk.LEFT, padx=5)
        
        # Iniciar/Pausar
        self.btn_iniciar = tk.Button(ctrl_frame, text="▶ Iniciar", command=self.toggle_sim,
                                      bg=TEXT_GREEN, fg="white", font=("", 9, "bold"),
                                      relief=tk.FLAT, cursor="hand2", padx=10, pady=4)
        self.btn_iniciar.pack(side=tk.LEFT, padx=3)
        
        # Reiniciar
        self.btn_reiniciar = tk.Button(ctrl_frame, text="↻ Reiniciar", command=self.reiniciar,
                                        bg=TEXT_GRAY, fg="white", font=("", 9, "bold"),
                                        relief=tk.FLAT, cursor="hand2", padx=10, pady=4)
        self.btn_reiniciar.pack(side=tk.LEFT, padx=3)
        
        # Velocidad
        tk.Label(ctrl_frame, text="Vel:", font=("", 9), fg=TEXT_GRAY, bg=BG_SECTION).pack(side=tk.LEFT, padx=(10, 3))
        self.vel_var = tk.StringVar(value="8x (rápido)")
        self.vel_menu = tk.OptionMenu(
            ctrl_frame, self.vel_var, "1x", "2x", "4x", "8x (rápido)", "16x", "32x", "64x (ultra)",
            command=self._update_speed
        )
        self.vel_menu.config(font=("", 8), bg=BG_CARD, fg=TEXT_DARK, relief=tk.FLAT, cursor="hand2")
        self.vel_menu.pack(side=tk.LEFT, padx=3)
    
    def _build_data_panel(self):
        """Construye el panel de datos de la pecera seleccionada."""
        # Limpiar contenido anterior
        for widget in self.scroll_data_frame.winfo_children():
            widget.destroy()
        
        pid = self.selected_pecera_id
        pdata = self.peceras[pid]
        sim = self.sim_data[pid]
        agua = sim["agua"]
        eq = sim["equipos"]
        
        # Nombre de la pecera
        tk.Label(self.scroll_data_frame, text=f"{pdata['nombre']}",
                 font=("", 14, "bold"), fg=TEXT_DARK, bg=BG_LIGHT).pack(pady=(5, 2))
        tk.Label(self.scroll_data_frame, text=f"Volumen: {pdata['volumen_l']}L",
                 font=("", 10), fg=TEXT_GRAY, bg=BG_LIGHT).pack(pady=(0, 8))
        
        # === Condiciones del agua ===
        self._add_section(self.scroll_data_frame, "💧 Condiciones del Agua")
        agua_card = tk.Frame(self.scroll_data_frame, bg=BG_CARD, padx=12, pady=8)
        agua_card.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        agua_items = [
            ("pH:", f"{agua['ph']:.2f}"),
            ("Temperatura:", f"{agua['temperatura_c']:.1f} °C"),
            ("Oxígeno:", f"{agua['oxigeno_mg_l']:.2f} mg/L"),
            ("Amoniaco:", f"{agua['amoniaco_mg_l']:.4f} mg/L"),
        ]
        
        for label, value in agua_items:
            row = tk.Frame(agua_card, bg=BG_CARD)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label, font=("", 10), fg=TEXT_GRAY, bg=BG_CARD, width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, font=("", 10, "bold"), fg=TEXT_DARK, bg=BG_CARD).pack(side=tk.LEFT)
        
        # === Equipos ===
        self._add_section(self.scroll_data_frame, "🔧 Equipos")
        eq_card = tk.Frame(self.scroll_data_frame, bg=BG_CARD, padx=12, pady=8)
        eq_card.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        eq_items = [
            ("Filtro:", f"{eq.get('filtro_remocion_mg_h', 0):.1f} mg/h"),
            ("Aireación:", f"{eq.get('aireacion_mg_h', 0):.1f} mg/h"),
        ]
        for label, value in eq_items:
            row = tk.Frame(eq_card, bg=BG_CARD)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label, font=("", 10), fg=TEXT_GRAY, bg=BG_CARD, width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, font=("", 10, "bold"), fg=TEXT_DARK, bg=BG_CARD).pack(side=tk.LEFT)
        
        # === Población ===
        self._add_section(self.scroll_data_frame, "🐠 Población")
        
        for pop in sim["poblacion_sim"]:
            esp = self.especies.get(pop["id_especie"], {})
            esp_name = esp.get('nombre', 'Desconocida')
            
            pop_card = tk.Frame(self.scroll_data_frame, bg=BG_CARD, padx=12, pady=8)
            pop_card.pack(fill=tk.X, padx=10, pady=(0, 5))
            
            tk.Label(pop_card, text=esp_name, font=("", 10, "bold"), fg=TEXT_BLUE, bg=BG_CARD).pack(anchor=tk.W, pady=(0, 4))
            
            pop_items = [
                ("Vivos:", f"{pop['vivos']}/{pop['cantidad_original']}"),
                ("Muertos:", f"{pop['cantidad_original'] - pop['vivos']}"),
                ("Peso:", f"{pop['peso_g']} g"),
                ("Alimento:", f"{pop['alimento_g_h']} g/h"),
            ]
            for label, value in pop_items:
                row = tk.Frame(pop_card, bg=BG_CARD)
                row.pack(fill=tk.X, pady=1)
                tk.Label(row, text=f"  {label}", font=("", 9), fg=TEXT_GRAY, bg=BG_CARD, anchor="w").pack(side=tk.LEFT)
                tk.Label(row, text=value, font=("", 9, "bold"), fg=TEXT_DARK, bg=BG_CARD).pack(side=tk.LEFT)
            
            # Barra de supervivencia
            ratio = pop["vivos"] / max(pop["cantidad_original"], 1)
            bar_frame = tk.Frame(pop_card, bg=BG_SECTION, height=8)
            bar_frame.pack(fill=tk.X, pady=(5, 0))
            bar_color = TEXT_GREEN if ratio > 0.5 else TEXT_YELLOW if ratio > 0.25 else TEXT_RED
            bar_width = int(200 * ratio)
            if bar_width > 0:
                tk.Canvas(bar_frame, width=bar_width, height=8, bg=bar_color, highlightthickness=0).pack(side=tk.LEFT)
        
        # === Diagnóstico ===
        self._add_section(self.scroll_data_frame, "🔍 Diagnóstico")
        diag_card = tk.Frame(self.scroll_data_frame, bg=BG_CARD, padx=12, pady=8)
        diag_card.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        if sim["poblacion_sim"]:
            biomasa = sum(pop["vivos"] * pop["peso_g"] / 1000 for pop in sim["poblacion_sim"])
            volumen = agua["volumen_l"]
            densidad = (biomasa / volumen) * 1000 if volumen > 0 else 0
            first_esp_id = sim["poblacion_sim"][0]["id_especie"]
            first_esp = self.especies.get(first_esp_id, {})
            problemas = explicar_condiciones(agua, first_esp, eq, densidad)
            
            if problemas:
                tk.Label(diag_card, text="⚠️  Problemas detectados:", font=("", 9, "bold"),
                         fg=TEXT_RED, bg=BG_CARD).pack(anchor=tk.W, pady=(0, 3))
                for prob in problemas[:5]:
                    tk.Label(diag_card, text=f"  • {prob}", font=("", 8),
                             fg=TEXT_YELLOW, bg=BG_CARD).pack(anchor=tk.W, pady=1)
            else:
                tk.Label(diag_card, text="✅ Todo parece normal", font=("", 9),
                         fg=TEXT_GREEN, bg=BG_CARD).pack(anchor=tk.W, pady=2)
        
        # Espacio al final
        tk.Label(self.scroll_data_frame, text="", bg=BG_LIGHT).pack(pady=20)
    
    def _add_section(self, parent, title):
        """Agrega un título de sección."""
        tk.Label(parent, text=title, font=("", 11, "bold"), fg=TEXT_DARK, bg=BG_LIGHT).pack(pady=(10, 3))
        sep = tk.Canvas(parent, height=1, bg=TEXT_LIGHT_GRAY, highlightthickness=0)
        sep.pack(fill=tk.X, padx=10, pady=(0, 3))
    
    def _init_tank_visuals(self):
        """Inicializa los peces y burbujas del estanque."""
        # Limpiar canvas
        self.tank_canvas.delete("all")
        self.peces_animados = []
        self.burbujas = []
        
        pid = self.selected_pecera_id
        sim = self.sim_data[pid]
        
        cw = self.tank_canvas.winfo_width()
        ch = self.tank_canvas.winfo_height()
        if cw < 100:
            cw = 600
        if ch < 100:
            ch = 400
        
        # Fondo del estanque
        self.tank_canvas.create_rectangle(0, 0, cw, ch, fill=AQUA_WATER, outline="")
        
        # Fondo del agua (más claro arriba)
        self.tank_canvas.create_rectangle(0, 0, cw, int(ch * 0.15), fill="#eaf2f8", outline="")
        
        # Piso del estanque
        floor_y = ch - 30
        self.tank_canvas.create_rectangle(0, floor_y, cw, ch, fill=AQUA_FLOOR, outline="")
        
        # Decoración: plantas
        for i in range(5):
            px = random.randint(30, cw - 30)
            plant_h = random.randint(30, 80)
            self.tank_canvas.create_line(px, floor_y, px + random.randint(-10, 10), floor_y - plant_h,
                                         fill="#27ae60", width=3, capstyle="round")
            self.tank_canvas.create_oval(px - 8, floor_y - plant_h, px + 8, floor_y - plant_h + 15,
                                         fill="#2ecc71", outline="")
        
        # Piedras
        for i in range(3):
            rx = random.randint(50, cw - 50)
            ry = floor_y - random.randint(2, 8)
            self.tank_canvas.create_oval(rx - 10, ry - 6, rx + 10, ry + 6, fill="#bdc3c7", outline="")
        
        # Crear peces
        pez_counter = 0
        for pop in sim["poblacion_sim"]:
            esp = self.especies.get(pop["id_especie"], {})
            esp_name = esp.get('nombre', 'Pez')
            num_repr = min(15, pop["cantidad_original"])
            
            for i in range(num_repr):
                x = random.randint(50, cw - 50)
                y = random.randint(30, floor_y - 30)
                color = PEZ_COLORES[pez_counter % len(PEZ_COLORES)]
                
                pez = PezAnimado(self.tank_canvas, x, y, color, esp_name)
                self.peces_animados.append(pez)
                pez_counter += 1
        
        # Crear burbujas iniciales
        for _ in range(10):
            bx = random.randint(cw // 3, cw * 2 // 3)
            by = random.randint(0, floor_y)
            self.burbujas.append(Burbuja(self.tank_canvas, bx, by))
    
    def _on_pecera_changed(self, value):
        """Cuando cambia la pecera seleccionada."""
        self.selected_pecera_id = int(value) if value.isdigit() else value
        self._init_tank_visuals()
        self._build_data_panel()
    
    def toggle_sim(self):
        self.running = not self.running
        if self.running:
            self.btn_iniciar.config(text="⏸ Pausar", bg=TEXT_RED)
            self._tick()
        else:
            self.btn_iniciar.config(text="▶ Iniciar", bg=TEXT_GREEN)
    
    def reiniciar(self):
        self.running = False
        self.btn_iniciar.config(text="▶ Iniciar", bg=TEXT_GREEN)
        self.tick_count = 0
        self.day = 0
        self.hour = 0
        
        # Reiniciar datos
        for pid in self.peceras:
            self.sim_data[pid] = self._init_sim_data(pid)
        
        self._init_tank_visuals()
        self._build_data_panel()
        self.lbl_tiempo.config(text="Día 0 - Hora 0:00")
    
    def _update_speed(self, value):
        pass  # velocidad se lee en _tick
    
    def _get_interval(self):
        val = self.vel_var.get()
        if "64x" in val:
            return 4
        elif "32x" in val:
            return 8
        elif "16x" in val:
            return 16
        elif "8x" in val:
            return 31
        elif "4x" in val:
            return 62
        elif "2x" in val:
            return 125
        else:
            return 250
    
    def _tick(self):
        if not self.running:
            return
        
        pid = self.selected_pecera_id
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
            peces_especie = [p for p in self.peces_animados 
                            if p.especie == esp.get('nombre', 'Desconocida')]
            
            if peces_especie:
                # Convertir peces animados al formato esperado
                peces_data = []
                for p in peces_especie:
                    peces_data.append({
                        "id": p.id,
                        "salud": p.salud,
                        "vivo": p.vivo,
                        "causa_muerte": None,
                        "ultimo_evento": None,
                    })
                
                eventos = evaluar_eventos_peces(peces_data, agua, esp, densidad,
                                                num_especies_en_pecera=len(poblacion))
                
                # Aplicar eventos a peces animados
                for ev in eventos:
                    for p in peces_especie:
                        if p.id == ev.get("pez_id"):
                            p.salud = max(0, ev.get("nueva_salud", p.salud))
                            if p.salud <= 0 and p.vivo:
                                p.vivo = False
                                p.sinking = True
                                p.sink_speed = random.uniform(0.3, 0.8)
                            break
                
                # Actualizar conteo
                vivos = sum(1 for p in peces_especie if p.vivo)
                total_repr = len(peces_especie)
                if total_repr > 0:
                    pop["vivos"] = int(vivos * (pop["cantidad_original"] / max(total_repr, 1)))
        
        # Actualizar peces muertos por condiciones extremas
        for pez in self.peces_animados:
            if pez.vivo:
                # Daño por amoniaco alto
                if agua["amoniaco_mg_l"] > 0.5:
                    pez.salud -= agua["amoniaco_mg_l"] * 2
                # Daño por oxígeno bajo
                if agua["oxigeno_mg_l"] < 3:
                    pez.salud -= (3 - agua["oxigeno_mg_l"]) * 1.5
                
                if pez.salud <= 0 and pez.vivo:
                    pez.salud = 0
                    pez.vivo = False
                    pez.sinking = True
                    pez.sink_speed = random.uniform(0.3, 0.8)
        
        self.tick_count += 1
        self.day = self.tick_count // 24
        self.hour = self.tick_count % 24
        
        self.lbl_tiempo.config(text=f"Día {self.day} - Hora {self.hour}:00")
        
        # Actualizar panel de datos
        self._build_data_panel()
        
        interval = self._get_interval()
        self.root.after(interval, self._tick)
    
    def _animate_tank(self):
        """Animación continua del estanque (independiente de la simulación)."""
        cw = self.tank_canvas.winfo_width()
        ch = self.tank_canvas.winfo_height()
        floor_y = ch - 30
        
        if cw < 10 or ch < 10:
            self.root.after(50, self._animate_tank)
            return
        
        # Mover peces
        for pez in self.peces_animados:
            pez.update_position(cw, ch, floor_y)
        
        # Actualizar burbujas
        self.burbujas = [b for b in self.burbujas if b.update(floor_y)]
        
        # Crear nuevas burbujas ocasionalmente
        if random.random() < 0.1:
            bx = random.randint(cw // 3, cw * 2 // 3)
            by = floor_y
            self.burbujas.append(Burbuja(self.tank_canvas, bx, by))
        
        self.root.after(50, self._animate_tank)


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
    app = SimulacionEstanque(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
