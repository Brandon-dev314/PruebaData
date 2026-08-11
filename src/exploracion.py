import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, kpss
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.stats.outliers_influence import variance_inflation_factor

MATERIAS_PRIMAS = ["Price_X","Price_Y","Price_Z"]
EQUIPOS=["Price_Equipo1","Price_Equipo2"]
REZAGO=3

def leer_panel():
    df=pd.read_csv("Datos/procesado/panel_diario.csv", index_col = 0, parse_dates=True)
    df=df.dropna()
    print(f"\nPanel diario: {df.shape[0]} observaciones de {df.shape[1]} variables")
    return df

def mensual(diario):
    mensual= diario.resample("ME").mean()
    print(f"\npanel mensual: {mensual.shape[0]}")
    return mensual
def estacionariedad(df, etiqueta):
    filas=[]
    for i in df.columns:
        serie=df[i].dropna()
        adf=adfuller(serie, autolag="AIC")
        kps= kpss(serie, regression="c", nlags="auto")
        estacionario=adf[1]<0.05 and kps[1]>0.05
        filas.append({"serie":i, "transformacion":etiqueta, "adf": round(adf[1], 4), "kps": round(kps[1],4), "estacionario": estacionario})
        print(f"\n{i} {etiqueta} ADF: {adf[1]:.4f} KPSS: {kps[1]:.4f} estacionario: {estacionario}")
    return pd.DataFrame(filas)

def correlaciones(niveles, retornos):
    for i in EQUIPOS:
        for p in MATERIAS_PRIMAS:
            correlacion1 = niveles[p].corr(niveles[i])
            correlacion2=retornos[p].corr(retornos[i])
            print(f"\n{p:<10} niveles={correlacion1:+.3f} retornos={correlacion2:+.3f}")
    return niveles.corr(), retornos.corr()

def correlacion_cruzada(retornos):
    print(f"\ncorrelacion cruzada hasta {REZAGO} meses de rezago")
    filas = []
    for i in EQUIPOS:
        for p in MATERIAS_PRIMAS:
            correlaciones= {k: retornos[p].shift(k).corr(retornos[i]) for k in range(REZAGO +1)}
            mejo=max(correlaciones, key=lambda k:abs(correlaciones[k]))
            for k, c in correlaciones.items():
                filas.append({"equipo": i, "precio": p, "rezago": k, "corr": round(c,4)})
            print(f"\n{p:<10} mejor k ={mejo}")
    return pd.DataFrame(filas)

def checar_colinealidad(retornos):
    X = sm.add_constant(retornos[MATERIAS_PRIMAS])
    valores ={c: round(variance_inflation_factor(X.values, i), 2) for i,c in enumerate(X.columns) if c!="const"}
    print(f"Valores: {valores}")
    if max(valores.values()) > 5:
        print("\nhay colinealidad, los coeficientes individuales no son confiables")
    else:
        print("sin colinealidad relevante, las tres pueden entrar juntas")
    return valores

def regresion_exploratoria(retornos):
    filas= []
    X = sm.add_constant(retornos[MATERIAS_PRIMAS])
    for i in EQUIPOS:
        modelo = sm.OLS(retornos[i], X).fit()
        print(f"\n{i} R Cuadrada={modelo.rsquared:.4f} R={modelo.rsquared_adj:.4f}")
        for p in MATERIAS_PRIMAS:
            significativa = modelo.pvalues[p] < 0.05
            filas.append({"equipo": i, "precio": p,"coef": round(modelo.params[p], 4),"t": round(modelo.tvalues[p], 2),"p": modelo.pvalues[p],"significativa": significativa,"r2": round(modelo.rsquared, 4)})
            print(f"coef={modelo.params[p]:+.4f}  t={modelo.tvalues[p]:+7.2f}, p={modelo.pvalues[p]:.2e}  {'SI' if significativa else 'no'}")
        relevantes = [f["precio"] for f in filas if f["equipo"] == i and f["significativa"]]
        print(f"\nsignificativas: {', '.join(relevantes) if relevantes else 'ninguna'}")
    return pd.DataFrame(filas)   

def graficar(mensual, retornos):
    fig, ejes = plt.subplots(2,1, figsize=(11,7), sharex = True)
    for p in MATERIAS_PRIMAS:
        ejes[0].plot(mensual.index, mensual[p] / mensual[p].iloc[0]*100, label=p)
    ejes[0].set_title("Precios")
    ejes[0].legend(fontsize=8)
    for i in EQUIPOS:
        ejes[1].plot(mensual.index, mensual[i]/mensual[i].iloc[0]*100, label=i)
    ejes[1].set_title("Equipos")
    ejes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig("Resultados/figuras/normalizadas.png", dpi=120)
    plt.close()
    fig, ejes=plt.subplots(1,2,figsize=(11,4))
    for eje, i, p in zip(ejes, EQUIPOS, ["Price_Y", "Price_Z"]):
        eje.scatter(retornos[p], retornos[i], s=12, alpha=0.6)
        eje.set_xlabel(f"log-retorno {p}")
        eje.set_ylabel(f"log-retorno {i}")
        eje.set_title(f"{i} vs {p}  (r={retornos[p].corr(retornos[i]):.3f})")
    fig.tight_layout()
    fig.savefig("Resultados/figuras/dispersion.png", dpi=120)
    plt.close(fig)
    print(f"\nfiguras guardadas en Resultados/figuras")



diario = leer_panel()
mes = mensual(diario)
retornos = np.log(mes).diff().dropna()

est_niveles = estacionariedad(mes, "niveles")
est_retornos = estacionariedad(retornos, "log-retornos")

correlaciones(mes, retornos)
cruzada = correlacion_cruzada(retornos)
checar_colinealidad(retornos)
resultados = regresion_exploratoria(retornos)
graficar(mes, retornos)

mes.to_csv("Datos/procesado/panel_mensual.csv")
retornos.to_csv("Datos/procesado/retornos_mensual.csv")
pd.concat([est_niveles, est_retornos]).to_csv("Datos/procesado/estacionariedad.csv", index=False)
cruzada.to_csv("Datos/procesado/correlacion_cruzada.csv", index=False)
resultados.to_csv("Datos/procesado/regresion_exploratoria.csv", index=False)
print("resultados guardados en Datos/procesado")




