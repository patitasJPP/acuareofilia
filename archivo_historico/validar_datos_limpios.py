"""Validacion estructural, sin imponer 343 peces, 160 horas o mortalidad deseada.

No certifica la etiqueta por ausencia de filas: exige trazabilidad de eventos
del generador para auditar muerte y censura. Ejecutar con --entrada ARCHIVO.
"""
from pathlib import Path
import argparse
import pandas as pd


def validar(df):
    requeridas = {'pez_id', 'pecera_id', 'hora_sim', 'especie_nombre', 'muere_siguiente_hora'}
    errores = []
    if not requeridas <= set(df):
        return [f'Faltan columnas: {requeridas - set(df)}']
    if df.empty:
        return ['El archivo no tiene filas.']
    if df.isna().any().any():
        errores.append('Hay valores nulos.')
    if df.duplicated(['pez_id', 'hora_sim']).any():
        errores.append('Se repite pez_id/hora_sim.')
    if not df.muere_siguiente_hora.isin([0, 1]).all():
        errores.append('Objetivo no binario.')
    if not df.hora_sim.eq(df.hora_sim.round()).all():
        errores.append('Las horas no son enteras.')
    for _, g in df.groupby('pez_id'):
        g = g.sort_values('hora_sim')
        if g.pecera_id.nunique() > 1 or g.especie_nombre.nunique() > 1:
            errores.append('Un pez cambia de pecera/especie.')
        if not g.hora_sim.diff().dropna().eq(1).all():
            errores.append('Hay saltos de hora dentro de un pez.')
        positivos = g.index[g.muere_siguiente_hora.eq(1)]
        if len(positivos) > 1 or (len(positivos) and positivos[0] != g.index[-1]):
            errores.append('Un pez tiene registros posteriores a su muerte prevista.')
    return sorted(set(errores))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entrada', type=Path, default=Path(__file__).resolve().parent / 'exportaciones/MEGA_DATOS_ML_LIMPIO.xlsx')
    args = p.parse_args()
    df = pd.read_excel(args.entrada, sheet_name='MegaDatosML')
    errores = validar(df)
    print(f'{len(df):,} filas; {len(df.columns)} columnas; {df.pez_id.nunique()} peces.')
    print(f'Objetivo: {df.muere_siguiente_hora.value_counts().to_dict()}')
    print('Constantes (se seleccionan dentro de cada fold):', [c for c in df if df[c].nunique() <= 1])
    print('Limite: este archivo sin eventos de muerte no permite verificar por si solo etiquetas y censura.')
    if errores:
        raise SystemExit('\n'.join(errores))
    print('Validacion estructural correcta. Esto no certifica validez biologica ni ausencia de fuga.')
