"""
Simulación visual de todas las peceras simultáneamente.

Muestra las 7 peceras como tarjetas con toda la información disponible.
Al hacer clic en una pecera, se abre un panel detallado con toda la información sin comprimir.
Cada segundo real = 1 día simulado (24 horas).
"""

import tkinter as tk
from tkinter import messagebox
import math
import random

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
# Colores y configuración
# ============================================================
PEZ_COLORES = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c", "#e67e22", "#34495e", "#e91e63", "#00bcd4"]
PEZERA_COLORES = ["#2980b9", "#27ae60", "#8e44ad", "#d35400", "#16a085", "#c0392b", "#2c3e50"]
BG_DARK = "#1a1a2e"
BG_CARD = "#16213e"
BG_SECTION = "#0f3460"
TEXT_WHITE = "#ecf0f1"
TEXT_LIGHT = "#bdc3c7"
TEXT_GREEN = "#2ecc71"
TEXT_YELLOW = "#f39c12"
TEXT_RED = "#e74c3c"


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


class PeceraCard:
    """Tarjeta visual para una pecera individual usando widgets nativos de tk."""
    
    def __init__(self, parent, pecera_id, pecera_data, estado_data, equipos_data, 
                 especies_dict, poblaciones_list, color_index):
        self.pecera_id = pecera_id
        self.pecera_data = pecera_data
        self.estado_data = estado_data
        self.equipos_data = equipos_data
        self.especies_dict = especies_dict
        self.poblaciones_list = poblaciones_list
        self.color_index = color_index
        
        # Estado del agua
        self.agua = {
            "ph": estado_data["ph"],
            "temperatura_c": estado_data["temperatura_c"],
            "oxigeno_mg_l": estado_data["oxigeno_mg_l"],
            "amoniaco_mg_l": estado_data["amoniaco_mg_l"],
            "volumen_l": pecera_data["volumen_l"],
        }
        
        # Población simulada
        self.poblacion_sim = []
        pecera_pops = [p for p in poblaciones_list if p["id_pecera"] == pecera_id]
        for pop in pecera_pops:
            self.poblacion_sim.append({
                "vivos": pop["cantidad"],
                "peso_g": pop["peso_g"],
                "alimento_g_h": pop["alimento_g_h"],
                "amoniaco_mg_por_g": pop["amoniaco_mg_por_g"],
                "consumo_o2": especies_dict.get(pop["id_especie"], {}).get("consumo_o2", 0),
                "id_especie": pop["id_especie"],
                "cantidad_original": pop["cantidad"],
            })
        
        # Peces individuales (representativos, máx 10 por especie)
        self.peces = []
        pez_counter = 0
        for pop in pecera_pops:
            num_repr = min(10, pop["cantidad"])
            for i in range(num_repr):
                self.peces.append({
                    "id": pez_counter + 1,
                    "id_especie": pop["id_especie"],
                    "salud": 100.0,
                    "vivo": True,
                    "causa_muerte": None,
                    "ultimo_evento": None,
                    "color": PEZ_COLORES[pez_counter % len(PEZ_COLORES)],
                    "nombre": f"{especies_dict[pop['id_especie']]['nombre']} {i+1}",
                })
                pez_counter += 1
        
        # Equipos
        self.eq = equipos_data
        
        # Color base de esta pecera
        self.base_color = PEZERA_COLORES[color_index % len(PEZERA_COLORES)]
        
        # Crear la tarjeta con Canvas para borde de color
        self.card_canvas = tk.Canvas(parent, highlightthickness=0, bg=BG_DARK)
        self.card = tk.Frame(self.card_canvas, bg=BG_CARD, padx=8, pady=8)
        self.card_canvas.create_rectangle(0, 0, 1, 1, fill=self.base_color, outline=self.base_color, width=3, tags="border")
        self.card_canvas.create_window(0, 0, window=self.card, anchor="nw", tags="content")
        
        self._build_card()
    
    def _resize_border(self, event=None):
        """Ajusta el borde al tamaño de la tarjeta."""
        self.card_canvas.config(width=self.card.winfo_width() + 6, height=self.card.winfo_height() + 6)
        self.card_canvas.delete("border")
        self.card_canvas.create_rectangle(0, 0, self.card.winfo_width() + 6, self.card.winfo_height() + 6,
                                          fill=self.base_color, outline=self.base_color, width=3, tags="border")
        self.card_canvas.delete("content")
        self.card_canvas.create_window(3, 3, window=self.card, anchor="nw", tags="content")
    
    def _build_card(self):
        """Construye la tarjeta con toda la información de la pecera usando tk nativo."""
        
        # Título de la pecera
        title_frame = tk.Frame(self.card, bg=BG_CARD)
        title_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(title_frame, text=f"🐟 {self.pecera_data['nombre']}", 
                 font=("", 11, "bold"), fg=TEXT_WHITE, bg=BG_CARD).pack(side=tk.LEFT)
        
        tk.Label(title_frame, text=f"{self.pecera_data['volumen_l']}L", 
                 font=("", 9), fg=TEXT_LIGHT, bg=BG_CARD).pack(side=tk.RIGHT)
        
        # Condiciones del agua
        agua_frame = tk.Frame(self.card, bg=BG_SECTION, padx=5, pady=5)
        agua_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(agua_frame, text="💧 Condiciones del Agua", font=("", 9, "bold"),
                 fg=TEXT_WHITE, bg=BG_SECTION).pack(anchor=tk.W, pady=(0, 3))
        
        # pH
        ph_frame = tk.Frame(agua_frame, bg=BG_SECTION)
        ph_frame.pack(fill=tk.X, pady=1)
        tk.Label(ph_frame, text="pH:", font=("", 8), fg=TEXT_LIGHT, bg=BG_SECTION).pack(side=tk.LEFT, padx=2)
        self.lbl_ph = tk.Label(ph_frame, text=f"{self.agua['ph']:.2f}", font=("", 8, "bold"), fg=TEXT_WHITE, bg=BG_SECTION)
        self.lbl_ph.pack(side=tk.LEFT, padx=2)
        
        # Temperatura
        temp_frame = tk.Frame(agua_frame, bg=BG_SECTION)
        temp_frame.pack(fill=tk.X, pady=1)
        tk.Label(temp_frame, text="Temp:", font=("", 8), fg=TEXT_LIGHT, bg=BG_SECTION).pack(side=tk.LEFT, padx=2)
        self.lbl_temp = tk.Label(temp_frame, text=f"{self.agua['temperatura_c']:.1f}°C", font=("", 8, "bold"), fg=TEXT_WHITE, bg=BG_SECTION)
        self.lbl_temp.pack(side=tk.LEFT, padx=2)
        
        # Oxígeno
        ox_frame = tk.Frame(agua_frame, bg=BG_SECTION)
        ox_frame.pack(fill=tk.X, pady=1)
        tk.Label(ox_frame, text="O₂:", font=("", 8), fg=TEXT_LIGHT, bg=BG_SECTION).pack(side=tk.LEFT, padx=2)
        self.lbl_ox = tk.Label(ox_frame, text=f"{self.agua['oxigeno_mg_l']:.2f} mg/L", font=("", 8, "bold"), fg=TEXT_WHITE, bg=BG_SECTION)
        self.lbl_ox.pack(side=tk.LEFT, padx=2)
        
        # Amoniaco
        nh3_frame = tk.Frame(agua_frame, bg=BG_SECTION)
        nh3_frame.pack(fill=tk.X, pady=1)
        tk.Label(nh3_frame, text="NH₃:", font=("", 8), fg=TEXT_LIGHT, bg=BG_SECTION).pack(side=tk.LEFT, padx=2)
        self.lbl_nh3 = tk.Label(nh3_frame, text=f"{self.agua['amoniaco_mg_l']:.4f} mg/L", font=("", 8, "bold"), fg=TEXT_WHITE, bg=BG_SECTION)
        self.lbl_nh3.pack(side=tk.LEFT, padx=2)
        
        # Equipos
        equipos_frame = tk.Frame(self.card, bg=BG_SECTION, padx=5, pady=5)
        equipos_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(equipos_frame, text="🔧 Equipos", font=("", 9, "bold"),
                 fg=TEXT_WHITE, bg=BG_SECTION).pack(anchor=tk.W, pady=(0, 3))
        
        eq_row = tk.Frame(equipos_frame, bg=BG_SECTION)
        eq_row.pack(fill=tk.X, pady=1)
        tk.Label(eq_row, text=f"Filtro: {self.eq.get('filtro_remocion_mg_h', 0):.0f} mg/h", 
                 font=("", 8), fg=TEXT_LIGHT, bg=BG_SECTION).pack(side=tk.LEFT, padx=2)
        tk.Label(eq_row, text=f"| Aireación: {self.eq.get('aireacion_mg_h', 0):.0f} mg/h", 
                 font=("", 8), fg=TEXT_LIGHT, bg=BG_SECTION).pack(side=tk.LEFT, padx=2)
        
        # Especies y población
        especies_frame = tk.Frame(self.card, bg=BG_SECTION, padx=5, pady=5)
        especies_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(especies_frame, text="🐠 Especies y Población", font=("", 9, "bold"),
                 fg=TEXT_WHITE, bg=BG_SECTION).pack(anchor=tk.W, pady=(0, 3))
        
        self.especie_labels = []
        for pop in self.poblacion_sim:
            esp = self.especies_dict.get(pop["id_especie"], {})
            esp_frame = tk.Frame(especies_frame, bg=BG_SECTION)
            esp_frame.pack(fill=tk.X, pady=2)
            
            tk.Label(esp_frame, text=f"{esp.get('nombre', 'Desconocida')}: ", 
                     font=("", 8, "bold"), fg=TEXT_YELLOW, bg=BG_SECTION).pack(side=tk.LEFT)
            
            lbl_vivos = tk.Label(esp_frame, text=f"{pop['vivos']}/{pop['cantidad_original']} vivos", 
                                 font=("", 8), fg=TEXT_WHITE, bg=BG_SECTION)
            lbl_vivos.pack(side=tk.LEFT, padx=2)
            
            # Barra de supervivencia
            bar_canvas = tk.Canvas(esp_frame, width=60, height=8, highlightthickness=0, bg="#34495e")
            bar_canvas.pack(side=tk.LEFT, padx=5)
            ratio = pop["vivos"] / max(pop["cantidad_original"], 1)
            bar_color = TEXT_GREEN if ratio > 0.5 else TEXT_YELLOW if ratio > 0.25 else TEXT_RED
            bar_canvas.create_rectangle(0, 0, 60 * ratio, 8, fill=bar_color, outline="")
            self.especie_labels.append({"vivos": lbl_vivos, "bar": bar_canvas, "pop": pop})
        
        # Salud general
        salud_frame = tk.Frame(self.card, bg=BG_SECTION, padx=5, pady=5)
        salud_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(salud_frame, text="❤️ Salud General", font=("", 9, "bold"),
                 fg=TEXT_WHITE, bg=BG_SECTION).pack(anchor=tk.W, pady=(0, 3))
        
        self.lbl_salud_general = tk.Label(salud_frame, text="Calculando...", font=("", 9, "bold"), fg=TEXT_WHITE, bg=BG_SECTION)
        self.lbl_salud_general.pack(pady=2)
        
        # Diagnóstico
        diag_frame = tk.Frame(self.card, bg=BG_SECTION, padx=5, pady=5)
        diag_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(diag_frame, text="🔍 Diagnóstico", font=("", 9, "bold"),
                 fg=TEXT_WHITE, bg=BG_SECTION).pack(anchor=tk.W, pady=(0, 3))
        
        self.lbl_diagnostico = tk.Label(diag_frame, text="", font=("", 7), fg=TEXT_LIGHT, 
                                         justify=tk.LEFT, wraplength=250, bg=BG_SECTION)
        self.lbl_diagnostico.pack(pady=2)
        
        # Botón de detalles
        btn_frame = tk.Frame(self.card, bg=BG_CARD)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.btn_detalle = tk.Button(btn_frame, text="📋 Ver todos los detalles", 
                                      command=self.mostrar_detalle,
                                      bg=self.base_color, fg=TEXT_WHITE,
                                      font=("", 9, "bold"), relief=tk.FLAT, cursor="hand2",
                                      padx=10, pady=5)
        self.btn_detalle.pack(fill=tk.X)
        
        # Bind para redimensionar borde
        self.card.bind("<Configure>", self._resize_border)
    
    def mostrar_detalle(self):
        """Abre ventana con TODA la información sin comprimir."""
        detail_win = tk.Toplevel()
        detail_win.title(f"📋 {self.pecera_data['nombre']} — Todos los detalles")
        detail_win.geometry("900x700")
        detail_win.minsize(700, 500)
        detail_win.configure(bg=BG_DARK)
        
        # Canvas con scroll
        main_canvas = tk.Canvas(detail_win, bg=BG_DARK, highlightthickness=0)
        scrollbar = tk.Scrollbar(detail_win, command=main_canvas.yview, bg=BG_SECTION,
                                 troughcolor=BG_DARK, width=20)
        scroll_frame = tk.Frame(main_canvas, bg=BG_DARK)
        
        def _configure_scroll(event=None):
            main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        scroll_frame.bind("<Configure>", _configure_scroll)
        
        main_canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Scroll solo en esta ventana (bind al canvas, no global)
        def _on_mousewheel(event):
            if event.widget == main_canvas or event.widget == scroll_frame or event.widget in scroll_frame.winfo_children():
                main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        main_canvas.bind("<MouseWheel>", _on_mousewheel)
        scroll_frame.bind("<MouseWheel>", _on_mousewheel)
        
        def _bind_children(widget):
            widget.bind("<MouseWheel>", _on_mousewheel)
            for child in widget.winfo_children():
                _bind_children(child)
        # Note: children bound after creation handled below
        
        def _separator(parent):
            canvas = tk.Canvas(parent, height=2, bg=BG_SECTION, highlightthickness=0)
            canvas.pack(fill=tk.X, padx=10, pady=5)
        
        def _section_title(parent, text, font_size=13):
            tk.Label(parent, text=text, font=("", font_size, "bold"),
                     fg=TEXT_WHITE, bg=BG_DARK).pack(pady=(8, 4))
        
        # === TÍTULO ===
        tk.Label(scroll_frame, text=f"🐟 {self.pecera_data['nombre']}", 
                  font=("", 16, "bold"), fg=TEXT_WHITE, bg=BG_DARK).pack(pady=(15, 5))
        tk.Label(scroll_frame, text=f"Volumen: {self.pecera_data['volumen_l']} litros", 
                  font=("", 11), fg=TEXT_LIGHT, bg=BG_DARK).pack(pady=(0, 10))
        
        _separator(scroll_frame)
        
        # === CONDICIONES DEL AGUA ===
        _section_title(scroll_frame, "💧 Condiciones del Agua (completas)")
        
        agua_info = tk.Frame(scroll_frame, bg=BG_SECTION, padx=15, pady=8)
        agua_info.pack(fill=tk.X, padx=10)
        
        agua_datos = [
            ("pH actual:", f"{self.agua['ph']:.2f}"),
            ("Temperatura:", f"{self.agua['temperatura_c']:.1f} °C"),
            ("Oxígeno disuelto:", f"{self.agua['oxigeno_mg_l']:.3f} mg/L"),
            ("Amoniaco:", f"{self.agua['amoniaco_mg_l']:.4f} mg/L"),
            ("Volumen:", f"{self.agua['volumen_l']} litros"),
        ]
        for label, value in agua_datos:
            tk.Label(agua_info, text=f"  {label}", font=("", 10), fg=TEXT_LIGHT, bg=BG_SECTION).pack(side=tk.LEFT, anchor=tk.W, pady=2)
            tk.Label(agua_info, text=f"{value}", font=("", 10, "bold"), fg=TEXT_WHITE, bg=BG_SECTION).pack(side=tk.LEFT, anchor=tk.W, pady=2)
        
        _separator(scroll_frame)
        
        # === EQUIPOS ===
        _section_title(scroll_frame, "🔧 Equipos del tanque")
        
        equipos_info = tk.Frame(scroll_frame, bg=BG_SECTION, padx=15, pady=8)
        equipos_info.pack(fill=tk.X, padx=10)
        
        tk.Label(equipos_info, text=f"  Filtro remoción: {self.eq.get('filtro_remocion_mg_h', 0):.1f} mg/h", 
                  font=("", 10), fg=TEXT_WHITE, bg=BG_SECTION).pack(anchor=tk.W, pady=2)
        tk.Label(equipos_info, text=f"  Aireación: {self.eq.get('aireacion_mg_h', 0):.1f} mg/h", 
                  font=("", 10), fg=TEXT_WHITE, bg=BG_SECTION).pack(anchor=tk.W, pady=2)
        
        _separator(scroll_frame)
        
        # === ESPECIES Y POBLACIÓN ===
        _section_title(scroll_frame, "🐠 Especies y Población (detalle completo)")
        
        for pop in self.poblacion_sim:
            esp = self.especies_dict.get(pop["id_especie"], {})
            esp_name = esp.get('nombre', 'Desconocida')
            
            esp_detail = tk.LabelFrame(scroll_frame, text=f"  {esp_name}  ", padding=8,
                                       bg=BG_SECTION, fg=TEXT_YELLOW, font=("", 10, "bold"),
                                       labelanchor=tk.NW)
            esp_detail.pack(fill=tk.X, padx=10, pady=5)
            
            pop_orig = pop['cantidad_original']
            pop_vivos = pop['vivos']
            pop_muertos = pop_orig - pop_vivos
            pct = (pop_muertos / max(pop_orig, 1)) * 100
            
            esp_datos = [
                ("Población original:", f"{pop_orig} peces"),
                ("Peces vivos:", f"{pop_vivos}"),
                ("Peces muertos:", f"{pop_muertos}"),
                ("Tasa de mortalidad:", f"{pct:.1f}%"),
                ("Peso promedio:", f"{pop['peso_g']} g"),
                ("Alimento:", f"{pop['alimento_g_h']} g/hora"),
            ]
            for label, value in esp_datos:
                tk.Label(esp_detail, text=f"    {label}", font=("", 9), fg=TEXT_LIGHT, bg=BG_SECTION).pack(side=tk.LEFT, anchor=tk.W, pady=1)
                tk.Label(esp_detail, text=f"{value}", font=("", 9, "bold"), fg=TEXT_WHITE, bg=BG_SECTION).pack(side=tk.LEFT, anchor=tk.W, pady=1)
            
            # Rangos ideales
            sep2 = tk.Canvas(esp_detail, height=1, bg="#34495e", highlightthickness=0)
            sep2.pack(fill=tk.X, pady=5)
            
            tk.Label(esp_detail, text="  Rangos ideales:", font=("", 8, "italic"), fg=TEXT_LIGHT, bg=BG_SECTION).pack(anchor=tk.W, pady=(2, 0))
            tk.Label(esp_detail, text=f"    pH: {esp.get('ph_min', 'N/A')} - {esp.get('ph_max', 'N/A')}  |  Temp: {esp.get('temp_min', 'N/A')} - {esp.get('temp_max', 'N/A')} °C", 
                      font=("", 8), fg=TEXT_WHITE, bg=BG_SECTION).pack(anchor=tk.W)
            tk.Label(esp_detail, text=f"    O₂ min: {esp.get('oxigeno_min', 'N/A')} mg/L  |  NH₃ max: {esp.get('amoniaco_max', 'N/A')} mg/L", 
                      font=("", 8), fg=TEXT_WHITE, bg=BG_SECTION).pack(anchor=tk.W)
        
        _separator(scroll_frame)
        
        # === DIAGNÓSTICO ===
        _section_title(scroll_frame, "🔍 Diagnóstico del Tanque (completo)")
        
        diag_container = tk.Frame(scroll_frame, bg=BG_SECTION, padx=15, pady=8)
        diag_container.pack(fill=tk.X, padx=10)
        
        biomasa = sum(pop["vivos"] * pop["peso_g"] / 1000 for pop in self.poblacion_sim)
        volumen = self.agua["volumen_l"]
        densidad = (biomasa / volumen) * 1000 if volumen > 0 else 0
        
        if self.poblacion_sim:
            first_esp_id = self.poblacion_sim[0]["id_especie"]
            first_esp = self.especies_dict.get(first_esp_id, {})
            problemas = explicar_condiciones(self.agua, first_esp, self.eq, densidad)
            
            if problemas:
                tk.Label(diag_container, text="  ⚠️  Problemas detectados:", font=("", 10, "bold"), 
                          fg=TEXT_RED, bg=BG_SECTION).pack(anchor=tk.W, pady=2)
                for prob in problemas:
                    tk.Label(diag_container, text=f"    {prob}", font=("", 9), 
                              fg=TEXT_YELLOW, bg=BG_SECTION).pack(anchor=tk.W, pady=1)
            else:
                tk.Label(diag_container, text="  ✅ Todo parece normal en el tanque", 
                          font=("", 10), fg=TEXT_GREEN, bg=BG_SECTION).pack(anchor=tk.W, pady=2)
        
        _separator(scroll_frame)
        
        # === PECES INDIVIDUALES ===
        _section_title(scroll_frame, "🐟 Peces Individuales")
        
        for pez in self.peces:
            pez_esp = self.especies_dict.get(pez["id_especie"], {})
            
            pez_frame = tk.Frame(scroll_frame, bg=BG_SECTION, padx=10, pady=5)
            pez_frame.pack(fill=tk.X, padx=10, pady=2)
            
            # Borde de color a la izquierda
            color_bar = tk.Canvas(pez_frame, width=4, height=50, highlightthickness=0, bg=pez["color"])
            color_bar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
            
            pez_content = tk.Frame(pez_frame, bg=BG_SECTION)
            pez_content.pack(side=tk.LEFT, fill=tk.X)
            
            # Nombre
            tk.Label(pez_content, text=f"{pez['nombre']}", font=("", 9, "bold"),
                     fg=pez["color"], bg=BG_SECTION).pack(anchor=tk.W)
            
            # Salud
            salud_val = pez['salud']
            if salud_val > 70:
                salud_icon = "🟢"
                salud_color = TEXT_GREEN
            elif salud_val > 30:
                salud_icon = "🟡"
                salud_color = TEXT_YELLOW
            else:
                salud_icon = "🔴"
                salud_color = TEXT_RED
            
            tk.Label(pez_content, text=f"  Salud: {salud_val:.1f}/100 {salud_icon}", 
                     font=("", 8), fg=salud_color, bg=BG_SECTION).pack(anchor=tk.W, pady=1)
            
            # Estado
            if pez["vivo"]:
                tk.Label(pez_content, text="  Estado: Vivo ✓", font=("", 8), fg=TEXT_GREEN, bg=BG_SECTION).pack(anchor=tk.W, pady=1)
            else:
                tk.Label(pez_content, text="  Estado: MUERTO ✗", font=("", 8), fg=TEXT_RED, bg=BG_SECTION).pack(anchor=tk.W, pady=1)
                if pez.get("causa_muerte"):
                    tk.Label(pez_content, text=f"  Causa: {pez['causa_muerte']}", font=("", 8), fg=TEXT_RED, bg=BG_SECTION).pack(anchor=tk.W, pady=1)
            
            if pez.get("ultimo_evento"):
                tk.Label(pez_content, text=f"  Último: {pez['ultimo_evento']}", 
                          font=("", 7, "italic"), fg=TEXT_LIGHT, bg=BG_SECTION).pack(anchor=tk.W, pady=1)
        
        # Espacio al final
        tk.Label(scroll_frame, text="", bg=BG_DARK).pack(pady=40)
        
        # Bind scroll a todos los hijos creados
        def _bind_all_children(widget):
            widget.bind("<MouseWheel>", _on_mousewheel)
            for child in widget.winfo_children():
                _bind_all_children(child)
        _bind_all_children(scroll_frame)
    
    def update_display(self):
        """Actualiza los labels de la tarjeta con los nuevos valores."""
        self.lbl_ph.config(text=f"{self.agua['ph']:.2f}")
        self.lbl_temp.config(text=f"{self.agua['temperatura_c']:.1f}°C")
        self.lbl_ox.config(text=f"{self.agua['oxigeno_mg_l']:.2f} mg/L")
        self.lbl_nh3.config(text=f"{self.agua['amoniaco_mg_l']:.4f} mg/L")
        
        # Actualizar especies
        for el in self.especie_labels:
            pop = el["pop"]
            el["vivos"].config(text=f"{pop['vivos']}/{pop['cantidad_original']} vivos")
            
            ratio = pop["vivos"] / max(pop["cantidad_original"], 1)
            bar_color = TEXT_GREEN if ratio > 0.5 else TEXT_YELLOW if ratio > 0.25 else TEXT_RED
            el["bar"].delete("all")
            el["bar"].create_rectangle(0, 0, 60 * ratio, 8, fill=bar_color, outline="")
        
        # Salud general
        if self.peces:
            vivos = sum(1 for p in self.peces if p["vivo"])
            salud_prom = sum(p["salud"] for p in self.peces if p["vivo"]) / max(vivos, 1)
            total = len(self.peces)
            
            if salud_prom > 70:
                salud_icon = "🟢"
            elif salud_prom > 30:
                salud_icon = "🟡"
            else:
                salud_icon = "🔴"
            
            self.lbl_salud_general.config(
                text=f"{vivos}/{total} vivos | Salud: {salud_prom:.1f} {salud_icon}"
            )
        
        # Diagnóstico
        if self.poblacion_sim:
            biomasa = sum(pop["vivos"] * pop["peso_g"] / 1000 for pop in self.poblacion_sim)
            volumen = self.agua["volumen_l"]
            densidad = (biomasa / volumen) * 1000 if volumen > 0 else 0
            first_esp_id = self.poblacion_sim[0]["id_especie"]
            first_esp = self.especies_dict.get(first_esp_id, {})
            problemas = explicar_condiciones(self.agua, first_esp, self.eq, densidad)
            
            if problemas:
                diag_text = "\n".join(problemas[:5])
                self.lbl_diagnostico.config(text=diag_text, fg=TEXT_YELLOW)
            else:
                self.lbl_diagnostico.config(text="✅ Todo normal", fg=TEXT_GREEN)


class SimulacionTodasPeceras:
    def __init__(self, root):
        self.root = root
        self.root.title("🐟 Simulación de Todas las Pecera - Mortalidad Acuícola")
        self.root.geometry("1500x950")
        self.root.minsize(1300, 850)
        self.root.configure(bg=BG_DARK)
        
        # Estado de la simulación
        self.running = False
        self.tick_count = 0
        self.day = 0
        self.hour = 0
        
        # Cargar datos
        self.peceras, self.estado, self.equipos, self.especies, self.poblaciones = consultar_datos_iniciales()
        
        # Crear tarjetas para cada pecera
        self.cards = []
        self._build_ui()
    
    def _build_ui(self):
        """Construye la interfaz principal con todas las peceras."""
        
        # === BARRA SUPERIOR DE CONTROLES ===
        top_frame = tk.Frame(self.root, bg=BG_SECTION, padx=15, pady=10)
        top_frame.pack(fill=tk.X)
        
        # Título
        tk.Label(top_frame, text="🐟 Simulación de Mortalidad Acuícola", 
                 font=("", 14, "bold"), fg=TEXT_WHITE, bg=BG_SECTION).pack(side=tk.LEFT, padx=10)
        
        # Tiempo
        self.lbl_tiempo = tk.Label(top_frame, text="Día 0 - Hora 0:00", 
                                    font=("", 12, "bold"), fg=TEXT_YELLOW, bg=BG_SECTION)
        self.lbl_tiempo.pack(side=tk.LEFT, padx=15)
        
        # Separador vertical
        tk.Canvas(top_frame, width=2, height=30, bg=TEXT_LIGHT, highlightthickness=0).pack(side=tk.LEFT, padx=10)
        
        # Botón iniciar
        self.btn_iniciar = tk.Button(top_frame, text="▶ Iniciar", command=self.toggle_sim,
                                      bg=TEXT_GREEN, fg="white", font=("", 10, "bold"),
                                      relief=tk.FLAT, cursor="hand2", padx=12, pady=5)
        self.btn_iniciar.pack(side=tk.LEFT, padx=5)
        
        # Botón reiniciar
        self.btn_reiniciar = tk.Button(top_frame, text="↻ Reiniciar", command=self.reiniciar,
                                        bg="#7f8c8d", fg="white", font=("", 10, "bold"),
                                        relief=tk.FLAT, cursor="hand2", padx=12, pady=5)
        self.btn_reiniciar.pack(side=tk.LEFT, padx=5)
        
        # Velocidad
        tk.Label(top_frame, text="Velocidad:", font=("", 10), fg=TEXT_LIGHT, bg=BG_SECTION).pack(side=tk.LEFT, padx=(15, 5))
        self.vel_var = tk.StringVar(value="1x (1s = 1 día)")
        self.vel_menu = tk.OptionMenu(
            top_frame, self.vel_var, "1x",
            "1x (1s = 1 día)",
            "2x (0.5s = 1 día)",
            "4x (0.25s = 1 día)",
            "8x (0.125s = 1 día)",
            "16x (0.06s = 1 día)",
            "32x (0.03s = 1 día)",
            "64x (0.015s = 1 día)",
            "128x (ultra)"
        )
        self.vel_menu.config(bg=BG_CARD, fg=TEXT_WHITE, font=("", 9), relief=tk.FLAT, cursor="hand2")
        self.vel_menu.pack(side=tk.LEFT, padx=5)
        
        # === ÁREA PRINCIPAL CON LAS 7 PECERAS ===
        # Usar grid directo sin scroll para que quepan en pantalla
        main_area = tk.Frame(self.root, bg=BG_DARK)
        main_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Cuadrícula 3 columnas x 3 filas (7 peceras)
        num_peceras = len(self.peceras)
        cols = 3
        rows = (num_peceras + cols - 1) // cols
        
        for r in range(rows):
            main_area.rowconfigure(r, weight=1, uniform="row")
        for c in range(cols):
            main_area.columnconfigure(c, weight=1, uniform="col")
        
        # Crear una tarjeta por cada pecera
        row = 0
        col = 0
        for idx, (pid, pdata) in enumerate(self.peceras.items()):
            estado_data = self.estado.get(pid, {"ph": 7.0, "temperatura_c": 25, "oxigeno_mg_l": 7.0, "amoniaco_mg_l": 0.0})
            equipos_data = self.equipos.get(pid, {"filtro_remocion_mg_h": 0, "aireacion_mg_h": 0})
            
            card = PeceraCard(
                main_area, pid, pdata, estado_data, equipos_data,
                self.especies, self.poblaciones, idx
            )
            card.card_canvas.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            
            self.cards.append(card)
            
            col += 1
            if col >= cols:
                col = 0
                row += 1
    
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
        
        # Reiniciar cada tarjeta
        for card in self.cards:
            card.agua = {
                "ph": self.estado[card.pecera_id]["ph"],
                "temperatura_c": self.estado[card.pecera_id]["temperatura_c"],
                "oxigeno_mg_l": self.estado[card.pecera_id]["oxigeno_mg_l"],
                "amoniaco_mg_l": self.estado[card.pecera_id]["amoniaco_mg_l"],
                "volumen_l": card.pecera_data["volumen_l"],
            }
            
            # Reiniciar población
            pecera_pops = [p for p in self.poblaciones if p["id_pecera"] == card.pecera_id]
            card.poblacion_sim = []
            for pop in pecera_pops:
                card.poblacion_sim.append({
                    "vivos": pop["cantidad"],
                    "peso_g": pop["peso_g"],
                    "alimento_g_h": pop["alimento_g_h"],
                    "amoniaco_mg_por_g": pop["amoniaco_mg_por_g"],
                    "consumo_o2": self.especies.get(pop["id_especie"], {}).get("consumo_o2", 0),
                    "id_especie": pop["id_especie"],
                    "cantidad_original": pop["cantidad"],
                })
            
            # Reiniciar peces
            card.peces = []
            pez_counter = 0
            for pop in pecera_pops:
                num_repr = min(10, pop["cantidad"])
                for i in range(num_repr):
                    card.peces.append({
                        "id": pez_counter + 1,
                        "id_especie": pop["id_especie"],
                        "salud": 100.0,
                        "vivo": True,
                        "causa_muerte": None,
                        "ultimo_evento": None,
                        "color": PEZ_COLORES[pez_counter % len(PEZ_COLORES)],
                        "nombre": f"{self.especies[pop['id_especie']]['nombre']} {i+1}",
                    })
                    pez_counter += 1
            
            card.update_display()
        
        self.lbl_tiempo.config(text="Día 0 - Hora 0:00")
    
    def _get_interval(self):
        val = self.vel_var.get()
        if "128x" in val:
            return 4
        elif "64x" in val:
            return 8
        elif "32x" in val:
            return 16
        elif "16x" in val:
            return 31
        elif "8x" in val:
            return 62
        elif "4x" in val:
            return 125
        elif "2x" in val:
            return 250
        else:
            return 500
    
    def _tick(self):
        if not self.running:
            return
        
        # Evolucionar cada pecera
        for card in self.cards:
            # Evolucionar agua
            card.agua = evolucionar_agua(card.agua, card.eq, card.poblacion_sim)
            
            biomasa = card.agua.get("biomasa_kg", 0)
            volumen = card.agua["volumen_l"]
            densidad = (biomasa / volumen) * 1000 if volumen > 0 else 0
            
            # Evaluar eventos para cada especie en la pecera
            for pop in card.poblacion_sim:
                esp = self.especies.get(pop["id_especie"], {})
                peces_especie = [p for p in card.peces if p["id_especie"] == pop["id_especie"]]
                
                if peces_especie:
                    eventos = evaluar_eventos_peces(peces_especie, card.agua, esp, densidad, 
                                                    num_especies_en_pecera=len(card.poblacion_sim))
                    
                    # Actualizar conteo de muertos
                    peces_especie_vivos = sum(1 for p in peces_especie if p["vivo"])
                    pop["vivos"] = peces_especie_vivos * (pop["cantidad_original"] // max(len(peces_especie), 1))
                    
                    # Registrar eventos
                    for ev in eventos:
                        pez_id = ev["pez_id"]
                        for p in peces_especie:
                            if p.get("id") == pez_id:
                                p["ultimo_evento"] = ev["detalle"]
                                break
            
            # Actualizar display
            card.update_display()
        
        self.tick_count += 1
        self.day = self.tick_count // 24
        self.hour = self.tick_count % 24
        
        self.lbl_tiempo.config(text=f"Día {self.day} - Hora {self.hour}:00")
        
        interval = self._get_interval()
        self.root.after(interval, self._tick)


def main():
    try:
        with conectar_bd() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error de conexión", f"No se pudo conectar a PostgreSQL:\n{e}")
        root.destroy()
        return 1
    
    root = tk.Tk()
    app = SimulacionTodasPeceras(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
