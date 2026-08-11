import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm

MATERIAS_PRIMAS = ["Price_X", "Price_Y", "Price_Z"]
EQUIPOS = ["Price_Equipo1", "Price_Equipo2"]
HORIZONTE = 6
SIMULACIONES = 5000
SEMILLA = 42


def leer_todo():
    diario = pd.read_csv("Datos/procesado/panel_diario.csv", index_col=0, parse_dates=True).dropna()
    log = np.log(diario.resample("ME").mean())
    with open("Resultados/modelos/coeficientes.json") as f:
        coefi = json.load(f)
    print(f"cargue {len(log)} meses, el ultimo dato de equipos es de {log.index[-1].date()}")
    print(f"proyecto {HORIZONTE} meses hacia adelante con {SIMULACIONES} simulaciones\n")
    return log, coefi


def modelar_materias(log):
    """
    Descarte el random walk puro (retorno = ruido). Los log-retornos de las tres
    materias traen autocorrelacion de primer orden entre 0.24 y 0.42, o sea que un
    mes que sube arrastra algo al siguiente. Con RW puro esa inercia se pierde.
    """
    retorno = log[MATERIAS_PRIMAS].diff().dropna()
    parametros = {}
    residuos = {}

    print("ajuste un AR(1) a los retornos de cada materia:")
    for m in MATERIAS_PRIMAS:
        y = retorno[m].iloc[1:]
        x = sm.add_constant(retorno[m].shift(1).iloc[1:])
        modelo = sm.OLS(y, x).fit()
        constante = modelo.params.iloc[0]
        phi = modelo.params.iloc[1]
        parametros[m] = {"c": constante, "phi": phi}
        residuos[m] = modelo.resid

        deriva = constante / (1 - phi) * 12 * 100
        volatilidad = modelo.resid.std() * np.sqrt(12) * 100
        print(f"   {m}: phi de {phi:.3f}, con deriva anual de {deriva:+.2f}% "
              f"y volatilidad anual de {volatilidad:.1f}%")
    return parametros, pd.DataFrame(residuos).dropna()


def simular(log, parametros, residuos, generador):
    nivel_inicial = log[MATERIAS_PRIMAS].iloc[-1].values
    retorno_inicial = log[MATERIAS_PRIMAS].diff().iloc[-1].values
    constantes = np.array([parametros[m]["c"] for m in MATERIAS_PRIMAS])
    phis = np.array([parametros[m]["phi"] for m in MATERIAS_PRIMAS])
    ruido = residuos.values

    caminos = np.zeros((SIMULACIONES, HORIZONTE, len(MATERIAS_PRIMAS)))
    for s in range(SIMULACIONES):
        nivel = nivel_inicial.copy()
        retorno = retorno_inicial.copy()
        sorteo = generador.integers(0, len(ruido), HORIZONTE)
        for h in range(HORIZONTE):
            retorno = constantes + phis * retorno + ruido[sorteo[h]]
            nivel = nivel + retorno
            caminos[s, h] = nivel

    print(f"simule {SIMULACIONES} trayectorias de materias primas a {HORIZONTE} meses\n")
    return caminos


def proyectar(log, coefi, equipo, caminos, generador):
    variables = coefi[equipo]["variables"]
    posiciones = [MATERIAS_PRIMAS.index(v) for v in variables]

    modelo = sm.OLS(log[equipo], sm.add_constant(log[variables])).fit()
    betas = generador.multivariate_normal(modelo.params.values,modelo.cov_params().values,SIMULACIONES)
    sigma = modelo.resid.std()

    simulado = np.zeros((SIMULACIONES, HORIZONTE))
    for h in range(HORIZONTE):
        x = np.column_stack([np.ones(SIMULACIONES), caminos[:, h, posiciones]])
        simulado[:, h] = np.exp((betas * x).sum(axis=1) + generador.normal(0, sigma, SIMULACIONES))

    fechas = pd.date_range(log.index[-1] + pd.offsets.MonthEnd(1), periods=HORIZONTE, freq="ME")
    proyeccion = pd.DataFrame({"fecha": fechas,"p05": np.percentile(simulado, 5, axis=0),"p25": np.percentile(simulado, 25, axis=0),"mediana": np.percentile(simulado, 50, axis=0),
        "p75": np.percentile(simulado, 75, axis=0),
        "p95": np.percentile(simulado, 95, axis=0)}).set_index("fecha")
    proyeccion["amplitud"] = (proyeccion["p95"] - proyeccion["p05"]) / proyeccion["mediana"] * 100

    ultimo = float(np.exp(log[equipo].iloc[-1]))
    print(f"{equipo}, el ultimo precio observado fue de {ultimo:.2f}")
    print(f"   se modela con {' y '.join(variables)}")
    for fecha, fila in proyeccion.iterrows():
        print(f"   {fecha.strftime('%Y-%m')}: la mediana queda en {fila['mediana']:.2f} y el 90% de los casos cae entre {fila['p05']:.2f} y {fila['p95']:.2f} "
              f"(banda de {fila['amplitud']:.1f}%)")
    print()
    return proyeccion


def sensibilidad(log, coefi, equipo):
    # como el modelo es log-log el efecto de un choque es la elasticidad, pero en
    # pesos es lo que le sirve a alguien que esta armando un presupuesto
    variables = coefi[equipo]["variables"]
    modelo = sm.OLS(log[equipo], sm.add_constant(log[variables])).fit()
    hoy = log[variables].iloc[-1]
    base = float(np.exp(modelo.params.iloc[0] + (hoy * modelo.params[variables]).sum()))

    filas = []
    print(f"que pasa si una materia se mueve, partiendo de {base:.2f}:")
    for v in variables:
        for choque in (-0.20, -0.10, 0.10, 0.20):
            movido = hoy.copy()
            movido[v] += np.log1p(choque)
            precio = float(np.exp(modelo.params.iloc[0] + (movido * modelo.params[variables]).sum()))
            impacto = (precio / base - 1) * 100
            filas.append({"equipo": equipo, "materia": v, "choque": choque * 100,"precio": round(precio, 2), "impacto": round(impacto, 2)})
            if choque == 0.20:
                print(f"si {v} sube 20%, el equipo se va a {precio:.2f}, o sea {impacto:+.2f}%")
    print()
    return pd.DataFrame(filas)


def graficar(log, equipo, proyeccion):
    historico = np.exp(log[equipo]).iloc[-36:]
    figura, eje = plt.subplots(figsize=(11, 4.5))
    eje.plot(historico.index, historico.values, label="historico", lw=1.4)
    eje.plot(proyeccion.index, proyeccion["mediana"], label="mediana", ls="--", lw=1.6)
    eje.fill_between(proyeccion.index, proyeccion["p05"], proyeccion["p95"], alpha=0.2, label="90%")
    eje.fill_between(proyeccion.index, proyeccion["p25"], proyeccion["p75"], alpha=0.35, label="50%")
    eje.set_title(f"Proyeccion de {equipo} a {HORIZONTE} meses")
    eje.set_ylabel("Precio")
    eje.legend(fontsize=8)
    eje.grid(alpha=0.3)
    figura.tight_layout()
    figura.savefig(f"Resultados/figuras/pronostico_{equipo}.png", dpi=120)
    plt.close(figura)


generador = np.random.default_rng(SEMILLA)
logaritmos, coeficientes = leer_todo()

parametros, residuos = modelar_materias(logaritmos)
caminos = simular(logaritmos, parametros, residuos, generador)

proyecciones = []
choques = []
for equipo in EQUIPOS:
    proyeccion = proyectar(logaritmos, coeficientes, equipo, caminos, generador)
    graficar(logaritmos, equipo, proyeccion)
    proyeccion.insert(0, "equipo", equipo)
    proyecciones.append(proyeccion)
    choques.append(sensibilidad(logaritmos, coeficientes, equipo))

pd.concat(proyecciones).to_csv(PRONOSTICOS / "proyeccion_mensual.csv")
pd.concat(choques).to_csv(PRONOSTICOS / "escenarios.csv", index=False)
print(f"listo, la proyeccion y los escenarios quedaron en {PRONOSTICOS}")