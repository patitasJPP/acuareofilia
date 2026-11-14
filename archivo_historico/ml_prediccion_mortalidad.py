"""Entrada compatible al entrenamiento corregido, sin interfaz grafica.

El codigo anterior se conserva en backups/auditoria_ml/.
Para opciones de entrada/salida usar py entrenar_mortalidad.py --help.
"""
from entrenar_mortalidad import BASE, ejecutar


if __name__ == '__main__':
    ejecutar(BASE / 'exportaciones/MEGA_DATOS_ML.xlsx', BASE / 'resultados_ml')
