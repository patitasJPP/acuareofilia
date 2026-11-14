-- Base maestra PostgreSQL del esquema public, regenerada desde la base actual.
-- Generada: 2026-11-10T12:47:27-05:00
-- Versión de PostgreSQL origen: 17.4.
-- Incluye tablas referenciales, restricciones, índices, funciones, triggers, vistas y datos actuales.
-- Regeneración: PowerShell `@' ... '@ | py -` con Python/psycopg consultando pg_catalog en solo lectura; pg_dump no está disponible en PATH.
-- No incluye contraseñas, usuarios ni datos de conexión.
SET client_encoding = 'UTF8';
BEGIN;
SET LOCAL search_path TO public, pg_catalog;

CREATE TABLE IF NOT EXISTS public."especies" (
    "id_especie" SERIAL,
    "nombre_comun" character varying(100) NOT NULL,
    "ph_min" numeric(4,2) NOT NULL,
    "ph_max" numeric(4,2) NOT NULL,
    "temp_min_c" numeric(5,2) NOT NULL,
    "temp_max_c" numeric(5,2) NOT NULL,
    "oxigeno_min_mg_l" numeric(5,2) NOT NULL,
    "amoniaco_max_mg_l" numeric(6,3) NOT NULL,
    "consumo_o2_mg_kg_h" numeric(8,2) NOT NULL,
    CONSTRAINT "especies_pkey" PRIMARY KEY (id_especie),
    CONSTRAINT "especies_nombre_comun_key" UNIQUE (nombre_comun),
    CONSTRAINT "ck_ph_rango" CHECK (ph_min <= ph_max),
    CONSTRAINT "ck_temp_rango" CHECK (temp_min_c <= temp_max_c),
    CONSTRAINT "especies_amoniaco_max_mg_l_check" CHECK (amoniaco_max_mg_l >= 0::numeric),
    CONSTRAINT "especies_consumo_o2_mg_kg_h_check" CHECK (consumo_o2_mg_kg_h >= 0::numeric),
    CONSTRAINT "especies_oxigeno_min_mg_l_check" CHECK (oxigeno_min_mg_l >= 0::numeric),
    CONSTRAINT "especies_ph_max_check" CHECK (ph_max >= 0::numeric AND ph_max <= 14::numeric),
    CONSTRAINT "especies_ph_min_check" CHECK (ph_min >= 0::numeric AND ph_min <= 14::numeric)
);

CREATE TABLE IF NOT EXISTS public."alimentos" (
    "id_alimento" SERIAL,
    "nombre_alimento" character varying(100) NOT NULL,
    "amoniaco_mg_por_g" numeric(8,3) NOT NULL,
    CONSTRAINT "alimentos_pkey" PRIMARY KEY (id_alimento),
    CONSTRAINT "alimentos_nombre_alimento_key" UNIQUE (nombre_alimento),
    CONSTRAINT "alimentos_amoniaco_mg_por_g_check" CHECK (amoniaco_mg_por_g >= 0::numeric)
);

CREATE TABLE IF NOT EXISTS public."peceras" (
    "id_pecera" SERIAL,
    "nombre_pecera" character varying(100) NOT NULL,
    "volumen_l" numeric(10,2) NOT NULL,
    CONSTRAINT "peceras_pkey" PRIMARY KEY (id_pecera),
    CONSTRAINT "peceras_nombre_pecera_key" UNIQUE (nombre_pecera),
    CONSTRAINT "peceras_volumen_l_check" CHECK (volumen_l > 0::numeric)
);

CREATE TABLE IF NOT EXISTS public."schema_migrations" (
    "version" text NOT NULL,
    "description" text NOT NULL,
    "applied_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT "schema_migrations_pkey" PRIMARY KEY (version)
);

CREATE TABLE IF NOT EXISTS public."equipos_pecera" (
    "id_pecera" integer NOT NULL,
    "filtro_remocion_mg_h" numeric(10,2) DEFAULT 0 NOT NULL,
    "aireacion_mg_h" numeric(10,2) DEFAULT 0 NOT NULL,
    CONSTRAINT "equipos_pecera_pkey" PRIMARY KEY (id_pecera),
    CONSTRAINT "equipos_pecera_id_pecera_fkey" FOREIGN KEY (id_pecera) REFERENCES peceras(id_pecera) ON DELETE CASCADE,
    CONSTRAINT "equipos_pecera_aireacion_mg_h_check" CHECK (aireacion_mg_h >= 0::numeric),
    CONSTRAINT "equipos_pecera_filtro_remocion_mg_h_check" CHECK (filtro_remocion_mg_h >= 0::numeric)
);

CREATE TABLE IF NOT EXISTS public."estado_pecera" (
    "id_pecera" integer NOT NULL,
    "ph" numeric(4,2) NOT NULL,
    "temperatura_c" numeric(5,2) NOT NULL,
    "oxigeno_mg_l" numeric(6,3) NOT NULL,
    "amoniaco_mg_l" numeric(8,4) NOT NULL,
    CONSTRAINT "estado_pecera_pkey" PRIMARY KEY (id_pecera),
    CONSTRAINT "estado_pecera_id_pecera_fkey" FOREIGN KEY (id_pecera) REFERENCES peceras(id_pecera) ON DELETE CASCADE,
    CONSTRAINT "estado_pecera_amoniaco_mg_l_check" CHECK (amoniaco_mg_l >= 0::numeric),
    CONSTRAINT "estado_pecera_oxigeno_mg_l_check" CHECK (oxigeno_mg_l >= 0::numeric),
    CONSTRAINT "estado_pecera_ph_check" CHECK (ph >= 0::numeric AND ph <= 14::numeric)
);

CREATE TABLE IF NOT EXISTS public."pecera_especie" (
    "id_pecera" integer NOT NULL,
    "id_especie" integer NOT NULL,
    "id_alimento" integer NOT NULL,
    "cantidad_peces" integer NOT NULL,
    "peso_promedio_g" numeric(10,2) NOT NULL,
    "alimento_g_por_hora" numeric(10,3) DEFAULT 0 NOT NULL,
    CONSTRAINT "pecera_especie_pkey" PRIMARY KEY (id_pecera, id_especie),
    CONSTRAINT "pecera_especie_id_alimento_fkey" FOREIGN KEY (id_alimento) REFERENCES alimentos(id_alimento) ON DELETE RESTRICT,
    CONSTRAINT "pecera_especie_id_especie_fkey" FOREIGN KEY (id_especie) REFERENCES especies(id_especie) ON DELETE RESTRICT,
    CONSTRAINT "pecera_especie_id_pecera_fkey" FOREIGN KEY (id_pecera) REFERENCES peceras(id_pecera) ON DELETE CASCADE,
    CONSTRAINT "pecera_especie_alimento_g_por_hora_check" CHECK (alimento_g_por_hora >= 0::numeric),
    CONSTRAINT "pecera_especie_cantidad_peces_check" CHECK (cantidad_peces >= 0),
    CONSTRAINT "pecera_especie_peso_promedio_g_check" CHECK (peso_promedio_g > 0::numeric)
);

CREATE TABLE IF NOT EXISTS public."especie_ficha" (
    "id_especie" integer NOT NULL,
    "nombre_cientifico" text,
    "temperamento" text,
    "dieta" text,
    "talla_adulta_cm" numeric(7,2),
    "longevidad_anios" numeric(6,2),
    "volumen_min_l" numeric(10,2),
    "zona_agua" text,
    "es_depredador" boolean,
    "es_supuesto" boolean DEFAULT true NOT NULL,
    "fuente" text NOT NULL,
    CONSTRAINT "especie_ficha_pkey" PRIMARY KEY (id_especie),
    CONSTRAINT "especie_ficha_id_especie_fkey" FOREIGN KEY (id_especie) REFERENCES especies(id_especie) ON DELETE RESTRICT,
    CONSTRAINT "especie_ficha_longevidad_anios_check" CHECK (longevidad_anios IS NULL OR longevidad_anios > 0::numeric),
    CONSTRAINT "especie_ficha_talla_adulta_cm_check" CHECK (talla_adulta_cm IS NULL OR talla_adulta_cm > 0::numeric),
    CONSTRAINT "especie_ficha_volumen_min_l_check" CHECK (volumen_min_l IS NULL OR volumen_min_l > 0::numeric)
);

CREATE TABLE IF NOT EXISTS public."especie_interaccion" (
    "id" bigint GENERATED BY DEFAULT AS IDENTITY,
    "id_especie_a" integer NOT NULL,
    "id_especie_b" integer NOT NULL,
    "tipo" text NOT NULL,
    "multiplicador_riesgo_min" numeric(12,6) NOT NULL,
    "multiplicador_riesgo_probable" numeric(12,6) NOT NULL,
    "multiplicador_riesgo_max" numeric(12,6) NOT NULL,
    "observaciones" text,
    "es_supuesto" boolean DEFAULT true NOT NULL,
    "fuente" text NOT NULL,
    CONSTRAINT "especie_interaccion_pkey" PRIMARY KEY (id),
    CONSTRAINT "uq_especie_interaccion" UNIQUE (id_especie_a, id_especie_b, tipo),
    CONSTRAINT "especie_interaccion_id_especie_a_fkey" FOREIGN KEY (id_especie_a) REFERENCES especies(id_especie) ON DELETE RESTRICT,
    CONSTRAINT "especie_interaccion_id_especie_b_fkey" FOREIGN KEY (id_especie_b) REFERENCES especies(id_especie) ON DELETE RESTRICT,
    CONSTRAINT "ck_especie_interaccion_distintas" CHECK (id_especie_a <> id_especie_b),
    CONSTRAINT "ck_especie_interaccion_rango" CHECK (multiplicador_riesgo_min <= multiplicador_riesgo_probable AND multiplicador_riesgo_probable <= multiplicador_riesgo_max),
    CONSTRAINT "especie_interaccion_multiplicador_riesgo_max_check" CHECK (multiplicador_riesgo_max >= 0::numeric),
    CONSTRAINT "especie_interaccion_multiplicador_riesgo_min_check" CHECK (multiplicador_riesgo_min >= 0::numeric),
    CONSTRAINT "especie_interaccion_multiplicador_riesgo_probable_check" CHECK (multiplicador_riesgo_probable >= 0::numeric),
    CONSTRAINT "especie_interaccion_tipo_check" CHECK (tipo = ANY (ARRAY['depredacion'::text, 'agresividad'::text, 'competencia_alimento'::text, 'enfermedad'::text, 'compatible'::text]))
);

CREATE TABLE IF NOT EXISTS public."parametro_simulacion" (
    "id" bigint GENERATED BY DEFAULT AS IDENTITY,
    "nombre" text NOT NULL,
    "descripcion" text,
    "valor_min" numeric(16,8) NOT NULL,
    "valor_probable" numeric(16,8) NOT NULL,
    "valor_max" numeric(16,8) NOT NULL,
    "unidad" text NOT NULL,
    "es_supuesto" boolean DEFAULT true NOT NULL,
    "fuente" text NOT NULL,
    CONSTRAINT "parametro_simulacion_pkey" PRIMARY KEY (id),
    CONSTRAINT "parametro_simulacion_nombre_key" UNIQUE (nombre),
    CONSTRAINT "ck_parametro_simulacion_rango" CHECK (valor_min <= valor_probable AND valor_probable <= valor_max),
    CONSTRAINT "parametro_simulacion_valor_max_check" CHECK (valor_max >= 0::numeric),
    CONSTRAINT "parametro_simulacion_valor_min_check" CHECK (valor_min >= 0::numeric),
    CONSTRAINT "parametro_simulacion_valor_probable_check" CHECK (valor_probable >= 0::numeric)
);

CREATE TABLE IF NOT EXISTS public."lectura_agua" (
    "id" bigint GENERATED BY DEFAULT AS IDENTITY,
    "id_pecera" integer NOT NULL,
    "fecha_hora" timestamp with time zone NOT NULL,
    "ph" numeric(4,2),
    "temperatura_c" numeric(5,2),
    "oxigeno_mg_l" numeric(8,4),
    "amoniaco_mg_l" numeric(8,4),
    "nitrito_mg_l" numeric(8,4),
    "nitrato_mg_l" numeric(8,4),
    "observaciones" text,
    CONSTRAINT "lectura_agua_pkey" PRIMARY KEY (id),
    CONSTRAINT "lectura_agua_id_pecera_fkey" FOREIGN KEY (id_pecera) REFERENCES peceras(id_pecera) ON DELETE RESTRICT,
    CONSTRAINT "lectura_agua_amoniaco_mg_l_check" CHECK (amoniaco_mg_l IS NULL OR amoniaco_mg_l >= 0::numeric),
    CONSTRAINT "lectura_agua_nitrato_mg_l_check" CHECK (nitrato_mg_l IS NULL OR nitrato_mg_l >= 0::numeric),
    CONSTRAINT "lectura_agua_nitrito_mg_l_check" CHECK (nitrito_mg_l IS NULL OR nitrito_mg_l >= 0::numeric),
    CONSTRAINT "lectura_agua_oxigeno_mg_l_check" CHECK (oxigeno_mg_l IS NULL OR oxigeno_mg_l >= 0::numeric),
    CONSTRAINT "lectura_agua_ph_check" CHECK (ph IS NULL OR ph >= 0::numeric AND ph <= 14::numeric),
    CONSTRAINT "lectura_agua_temperatura_c_check" CHECK (temperatura_c IS NULL OR temperatura_c >= 0::numeric AND temperatura_c <= 60::numeric)
);

CREATE TABLE IF NOT EXISTS public."registro_mortalidad" (
    "id" bigint GENERATED BY DEFAULT AS IDENTITY,
    "id_pecera" integer NOT NULL,
    "id_especie" integer NOT NULL,
    "fecha" date NOT NULL,
    "cantidad_inicial" integer NOT NULL,
    "cantidad_muertos" integer NOT NULL,
    "causa" text,
    "observaciones" text,
    CONSTRAINT "registro_mortalidad_pkey" PRIMARY KEY (id),
    CONSTRAINT "registro_mortalidad_id_especie_fkey" FOREIGN KEY (id_especie) REFERENCES especies(id_especie) ON DELETE RESTRICT,
    CONSTRAINT "registro_mortalidad_id_pecera_fkey" FOREIGN KEY (id_pecera) REFERENCES peceras(id_pecera) ON DELETE RESTRICT,
    CONSTRAINT "ck_registro_mortalidad_cantidades" CHECK (cantidad_muertos <= cantidad_inicial),
    CONSTRAINT "registro_mortalidad_cantidad_inicial_check" CHECK (cantidad_inicial >= 0),
    CONSTRAINT "registro_mortalidad_cantidad_muertos_check" CHECK (cantidad_muertos >= 0)
);

CREATE TABLE IF NOT EXISTS public."evento_enfermedad" (
    "id" bigint GENERATED BY DEFAULT AS IDENTITY,
    "id_pecera" integer NOT NULL,
    "id_especie" integer,
    "enfermedad" text NOT NULL,
    "fecha_inicio" date NOT NULL,
    "fecha_fin" date,
    "peces_afectados" integer,
    "observaciones" text,
    CONSTRAINT "evento_enfermedad_pkey" PRIMARY KEY (id),
    CONSTRAINT "evento_enfermedad_id_especie_fkey" FOREIGN KEY (id_especie) REFERENCES especies(id_especie) ON DELETE RESTRICT,
    CONSTRAINT "evento_enfermedad_id_pecera_fkey" FOREIGN KEY (id_pecera) REFERENCES peceras(id_pecera) ON DELETE RESTRICT,
    CONSTRAINT "ck_evento_enfermedad_fechas" CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio),
    CONSTRAINT "evento_enfermedad_peces_afectados_check" CHECK (peces_afectados IS NULL OR peces_afectados >= 0)
);

CREATE INDEX IF NOT EXISTS idx_pecera_especie_alimento ON public.pecera_especie USING btree (id_alimento);

CREATE OR REPLACE FUNCTION public.simular_tick()
 RETURNS void
 LANGUAGE plpgsql
AS $function$
BEGIN
    UPDATE estado_pecera s
    SET amoniaco_mg_l = GREATEST(0,
            s.amoniaco_mg_l
            + (COALESCE(c.nh3_mg, 0) - COALESCE(q.filtro_remocion_mg_h, 0)) / p.volumen_l),
        oxigeno_mg_l = LEAST(9, GREATEST(0,
            s.oxigeno_mg_l
            + (COALESCE(q.aireacion_mg_h, 0) - COALESCE(c.o2_mg, 0)) / p.volumen_l))
    FROM peceras p
    LEFT JOIN equipos_pecera q ON q.id_pecera = p.id_pecera
    LEFT JOIN (
        SELECT pe.id_pecera,
               SUM(pe.alimento_g_por_hora * a.amoniaco_mg_por_g)                       AS nh3_mg,
               SUM(pe.cantidad_peces * pe.peso_promedio_g / 1000.0 * e.consumo_o2_mg_kg_h) AS o2_mg
        FROM pecera_especie pe
        JOIN alimentos a ON a.id_alimento = pe.id_alimento
        JOIN especies  e ON e.id_especie  = pe.id_especie
        GROUP BY pe.id_pecera
    ) c ON c.id_pecera = p.id_pecera
    WHERE s.id_pecera = p.id_pecera;
END;
$function$
;

CREATE OR REPLACE VIEW public."v_peligro" AS
 SELECT pe.id_pecera,
    p.nombre_pecera,
    e.nombre_comun,
    s.ph < e.ph_min OR s.ph > e.ph_max AS ph_fuera,
    s.temperatura_c < e.temp_min_c OR s.temperatura_c > e.temp_max_c AS temp_fuera,
    s.oxigeno_mg_l < e.oxigeno_min_mg_l AS oxigeno_bajo,
    s.amoniaco_mg_l > e.amoniaco_max_mg_l AS amoniaco_alto
   FROM pecera_especie pe
     JOIN peceras p ON p.id_pecera = pe.id_pecera
     JOIN especies e ON e.id_especie = pe.id_especie
     JOIN estado_pecera s ON s.id_pecera = pe.id_pecera
  WHERE s.ph < e.ph_min OR s.ph > e.ph_max OR s.temperatura_c < e.temp_min_c OR s.temperatura_c > e.temp_max_c OR s.oxigeno_mg_l < e.oxigeno_min_mg_l OR s.amoniaco_mg_l > e.amoniaco_max_mg_l;;

INSERT INTO public."especies" ("id_especie", "nombre_comun", "ph_min", "ph_max", "temp_min_c", "temp_max_c", "oxigeno_min_mg_l", "amoniaco_max_mg_l", "consumo_o2_mg_kg_h") VALUES
    (1, 'Tilapia', 6.50, 8.50, 24.00, 32.00, 3.00, 0.050, 300.00),
    (2, 'Carpa', 6.50, 8.50, 18.00, 28.00, 3.50, 0.050, 250.00),
    (3, 'Trucha arcoíris', 6.50, 8.00, 10.00, 18.00, 6.00, 0.020, 400.00),
    (4, 'Bagre', 6.50, 8.50, 22.00, 30.00, 3.00, 0.050, 220.00),
    (5, 'Goldfish', 6.50, 8.00, 18.00, 24.00, 4.00, 0.020, 180.00),
    (6, 'Guppy', 6.80, 7.80, 22.00, 28.00, 4.00, 0.020, 350.00),
    (7, 'Tetra neón', 5.50, 7.00, 22.00, 27.00, 4.00, 0.020, 400.00),
    (8, 'Gamitana', 6.00, 8.00, 25.00, 32.00, 3.00, 0.050, 280.00)
ON CONFLICT DO NOTHING;
INSERT INTO public."alimentos" ("id_alimento", "nombre_alimento", "amoniaco_mg_por_g") VALUES
    (1, 'Pellet 28% proteína', 22.000),
    (2, 'Pellet 32% proteína', 25.000),
    (3, 'Pellet 40% proteína', 32.000),
    (4, 'Hojuelas 35% proteína', 28.000),
    (5, 'Starter 45% proteína', 36.000)
ON CONFLICT DO NOTHING;
INSERT INTO public."peceras" ("id_pecera", "nombre_pecera", "volumen_l") VALUES
    (1, 'Tanque Tilapia', 5000.00),
    (2, 'Estanque Mixto', 3000.00),
    (3, 'Tanque Trucha', 2000.00),
    (4, 'Acuario Comunitario', 200.00),
    (5, 'Tanque Gamitana', 4000.00),
    (6, 'Pecera Goldfish', 300.00),
    (7, 'Pecera Sobrealimentada', 500.00)
ON CONFLICT DO NOTHING;
INSERT INTO public."schema_migrations" ("version", "description", "applied_at") VALUES
    ('001_base_simulacion', 'Tablas aditivas para fichas y simulación acuática', '2026-11-10T12:28:54.266866-05:00'),
    ('002_eliminar_tablas_resultados', 'Elimina tablas de resultados de simulación; los resultados se guardan en archivos Excel', '2026-11-10T12:46:55.111701-05:00')
ON CONFLICT DO NOTHING;
INSERT INTO public."equipos_pecera" ("id_pecera", "filtro_remocion_mg_h", "aireacion_mg_h") VALUES
    (1, 450.00, 12000.00),
    (2, 350.00, 8000.00),
    (3, 200.00, 6000.00),
    (4, 10.00, 300.00),
    (5, 450.00, 9000.00),
    (6, 40.00, 600.00),
    (7, 50.00, 3000.00)
ON CONFLICT DO NOTHING;
INSERT INTO public."estado_pecera" ("id_pecera", "ph", "temperatura_c", "oxigeno_mg_l", "amoniaco_mg_l") VALUES
    (1, 7.40, 27.00, 7.500, 0.0100),
    (2, 7.30, 25.00, 7.500, 0.0100),
    (3, 7.20, 14.00, 8.500, 0.0000),
    (4, 6.90, 25.00, 7.000, 0.0000),
    (5, 7.00, 28.00, 7.000, 0.0100),
    (6, 7.20, 21.00, 7.500, 0.0000),
    (7, 7.50, 24.00, 6.000, 0.0500)
ON CONFLICT DO NOTHING;
INSERT INTO public."pecera_especie" ("id_pecera", "id_especie", "id_alimento", "cantidad_peces", "peso_promedio_g", "alimento_g_por_hora") VALUES
    (1, 1, 2, 100, 200.00, 16.000),
    (2, 1, 1, 40, 150.00, 6.000),
    (2, 2, 2, 20, 300.00, 6.000),
    (3, 3, 3, 50, 120.00, 5.000),
    (4, 6, 4, 30, 0.50, 0.020),
    (4, 7, 4, 20, 0.40, 0.010),
    (5, 8, 3, 60, 250.00, 12.500),
    (6, 5, 4, 8, 60.00, 0.400),
    (7, 2, 2, 15, 250.00, 20.000)
ON CONFLICT DO NOTHING;
INSERT INTO public."especie_ficha" ("id_especie", "nombre_cientifico", "temperamento", "dieta", "talla_adulta_cm", "longevidad_anios", "volumen_min_l", "zona_agua", "es_depredador", "es_supuesto", "fuente") VALUES
    (1, NULL, 'Territorialidad variable según la especie', 'Omnívora; variable según la especie', NULL, NULL, NULL, 'Media-fondo', FALSE, TRUE, 'conocimiento general, pendiente de verificar'),
    (2, 'Cyprinus carpio', 'Generalmente pacífica; puede competir por alimento', 'Omnívora', 60.00, 20.00, NULL, 'Fondo', FALSE, TRUE, 'conocimiento general, pendiente de verificar'),
    (3, 'Oncorhynchus mykiss', 'Depredadora; comportamiento variable según tamaño y entorno', 'Carnívora', 60.00, 6.00, NULL, 'Media', TRUE, TRUE, 'conocimiento general, pendiente de verificar'),
    (4, NULL, 'Variable según la especie', 'Variable según la especie; puede ser omnívora o carnívora', NULL, NULL, NULL, 'Fondo', NULL, TRUE, 'conocimiento general, pendiente de verificar'),
    (5, 'Carassius auratus', 'Generalmente pacífica', 'Omnívora', 25.00, 15.00, NULL, 'Media-fondo', FALSE, TRUE, 'conocimiento general, pendiente de verificar'),
    (6, 'Poecilia reticulata', 'Generalmente pacífica', 'Omnívora', 5.00, 3.00, NULL, 'Superficie-media', FALSE, TRUE, 'conocimiento general, pendiente de verificar'),
    (7, 'Paracheirodon innesi', 'Pacífica; forma cardúmenes', 'Omnívora', 4.00, 5.00, NULL, 'Media', FALSE, TRUE, 'conocimiento general, pendiente de verificar'),
    (8, 'Colossoma macropomum', 'Generalmente pacífica en etapa adulta', 'Omnívora; incluye materia vegetal y frutos', 80.00, 10.00, NULL, 'Media-fondo', FALSE, TRUE, 'conocimiento general, pendiente de verificar')
ON CONFLICT DO NOTHING;

SELECT setval(pg_get_serial_sequence('public.especies', 'id_especie'), GREATEST(COALESCE((SELECT MAX("id_especie") FROM public."especies"),1),1), EXISTS (SELECT 1 FROM public."especies"));
SELECT setval(pg_get_serial_sequence('public.alimentos', 'id_alimento'), GREATEST(COALESCE((SELECT MAX("id_alimento") FROM public."alimentos"),1),1), EXISTS (SELECT 1 FROM public."alimentos"));
SELECT setval(pg_get_serial_sequence('public.peceras', 'id_pecera'), GREATEST(COALESCE((SELECT MAX("id_pecera") FROM public."peceras"),1),1), EXISTS (SELECT 1 FROM public."peceras"));
SELECT setval(pg_get_serial_sequence('public.especie_interaccion', 'id'), GREATEST(COALESCE((SELECT MAX("id") FROM public."especie_interaccion"),1),1), EXISTS (SELECT 1 FROM public."especie_interaccion"));
SELECT setval(pg_get_serial_sequence('public.parametro_simulacion', 'id'), GREATEST(COALESCE((SELECT MAX("id") FROM public."parametro_simulacion"),1),1), EXISTS (SELECT 1 FROM public."parametro_simulacion"));
SELECT setval(pg_get_serial_sequence('public.lectura_agua', 'id'), GREATEST(COALESCE((SELECT MAX("id") FROM public."lectura_agua"),1),1), EXISTS (SELECT 1 FROM public."lectura_agua"));
SELECT setval(pg_get_serial_sequence('public.registro_mortalidad', 'id'), GREATEST(COALESCE((SELECT MAX("id") FROM public."registro_mortalidad"),1),1), EXISTS (SELECT 1 FROM public."registro_mortalidad"));
SELECT setval(pg_get_serial_sequence('public.evento_enfermedad', 'id'), GREATEST(COALESCE((SELECT MAX("id") FROM public."evento_enfermedad"),1),1), EXISTS (SELECT 1 FROM public."evento_enfermedad"));

-- Verificación manual de conteos esperados (consultas comentadas):
-- SELECT 'especies' AS tabla, COUNT(*) AS filas, 8 AS esperado FROM public."especies";
-- SELECT 'peceras' AS tabla, COUNT(*) AS filas, 7 AS esperado FROM public."peceras";
-- SELECT 'pecera_especie' AS tabla, COUNT(*) AS filas, 9 AS esperado FROM public."pecera_especie";
-- SELECT 'estado_pecera' AS tabla, COUNT(*) AS filas, 7 AS esperado FROM public."estado_pecera";
-- SELECT 'alimentos' AS tabla, COUNT(*) AS filas, 5 AS esperado FROM public."alimentos";
-- SELECT 'equipos_pecera' AS tabla, COUNT(*) AS filas, 7 AS esperado FROM public."equipos_pecera";
-- SELECT 'especie_ficha' AS tabla, COUNT(*) AS filas, 8 AS esperado FROM public."especie_ficha";
-- SELECT 'especie_interaccion' AS tabla, COUNT(*) AS filas, 0 AS esperado FROM public."especie_interaccion";
-- SELECT 'parametro_simulacion' AS tabla, COUNT(*) AS filas, 0 AS esperado FROM public."parametro_simulacion";
-- SELECT 'lectura_agua' AS tabla, COUNT(*) AS filas, 0 AS esperado FROM public."lectura_agua";
-- SELECT 'registro_mortalidad' AS tabla, COUNT(*) AS filas, 0 AS esperado FROM public."registro_mortalidad";
-- SELECT 'evento_enfermedad' AS tabla, COUNT(*) AS filas, 0 AS esperado FROM public."evento_enfermedad";
-- SELECT 'schema_migrations' AS tabla, COUNT(*) AS filas, 2 AS esperado FROM public."schema_migrations";
-- SELECT COUNT(*) AS filas_v_peligro FROM public."v_peligro"; -- 0 en el origen al generar este archivo
COMMIT;
