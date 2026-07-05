import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# Cargar dataset real si existe, si no usar el sintético
csv_path = "eventos_reales.csv" if Path("eventos_reales.csv").exists() else "eventos_sinteticos.csv"
df = pd.read_csv(csv_path)

st.title("📊 Dashboard de Futsal" + (" (Datos Reales)" if csv_path == "eventos_reales.csv" else " (Datos Sintéticos)"))

# --- Eventos por jugador con gráfico interactivo ---
st.subheader("Eventos por jugador (interactivo)")
jugador_counts = df["jugador"].value_counts().sort_index()
fig = px.bar(
    jugador_counts,
    x=jugador_counts.index,
    y=jugador_counts.values,
    labels={"x": "Jugador", "y": "Cantidad de eventos"},
    title="Eventos por jugador"
)
st.plotly_chart(fig)

# --- Filtro dinámico ---
st.subheader("Filtrar por jugador")
jugador_sel = st.selectbox("Seleccionar jugador", sorted(df["jugador"].unique()))

df_jugador = df[df["jugador"] == jugador_sel]
st.write(f"Eventos del jugador {jugador_sel}")
st.dataframe(df_jugador)

# --- Gráfico de eficiencia del jugador seleccionado ---
if not df_jugador.empty and "Finalizacion" in df_jugador["tipo_evento"].values:
    finalizaciones_jugador = df_jugador[df_jugador["tipo_evento"] == "Finalizacion"]
    eficiencia_jugador = finalizaciones_jugador["resultado"].value_counts()
    fig2 = px.bar(
        eficiencia_jugador,
        x=eficiencia_jugador.index,
        y=eficiencia_jugador.values,
        labels={"x": "Resultado", "y": "Cantidad"},
        title=f"Eficiencia de finalizaciones - Jugador {jugador_sel}"
    )
    st.plotly_chart(fig2)

# --- Comparación múltiple de jugadores ---
st.subheader("Comparar varios jugadores")
jugadores_sel = st.multiselect("Seleccionar jugadores", sorted(df["jugador"].unique()))

if jugadores_sel:
    df_multi = df[df["jugador"].isin(jugadores_sel)]

    # Gráfico de cantidad de eventos por jugador
    eventos_por_jugador = df_multi["jugador"].value_counts().sort_index()
    fig = px.bar(
        eventos_por_jugador,
        x=eventos_por_jugador.index,
        y=eventos_por_jugador.values,
        labels={"x": "Jugador", "y": "Cantidad de eventos"},
        title="Eventos por jugadores seleccionados"
    )
    st.plotly_chart(fig)

    # Gráfico de eficiencia de finalizaciones por jugador
    finalizaciones_multi = df_multi[df_multi["tipo_evento"] == "Finalizacion"]
    if not finalizaciones_multi.empty:
        eficiencia_multi = (
            finalizaciones_multi.groupby(["jugador", "resultado"])
            .size()
            .unstack(fill_value=0)
        )
        eficiencia_multi = eficiencia_multi.reset_index()

        fig2 = px.bar(
            eficiencia_multi,
            x="jugador",
            y=eficiencia_multi.columns[1:],
            barmode="group",
            labels={"value": "Cantidad", "variable": "Resultado"},
            title="Eficiencia de finalizaciones por jugador"
        )
        st.plotly_chart(fig2)
    st.dataframe(df_multi)
