import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import json
from datetime import datetime

# =========================================================
# CONFIGURACIÓN DE PÁGINA
# =========================================================
st.set_page_config(page_title="Planilla Digital de Futsal", page_icon="📊", layout="wide")


# =========================================================
# CAPA DE DATOS (SQLite)
# =========================================================
def get_connection():
    """Devuelve una conexión a la base de datos futsal.db, reutilizable entre pestañas."""
    conn = sqlite3.connect("futsal.db", check_same_thread=False)
    return conn


def init_db(conn):
    cursor = conn.cursor()
    # Tabla de eventos (la que ya tenés)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
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
        );
    """)
    # NUEVA TABLA: Ficha de Resultados Oficiales
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS partidos (
            fecha TEXT,
            rival TEXT PRIMARY KEY,
            goles_troncos INTEGER,
            goles_rival INTEGER,
            condicion TEXT
        );
    """)
    conn.commit()


def cargar_partidos_df(conn):
    """Devuelve el DataFrame de partidos, o None si está vacío."""
    df = pd.read_sql("SELECT * FROM partidos", conn)
    return df if not df.empty else None


def cargar_eventos_df(conn, limit=None):
    """Devuelve el DataFrame de eventos, o None si está vacío."""
    query = "SELECT * FROM eventos ORDER BY id DESC"
    if limit:
        query += f" LIMIT {limit}"
    df = pd.read_sql(query, conn)
    return df if not df.empty else None

def obtener_lista_partidos_formateada(conn, jugador_especifico=None):
    """Trae los partidos combinando la info de eventos y resultados oficiales.
       Permite filtrar opcionalmente por un jugador para Pestaña 3."""
    cursor = conn.cursor()
    try:
        if jugador_especifico:
            cursor.execute("SELECT DISTINCT fecha, rival FROM eventos WHERE jugador = ? ORDER BY fecha DESC;", (jugador_especifico,))
        else:
            cursor.execute("SELECT DISTINCT fecha, rival FROM eventos ORDER BY fecha DESC;")
        eventos_partidos = cursor.fetchall()
        
        opciones = []
        mapeo_partidos = {} # Para saber qué rival/fecha real corresponde a cada opción
        
        for fecha, rival in eventos_partidos:
            # Buscamos si ese partido tiene ficha de resultado oficial
            cursor.execute("SELECT goles_troncos, goles_rival FROM partidos WHERE rival = ? AND fecha = ?;", (rival, fecha))
            ficha = cursor.fetchone()
            
            if ficha:
                label = f"⚽ {rival} ({fecha}) | Res: {ficha[0]}-{ficha[1]}"
            else:
                label = f"🏃‍♂️ {rival} ({fecha}) | (Sin resultado oficial)"
                
            opciones.append(label)
            mapeo_partidos[label] = {"rival": rival, "fecha": fecha}
            
        return opciones, mapeo_partidos
    except Exception as e:
        return [], {}


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
    # Color de fondo LIMITADO ESTRICTAMENTE a la cancha (Piso Azul)
    fig.add_shape(type="rect", x0=0, y0=0, x1=40, y1=20, fillcolor="#4158f6", line=dict(color="white", width=2.5), layer="below")
    
    # Área Penal Izquierda (Radio 6m desde postes)
    fig.add_shape(type="path", path="M 0,4 Q 6,4 6,10 Q 6,16 0,16 Z", fillcolor="#e5a93c", line=dict(color="white", width=2), layer="below")
    
    # Área Penal Derecha (Radio 6m)
    fig.add_shape(type="path", path="M 40,4 Q 34,4 34,10 Q 34,16 40,16 Z", fillcolor="#e5a93c", line=dict(color="white", width=2), layer="below")
    
    # Círculo Central (Radio 3m, centro en X=20, Y=10)
    fig.add_shape(type="circle", x0=17, y0=7, x1=23, y1=13, fillcolor="#e5a93c", line=dict(color="white", width=2), layer="below")
    
    # Línea de Mitad de Cancha
    fig.add_shape(type="line", x0=20, y0=0, x1=20, y1=20, line=dict(color="white", width=2.5))
    
    # Puntos de Penal (6m) y Doble Penal (10m)
    fig.add_trace(go.Scatter(x=[6, 10, 34, 30], y=[10, 10, 10, 10], mode="markers", marker=dict(color="white", size=5), showlegend=False, hoverinfo="skip"))
    
    fig.add_shape(type="rect", x0=-1.5, y0=8.5, x1=0, y1=11.5, fillcolor="rgba(0,0,0,0)", line=dict(color="white", width=2))
    fig.add_shape(type="rect", x0=40, y0=8.5, x1=41.5, y1=11.5, fillcolor="rgba(0,0,0,0)", line=dict(color="white", width=2))


def crear_figura_cancha():
    """Dibuja la cancha interactiva de Futsal limpia para la captura de datos tácticos."""
    xs = list(range(1, 100, 2))  # Mantiene consistencia con la grilla de captura 0-100
    ys = list(range(1, 60, 2))   # Mantiene consistencia con la grilla de captura 0-60
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

    # Adaptamos temporalmente la visualización de las capas al tamaño de grilla de captura
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

        # FIX de Escala: Reescalamos de 100x60 a 40x20 antes del truncado por rango
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


def obtener_zona_desde_click(x):
    # En base a la grilla de clics (0 a 100), la mitad es 50
    return "Defensiva" if x < 50 else "Ofensiva"


# =========================================================
# PESTAÑA 1: CARGA DE DATOS
# =========================================================
def render_carga_datos(conn):
    st.header("📥 Carga de Datos")

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

    st.subheader("⚡ Carga rápida de eventos (clic en la cancha)")

    col_ctx1, col_ctx2 = st.columns(2)
    with col_ctx1:
        fecha = st.date_input("Fecha del partido", key="fecha_partido")
    with col_ctx2:
        rival = st.text_input("Equipo rival", key="rival_partido")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        tipo_evento = st.selectbox("Tipo de evento", ["Finalizaciones", "Recuperos", "Perdidas", "Faltas", "Tarjetas"], key="tipo_evento_rapido")
    with col2:
        jugador = st.text_input("Número de jugador", key="jugador_rapido")
    with col3:
        tiempo = st.selectbox("Tiempo", ["1T", "2T"], key="tiempo_rapido")
    with col4:
        equipo = st.selectbox("Equipo", ["Local", "Visitante"], key="equipo_rapido")

    resultado, tipo_tarjeta = "", ""
    if tipo_evento == "Finalizaciones":
        resultado = st.selectbox("Resultado", ["Gol", "Al arco (Atajado / Palo)", "Desviado (Afuera)", "Bloqueado (En defensor)"], key="resultado_rapido")
    elif tipo_evento == "Tarjetas":
        tipo_tarjeta = st.selectbox("Tipo de tarjeta", ["Amarilla", "Roja"], key="tipo_tarjeta_rapido")

    st.info("💡 **Instrucciones:** Completá la info del jugador arriba y hacé **un clic directo** en el sector azul o naranja de la cancha para registrar el evento.")
    
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
            zona = obtener_zona_desde_click(x_click)

            insertar_evento_individual(
                conn, fecha, rival, tipo_evento, tiempo, equipo,
                jugador, zona, resultado, tipo_tarjeta, x=x_click, y=y_click
            )

            st.session_state["ultimo_click_registrado"] = click_id
            st.success(f"✅ ¡Registrado con éxito! {tipo_evento} - Jugador {jugador} en zona {zona} (X: {x_click}, Y: {y_click})")
    else:
        st.caption("📍 Esperando clic posicional...")

    st.divider()

    st.subheader("Últimos eventos cargados")
    df_eventos_recientes = cargar_eventos_df(conn, limit=10)
    if df_eventos_recientes is not None:
        st.dataframe(df_eventos_recientes)
    else:
        st.info("No hay eventos cargados aún")

    # --- SECCIÓN: REGISTRO DE RESULTADO FINAL ---
    st.markdown("---")
    st.subheader("📝 Ficha de Resultado Final")
    st.caption("Guardá el score oficial del partido para el historial del torneo.")

    # Detectamos de forma dinámica el rival que estás escribiendo arriba en la carga rápida
    rival_actual = st.session_state.get("rival_partido", "").strip()
    fecha_actual = st.session_state.get("fecha_partido", datetime.now().date())

    if rival_actual:
        # --- TABLERO ELECTRÓNICO DINÁMICO (Cálculo interactivo en base a los clics) ---
        df_todos_eventos = cargar_eventos_df(conn)
        goles_calculados_troncos = 0
        
        # Filtramos de forma temporal los eventos de este partido para contar los goles marcados por Los Troncos
        if df_todos_eventos is not None:
            df_este_partido = df_todos_eventos[(df_todos_eventos["rival"] == rival_actual) & (df_todos_eventos["fecha"] == str(fecha_actual))]
            if not df_este_partido.empty:
                # Contamos cuántos eventos de "Finalizaciones" dieron como resultado exacto "Gol"
                goles_calculados_troncos = len(df_este_partido[(df_este_partido["tipo_evento"] == "Finalizaciones") & (df_este_partido["resultado"] == "Gol")])

        col_res1, col_res2, col_res3 = st.columns(3)
        with col_res1:
            # Ponemos el valor calculado de forma automática pero dejamos modificar por si acaso
            goles_troncos = st.number_input("Goles de Los Troncos", min_value=0, step=1, value=goles_calculados_troncos, key="f_goles_troncos")
        with col_res2:
            goles_rival = st.number_input(f"Goles de {rival_actual}", min_value=0, step=1, value=0, key="f_goles_rival")
        with col_res3:
            condicion_partido = st.selectbox("Condición de Los Troncos", ["Local", "Visitante"], key="f_condicion_partido")

        # --- TARJETA DE RESULTADO DESTACADA ---
        st.markdown("#### 🏆 VISTA PREVIA DEL MARCADOR")
        if goles_troncos > goles_rival:
            estado_texto = f"🎉 ¡VICTORIA TEMPORAL CONTRA {rival_actual.upper()}!"
            contenedor_resultado = st.success
        elif goles_troncos < goles_rival:
            estado_texto = f"❌ DERROTA TEMPORAL CONTRA {rival_actual.upper()}"
            contenedor_resultado = st.error
        else:
            estado_texto = f"🤝 EMPATE TEMPORAL CONTRA {rival_actual.upper()}"
            contenedor_resultado = st.info

        with contenedor_resultado(estado_texto):
            col_local, col_vs, col_visitante = st.columns([2, 1, 2])
            with col_local:
                st.metric(label="Los Troncos FC", value=f"⚽ {goles_troncos}")
                st.caption(f"Condición: {condicion_partido}")
            with col_vs:
                st.markdown("<h2 style='text-align: center; margin-top: 15px;'>VS</h2>", unsafe_allow_html=True)
            with col_visitante:
                st.metric(label=f"{rival_actual}", value=f"⚽ {goles_rival}")
                st.caption("Rival")

        if st.button("💾 Guardar Resultado Oficial", key="btn_guardar_resultado"):
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO partidos (fecha, rival, goles_troncos, goles_rival, condicion)
                    VALUES (?, ?, ?, ?, ?);
                """, (str(fecha_actual), rival_actual, goles_troncos, goles_rival, condicion_partido))
                conn.commit()
                st.success(f"⚽ ¡Resultado oficial guardado con éxito en el historial!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar el resultado en la base de datos: {e}")
    else:
        st.info("💡 Escribí el nombre del 'Equipo rival' en la sección de carga rápida arriba para habilitar la ficha de resultado final.")

    # --- SECCIÓN DE GESTIÓN DE PARTIDOS ---
    st.markdown("---")
    st.subheader("⚽ GESTIÓN DEL PARTIDO ACTIVO")
    st.caption("Usá estas opciones para controlar el cierre de datos de cada tiempo o partido.")
    
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        def finalizar_y_limpiar():
            if "rival_partido" in st.session_state:
                del st.session_state["rival_partido"]
            if "jugador_rapido" in st.session_state:
                del st.session_state["jugador_rapido"]
            st.toast("📝 Campos de carga reiniciados para el próximo partido/tiempo.", icon="🔄")

        st.button("🏁 Finalizar Tiempo / Partido Actual", key="btn_clear_inputs", on_click=finalizar_y_limpiar)

    with col_g2:
        rivales_guardados = ["Seleccionar..."] + list(df_eventos_recientes["rival"].unique()) if df_eventos_recientes is not None else []
        partido_a_borrar = st.selectbox("🗑️ ¿Borrar un partido específico por error de carga?", rivales_guardados, key="sb_borrar_partido")
        
        if partido_a_borrar != "Seleccionar...":
            if st.button(f"Confirmar eliminación de: {partido_a_borrar}", key="btn_borrar_especifico"):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM eventos WHERE rival = ?;", (partido_a_borrar,))
                cursor.execute("DELETE FROM partidos WHERE rival = ?;", (partido_a_borrar,))
                conn.commit()
                st.warning(f"Se eliminaron los eventos y fichas contra {partido_a_borrar} por corrección de errores.")
                st.rerun()

# =========================================================
# PESTAÑA 2: DASHBOARD GENERAL
# =========================================================
def render_dashboard_general(conn):
    st.header("📈 Dashboard Analítico Advanced")

    df_eventos = cargar_eventos_df(conn)
    if df_eventos is None:
        st.info("No hay eventos cargados aún. Registrá datos en la primera pestaña.")
        return

    # --- BARRA DE FILTROS SUPERIOR ---
    st.markdown("### 🔍 Filtros Globales")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        opciones_partidos, mapeo_partidos = obtener_lista_partidos_formateada(conn)
        if opciones_partidos:
            partido_seleccionado = st.selectbox("Seleccionar Partido:", opciones_partidos, key="dash_gen_partido")
            rival_filtro = mapeo_partidos[partido_seleccionado]["rival"]
            fecha_filtro = mapeo_partidos[partido_seleccionado]["fecha"]
        else:
            st.info("No hay partidos registrados.")
            return
            
    df_partido_base = df_eventos[(df_eventos["rival"] == rival_filtro) & (df_eventos["fecha"] == fecha_filtro)]

    with c2:
        jugadores_disponibles = ["Todos"] + sorted(list(df_partido_base["jugador"].dropna().unique()))
        jugador_sel = st.selectbox("Filtrar por Jugador", jugadores_disponibles)
    with c3:
        tipos_disponibles = ["Todos"] + list(df_partido_base["tipo_evento"].dropna().unique())
        tipo_sel = st.selectbox("Filtrar por Tipo de Acción", tipos_disponibles)

    df_filtrado = df_partido_base.copy()
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
        goles_tiros = len(df_filtrado[(df_filtrado["tipo_evento"] == "Finalizaciones") & (df_filtrado["resultado"].isin(["Gol", "Al arco", "Al arco (Atajado / Palo)"]))])
        st.metric("Goles / Tiros al Arco", goles_tiros)
    with col3:
        st.metric("Balones Perdidos", len(df_filtrado[df_filtrado["tipo_evento"] == "Perdidas"]))
    with col4:
        st.metric("Recuperaciones", len(df_filtrado[df_filtrado["tipo_evento"] == "Recuperos"]))

    # --- DISEÑO TÁCTICO INTERACTIVO ---
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


# =========================================================
# PESTAÑA 3: RENDIMIENTO INDIVIDUAL
# =========================================================
def render_rendimiento_individual(conn):
    st.header("🏃 Rendimiento Individual y Scouting")

    df_eventos = cargar_eventos_df(conn)
    if df_eventos is None:
        st.info("No hay eventos cargados aún. Registrá datos en la primera pestaña para analizar jugadores.")
        return

    st.markdown("### 🔍 Filtros de Jugador")
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        jugadores_disponibles = sorted(df_eventos["jugador"].dropna().unique())
        jugador_sel = st.selectbox("Seleccionar Jugador", jugadores_disponibles, key="rend_indiv_sel")
    
    with col_f2:
        opciones_partidos_j, mapeo_partidos_j = obtener_lista_partidos_formateada(conn, jugador_especifico=jugador_sel)
        
        if opciones_partidos_j:
            partido_seleccionado_j = st.selectbox("Seleccionar Partido:", opciones_partidos_j, key="rend_partido_sel")
            rival_filtro = mapeo_partidos_j[partido_seleccionado_j]["rival"]
            fecha_filtro = mapeo_partidos_j[partido_seleccionado_j]["fecha"]
        else:
            st.info("Este jugador no tiene partidos registrados.")
            return

    df_jugador_part = df_eventos[
        (df_eventos["jugador"] == jugador_sel) & 
        (df_eventos["rival"] == rival_filtro) & 
        (df_eventos["fecha"] == fecha_filtro)
    ]
    
    with col_f3:
        tiempos_disponibles = ["Todos"] + list(df_jugador_part["tiempo"].dropna().unique())
        tiempo_sel = st.selectbox("Filtrar por Tiempo de Juego", tiempos_disponibles, key="rend_tiempo_sel")

    df_jugador_filtrado = df_jugador_part.copy()
    if tiempo_sel != "Todos":
        df_jugador_filtrado = df_jugador_filtrado[df_jugador_filtrado["tiempo"] == tiempo_sel]

    st.divider()

    st.markdown(f"### 📈 Estadísticas Clave: Jugador {jugador_sel}")
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        st.metric("Total Acciones", len(df_jugador_filtrado))
    with m2:
        goles_tiros = len(df_jugador_filtrado[(df_jugador_filtrado["tipo_evento"] == "Finalizaciones") & (df_jugador_filtrado["resultado"].isin(["Gol", "Al arco", "Al arco (Atajado / Palo)"]))])
        st.metric("Tiros al Arco / Goles", goles_tiros)
    with m3:
        recuperos = len(df_jugador_filtrado[df_jugador_filtrado["tipo_evento"] == "Recuperos"])
        st.metric("Recuperaciones", recuperos)
    with m4:
        perdidas = len(df_jugador_filtrado[df_jugador_filtrado["tipo_evento"] == "Perdidas"])
        st.metric("Pérdidas de Balón", perdidas)

    st.divider()

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


# =========================================================
# MAIN
# =========================================================
def main():
    st.title("📊 Planilla Digital de Futsal")

    conn = get_connection()
    init_db(conn)

    tab1, tab2, tab3 = st.tabs(["Carga de Datos", "Dashboard General", "Rendimiento Individual"])

    with tab1:
        render_carga_datos(conn)
    with tab2:
        render_dashboard_general(conn)
    with tab3:
        render_rendimiento_individual(conn)


if __name__ == "__main__":
    main()