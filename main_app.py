import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import json
import hashlib  # Para encriptar contraseñas de forma segura
import time
import streamlit.components.v1 as components
import os
from datetime import date
PLAYER_PHOTOS_DIR = "player_photos"
os.makedirs(PLAYER_PHOTOS_DIR, exist_ok=True)


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
    
    # Tabla de jugadores
    c.execute("""CREATE TABLE IF NOT EXISTS jugadores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT,
                    apellido TEXT,
                    dni TEXT UNIQUE,
                    comet TEXT,
                    fecha_nacimiento TEXT,
                    numero_camiseta INTEGER,
                    posicion TEXT,
                    pie_habil TEXT,
                    grupo_sanguineo TEXT,
                    obra_social TEXT,
                    telefono TEXT,
                    direccion TEXT,
                    contacto_emergencia_nombre TEXT,
                    contacto_emergencia_telefono TEXT,
                    estado TEXT DEFAULT 'Habilitado',
                    foto_path TEXT,
                    fecha_alta TEXT,
                    observaciones TEXT,
                    activo INTEGER DEFAULT 1
                )""")
    
    # --- MANTENIMIENTO DE COLUMNAS (ALTER TABLE) ---
    
    # Asegurar columnas X e Y en eventos
    c.execute("PRAGMA table_info(eventos)")
    columnas_eventos = [col[1] for col in c.fetchall()]
    if "x" not in columnas_eventos:
        c.execute("ALTER TABLE eventos ADD COLUMN x REAL")
    if "y" not in columnas_eventos:
        c.execute("ALTER TABLE eventos ADD COLUMN y REAL")

    # Asegurar columnas nuevas en tabla partidos
    c.execute("PRAGMA table_info(partidos)")
    columnas_partidos = [col[1] for col in c.fetchall()]
    nuevas_columnas_partidos = {
        "equipo_propio": "TEXT",
        "lugar": "TEXT",
        "lado_inicio_1t": "TEXT",
        "posesion_1t_propio_seg": "REAL",
        "posesion_1t_rival_seg": "REAL",
        "posesion_2t_propio_seg": "REAL",
        "posesion_2t_rival_seg": "REAL",
    }
    for col_nombre, col_tipo in nuevas_columnas_partidos.items():
        if col_nombre not in columnas_partidos:
            c.execute(f"ALTER TABLE partidos ADD COLUMN {col_nombre} {col_tipo}")
        
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
        
     # Migración futura de columnas (mismo patrón que usás en partidos)
    c.execute("PRAGMA table_info(jugadores)")
    columnas_jugadores = [col[1] for col in c.fetchall()]
    nuevas_columnas_jugadores = {
        "posicion": "TEXT", "pie_habil": "TEXT", "estado": "TEXT DEFAULT 'Habilitado'",
        "contacto_emergencia_nombre": "TEXT", "contacto_emergencia_telefono": "TEXT",
        "fecha_alta": "TEXT", "observaciones": "TEXT", "activo": "INTEGER DEFAULT 1",
    }
    for col_nombre, col_tipo in nuevas_columnas_jugadores.items():
        if col_nombre not in columnas_jugadores:
            c.execute(f"ALTER TABLE jugadores ADD COLUMN {col_nombre} {col_tipo}")

    os.makedirs(PLAYER_PHOTOS_DIR, exist_ok=True)
        
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

def guardar_posesion_partido(conn, fecha, rival, equipo_propio, lugar, lado_inicio_1t,
                              pos_1t_propio, pos_1t_rival, pos_2t_propio, pos_2t_rival):
    """Inserta o actualiza (upsert) el registro de partido con los datos de posesión por tiempo."""
    c = conn.cursor()
    c.execute("SELECT id FROM partidos WHERE fecha = ? AND rival = ?", (str(fecha), rival))
    existente = c.fetchone()
    if existente:
        c.execute("""UPDATE partidos SET equipo_propio=?, lugar=?, lado_inicio_1t=?,
                     posesion_1t_propio_seg=?, posesion_1t_rival_seg=?,
                     posesion_2t_propio_seg=?, posesion_2t_rival_seg=?
                     WHERE id=?""",
                  (equipo_propio, lugar, lado_inicio_1t, pos_1t_propio, pos_1t_rival,
                   pos_2t_propio, pos_2t_rival, existente[0]))
    else:
        c.execute("""INSERT INTO partidos (fecha, rival, equipo_propio, lugar, lado_inicio_1t,
                     posesion_1t_propio_seg, posesion_1t_rival_seg,
                     posesion_2t_propio_seg, posesion_2t_rival_seg)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (str(fecha), rival, equipo_propio, lugar, lado_inicio_1t,
                   pos_1t_propio, pos_1t_rival, pos_2t_propio, pos_2t_rival))
    conn.commit()


def formatear_tiempo(segundos_totales):
    """Convierte segundos a formato MM:SS. Usado en Carga de Datos y en Dashboard General."""
    minutos = int(segundos_totales) // 60
    segundos = int(segundos_totales) % 60
    return f"{minutos:02d}:{segundos:02d}"


def calcular_tenencia_partido(df_partidos, partido_sel="Todos", tiempo_sel="Todos"):
    """Suma los segundos de posesión propia/rival desde la tabla partidos,
    respetando los filtros de Partido y Tiempo de juego del Dashboard General."""
    if df_partidos is None or df_partidos.empty:
        return 0.0, 0.0

    dfp = df_partidos.copy()
    dfp["partido"] = dfp["fecha"].astype(str) + " - " + dfp["rival"].astype(str)
    if partido_sel != "Todos":
        dfp = dfp[dfp["partido"] == partido_sel]
    if dfp.empty:
        return 0.0, 0.0

    if tiempo_sel == "1T":
        propio = dfp["posesion_1t_propio_seg"].fillna(0).sum()
        rival = dfp["posesion_1t_rival_seg"].fillna(0).sum()
    elif tiempo_sel == "2T":
        propio = dfp["posesion_2t_propio_seg"].fillna(0).sum()
        rival = dfp["posesion_2t_rival_seg"].fillna(0).sum()
    else:
        propio = dfp[["posesion_1t_propio_seg", "posesion_2t_propio_seg"]].fillna(0).sum().sum()
        rival = dfp[["posesion_1t_rival_seg", "posesion_2t_rival_seg"]].fillna(0).sum().sum()

    return propio, rival

def resolver_tipo_tarjeta(conn, fecha, rival, equipo, jugador, tipo_tarjeta_seleccionado):
    """Si el jugador ya tiene una amarilla cargada en este partido y se carga otra amarilla,
    la convierte automáticamente en 'Roja (2da Amarilla)', distinta de una roja directa."""
    if tipo_tarjeta_seleccionado != "Amarilla":
        return tipo_tarjeta_seleccionado
    c = conn.cursor()
    c.execute("""SELECT COUNT(*) FROM eventos
                 WHERE fecha=? AND rival=? AND equipo=? AND jugador=? AND tipo_tarjeta='Amarilla'""",
              (str(fecha), rival, equipo, jugador))
    amarillas_previas = c.fetchone()[0]
    if amarillas_previas >= 1:
        return "Roja (2da Amarilla)"
    return "Amarilla"

# =========================================================
# CAPA DE DATOS: JUGADORES (CRUD)
# =========================================================
def calcular_edad(fecha_nacimiento_str):
    """Calcula la edad actual a partir de la fecha de nacimiento (string ISO)."""
    if not fecha_nacimiento_str:
        return None
    try:
        fn = pd.to_datetime(fecha_nacimiento_str).date()
        hoy = date.today()
        return hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))
    except Exception:
        return None


def guardar_foto_jugador(uploaded_file, dni):
    """Guarda la foto subida en disco usando el DNI como nombre de archivo único."""
    if uploaded_file is None:
        return None
    ext = uploaded_file.name.split(".")[-1].lower()
    path = f"{PLAYER_PHOTOS_DIR}/{dni}.{ext}"
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return path


def dni_ya_existe(conn, dni, excluir_id=None):
    """Chequea unicidad de DNI, excluyendo opcionalmente el propio registro (para ediciones)."""
    c = conn.cursor()
    if excluir_id is not None:
        c.execute("SELECT COUNT(*) FROM jugadores WHERE dni = ? AND id != ?", (dni, excluir_id))
    else:
        c.execute("SELECT COUNT(*) FROM jugadores WHERE dni = ?", (dni,))
    return c.fetchone()[0] > 0


def insertar_jugador(conn, datos):
    """Inserta un nuevo jugador. `datos` es un dict con las claves de la tabla."""
    c = conn.cursor()
    c.execute("""INSERT INTO jugadores
                 (nombre, apellido, dni, comet, fecha_nacimiento, numero_camiseta, posicion,
                  pie_habil, grupo_sanguineo, obra_social, telefono, direccion,
                  contacto_emergencia_nombre, contacto_emergencia_telefono, estado,
                  foto_path, fecha_alta, observaciones, activo)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
              (datos["nombre"], datos["apellido"], datos["dni"], datos["comet"],
               datos["fecha_nacimiento"], datos["numero_camiseta"], datos["posicion"],
               datos["pie_habil"], datos["grupo_sanguineo"], datos["obra_social"],
               datos["telefono"], datos["direccion"], datos["contacto_emergencia_nombre"],
               datos["contacto_emergencia_telefono"], datos["estado"], datos["foto_path"],
               str(date.today()), datos["observaciones"]))
    conn.commit()


def actualizar_jugador(conn, jugador_id, datos):
    """Actualiza los campos de un jugador existente."""
    c = conn.cursor()
    c.execute("""UPDATE jugadores SET nombre=?, apellido=?, dni=?, comet=?, fecha_nacimiento=?,
                 numero_camiseta=?, posicion=?, pie_habil=?, grupo_sanguineo=?, obra_social=?,
                 telefono=?, direccion=?, contacto_emergencia_nombre=?, contacto_emergencia_telefono=?,
                 estado=?, observaciones=?
                 WHERE id=?""",
              (datos["nombre"], datos["apellido"], datos["dni"], datos["comet"],
               datos["fecha_nacimiento"], datos["numero_camiseta"], datos["posicion"],
               datos["pie_habil"], datos["grupo_sanguineo"], datos["obra_social"],
               datos["telefono"], datos["direccion"], datos["contacto_emergencia_nombre"],
               datos["contacto_emergencia_telefono"], datos["estado"], datos["observaciones"],
               jugador_id))
    if datos.get("foto_path"):
        c.execute("UPDATE jugadores SET foto_path=? WHERE id=?", (datos["foto_path"], jugador_id))
    conn.commit()


def cargar_jugadores_df(conn, solo_activos=True):
    """Devuelve el DataFrame del plantel."""
    query = "SELECT * FROM jugadores"
    if solo_activos:
        query += " WHERE activo = 1"
    query += " ORDER BY numero_camiseta"
    df = pd.read_sql(query, conn)
    return df if not df.empty else None


def dar_baja_jugador(conn, jugador_id):
    """Borrado lógico: no elimina el registro, lo marca inactivo para preservar el historial."""
    c = conn.cursor()
    c.execute("UPDATE jugadores SET activo = 0, estado = 'Inactivo' WHERE id = ?", (jugador_id,))
    conn.commit()

def buscar_jugador_por_numero(conn, numero_camiseta):
    """Busca la ficha de un jugador propio por su número de camiseta (solo activos)."""
    try:
        numero = int(numero_camiseta)
    except (ValueError, TypeError):
        return None
    c = conn.cursor()
    c.execute("""SELECT nombre, apellido, comet, foto_path, posicion, fecha_nacimiento
                 FROM jugadores WHERE numero_camiseta = ? AND activo = 1""", (numero,))
    row = c.fetchone()
    if row is None:
        return None
    return {
        "nombre": row[0], "apellido": row[1], "comet": row[2],
        "foto_path": row[3], "posicion": row[4], "fecha_nacimiento": row[5],
    }    

def _renderizar_reloj_visual(segundos_nuestra, segundos_rival, estado_actual):
    """Reloj visual que sigue sumando en el navegador entre reruns (solo visual;
    la fuente de verdad del cálculo real sigue siendo session_state en el servidor)."""
    incrementa_nuestra = 1 if estado_actual == "Nosotros" else 0
    incrementa_rival = 1 if estado_actual == "Rival" else 0
    html = f"""
    <div style="display:flex; gap:24px; justify-content:center; font-family:monospace; font-size:28px; color:white; padding:8px;">
        <div>🟢 <span id="reloj_nuestra">00:00</span></div>
        <div>🔴 <span id="reloj_rival">00:00</span></div>
    </div>
    <script>
    let segNuestra = {segundos_nuestra};
    let segRival = {segundos_rival};
    const incNuestra = {incrementa_nuestra};
    const incRival = {incrementa_rival};
    function formatear(s) {{
        const m = Math.floor(s / 60).toString().padStart(2, '0');
        const ss = Math.floor(s % 60).toString().padStart(2, '0');
        return m + ":" + ss;
    }}
    document.getElementById("reloj_nuestra").innerText = formatear(segNuestra);
    document.getElementById("reloj_rival").innerText = formatear(segRival);
    setInterval(() => {{
        segNuestra += incNuestra;
        segRival += incRival;
        document.getElementById("reloj_nuestra").innerText = formatear(segNuestra);
        document.getElementById("reloj_rival").innerText = formatear(segRival);
    }}, 1000);
    </script>
    """
    components.html(html, height=70)

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
        height=620, margin=dict(l=10, r=10, t=10, b=10),
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

            # Puntos más chicos y sin borde, para no tapar el degradé de calor
            fig.add_trace(go.Heatmap(
                x=x_centros, y=y_centros, z=matriz,
                colorscale="YlOrRd", opacity=0.90, showscale=True,
                zsmooth="best", hoverinfo="skip", name="Densidad Táctica",
                zmin=max_val * 0.05, zmax=max_val
            ))

            # Capa superior con todos los puntos exactos recuperados
            fig.add_trace(go.Scatter(
                x=df_cancha["x"], y=df_cancha["y"],
                mode="markers",
                marker=dict(color="black", size=5, opacity=0.5, line=dict(color="white", width=1.5)),
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
        conn.close()
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

    # =====================================================
    # DATOS DEL PARTIDO (se configuran una sola vez al inicio)
    # =====================================================
    st.subheader("🗓️ Datos del Partido")
    st.caption("Configurá esto una sola vez al arrancar la carga; se mantiene fijo para todo el partido.")

    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        fecha = st.date_input("Fecha del partido", key="fecha_partido")
    with col_p2:
        equipo_propio = st.text_input("Equipo propio", key="equipo_propio_partido", placeholder="Ej: Camioneros")
    with col_p3:
        rival = st.text_input("Equipo rival", key="rival_partido")

    col_p4, col_p5 = st.columns(2)
    with col_p4:
        lado_inicio = st.selectbox(
            "En el 1T atacamos hacia:",
            [
                "Derecha ➡️ (Arco Rival a la Derecha)",
                "Izquierda ⬅️ (Arco Rival a la Izquierda)"
            ],
            key="lado_inicio_1t"
        )
    with col_p5:
        lugar = st.text_input("Lugar / Gimnasio", key="lugar_partido", placeholder="Ej: Polideportivo Municipal")

    st.divider()

    # =====================================================
    # CONTROL DE POSESIÓN (Reloj Parado)
    # =====================================================
    st.subheader("⏱️ Control de Posesión (Reloj Parado)")

    for key_pos in ["pos_1t_propio", "pos_1t_rival", "pos_2t_propio", "pos_2t_rival"]:
        if key_pos not in st.session_state:
            st.session_state[key_pos] = 0.0
    if "pos_estado_actual" not in st.session_state:
        st.session_state.pos_estado_actual = "Pausa"
    if "pos_ultimo_click" not in st.session_state:
        st.session_state.pos_ultimo_click = None
    if "pos_tiempo_actual" not in st.session_state:
        st.session_state.pos_tiempo_actual = "1T"

    tiempo_pos_sel = st.radio(
        "Tiempo actual de posesión", ["1T", "2T"],
        horizontal=True, key="pos_tiempo_widget",
        index=["1T", "2T"].index(st.session_state.pos_tiempo_actual)
    )
    if tiempo_pos_sel != st.session_state.pos_tiempo_actual:
        st.session_state.pos_tiempo_actual = tiempo_pos_sel
        st.session_state.pos_estado_actual = "Pausa"
        st.session_state.pos_ultimo_click = None
        st.rerun()

    clave_propio = f"pos_{st.session_state.pos_tiempo_actual.lower()}_propio"
    clave_rival = f"pos_{st.session_state.pos_tiempo_actual.lower()}_rival"

    ahora = time.time()
    if st.session_state.pos_estado_actual != "Pausa" and st.session_state.pos_ultimo_click is not None:
        transcurrido = ahora - st.session_state.pos_ultimo_click
        if st.session_state.pos_estado_actual == "Nosotros":
            st.session_state[clave_propio] += transcurrido
        elif st.session_state.pos_estado_actual == "Rival":
            st.session_state[clave_rival] += transcurrido
        st.session_state.pos_ultimo_click = ahora

    _renderizar_reloj_visual(
        st.session_state[clave_propio],
        st.session_state[clave_rival],
        st.session_state.pos_estado_actual
    )

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
        if st.button("🔄 RESET", use_container_width=True, help="Reiniciar cronómetros de este tiempo a cero"):
            st.session_state[clave_propio] = 0.0
            st.session_state[clave_rival] = 0.0
            st.session_state.pos_estado_actual = "Pausa"
            st.session_state.pos_ultimo_click = None
            st.rerun()

    total_tiempo_neto = st.session_state[clave_propio] + st.session_state[clave_rival]
    pct_nuestro = (st.session_state[clave_propio] / total_tiempo_neto * 100) if total_tiempo_neto > 0 else 0
    pct_rival = (st.session_state[clave_rival] / total_tiempo_neto * 100) if total_tiempo_neto > 0 else 0

    col_res1, col_res2, col_res3 = st.columns(3)
    with col_res1:
        st.metric(f"⏱️ Nuestra Posesión ({st.session_state.pos_tiempo_actual})", formatear_tiempo(st.session_state[clave_propio]), f"{pct_nuestro:.1f}%")
    with col_res2:
        estado_icon = "🟢" if st.session_state.pos_estado_actual == "Nosotros" else "🔴" if st.session_state.pos_estado_actual == "Rival" else "⏸️"
        st.metric("Estado Reloj", f"{estado_icon} {st.session_state.pos_estado_actual.upper()}")
    with col_res3:
        st.metric(f"⏱️ Posesión Rival ({st.session_state.pos_tiempo_actual})", formatear_tiempo(st.session_state[clave_rival]), f"{pct_rival:.1f}%", delta_color="inverse")

    if st.button("💾 GUARDAR / FINALIZAR PARTIDO", type="primary", use_container_width=True):
        if not rival:
            st.warning("⚠️ Ingresá el nombre del equipo rival antes de guardar el partido.")
        else:
            guardar_posesion_partido(
                conn, fecha, rival, equipo_propio, lugar, lado_inicio,
                st.session_state["pos_1t_propio"], st.session_state["pos_1t_rival"],
                st.session_state["pos_2t_propio"], st.session_state["pos_2t_rival"]
            )
            st.success("✅ Datos del partido y posesión guardados en la base de datos.")

    st.divider()

    st.subheader("⚡ Carga rápida de eventos (clic en la cancha)")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        tipo_evento = st.selectbox(
            "Tipo de evento",
            ["Finalizaciones", "Recuperos", "Perdidas", "Faltas", "Tarjetas", "ABP"],
            key="tipo_evento_rapido"
        )
    with col2:
        jugador = st.text_input(
            "Número de jugador", key="jugador_rapido",
            disabled=(tipo_evento == "ABP"),
            help="No aplica para ABP" if tipo_evento == "ABP" else None
        )
    with col3:
        tiempo = st.selectbox("Tiempo", ["1T", "2T"], key="tiempo_rapido")
    with col4:
        equipo = st.selectbox("Equipo", ["Propio", "Rival"], key="equipo_rapido")

    resultado, tipo_tarjeta_sel = "", ""
    tipo_abp_sel, lado_abp_sel = "", ""

    if tipo_evento == "Finalizaciones":
        resultado = st.selectbox("Resultado", ["Gol", "Atajado", "Desviado", "Bloqueado"], key="resultado_rapido")
    elif tipo_evento == "Faltas":
        tipo_tarjeta_sel = st.selectbox("Tarjeta asociada a la falta", ["Sin tarjeta", "Amarilla", "Roja"], key="tipo_tarjeta_falta")
    elif tipo_evento == "Tarjetas":
        tipo_tarjeta_sel = st.selectbox("Tipo de tarjeta", ["Amarilla", "Roja"], key="tipo_tarjeta_rapido")
    elif tipo_evento == "ABP":
        col_abp1, col_abp2 = st.columns(2)
        with col_abp1:
            tipo_abp_sel = st.selectbox("Tipo de ABP", ["Córner", "Tiro Libre", "Lateral"], key="tipo_abp_rapido")
        with col_abp2:
            lado_abp_sel = st.selectbox("Lado", ["Derecho", "Izquierdo"], key="lado_abp_rapido")

    # -----------------------------------------------------
    # ABP: registro directo por botón (no requiere clic en cancha ni jugador)
    # -----------------------------------------------------
    if tipo_evento == "ABP":
        st.info("🚩 Los ABP se registran directo con el botón — no hace falta clic en la cancha ni número de jugador.")
        if st.button("➕ Registrar ABP", type="primary", use_container_width=True):
            insertar_evento_individual(
                conn, fecha, rival, "ABP", tiempo, equipo,
                jugador="", zona=lado_abp_sel, resultado=tipo_abp_sel,
                tipo_tarjeta="", x=None, y=None
            )
            st.success(f"✅ ABP registrado: {tipo_abp_sel} ({lado_abp_sel}) - {equipo} - {tiempo}")
            st.rerun()

    # -----------------------------------------------------
    # Resto de eventos: flujo normal de clic en cancha
    # -----------------------------------------------------
    else:
        st.info("💡 **Instrucciones:** Completá la info del jugador arriba y hacé **un clic directo** en la cancha táctica. El sistema procesará automáticamente el lado de ataque actual según tu configuración de sorteo.")

        fig_cancha = crear_figura_cancha()

        evento_click = st.plotly_chart(
            fig_cancha, use_container_width=True,
            on_select="rerun", selection_mode="points", key="click_cancha",
            config={"responsive": True, "displaylogo": False}
        )

        x_click, y_click = extraer_punto_click(evento_click)

        if x_click is not None and y_click is not None:
            click_id = (x_click, y_click, tipo_evento, jugador, tiempo, equipo)

            if not jugador:
                st.warning("⚠️ Ingresá el número de jugador antes de hacer clic en la cancha")
            elif st.session_state.get("ultimo_click_registrado") != click_id:

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

                tipo_tarjeta_final = ""
                if tipo_evento in ("Faltas", "Tarjetas") and tipo_tarjeta_sel not in ("", "Sin tarjeta"):
                    tipo_tarjeta_final = resolver_tipo_tarjeta(conn, fecha, rival, equipo, jugador, tipo_tarjeta_sel)

                insertar_evento_individual(
                    conn, fecha, rival, tipo_evento, tiempo, equipo,
                    jugador, zona, resultado, tipo_tarjeta_final, x=x_guardar, y=y_guardar
                )

                st.session_state["ultimo_click_registrado"] = click_id
                mensaje_extra = f" | Tarjeta: {tipo_tarjeta_final}" if tipo_tarjeta_final else ""
                st.success(f"✅ ¡Registrado! {tipo_evento} ({zona}) - Jugador {jugador}{mensaje_extra}. Guardado de manera normalizada.")
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
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        partidos_disponibles = ["Todos"] + sorted(list(df_eventos["partido"].dropna().unique()), reverse=True)
        partido_sel = st.selectbox("Filtrar por Partido (Fecha - Rival)", partidos_disponibles)
    with c2:
        jugadores_disponibles = ["Todos"] + sorted(list(df_eventos["jugador"].dropna().unique()))
        jugador_sel = st.selectbox("Filtrar por Jugador", jugadores_disponibles)
    with c3:
        tipos_disponibles = ["Todos"] + list(df_eventos["tipo_evento"].dropna().unique())
        tipo_sel = st.selectbox("Filtrar por Tipo de Acción", tipos_disponibles)
    with c4:
        equipos_disponibles = ["Todos"] + sorted(list(df_eventos["equipo"].dropna().unique()))
        equipo_sel = st.selectbox("Filtrar por Equipo", equipos_disponibles)
    with c5:
        tiempos_disponibles = ["Todos"] + sorted(list(df_eventos["tiempo"].dropna().unique()))
        tiempo_sel = st.selectbox("Filtrar por Tiempo de Juego", tiempos_disponibles)

    # Filtros cruzados
    df_filtrado = df_eventos.copy()
    if partido_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["partido"] == partido_sel]
    if jugador_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["jugador"] == jugador_sel]
    if tipo_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["tipo_evento"] == tipo_sel]
    if equipo_sel != "Todos":
       df_filtrado = df_filtrado[df_filtrado["equipo"] == equipo_sel]
    if tiempo_sel != "Todos":
       df_filtrado = df_filtrado[df_filtrado["tiempo"] == tiempo_sel]   

    # --- INDICADORES ---
    st.divider()
    col1, col2, col3, col4, col5 = st.columns(5)
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
    with col5:
        st.metric("ABP Ejecutados", len(df_filtrado[df_filtrado["tipo_evento"] == "ABP"]))

    # --- TENENCIA DE LA PELOTA ---
    st.divider()
    st.markdown("### ⚽ Tenencia de la Pelota")
    df_partidos = cargar_partidos_df(conn)
    segundos_propio, segundos_rival = calcular_tenencia_partido(df_partidos, partido_sel, tiempo_sel)
    total_segundos = segundos_propio + segundos_rival

    if total_segundos > 0:
        col_pos_metric, col_pos_chart = st.columns([1, 1.5])
        with col_pos_metric:
            st.metric("Posesión Propia", formatear_tiempo(segundos_propio), f"{segundos_propio / total_segundos * 100:.1f}%")
            st.metric("Posesión Rival", formatear_tiempo(segundos_rival), f"{segundos_rival / total_segundos * 100:.1f}%")
        with col_pos_chart:
            df_tenencia = pd.DataFrame({"Equipo": ["Propio", "Rival"], "Segundos": [segundos_propio, segundos_rival]})
            fig_tenencia = px.pie(
                df_tenencia, values="Segundos", names="Equipo", hole=0.5,
                color="Equipo", color_discrete_map={"Propio": "#2ecc71", "Rival": "#e74c3c"}
            )
            fig_tenencia.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig_tenencia, use_container_width=True, key="tenencia_pelota_chart")
    else:
        st.info("No hay datos de posesión cargados para este filtro. Cargalos desde el reloj de 'Control de Posesión' en Carga de Datos.")

    # --- DISEÑO TÁCTICO INTERACTIVO (Fila Superior) ---
    st.divider()
    col_izq, col_der = st.columns([1.3, 1])

    with col_izq:
        st.subheader("📍 Mapa de Distribución y Calor de Futsal")
        txt_mapa = f"Filtro - Jugador: {jugador_sel} | Acción: {tipo_sel} | Equipo: {equipo_sel}"
        fig_heatmap = generar_heatmap_analisis(df_filtrado, titulo_mapa=txt_mapa)
        st.plotly_chart(fig_heatmap, use_container_width=True, key="heatmap_dashboard_general", config={"responsive": True, "displaylogo": False})

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

    # --- DESGLOSE DE FINALIZACIONES Y TABLA DE GOLEADORES (Fila Inferior) ---
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

    # --- ANÁLISIS DE ABP ---
    if not df_filtrado.empty:
        df_abp = df_filtrado[df_filtrado["tipo_evento"] == "ABP"]
        if not df_abp.empty:
            st.divider()
            st.markdown("### 🚩 Análisis de ABP (Corners / Tiros Libres / Laterales)")
            col_tipo_abp, col_lado_abp = st.columns(2)
            with col_tipo_abp:
                st.markdown("#### 📋 Por Tipo de ABP")
                tipo_abp_counts = df_abp["resultado"].fillna("Sin especificar").value_counts().reset_index()
                tipo_abp_counts.columns = ["Tipo de ABP", "Cantidad"]
                fig_abp_tipo = px.bar(
                    tipo_abp_counts, x="Tipo de ABP", y="Cantidad", color="Tipo de ABP",
                    color_discrete_sequence=px.colors.qualitative.Pastel2
                )
                fig_abp_tipo.update_layout(height=280, margin=dict(t=20, b=20), showlegend=False)
                st.plotly_chart(fig_abp_tipo, use_container_width=True, key="abp_por_tipo")
            with col_lado_abp:
                st.markdown("#### 📋 Por Lado")
                lado_abp_counts = df_abp["zona"].fillna("Sin especificar").value_counts().reset_index()
                lado_abp_counts.columns = ["Lado", "Cantidad"]
                fig_abp_lado = px.pie(
                    lado_abp_counts, values="Cantidad", names="Lado", hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Pastel1
                )
                fig_abp_lado.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig_abp_lado, use_container_width=True, key="abp_por_lado")

    # --- ANÁLISIS DE PÉRDIDAS Y RECUPEROS POR ZONA + TOP 3 ---
    if not df_filtrado.empty:
        for tipo_evento_analisis, emoji, color_seq in [
            ("Perdidas", "🔴", px.colors.qualitative.Set2),
            ("Recuperos", "🟢", px.colors.qualitative.Set3),
        ]:
            df_tipo = df_filtrado[df_filtrado["tipo_evento"] == tipo_evento_analisis]
            if df_tipo.empty:
                continue

            st.divider()
            st.markdown(f"### {emoji} Análisis de {tipo_evento_analisis}")

            col_tabla_z, col_grafico_z, col_top3 = st.columns([1.1, 1.0, 1.1])

            with col_tabla_z:
                st.markdown("#### 📋 Desglose por Zona")
                zona_counts = df_tipo["zona"].fillna("Sin especificar").value_counts().reset_index()
                zona_counts.columns = ["Zona", "Cantidad"]
                total_zona = zona_counts["Cantidad"].sum()
                zona_counts["Porcentaje"] = ((zona_counts["Cantidad"] / total_zona) * 100).round(1).astype(str) + "%"
                st.dataframe(zona_counts, use_container_width=True, hide_index=True)

            with col_grafico_z:
                fig_torta_zona = px.pie(
                    zona_counts, values="Cantidad", names="Zona",
                    color="Zona", color_discrete_sequence=color_seq, hole=0.4
                )
                fig_torta_zona.update_layout(height=240, margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
                st.plotly_chart(fig_torta_zona, use_container_width=True, key=f"torta_zona_{tipo_evento_analisis}")

            with col_top3:
                st.markdown(f"#### 🏆 Top 3 Jugadores - {tipo_evento_analisis}")
                top_jugadores = df_tipo["jugador"].value_counts().reset_index().head(3)
                top_jugadores.columns = ["Jugador", "Cantidad"]
                if not top_jugadores.empty:
                    fig_top3 = px.bar(
                        top_jugadores.sort_values("Cantidad"), x="Cantidad", y="Jugador",
                        orientation="h", text="Cantidad",
                        color_discrete_sequence=[color_seq[0]]
                    )
                    fig_top3.update_layout(height=240, margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
                    fig_top3.update_traces(textposition="outside")
                    st.plotly_chart(fig_top3, use_container_width=True, key=f"top3_{tipo_evento_analisis}")
                else:
                    st.info("Sin datos suficientes.")

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
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
       equipos_disponibles = sorted(df_eventos["equipo"].dropna().unique())
       equipo_sel = st.selectbox("Seleccionar Equipo", equipos_disponibles, key="rend_equipo_sel")

    df_base_equipo = df_eventos[df_eventos["equipo"] == equipo_sel]
    
    with col_f2:
       jugadores_disponibles = sorted(df_base_equipo["jugador"].dropna().unique())
       jugador_sel = st.selectbox("Seleccionar Jugador", jugadores_disponibles, key="rend_indiv_sel")

    df_base_jugador = df_base_equipo[df_base_equipo["jugador"] == jugador_sel]

    with col_f3:
       partidos_disponibles = ["Todos"] + sorted(list(df_base_jugador["partido"].dropna().unique()), reverse=True)
       partido_sel = st.selectbox("Filtrar por Partido / Rival", partidos_disponibles, key="rend_rival_sel")

    with col_f4:
        tiempos_disponibles = ["Todos"] + list(df_base_jugador["tiempo"].dropna().unique())
        tiempo_sel = st.selectbox("Filtrar por Tiempo de Juego", tiempos_disponibles, key="rend_tiempo_sel")

    df_jugador_filtrado = df_base_jugador.copy()
    if partido_sel != "Todos":
        df_jugador_filtrado = df_jugador_filtrado[df_jugador_filtrado["partido"] == partido_sel]
    if tiempo_sel != "Todos":
        df_jugador_filtrado = df_jugador_filtrado[df_jugador_filtrado["tiempo"] == tiempo_sel]

   # --- MINI FICHA DEL JUGADOR (solo si es de nuestro plantel registrado) ---
    if equipo_sel == "Propio":
        ficha = buscar_jugador_por_numero(conn, jugador_sel)
        if ficha:
            col_foto, col_datos = st.columns([1, 5])
            with col_foto:
                if ficha["foto_path"] and os.path.exists(ficha["foto_path"]):
                    st.image(ficha["foto_path"], width=80)
                else:
                    st.markdown("### 👤")
            with col_datos:
                edad = calcular_edad(ficha["fecha_nacimiento"])
                st.markdown(f"**{ficha['apellido']}, {ficha['nombre']}**")
                st.caption(f"COMET: {ficha['comet'] or '—'} · {ficha['posicion'] or '—'} · {edad if edad is not None else '—'} años")
    st.divider()

    # --- TARJETAS DE MÉTRICAS INDIVIDUALES ---
    st.markdown(f"### 📈 Estadísticas Clave: Jugador {jugador_sel} ({equipo_sel})")
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
        txt_mapa_indiv = f"Densidad en Cancha - Jugador {jugador_sel} ({equipo_sel})"
        fig_heatmap_indiv = generar_heatmap_analisis(df_jugador_filtrado, titulo_mapa=txt_mapa_indiv)
        st.plotly_chart(fig_heatmap_indiv, use_container_width=True, key="heatmap_individual_chart", config={"responsive": True, "displaylogo": False})

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
            st.markdown(f"### 🎯 Efectividad de Remates - Jugador {jugador_sel} ({equipo_sel})")
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
# PESTAÑA 4: PLANTEL DE JUGADORES
# =========================================================

def render_jugadores(conn, rol_actual):
    st.header("🪪 Plantel de Jugadores")

    POSICIONES = ["Arquero", "Cierre", "Ala Derecha", "Ala Izquierda", "Pivot", "Universal"]
    PIES = ["Derecho", "Izquierdo", "Ambidiestro"]
    GRUPOS_SANGUINEOS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Desconocido"]
    ESTADOS = ["Habilitado", "Lesionado", "Suspendido", "Inactivo"]
    COLOR_ESTADO = {"Habilitado": "🟢", "Lesionado": "🟡", "Suspendido": "🔴", "Inactivo": "⚫"}

    puede_editar = rol_actual == "Administrador"
    nombres_tabs = ["📋 Ver Plantel", "➕ Agregar Jugador", "✏️ Editar / Baja"] if puede_editar else ["📋 Ver Plantel"]
    tabs = st.tabs(nombres_tabs)

    # -----------------------------------------------------
    # TAB: VER PLANTEL
    # -----------------------------------------------------
    with tabs[0]:
        df_jug = cargar_jugadores_df(conn)
        if df_jug is None:
            st.info("Todavía no cargaste jugadores en el plantel.")
        else:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                pos_filtro = st.selectbox("Filtrar por posición", ["Todas"] + POSICIONES, key="jug_filtro_pos")
            with col_f2:
                estado_filtro = st.selectbox("Filtrar por estado", ["Todos"] + ESTADOS, key="jug_filtro_estado")

            df_vista = df_jug.copy()
            if pos_filtro != "Todas":
                df_vista = df_vista[df_vista["posicion"] == pos_filtro]
            if estado_filtro != "Todos":
                df_vista = df_vista[df_vista["estado"] == estado_filtro]

            st.caption(f"{len(df_vista)} jugador/es en el plantel")
            st.divider()

            columnas = st.columns(4)
            for i, (_, jug) in enumerate(df_vista.iterrows()):
                with columnas[i % 4]:
                    with st.container(border=True):
                        if jug["foto_path"] and os.path.exists(jug["foto_path"]):
                            st.image(jug["foto_path"], use_container_width=True)
                        else:
                            st.markdown("### 👤")
                        edad = calcular_edad(jug["fecha_nacimiento"])
                        st.markdown(f"**#{int(jug['numero_camiseta']) if pd.notna(jug['numero_camiseta']) else '-'} {jug['apellido']}, {jug['nombre']}**")
                        st.caption(f"{jug['posicion'] or '-'} · {edad if edad is not None else '-'} años")
                        st.caption(f"COMET: {jug['comet'] or '—'}")
                        st.caption(f"{COLOR_ESTADO.get(jug['estado'], '⚪')} {jug['estado']}")

    # -----------------------------------------------------
    # TAB: AGREGAR JUGADOR (solo Administrador)
    # -----------------------------------------------------
    if puede_editar:
        with tabs[1]:
            st.subheader("Nueva ficha de jugador")
            with st.form("form_nuevo_jugador", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    nombre = st.text_input("Nombre*")
                    dni = st.text_input("DNI*")
                    comet = st.text_input("Número de COMET")
                with c2:
                    apellido = st.text_input("Apellido*")
                    fecha_nac = st.date_input("Fecha de nacimiento", min_value=date(1970, 1, 1), max_value=date.today())
                    numero_camiseta = st.number_input("Número de camiseta", min_value=0, max_value=99, step=1)
                with c3:
                    posicion = st.selectbox("Posición", POSICIONES)
                    pie_habil = st.selectbox("Pie hábil", PIES)
                    estado = st.selectbox("Estado", ESTADOS)

                st.markdown("**Datos de contacto y salud**")
                c4, c5, c6 = st.columns(3)
                with c4:
                    telefono = st.text_input("Teléfono")
                    direccion = st.text_input("Dirección")
                with c5:
                    grupo_sanguineo = st.selectbox("Grupo sanguíneo", GRUPOS_SANGUINEOS)
                    obra_social = st.text_input("Obra social")
                with c6:
                    contacto_emerg_nombre = st.text_input("Contacto de emergencia")
                    contacto_emerg_tel = st.text_input("Teléfono de emergencia")

                observaciones = st.text_area("Observaciones (alergias, lesiones previas, etc.)")
                foto = st.file_uploader("Foto del jugador", type=["jpg", "jpeg", "png"])

                enviado = st.form_submit_button("💾 Guardar jugador", type="primary", use_container_width=True)

                if enviado:
                    if not nombre or not apellido or not dni:
                        st.warning("⚠️ Nombre, Apellido y DNI son obligatorios.")
                    elif dni_ya_existe(conn, dni):
                        st.error("❌ Ya existe un jugador cargado con ese DNI.")
                    else:
                        foto_path = guardar_foto_jugador(foto, dni)
                        insertar_jugador(conn, {
                            "nombre": nombre, "apellido": apellido, "dni": dni, "comet": comet,
                            "fecha_nacimiento": str(fecha_nac), "numero_camiseta": numero_camiseta,
                            "posicion": posicion, "pie_habil": pie_habil, "grupo_sanguineo": grupo_sanguineo,
                            "obra_social": obra_social, "telefono": telefono, "direccion": direccion,
                            "contacto_emergencia_nombre": contacto_emerg_nombre,
                            "contacto_emergencia_telefono": contacto_emerg_tel, "estado": estado,
                            "foto_path": foto_path, "observaciones": observaciones,
                        })
                        st.success(f"✅ {nombre} {apellido} agregado al plantel.")
                        st.rerun()

    # -----------------------------------------------------
    # TAB: EDITAR / BAJA (solo Administrador)
    # -----------------------------------------------------
    if puede_editar:
        with tabs[2]:
            df_jug_edit = cargar_jugadores_df(conn)
            if df_jug_edit is None:
                st.info("No hay jugadores para editar.")
            else:
                opciones = {
                    f"#{int(r['numero_camiseta']) if pd.notna(r['numero_camiseta']) else '-'} - {r['apellido']}, {r['nombre']} (DNI {r['dni']})": r["id"]
                    for _, r in df_jug_edit.iterrows()
                }
                seleccion = st.selectbox("Seleccioná un jugador", list(opciones.keys()), key="jug_edit_sel")
                jugador_id = opciones[seleccion]
                jug = df_jug_edit[df_jug_edit["id"] == jugador_id].iloc[0]

                with st.form("form_editar_jugador"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        nombre = st.text_input("Nombre*", value=jug["nombre"])
                        dni = st.text_input("DNI*", value=jug["dni"])
                        comet = st.text_input("Número de COMET", value=jug["comet"] or "")
                    with c2:
                        apellido = st.text_input("Apellido*", value=jug["apellido"])
                        fecha_nac = st.date_input("Fecha de nacimiento", value=pd.to_datetime(jug["fecha_nacimiento"]).date() if jug["fecha_nacimiento"] else date.today())
                        numero_camiseta = st.number_input("Número de camiseta", min_value=0, max_value=99, step=1, value=int(jug["numero_camiseta"]) if pd.notna(jug["numero_camiseta"]) else 0)
                    with c3:
                        posicion = st.selectbox("Posición", POSICIONES, index=POSICIONES.index(jug["posicion"]) if jug["posicion"] in POSICIONES else 0)
                        pie_habil = st.selectbox("Pie hábil", PIES, index=PIES.index(jug["pie_habil"]) if jug["pie_habil"] in PIES else 0)
                        estado = st.selectbox("Estado", ESTADOS, index=ESTADOS.index(jug["estado"]) if jug["estado"] in ESTADOS else 0)

                    c4, c5, c6 = st.columns(3)
                    with c4:
                        telefono = st.text_input("Teléfono", value=jug["telefono"] or "")
                        direccion = st.text_input("Dirección", value=jug["direccion"] or "")
                    with c5:
                        grupo_sanguineo = st.selectbox("Grupo sanguíneo", GRUPOS_SANGUINEOS, index=GRUPOS_SANGUINEOS.index(jug["grupo_sanguineo"]) if jug["grupo_sanguineo"] in GRUPOS_SANGUINEOS else 8)
                        obra_social = st.text_input("Obra social", value=jug["obra_social"] or "")
                    with c6:
                        contacto_emerg_nombre = st.text_input("Contacto de emergencia", value=jug["contacto_emergencia_nombre"] or "")
                        contacto_emerg_tel = st.text_input("Teléfono de emergencia", value=jug["contacto_emergencia_telefono"] or "")

                    observaciones = st.text_area("Observaciones", value=jug["observaciones"] or "")
                    nueva_foto = st.file_uploader("Reemplazar foto (opcional)", type=["jpg", "jpeg", "png"])

                    col_upd, col_baja = st.columns(2)
                    with col_upd:
                        actualizar = st.form_submit_button("💾 Guardar cambios", type="primary", use_container_width=True)
                    with col_baja:
                        confirmar_baja = st.checkbox("Confirmo la baja de este jugador")
                        dar_baja = st.form_submit_button("🗑️ Dar de baja", use_container_width=True)

                    if actualizar:
                        if dni_ya_existe(conn, dni, excluir_id=jugador_id):
                            st.error("❌ Ese DNI ya pertenece a otro jugador.")
                        else:
                            foto_path = guardar_foto_jugador(nueva_foto, dni) if nueva_foto else None
                            actualizar_jugador(conn, jugador_id, {
                                "nombre": nombre, "apellido": apellido, "dni": dni, "comet": comet,
                                "fecha_nacimiento": str(fecha_nac), "numero_camiseta": numero_camiseta,
                                "posicion": posicion, "pie_habil": pie_habil, "grupo_sanguineo": grupo_sanguineo,
                                "obra_social": obra_social, "telefono": telefono, "direccion": direccion,
                                "contacto_emergencia_nombre": contacto_emerg_nombre,
                                "contacto_emergencia_telefono": contacto_emerg_tel, "estado": estado,
                                "foto_path": foto_path, "observaciones": observaciones,
                            })
                            st.success("✅ Ficha actualizada.")
                            st.rerun()

                    if dar_baja:
                        if not confirmar_baja:
                            st.warning("⚠️ Marcá la casilla de confirmación para dar de baja al jugador.")
                        else:
                            dar_baja_jugador(conn, jugador_id)
                            st.success("Jugador dado de baja (queda inactivo, no se borra el historial).")
                            st.rerun()

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
        tab1, tab2, tab3, tab4 = st.tabs(["Carga de Datos", "Dashboard General", "Rendimiento Individual", "Plantel de Jugadores"])
        
        with tab1:
            render_carga_datos(conn)
        with tab2:
            render_dashboard_general(conn)
        with tab3:
            render_rendimiento_individual(conn)
        with tab4:
            render_jugadores(conn, rol_actual)
            
    elif rol_actual == "Lector":
        # Acceso limitado: Ocultamos pestaña de carga de datos para proteger la integridad de la DB
        st.title("📊 Planilla Digital de Futsal")
        tab2, tab3, tab4 = st.tabs(["Dashboard General", "Rendimiento Individual", "Plantel de Jugadores"])
        
        with tab2:
            render_dashboard_general(conn)
        with tab3:
            render_rendimiento_individual(conn)
        with tab4:
            render_jugadores(conn, rol_actual)


if __name__ == "__main__":
    main()