BEGIN;

DO $$
DECLARE
    corrida_existe BOOLEAN := to_regclass('public.simulacion_corrida') IS NOT NULL;
    resultado_existe BOOLEAN := to_regclass('public.simulacion_resultado') IS NOT NULL;
    cantidad BIGINT;
BEGIN
    IF corrida_existe <> resultado_existe THEN
        RAISE EXCEPTION 'Solo existe una de las tablas de simulación; se cancela la migración.';
    END IF;

    IF corrida_existe THEN
        EXECUTE 'SELECT COUNT(*) FROM public.simulacion_resultado' INTO cantidad;
        IF cantidad <> 0 THEN
            RAISE EXCEPTION 'simulacion_resultado contiene % filas; se cancela la migración.', cantidad;
        END IF;

        EXECUTE 'SELECT COUNT(*) FROM public.simulacion_corrida' INTO cantidad;
        IF cantidad <> 0 THEN
            RAISE EXCEPTION 'simulacion_corrida contiene % filas; se cancela la migración.', cantidad;
        END IF;
    END IF;
END
$$;

DROP TABLE IF EXISTS public.simulacion_resultado;
DROP TABLE IF EXISTS public.simulacion_corrida;

INSERT INTO public.schema_migrations (version, description)
VALUES ('002_eliminar_tablas_resultados', 'Elimina tablas de resultados de simulación; los resultados se guardan en archivos Excel')
ON CONFLICT (version) DO NOTHING;

COMMIT;
