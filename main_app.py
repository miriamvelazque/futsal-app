import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import json
import hashlib  # Para encriptar contraseñas de forma segura
import time

# =========================================================
# CONFIGURACIÓN DE PÁGINA
# =========================================================
st.set_page_config(page_title="Planilla Digital de Futsal", page_icon="📊", layout="wide")


# =========================================================
# CAPA DE SEGURIDAD (Autenticación y Roles)
# =========================================================
def encriptar_clave(clave):
    """Encripta la contraseña usando SHA-256."""
    return hashlib.sha256(clave.encode()).hexdigest()


def verificar_usuario(conn, usuario, clave):
    """Verifica si las credenciales son correctas y devuelve el rol del usuario."""
    c = conn.cursor()
    clave_encriptada = encriptar_clave(clave)
    c.execute("SELECT rol FROM usuarios WHERE usuario = ? AND clave = ?", (usuario, clave_encriptada))
    resultado = c.fetchone()
    return resultado[0] if resultado else None


def mostrar_login(conn):
    """Muestra un formulario estético de Login en el centro de la pantalla."""
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso Planilla Digital</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col2:
        with st.form("formulario_login"):
            st.markdown("### Iniciar Sesión")
            usuario = st.text_input("Usuario")
            clave = st.text_input("Contraseña", type="password")
            boton_ingresar = st.form_submit_button("Ingresar", use_container_width=True)
            
            if boton_ingresar:
                if not usuario or not clave:
                    st.warning("⚠️ Por favor, completá ambos campos.")
                else:
                    rol = verificar_usuario(conn, usuario, clave)
                    if rol:
                        st.session_state["usuario_logueado"] = usuario
                        st.session_state["rol_usuario"] = rol
                        st.success(f"¡Bienvenido {usuario}! Ingresando...")
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos.")


# =========================================================
# CAPA DE DATOS (SQLite)
# =========================================================
def get_connection():
    """Devuelve una conexión a la base de datos futsal.db, reutilizable entre pestañas."""
    conn = sqlite3.connect("futsal.db", check_same_thread=False)
    return conn


def init_db(conn):
    """Crea las tablas necesarias si no existen, incluyendo la de usuarios."""
    c = conn.cursor()
    
    # Tabla de partidos
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

    # Tabla de eventos
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
                    tipo_tarjeta TEXT,
                    x REAL,
                    y REAL
                )""")
    
    # Tabla de usuarios
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT UNIQUE,
                    clave TEXT,
                    rol TEXT
                )""")
    
    # Asegurar columnas X e Y en eventos
    c.execute("PRAGMA table_info(eventos)")
    columnas = [col[1] for col in c.fetchall()]
    if "x" not in columnas:
        c.execute("ALTER TABLE eventos ADD COLUMN x REAL")
    if "y" not in columnas:
        c.execute("ALTER TABLE eventos ADD COLUMN y REAL")
        
    # Insertar usuarios por defecto si la tabla está vacía leyendo desde secrets de Streamlit
    c.execute("SELECT COUNT(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        try:
            # Intentamos leer claves seguras desde secrets
            pass_admin = st.secrets["credentials"]["admin_pass"]
            pass_dt = st.secrets["credentials"]["dt_pass"]
        except Exception:
            # Claves de respaldo seguras en caso de no estar configuradas aún
            pass_admin = "admin123"
            pass_dt = "troncos2026"

        clave_admin = encriptar_clave(pass_admin)
        c.execute("INSERT INTO usuarios (usuario, clave, rol) VALUES (?, ?, ?)", 
                  ("admin", clave_admin, "Administrador"))
        
        clave_dt = encriptar_clave(pass_dt)
        c.execute("INSERT INTO usuarios (usuario, clave, rol) VALUES (?, ?, ?)", 
                  ("dt_troncos", clave_dt, "Lector"))
        
    conn.commit()


def cargar_partidos_df(conn):
    """Devuelve el DataFrame de partidos, o None si está vacío."""
    df = pd.read_sql("SELECT * FROM partidos", conn)
    return df if not df.empty else None


def cargar_eventos_df(conn, limit=None):
    """Devuelve el DataFrame de eventos de forma segura utilizando parámetros SQL."""
    if limit is not None:
        query = "SELECT * FROM eventos ORDER BY id DESC LIMIT ?"
        df = pd.read_sql(query, conn, params=(limit,))
    else:
        query = "SELECT * FROM eventos ORDER BY id DESC"
        df = pd.read_sql(query, conn)
    return df if not df.empty else None


def insertar_eventos_bulk(conn, df_upload):
    """Inserta eventos provenientes de un archivo CSV/Excel en la tabla eventos."""
    c = conn.cursor()
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
        x = row.get("x", None)
        y = row.get("y", None)

        c.execute("""INSERT INTO eventos (fecha, rival, tipo_evento, tiempo, equipo, jugador, zona, resultado, tipo_tarjeta, x, y)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (fecha, rival, tipo_evento, tiempo, equipo, jugador, zona, resultado, tipo_tarjeta, x, y))
        count += 1
    conn.commit()
    return count


def insertar_evento_individual(conn, fecha, rival, tipo_evento, tiempo, equipo, jugador, zona, resultado="", tipo_tarjeta="", x=None, y=None):
    """Inserta un único evento con coordenadas X e Y exactas en la tabla."""
    c = conn.cursor()
    c.execute("""INSERT INTO eventos (fecha, rival, tipo_evento, tiempo, equipo, jugador, zona, resultado, tipo_tarjeta, x, y)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (str(fecha), rival, tipo_evento, tiempo, equipo, jugador, zona, resultado, tipo_tarjeta, x, y))
    conn.commit()


# =========================================================
# COMPONENTES GRÁFICOS Y TRAZADO TÁCTICO FIEL A LA REFERENCIA
# =========================================================
CANCHA_ANCHO = 40  # metros real (eje X)
CANCHA_ALTO = 20   # metros real (eje Y)


def dibujar_capas_cancha(fig):
    """Agrega las formas reglamentarias de una cancha de Futsal oficial (40x20m) sin textos internos."""
    fig.add_shape(type="rect", x0=0, y0=0, x1=40, y1=20, fillcolor="#4158f6", line=dict(color="white", width=2.5), layer="below")
    fig.add_shape(type="path", path="M 0,4 Q 6,4 6,10 Q 6,16 0,16 Z", fillcolor="#e5a93c", line=dict(color="white", width=2), layer="below")
    fig.add_shape(type="path", path="M 40,4 Q 34,4 34,10 Q 34,16 40,16 Z", fillcolor="#e5a93c", line=dict(color="white", width=2), layer="below")
    fig.add_shape(type="circle", x0=17, y0=7, x1=23, y1=13, fillcolor="#e5a93c", line=dict(color="white", width=2), layer="below")
    fig.add_shape(type="line", x0=20, y0=0, x1=20, y1=20, line=dict(color="white", width=2.5))
    fig.add_trace(go.Scatter(x=[6, 10, 34, 30], y=[10, 10, 10, 10], mode="markers", marker=dict(color="white", size=5), showlegend=False, hoverinfo="skip"))
    fig.add_shape(type="rect", x0=-1.5, y0=8.5, x1=0, y1=11.5, fillcolor="rgba(0,0,0,0)", line=dict(color="white", width=2))
    fig.add_shape(type="rect", x0=40, y0=8.5, x1=41.5, y1=11.5, fillcolor="rgba(0,0,0,0)", line=dict(color="white", width=2))


def crear_figura_cancha():
    """Dibuja la cancha interactiva de Futsal limpia para la captura de datos tácticos."""
    xs = list(range(1, 100, 2))  
    ys = list(range(1, 60, 2))   
    grid_x = [x for y in ys for x in xs]
    grid_y = [y for y in ys for x in xs]

    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=grid_x, y=grid_y,
        mode="markers",
        marker=dict(size=14, color="#4158f6", opacity=0.01),
        hoverinfo="none",
        hovertemplate=None,
        showlegend=False,
        name="cancha_click"
    ))

    fig.add_shape(type="rect", x0=0, y0=0, x1=100, y1=60, fillcolor="#4158f6", line=dict(color="white", width=2.5), layer="below")
    fig.add_shape(type="path", path="M 0,12 Q 15,12 15,30 Q 15,48 0,48 Z", fillcolor="#e5a93c", line=dict(color="white", width=2), layer="below")
    fig.add_shape(type="path", path="M 100,12 Q 85,12 85,30 Q 85,48 100,48 Z", fillcolor="#e5a93c", line=dict(color="white", width=2), layer="below")
    fig.add_shape(type="circle", x0=42.5, y0=21, x1=57.5, y1=39, fillcolor="#e5a93c", line=dict(color="white", width=2), layer="below")
    fig.add_shape(type="line", x0=50, y0=0, x1=50, y1=60, line=dict(color="white", width=2.5))
    fig.add_shape(type="rect", x0=-3, y0=25.5, x1=0, y1=34.5, fillcolor="rgba(0,0,0,0)", line=dict(color="white", width=2))
    fig.add_shape(type="rect", x0=100, y0=25.5, x1=103, y1=34.5, fillcolor="rgba(0,0,0,0)", line=dict(color="white", width=2))

    fig.update_xaxes(range=[-5, 105], visible=False, fixedrange=True)
    fig.update_yaxes(range=[-3, 63], visible=False, fixedrange=True, scaleanchor="x")

    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=380, margin=dict(l=10, r=10, t=10, b=10),
        modebar=dict(remove=["zoom", "pan", "select2d", "lasso2d", "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d"])
    )
    return fig


def _reescalar_coordenadas(df, ancho_origen, alto_origen):
    """Transforma las coordenadas desde el sistema de clics (0-100, 0-60) a metros reales (40x20)."""
    df = df.copy()
    df["x"] = df["x"] * (CANCHA_ANCHO / ancho_origen)
    df["y"] = df["y"] * (CANCHA_ALTO / alto_origen)
    return df


def _matriz_densidad(x, y, bins_x=40, bins_y=20, pasadas_suavizado=2):
    """Calcula la matriz de densidad regular 2D y aplica suavizado por convolución."""
    hist, xedges, yedges = np.histogram2d(
        x, y, bins=[bins_x, bins_y], range=[[0, CANCHA_ANCHO], [0, CANCHA_ALTO]]
    )
    matriz = hist.T

    for _ in range(pasadas_suavizado):
        pad = np.pad(matriz, 1, mode="edge")
        matriz = (
            pad[1:-1, 1:-1] * 4
            + pad[:-2, 1:-1] + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:]
        ) / 8.0

    x_centros = (xedges[:-1] + xedges[1:]) / 2
    y_centros = (yedges[:-1] + yedges[1:]) / 2
    return matriz, x_centros, y_centros


def generar_heatmap_analisis(df_filtrado, titulo_mapa="Mapa de Densidad",
                             ancho_origen_captura=100, alto_origen_captura=60):
    """Genera el mapa de calor táctico definitivo reescalando las coordenadas."""
    fig = go.Figure()

    if df_filtrado is not None and not df_filtrado.empty:
        df_cancha = df_filtrado.copy()
        df_cancha["x"] = pd.to_numeric(df_cancha["x"], errors="coerce")
        df_cancha["y"] = pd.to_numeric(df_cancha["y"], errors="coerce")
        df_cancha = df_cancha.dropna(subset=["x", "y"])

        # Reescalamos de 100x60 a 40x20 antes del truncado por rango
        df_cancha = _reescalar_coordenadas(df_cancha, ancho_origen_captura, alto_origen_captura)
        df_cancha = df_cancha[(df_cancha["x"] >= 0) & (df_cancha["x"] <= CANCHA_ANCHO) &
                               (df_cancha["y"] >= 0) & (df_cancha["y"] <= CANCHA_ALTO)]

        if not df_cancha.empty:
            matriz, x_centros, y_centros = _matriz_densidad(df_cancha["x"].values, df_cancha["y"].values)
            max_val = np.max(matriz) if np.max(matriz) > 0 else 1

            # Capa del mapa de calor continuo
            fig.add_trace(go.Heatmap(
                x=x_centros, y=y_centros, z=matriz,
                colorscale="YlOrRd", opacity=0.75, showscale=True,
                zsmooth="best", hoverinfo="skip", name="Densidad Táctica",
                zmin=max_val * 0.1, zmax=max_val
            ))

            # Capa superior con todos los puntos exactos recuperados
            fig.add_trace(go.Scatter(
                x=df_cancha["x"], y=df_cancha["y"],
                mode="markers",
                marker=dict(color="black", size=7, opacity=0.85, line=dict(color="white", width=1.5)),
                text=df_cancha["tipo_evento"].astype(str) + " - J" + df_cancha["jugador"].astype(str),
                hoverinfo="text", name="Punto Exacto"
            ))

    dibujar_capas_cancha(fig)

    fig.update_xaxes(range=[-2, 42], visible=False, fixedrange=True)
    fig.update_yaxes(range=[-1, 21], visible=False, fixedrange=True, scaleanchor="x")

    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=400, margin=dict(l=10, r=10, t=40, b=10),
        title=dict(text=titulo_mapa, font=dict(size=15, color="white", family="Arial Black")),
        showlegend=False
    )
    return fig


def extraer_punto_click(evento_click):
    """Devuelve (x, y) del primer punto seleccionado, soportando dict y objeto."""
    if not evento_click:
        return None, None

    if isinstance(evento_click, dict):
        seleccion = evento_click.get("selection", {})
        puntos = seleccion.get("points", []) if isinstance(seleccion, dict) else []
    else:
        seleccion = getattr(evento_click, "selection", None)
        puntos = getattr(seleccion, "points", []) if seleccion else []

    if not puntos:
        return None, None

    primer_punto = puntos[0]
    if isinstance(primer_punto, dict):
        return primer_punto.get("x"), primer_punto.get("y")
    return getattr(primer_punto, "x", None), getattr(primer_punto, "y", None)


# =========================================================
# PESTAÑA 1: CARGA DE DATOS
# =========================================================
def render_carga_datos(conn):
    st.header("📥 Carga de Datos")

    # 🚨 BOTÓN DE EMERGENCIA SEGURO PARA ELIMINAR BASE DE DATOS Y EMPEZAR DE CERO
    st.warning("⚠️ **Zona de Reajuste:** Si querés borrar todos los datos de prueba anteriores para cargar tus partidos reales, usá este botón.")
    if st.button("🗑️ ELIMINAR BASE DE DATOS DE PRUEBA Y EMPEZAR DE CERO", type="primary", use_container_width=True):
        import os
        conn.close() # Cerramos conexión para liberar archivo en Windows
        if os.path.exists("futsal.db"):
            os.remove("futsal.db")
            st.success("💥 ¡Base de datos borrada con éxito! Reiniciando sistema en limpio...")
            time.sleep(2)
            st.rerun()

    st.divider()

    st.subheader("Cargar eventos desde CSV o Excel")
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
                count = insertar_eventos_bulk(conn, df_upload)
                st.success(f"✅ Se guardaron {count} eventos desde el archivo")
        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")

    st.divider()

    st.subheader("⏱️ Control de Posesión (Reloj Parado)")
    
    # --- INICIALIZACIÓN DE VARIABLES EN MEMORIA (SESSION STATE) ---
    if "pos_nuestra_acumulada" not in st.session_state:
        st.session_state.pos_nuestra_acumulada = 0.0
    if "pos_rival_acumulada" not in st.session_state:
        st.session_state.pos_rival_acumulada = 0.0
    if "pos_estado_actual" not in st.session_state:
        st.session_state.pos_estado_actual = "Pausa"
    if "pos_ultimo_click" not in st.session_state:
        st.session_state.pos_ultimo_click = None

    # --- LÓGICA DE ACTUALIZACIÓN DE TIEMPOS DE POSESIÓN ---
    ahora = time.time()

    if st.session_state.pos_estado_actual != "Pausa" and st.session_state.pos_ultimo_click is not None:
        transcurrido = ahora - st.session_state.pos_ultimo_click
        if st.session_state.pos_estado_actual == "Nosotros":
            st.session_state.pos_nuestra_acumulada += transcurrido
        elif st.session_state.pos_estado_actual == "Rival":
            st.session_state.pos_rival_acumulada += transcurrido
        st.session_state.pos_ultimo_click = ahora

    def formatear_tiempo(segundos_totales):
        minutos = int(segundos_totales) // 60
        segundos = int(segundos_totales) % 60
        return f"{minutos:02d}:{segundos:02d}"

    # --- DISEÑO DEL CONTROLLER DE POSESIÓN ---
    c_pos1, c_pos2, c_pos3, c_pos4 = st.columns([1.2, 1.2, 1.2, 1])

    with c_pos1:
        tipo_boton_nos = "primary" if st.session_state.pos_estado_actual == "Nosotros" else "secondary"
        if st.button("🟢 NUESTRA POSESIÓN", use_container_width=True, type=tipo_boton_nos):
            st.session_state.pos_estado_actual = "Nosotros"
            st.session_state.pos_ultimo_click = time.time()
            st.rerun()

    with c_pos2:
        tipo_boton_rival = "primary" if st.session_state.pos_estado_actual == "Rival" else "secondary"
        if st.button("🔴 POSESIÓN RIVAL", use_container_width=True, type=tipo_boton_rival):
            st.session_state.pos_estado_actual = "Rival"
            st.session_state.pos_ultimo_click = time.time()
            st.rerun()

    with c_pos3:
        tipo_boton_pausa = "primary" if st.session_state.pos_estado_actual == "Pausa" else "secondary"
        if st.button("⏸️ PAUSAR RELOJ", use_container_width=True, type=tipo_boton_pausa):
            st.session_state.pos_estado_actual = "Pausa"
            st.session_state.pos_ultimo_click = None
            st.rerun()

    with c_pos4:
        if st.button("🔄 RESET", use_container_width=True, help="Reiniciar cronómetros a cero"):
            st.session_state.pos_nuestra_acumulada = 0.0
            st.session_state.pos_rival_acumulada = 0.0
            st.session_state.pos_estado_actual = "Pausa"
            st.session_state.pos_ultimo_click = None
            st.rerun()

    # Marcadores rápidos debajo de los botones de posesión
    total_tiempo_neto = st.session_state.pos_nuestra_acumulada + st.session_state.pos_rival_acumulada
    pct_nuestro = (st.session_state.pos_nuestra_acumulada / total_tiempo_neto * 100) if total_tiempo_neto > 0 else 0
    pct_rival = (st.session_state.pos_rival_acumulada / total_tiempo_neto * 100) if total_tiempo_neto > 0 else 0

    col_res1, col_res2, col_res3 = st.columns(3)
    with col_res1:
        st.metric("⏱️ Nuestra Posesión", formatear_tiempo(st.session_state.pos_nuestra_acumulada), f"{pct_nuestro:.1f}%")
    with col_res2:
        estado_icon = "🟢" if st.session_state.pos_estado_actual == "Nosotros" else "🔴" if st.session_state.pos_estado_actual == "Rival" else "⏸️"
        st.metric("Estado Reloj", f"{estado_icon} {st.session_state.pos_estado_actual.upper()}")
    with col_res3:
        st.metric("⏱️ Posesión Rival", formatear_tiempo(st.session_state.pos_rival_acumulada), f"{pct_rival:.1f}%", delta_color="inverse")

    st.divider()

    st.subheader("⚡ Carga rápida de eventos (clic en la cancha)")

    col_ctx1, col_ctx2, col_ctx3 = st.columns([1, 1, 1.2])
    with col_ctx1:
        fecha = st.date_input("Fecha del partido", key="fecha_partido")
    with col_ctx2:
        rival = st.text_input("Equipo rival", key="rival_partido")
    with col_ctx3:
        lado_inicio = st.selectbox(
            "En el 1T atacamos hacia:", 
            [
                "Derecha ➡️ (Arco Rival a la Derecha)", 
                "Izquierda ⬅️ (Arco Rival a la Izquierda)"
            ],
            key="lado_inicio_1t"
        )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        tipo_evento = st.selectbox("Tipo de evento", ["Finalizaciones", "Recuperos", "Perdidas", "Faltas", "Tarjetas"], key="tipo_evento_rapido")
    with col2:
        jugador = st.text_input("Número de jugador", key="jugador_rapido")
    with col3:
        tiempo = st.selectbox("Tiempo", ["1T", "2T"], key="tiempo_rapido")
    with col4:
        equipo = st.selectbox("Equipo", ["Propio", "Rival"], key="equipo_rapido")

    resultado, tipo_tarjeta = "", ""
    if tipo_evento == "Finalizaciones":
        # ⭐ OPCIONES SÚPER ACTUALIZADAS PARA TU SISTEMA
        resultado = st.selectbox("Resultado", ["Gol", "Atajado", "Desviado", "Bloqueado"], key="resultado_rapido")
    elif tipo_evento == "Tarjetas":
        tipo_tarjeta = st.selectbox("Tipo de tarjeta", ["Amarilla", "Roja"], key="tipo_tarjeta_rapido")

    st.info("💡 **Instrucciones:** Completá la info del jugador arriba y hacé **un clic directo** en la cancha táctica. El sistema procesará automáticamente el lado de ataque actual según tu configuración de sorteo.")
    
    fig_cancha = crear_figura_cancha()

    evento_click = st.plotly_chart(
        fig_cancha, use_container_width=True,
        on_select="rerun", selection_mode="points", key="click_cancha"
    )

    x_click, y_click = extraer_punto_click(evento_click)

    if x_click is not None and y_click is not None:
        click_id = (x_click, y_click, tipo_evento, jugador, tiempo, equipo)

        if not jugador:
            st.warning("⚠️ Ingresá el número de jugador antes de hacer clic en la cancha")
        elif st.session_state.get("ultimo_click_registrado") != click_id:
            
            # --- LÓGICA INTELIGENTE DE DETERMINACIÓN DE LADOS ---
            es_1t_y_ataca_izquierda = (tiempo == "1T" and "Izquierda" in lado_inicio)
            es_2t_y_ataca_izquierda = (tiempo == "2T" and "Derecha" in lado_inicio)

            if es_1t_y_ataca_izquierda or es_2t_y_ataca_izquierda:
                zona = "Ofensiva" if x_click < 50 else "Defensiva"
                x_guardar = 100 - x_click
                y_guardar = 60 - y_click
            else:
                zona = "Defensiva" if x_click < 50 else "Ofensiva"
                x_guardar = x_click
                y_guardar = y_click

            # Guardamos los datos normalizados en la DB
            insertar_evento_individual(
                conn, fecha, rival, tipo_evento, tiempo, equipo,
                jugador, zona, resultado, tipo_tarjeta, x=x_guardar, y=y_guardar
            )

            st.session_state["ultimo_click_registrado"] = click_id
            st.success(f"✅ ¡Registrado! {tipo_evento} ({zona}) - Jugador {jugador}. Guardado de manera normalizada.")
            st.rerun()
    else:
        st.caption("📍 Esperando clic posicional...")

    st.divider()

    st.subheader("Últimos eventos cargados")
    df_eventos_recientes = cargar_eventos_df(conn, limit=10)
    if df_eventos_recientes is not None:
        st.dataframe(df_eventos_recientes)
    else:
        st.info("No hay eventos cargados aún")


# =========================================================
# PESTAÑA 2: DASHBOARD GENERAL
# =========================================================
def render_dashboard_general(conn):
    st.header("📈 Dashboard Analítico Avanzado")

    df_eventos = cargar_eventos_df(conn)
    if df_eventos is None:
        st.info("No hay eventos cargados aún. Registrá datos en la primera pestaña.")
        return

    # --- Creamos columna combinada de Fecha - Rival para el selector ---
    df_eventos["partido"] = df_eventos["fecha"].astype(str) + " - " + df_eventos["rival"].astype(str)

    # --- BARRA DE FILTROS SUPERIOR ---
    st.markdown("### 🔍 Filtros Globales")
    c1, c2, c3 = st.columns(3)
    with c1:
        partidos_disponibles = ["Todos"] + sorted(list(df_eventos["partido"].dropna().unique()), reverse=True)
        partido_sel = st.selectbox("Filtrar por Partido (Fecha - Rival)", partidos_disponibles)
    with c2:
        jugadores_disponibles = ["Todos"] + sorted(list(df_eventos["jugador"].dropna().unique()))
        jugador_sel = st.selectbox("Filtrar por Jugador", jugadores_disponibles)
    with c3:
        tipos_disponibles = ["Todos"] + list(df_eventos["tipo_evento"].dropna().unique())
        tipo_sel = st.selectbox("Filtrar por Tipo de Acción", tipos_disponibles)

    # Filtros cruzados
    df_filtrado = df_eventos.copy()
    if partido_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["partido"] == partido_sel]
    if jugador_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["jugador"] == jugador_sel]
    if tipo_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["tipo_evento"] == tipo_sel]

    # --- INDICADORES ---
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Acciones Filtradas", len(df_filtrado))
    with col2:
        # ⭐ CORRECCIÓN: Contamos como tiros al arco tanto Goles como Atajados
        tiros_efectivos = len(df_filtrado[(df_filtrado["tipo_evento"] == "Finalizaciones") & (df_filtrado["resultado"].isin(["Gol", "Atajado"]))])
        st.metric("Goles/Tiros al Arco", tiros_efectivos)
    with col3:
        st.metric("Balones Perdidos", len(df_filtrado[df_filtrado["tipo_evento"] == "Perdidas"]))
    with col4:
        st.metric("Recuperaciones", len(df_filtrado[df_filtrado["tipo_evento"] == "Recuperos"]))

    # --- DISEÑO TÁCTICO INTERACTIVO (Fila Superior) ---
    st.divider()
    col_izq, col_der = st.columns([1.3, 1])

    with col_izq:
        st.subheader("📍 Mapa de Distribución y Calor de Futsal")
        txt_mapa = f"Filtro - Jugador: {jugador_sel} | Acción: {tipo_sel}"
        fig_heatmap = generar_heatmap_analisis(df_filtrado, titulo_mapa=txt_mapa)
        st.plotly_chart(fig_heatmap, use_container_width=True)

    with col_der:
        st.subheader("📊 Distribución de Volumen Táctico")
        if not df_filtrado.empty:
            counts = df_filtrado["tipo_evento"].value_counts().reset_index()
            counts.columns = ["Tipo de Acción", "Cantidad"]
            fig_barras = px.bar(
                counts, x="Cantidad", y="Tipo de Acción", 
                orientation="h", color="Tipo de Acción",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_barras.update_layout(showlegend=False, height=380, margin=dict(t=20, b=20))
            st.plotly_chart(fig_barras, use_container_width=True)
        else:
            st.info("Sin datos para generar gráficos.")

    # --- NUEVA SECCIÓN: DESGLOSE DE FINALIZACIONES Y TABLA DE GOLEADORES (Fila Inferior) ---
    if not df_filtrado.empty:
        df_finalizaciones = df_filtrado[df_filtrado["tipo_evento"] == "Finalizaciones"]
        
        if not df_finalizaciones.empty:
            st.divider()
            st.markdown("### 🎯 Análisis de Efectividad en Finalizaciones")
            
            col_tabla_f, col_grafico_f, col_goleadores = st.columns([1.1, 1.0, 1.1])
            
            with col_tabla_f:
                st.markdown("#### 📋 Detalle de Tiros")
                res_counts = df_finalizaciones["resultado"].fillna("Sin especificar").value_counts().reset_index()
                res_counts.columns = ["Resultado", "Cantidad"]
                
                total_fin = res_counts["Cantidad"].sum()
                res_counts["Porcentaje"] = ((res_counts["Cantidad"] / total_fin) * 100).round(1).astype(str) + "%"
                
                st.dataframe(res_counts, use_container_width=True, hide_index=True)
                
            with col_grafico_f:
                fig_torta = px.pie(
                    res_counts, values="Cantidad", names="Resultado",
                    color="Resultado",
                    color_discrete_sequence=px.colors.qualitative.Safe,
                    hole=0.4
                )
                fig_torta.update_layout(
                    height=240, 
                    margin=dict(t=10, b=10, l=10, r=10),
                    showlegend=False
                )
                st.plotly_chart(fig_torta, use_container_width=True)

            with col_goleadores:
                st.markdown("#### ⚽ Tabla de Goleadores")
                
                # ⭐ CORRECCIÓN: Filtramos exclusivamente los resultados anotados como "Gol"
                df_goles = df_finalizaciones[df_finalizaciones["resultado"].str.lower().str.contains("gol", na=False)]
                
                if not df_goles.empty:
                    goleadores = df_goles["jugador"].value_counts().reset_index()
                    goleadores.columns = ["Jugador", "Goles"]
                    
                    st.dataframe(
                        goleadores, 
                        column_config={
                            "Jugador": st.column_config.TextColumn("Camiseta / Jugador", help="Número de camiseta registrado"),
                            "Goles": st.column_config.NumberColumn("Goles", format="%d ⚽")
                        },
                        use_container_width=True, 
                        hide_index=True
                    )
                else:
                    st.info("No se registraron goles en los partidos seleccionados.")


# =========================================================
# PESTAÑA 3: RENDIMIENTO INDIVIDUAL
# =========================================================
def render_rendimiento_individual(conn):
    st.header("🏃 Rendimiento Individual y Scouting")

    df_eventos = cargar_eventos_df(conn)
    if df_eventos is None:
        st.info("No hay eventos cargados aún. Registrá datos en la primera pestaña para analizar jugadores.")
        return

    # Creamos columna combinada de Fecha - Rival para el filtrado individual
    df_eventos["partido"] = df_eventos["fecha"].astype(str) + " - " + df_eventos["rival"].astype(str)

    # --- PANEL DE FILTROS INDIVIDUALES ---
    st.markdown("### 🔍 Filtros de Jugador")
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        jugadores_disponibles = sorted(df_eventos["jugador"].dropna().unique())
        jugador_sel = st.selectbox("Seleccionar Jugador", jugadores_disponibles, key="rend_indiv_sel")
    
    df_base_jugador = df_eventos[df_eventos["jugador"] == jugador_sel]
    
    with col_f2:
        partidos_disponibles = ["Todos"] + sorted(list(df_base_jugador["partido"].dropna().unique()), reverse=True)
        partido_sel = st.selectbox("Filtrar por Partido / Rival", partidos_disponibles, key="rend_rival_sel")
    
    with col_f3:
        tiempos_disponibles = ["Todos"] + list(df_base_jugador["tiempo"].dropna().unique())
        tiempo_sel = st.selectbox("Filtrar por Tiempo de Juego", tiempos_disponibles, key="rend_tiempo_sel")

    df_jugador_filtrado = df_base_jugador.copy()
    if partido_sel != "Todos":
        df_jugador_filtrado = df_jugador_filtrado[df_jugador_filtrado["partido"] == partido_sel]
    if tiempo_sel != "Todos":
        df_jugador_filtrado = df_jugador_filtrado[df_jugador_filtrado["tiempo"] == tiempo_sel]

    st.divider()

    # --- TARJETAS DE MÉTRICAS INDIVIDUALES ---
    st.markdown(f"### 📈 Estadísticas Clave: Jugador {jugador_sel}")
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        total_acciones = len(df_jugador_filtrado)
        st.metric("Total Acciones", total_acciones)
    with m2:
        # ⭐ CORRECCIÓN: Consideramos Tiros al Arco los anotados como "Gol" y "Atajado"
        goles_tiros = len(df_jugador_filtrado[(df_jugador_filtrado["tipo_evento"] == "Finalizaciones") & (df_jugador_filtrado["resultado"].isin(["Gol", "Atajado"]))])
        st.metric("Tiros al Arco", goles_tiros)
    with m3:
        recuperos = len(df_jugador_filtrado[df_jugador_filtrado["tipo_evento"] == "Recuperos"])
        st.metric("Recuperaciones", recuperos)
    with m4:
        perdidas = len(df_jugador_filtrado[df_jugador_filtrado["tipo_evento"] == "Perdidas"])
        st.metric("Pérdidas de Balón", perdidas)

    st.divider()

    # --- DISPOSICIÓN VISUAL (MAPA + TABLA DETALLADA) ---
    col_mapa, col_tabla = st.columns([1.2, 1])

    with col_mapa:
        st.subheader("📍 Mapa de Calor Propio")
        txt_mapa_indiv = f"Densidad en Cancha - Jugador {jugador_sel}"
        fig_heatmap_indiv = generar_heatmap_analisis(df_jugador_filtrado, titulo_mapa=txt_mapa_indiv)
        st.plotly_chart(fig_heatmap_indiv, use_container_width=True, key="heatmap_individual_chart")

    with col_tabla:
        st.subheader("📋 Historial de Acciones")
        if not df_jugador_filtrado.empty:
            columnas_visibles = ["fecha", "rival", "tipo_evento", "tiempo", "equipo", "zona", "resultado", "tipo_tarjeta"]
            df_tabla_limpia = df_jugador_filtrado[columnas_visibles].reset_index(drop=True)
            st.dataframe(df_tabla_limpia, use_container_width=True, height=380)
        else:
            st.info("Sin registros para los filtros seleccionados.")

    # --- NUEVA SECCIÓN: DESGLOSE DE FINALIZACIONES DEL JUGADOR (Fila Inferior) ---
    if not df_jugador_filtrado.empty:
        df_fin_jugador = df_jugador_filtrado[df_jugador_filtrado["tipo_evento"] == "Finalizaciones"]
        
        if not df_fin_jugador.empty:
            st.divider()
            st.markdown(f"### 🎯 Efectividad de Remates - Jugador {jugador_sel}")
            col_t_ind, col_g_ind = st.columns([1, 1.2])
            
            with col_t_ind:
                st.markdown("#### 📋 Desglose de sus tiros")
                res_counts_j = df_fin_jugador["resultado"].fillna("Sin especificar").value_counts().reset_index()
                res_counts_j.columns = ["Resultado", "Cantidad"]
                total_fin_j = res_counts_j["Cantidad"].sum()
                res_counts_j["Porcentaje"] = ((res_counts_j["Cantidad"] / total_fin_j) * 100).round(1).astype(str) + "%"
                
                st.dataframe(res_counts_j, use_container_width=True, hide_index=True)
                
            with col_g_ind:
                fig_torta_j = px.pie(
                    res_counts_j, values="Cantidad", names="Resultado",
                    color="Resultado",
                    color_discrete_sequence=px.colors.qualitative.Bold,
                    hole=0.4
                )
                fig_torta_j.update_layout(
                    height=240, 
                    margin=dict(t=10, b=10, l=10, r=10),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_torta_j, use_container_width=True, key="torta_individual_finalizaciones")


# =========================================================
# FUNCIÓN PRINCIPAL (MAIN con Gestión de Sesión)
# =========================================================
def main():
    conn = get_connection()
    init_db(conn)

    # ⭐ CORRECCIÓN SEGURIDAD: Inicializar estado antes del chequeo para evitar renderizado huérfano
    if "usuario_logueado" not in st.session_state:
        st.session_state["usuario_logueado"] = None
    if "rol_usuario" not in st.session_state:
        st.session_state["rol_usuario"] = None

    # 1. Verificar si hay sesión activa. Si no, renderizar el Login
    if st.session_state["usuario_logueado"] is None:
        mostrar_login(conn)
        return  # Detiene la ejecución para usuarios no autenticados

    # 2. Sidebar con información de sesión y botón de salir
    st.sidebar.markdown(f"### 👤 Usuario: **{st.session_state['usuario_logueado']}**")
    st.sidebar.markdown(f"🔑 Rol: `{st.session_state['rol_usuario']}`")
    
    st.sidebar.divider()
    if st.sidebar.button("Cerrar Sesión", use_container_width=True):
        st.session_state["usuario_logueado"] = None
        st.session_state["rol_usuario"] = None
        st.rerun()

    # 3. Control de acceso a pestañas por ROLES
    rol_actual = st.session_state["rol_usuario"]

    if rol_actual == "Administrador":
        # Acceso total a todas las funciones
        st.title("📊 Planilla Digital de Futsal - Panel Admin")
        tab1, tab2, tab3 = st.tabs(["Carga de Datos", "Dashboard General", "Rendimiento Individual"])
        
        with tab1:
            render_carga_datos(conn)
        with tab2:
            render_dashboard_general(conn)
        with tab3:
            render_rendimiento_individual(conn)
            
    elif rol_actual == "Lector":
        # Acceso limitado: Ocultamos pestaña de carga de datos para proteger la integridad de la DB
        st.title("📊 Planilla Digital de Futsal")
        tab2, tab3 = st.tabs(["Dashboard General", "Rendimiento Individual"])
        
        with tab2:
            render_dashboard_general(conn)
        with tab3:
            render_rendimiento_individual(conn)


if __name__ == "__main__":
    main()