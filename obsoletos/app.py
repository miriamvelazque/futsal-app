import streamlit as st
import pandas as pd
import sqlite3
import json

# --- Configuración de base de datos ---
conn = sqlite3.connect("futsal.db")
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS partidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                rival TEXT,
                finalizaciones TEXT,
                recuperos TEXT,
                perdidas TEXT,
                faltas TEXT,
                tarjetas TEXT
            )""")

c.execute("""CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                rival TEXT,
                tipo_evento TEXT,
                tiempo TEXT,
                equipo TEXT,
                jugador TEXT,
                zona TEXT,
                resultado TEXT,
                tipo_tarjeta TEXT
            )""")
conn.commit()

st.title("📊 Planilla Digital de Futsal")

st.subheader("Cargar partidos desde CSV o Excel")
st.info("Formato recomendado: fecha, rival, tipo_evento, tiempo, equipo, jugador, zona, resultado, tipo_tarjeta")
uploaded_file = st.file_uploader("Subí tu archivo con los eventos", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".csv"):
            df_upload = pd.read_csv(uploaded_file)
        else:
            df_upload = pd.read_excel(uploaded_file)

        st.write("Vista previa del archivo:")
        st.dataframe(df_upload.head(10))

        if st.button("Guardar eventos cargados"):
            count = 0
            for _, row in df_upload.iterrows():
                fecha = str(row.get("fecha", "")) if not pd.isna(row.get("fecha", "")) else ""
                rival = str(row.get("rival", "")) if not pd.isna(row.get("rival", "")) else ""
                tipo_evento = str(row.get("tipo_evento", row.get("tipo", row.get("evento", ""))))
                tiempo = str(row.get("tiempo", "")) if not pd.isna(row.get("tiempo", "")) else ""
                equipo = str(row.get("equipo", "")) if not pd.isna(row.get("equipo", "")) else ""
                jugador = str(row.get("jugador", "")) if not pd.isna(row.get("jugador", "")) else ""
                zona = str(row.get("zona", "")) if not pd.isna(row.get("zona", "")) else ""
                resultado = str(row.get("resultado", "")) if not pd.isna(row.get("resultado", "")) else ""
                tipo_tarjeta = str(row.get("tipo_tarjeta", "")) if not pd.isna(row.get("tipo_tarjeta", "")) else ""

                c.execute("""INSERT INTO eventos (fecha, rival, tipo_evento, tiempo, equipo, jugador, zona, resultado, tipo_tarjeta)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (fecha, rival, tipo_evento, tiempo, equipo, jugador, zona, resultado, tipo_tarjeta))
                count += 1

            conn.commit()
            st.success(f"✅ Se guardaron {count} eventos desde el archivo")
    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")

st.subheader("Carga manual de un partido")
fecha = st.date_input("Fecha del partido")
rival = st.text_input("Equipo rival")

# --- Función para cargar eventos ---
def cargar_eventos(nombre, opciones_extra=None):
    eventos = []
    num = st.number_input(f"Cantidad de {nombre}", 0)
    for i in range(num):
        tiempo = st.selectbox(f"Tiempo ({nombre} {i+1})", ["1T", "2T"])
        equipo = st.selectbox(f"Equipo ({nombre} {i+1})", ["Local", "Visitante"])
        jugador = st.text_input(f"Número de jugador ({nombre} {i+1})")
        zona = st.selectbox(f"Zona ({nombre} {i+1})", ["Ofensiva", "Defensiva"])
        extra = {}
        if opciones_extra:
            for campo, opciones in opciones_extra.items():
                extra[campo] = st.selectbox(f"{campo} ({nombre} {i+1})", opciones)
        evento = {"tiempo": tiempo, "equipo": equipo, "jugador": jugador, "zona": zona}
        evento.update(extra)
        eventos.append(evento)
    return eventos

# --- Eventos ---
st.subheader("Finalizaciones")
finalizaciones = cargar_eventos("Finalizaciones", {"Resultado": ["Al arco", "Desviado", "Bloqueado"]})

st.subheader("Recuperos")
recuperos = cargar_eventos("Recuperos")

st.subheader("Pérdidas")
perdidas = cargar_eventos("Pérdidas")

st.subheader("Faltas")
faltas = cargar_eventos("Faltas")

st.subheader("Tarjetas")
tarjetas = cargar_eventos("Tarjetas", {"Tipo": ["Amarilla", "Roja"]})

# --- Guardar partido ---
if st.button("Guardar partido"):
    c.execute("""INSERT INTO partidos (fecha, rival, finalizaciones, recuperos, perdidas, faltas, tarjetas)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (str(fecha), rival,
               json.dumps(finalizaciones), json.dumps(recuperos),
               json.dumps(perdidas), json.dumps(faltas), json.dumps(tarjetas)))
    conn.commit()
    st.success("✅ Partido guardado correctamente")

# --- Estadísticas acumuladas ---
st.subheader("Estadísticas acumuladas")
df = pd.read_sql("SELECT * FROM partidos", conn)
if not df.empty:
    st.write(df)

st.subheader("Eventos ya cargados")
df_eventos = pd.read_sql("SELECT * FROM eventos ORDER BY id DESC LIMIT 20", conn)
if not df_eventos.empty:
    st.write(df_eventos)


