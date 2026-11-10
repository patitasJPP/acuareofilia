# Consulta de peceras

Aplicación de escritorio en Python que consulta datos de peceras en PostgreSQL y los muestra en una tabla.

## Configurar la conexión

Edita las constantes en `database.py`:

- `HOST`: servidor PostgreSQL.
- `PUERTO`: puerto (por defecto, `5432`).
- `BASE_DATOS`: nombre de la base de datos.
- `USUARIO` y `CONTRASENA`: credenciales de PostgreSQL.

La función `conectar_bd()` centraliza la conexión y la usa la aplicación.

## Instalar y ejecutar

Requiere Python 3 y PostgreSQL accesible con las credenciales configuradas.

```powershell
py -m pip install -r requirements.txt
py consultar_peceras.py
```

La ventana presenta los resultados de la consulta con encabezados y barras de desplazamiento. Si ocurre un error de conexión o SQL, muestra una alerta.

## Consulta

Lee peceras, estado del agua, equipos, especies, peces y alimentos mediante `LEFT JOIN`. Calcula la biomasa en kilogramos y ordena los resultados por pecera y especie.

## Archivos

- `consultar_peceras.py`: consulta PostgreSQL y muestra la ventana.
- `database.py`: credenciales y función de conexión.
- `requirements.txt`: dependencia Psycopg para PostgreSQL.
