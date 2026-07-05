import sqlite3
import pandas as pd

# Conectar a la base
conn = sqlite3.connect("futsal.db")

# Leer todos los eventos cargados (formato útil para dashboards)
df = pd.read_sql("SELECT * FROM eventos ORDER BY fecha, rival, tipo_evento", conn)

# Mostrar en consola
print(df)

# Exportar a CSV para abrir en Excel
df.to_csv("eventos_reales.csv", index=False)

conn.close()
