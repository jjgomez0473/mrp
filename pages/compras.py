import streamlit as st
import pandas as pd
from helper import get_data_requirements


st.set_page_config(
        page_title="Compras",  # Título para esta página
        page_icon= "images/roles.png"  # Icono para esta página 
        )

st.header(f':blue[compras]')

file_compras = st.file_uploader("Please upload an xls, xlsx", type=["xls","xlsx"])  
if file_compras:
    data_compras = get_data_requirements(file_compras)
    st.write(data_compras)