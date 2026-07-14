import sqlite3
import pandas as pd
import os


def conectar_db():
    return sqlite3.connect("futsal.db")


def limpiar_valor(val):
    if pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() in ["nan", "n/a", "none"]:
        return None
    return val


def mapear_resultado(res_excel):
    if res_excel is None:
        return "DESVIADO"
    res_limpio = str(res_excel).strip().upper()
    if res_limpio == "A":
        return "ATAJADO"
    elif res_limpio == "D":
        return "DESVIADO"
    if "GOL" in res_limpio:
        return "GOL"
    elif "DESV" in res_limpio:
        return "DESVIADO"
    elif "ATAJ" in res_limpio:
        return "ATAJADO"
    elif "BLOQ" in res_limpio:
        return "BLOQUEADO"
    return "DESVIADO"


# =========================================================
# 🌟 CORRECCIÓN CLAVE: detección robusta de la hoja de datos
# =========================================================
def detectar_hoja_datos(xls):
    """
    Encuentra la hoja que realmente contiene el detalle táctico completo
    (Finalizaciones, Pérdidas, Recuperos y datos del Rival).

    IMPORTANTE: las hojas llamadas "Mapa" suelen ser solo una grilla visual
    (una cancha dibujada con formato condicional dentro del propio Excel)
    y NO contienen los bloques de Pérdidas/Recuperos/Rival. Buscar por
    nombre ("mapa" in sheet.lower()) hacía que el script leyera esa hoja
    incompleta en lugar de la tabla real de datos por jugador.

    Estrategia: buscamos la hoja cuyo encabezado (fila 0) contenga las
    columnas "Perd. 1T" y "Rec. 1T", que solo existen en la tabla completa.
    """
    marcadores_requeridos = ["Perd. 1T", "Rec. 1T"]

    for sheet in xls.sheet_names:
        header = pd.read_excel(xls, sheet_name=sheet, header=None, nrows=1).iloc[0]
        header_str = [str(c) for c in header.tolist()]
        if all(any(marcador in celda for celda in header_str) for marcador in marcadores_requeridos):
            print(f"✅ Hoja de datos detectada automáticamente: '{sheet}'")
            return sheet

    # Fallback de seguridad: si por algún motivo no se encuentran los
    # marcadores (headers editados a mano, etc.), usamos la hoja con más
    # columnas, ya que la tabla completa siempre es la más ancha.
    anchos = {
        sheet: pd.read_excel(xls, sheet_name=sheet, header=None, nrows=1).shape[1]
        for sheet in xls.sheet_names
    }
    hoja_fallback = max(anchos, key=anchos.get)
    print(f"⚠️ No se encontraron los marcadores esperados. Usando hoja más ancha como fallback: '{hoja_fallback}'")
    return hoja_fallback


def importar_excel_completo_dt(archivo_path, fecha_partido, rival_partido):
    if not os.path.exists(archivo_path):
        print(f"❌ Error: No se encontró el archivo en '{archivo_path}'")
        return

    try:
        xls = pd.ExcelFile(archivo_path)

        hoja_mapa = detectar_hoja_datos(xls)

        print(f"📖 Leyendo datos desde la pestaña táctica: '{hoja_mapa}'")
        df = pd.read_excel(xls, sheet_name=hoja_mapa)

        conn = conectar_db()
        c = conn.cursor()

        # Limpieza previa del partido para evitar duplicados
        c.execute("DELETE FROM eventos WHERE fecha = ? AND rival = ?", (str(fecha_partido), rival_partido))
        conn.commit()
        print("🧹 Base de datos limpia de registros anteriores para este partido.")

        insertados = 0

        # --- FUNCIÓN DE REGISTRO INTERNO ---
        def registrar_evento(tipo, tiempo, jugador, x_orig, y_orig, resultado=None, equipo='Local'):
            nonlocal insertados

            jugador_limpio = limpiar_valor(jugador)

            # 🌟 CORRECCIÓN: las finalizaciones del Rival muchas veces no
            # traen número de camiseta asignado. Antes, si jugador_limpio
            # era None, se descartaba TODO el evento (incluyendo x, y y
            # resultado, que sí estaban disponibles). Ahora, si el evento
            # es del Rival, lo registramos igual con un jugador genérico.
            if jugador_limpio is None:
                if equipo == 'Rival':
                    jugador_limpio = "Rival"
                else:
                    return

            # Filtro anti-encabezados (ignora palabras como "Final.1", "x", "y")
            jugador_str_control = str(jugador_limpio).strip().lower()
            if any(x in jugador_str_control for x in ["final", "pérdid", "recup", "jugador", "rival", "x", "y"]) \
                    and jugador_str_control != "rival":
                return

            try:
                # Convertimos a entero para limpiar formatos como "10.0"
                jugador_str = str(int(float(jugador_limpio)))
            except ValueError:
                # Si es texto (ej: "Rival" o un nombre), lo guardamos como texto
                jugador_str = str(jugador_limpio)

            x_val = limpiar_valor(x_orig)
            y_val = limpiar_valor(y_orig)

            x_db, y_db = None, None
            if x_val is not None and y_val is not None:
                try:
                    # 🌟 Conversión de escala confirmada: el Excel del DT usa
                    # una cancha de 40x20, y la app espera la grilla 100x60.
                    x_db = float(x_val) * 2.5
                    y_db = float(y_val) * 3.0
                except ValueError:
                    pass

            # Si no hay coordenadas válidas, no registramos el evento táctico
            if x_db is None or y_db is None:
                return

            zona = "Defensiva" if x_db < 50 else "Ofensiva"

            c.execute("""
                INSERT INTO eventos (fecha, rival, tipo_evento, tiempo, equipo, jugador, zona, resultado, x, y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(fecha_partido), rival_partido, tipo, tiempo, equipo, jugador_str, zona, resultado, x_db, y_db))
            insertados += 1

        def obtener_celda_segura(fila, idx):
            if idx < len(fila):
                return fila.iloc[idx]
            return None

        # Recorremos cada fila del Excel mapeando las columnas reales de la planilla táctica
        # (índices verificados directamente contra "LT vs Camioneros (2)")
        for idx in range(len(df)):
            fila = df.iloc[idx]

            # =========================================================
            # 1. NUESTRAS FINALIZACIONES (Local)
            # =========================================================
            # 1T: col38=Res, col39=Jugador, col40=X, col41=Y
            val_res_1t = obtener_celda_segura(fila, 38)
            res_txt_1t = mapear_resultado(val_res_1t) if pd.notna(val_res_1t) else None
            registrar_evento("Finalizaciones", "1T", obtener_celda_segura(fila, 39), obtener_celda_segura(fila, 40), obtener_celda_segura(fila, 41), res_txt_1t, equipo='Local')

            # 2T: col42=Res, col43=Jugador, col44=X, col45=Y
            val_res_2t = obtener_celda_segura(fila, 42)
            res_txt_2t = mapear_resultado(val_res_2t) if pd.notna(val_res_2t) else None
            registrar_evento("Finalizaciones", "2T", obtener_celda_segura(fila, 43), obtener_celda_segura(fila, 44), obtener_celda_segura(fila, 45), res_txt_2t, equipo='Local')

            # =========================================================
            # 2. NUESTRAS PÉRDIDAS (Local)
            # =========================================================
            # 1T: col46=Jugador, col47=X, col48=Y
            registrar_evento("Perdidas", "1T", obtener_celda_segura(fila, 46), obtener_celda_segura(fila, 47), obtener_celda_segura(fila, 48), equipo='Local')
            # 2T: col49=Jugador, col50=X, col51=Y
            registrar_evento("Perdidas", "2T", obtener_celda_segura(fila, 49), obtener_celda_segura(fila, 50), obtener_celda_segura(fila, 51), equipo='Local')

            # =========================================================
            # 3. NUESTROS RECUPEROS (Local)
            # =========================================================
            # 1T: col52=Jugador, col53=X, col54=Y
            registrar_evento("Recuperos", "1T", obtener_celda_segura(fila, 52), obtener_celda_segura(fila, 53), obtener_celda_segura(fila, 54), equipo='Local')
            # 2T: col55=Jugador, col56=X, col57=Y
            registrar_evento("Recuperos", "2T", obtener_celda_segura(fila, 55), obtener_celda_segura(fila, 56), obtener_celda_segura(fila, 57), equipo='Local')

            # =========================================================
            # 4. FINALIZACIONES DEL RIVAL (Rival)
            # =========================================================
            # 1T: col72=Res, col73=Jugador, col74=X, col75=Y
            val_res_r1 = obtener_celda_segura(fila, 72)
            res_txt_r1 = mapear_resultado(val_res_r1) if pd.notna(val_res_r1) else None
            registrar_evento("Finalizaciones", "1T", obtener_celda_segura(fila, 73), obtener_celda_segura(fila, 74), obtener_celda_segura(fila, 75), res_txt_r1, equipo='Rival')

            # 2T: col76=Res, col77=Jugador, col78=X, col79=Y
            val_res_r2 = obtener_celda_segura(fila, 76)
            res_txt_r2 = mapear_resultado(val_res_r2) if pd.notna(val_res_r2) else None
            registrar_evento("Finalizaciones", "2T", obtener_celda_segura(fila, 77), obtener_celda_segura(fila, 78), obtener_celda_segura(fila, 79), res_txt_r2, equipo='Rival')

        conn.commit()
        conn.close()

        print("--------------------------------------------------")
        print("🎉 ¡MIGRACIÓN DE PARTIDO COMPLETADA EXITOSAMENTE!")
        print(f"🏟️  Partido: Los Troncos vs {rival_partido}")
        print(f"📅 Fecha Oficial: {fecha_partido}")
        print(f"📊 Total de eventos tácticos reales registrados: {insertados}")
        print("--------------------------------------------------")

    except Exception as e:
        print(f"❌ Error crítico procesando el archivo: {str(e)}")


if __name__ == "__main__":
    archivo_excel = "Camioneros_Historico.xlsx"
    fecha = "2025-08-22"
    rival = "Camioneros"
    importar_excel_completo_dt(archivo_excel, fecha, rival)
