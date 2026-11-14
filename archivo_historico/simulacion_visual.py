"""
Simulación visual de mortalidad acuícola.

Muestra 3 peces en un acuario animado. Cada segundo real = 1 día simulado (24 horas).
Los datos del agua y la salud de cada pez se actualizan en tiempo real en el panel derecho.
"""

import tkinter as tk
from tkinter import ttk, messagebox
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
# Colores para cada pez
# ============================================================
PEZ_COLORES = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c", "#e67e22", "#34495e", "#e91e63", "#00bcd4"]
PEZ_NOMBRES_BASE = ["Pez 1", "Pez 2", "Pez 3", "Pez 4", "Pez 5", "Pez 6", "Pez 7", "Pez 8", "Pez 9", "Pez 10"]
MAX_PECES = 10


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


class SimulacionVisual:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulación Visual de Peces")
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)

        # Estado de la simulación
        self.running = False
        self.tick_count = 0  # cada tick = 1 hora
        self.day = 0
        self.hour = 0

        # Cargar datos
        self.peceras, self.estado, self.equipos, self.especies, self.poblaciones = consultar_datos_iniciales()

        # Seleccionar pecera (la primera por defecto)
        self.pecera_id = list(self.peceras.keys())[0]
        self.pecera_nombre = self.peceras[self.pecera_id]["nombre"]

        # Especies en esta pecera
        self.especies_en_pecera = [p for p in self.poblaciones if p["id_pecera"] == self.pecera_id]
        if not self.especies_en_pecera:
            self.especies_en_pecera = self.poblaciones[:1]
            self.pecera_id = self.especies_en_pecera[0]["id_pecera"]

        # Estado del agua (copia)
        self.agua = {
            "ph": self.estado[self.pecera_id]["ph"],
            "temperatura_c": self.estado[self.pecera_id]["temperatura_c"],
            "oxigeno_mg_l": self.estado[self.pecera_id]["oxigeno_mg_l"],
            "amoniaco_mg_l": self.estado[self.pecera_id]["amoniaco_mg_l"],
            "volumen_l": self.peceras[self.pecera_id]["volumen_l"],
        }

        # Equipos
        self.eq = self.equipos.get(self.pecera_id, {"filtro_remocion_mg_h": 0, "aireacion_mg_h": 0})

        # Peces individuales con salud propia
        self.pez_especie = self.especies_en_pecera[0]
        self.pez_consumo_o2 = self.especies[self.pez_especie["id_especie"]]["consumo_o2"]

        self.num_peces = 3  # Cantidad inicial de peces
        self.peces = []
        self._crear_peces(self.num_peces)

        # Población para evolucionar_agua
        self.pop_sim = [{
            "vivos": self.num_peces,
            "peso_g": self.pez_especie["peso_g"],
            "alimento_g_h": self.pez_especie["alimento_g_h"] / self.pez_especie["cantidad"] * self.num_peces,
            "amoniaco_mg_por_g": self.pez_especie["amoniaco_mg_por_g"],
            "consumo_o2": self.pez_consumo_o2,
        }]

        # Burbujas decorativas
        self.burbujas = []

        # --- UI ---
        self._build_ui()

    def _crear_peces(self, cantidad):
        """Crea una lista de peces con la cantidad especificada, usando la especie del tanque."""
        self.peces = []
        cw = getattr(self, "canvas_width", 600)
        ch = getattr(self, "canvas_height", 400)
        id_esp = self.pez_especie["id_especie"]
        esp_nombre = self.especies[id_esp]["nombre"]
        pecera_nombre = self.pecera_nombre
        for i in range(cantidad):
            self.peces.append({
                "id": i + 1,
                "id_especie": id_esp,
                "salud": 100.0,
                "vivo": True,
                "causa_muerte": None,
                "ultimo_evento": None,
                "x": 80 + (i % 5) * ((cw - 160) // max(5, cantidad)),
                "y": 100 + (i // 5) * 100 + random.randint(-30, 30),
                "vx": random.uniform(0.5, 2),
                "vy": random.uniform(0.3, 1.5),
                "direccion": 1 if random.random() > 0.5 else -1,
                "color": PEZ_COLORES[i % len(PEZ_COLORES)],
                "nombre": f"{esp_nombre} {i + 1}",
                "nombre_pecera": pecera_nombre,
                "burbuja_timer": 0,
            })

    def _build_ui(self):
        # Frame principal
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        # === IZQUIERDA: Acuario ===
        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left.rowconfigure(0, weight=1)
        left.rowconfigure(1, weight=0)
        left.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(left, bg="#1a5276", highlightthickness=2, highlightbackground="#2c3e50")
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Controles
        ctrl = ttk.Frame(left)
        ctrl.grid(row=1, column=0, sticky="ew", pady=(5, 0))

        self.btn_iniciar = ttk.Button(ctrl, text="▶ Iniciar", command=self.toggle_sim)
        self.btn_iniciar.pack(side=tk.LEFT, padx=2)

        self.btn_reiniciar = ttk.Button(ctrl, text="↻ Reiniciar", command=self.reiniciar)
        self.btn_reiniciar.pack(side=tk.LEFT, padx=2)

        # Botón para agregar peces
        self.btn_agregar_pez = ttk.Button(ctrl, text="+ Agregar pez", command=self.agregar_pez)
        self.btn_agregar_pez.pack(side=tk.LEFT, padx=(5, 2))

        ttk.Label(ctrl, text="Velocidad:").pack(side=tk.LEFT, padx=(10, 5))
        self.vel_var = tk.StringVar(value="1x (1s = 1 día)")
        self.vel_menu = ttk.OptionMenu(
            ctrl, self.vel_var, "1x",
            "1x (1s = 1 día)",
            "2x (0.5s = 1 día)",
            "4x (0.25s = 1 día)",
            "8x (0.125s = 1 día)",
            "16x (0.06s = 1 día)",
            "32x (0.03s = 1 día)",
            "64x (0.015s = 1 día)",
            "128x (ultra)"
        )
        self.vel_menu.pack(side=tk.LEFT, padx=2)

        ttk.Label(ctrl, text="Custom(ms):").pack(side=tk.LEFT, padx=(10, 5))
        self.vel_custom_var = tk.StringVar(value="")
        self.vel_custom_entry = ttk.Entry(ctrl, textvariable=self.vel_custom_var, width=6)
        self.vel_custom_entry.pack(side=tk.LEFT, padx=2)
        self.vel_custom_entry.bind("<Return>", self._apply_custom_speed)

        ttk.Label(ctrl, text="Pecera:").pack(side=tk.LEFT, padx=(15, 5))
        self.pecera_var = tk.StringVar(value=self.pecera_nombre)
        pecera_names = [self.peceras[p]["nombre"] for p in self.peceras]
        self.pecera_menu = ttk.OptionMenu(ctrl, self.pecera_var, self.pecera_nombre, *pecera_names, command=self.cambiar_pecera)
        self.pecera_menu.pack(side=tk.LEFT, padx=2)

        # === DERECHA: Panel de datos ===
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        # Scrollable frame para el panel derecho
        right_canvas = tk.Canvas(right, highlightthickness=0)
        right_scrollbar = ttk.Scrollbar(right, orient="vertical", command=right_canvas.yview)
        self.scrollable_right = ttk.Frame(right_canvas)

        self.scrollable_right.bind(
            "<Configure>",
            lambda e: right_canvas.configure(scrollregion=right_canvas.bbox("all"))
        )

        right_canvas.create_window((0, 0), window=self.scrollable_right, anchor="nw")
        right_canvas.configure(yscrollcommand=right_scrollbar.set)

        right_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mouse wheel para scroll
        def _on_mousewheel(event):
            right_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        right_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Construir el contenido del panel derecho
        self._build_right_panel()

    def _build_right_panel(self):
        """Construye el panel derecho con datos del acuario y los peces."""
        container = self.scrollable_right
        for widget in container.winfo_children():
            widget.destroy()

        esp = self.especies[self.pez_especie["id_especie"]]

        ttk.Label(container, text="📊 Datos del Acuario", font=("", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))

        # Tiempo
        self.lbl_tiempo = ttk.Label(container, text="Día 0 - Hora 0", font=("", 11))
        self.lbl_tiempo.pack(anchor=tk.W, pady=2)

        ttk.Separator(container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # Condiciones del agua
        ttk.Label(container, text="💧 Condiciones del Agua", font=("", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))

        self.lbl_ph = ttk.Label(container, text=f"pH: {self.agua['ph']:.2f}")
        self.lbl_ph.pack(anchor=tk.W, pady=2)

        self.lbl_temp = ttk.Label(container, text=f"Temperatura: {self.agua['temperatura_c']:.1f} °C")
        self.lbl_temp.pack(anchor=tk.W, pady=2)

        self.lbl_ox = ttk.Label(container, text=f"Oxígeno: {self.agua['oxigeno_mg_l']:.3f} mg/L")
        self.lbl_ox.pack(anchor=tk.W, pady=2)

        self.lbl_nh3 = ttk.Label(container, text=f"Amoniaco: {self.agua['amoniaco_mg_l']:.4f} mg/L")
        self.lbl_nh3.pack(anchor=tk.W, pady=2)

        # Equipos
        ttk.Separator(container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        ttk.Label(container, text="🔧 Equipos del tanque", font=("", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.lbl_filtro = ttk.Label(container, text=f"Filtro: {self.eq.get('filtro_remocion_mg_h', 0):.1f} mg/h")
        self.lbl_filtro.pack(anchor=tk.W, pady=2)
        self.lbl_aireacion = ttk.Label(container, text=f"Aireación: {self.eq.get('aireacion_mg_h', 0):.1f} mg/h")
        self.lbl_aireacion.pack(anchor=tk.W, pady=2)

        ttk.Separator(container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # Especie
        ttk.Label(container, text=f"🏷️ Especie: {esp['nombre']}", font=("", 10)).pack(anchor=tk.W, pady=(0, 3))

        ttk.Separator(container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # Diagnóstico del tanque (nuevo)
        ttk.Label(container, text="🔍 Diagnóstico del Tanque", font=("", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.lbl_diagnostico = ttk.Label(container, text="", font=("", 8), justify=tk.LEFT, wraplength=280)
        self.lbl_diagnostico.pack(anchor=tk.W, pady=2)

        ttk.Separator(container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # Contador de peces
        self.lbl_num_peces = ttk.Label(container, text=f"🐟 Peces: {len(self.peces)} / {MAX_PECES}", font=("", 10, "bold"))
        self.lbl_num_peces.pack(anchor=tk.W, pady=(0, 5))

        # Datos de cada pez (dinámico) — cada pez usa SU especie
        self.pez_labels = []
        for i in range(len(self.peces)):
            p = self.peces[i]
            # Usar la especie individual de cada pez
            pez_id_esp = p.get("id_especie", self.pez_especie["id_especie"])
            pez_esp = self.especies[pez_id_esp]

            frame_pez = ttk.LabelFrame(container, text=p["nombre"], padding=5)
            frame_pez.pack(fill=tk.X, pady=3)

            s = ttk.Style()
            style_name = f"Pez{i+1}.TLabelframe"
            s.configure(style_name, foreground=p["color"], background="#f0f0f0", font=("", 10, "bold"))
            frame_pez.configure(style=style_name)

            lbl_salud = ttk.Label(frame_pez, text=f"Salud: 100.0 / 100")
            lbl_salud.pack(anchor=tk.W)

            lbl_estado = ttk.Label(frame_pez, text="Estado: Vivo ✓")
            lbl_estado.pack(anchor=tk.W)

            lbl_dano = ttk.Label(frame_pez, text="Riesgo: Bajo")
            lbl_dano.pack(anchor=tk.W)

            lbl_evento = ttk.Label(frame_pez, text="Evento: -", font=("", 8, "italic"))
            lbl_evento.pack(anchor=tk.W)

            lbl_porque = ttk.Label(frame_pez, text="", font=("", 7, "italic"), foreground="#7f8c8d", justify=tk.LEFT, wraplength=260)
            lbl_porque.pack(anchor=tk.W)

            lbl_causa = ttk.Label(frame_pez, text="", font=("", 8))
            lbl_causa.pack(anchor=tk.W)

            ttk.Separator(frame_pez, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)

            ttk.Label(frame_pez, text=f"📋 {pez_esp['nombre']} — Valores recomendables:", font=("", 8, "italic")).pack(anchor=tk.W)

            lbl_rec_ph = ttk.Label(frame_pez, text=f"  pH ideal: {pez_esp['ph_min']} - {pez_esp['ph_max']}", font=("", 8))
            lbl_rec_ph.pack(anchor=tk.W)

            lbl_rec_temp = ttk.Label(frame_pez, text=f"  Temp ideal: {pez_esp['temp_min']} - {pez_esp['temp_max']} °C", font=("", 8))
            lbl_rec_temp.pack(anchor=tk.W)

            lbl_rec_ox = ttk.Label(frame_pez, text=f"  O₂ mínimo: {pez_esp['oxigeno_min']} mg/L", font=("", 8))
            lbl_rec_ox.pack(anchor=tk.W)

            lbl_rec_nh3 = ttk.Label(frame_pez, text=f"  NH₃ máximo: {pez_esp['amoniaco_max']} mg/L", font=("", 8))
            lbl_rec_nh3.pack(anchor=tk.W)

            self.pez_labels.append({
                "salud": lbl_salud,
                "estado": lbl_estado,
                "riesgo": lbl_dano,
                "evento": lbl_evento,
                "porque": lbl_porque,
                "causa": lbl_causa,
                "frame": frame_pez,
            })

        # Iniciar animación
        self.canvas.bind("<Configure>", self._on_resize)
        self._on_resize(None)
        self._draw()

    def _on_resize(self, event):
        if hasattr(self, "canvas"):
            self.canvas_width = self.canvas.winfo_width()
            self.canvas_height = self.canvas.winfo_height()

    def cambiar_pecera(self, valor):
        for pid in self.peceras:
            if self.peceras[pid]["nombre"] == valor:
                self.pecera_id = pid
                self.pecera_nombre = valor
                break
        self.reiniciar()

    def _mostrar_dialogo_especie(self):
        """Muestra una ventana para elegir qué especie de pez agregar."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Elegir especie de pez")
        dialog.geometry("400x420")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Centrar sobre la ventana principal
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 420) // 2
        dialog.geometry(f"400x420+{x}+{y}")

        ttk.Label(dialog, text="🐟 Selecciona la especie del pez", font=("", 12, "bold")).pack(pady=(15, 5))
        ttk.Label(dialog, text="Haz clic en la especie que quieres agregar", font=("", 9)).pack(pady=(0, 10))

        # Resultado seleccionado
        resultado = {"id_especie": None}

        def seleccionar_especie(id_esp):
            resultado["id_especie"] = id_esp
            dialog.destroy()

        # Botones para cada especie con emojis
        especie_emojis = {
            "Tilapia": "🐟",
            "Carpa": "🐠",
            "Trucha": "🐡",
            "Bagre": "🐟",
            "Goldfish": "🐠",
            "Guppy": "🐟",
            "Tetra neón": "🐠",
            "Gamitana": "🐟",
        }

        for id_esp, datos_esp in self.especies.items():
            nombre = datos_esp["nombre"]
            emoji = especie_emojis.get(nombre, "🐟")
            ph_rango = f"pH {datos_esp['ph_min']}-{datos_esp['ph_max']}"
            temp_rango = f"{datos_esp['temp_min']}-{datos_esp['temp_max']}°C"

            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(fill=tk.X, padx=15, pady=2)

            btn = ttk.Button(btn_frame, text=f"  {emoji} {nombre}", command=lambda i=id_esp: seleccionar_especie(i))
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

            lbl_info = ttk.Label(btn_frame, text=f"{ph_rango} | {temp_rango}", font=("", 8), foreground="#7f8c8d")
            lbl_info.pack(side=tk.RIGHT)

        # Botón cancelar
        ttk.Button(dialog, text="Cancelar", command=dialog.destroy).pack(pady=(10, 15))

        # Esperar a que el usuario seleccione
        self.root.wait_window(dialog)
        return resultado["id_especie"]

    def agregar_pez(self):
        """Agrega un pez más al acuario (hasta MAX_PECES). Pide elegir especie."""
        if len(self.peces) >= MAX_PECES:
            messagebox.showinfo("Límite alcanzado", f"No se pueden agregar más peces. Máximo: {MAX_PECES}")
            return

        # Mostrar diálogo para elegir especie
        id_especie = self._mostrar_dialogo_especie()
        if id_especie is None:
            return  # El usuario canceló

        idx = len(self.peces)
        cw = getattr(self, "canvas_width", 600)
        ch = getattr(self, "canvas_height", 400)
        esp_seleccionada = self.especies[id_especie]
        nuevo_pez = {
            "id": idx + 1,
            "id_especie": id_especie,
            "salud": 100.0,
            "vivo": True,
            "causa_muerte": None,
            "ultimo_evento": None,
            "x": 80 + (idx % 5) * ((cw - 160) // max(5, idx + 1)),
            "y": 100 + (idx // 5) * 100 + random.randint(-30, 30),
            "vx": random.uniform(0.5, 2),
            "vy": random.uniform(0.3, 1.5),
            "direccion": 1 if random.random() > 0.5 else -1,
            "color": PEZ_COLORES[idx % len(PEZ_COLORES)],
            "nombre": f"{esp_seleccionada['nombre']} {idx + 1}",
            "nombre_pecera": self.pecera_nombre,
            "burbuja_timer": 0,
        }
        self.peces.append(nuevo_pez)
        self.num_peces = len(self.peces)
        # Actualizar población para simulación
        self.pop_sim[0]["vivos"] = self.num_peces
        self.pop_sim[0]["alimento_g_h"] = self.pez_especie["alimento_g_h"] / self.pez_especie["cantidad"] * self.num_peces
        # Reconstruir panel derecho
        self._build_right_panel()
        self._draw()
        # Actualizar estado del botón
        if len(self.peces) >= MAX_PECES:
            self.btn_agregar_pez.config(state="disabled")
        messagebox.showinfo("Pez agregado", f"Se agregó {nuevo_pez['nombre']} al acuario.")

    def toggle_sim(self):
        self.running = not self.running
        if self.running:
            self.btn_iniciar.config(text="⏸ Pausar")
            self._tick()
        else:
            self.btn_iniciar.config(text="▶ Iniciar")

    def reiniciar(self):
        self.running = False
        self.btn_iniciar.config(text="▶ Iniciar")
        self.tick_count = 0
        self.day = 0
        self.hour = 0

        # Recargar datos de la pecera seleccionada
        self.especies_en_pecera = [p for p in self.poblaciones if p["id_pecera"] == self.pecera_id]
        if not self.especies_en_pecera:
            self.especies_en_pecera = self.poblaciones[:1]
            self.pecera_id = self.especies_en_pecera[0]["id_pecera"]

        self.agua = {
            "ph": self.estado[self.pecera_id]["ph"],
            "temperatura_c": self.estado[self.pecera_id]["temperatura_c"],
            "oxigeno_mg_l": self.estado[self.pecera_id]["oxigeno_mg_l"],
            "amoniaco_mg_l": self.estado[self.pecera_id]["amoniaco_mg_l"],
            "volumen_l": self.peceras[self.pecera_id]["volumen_l"],
        }
        self.eq = self.equipos.get(self.pecera_id, {"filtro_remocion_mg_h": 0, "aireacion_mg_h": 0})

        self.pez_especie = self.especies_en_pecera[0]
        self.pez_consumo_o2 = self.especies[self.pez_especie["id_especie"]]["consumo_o2"]

        # Reiniciar con la cantidad actual de peces
        self.num_peces = len(self.peces) if self.peces else 3
        self._crear_peces(self.num_peces)

        self.pop_sim = [{
            "vivos": self.num_peces,
            "peso_g": self.pez_especie["peso_g"],
            "alimento_g_h": self.pez_especie["alimento_g_h"] / self.pez_especie["cantidad"] * self.num_peces,
            "amoniaco_mg_por_g": self.pez_especie["amoniaco_mg_por_g"],
            "consumo_o2": self.pez_consumo_o2,
        }]

        self.burbujas = []
        self._custom_interval = 500
        self.btn_agregar_pez.config(state="normal")
        self._build_right_panel()
        self._update_labels()
        self._draw()

    def _apply_custom_speed(self, event=None):
        try:
            ms = int(self.vel_custom_var.get())
            if ms > 0:
                self._custom_interval = ms
                self.vel_var.set(f"Custom ({ms}ms/tick)")
        except (ValueError, TypeError):
            pass

    def _get_interval(self):
        val = self.vel_var.get()
        if val.startswith("Custom"):
            return getattr(self, "_custom_interval", 500)
        elif "128x" in val:
            return 4  # ultra rápido
        elif "64x" in val:
            return 8  # ~8ms por tick
        elif "32x" in val:
            return 16  # ~16ms por tick
        elif "16x" in val:
            return 31  # ~31ms por tick
        elif "8x" in val:
            return 62  # ~62ms por tick
        elif "4x" in val:
            return 125  # 125ms por tick
        elif "2x" in val:
            return 250  # 250ms por tick
        else:
            return 500  # 500ms por tick (2 ticks por segundo = 2 horas/seg)

    def _tick(self):
        if not self.running:
            return

        # Evolucionar agua 1 hora
        self.pop_sim[0]["vivos"] = sum(1 for p in self.peces if p["vivo"])
        self.agua = evolucionar_agua(self.agua, self.eq, self.pop_sim)

        biomasa = self.agua.get("biomasa_kg", 0)
        volumen = self.agua["volumen_l"]
        densidad = (biomasa / volumen) * 1000 if volumen > 0 else 0

        esp = self.especies[self.pez_especie["id_especie"]]

        # Evaluar eventos estocásticos para los peces
        eventos = evaluar_eventos_peces(self.peces, self.agua, esp, densidad, num_especies_en_pecera=1)
        
        # Registrar último evento por pez
        for ev in eventos:
            pez_id = ev["pez_id"]
            for p in self.peces:
                if p.get("id") == pez_id:
                    p["ultimo_evento"] = ev["detalle"]
                    break

        self.tick_count += 1
        self.day = self.tick_count // 24
        self.hour = self.tick_count % 24

        # Mover peces
        cw = max(self.canvas_width, 600)
        ch = max(self.canvas_height, 400)
        for p in self.peces:
            if p["vivo"]:
                p["x"] += p["vx"] * p["direccion"]
                p["y"] += p["vy"]
                if p["x"] > cw - 60 or p["x"] < 30:
                    p["direccion"] *= -1
                if p["y"] > ch - 80 or p["y"] < 40:
                    p["vy"] *= -1
                # Burbujas
                p["burbuja_timer"] += 1
                if p["burbuja_timer"] > 30:
                    self.burbujas.append({"x": p["x"] + 15, "y": p["y"] - 10, "r": random.uniform(2, 5), "alpha": 0.6})
                    p["burbuja_timer"] = 0
            else:
                # Peces muertos se hunden
                p["y"] += 0.3

        # Actualizar burbujas
        for b in self.burbujas:
            b["y"] -= 1
            b["alpha"] -= 0.005
        self.burbujas = [b for b in self.burbujas if b["y"] > 0 and b["alpha"] > 0]

        # Calcular índices de riesgo para mostrar en el panel
        ox = self.agua["oxigeno_mg_l"]
        am = self.agua["amoniaco_mg_l"]
        ph = self.agua["ph"]
        temp = self.agua["temperatura_c"]
        
        riesgo_ph = calcular_dano_ph(ph, esp["ph_min"], esp["ph_max"])
        riesgo_temp = calcular_dano_temp(temp, esp["temp_min"], esp["temp_max"])
        riesgo_ox = calcular_dano_oxigeno(ox, esp["oxigeno_min"])
        riesgo_am = calcular_dano_amoniaco(am, esp["amoniaco_max"])
        riesgo_dens = calcular_dano_densidad(biomasa, volumen)
        riesgo_total = riesgo_ph + riesgo_temp + riesgo_ox + riesgo_am + riesgo_dens

        # Preparar datos por pez para el panel
        datos_por_pez = []
        for p in self.peces:
            datos_por_pez.append({
                "riesgo": riesgo_total,
                "evento": p.get("ultimo_evento"),
            })
        # Limpiar eventos después de mostrarlos
        for p in self.peces:
            p["ultimo_evento"] = None

        self._update_labels(datos_por_pez)
        self._draw()

        interval = self._get_interval()
        self.root.after(interval, self._tick)

    def _update_labels(self, datos_por_pez=None):
        self.lbl_tiempo.config(text=f"Día {self.day} - Hora {self.hour}:00")
        self.lbl_ph.config(text=f"pH: {self.agua['ph']:.2f}")
        self.lbl_temp.config(text=f"Temperatura: {self.agua['temperatura_c']:.1f} °C")
        self.lbl_ox.config(text=f"Oxígeno: {self.agua['oxigeno_mg_l']:.3f} mg/L")
        self.lbl_nh3.config(text=f"Amoniaco: {self.agua['amoniaco_mg_l']:.4f} mg/L")

        if hasattr(self, "lbl_filtro"):
            self.lbl_filtro.config(text=f"Filtro: {self.eq.get('filtro_remocion_mg_h', 0):.1f} mg/h")
        if hasattr(self, "lbl_aireacion"):
            self.lbl_aireacion.config(text=f"Aireación: {self.eq.get('aireacion_mg_h', 0):.1f} mg/h")

        if hasattr(self, "lbl_num_peces"):
            self.lbl_num_peces.config(text=f"🐟 Peces: {len(self.peces)} / {MAX_PECES}")

        # Calcular densidad para diagnóstico
        biomasa = self.agua.get("biomasa_kg", 0)
        volumen = self.agua["volumen_l"]
        densidad = (biomasa / volumen) * 1000 if volumen > 0 else 0
        esp = self.especies[self.pez_especie["id_especie"]]

        # Actualizar diagnóstico del tanque
        if hasattr(self, "lbl_diagnostico"):
            problemas = explicar_condiciones(self.agua, esp, self.eq, densidad)
            if problemas:
                diag_text = "\n".join(problemas[:8])  # Máximo 8 líneas
                self.lbl_diagnostico.config(text=diag_text, foreground="#e67e22")
            else:
                self.lbl_diagnostico.config(text="✅ Todo parece normal en el tanque", foreground="#27ae60")

        if datos_por_pez is None:
            datos_por_pez = [{"riesgo": 0, "evento": None}] * len(self.peces)

        for i, p in enumerate(self.peces):
            if i >= len(self.pez_labels):
                break
            pl = self.pez_labels[i]
            salud_text = f"Salud: {p['salud']:.1f} / 100"
            if p["salud"] > 70:
                salud_text += " 🟢"
            elif p["salud"] > 30:
                salud_text += " 🟡"
            else:
                salud_text += " 🔴"
            pl["salud"].config(text=salud_text)

            if p["vivo"]:
                pl["estado"].config(text="Estado: Vivo ✓")
            else:
                pl["estado"].config(text="Estado: MUERTO ✗")

            # Mostrar nivel de riesgo
            dato = datos_por_pez[i] if i < len(datos_por_pez) else {"riesgo": 0, "evento": None}
            riesgo = dato.get("riesgo", 0)
            if riesgo < 1:
                riesgo_text = "Riesgo: Bajo 🟢"
            elif riesgo < 3:
                riesgo_text = f"Riesgo: Medio 🟡 ({riesgo:.1f})"
            else:
                riesgo_text = f"Riesgo: ALTO 🔴 ({riesgo:.1f})"
            pl["riesgo"].config(text=riesgo_text)

            # Mostrar evento reciente y por qué pasó
            evento = dato.get("evento")
            if evento and p["vivo"]:
                pl["evento"].config(text=f"⚡ {evento}")
                # Explicar por qué pasó este evento
                problema_list = explicar_condiciones(self.agua, esp, self.eq, densidad)
                if problema_list:
                    pl["porque"].config(text="Por qué: " + problema_list[0], foreground="#e67e22")
                else:
                    pl["porque"].config(text="", foreground="#7f8c8d")
            elif not p["vivo"]:
                pl["evento"].config(text="")
                pl["porque"].config(text="", foreground="#7f8c8d")
            else:
                pl["evento"].config(text="")
                pl["porque"].config(text="", foreground="#7f8c8d")

            # Mostrar causa de muerte con explicación detallada
            if not p["vivo"] and p.get("causa_muerte"):
                # Generar explicación completa de la muerte
                explicacion = explicar_causa_muerte(p["causa_muerte"], self.agua, esp, self.eq, densidad)
                pl["causa"].config(text=explicacion, foreground="#e74c3c", justify=tk.LEFT, wraplength=260)
            else:
                pl["causa"].config(text="")

    def _draw(self):
        c = self.canvas
        cw = max(self.canvas_width, 600)
        ch = max(self.canvas_height, 400)
        c.config(width=cw, height=ch)
        c.delete("all")

        # Fondo degradado (agua)
        for y in range(0, ch, 5):
            ratio = y / ch
            r = int(26 + ratio * 20)
            g = int(82 + ratio * 30)
            b = int(118 + ratio * 20)
            color = f"#{r:02x}{g:02x}{b:02x}"
            c.create_rectangle(0, y, cw, y + 5, fill=color, outline="")

        # Fondo del acuario (arena)
        c.create_rectangle(0, ch - 40, cw, ch, fill="#d4a76a", outline="")
        c.create_rectangle(0, ch - 35, cw, ch - 38, fill="#c49a5a", outline="")

        # Plantas decorativas
        for x in [50, cw - 80, cw // 2]:
            self._draw_plant(c, x, ch - 40)

        # Burbujas
        for b in self.burbujas:
            c.create_oval(b["x"] - b["r"], b["y"] - b["r"],
                          b["x"] + b["r"], b["y"] + b["r"],
                          fill="#aed6f1", outline="#85c1e9", stipple="gray50")

        # Peces
        for p in self.peces:
            self._draw_fish(c, p)

        # Título
        c.create_text(cw // 2, 20, text=f"{self.pecera_nombre} - Día {self.day}",
                      fill="white", font=("", 12, "bold"))

    def _draw_plant(self, c, x, y):
        """Dibuja una planta decorativa."""
        c.create_line(x, y, x - 10, y - 60, fill="#27ae60", width=3)
        c.create_line(x, y, x + 15, y - 50, fill="#2ecc71", width=3)
        c.create_line(x, y, x + 5, y - 70, fill="#229954", width=2)
        c.create_oval(x - 15, y - 65, x - 5, y - 55, fill="#27ae60", outline="")
        c.create_oval(x + 10, y - 55, x + 22, y - 45, fill="#2ecc71", outline="")

    def _draw_fish(self, c, p):
        """Dibuja un pez con su color y estado."""
        x, y = p["x"], p["y"]
        color = p["color"]
        dir = p["direccion"]

        if not p["vivo"]:
            # Pez muerto: gris, boca abajo
            color = "#7f8c8d"
            c.create_oval(x - 20, y - 10, x + 20, y + 10, fill=color, outline="#555")
            c.create_polygon(x + 20 * dir, y, x + 35 * dir, y - 12, x + 35 * dir, y + 12,
                             fill=color, outline="#555")
            # X en los ojos
            eye_x = x + 8 * dir
            eye_y = y - 3
            c.create_line(eye_x - 3, eye_y - 3, eye_x + 3, eye_y + 3, fill="black", width=2)
            c.create_line(eye_x + 3, eye_y - 3, eye_x - 3, eye_y + 3, fill="black", width=2)
            # Nombre con pecera
            pez_label = p["nombre"]
            if p.get("nombre_pecera"):
                pez_label = f"{p['nombre']} - {p['nombre_pecera']}"
            c.create_text(x, y - 20, text=pez_label, fill=color, font=("", 9, "bold"))
            c.create_text(x, y + 25, text="MUERTO", fill="#e74c3c", font=("", 8))
            return

        # Cuerpo del pez
        c.create_oval(x - 20, y - 12, x + 20, y + 12, fill=color, outline=darken(color))

        # Cola
        c.create_polygon(x + 20 * dir, y, x + 35 * dir, y - 15, x + 35 * dir, y + 15,
                         fill=color, outline=darken(color))

        # Aleta dorsal
        c.create_polygon(x - 5 * dir, y - 12, x + 5 * dir, y - 25, x + 10 * dir, y - 12,
                         fill=darken(color), outline="")

        # Ojo
        eye_x = x + 10 * dir
        eye_y = y - 3
        c.create_oval(eye_x - 4, eye_y - 4, eye_x + 4, eye_y + 4, fill="white", outline="")
        c.create_oval(eye_x - 2, eye_y - 2, eye_x + 2, eye_y + 2, fill="black")

        # Boca
        c.create_arc(x + 15 * dir, y + 2, x + 22 * dir, y + 10,
                     start=0, extent=90 if dir > 0 else -90,
                     style=tk.ARC, outline="black", width=1.5)

        # Nombre y salud sobre el pez (con nombre de pecera)
        pez_label = p["nombre"]
        if p.get("nombre_pecera"):
            pez_label = f"{p['nombre']} - {p['nombre_pecera']}"
        c.create_text(x, y - 22, text=pez_label, fill=color, font=("", 9, "bold"))

        # Barra de salud
        bar_w = 40
        bar_h = 5
        bar_x = x - bar_w // 2
        bar_y = y - 30
        c.create_rectangle(bar_x - 1, bar_y - 1, bar_x + bar_w + 1, bar_y + bar_h + 1,
                           fill="black", outline="")
        salud_ratio = p["salud"] / 100.0
        if salud_ratio > 0.5:
            bar_color = "#2ecc71"
        elif salud_ratio > 0.25:
            bar_color = "#f39c12"
        else:
            bar_color = "#e74c3c"
        c.create_rectangle(bar_x, bar_y, bar_x + bar_w * salud_ratio, bar_y + bar_h,
                           fill=bar_color, outline="")

def darken(hex_color):
    """Oscurece un color hex para bordes."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = max(0, r - 40)
    g = max(0, g - 40)
    b = max(0, b - 40)
    return f"#{r:02x}{g:02x}{b:02x}"


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
    app = SimulacionVisual(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
