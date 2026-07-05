import sqlite3
import random
from datetime import datetime, timedelta

def generar_datos_pro():
    # Conectamos a la base de datos (se crea el archivo si no existe)
    conn = sqlite3.connect("futsal.db")
    cursor = conn.cursor()
    
    print("🛠️ Creando estructura de tablas limpias...")
    # 1. Creamos las tablas por si las moscas
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS partidos (
            fecha TEXT,
            rival TEXT PRIMARY KEY,
            goles_troncos INTEGER,
            goles_rival INTEGER,
            condicion TEXT
        );
    """)
    
    # 2. Ahora que existen seguro, las vaciamos para no duplicar datos
    cursor.execute("DELETE FROM eventos;")
    cursor.execute("DELETE FROM partidos;")
    
    print("⚽ Generando partidos y eventos sintéticos...")
    
    # Datos de configuración de la simulación
    rivales = ["Desamparados", "Defensores FC", "La Academia", "Sportivo TDF", "Patagonia Futsal"]
    tipos_evento = ["Finalizaciones", "Recuperos", "Perdidas", "Faltas", "Tarjetas"]
    resultados_fin = ["Gol", "Al arco (Atajado / Palo)", "Desviado (Afuera)", "Bloqueado (En defensor)"]
    jugadores = [str(i) for i in [5, 7, 9, 10, 11, 22]]
    
    fecha_base = datetime.now() - timedelta(days=60)
    
    for i, rival in enumerate(rivales):
        fecha_partido = (fecha_base + timedelta(days=i*7)).strftime("%Y-%m-%d")
        condicion = random.choice(["Local", "Visitante"])
        
        # Simular eventos de este partido (entre 30 y 50 eventos por partido)
        num_eventos = random.randint(30, 50)
        goles_troncos_calc = 0
        goles_rival_calc = random.randint(0, 4)
        
        for _ in range(num_eventos):
            tipo = random.choice(tipos_evento)
            jugador = random.choice(jugadores)
            tiempo = random.choice(["1T", "2T"])
            equipo = random.choice(["Local", "Visitante"])
            
            # Grilla de clics estándar (0-100 para X, 0-60 para Y)
            x = round(random.uniform(5, 95), 2)
            y = round(random.uniform(3, 57), 2)
            zona = "Defensiva" if x < 50 else "Ofensiva"
            
            res_evento = ""
            tarjeta = ""
            
            if tipo == "Finalizaciones":
                res_evento = random.choice(resultados_fin)
                if res_evento == "Gol" and equipo == "Local" and condicion == "Local":
                    goles_troncos_calc += 1
                elif res_evento == "Gol" and equipo == "Visitante" and condicion == "Visitante":
                    goles_troncos_calc += 1
            elif tipo == "Tarjetas":
                tarjeta = random.choice(["Amarilla", "Roja"])
                
            cursor.execute("""
                INSERT INTO eventos (fecha, rival, tipo_evento, tiempo, equipo, jugador, zona, resultado, tipo_tarjeta, x, y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fecha_partido, rival, tipo, tiempo, equipo, jugador, zona, res_evento, tarjeta, x, y))
            
        # Insertar la ficha del partido con los goles calculados
        cursor.execute("""
            INSERT OR REPLACE INTO partidos (fecha, rival, goles_troncos, goles_rival, condicion)
            VALUES (?, ?, ?, ?, ?)
        """, (fecha_partido, rival, goles_troncos_calc, goles_rival_calc, condicion))
        
    conn.commit()
    conn.close()
    print("✨ ¡Temporada sintética generada con éxito en futsal.db!")

if __name__ == "__main__":
    generar_datos_pro()