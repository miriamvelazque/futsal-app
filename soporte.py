def generar_pdf_partido_avanzado(conn, fecha_sel, rival_sel, _ignorado=None, lista_figuras=None):
    """
    Reporte PDF estructurado por tiempo (1T / 2T / Total).
    Diseño moderno tipo dashboard: tarjetas KPI, scoreboard centrado,
    gráficos con paleta del sistema, tipografía limpia sobre fondo claro.

    BUG FIX: siempre recarga los eventos desde la DB usando solo fecha+rival,
    ignorando cualquier filtro activo en el dashboard.

    Rotación 2T: si en 1T el equipo atacaba hacia la derecha, en 2T las
    coordenadas del heatmap se invierten (x=100-x, y=60-y).
    """
    import io as _io

    # ── Recargar desde DB sin filtros de pantalla ─────────────────────────────
    df_partido_completo = pd.read_sql(
        "SELECT * FROM eventos WHERE fecha = ? AND rival = ?",
        conn, params=(str(fecha_sel), rival_sel)
    )
    if df_partido_completo.empty:
        buf = _io.BytesIO()
        buf.write(b"%PDF-1.4\n")
        buf.seek(0)
        return buf

    for col_num in ["x", "y"]:
        if col_num in df_partido_completo.columns:
            df_partido_completo[col_num] = pd.to_numeric(df_partido_completo[col_num], errors="coerce")

    df_ev = df_partido_completo

    buffer = _io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )

    # ── Paleta de colores ─────────────────────────────────────────────────────
    C_VERDE      = colors.HexColor("#8DC63F")   # acento marca
    C_VERDE_SUAVE= colors.HexColor("#EEF7DC")   # fondo claro verde
    C_OSCURO     = colors.HexColor("#1F2937")   # texto principal
    C_GRIS_CARD  = colors.HexColor("#F8F9FA")   # fondo tarjetas
    C_GRIS_BORDE = colors.HexColor("#E5E7EB")   # bordes suaves
    C_GRIS_TEXT  = colors.HexColor("#6B7280")   # texto secundario
    C_TEXTO      = colors.HexColor("#111827")   # cuerpo
    C_GOL        = colors.HexColor("#2ecc71")
    C_RIVAL      = colors.HexColor("#e74c3c")
    C_EMPATE     = colors.HexColor("#F59E0B")

    # Paleta de eventos — misma que el dashboard
    PALETA_EVENTO = {
        "Finalizaciones": "#FF6B6B",
        "Recuperos":      "#4ECDC4",
        "Perdidas":       "#FFD166",
        "Faltas":         "#A78BFA",
        "ABP":            "#118AB2",
    }

    # ── Estilos de texto ──────────────────────────────────────────────────────
    estilos = getSampleStyleSheet()

    def _estilo(nombre, **kwargs):
        return ParagraphStyle(nombre, parent=estilos["Normal"], **kwargs)

    est_titulo   = _estilo("Titulo",   fontSize=17, fontName="Helvetica-Bold",
                           textColor=C_OSCURO, spaceAfter=2, leading=21)
    est_subtitulo= _estilo("Subtit",   fontSize=9,  fontName="Helvetica",
                           textColor=C_GRIS_TEXT, spaceAfter=4, leading=13)
    est_seccion  = _estilo("Seccion",  fontSize=13, fontName="Helvetica-Bold",
                           textColor=C_OSCURO, spaceBefore=4, spaceAfter=3, leading=16)
    est_sub      = _estilo("Sub",      fontSize=11, fontName="Helvetica-Bold",
                           textColor=C_OSCURO, spaceBefore=5, spaceAfter=3)
    est_cuerpo   = _estilo("Cuerpo",   fontSize=9,  fontName="Helvetica",
                           textColor=C_TEXTO, leading=14)
    est_resumen  = _estilo("Resumen",  fontSize=10, fontName="Helvetica",
                           textColor=C_TEXTO, leading=16, spaceAfter=4)
    est_caption  = _estilo("Caption",  fontSize=8,  fontName="Helvetica",
                           textColor=C_GRIS_TEXT, spaceAfter=3)
    est_footer   = _estilo("Footer",   fontSize=7,  fontName="Helvetica",
                           textColor=C_GRIS_TEXT, alignment=1)
    # Estilos para tarjetas KPI
    est_kpi_label= _estilo("KpiLbl",  fontSize=7,  fontName="Helvetica-Bold",
                           textColor=C_GRIS_TEXT, alignment=1, leading=9,
                           spaceAfter=2, spaceBefore=6)
    est_kpi_val  = _estilo("KpiVal",  fontSize=22, fontName="Helvetica-Bold",
                           textColor=C_OSCURO, alignment=1, leading=26, spaceAfter=6)

    elementos = []

    # =========================================================================
    # HELPERS INTERNOS
    # =========================================================================

    def linea_verde():
        from reportlab.platypus import HRFlowable
        return HRFlowable(width="100%", thickness=2,
                          color=C_VERDE, spaceAfter=6, spaceBefore=2)

    def linea_gris():
        from reportlab.platypus import HRFlowable
        return HRFlowable(width="100%", thickness=0.5,
                          color=C_GRIS_BORDE, spaceAfter=4, spaceBefore=4)

    def tabla_simple(data, col_widths):
        """Tabla con encabezado oscuro y filas alternadas."""
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  C_OSCURO),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, C_GRIS_CARD]),
            ("GRID",          (0, 0), (-1, -1), 0.3, C_GRIS_BORDE),
            ("PADDING",       (0, 0), (-1, -1), 5),
            ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return t

    def tarjeta_kpi(label, valor, color_acento=None):
        """Bloque KPI individual: etiqueta pequeña + número grande.
        Devuelve una lista de flowables pensada para meter en una celda de Table."""
        color_acento = color_acento or C_VERDE
        lbl = Paragraph(label.upper(), est_kpi_label)
        val = Paragraph(str(valor), _estilo(
            f"KV_{label}", fontSize=22, fontName="Helvetica-Bold",
            textColor=colors.HexColor(color_acento) if isinstance(color_acento, str) else color_acento,
            alignment=1, leading=26, spaceAfter=6
        ))
        return [lbl, val]

    def grid_kpi(items, ancho_total=504):
        """
        items: lista de (label, valor, color_hex)
        Genera una tabla de tarjetas KPI lado a lado con borde gris claro.
        """
        n = len(items)
        ancho_col = ancho_total / n
        celdas = [tarjeta_kpi(lbl, val, col) for lbl, val, col in items]
        t = Table([celdas], colWidths=[ancho_col] * n)
        t.setStyle(TableStyle([
            ("BOX",       (0, 0), (-1, -1), 0.8, C_GRIS_BORDE),
            ("INNERGRID", (0, 0), (-1, -1), 0.8, C_GRIS_BORDE),
            ("BACKGROUND",(0, 0), (-1, -1), C_GRIS_CARD),
            ("VALIGN",    (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING",   (0, 0), (-1, -1), 4),
            # Línea de acento verde en la parte superior de cada tarjeta
            ("LINEABOVE", (0, 0), (-1, 0), 2.5, C_VERDE),
        ]))
        return t

    def fig_a_imagen(fig, ancho_pts=500, alto_pts=210):
        """Renderiza figura Plotly → RLImage con fondo blanco. Devuelve None si falla."""
        try:
            fig_c = go.Figure(fig)
            fig_c.update_layout(
                paper_bgcolor="white", plot_bgcolor="white",
                font=dict(color=C_TEXTO.hexval() if hasattr(C_TEXTO, 'hexval') else "#111827", size=10),
                width=750, height=320,
                margin=dict(t=30, b=60, l=20, r=20)
            )
            img_bytes = pio.to_image(fig_c, format="png", scale=2)
            return RLImage(_io.BytesIO(img_bytes), width=ancho_pts, height=alto_pts)
        except Exception:
            return None

    def heatmap_pdf_blanco(df_sub, titulo_mapa, rotar_180=False):
        """Heatmap con fondo blanco, leyenda en negro. rotar_180 invierte coordenadas 2T."""
        if df_sub is None or df_sub.empty:
            return None
        df_c = df_sub.copy()
        df_c["x"] = pd.to_numeric(df_c["x"], errors="coerce")
        df_c["y"] = pd.to_numeric(df_c["y"], errors="coerce")
        df_c = df_c.dropna(subset=["x", "y"])
        if df_c.empty:
            return None
        if rotar_180:
            df_c["x"] = 100.0 - df_c["x"]
            df_c["y"] = 60.0  - df_c["y"]
        fig = generar_heatmap_analisis(df_c, titulo_mapa=titulo_mapa)
        fig.update_layout(
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(color="#111827"),
            title=dict(font=dict(color="#111827")),
            legend=dict(font=dict(color="#111827")),
        )
        return fig_a_imagen(fig, ancho_pts=504, alto_pts=215)

    def torta_imagen(df_sub, col, mapa_colores=None, color_seq=None,
                     ancho_pts=200, alto_pts=190):
        """Torta con leyenda horizontal abajo, sin porcentajes encimados."""
        if df_sub is None or df_sub.empty or col not in df_sub.columns:
            return None
        counts = df_sub[col].fillna("Sin especificar").value_counts().reset_index()
        counts.columns = ["Valor", "Cantidad"]
        if counts.empty:
            return None
        kwargs = dict(values="Cantidad", names="Valor", hole=0.4)
        fig = (px.pie(counts, color="Valor", color_discrete_map=mapa_colores, **kwargs)
               if mapa_colores else
               px.pie(counts, color_discrete_sequence=color_seq or px.colors.qualitative.Set2, **kwargs))
        # Solo porcentaje dentro, sin etiqueta (evita superposición)
        fig.update_traces(
            textinfo="percent", textposition="inside",
            textfont=dict(size=9, color="#111827"),
            insidetextorientation="horizontal"
        )
        fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", y=-0.28, x=0.5, xanchor="center",
                        font=dict(size=8, color="#111827")),
            margin=dict(t=10, b=50, l=10, r=10),
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(color="#111827", size=8),
            width=int(ancho_pts * 1.6),
            height=int(alto_pts * 1.6),
        )
        try:
            img_bytes = pio.to_image(fig, format="png", scale=2)
            return RLImage(_io.BytesIO(img_bytes), width=ancho_pts, height=alto_pts)
        except Exception:
            return None

    def barras_top3_imagen(df_sub, col, color_barra="#4ECDC4",
                           ancho_pts=504, alto_pts=115, mapa_dorsal_nombre=None):
        """Barras horizontales Top-3. Nombre dentro de la barra, eje X limpio."""
        if df_sub is None or df_sub.empty or col not in df_sub.columns:
            return None
        top = (df_sub[col].replace("", pd.NA).dropna()
               .value_counts().head(3).reset_index())
        top.columns = ["Jugador", "Cantidad"]
        if top.empty:
            return None

        top_s = top.sort_values("Cantidad", ascending=True)

        if mapa_dorsal_nombre:
            top_s["Label"] = top_s.apply(
                lambda r: f"{mapa_dorsal_nombre.get(str(r['Jugador']), '#' + str(r['Jugador']))}  ({int(r['Cantidad'])})",
                axis=1
            )
        else:
            top_s["Label"] = top_s["Cantidad"].astype(str)

        fig = px.bar(top_s, x="Cantidad", y="Jugador", orientation="h",
                     text="Label", color_discrete_sequence=[color_barra])
        fig.update_traces(
            textposition="inside", insidetextanchor="start",
            textfont=dict(size=9, color="#0F172A"),
            marker=dict(line=dict(width=0)),
        )
        fig.update_layout(
            height=150, width=700,
            margin=dict(t=6, b=6, l=28, r=12),
            showlegend=False,
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(color="#111827", size=9),
            yaxis=dict(type="category", tickfont=dict(size=9)),
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        )
        try:
            img_bytes = pio.to_image(fig, format="png", scale=2)
            return RLImage(_io.BytesIO(img_bytes), width=ancho_pts, height=alto_pts)
        except Exception:
            return None

    def contenedor(flowables_lista, color_borde=None, color_fondo=None, padding=6):
        """Envuelve una lista de flowables en una 'tarjeta' con borde y fondo opcionales."""
        color_borde = color_borde or C_GRIS_BORDE
        color_fondo = color_fondo or colors.white
        t = Table([[flowables_lista]], colWidths=[504])
        t.setStyle(TableStyle([
            ("BOX",        (0, 0), (-1, -1), 0.8, color_borde),
            ("BACKGROUND", (0, 0), (-1, -1), color_fondo),
            ("PADDING",    (0, 0), (-1, -1), padding),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ]))
        return t

    def header_seccion(emoji, nombre_tipo, equipo_label, nombre_tiempo, cantidad):
        """Cabecera de sección: título + subtítulo + línea verde. Sin repetición."""
        # Solo muestra "FINALIZACIONES — PRIMER TIEMPO" sin el conteo en el título
        titulo_txt = f"{emoji}  {nombre_tipo.upper()}  ·  {equipo_label.upper()}"
        sub_txt    = f"{nombre_tiempo.upper()}  —  {cantidad} acciones registradas"
        elementos.append(Paragraph(titulo_txt, est_seccion))
        elementos.append(Paragraph(sub_txt,    est_caption))
        elementos.append(linea_verde())

    # =========================================================================
    # PÁGINAS DE EVENTO
    # =========================================================================

    def pagina_evento(df_sub, emoji, nombre_tipo, nombre_tiempo, equipo_label,
                      rotar_180=False, es_finalizaciones=False,
                      color_zona_seq=None, color_barra="#4ECDC4",
                      mapa_dorsal_nombre=None):
        """
        Layout por página:
          · Heatmap a ancho completo
          · Finalizaciones → Tabla resultado | Torta resultado (2 col)
          · Otros          → Tabla zona | Torta zona (2 col) + Top3 a ancho completo
        """
        if df_sub is None or df_sub.empty:
            return

        cantidad = len(df_sub)
        elementos.append(PageBreak())
        header_seccion(emoji, nombre_tipo, equipo_label, nombre_tiempo, cantidad)

        # Heatmap
        img_hm = heatmap_pdf_blanco(df_sub, f"{nombre_tipo} — {nombre_tiempo}", rotar_180=rotar_180)
        if img_hm:
            elementos.append(img_hm)
        else:
            elementos.append(Paragraph("<i>(Sin coordenadas para renderizar el mapa)</i>", est_caption))
        elementos.append(Spacer(1, 8))

        # ── FINALIZACIONES ────────────────────────────────────────────────────
        if es_finalizaciones:
            res_c = df_sub["resultado"].fillna("Sin especificar").value_counts().reset_index()
            res_c.columns = ["Resultado", "Cant."]
            total_r = res_c["Cant."].sum()
            res_c["%"] = ((res_c["Cant."] / total_r) * 100).round(1).astype(str) + "%"
            t_res = tabla_simple([["Resultado", "Cant.", "%"]] + res_c.values.tolist(),
                                 [110, 40, 40])

            df_gol = df_sub[df_sub["resultado"].str.lower() == "gol"]
            if not df_gol.empty:
                g_c = df_gol["jugador"].replace("", "S/D").value_counts().reset_index()
                g_c.columns = ["Dorsal", "Goles"]
                if mapa_dorsal_nombre:
                    g_c["Dorsal"] = g_c["Dorsal"].apply(
                        lambda d: mapa_dorsal_nombre.get(str(d), f"#{d}")
                    )
                    g_c.rename(columns={"Dorsal": "Jugador"}, inplace=True)
                    t_gol = tabla_simple([["Jugador", "Goles"]] + g_c.values.tolist(), [120, 36])
                else:
                    t_gol = tabla_simple([["Dorsal", "Goles"]] + g_c.values.tolist(), [90, 46])
            else:
                t_gol = Paragraph("Sin goles.", est_caption)

            col1 = [Paragraph("<b>Desglose de tiros:</b>", est_caption), t_res,
                    Spacer(1, 6), Paragraph("<b>Goleadores:</b>", est_caption), t_gol]

            img_torta = torta_imagen(df_sub, "resultado",
                                     mapa_colores=COLORES_RESULTADO_FINALIZACION,
                                     ancho_pts=248, alto_pts=200)
            col2 = [Paragraph("<b>Resultados:</b>", est_caption),
                    img_torta if img_torta else Paragraph("(Sin gráfico)", est_caption)]

            fila = Table([[col1, col2]], colWidths=[248, 256])
            fila.setStyle(TableStyle([
                ("VALIGN",      (0, 0), (-1, -1), "TOP"),
                ("PADDING",     (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (1, 0), (1, 0), 12),
            ]))
            elementos.append(fila)
            return

        # ── OTROS EVENTOS (Pérdidas / Recuperos / Faltas) ─────────────────────
        if "zona" in df_sub.columns:
            zona_c = df_sub["zona"].fillna("Sin especificar").value_counts().reset_index()
            zona_c.columns = ["Zona", "Cant."]
            total_z = zona_c["Cant."].sum()
            zona_c["%"] = ((zona_c["Cant."] / total_z) * 100).round(1).astype(str) + "%"
            t_zona = tabla_simple([["Zona", "Cant.", "%"]] + zona_c.values.tolist(),
                                  [115, 46, 46])
        else:
            t_zona = Paragraph("Sin datos de zona.", est_caption)

        col1 = [Paragraph("<b>Desglose por zona:</b>", est_caption), t_zona]
        img_torta = torta_imagen(df_sub, "zona",
                                 color_seq=color_zona_seq or px.colors.qualitative.Set2,
                                 ancho_pts=200, alto_pts=185)
        col2 = [Paragraph("<b>Distribución:</b>", est_caption),
                img_torta if img_torta else Paragraph("(Sin gráfico)", est_caption)]

        fila_sup = Table([[col1, col2]], colWidths=[207, 260])
        fila_sup.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("PADDING",     (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (1, 0), (1, 0), 8),
        ]))
        elementos.append(fila_sup)
        elementos.append(Spacer(1, 6))

        # Top 3 — ancho completo
        img_top3 = barras_top3_imagen(df_sub, "jugador", color_barra=color_barra,
                                      ancho_pts=504, alto_pts=112,
                                      mapa_dorsal_nombre=mapa_dorsal_nombre)
        if img_top3:
            elementos.append(Paragraph("<b>Top 3 jugadores:</b>", est_caption))
            elementos.append(img_top3)
        else:
            elementos.append(Paragraph("Sin datos de jugadores.", est_caption))

    # =========================================================================
    # DATOS BASE DEL PARTIDO
    # =========================================================================

    df_partido_info = pd.read_sql(
        "SELECT * FROM partidos WHERE fecha = ? AND rival = ?",
        conn, params=(str(fecha_sel), rival_sel)
    )
    fila_p = df_partido_info.iloc[0] if not df_partido_info.empty else pd.Series(dtype=object)

    def get(campo, default="—"):
        try:
            val = fila_p.get(campo, default)
            return val if (pd.notna(val) and str(val).strip() not in ("", "nan")) else default
        except Exception:
            return default

    competencia    = get("competencia", "—")
    lugar          = get("lugar", "—")
    equipo_propio  = get("equipo_propio", "Equipo Propio")
    lado_inicio_1t = get("lado_inicio_1t", "Derecha")
    rotar_180_2t   = "Izquierda" not in str(lado_inicio_1t)

    # Posesión
    try:
        pos_1t_p = float(fila_p.get("posesion_1t_propio_seg") or 0)
        pos_1t_r = float(fila_p.get("posesion_1t_rival_seg")  or 0)
        pos_2t_p = float(fila_p.get("posesion_2t_propio_seg") or 0)
        pos_2t_r = float(fila_p.get("posesion_2t_rival_seg")  or 0)
        tiene_posesion = (pos_1t_p + pos_1t_r + pos_2t_p + pos_2t_r) > 0
    except Exception:
        pos_1t_p = pos_1t_r = pos_2t_p = pos_2t_r = 0.0
        tiene_posesion = False

    # Marcador
    TIPOS_CON_GOL = ["Finalizaciones"]
    df_gm  = df_ev[df_ev["tipo_evento"].isin(TIPOS_CON_GOL) &
                   (df_ev["resultado"].str.lower() == "gol")]
    df_gec = df_ev[df_ev["tipo_evento"] == "Gol en Contra"]
    gp = (len(df_gm[df_gm["equipo"].str.lower() == "propio"]) +
          len(df_gec[df_gec["equipo"].str.lower() == "rival"]))
    gr = (len(df_gm[df_gm["equipo"].str.lower() == "rival"]) +
          len(df_gec[df_gec["equipo"].str.lower() == "propio"]))

    resultado_txt   = "VICTORIA" if gp > gr else ("DERROTA" if gp < gr else "EMPATE")
    c_resultado_hex = "#2ecc71" if gp > gr else ("#e74c3c" if gp < gr else "#F59E0B")
    c_resultado     = colors.HexColor(c_resultado_hex)

    # KPIs
    df_p        = df_ev[df_ev["equipo"].str.lower() == "propio"]
    total_fin   = len(df_p[df_p["tipo_evento"] == "Finalizaciones"])
    efectividad = f"{(gp / total_fin * 100):.0f}%" if total_fin > 0 else "—"
    perdidas_p  = len(df_p[df_p["tipo_evento"] == "Perdidas"])
    recuperos_p = len(df_p[df_p["tipo_evento"] == "Recuperos"])
    faltas_p    = len(df_p[df_p["tipo_evento"] == "Faltas"])
    abp_p       = len(df_p[df_p["tipo_evento"] == "ABP"])

    # Mapa dorsal → nombre
    try:
        df_jug_mapa = pd.read_sql(
            "SELECT numero_camiseta, nombre, apellido FROM jugadores WHERE activo = 1", conn
        )
        mapa_dorsal_nombre = {
            str(int(r["numero_camiseta"])): f"{r['apellido']} {r['nombre']}"
            for _, r in df_jug_mapa.iterrows()
            if pd.notna(r["numero_camiseta"])
        }
    except Exception:
        mapa_dorsal_nombre = {}

    # =========================================================================
    # PÁGINA 1: PORTADA
    # =========================================================================

    LOGO_BLANCO_PATH = "imagenes/Logo_RGB_Fondo Blanco_FutsalIQ.jpg"

    # Encabezado: título + logo
    titulo_col = [
        Paragraph("RESUMEN DE ESTADÍSTICAS DE JUEGO", est_titulo),
        Paragraph("Reporte táctico para el cuerpo técnico — FutsalIQ", est_subtitulo),
    ]
    if os.path.exists(LOGO_BLANCO_PATH):
        try:
            logo_col = [RLImage(LOGO_BLANCO_PATH, width=140, height=46)]
        except Exception:
            logo_col = [Paragraph("FutsalIQ", est_titulo)]
    else:
        logo_col = [Paragraph("FutsalIQ", est_titulo)]

    t_header = Table([[titulo_col, logo_col]], colWidths=[354, 150])
    t_header.setStyle(TableStyle([
        ("VALIGN",    (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",     (1, 0), (1, 0),   "RIGHT"),
        ("PADDING",   (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, 0),  2, C_VERDE),
    ]))
    elementos.append(t_header)
    elementos.append(Spacer(1, 10))

    # Metadata del partido
    meta_rows = [
        [Paragraph("<b>Fecha</b>",        est_cuerpo), Paragraph(str(fecha_sel),  est_cuerpo),
         Paragraph("<b>Competencia</b>",  est_cuerpo), Paragraph(competencia,     est_cuerpo)],
        [Paragraph("<b>Rival</b>",        est_cuerpo), Paragraph(rival_sel,       est_cuerpo),
         Paragraph("<b>Lugar / Sede</b>", est_cuerpo), Paragraph(lugar,           est_cuerpo)],
        [Paragraph("<b>Plantel</b>",      est_cuerpo), Paragraph(equipo_propio,   est_cuerpo),
         Paragraph("<b>Acciones reg.</b>",est_cuerpo), Paragraph(str(len(df_ev)), est_cuerpo)],
    ]
    t_meta = Table(meta_rows, colWidths=[80, 172, 90, 162])
    t_meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_GRIS_CARD),
        ("BOX",        (0, 0), (-1, -1), 0.8, C_GRIS_BORDE),
        ("INNERGRID",  (0, 0), (-1, -1), 0.3, C_GRIS_BORDE),
        ("PADDING",    (0, 0), (-1, -1), 6),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elementos.append(t_meta)
    elementos.append(Spacer(1, 12))

    # ── SCOREBOARD ────────────────────────────────────────────────────────────
    # Goleadores propios (solo de finalizaciones → resultado=Gol)
    df_goles_prop = df_gm[df_gm["equipo"].str.lower() == "propio"]
    df_goles_riv  = df_gm[df_gm["equipo"].str.lower() == "rival"]
    # Suma GEC: gec que sufrió el rival suma a propios; gec que sufrió propio suma a rival
    df_gec_a_favor_prop = df_gec[df_gec["equipo"].str.lower() == "rival"]
    df_gec_a_favor_riv  = df_gec[df_gec["equipo"].str.lower() == "propio"]

    def _html_goleadores(df_norm, df_gec_favor, es_propio):
        lineas = []
        for df_g, es_gec in [(df_norm, False), (df_gec_favor, True)]:
            if df_g.empty or "jugador" not in df_g.columns:
                continue
            cuentas = df_g["jugador"].replace("", "S/D").value_counts()
            for jug, cant in cuentas.items():
                if es_propio and not es_gec and mapa_dorsal_nombre:
                    nombre = mapa_dorsal_nombre.get(str(jug), f"#{jug}")
                else:
                    nombre = f"#{jug}"
                sufijo = " (GEC)" if es_gec else ""
                rep    = f" x{cant}" if cant > 1 else ""
                lineas.append(f"{nombre}{rep}{sufijo}")
        return "\n".join(lineas)

    gol_txt_prop = _html_goleadores(df_goles_prop, df_gec_a_favor_prop, True)
    gol_txt_riv  = _html_goleadores(df_goles_riv,  df_gec_a_favor_riv,  False)

    est_eq_nombre = _estilo("EqNom", fontSize=11, fontName="Helvetica-Bold",
                            textColor=C_OSCURO, alignment=1, leading=14)
    est_gol_lista = _estilo("GolLst", fontSize=8, fontName="Helvetica",
                            textColor=C_GRIS_TEXT, alignment=1, leading=12)
    est_score     = _estilo("Score", fontSize=38, fontName="Helvetica-Bold",
                            textColor=C_OSCURO, alignment=1, leading=42)
    est_resultado = _estilo("Res",   fontSize=10, fontName="Helvetica-Bold",
                            textColor=c_resultado, alignment=1, leading=14)

    score_propio = Paragraph(str(gp), _estilo("SP", fontSize=38, fontName="Helvetica-Bold",
                             textColor=C_GOL, alignment=1, leading=42))
    score_rival  = Paragraph(str(gr), _estilo("SR", fontSize=38, fontName="Helvetica-Bold",
                             textColor=C_RIVAL, alignment=1, leading=42))
    score_guion  = Paragraph("–",    _estilo("SG", fontSize=24, fontName="Helvetica-Bold",
                             textColor=C_OSCURO, alignment=1, leading=42))

    col_propio = [
        Paragraph(equipo_propio, est_eq_nombre),
        Spacer(1, 4),
        Paragraph(gol_txt_prop.replace("\n", "<br/>"), est_gol_lista),
    ]
    col_score = [
        score_propio, score_guion, score_rival,
        Spacer(1, 4),
        Paragraph(resultado_txt, est_resultado),
    ]
    col_rival = [
        Paragraph(rival_sel, est_eq_nombre),
        Spacer(1, 4),
        Paragraph(gol_txt_riv.replace("\n", "<br/>"), est_gol_lista),
    ]

    t_score = Table([[col_propio, col_score, col_rival]], colWidths=[186, 132, 186])
    t_score.setStyle(TableStyle([
        ("BOX",        (0, 0), (-1, -1), 1.5, c_resultado),
        ("BACKGROUND", (0, 0), (-1, -1), C_GRIS_CARD),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        # Línea de acento en el borde superior
        ("LINEABOVE",  (0, 0), (-1, 0), 3, c_resultado),
    ]))
    elementos.append(t_score)
    elementos.append(Spacer(1, 12))

    # ── GRID DE KPIs ─────────────────────────────────────────────────────────
    elementos.append(Paragraph("Indicadores del partido", est_sub))
    elementos.append(linea_verde())

    kpi_items = [
        ("Finalizaciones",    str(total_fin),   PALETA_EVENTO["Finalizaciones"]),
        ("Goles",             str(gp),          "#2ecc71"),
        ("Efectividad",       efectividad,       "#8DC63F"),
        ("Pérdidas",          str(perdidas_p),   PALETA_EVENTO["Perdidas"]),
        ("Recuperos",         str(recuperos_p),  PALETA_EVENTO["Recuperos"]),
        ("Faltas",            str(faltas_p),     PALETA_EVENTO["Faltas"]),
        ("ABP",               str(abp_p),        PALETA_EVENTO["ABP"]),
    ]
    elementos.append(grid_kpi(kpi_items))
    elementos.append(Spacer(1, 10))

    # ── RESUMEN EJECUTIVO ─────────────────────────────────────────────────────
    elementos.append(Paragraph("Resumen Ejecutivo", est_sub))
    elementos.append(linea_verde())
    resumen_lineas = [
        f"El equipo ejecutó <b>{total_fin} finalizaciones</b> con efectividad del <b>{efectividad}</b> ({gp} goles anotados).",
        f"Se registraron <b>{perdidas_p} pérdidas</b> y <b>{recuperos_p} recuperos</b> de pelota.",
        f"El equipo cometió <b>{faltas_p} faltas</b> y ejecutó <b>{abp_p} ABP</b>.",
    ]
    if tiene_posesion:
        total_pp = pos_1t_p + pos_2t_p
        total_rr = pos_1t_r + pos_2t_r
        grand    = total_pp + total_rr
        pct_p    = total_pp / grand * 100 if grand > 0 else 0
        resumen_lineas.append(
            f"Posesión total: <b>{pct_p:.1f}%</b> ({formatear_tiempo(total_pp)} vs {formatear_tiempo(total_rr)} del rival)."
        )
    for linea in resumen_lineas:
        elementos.append(Paragraph(f"  {linea}", est_resumen))

    # Tabla de posesión
    if tiene_posesion:
        elementos.append(Spacer(1, 8))
        elementos.append(Paragraph("Posesión de Pelota", est_sub))
        elementos.append(linea_verde())
        total_pp = pos_1t_p + pos_2t_p
        total_rr = pos_1t_r + pos_2t_r
        grand    = total_pp + total_rr
        pos_rows = [
            ["", "1er Tiempo", "2do Tiempo", "Total", "%"],
            [equipo_propio,
             formatear_tiempo(pos_1t_p), formatear_tiempo(pos_2t_p),
             formatear_tiempo(total_pp),
             f"{total_pp/grand*100:.1f}%" if grand > 0 else "—"],
            [rival_sel,
             formatear_tiempo(pos_1t_r), formatear_tiempo(pos_2t_r),
             formatear_tiempo(total_rr),
             f"{total_rr/grand*100:.1f}%" if grand > 0 else "—"],
        ]
        elementos.append(tabla_simple(pos_rows, [145, 75, 75, 75, 58]))

    # =========================================================================
    # PÁGINA 2: VOLUMEN TÁCTICO
    # =========================================================================
    df_propio_total = df_ev[df_ev["equipo"].str.lower() == "propio"].copy()
    df_propio_1t    = df_propio_total[df_propio_total["tiempo"] == "1T"].copy()
    df_propio_2t    = df_propio_total[df_propio_total["tiempo"] == "2T"].copy()

    elementos.append(PageBreak())
    elementos.append(Paragraph("DISTRIBUCIÓN DE VOLUMEN TÁCTICO", est_seccion))
    elementos.append(Paragraph(f"Acciones del equipo propio — {equipo_propio}", est_caption))
    elementos.append(linea_verde())

    if not df_propio_total.empty:
        df_vol = df_propio_total.groupby(["tipo_evento", "tiempo"]).size().unstack(fill_value=0)
        for col_t in ["1T", "2T"]:
            if col_t not in df_vol.columns:
                df_vol[col_t] = 0
        df_vol["Total"] = df_vol["1T"] + df_vol["2T"]
        df_vol = df_vol.sort_values("Total", ascending=False).reset_index()

        t_vol = tabla_simple(
            [["Tipo de Evento", "Total", "1T", "2T"]] +
            df_vol[["tipo_evento", "Total", "1T", "2T"]].values.tolist(),
            [195, 70, 70, 70]
        )
        elementos.append(t_vol)
        elementos.append(Spacer(1, 14))

        try:
            # Colores del sistema para cada tipo de evento
            colores_vol = [PALETA_EVENTO.get(t, "#9CA3AF") for t in df_vol["tipo_evento"]]
            fig_vol = px.bar(
                df_vol, y="tipo_evento", x="Total", orientation="h",
                text="Total", color="tipo_evento",
                color_discrete_map={t: PALETA_EVENTO.get(t, "#9CA3AF") for t in df_vol["tipo_evento"]}
            )
            fig_vol.update_traces(
                textposition="outside",
                textfont=dict(size=10, color="#111827"),
                marker=dict(line=dict(width=0)),
            )
            fig_vol.update_layout(
                margin=dict(l=120, r=40, t=10, b=30),
                height=260, width=504,
                paper_bgcolor="white", plot_bgcolor="white",
                showlegend=False,
                font=dict(color="#111827", size=9),
                xaxis=dict(showgrid=True, gridcolor="#E5E7EB", title=None,
                           showticklabels=False),
                yaxis=dict(autorange="reversed", title=None,
                           tickfont=dict(size=9)),
            )
            img_bytes_v = pio.to_image(fig_vol, format="png", scale=2)
            elementos.append(RLImage(_io.BytesIO(img_bytes_v), width=504, height=260))
        except Exception as e:
            elementos.append(Paragraph(f"<i>(Error al generar gráfico: {e})</i>", est_caption))

    # =========================================================================
    # SECCIONES POR TIPO DE EVENTO (Total → 1T → 2T)
    # =========================================================================
    config_tipos = [
        ("Finalizaciones", "🎯", "FINALIZACIONES", px.colors.qualitative.Set1,   PALETA_EVENTO["Finalizaciones"], True),
        ("Perdidas",       "🔴", "PÉRDIDAS",       px.colors.qualitative.Set2,   PALETA_EVENTO["Perdidas"],       False),
        ("Recuperos",      "🟢", "RECUPEROS",      px.colors.qualitative.Set3,   PALETA_EVENTO["Recuperos"],      False),
        ("Faltas",         "🟨", "FALTAS",         px.colors.qualitative.Pastel1, PALETA_EVENTO["Faltas"],         False),
    ]

    for tipo_ev, emoji, label, color_seq, color_barra, es_fin in config_tipos:
        df_tot = df_propio_total[df_propio_total["tipo_evento"] == tipo_ev].copy()
        df_1t  = df_propio_1t[df_propio_1t["tipo_evento"]   == tipo_ev].copy()
        df_2t  = df_propio_2t[df_propio_2t["tipo_evento"]   == tipo_ev].copy()

        if df_tot.empty:
            continue

        pagina_evento(df_tot, emoji, label, "TOTAL",
                      equipo_propio, rotar_180=False,
                      es_finalizaciones=es_fin,
                      color_zona_seq=color_seq, color_barra=color_barra,
                      mapa_dorsal_nombre=mapa_dorsal_nombre)

        pagina_evento(df_1t, emoji, label, "PRIMER TIEMPO",
                      equipo_propio, rotar_180=False,
                      es_finalizaciones=es_fin,
                      color_zona_seq=color_seq, color_barra=color_barra,
                      mapa_dorsal_nombre=mapa_dorsal_nombre)

        pagina_evento(df_2t, emoji, label, "SEGUNDO TIEMPO",
                      equipo_propio, rotar_180=rotar_180_2t,
                      es_finalizaciones=es_fin,
                      color_zona_seq=color_seq, color_barra=color_barra,
                      mapa_dorsal_nombre=mapa_dorsal_nombre)

    # =========================================================================
    # ABP PROPIO (consolidado en una página, sin heatmap)
    # =========================================================================
    def _abp_tipo_series(df_abp_sub):
        if "tipo_abp" in df_abp_sub.columns:
            s = df_abp_sub["tipo_abp"].replace("", pd.NA)
        else:
            s = pd.Series(index=df_abp_sub.index, dtype=object)
        if "resultado" in df_abp_sub.columns:
            s = s.fillna(df_abp_sub["resultado"])
        return s.fillna("Sin especificar")

    def bloque_abp(df_abp_sub, nombre_tiempo):
        if df_abp_sub is None or df_abp_sub.empty:
            return []

        cantidad = len(df_abp_sub)
        bloque = [
            Paragraph(f"<b>{nombre_tiempo.upper()}  —  {cantidad} ABP</b>", est_caption),
            Spacer(1, 4)
        ]

        tipo_s = _abp_tipo_series(df_abp_sub)
        tipo_c = tipo_s.value_counts().reset_index()
        tipo_c.columns = ["Tipo de ABP", "Cant."]
        total_abp = tipo_c["Cant."].sum()
        tipo_c["%"] = ((tipo_c["Cant."] / total_abp) * 100).round(1).astype(str) + "%"

        lado_c = (df_abp_sub["zona"].fillna("Sin especificar").value_counts().reset_index()
                  if "zona" in df_abp_sub.columns else pd.DataFrame(columns=["Lado", "Cant."]))
        if not lado_c.empty and "zona" in df_abp_sub.columns:
            lado_c.columns = ["Lado", "Cant."]
        lado_total = lado_c["Cant."].sum() if not lado_c.empty else 0

        t_simple = tabla_simple([["Tipo de ABP", "Cant.", "%"]] + tipo_c.values.tolist(),
                                [105, 32, 32])
        col1 = [Paragraph("Desglose:", est_caption), t_simple]

        # Torta tipo ABP
        try:
            ancho_c, alto_c = 150, 112
            df_tp = tipo_c[["Tipo de ABP", "Cant."]].copy()
            df_tp.columns = ["Tipo", "Cantidad"]
            fig_t = px.pie(df_tp, values="Cantidad", names="Tipo", hole=0.4,
                           color_discrete_sequence=px.colors.qualitative.Pastel2)
            fig_t.update_traces(textinfo="percent", textposition="inside",
                                textfont=dict(size=7), insidetextorientation="horizontal")
            fig_t.update_layout(
                showlegend=True,
                legend=dict(orientation="h", y=-0.28, x=0.5, xanchor="center",
                            font=dict(size=7, color="#111827")),
                margin=dict(t=6, b=28, l=6, r=6),
                paper_bgcolor="white", plot_bgcolor="white",
                font=dict(color="#111827", size=7),
                width=int(ancho_c * 1.6), height=int(alto_c * 1.6)
            )
            img_t = RLImage(_io.BytesIO(pio.to_image(fig_t, format="png", scale=2)),
                            width=ancho_c, height=alto_c)
            col2 = [Paragraph("Tipos:", est_caption), img_t]
        except Exception:
            col2 = [Paragraph("(Sin gráfico)", est_caption)]

        # Barras de lado
        try:
            if not lado_c.empty and lado_total > 0:
                df_lp = lado_c[["Lado", "Cant."]].copy()
                df_lp.columns = ["Lado", "Cantidad"]
                mapa_lado = {"Derecho": "#118AB2", "Izquierdo": "#F4A261",
                             "Sin especificar": "#6B7280"}
                ancho_b, alto_b = 132, 112
                fig_b = px.bar(df_lp, x="Lado", y="Cantidad", color="Lado",
                               color_discrete_map=mapa_lado, text="Cantidad")
                fig_b.update_traces(
                    textposition="outside",
                    textfont=dict(size=9, color="#111827"),
                    marker=dict(line=dict(width=0)),
                )
                fig_b.update_layout(
                    height=int(alto_b * 1.6), width=int(ancho_b * 1.6),
                    margin=dict(t=12, b=20, l=10, r=10),
                    showlegend=False,
                    paper_bgcolor="white", plot_bgcolor="white",
                    font=dict(color="#111827", size=8),
                    xaxis_title=None, yaxis_title=None,
                    yaxis=dict(showgrid=False),
                )
                img_b = RLImage(_io.BytesIO(pio.to_image(fig_b, format="png", scale=2)),
                                width=ancho_b, height=alto_b)
                col3 = [Paragraph("Por lado:", est_caption), img_b]
            else:
                col3 = [Paragraph("Sin datos de lado.", est_caption)]
        except Exception:
            col3 = [Paragraph("(Sin gráfico)", est_caption)]

        fila = Table([[col1, col2, col3]], colWidths=[175, 162, 148])
        fila.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("PADDING",     (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (1, 0), (1, 0), 6),
            ("LEFTPADDING", (2, 0), (2, 0), 6),
        ]))
        bloque.append(fila)
        bloque.append(Spacer(1, 10))
        return bloque

    def pagina_abp_unica(df_abp_p, equipo_label):
        if df_abp_p is None or df_abp_p.empty:
            return
        elementos.append(PageBreak())
        elementos.append(Paragraph(f"🚩  ABP — {equipo_label.upper()}", est_seccion))
        elementos.append(Paragraph("Análisis consolidado — Total, 1T y 2T", est_caption))
        elementos.append(linea_verde())
        elementos.extend(bloque_abp(df_abp_p, "TOTAL"))
        elementos.append(linea_gris())
        elementos.extend(bloque_abp(df_abp_p[df_abp_p["tiempo"] == "1T"], "PRIMER TIEMPO"))
        elementos.append(linea_gris())
        elementos.extend(bloque_abp(df_abp_p[df_abp_p["tiempo"] == "2T"], "SEGUNDO TIEMPO"))

    df_abp_p = df_propio_total[df_propio_total["tipo_evento"] == "ABP"].copy()
    if not df_abp_p.empty:
        pagina_abp_unica(df_abp_p, equipo_label=equipo_propio)

    # =========================================================================
    # FINALIZACIONES Y ABP DEL RIVAL
    # =========================================================================
    df_rival_ev  = df_ev[df_ev["equipo"].str.lower() == "rival"]
    df_fin_rival = df_rival_ev[df_rival_ev["tipo_evento"] == "Finalizaciones"].copy()

    if not df_fin_rival.empty:
        pagina_evento(df_fin_rival, "🔍", f"FINALIZACIONES {rival_sel.upper()}",
                      "TOTAL", rival_sel, rotar_180=False, es_finalizaciones=True)
        df_fn_1t = df_fin_rival[df_fin_rival["tiempo"] == "1T"]
        df_fn_2t = df_fin_rival[df_fin_rival["tiempo"] == "2T"]
        pagina_evento(df_fn_1t, "🔍", f"FINALIZACIONES {rival_sel.upper()}",
                      "PRIMER TIEMPO", rival_sel, rotar_180=False, es_finalizaciones=True)
        pagina_evento(df_fn_2t, "🔍", f"FINALIZACIONES {rival_sel.upper()}",
                      "SEGUNDO TIEMPO", rival_sel, rotar_180=True, es_finalizaciones=True)

    df_abp_rival = df_rival_ev[df_rival_ev["tipo_evento"] == "ABP"].copy()
    if not df_abp_rival.empty:
        pagina_abp_unica(df_abp_rival, equipo_label=rival_sel)

    # =========================================================================
    # TABLA INDIVIDUAL POR DORSAL
    # =========================================================================
    elementos.append(PageBreak())
    elementos.append(Paragraph("RENDIMIENTO INDIVIDUAL POR DORSAL", est_seccion))
    elementos.append(linea_verde())

    df_ind = df_propio_total[df_propio_total["jugador"].replace("", pd.NA).notna()].copy()
    if not df_ind.empty:
        tabla_piv = (df_ind.groupby(["jugador", "tipo_evento"])
                           .size().unstack(fill_value=0).reset_index())
        tabla_piv.rename(columns={"jugador": "Dorsal"}, inplace=True)
        tabla_piv = tabla_piv.sort_values(
            "Dorsal", key=lambda x: pd.to_numeric(x, errors="coerce")
        )

        # Enriquecer con nombre si hay mapa
        if mapa_dorsal_nombre:
            tabla_piv["Nombre"] = tabla_piv["Dorsal"].apply(
                lambda d: mapa_dorsal_nombre.get(str(d), "")
            )
            cols_orden = ["Dorsal", "Nombre"] + [
                c for c in tabla_piv.columns if c not in ("Dorsal", "Nombre")
            ]
            tabla_piv = tabla_piv[cols_orden]

        cols = list(tabla_piv.columns)
        ancho_dorsal = 38
        ancho_nombre = 110 if "Nombre" in cols else 0
        ancho_resto  = min(55, int((504 - ancho_dorsal - ancho_nombre) / max(len(cols) - 2, 1)))
        anchos = [ancho_dorsal]
        if "Nombre" in cols:
            anchos.append(ancho_nombre)
        anchos += [ancho_resto] * (len(cols) - len(anchos))

        data_ind = [cols] + [[str(v) for v in row] for _, row in tabla_piv.iterrows()]
        elementos.append(tabla_simple(data_ind, anchos))

        elementos.append(Spacer(1, 10))
        elementos.append(Paragraph("Destacados del partido:", est_sub))
        for col_dest, label_dest in [
            ("Finalizaciones", "finalizaciones"), ("Recuperos", "recuperos"),
            ("Faltas", "faltas"), ("Perdidas", "pérdidas"),
        ]:
            if col_dest in tabla_piv.columns:
                idx = tabla_piv[col_dest].idxmax()
                top = tabla_piv.loc[idx]
                if top[col_dest] > 0:
                    nombre_dest = top.get("Nombre", "") or f"Dorsal {top['Dorsal']}"
                    elementos.append(Paragraph(
                        f"  Mayor cantidad de {label_dest}: <b>{nombre_dest}</b> ({top[col_dest]})",
                        est_resumen
                    ))
    else:
        elementos.append(Paragraph("Sin datos individuales para este partido.", est_caption))

    # =========================================================================
    # PIE DE PÁGINA
    # =========================================================================
    elementos.append(Spacer(1, 14))
    elementos.append(linea_verde())
    elementos.append(Paragraph(
        "Generado por FutsalIQ Analyzer  ·  futsaliq@gmail.com  ·  2964 53-8214  ·  © 2026",
        est_footer
    ))

    doc.build(elementos)
    buffer.seek(0)
    return buffer