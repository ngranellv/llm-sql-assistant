import sqlite3

import pandas as pd
import streamlit as st
from google.genai import errors as genai_errors

from llm_sql import generar_y_ejecutar, obtener_esquema

st.set_page_config(page_title="Asistente SQL", page_icon="🎵")

st.title("Asistente de consultas en lenguaje natural")
st.caption(
    "Escribe una pregunta en español sobre la base de datos Chinook (una tienda de música). "
    "Un modelo de lenguaje la traduce a SQL, se valida y se ejecuta en modo solo lectura."
)


def mostrar_grafico(df):
    """Dibuja un gráfico de barras si el resultado es una columna de texto y otra numérica."""
    if df.shape[1] == 2 and len(df) > 1:
        etiqueta, valor = df.columns
        if not pd.api.types.is_numeric_dtype(df[etiqueta]) and pd.api.types.is_numeric_dtype(df[valor]):
            st.bar_chart(df.set_index(etiqueta)[valor])


# Con un formulario, pulsar Enter en la caja de texto también envía la pregunta
with st.form("consulta"):
    pregunta = st.text_input(
        "Tu pregunta",
        placeholder="¿Qué países han gastado más de 100 € en total?",
    )
    enviado = st.form_submit_button("Consultar")

if enviado:
    if not pregunta.strip():
        st.warning("Escribe una pregunta primero.")
    else:
        with st.spinner("Generando y ejecutando la consulta..."):
            try:
                sql, resultado = generar_y_ejecutar(pregunta.strip(), obtener_esquema())
            except ValueError as e:
                st.error(f"Consulta rechazada: {e}")
            except (sqlite3.Error, pd.errors.DatabaseError) as e:
                st.error(f"No se pudo obtener una consulta válida. Último error: {e}")
            except genai_errors.APIError as e:
                st.error(f"Error al llamar a la API de Gemini: {e}")
            else:
                st.subheader("SQL generado")
                st.code(sql, language="sql")

                st.subheader("Resultado")
                if resultado.empty:
                    st.info("La consulta se ejecutó pero no devolvió ninguna fila.")
                else:
                    st.dataframe(resultado)
                    mostrar_grafico(resultado)