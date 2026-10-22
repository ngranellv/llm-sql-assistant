import os
import re
import sqlite3
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

MODELO = "gemini-3.8-flash"
# Ruta a la base de datos, relativa a este archivo (funciona se ejecute desde donde se ejecute)
RUTA_BD = Path(__file__).parent / "chinook.db"
# Cuántas veces como máximo se intenta que el modelo acierte con una consulta
MAX_INTENTOS = 3

# Palabras que nunca deben aparecer en una consulta de solo lectura
PALABRAS_PROHIBIDAS = [
    "insert", "update", "delete", "drop", "alter", "create", "replace",
    "attach", "detach", "pragma", "vacuum", "truncate",
]


def conectar_solo_lectura():
    """Abre la base de datos en modo solo lectura: SQLite rechazará cualquier escritura."""
    if not RUTA_BD.exists():
        raise FileNotFoundError(f"No encuentro la base de datos en {RUTA_BD}")
    uri = RUTA_BD.resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def obtener_esquema():
    """Lee de la propia base de datos las sentencias CREATE TABLE de todas las tablas."""
    conn = conectar_solo_lectura()
    try:
        filas = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL;"
        ).fetchall()
    finally:
        conn.close()
    return "\n\n".join(fila[0] for fila in filas)


def consultar_modelo(prompt):
    """Envía un prompt a Gemini y devuelve el SQL limpio de formato markdown."""
    respuesta = client.models.generate_content(model=MODELO, contents=prompt)
    if not respuesta.text:
        raise ValueError("El modelo no devolvió ningún texto.")
    sql = respuesta.text.strip()
    return sql.replace("```sql", "").replace("```", "").strip()


def pregunta_a_sql(pregunta, esquema):
    prompt = f"""
Eres un asistente que traduce preguntas en español a consultas SQL válidas para SQLite.

Esquema de la base de datos:
{esquema}

Reglas:
- Usa únicamente las tablas y columnas que aparecen en el esquema.
- Genera una sola consulta de solo lectura (SELECT).

Pregunta: {pregunta}

Responde ÚNICAMENTE con la consulta SQL, sin explicaciones, sin comillas de markdown, sin texto adicional.
"""
    return consultar_modelo(prompt)


def corregir_sql(pregunta, esquema, sql_fallido, error):
    """Devuelve al modelo su consulta fallida y el error de SQLite para que la corrija."""
    prompt = f"""
Eres un asistente que traduce preguntas en español a consultas SQL válidas para SQLite.

Esquema de la base de datos:
{esquema}

Pregunta original: {pregunta}

La siguiente consulta que generaste falla al ejecutarse:
{sql_fallido}

Mensaje de error de SQLite:
{error}

Corrige la consulta. Usa únicamente las tablas y columnas que aparecen en el esquema y genera una sola consulta SELECT.
Responde ÚNICAMENTE con la consulta SQL corregida, sin explicaciones, sin comillas de markdown, sin texto adicional.
"""
    return consultar_modelo(prompt)


def _sin_textos(sql):
    """Vacía el contenido de los textos entre comillas, para no confundirlos con instrucciones."""
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)
    return re.sub(r'"(?:[^"]|"")*"', '""', sql)


def validar_sql(sql):
    """Lanza ValueError si la consulta no es un SELECT simple. Devuelve la consulta limpia."""
    limpio = sql.strip().rstrip(";").strip()
    revisable = _sin_textos(limpio)

    if ";" in revisable:
        raise ValueError("Solo se permite una consulta a la vez.")

    if not re.match(r"^(select|with)\b", revisable, re.IGNORECASE):
        raise ValueError("Solo se permiten consultas que empiecen por SELECT.")

    for palabra in PALABRAS_PROHIBIDAS:
        if re.search(rf"\b{palabra}\b", revisable, re.IGNORECASE):
            raise ValueError(f"La consulta contiene una instrucción no permitida: {palabra.upper()}")

    return limpio


def ejecutar_sql(sql):
    conn = conectar_solo_lectura()
    try:
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()


def generar_y_ejecutar(pregunta, esquema):
    """Genera el SQL y lo ejecuta. Si SQLite da error, pide al modelo que lo corrija."""
    sql = pregunta_a_sql(pregunta, esquema)

    for intento in range(1, MAX_INTENTOS + 1):
        print(f"SQL generado (intento {intento}):\n{sql}\n")

        # Un rechazo de seguridad (ValueError) sale directamente: nunca se reintenta
        sql_valido = validar_sql(sql)

        try:
            return ejecutar_sql(sql_valido)
        except (sqlite3.Error, pd.errors.DatabaseError) as e:
            print(f"Error de SQLite: {e}\n")
            if intento == MAX_INTENTOS:
                raise
            sql = corregir_sql(pregunta, esquema, sql, str(e))


def responder(pregunta):
    print(f"\nPregunta: {pregunta}")

    try:
        resultado = generar_y_ejecutar(pregunta, obtener_esquema())
    except ValueError as e:
        print(f"Consulta rechazada: {e}")
        return None
    except (sqlite3.Error, pd.errors.DatabaseError) as e:
        print(f"No se pudo obtener una consulta válida tras {MAX_INTENTOS} intentos. Último error: {e}")
        return None
    except genai_errors.APIError as e:
        print(f"Error al llamar a la API de Gemini: {e}")
        return None

    if resultado.empty:
        print("La consulta se ejecutó pero no devolvió ninguna fila.")
    else:
        print(resultado.to_string(index=False))
    return resultado


if __name__ == "__main__":
    print("Escribe una pregunta sobre la base de datos (déjala vacía para salir).")
    while True:
        pregunta = input("\n> ").strip()
        if not pregunta:
            break
        responder(pregunta)