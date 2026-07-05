import streamlit as st
import pandas as pd
from pathlib import Path

# Cargar dataset real si existe, si no usar el sintético
csv_path = "eventos_reales.csv" if Path("eventos_reales.csv").exists() else "eventos_sinteticos.csv"
df = pd.read_csv(csv_path)

st.title("📊 Dashboard de Futsal" + (" (Datos Reales)" if csv_path == "eventos_reales.csv" else " (Datos Sintéticos)"))

# --- Eventos por tipo ---
st.subheader("Eventos por tipo")
tipo_counts = df["tipo_evento"].value_counts()
st.bar_chart(tipo_counts)

# --- Comparación por jugador ---
st.subheader("Eventos por jugador")
jugador_counts = df["jugador"].value_counts().sort_index()
st.bar_chart(jugador_counts)

# --- Comparación por equipo ---
st.subheader("Eventos por equipo")
equipo_counts = df["equipo"].value_counts()
st.bar_chart(equipo_counts)

# --- Comparación por tiempo ---
st.subheader("Eventos por tiempo")
tiempo_counts = df["tiempo"].value_counts()
st.bar_chart(tiempo_counts)

# --- Filtros interactivos ---
st.subheader("Filtrar por jugador o rival")
jugador_sel = st.selectbox("Seleccionar jugador", sorted(df["jugador"].unique()))
rival_sel = st.selectbox("Seleccionar rival", sorted(df["rival"].unique()))

df_filtrado = df[(df["jugador"] == jugador_sel) | (df["rival"] == rival_sel)]
st.write(df_filtrado)
