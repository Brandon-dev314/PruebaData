import pandas as pd
import json

# historico y proyeccion en una sola tabla, con una columna que las distingue.
# power bi grafica mejor asi que uniendo dos tablas separadas
diario = pd.read_csv("Datos/procesado/panel_diario.csv", index_col=0, parse_dates=True).dropna()
mensual = diario.resample("ME").mean()

filas = []
for equipo in ["Price_Equipo1", "Price_Equipo2"]:
    for fecha, valor in mensual[equipo].items():
        filas.append({"fecha": fecha, "equipo": equipo, "tipo": "historico","valor": round(valor, 2), "p05": None, "p95": None})

proyeccion = pd.read_csv("Resultados/pronosticos/proyeccion_mensual.csv", index_col=0, parse_dates=True)
for fecha, fila in proyeccion.iterrows():
    filas.append({"fecha": fecha, "equipo": fila["equipo"], "tipo": "proyeccion","valor": round(fila["mediana"], 2),"p05": round(fila["p05"], 2), "p95": round(fila["p95"], 2)})

pd.DataFrame(filas).to_csv("Resultados/dashboard/serie_completa.csv", index=False)


with open("Resultados/modelos/coeficientes.json") as f:
    coefi = json.load(f)

contribuciones = []
for equipo, datos in coefi.items():
    for materia, beta in datos["betas"].items():
        contribuciones.append({"equipo": equipo, "materia": materia,"elasticidad": round(beta, 4),"peso_pct": round(beta / sum(datos["betas"].values()) * 100, 1)})
pd.DataFrame(contribuciones).to_csv("Resultados/dashboard/contribuciones.csv", index=False)

# los escenarios ya estan listos, solo los copio
pd.read_csv("Resultados/pronosticos/escenarios.csv").to_csv("Resultados/dashboard/escenarios.csv", index=False)

print(f"listo, tres archivos en Resultados/dashboard")