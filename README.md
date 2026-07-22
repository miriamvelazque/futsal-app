# Futsal App

Aplicación de análisis táctico y gestión de partidos de futsal desarrollada en Python. El proyecto actual se basa en un único dashboard activo y datos almacenados en SQLite.

## Estructura del proyecto activa

- `main_app.py` - Dashboard principal con carga de eventos, visualización táctica y mapas de calor de densidad.
- `generar_sintetico.py` - Generador de datos sintéticos que crea `eventos_sinteticos.csv`.
- `partidos.csv` - Datos de partidos de ejemplo.
- `eventos_sinteticos.csv` - Dataset sintético de eventos.
- `futsal.db` - Base de datos SQLite con tablas `partidos` y `eventos`.

> Nota: Las carpetas `obsoletos/`, `backup/` y `venv/` no se consideran parte del flujo activo del proyecto.

## Requisitos

- Python 3.10 o superior
- Paquetes Python:
  - `streamlit`
  - `pandas`
  - `numpy`
  - `plotly`
  - `openpyxl` (para archivos `.xlsx`)

## Instalación

1. Crear y activar un entorno virtual (recomendado):

```bash
python -m venv venv
venv\Scripts\activate
```

2. Instalar dependencias:

```bash
pip install streamlit pandas numpy plotly openpyxl
```

## Uso

### Ejecutar el dashboard principal

El archivo `main_app.py` es el dashboard activo para análisis táctico y visualizaciones de cancha.

```bash
streamlit run main_app.py
```

### Generar datos sintéticos

Ejecutar el generador para crear un dataset de eventos de ejemplo:

```bash
python generar_sintetico.py
```

## Formato esperado de los archivos de eventos

El dashboard actual puede usar archivos CSV/Excel con columnas como:

- `fecha`
- `rival`
- `tipo_evento`
- `tiempo`
- `equipo`
- `jugador`
- `zona`
- `resultado`
- `tipo_tarjeta`
- `x` (coordenada horizontal)
- `y` (coordenada vertical)

## Base de datos

El proyecto utiliza `futsal.db` con estas tablas:

- `partidos`: datos de cada partido con fecha, rival y registros JSON de los eventos agregados.
- `eventos`: registros individuales de cada evento, incluyendo las coordenadas `x` y `y` para trazado táctico.

## Precisión del análisis táctico

El dashboard principal genera un mapa de calor continuo a partir de eventos posicionados en la cancha. En lugar de agrupar por bloques cuadrados, se aplica una densidad de vecindad suave para mantener precisión puntual.

- Las coordenadas se reescalan a una cancha real de 40×20 metros.
- El mapa de calor utiliza suavizado por convolución.
- El resultado ofrece un nivel de detalle cercano a una precisión de un metro cuadrado, con margen de error menor al tamaño de la pelota.

## Notas

- `main_app.py` es la entrada principal del proyecto.
- `dashboard.py` y otros scripts anteriores están en `obsoletos/` y no forman parte del flujo activo.

## Mejoras sugeridas

- Validar columnas y formatos al cargar archivos.
- Agregar filtros de fecha, rival y tipo de evento en el dashboard.
- Añadir exportación directa desde la interfaz.
- Soportar corrección manual de coordenadas antes de guardar eventos.
