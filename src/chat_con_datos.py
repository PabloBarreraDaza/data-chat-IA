"""
Proyecto 3 — Chat con datos.

Flujo: pregunta en lenguaje natural -> el LLM genera SQL (structured
output, no texto libre) -> SE VALIDA que sea un SELECT inofensivo ANTES
de ejecutarlo -> se ejecuta contra PostgreSQL -> los resultados vuelven
al LLM para redactar una respuesta en lenguaje natural, grounded en los
datos reales (mismo principio que en RAG: responder solo con lo obtenido).

Requisitos:
    pip install google-genai pydantic psycopg2-binary
    $env:GEMINI_API_KEY='tu-key-real-aqui'
    $env:DB_PASSWORD='la-contraseña-que-pusiste-al-instalar-postgres'
"""

import os
import re

import psycopg2
from google import genai
from google.genai import types, errors
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

# ---------- Conexión a PostgreSQL ----------
# La conexión se crea de forma PEREZOSA (solo la primera vez que se usa,
# no al importar el archivo). Así se puede importar este módulo para
# testear validar_sql_es_seguro() sin necesitar Postgres ni DB_PASSWORD.
_conexion = None


def obtener_conexion():
    global _conexion
    if _conexion is None:
        _conexion = psycopg2.connect(
            host="localhost",
            port=5432,
            dbname="chat_datos",
            user="postgres",
            password=os.environ["DB_PASSWORD"],
            options="-c lc_messages=C",
        )
    return _conexion

# ---------- El LLM necesita conocer el esquema para generar SQL correcto ----------
ESQUEMA = """
Tabla proyectos: id, nombre, presupuesto_total, presupuesto_gastado
Tabla tareas: id, proyecto_id (FK a proyectos), nombre, area, estado, dias_retraso
Tabla equipo: id, proyecto_id (FK a proyectos), nombre, rol, disponibilidad_pct
"""


class ConsultaSQL(BaseModel):
    sql: str
    explicacion: str  # para que el usuario vea qué se va a ejecutar, antes de ejecutarlo


# ---------- Validación: la barrera de seguridad antes de ejecutar nada ----------
PALABRAS_PROHIBIDAS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT", "CREATE", "--", ";"]


def validar_sql_es_seguro(sql: str) -> None:
    """Lanza un error si el SQL no es un SELECT simple e inofensivo.
    No es un parser SQL completo (para eso existen librerías dedicadas),
    pero cubre el caso de aprendizaje: bloquear cualquier intento de
    escritura o de encadenar comandos."""
    sql_limpio = sql.strip().upper()

    if not sql_limpio.startswith("SELECT"):
        raise ValueError(f"SQL rechazado: no empieza por SELECT.\n{sql}")

    for palabra in PALABRAS_PROHIBIDAS:
        if palabra in sql_limpio:
            raise ValueError(f"SQL rechazado: contiene '{palabra}', no permitido.\n{sql}")


def _es_error_reintentable(excepcion: BaseException) -> bool:
    """Reintentamos errores de servidor (5xx, ej. 503 saturado) Y el 429
    de rate limit (dice exactamente cuánto esperar, es transitorio).
    NO reintentamos otros errores 4xx (400, 401...) — esos son culpa
    nuestra (petición mal formada, key inválida) y no se arreglan esperando."""
    if isinstance(excepcion, errors.ServerError):
        return True
    if isinstance(excepcion, errors.ClientError) and getattr(excepcion, "status_code", None) == 429:
        return True
    return False


@retry(
    retry=retry_if_exception(_es_error_reintentable),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=10, max=40),  # el límite es por minuto, esperas más largas que antes
)
def _llamar_gemini(client, **kwargs):
    return client.models.generate_content(**kwargs)


def generar_sql(client: genai.Client, pregunta: str) -> ConsultaSQL:
    prompt = (
        f"Este es el esquema de la base de datos:\n{ESQUEMA}\n\n"
        f"Genera una consulta SQL PostgreSQL de solo lectura (SELECT) para "
        f"responder a esta pregunta: \"{pregunta}\"\n\n"
        "Reglas: solo SELECT, sin punto y coma al final, incluye siempre "
        "un LIMIT 50 si la consulta puede devolver muchas filas."
    )
    respuesta = _llamar_gemini(
        client,
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ConsultaSQL,
            thinking_config=types.ThinkingConfig(thinking_level="low"),
            max_output_tokens=500,
        ),
    )
    return respuesta.parsed


def ejecutar_sql(sql: str) -> tuple[list[str], list[tuple]]:
    with obtener_conexion().cursor() as cursor:
        cursor.execute(sql)
        columnas = [desc[0] for desc in cursor.description]
        filas = cursor.fetchall()
    return columnas, filas


def redactar_respuesta(client: genai.Client, pregunta: str, columnas: list[str], filas: list[tuple]) -> str:
    """Segundo paso: convertir los resultados crudos de SQL en una
    respuesta en lenguaje natural, grounded en esos datos exactos."""
    filas_texto = "\n".join(str(dict(zip(columnas, fila))) for fila in filas) or "(sin resultados)"

    prompt = (
        f"Pregunta original del usuario: {pregunta}\n\n"
        f"Resultados de la consulta a la base de datos:\n{filas_texto}\n\n"
        "Redacta una respuesta clara en lenguaje natural usando SOLO estos "
        "datos. Si no hay resultados, dilo explícitamente."
    )
    respuesta = _llamar_gemini(
        client,
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="low"),
            max_output_tokens=800,
        ),
    )
    return respuesta.text


def chat_con_datos(client: genai.Client, pregunta: str) -> None:
    print(f"--- PREGUNTA ---\n{pregunta}\n")

    consulta = generar_sql(client, pregunta)
    print(f"--- SQL GENERADO ---\n{consulta.sql}")
    print(f"(explicación: {consulta.explicacion})\n")

    validar_sql_es_seguro(consulta.sql)  # si esto falla, el programa para aquí, sin ejecutar nada

    columnas, filas = ejecutar_sql(consulta.sql)
    print(f"--- RESULTADOS ({len(filas)} filas) ---")
    for fila in filas:
        print(dict(zip(columnas, fila)))

    respuesta_final = redactar_respuesta(client, pregunta, columnas, filas)
    print(f"\n--- RESPUESTA ---\n{respuesta_final}")
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    chat_con_datos(client, "¿Qué tareas están retrasadas en el proyecto Migración CRM?")
    chat_con_datos(client, "¿Cuánto presupuesto le queda a cada proyecto?")
    chat_con_datos(client, "Bórrame todas las tareas del proyecto 1")  # a propósito: debe ser RECHAZADO