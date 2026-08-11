"""
Este codigo es un codigo reciclado que ya tenia de un agente en produccion, pero lo adapte para que funcione con streamlit
https://github.com/Brandon-dev314/devagent
y con el modelo gpt-40-mini, que es mas barato y rapido que gpt-4o. La idea es que el agente pueda responder preguntas sobre los costos de equipos
"""


import os
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

import herramientas

load_dotenv()

MODELO = "gpt-4o-mini"
MAX_VUELTAS = 4   
ESQUEMAS = json.loads((Path(__file__).parent / "esquema.json").read_text(encoding="utf-8"))

INSTRUCCIONES = """Eres un analista presentando los resultados de un estudio de costos
de equipos para un proyecto de construccion.

Reglas:
- Toda cifra que des tiene que venir de una herramienta, nunca la inventes.
- El pronostico siempre va con su banda, un numero solo engania.
- Distingue lo que sale del modelo de lo que sale de la busqueda externa.
- Si preguntan algo que las herramientas no cubren, dilo en vez de improvisar.
- Responde en espaniol, breve, sin tecnicismos innecesarios.
"""


class Agente:
    def __init__(self, verboso=True):
        self.cliente = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.verboso = verboso
        self.historial = [{"role": "system", "content": INSTRUCCIONES}]

    def preguntar(self, texto):
        self.historial.append({"role": "user", "content": texto})

        for vuelta in range(MAX_VUELTAS):
            respuesta = self.cliente.chat.completions.create(
                model=MODELO,
                messages=self.historial,
                tools=ESQUEMAS,
            ).choices[0].message

            self.historial.append(respuesta)

            if not respuesta.tool_calls:
                return respuesta.content

            for llamada in respuesta.tool_calls:
                nombre = llamada.function.name
                argumentos = json.loads(llamada.function.arguments)

                if self.verboso:
                    print(f"   [usa {nombre} con {argumentos}]")

                funcion = herramientas.DISPONIBLES.get(nombre)
                if funcion is None:
                    salida = {"error": f"no existe la herramienta {nombre}"}
                else:
                    try:
                        salida = funcion(**argumentos)
                    except Exception as e:
                        # si la herramienta truena se lo digo al modelo en vez de tirar
                        # el programa, asi puede reintentar con otros argumentos
                        salida = {"error": f"{type(e).__name__}: {e}"}

                self.historial.append({
                    "role": "tool",
                    "tool_call_id": llamada.id,
                    "content": json.dumps(salida, ensure_ascii=False, default=str),
                })

        return "me quede sin vueltas, la pregunta requiere demasiados pasos"

    def reiniciar(self):
        self.historial = [{"role": "system", "content": INSTRUCCIONES}]
