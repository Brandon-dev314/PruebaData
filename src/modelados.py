from statsmodels.tsa.stattools import adfuller
import json
import numpy as np
import pandas as pd
from statsmodels.stats.stattools import durbin_watson
from statsmodels.stats.diagnostic import acorr_ljungbox
import matplotlib.pyplot as plt
import statsmodels.api as sm

MATERIAS = ["Price_X", "Price_Y", "Price_Z"]
EQUIPOS = ["Price_Equipo1", "Price_Equipo2"]
INICIO_BACKTEST = 60  
ALPHA = 0.05

def leer_datos_mensuales():
    diario = pd.read_csv("Datos/procesado/panel_diario.csv", index_col=0, parse_dates=True).dropna()
    mes = diario.resample("ME").mean()
    print(f"meses minimo de {mes.index.min().date()} a {mes.index.max().date()}")
    return np.log(mes)

def diagnostico(res, eti):
    durbin_w = durbin_watson(res)
    rho=pd.Series(res).autocorr(1)
    lb=acorr_ljungbox(res, lags=[12], return_df=True)["lb_pvalue"].iloc[0]
    print(f"{eti}: DW={durbin_w:.3f} rho1={rho:.3f} LjungBox(12) p={lb:.4f}")
    if rho < -0.35:
        print("rho cerca de -0.5 es sobrediferenciacion")
    #hola, redondeo lo hago armo cuando creo a diccionario para el reporte
    #return round(durbin_w,3), round(rho,3), round(lb,4)
    return durbin_w, rho, lb

def comparar_datos(log):
    retorno = log.diff().dropna()
    reporte= []

    for i in EQUIPOS:
        print(i)
        #no me sirve porque solo quita el equipo actual, por lo cual se necesita saber qué materias primas determinan cada equipo
        #modelo = sm.OLS(retorno[i], sm.add_constant(retorno.drop(columns=i))).fit() 
        #probando con documentacion encontre que: sm.OLS(retorno[i], sm.add_constant(retorno[MATERIAS])) sirve para estos casos
        modelo = sm.OLS(retorno[i], sm.add_constant(retorno[MATERIAS])).fit()

        print(f"las diferencias, de r2: {modelo.rsquared:.3f}")

        durbin_dif,autocorr_dif,ljungbox_dif= diagnostico(modelo.resid, "diferencias")

        #model_nivel= sm.OLS(log[i], sm.add_constant(log.drop(columns=i))).fit()
        
        model_nivel= sm.OLS(log[i], sm.add_constant(log[MATERIAS])).fit()
        #print(f"respecto a los niveles de r2: {model_nivel.rsquared:.3f} y para p-values: {model_nivel.pvalues[1]}")
        
        print(f"respecto a los niveles de r2: {model_nivel.rsquared:.3f}")
        durbin_nivel,autocorr_nivel,ljungbox_nivel= diagnostico(model_nivel.resid, "niveles")

        #p_integracion=adfuller(log[i], autolog="AIC")[1]
        p_integracion = adfuller(model_nivel.resid, autolag="AIC")[1]
        if p_integracion < ALPHA: 
            print(f"hay cointegracion p={p_integracion:.4f}")
        else:
            print(f"no hay cointegracion p={p_integracion:.4f}")
        dic = {}

        dic["equipo"] = i
        dic["r2_diferencias"] = round(modelo.rsquared, 3)
        dic["r2_niveles"] = round(model_nivel.rsquared, 3)
        dic["durbin_niveles"]= round(durbin_nivel, 3)
        dic["durbin_diferencias"] = round(durbin_dif, 3)
        dic["autocorr_diferencias"]= round(autocorr_dif, 3)
        dic["ljungbox_diferencias"]=round(ljungbox_dif, 4)
        dic["autocorr_niveles"] = round(autocorr_nivel, 3)
        dic["ljungbox_niveles"] = round(ljungbox_nivel, 4)
        dic["adf_residuos"]= p_integracion
        dic["cointegrado"]= p_integracion < ALPHA

        reporte.append(dic)
    return pd.DataFrame(reporte)

def ajustar_modelo(log, equipo):
    modelo= sm.OLS(log[equipo], sm.add_constant(log[MATERIAS])).fit()
    usado= [m for m in MATERIAS if modelo.pvalues[m] < ALPHA]
    for m in MATERIAS:
        estado="se usa" if m in usado else "no se usa"
        print(f"valor de : {m}, se queda\nviendo los valores de p-values: {modelo.pvalues[m]:.2e}, t: {modelo.tvalues[m]:.2f}, {estado}")
    modelo_f= sm.OLS(log[equipo], sm.add_constant(log[usado])).fit()
    sumar_los_modelos= modelo_f.params[usado].sum()
    print(f"la suma de las elasticidades es: {sumar_los_modelos:.2f}")
    if abs(sumar_los_modelos-1)< ALPHA:
        print("la suma cerca de 1 significa que el equipo es una canasta ponderada de insumos")
    return modelo_f, usado

def back_test(log, equipo, var):
    """
    Una de las primeras pruebas use ventana = 60, MAPE 0.336% contra 0.331% de la expansiva
    prácticamente idéntico. Eso dice que los coeficientes son estables, que es coherente con que la relación sea una identidad de costos y no un ajuste que se degrada. Con empate, 
    gana la expansiva porque usa toda la información disponible.
    
    VENTANA = 60
    for mes in range(VENTANA, len(log)):
    entrena = log.iloc[mes - VENTANA:mes]  
    modelo = sm.OLS(entrena[equipo], sm.add_constant(entrena[var])).fit()
    """
    filas = []
    for mes in range(INICIO_BACKTEST, len(log)):
        entrena = log.iloc[:mes]
        modelo = sm.OLS(entrena[equipo], sm.add_constant(entrena[var])).fit()
        materias_mes = np.r_[1.0, log[var].iloc[mes].values]
        filas.append({"fecha": log.index[mes],"real": np.exp(log[equipo].iloc[mes]),"prediccion": np.exp(modelo.params.values @ materias_mes),"naive": np.exp(log[equipo].iloc[mes - 1])})

    resultados = pd.DataFrame(filas).set_index("fecha")
    resultados["error_modelo"] = (resultados["prediccion"] / resultados["real"] - 1).abs() * 100
    resultados["error_naive"] = (resultados["naive"] / resultados["real"] - 1).abs() * 100

    error = resultados["error_modelo"].mean()
    error_naive = resultados["error_naive"].mean()
    rmse = np.sqrt(((resultados["prediccion"] - resultados["real"]) ** 2).mean())
    print(f"{len(resultados)} meses evaluados")
    print(f" mape {error:.3f}%, naive {error_naive:.3f}%, rmse {rmse:.2f}")
    print(f"la mejora sobre naive es de: {error_naive/error:.2f} veces")

    figura, ejes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)

    ejes[0].plot(resultados.index,resultados["real"], label="real", lw=1.4)
    ejes[0].plot(resultados.index,resultados["prediccion"], label="modelo", ls="--", lw=1.1)
    ejes[0].plot(resultados.index,resultados["naive"], label="naive", lw=0.8, alpha=0.5)
    ejes[0].set_title(f"Backtest de {equipo} usando {', '.join(var)}")
    #observe que por sharex=true no hace falta poner el xlabel pero lo comento
    #ejes[0].set_xlabel("Fecha") | ignorar
    ejes[0].set_ylabel("Precio")
    ejes[0].legend(fontsize=8)
    ejes[0].grid(alpha=0.3)

    acumulado = (resultados["prediccion"] - resultados["real"]).cumsum()
    ejes[1].plot(acumulado.index, acumulado, label="error acumulado", color="tab:orange")
    ejes[1].axhline(0, color="red", linestyle="--", lw=0.8)
    ejes[1].set_ylabel("Error acumulado")
    #ejes[1].set_title(f"Error acumulado de {equipo}") | ignorar
    ejes[1].set_xlabel("Fecha")
    ejes[1].legend(fontsize=8)
    ejes[1].grid(alpha=0.3)

    figura.tight_layout()
    figura.savefig(f"Resultados/figuras/backtest_{equipo}.png", dpi=120)
    plt.close(figura)

    return resultados

def graficar_diagn(modelo, equipo):
    residuos = modelo.resid
    figura, ejes = plt.subplots(1, 3, figsize=(13, 3.5))
    ejes[0].plot(residuos.index, residuos, lw=0.9)
    ejes[0].axhline(0, color="black", lw=0.6)
    ejes[0].set_title(f"Residuos {equipo}")
    ejes[1].hist(residuos, bins=30)
    ejes[1].set_title("Distribucion")
    pd.plotting.autocorrelation_plot(residuos, ax=ejes[2])
    ejes[2].set_xlim(0, 24)
    ejes[2].set_title("Autocorrelacion")
    figura.tight_layout()
    figura.savefig(f"Resultados/figuras/residuos_{equipo}.png", dpi=120)
    plt.close(figura)


logaritmos = leer_datos_mensuales()
especificacion_de_datos = comparar_datos(logaritmos)
especificacion_de_datos.to_csv("especificacion.csv", index=False)

r= []
coefi= {}

for i in EQUIPOS:
    modelo, usadas = ajustar_modelo(logaritmos, i)
    graficar_diagn(modelo, i)

    coefi[i] = {"variables": usadas,"const": float(modelo.params["const"]),"betas": {materia: float(modelo.params[materia]) for materia in usadas},
            "r2": float(modelo.rsquared),
            "sigma_residuos": float(modelo.resid.std()),
        }

    resultados = back_test(logaritmos, i, usadas)
    resultados.to_csv(f"Resultados/modelos/backtest_{i}.csv")

    r.append({"equipo": i,"variables": ", ".join(usadas),"r2": round(modelo.rsquared, 4),"suma_elasticidades": round(modelo.params[usadas].sum(), 3),"error_modelo": round(resultados["error_modelo"].mean(), 4),
              "error_naive": round(resultados["error_naive"].mean(), 4)})

pd.DataFrame(r).to_csv("Resultados/modelos/resumen_modelos.csv", index=False)
with open("Resultados/modelos/coeficientes.json", "w") as f:
    json.dump(coefi, f, indent=2)

print("listo, todo en Resultados/modelos")