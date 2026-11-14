BEGIN;

DROP TABLE IF EXISTS public.simulacion_resultado;
DROP TABLE IF EXISTS public.simulacion_corrida;
DROP TABLE IF EXISTS public.evento_enfermedad;
DROP TABLE IF EXISTS public.registro_mortalidad;
DROP TABLE IF EXISTS public.lectura_agua;
DROP TABLE IF EXISTS public.parametro_simulacion;
DROP TABLE IF EXISTS public.especie_interaccion;
DROP TABLE IF EXISTS public.especie_ficha;

DO $$
BEGIN
    IF to_regclass('public.schema_migrations') IS NOT NULL THEN
        EXECUTE 'DELETE FROM public.schema_migrations WHERE version = ''001_base_simulacion''';
        IF NOT EXISTS (SELECT 1 FROM public.schema_migrations) THEN
            DROP TABLE public.schema_migrations;
        END IF;
    END IF;
END
$$;

COMMIT;
