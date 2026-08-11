import pandas as pd
ARCHIVOS = {
    "X": dict(archivo = "X.csv", sep = ",", decimal= ".", dayfirst=False, encoding ="utf-8"),
    "Y": dict(archivo = "Y.csv", sep= ";", decimal = ",", dayfirst= True,encoding ="utf-8-sig"),
    "Z": dict(archivo= "Z.csv", sep=",", decimal= ".", dayfirst=False, encoding ="utf-8")
}

max_fill = 5

def leer_datos(nombre, cfg):
    df = pd.read_csv(f"Datos/{cfg['archivo']}", sep=cfg["sep"], encoding=cfg["encoding"])
    df.columns = [c.strip().lstrip("\ufeff") for c in df.columns]

    if not {"Date", "Price"}.issubset(df.columns):
        raise ValueError(f"El archivo {cfg['archivo']} no contiene las columnas requeridas")
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=cfg["dayfirst"], errors = "coerce")
    precio = df["Price"]
    if cfg["decimal"] == ",":
        precio = precio.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex= False)
    df[nombre]=pd.to_numeric(precio, errors="coerce")

    tam = len(df)
    df = df.dropna(subset = ["Date", nombre]).drop_duplicates("Date").sort_values("Date")
    desc = tam - len(df)
    if desc:
        print(f"se elimnaron {desc} filas del archivo {cfg['archivo']}")

    return df[["Date", nombre]].set_index("Date")

def leer_historico():
    df = pd.read_csv("Datos/historico_equipos.csv")
    df["Date"]= pd.to_datetime(df["Date"])
    df= df.dropna(subset = ["Date"]).drop_duplicates("Date").sort_values("Date")
    print(f"\nSe leyeron {len(df)} filas del archivo historico_equipos.csv")
    return df.set_index("Date")

def validar_datos(historico, materias):
    print("\nvalidando datos encontrados")
    consistente = True
    for i in ARCHIVOS:
        par = historico[[f"Price_{i}"]].join(materias[i], how="inner")
        dif = (par[f"Price_{i}"] - par[i]).abs()
        n_diferencias = int((dif > 1e-6).sum())
        consistente = consistente and n_diferencias == 0
        print(f"{n_diferencias} diferencias encontradas en {i} con historico_precios.csv")
    print("\nvalidacion finalizada" if consistente else "validacion fallida, revisar diferencias")
    return consistente

def revisar_estancamiento(panel):
    reporte=[]
    for i in panel.columns:
        c = panel[i].dropna()
        rachas = c.groupby((c != c.shift()).cumsum()).size()
        no_hay_cambios = (c.diff() == 0).mean() * 100
        reporte.append({"serie": i, "n": len(c), "max_racha": rachas.max(), "no_haycambios": round(no_hay_cambios, 1)})

    suposicion = [a["serie"] for a in reporte if a["no_haycambios"]> 20]
    if suposicion:
        print(f"\nSe encontraron series con estancamiento: {', '.join(suposicion)}")
    return pd.DataFrame(reporte)

print("\nleyendo datos de precios")

series =[leer_datos(nombre, cfg) for nombre, cfg in ARCHIVOS.items()]
material = pd.concat(series, axis=1, sort=True)

equipos = leer_historico()
validar_datos(equipos, material)

panel= pd.concat([material, equipos[["Price_Equipo1", "Price_Equipo2"]]], axis =1)
panel.columns = ["Price_X", "Price_Y", "Price_Z", "Price_Equipo1", "Price_Equipo2"]
panel=  panel.sort_index()

print(f"\nfechas duplicadas en el panel: {int(panel.index.duplicated().sum())}")
inicio = panel[["Price_Z", "Price_Equipo1"]].dropna(how="all").index.min()
fin = panel[["Price_Equipo2", "Price_Equipo1"]].dropna(how="all").index.max()
print(f"\nventana de modelado: {inicio.date()} a {fin.date()}")
futuro=panel.loc[panel.index>fin, ["Price_X", "Price_Y", "Price_Z"]].dropna(how = "all")
if len(futuro):
    print(f"\nse encontraron {len(futuro)} filas de datos futuros, desde {futuro.index.min().date()} a {futuro.index.max().date()}")

panel = panel.loc[inicio:fin]
for col in panel.columns:
    serie = panel[col]
    print(f"{col}: {serie.notna().sum()} obs, {serie.isna().sum()} nulos,"f"de {serie.first_valid_index().date()} a {serie.last_valid_index().date()}")

calendario = pd.bdate_range(start = inicio, end=fin)
panel = panel.reindex(calendario)
vacias = int(panel.isna().sum().sum())
panel = panel.ffill(limit = max_fill)
print(f"\ncalendario: {len(calendario)} dias habiles, {vacias} celdas vacias, ")
calidad= revisar_estancamiento(panel)

panel.index.name = "Date"
panel.to_csv("Datos/procesado/panel_diario.csv")
calidad.to_csv("Datos/procesado/reporte_calidad.csv", index = False)
print(f"\nguardado panel_diario.csv con {panel.shape[0]} filas y {panel.shape[1]} columnas")
print(panel.describe().T[["count", "mean", "std", "min", "max"]])

