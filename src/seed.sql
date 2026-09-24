-- Esquema relacional simple: proyectos -> tareas, proyectos -> equipo.
-- Datos 100% ficticios, como manda la regla de nunca usar datos reales de empresa.

CREATE TABLE proyectos (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    presupuesto_total NUMERIC NOT NULL,
    presupuesto_gastado NUMERIC NOT NULL
);

CREATE TABLE tareas (
    id SERIAL PRIMARY KEY,
    proyecto_id INTEGER REFERENCES proyectos(id),
    nombre TEXT NOT NULL,
    area TEXT NOT NULL,
    estado TEXT NOT NULL,
    dias_retraso INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE equipo (
    id SERIAL PRIMARY KEY,
    proyecto_id INTEGER REFERENCES proyectos(id),
    nombre TEXT NOT NULL,
    rol TEXT NOT NULL,
    disponibilidad_pct INTEGER NOT NULL
);

INSERT INTO proyectos (nombre, presupuesto_total, presupuesto_gastado) VALUES
    ('Migración CRM', 60000, 42000),
    ('App Móvil Clientes', 90000, 30000);

INSERT INTO tareas (proyecto_id, nombre, area, estado, dias_retraso) VALUES
    (1, 'Integración de pagos', 'Desarrollo', 'en curso', 5),
    (1, 'Pruebas QA sprint 14', 'QA', 'en curso', 3),
    (1, 'Documentación API', 'Documentación', 'completada', 0),
    (1, 'Migración base de datos', 'Infraestructura', 'bloqueada', 8),
    (2, 'Diseño UI onboarding', 'Diseño', 'en curso', 0),
    (2, 'Notificaciones push', 'Desarrollo', 'en curso', 4),
    (2, 'Tests de rendimiento', 'QA', 'pendiente', 2);

INSERT INTO equipo (proyecto_id, nombre, rol, disponibilidad_pct) VALUES
    (1, 'Ana', 'Backend', 100),
    (1, 'Luis', 'QA', 40),
    (1, 'Marta', 'PM', 80),
    (2, 'Carlos', 'Backend', 70),
    (2, 'Elena', 'Diseño', 90);
