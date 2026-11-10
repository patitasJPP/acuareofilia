import psycopg
from psycopg.rows import dict_row


# Cambia estos datos para conectar con otra base de datos.
HOST = "localhost"
PUERTO = 5432
BASE_DATOS = "Trabajo_innovador"
USUARIO = "postgres"
CONTRASENA = "jair"


def conectar_bd():
    return psycopg.connect(
        host=HOST,
        port=PUERTO,
        dbname=BASE_DATOS,
        user=USUARIO,
        password=CONTRASENA,
        row_factory=dict_row,
    )
