import streamlit as st
import pandas as pd
from helper import get_data_material, preprocessing_get_assistant

st.set_page_config(
        page_title="Material",  # Título para esta página
        page_icon= "images/roles.png"  # Icono para esta página 
        )

st.header(f':blue[Consumos]')

file_material = st.file_uploader("Please upload an xls, xlsx", type=["xls","xlsx"]) 
if file_material:
    data_material = preprocessing_get_assistant(get_data_material(file_material))            
    st.write(data_material)
