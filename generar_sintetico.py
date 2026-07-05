import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# Configuración de los equipos de Río Grande
MI_EQUIPO = "Los Troncos"
RIVALES = ["Camioneros", "Rosario", "ADEFU", "San Martin"]
EVENTOS_TIPOS = ["Finalizaciones", "Recuperos", "Perdidas", "Faltas", "Tarjetas"]

# Jugadores de Los Troncos (Simulados del 1 al 12)
JUGADORES = [str(i) for i in range(1, 13)]

def generar_coordenadas(tipo_evento, es_ofensivo):
    """Genera coordenadas realistas en escala 100x60 según el tipo de acción."""
    if tipo_evento == "Finalizaciones":
        # Mayormente cerca de los arcos (X muy baja o X muy alta)
        x = random.choice([random.uniform(5, 25), random.uniform(75, 95)])
        y = random.uniform(15, 45)
    elif tipo_evento == "Recuperos":
        # Distribuidos pero con énfasis en mitad de cancha hacia atrás
        x = random.uniform(15, 65)
        y = random.uniform(5, 55)
    else:
        # Pérdidas, Faltas y Tarjetas en cualquier lugar de la grilla
        x = random.uniform(10, 90)
        y = random.uniform(5, 55)
    return round(x, 1), round(y, 1)

def crear_dataset_futsal(num_eventos=200):
    datos = []
    fecha_base = datetime.now()

    # Vamos a simular 4 partidos para tener variedad de localías
    partidos_config = [
        {"rival": "Camioneros", "condicion": "Local"},       # Los Troncos es Local
        {"rival": "Rosario", "condicion": "Visitante"},     # Los Troncos es Visitante
        {"rival": "ADEFU", "condicion": "Local"},           # Los Troncos es Local
        {"rival": "San Martin", "condicion": "Visitante"}    # Los Troncos es Visitante
    ]

    for idx, part in enumerate(partidos_config):
        fecha_partido = (fecha_base - timedelta(days=idx*7)).strftime("%Y-%m-%d")
        
        # Generamos ~50 eventos por partido
        for _ in range(num_eventos // len(partidos_config)):
            tipo_ev = random.choice(EVENTOS_TIPOS)
            tiempo = random.choice(["1T", "2T"])
            
            # Decidimos de qué equipo es el evento (70% de eventos propios de Los Troncos para poblar tu análisis)
            es_evento_propio = random.random() < 0.70
            
            if es_evento_propio:
                equipo_registro = part["condicion"]  # Si somos locales, registra 'Local'. Si somos visitantes, 'Visitante'.
                jugador = random.choice(JUGADORES)
            else:
                # El evento es del Rival
                equipo_registro = "Visitante" if part["condicion"] == "Local" else "Local"
                jugador = f"R-{random.randint(1, 10)}" # Jugador rival genérico para no mezclar con los tuyos
            
            # Coordenadas y zonas
            x, y = generar_coordenadas(tipo_ev, es_ofensivo=(x > 50 if 'x' in locals() else True))
            zona = "Ofensiva" if x >= 50 else "Defensiva"
            
            # Campos condicionales
            resultado = ""
            tipo_tarjeta = ""
            if tipo_ev == "Finalizaciones":
                resultado = random.choice(["Al arco", "Desviado", "Bloqueado"])
            elif tipo_ev == "Tarjetas":
                tipo_tarjeta = random.choice(["Amarilla", "Roja"]) if random.random() < 0.15 else ""
                if not tipo_tarjeta: continue # saltamos si no amerita tarjeta real para mantener consistencia
            
            datos.append({
                "fecha": fecha_partido,
                "rival": part["rival"],
                "tipo_evento": tipo_ev,
                "tiempo": tiempo,
                "equipo": equipo_registro,
                "jugador": jugador,
                "zona": zona,
                "resultado": resultado,
                "tipo_tarjeta": tipo_tarjeta,
                "x": x,
                "y": y
            })

    df = pd.DataFrame(datos)
    df.to_csv("eventos_sinteticos.csv", index=False)
    print(f"🎉 ¡Dataset sintético exitosamente generado con {len(df)} eventos en 'eventos_sinteticos.csv'!")

if __name__ == "__main__":
    crear_dataset_futsal()
    