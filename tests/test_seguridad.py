"""
Tests de validar_sql_es_seguro() — SIN pasar por el LLM. El test de hoy
demostró que el modelo se autocensura y no genera DELETE/DROP por su
cuenta, pero eso no basta como garantía: hay que probar la barrera de
Python directamente, simulando qué pasaría si un LLM (este u otro, hoy
o en el futuro) sí generase SQL peligroso.
"""

import pytest
from chat_con_datos import validar_sql_es_seguro


def test_select_simple_pasa():
    validar_sql_es_seguro("SELECT * FROM tareas LIMIT 50")  # no debe lanzar error


def test_select_con_join_pasa():
    validar_sql_es_seguro("SELECT t.nombre FROM tareas t JOIN proyectos p ON t.proyecto_id = p.id")


@pytest.mark.parametrize(
    "sql_peligroso",
    [
        "DELETE FROM tareas WHERE proyecto_id = 1",
        "DROP TABLE tareas",
        "UPDATE proyectos SET presupuesto_gastado = 0",
        "TRUNCATE TABLE equipo",
        "SELECT * FROM tareas; DROP TABLE tareas",  # comando encadenado
        "SELECT * FROM tareas -- ; DROP TABLE tareas",  # intento vía comentario
        "INSERT INTO tareas (nombre) VALUES ('hackeado')",
    ],
)
def test_sql_peligroso_es_rechazado(sql_peligroso):
    with pytest.raises(ValueError):
        validar_sql_es_seguro(sql_peligroso)
