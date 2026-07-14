import pandas as pd

# Cargamos el Excel
xls = pd.ExcelFile("Camioneros_Historico.xlsx")
# Buscamos la pestaña del mapa
hoja_mapa = [s for s in xls.sheet_names if "mapa" in s.lower()][0]
df = pd.read_excel(xls, sheet_name=hoja_mapa)

print("📋 --- DIAGNÓSTICO DE COLUMNAS DEL EXCEL --- 📋\n")
for i, col in enumerate(df.columns):
    # Mostramos el índice, el nombre de la columna y los primeros 3 valores que tiene cargados
    valores = df.iloc[:, i].dropna().head(3).tolist()
    print(f"Col {i} (Letra aprox: {col}): Valores -> {valores}")