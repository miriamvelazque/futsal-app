import pandas as pd

def preparar_datos_para_app(archivo_entrada, archivo_salida):
    df = pd.read_excel(archivo_entrada)
    
    # 1. Escalar de (0-40, 0-20) a (0-100, 0-60)
    # Esto "engaña" a tu función `_reescalar_coordenadas` para que 
    # al hacer la cuenta inversa, el resultado sea el correcto.
    df['x'] = (df['x'] / 40) * 100
    df['y'] = (df['y'] / 20) * 60
    
    # 2. Redondeo
    df['x'] = df['x'].round(0)
    df['y'] = df['y'].round(0)
    
    # Guardar
    df.to_excel(archivo_salida, index=False)
    print(f"Archivo preparado para tu App: {archivo_salida}")

preparar_datos_para_app("partidos_antiguos.xlsx", "partidos_antiguos_PARA_APP.xlsx")