# Chat con Datos (PMO + IA + PostgreSQL)

Script que responde preguntas en lenguaje natural sobre el estado de
proyectos, traduciéndolas a SQL con un LLM, ejecutándolas contra una base
de datos PostgreSQL real, y redactando la respuesta final en lenguaje
natural a partir de los resultados obtenidos.

## Por qué existe

Es la evolución natural del Proyecto 2: en vez de partir de un CSV fijo,
aquí el usuario pregunta lo que quiera y el sistema decide qué consultar.
Es la base de cualquier "AI Project Assistant" más grande (Jira, GitHub,
Slack...) — aquí se aprende el patrón con una sola fuente de datos antes
de complicarlo con varias.

## Arquitectura

```
Pregunta en lenguaje natural
        │
        ▼
  generar_sql()          LLM + structured output → { sql, explicación }
        │
        ▼
  validar_sql_es_seguro() SOLO permite SELECT, bloquea DML/DDL y
        │                 comandos encadenados — verificado con tests
        │                 directos, sin depender del LLM
        ▼
  ejecutar_sql()          consulta real contra PostgreSQL
        │
        ▼
  redactar_respuesta()    LLM redacta la respuesta final, grounded
        │                 EXCLUSIVAMENTE en los resultados obtenidos
        ▼
     Respuesta
```

**Decisión de seguridad clave:** nunca se confía en que el LLM "se porte
bien". Aunque en las pruebas el modelo se negó por sí mismo a generar un
`DELETE` cuando se le pidió explícitamente, el código tiene una barrera
de validación en Python que se prueba de forma independiente (ver
`tests/test_seguridad.py`) — por si algún día el modelo (este u otro)
no se autocensura.

## Instalación

Requiere PostgreSQL instalado localmente (ver `seed.sql` para crear el
esquema y los datos de ejemplo).

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Configura las variables de entorno antes de ejecutar:
```powershell
$env:GEMINI_API_KEY='tu-key-de-gemini'
$env:DB_PASSWORD='tu-contraseña-de-postgres'
```

## Uso

```bash
python chat_con_datos.py
```

## Tests

```bash
pytest tests/ -v
```
Los tests cubren el validador de seguridad SQL de forma aislada, sin
llamar al LLM ni a la base de datos.

## Problemas encontrados durante el desarrollo

- **`UnicodeDecodeError` al conectar con `psycopg2`**: el mensaje de
  error engañaba — parecía un problema de codificación de texto, pero
  psycopg2 tiene un bug conocido por el que, ante ciertos fallos de
  conexión, corrompe el propio mensaje de error en vez de mostrarlo. El
  diagnóstico real se hizo con `psql` desde línea de comandos, que no
  tiene ese bug.
- **Rate limit del tier gratuito (429)**: el modelo permite solo 5
  peticiones/minuto en el tier gratuito, y cada pregunta consume 2
  (generar SQL + redactar respuesta). Con varias preguntas seguidas se
  agota rápido. Mitigado con reintento automático distinguiendo qué
  errores merece la pena reintentar (503 y 429 sí, otros 4xx no).
- **Conexión a la BD no debía ser global**: al principio la conexión a
  PostgreSQL se creaba al importar el módulo, lo que rompía los tests
  (intentaban conectar a la BD solo por importar el archivo). Se cambió
  a una conexión perezosa (`obtener_conexion()`), creada solo cuando
  hace falta.

## Qué mejoraría con más tiempo

- Usar un rol de PostgreSQL de solo lectura (`GRANT SELECT` únicamente),
  como segunda capa de seguridad además de la validación en Python.
- Historial de conversación (preguntas de seguimiento tipo "¿y del otro
  proyecto?" sin repetir todo el contexto).
- Cachear el esquema de la BD dinámicamente en vez de tenerlo escrito a
  mano en el prompt, para que se adapte solo si la BD cambia.
