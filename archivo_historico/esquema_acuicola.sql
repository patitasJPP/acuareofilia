-- ==========================================================
-- SIMULACIÓN ACUÍCOLA BÁSICA - PostgreSQL
-- Unidades fijas: litros, mg/L, gramos, kg, °C, horas
-- ==========================================================

DROP TABLE IF EXISTS pecera_especie CASCADE;
DROP TABLE IF EXISTS estado_pecera  CASCADE;
DROP TABLE IF EXISTS equipos_pecera CASCADE;
DROP TABLE IF EXISTS peceras        CASCADE;
DROP TABLE IF EXISTS alimentos      CASCADE;
DROP TABLE IF EXISTS especies       CASCADE;

-- ---------- ESPECIES ----------
CREATE TABLE especies (
    id_especie          SERIAL PRIMARY KEY,
    nombre_comun        VARCHAR(100) NOT NULL UNIQUE,
    ph_min              NUMERIC(4,2) NOT NULL CHECK (ph_min BETWEEN 0 AND 14),
    ph_max              NUMERIC(4,2) NOT NULL CHECK (ph_max BETWEEN 0 AND 14),
    temp_min_c          NUMERIC(5,2) NOT NULL,
    temp_max_c          NUMERIC(5,2) NOT NULL,
    oxigeno_min_mg_l    NUMERIC(5,2) NOT NULL CHECK (oxigeno_min_mg_l >= 0),
    amoniaco_max_mg_l   NUMERIC(6,3) NOT NULL CHECK (amoniaco_max_mg_l >= 0),
    consumo_o2_mg_kg_h  NUMERIC(8,2) NOT NULL CHECK (consumo_o2_mg_kg_h >= 0),
    CONSTRAINT ck_ph_rango   CHECK (ph_min   <= ph_max),
    CONSTRAINT ck_temp_rango CHECK (temp_min_c <= temp_max_c)
);

-- ---------- ALIMENTOS ----------
CREATE TABLE alimentos (
    id_alimento        SERIAL PRIMARY KEY,
    nombre_alimento    VARCHAR(100) NOT NULL UNIQUE,
    amoniaco_mg_por_g  NUMERIC(8,3) NOT NULL CHECK (amoniaco_mg_por_g >= 0)
);

-- ---------- PECERAS ----------
CREATE TABLE peceras (
    id_pecera      SERIAL PRIMARY KEY,
    nombre_pecera  VARCHAR(100) NOT NULL UNIQUE,
    volumen_l      NUMERIC(10,2) NOT NULL CHECK (volumen_l > 0)
);

-- ---------- EQUIPOS (1:1 con peceras) ----------
CREATE TABLE equipos_pecera (
    id_pecera             INT PRIMARY KEY
                          REFERENCES peceras(id_pecera) ON DELETE CASCADE,
    filtro_remocion_mg_h  NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (filtro_remocion_mg_h >= 0),
    aireacion_mg_h        NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (aireacion_mg_h >= 0)
);

-- ---------- ESTADO ACTUAL (1:1 con peceras) ----------
CREATE TABLE estado_pecera (
    id_pecera       INT PRIMARY KEY
                    REFERENCES peceras(id_pecera) ON DELETE CASCADE,
    ph              NUMERIC(4,2) NOT NULL CHECK (ph BETWEEN 0 AND 14),
    temperatura_c   NUMERIC(5,2) NOT NULL,
    oxigeno_mg_l    NUMERIC(6,3) NOT NULL CHECK (oxigeno_mg_l >= 0),
    amoniaco_mg_l   NUMERIC(8,4) NOT NULL CHECK (amoniaco_mg_l >= 0)
);

-- ---------- PECES EN CADA PECERA ----------
CREATE TABLE pecera_especie (
    id_pecera            INT NOT NULL REFERENCES peceras(id_pecera)      ON DELETE CASCADE,
    id_especie           INT NOT NULL REFERENCES especies(id_especie)    ON DELETE RESTRICT,
    id_alimento          INT NOT NULL REFERENCES alimentos(id_alimento)  ON DELETE RESTRICT,
    cantidad_peces       INT NOT NULL CHECK (cantidad_peces >= 0),
    peso_promedio_g      NUMERIC(10,2) NOT NULL CHECK (peso_promedio_g > 0),
    alimento_g_por_hora  NUMERIC(10,3) NOT NULL DEFAULT 0 CHECK (alimento_g_por_hora >= 0),
    PRIMARY KEY (id_pecera, id_especie)
);

CREATE INDEX idx_pecera_especie_alimento ON pecera_especie(id_alimento);

-- ==========================================================
-- TICK DE SIMULACIÓN (1 hora por ejecución)
--   amoniaco += (generado - removido por filtro) / volumen
--   oxígeno  += (aireación - consumido por peces) / volumen
-- Se limita a 0 como mínimo y el oxígeno a 9 mg/L (saturación aprox.)
-- ==========================================================
CREATE OR REPLACE FUNCTION simular_tick() RETURNS VOID AS $$
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
               SUM(pe.alimento_g_por_hora * a.amoniaco_mg_por_g) AS nh3_mg,
               SUM(pe.cantidad_peces * pe.peso_promedio_g / 1000.0 * e.consumo_o2_mg_kg_h) AS o2_mg
        FROM pecera_especie pe
        JOIN alimentos a ON a.id_alimento = pe.id_alimento
        JOIN especies e ON e.id_especie = pe.id_especie
        GROUP BY pe.id_pecera
    ) c ON c.id_pecera = p.id_pecera
    WHERE s.id_pecera = p.id_pecera;
END;
$$ LANGUAGE plpgsql;

-- ==========================================================
-- VISTA: especies en peligro (fuera de rango)
-- ==========================================================
CREATE OR REPLACE VIEW v_peligro AS
SELECT pe.id_pecera,
       p.nombre_pecera,
       e.nombre_comun,
       (s.ph NOT BETWEEN e.ph_min AND e.ph_max) AS ph_fuera,
       (s.temperatura_c NOT BETWEEN e.temp_min_c AND e.temp_max_c) AS temp_fuera,
       (s.oxigeno_mg_l < e.oxigeno_min_mg_l) AS oxigeno_bajo,
       (s.amoniaco_mg_l > e.amoniaco_max_mg_l) AS amoniaco_alto
FROM pecera_especie pe
JOIN peceras p ON p.id_pecera = pe.id_pecera
JOIN especies e ON e.id_especie = pe.id_especie
JOIN estado_pecera s ON s.id_pecera = pe.id_pecera
WHERE s.ph NOT BETWEEN e.ph_min AND e.ph_max
   OR s.temperatura_c NOT BETWEEN e.temp_min_c AND e.temp_max_c
   OR s.oxigeno_mg_l < e.oxigeno_min_mg_l
   OR s.amoniaco_mg_l > e.amoniaco_max_mg_l;

-- ==========================================================
-- DATOS DE EJEMPLO
-- ==========================================================
INSERT INTO especies (nombre_comun, ph_min, ph_max, temp_min_c, temp_max_c,
                      oxigeno_min_mg_l, amoniaco_max_mg_l, consumo_o2_mg_kg_h)
VALUES ('Tilapia',         6.5, 8.5, 24, 32, 3.0, 0.05, 300),
       ('Carpa',           6.5, 8.5, 18, 28, 3.5, 0.05, 250),
       ('Trucha arcoíris', 6.5, 8.0, 10, 18, 6.0, 0.02, 400),
       ('Bagre',           6.5, 8.5, 22, 30, 3.0, 0.05, 220),
       ('Goldfish',        6.5, 8.0, 18, 24, 4.0, 0.02, 180),
       ('Guppy',           6.8, 7.8, 22, 28, 4.0, 0.02, 350),
       ('Tetra neón',      5.5, 7.0, 22, 27, 4.0, 0.02, 400),
       ('Gamitana',        6.0, 8.0, 25, 32, 3.0, 0.05, 280);

INSERT INTO alimentos (nombre_alimento, amoniaco_mg_por_g)
VALUES ('Pellet 28% proteína', 22),
       ('Pellet 32% proteína', 25),
       ('Pellet 40% proteína', 32),
       ('Hojuelas 35% proteína', 28),
       ('Starter 45% proteína', 36);

INSERT INTO peceras (nombre_pecera, volumen_l)
VALUES ('Tanque Tilapia', 5000),
       ('Estanque Mixto', 3000),
       ('Tanque Trucha', 2000),
       ('Acuario Comunitario', 200),
       ('Tanque Gamitana', 4000),
       ('Pecera Goldfish', 300),
       ('Pecera Sobrealimentada', 500);

INSERT INTO equipos_pecera (id_pecera, filtro_remocion_mg_h, aireacion_mg_h)
VALUES (1, 450, 12000),
       (2, 350, 8000),
       (3, 200, 6000),
       (4, 10, 300),
       (5, 450, 9000),
       (6, 40, 600),
       (7, 50, 3000);

INSERT INTO estado_pecera (id_pecera, ph, temperatura_c, oxigeno_mg_l, amoniaco_mg_l)
VALUES (1, 7.4, 27, 7.5, 0.01),
       (2, 7.3, 25, 7.5, 0.01),
       (3, 7.2, 14, 8.5, 0.00),
       (4, 6.9, 25, 7.0, 0.00),
       (5, 7.0, 28, 7.0, 0.01),
       (6, 7.2, 21, 7.5, 0.00),
       (7, 7.5, 24, 6.0, 0.05);

INSERT INTO pecera_especie (id_pecera, id_especie, id_alimento,
                            cantidad_peces, peso_promedio_g, alimento_g_por_hora)
VALUES (1, 1, 2, 100, 200.00, 16.000),
       (2, 1, 1, 40, 150.00, 6.000),
       (2, 2, 2, 20, 300.00, 6.000),
       (3, 3, 3, 50, 120.00, 5.000),
       (4, 6, 4, 30, 0.50, 0.020),
       (4, 7, 4, 20, 0.40, 0.010),
       (5, 8, 3, 60, 250.00, 12.500),
       (6, 5, 4, 8, 60.00, 0.400),
       (7, 2, 2, 15, 250.00, 20.000);

-- ==========================================================
-- USO:
--   SELECT simular_tick();                 -- avanza 1 hora
--   SELECT * FROM estado_pecera;           -- ver estado
--   SELECT * FROM v_peligro;               -- ver especies en peligro
-- ==========================================================
