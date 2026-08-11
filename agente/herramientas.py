"""
Este codigo es un codigo reciclado que ya tenia de un agente en produccion, pero lo adapte para que funcione con streanlit
y con el modelo gpt-40-mini, que es mas barato y rapido que gpt-4o. La idea es que el agente pueda responder preguntas sobre los costos de equipos
"""
from tavily import TavilyClient
import os
import json
import numpy as np
import pandas as pd

MATERIAS_PRIMAS = ["Price_X", "Price_Y", "Price_Z"]


def _normalizar_equipo(nombre):
    texto = str(nombre).lower().replace(" ", "").replace("_", "")
    if "1" in texto or "uno" in texto:
        return "Price_Equipo1"
    if "2" in texto or "dos" in texto:
        return "Price_Equipo2"
    return None


def _normalizar_materia(nombre):
    texto = str(nombre).upper()
    for m in MATERIAS_PRIMAS:
        if m[-1] in texto:
            return m
    return None


def consultar_pronostico(equipo, mes=None):
    clave = _normalizar_equipo(equipo)
    if clave is None:
        return {"error": f"no reconozco el equipo '{equipo}', son Equipo1 o Equipo2"}

    tabla = pd.read_csv("Resultados/pronosticos/proyeccion_mensual.csv", index_col=0, parse_dates=True)
    tabla = tabla[tabla["equipo"] == clave]

    if mes:
        tabla = tabla[tabla.index.strftime("%Y-%m") == str(mes)[:7]]
        if tabla.empty:
            return {"error": f"no hay proyeccion para {mes}, el horizonte es de 6 meses"}

    filas = []
    for fecha, fila in tabla.iterrows():
        filas.append({"mes": fecha.strftime("%Y-%m"),
                      "mediana": round(fila["mediana"], 2),
                      "escenario_bajo_p05": round(fila["p05"], 2),
                      "escenario_alto_p95": round(fila["p95"], 2),
                      "amplitud_banda_pct": round(fila["amplitud"], 1)})

    return {"equipo": clave, "proyeccion": filas,
            "nota": "la banda es un intervalo del 90%, viene de simular las materias primas"}


def explicar_modelo(equipo):
    clave = _normalizar_equipo(equipo)
    if clave is None:
        return {"error": f"no reconozco el equipo '{equipo}'"}

    with open("Resultados/modelos/coeficientes.json") as f:
        coefi = json.load(f)[clave]

    resumen = pd.read_csv("Resultados/modelos/resumen_modelos.csv")
    fila = resumen[resumen["equipo"] == clave].iloc[0]
    backtest = pd.read_csv(f"Resultados/modelos/backtest_{clave}.csv", index_col=0, parse_dates=True)

    pesos = {}
    for materia, beta in coefi["betas"].items():
        pesos[materia] = {"elasticidad": round(beta, 4),"lectura": f"si {materia} sube 1%, el equipo sube {beta:.2f}%"}

    descartadas = [m for m in MATERIAS_PRIMAS if m not in coefi["variables"]]

    return {
        "equipo": clave,
        "variables_del_modelo": coefi["variables"],
        "variables_descartadas": descartadas,
        "pesos": pesos,
        "suma_elasticidades": round(fila["suma_elasticidades"], 3),
        "r2": round(coefi["r2"], 4),
        "error_backtest_pct": round(backtest["error_modelo"].mean(), 3),
        "error_naive_pct": round(backtest["error_naive"].mean(), 3),
        "meses_evaluados": len(backtest),
        "nota": ("el modelo es log-log, los coeficientes son elasticidades. "
                 "que sumen casi 1 significa que el precio del equipo se comporta "
                 "como una canasta ponderada de sus insumos")
    }


def simular_escenario(equipo, materia, cambio_pct):
    clave = _normalizar_equipo(equipo)
    if clave is None:
        return {"error": f"no reconozco el equipo '{equipo}'"}

    clave_materia = _normalizar_materia(materia)
    if clave_materia is None:
        return {"error": f"no reconozco la materia '{materia}', son X, Y o Z"}

    with open("Resultados/modelos/coeficientes.json") as f:
        coefi = json.load(f)[clave]

    if clave_materia not in coefi["variables"]:
        return {"equipo": clave, "materia": clave_materia, "impacto_pct": 0.0,
                "nota": (f"{clave_materia} no entro al modelo de {clave} porque no "
                         "resulto significativa, asi que moverla no cambia el precio estimado")}

    diario = pd.read_csv("Datos/procesado/panel_diario.csv", index_col=0, parse_dates=True).dropna()
    log = np.log(diario.resample("ME").mean())
    hoy = log[coefi["variables"]].iloc[-1]

    base = np.exp(coefi["const"] + sum(hoy[v] * coefi["betas"][v] for v in coefi["variables"]))
    movido = hoy.copy()
    movido[clave_materia] += np.log1p(cambio_pct / 100)
    nuevo = np.exp(coefi["const"] + sum(movido[v] * coefi["betas"][v] for v in coefi["variables"]))

    return {"equipo": clave, "materia": clave_materia, "cambio_aplicado_pct": cambio_pct,
            "precio_base": round(float(base), 2),
            "precio_escenario": round(float(nuevo), 2),
            "impacto_pct": round(float(nuevo / base - 1) * 100, 2),
            "elasticidad_usada": round(coefi["betas"][clave_materia], 4)}


def buscar_contexto_mercado(consulta):
    """
    Uso Tavily porque devuelve texto ya resumido y no HTML crudo, que es lo que
    necesita el modelo. Descarte scrapear con requests + BeautifulSoup: habria que
    mantener un parser por sitio y no aporta al caso.

    pueden leer mas en https://docs.tavily.com/sdk/javascript/reference?landing=docs.tavily.com%2Fdocs%2Fquickstart#response-3-3
    """
    clave = os.environ.get("TAVILY_API_KEY")
    if not clave:
        return {"error": "no hay TAVILY_API_KEY configurada, la busqueda externa esta apagada"}

    try:
        cliente = TavilyClient(api_key=clave)
        resultado = cliente.search(query=consulta, max_results=4, search_depth="basic")
    except Exception as e:
        return {"error": f"la busqueda fallo: {e}"}

    hallazgos = []
    for r in resultado.get("results", []):
        hallazgos.append({"titulo": r.get("title"),
                          "resumen": r.get("content", "")[:400],
                          "fuente": r.get("url")})

    return {"consulta": consulta, "hallazgos": hallazgos,
            "nota": ("esto es informacion externa, no sale del modelo estadistico. "
                     "Sirve para contextualizar el pronostico, no para corregirlo")}

DISPONIBLES = {
    "consultar_pronostico": consultar_pronostico,
    "explicar_modelo": explicar_modelo,
    "simular_escenario": simular_escenario,
    "buscar_contexto_mercado": buscar_contexto_mercado,
}


if __name__ == "__main__":
    print(json.dumps(consultar_pronostico("equipo 1", "2023-12"), indent=2, ensure_ascii=False))
    print(json.dumps(explicar_modelo("Equipo1"), indent=2, ensure_ascii=False))
    print(json.dumps(simular_escenario("equipo 2", "Z", 15), indent=2, ensure_ascii=False))
    print(json.dumps(simular_escenario("equipo 1", "Z", 15), indent=2, ensure_ascii=False))