"""
Este codigo es un codigo reciclado que ya tenia de un agente en produccion, pero lo adapte para que funcione con streamlit
https://github.com/Brandon-dev314/devagent
y con el modelo gpt-40-mini, que es mas barato y rapido que gpt-4o. La idea es que el agente pueda responder preguntas sobre los costos de equipos
"""


import streamlit as st
from agente import Agente

st.set_page_config(page_title="Costos de equipos", page_icon="📊")
st.title("Consulta de costos de equipos")
st.caption("Pregunta sobre la proyeccion, el modelo o simula escenarios")

if "agente" not in st.session_state:
    st.session_state.agente = Agente(verboso=False)
    st.session_state.mensajes = []

with st.sidebar:
    st.markdown("**Ejemplos**")
    st.markdown("- cuanto costara el equipo 1 en diciembre\n"
                "- de que depende el precio del equipo 2\n"
                "- que pasa si Z sube 20%\n"
                "- que esta pasando con los commodities")
    if st.button("Reiniciar conversacion"):
        st.session_state.agente.reiniciar()
        st.session_state.mensajes = []
        st.rerun()

for msg in st.session_state.mensajes:
    with st.chat_message(msg["rol"]):
        st.write(msg["texto"])

pregunta = st.chat_input("Escribe tu pregunta")
if pregunta:
    st.session_state.mensajes.append({"rol": "user", "texto": pregunta})
    with st.chat_message("user"):
        st.write(pregunta)

    with st.chat_message("assistant"):
        with st.spinner("consultando..."):
            respuesta = st.session_state.agente.preguntar(pregunta)
        st.write(respuesta)

    st.session_state.mensajes.append({"rol": "assistant", "texto": respuesta})
