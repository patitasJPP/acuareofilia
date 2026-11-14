"""Genera 104 semanas completas de pedidos, ventas e inventario auditables."""
import numpy as np
import pandas as pd


class MercadoSemanal:
    """Genera únicamente la próxima semana y conserva sus estados aleatorios."""
    def __init__(self, especies, semilla=20261114):
        streams = np.random.SeedSequence(semilla).spawn(len(especies) + 1)
        self.mercado = np.random.default_rng(streams[0])
        self.actividad, self.semana = 0., 0
        self.especies, self.supuestos = {}, []
        for i, especie in enumerate(especies):
            rng = np.random.default_rng(streams[i + 1])
            base, precio = float(rng.uniform(8, 26)), round(float(rng.uniform(3, 24)), 2)
            tendencia = float(rng.uniform(-.0001, .00035))
            fase = rng.uniform(0, 2 * np.pi)
            self.especies[especie] = dict(rng=rng, base=base, precio=precio, stock=int(base*11),
                tendencia=tendencia, fase=fase, local=0., anteriores=[])
            self.supuestos.append({'especie_nombre': especie, 'pedidos_diarios_base': round(base, 2),
                'precio_base_pen': precio, 'nota': 'Parámetros inventados para el experimento; no son precios ni ventas de Pisciber.'})

    def step(self):
        self.actividad = .72 * self.actividad + self.mercado.normal(0, .09)
        filas = []
        for especie, s in self.especies.items():
            r, base = s['rng'], s['base']
            s['local'] = .65 * s['local'] + r.normal(0, .1)
            for dia in range(7):
                d = self.semana * 7 + dia
                fecha = pd.Timestamp('2024-11-11') + pd.Timedelta(days=d)
                promocion = bool(r.random() < .07)
                precio = round(s['precio'] * (1 + .025 * d / 365) * (.9 if promocion else 1), 2)
                media = base * np.exp(self.actividad + s['local'] + s['tendencia'] * d)
                media *= 1 + .15 * np.sin(2 * np.pi * d / 365.25 + s['fase'])
                media *= [0.88, .92, 1., 1.04, 1.12, 1.2, .84][fecha.dayofweek]
                media *= 1.2 if promocion else 1.
                pedidos = int(r.negative_binomial(14, 14 / (14 + media)))
                inicial = s['stock']
                referencia = np.mean(s['anteriores']) if s['anteriores'] else base
                ingreso = max(0, int(referencia * 11) - inicial) if dia == 0 else 0
                if ingreso and r.random() < .1:
                    ingreso = int(ingreso * r.uniform(.35, .7))
                merma = int(r.binomial(inicial + ingreso, .0015))
                vendido = min(pedidos, inicial + ingreso - merma)
                s['stock'] = inicial + ingreso - merma - vendido
                filas.append({'fecha': fecha.date().isoformat(), 'semana_indice': self.semana,
                    'especie_nombre': especie, 'pedidos_solicitados': pedidos,
                    'cantidad_vendida': vendido, 'pedidos_no_atendidos': pedidos - vendido,
                    'precio_unitario_pen': precio, 'ingreso_pen': round(vendido * precio, 2),
                    'promocion': int(promocion), 'stock_inicial': inicial, 'reposicion': ingreso,
                    'merma_simulada': merma, 'stock_final': s['stock'], 'origen': 'simulado'})
                s['anteriores'] = (s['anteriores'] + [pedidos])[-28:]
        self.semana += 1
        return pd.DataFrame(filas).sort_values(['fecha', 'especie_nombre']).reset_index(drop=True)


def generar(especies, semilla=20261114):
    motor = MercadoSemanal(especies, semilla)
    return pd.concat([motor.step() for _ in range(104)], ignore_index=True), motor.supuestos


def semanal(diario):
    tabla = diario.copy()
    tabla['fecha'] = pd.to_datetime(tabla.fecha)
    return tabla.groupby(['semana_indice', 'especie_nombre'], as_index=False).agg(
        semana_inicio=('fecha', 'min'), semana_fin=('fecha', 'max'),
        pedidos_solicitados=('pedidos_solicitados', 'sum'), cantidad_vendida=('cantidad_vendida', 'sum'),
        pedidos_no_atendidos=('pedidos_no_atendidos', 'sum'), ingreso_pen=('ingreso_pen', 'sum'),
        merma_simulada=('merma_simulada', 'sum'), stock_final=('stock_final', 'last'))
