import streamlit as st
import pandas as pd
from helper import get_data_stock, preprocessing_get_assistant

st.set_page_config(
        page_title="Stock",  # Título para esta página
        page_icon= "images/roles.png"  # Icono para esta página
    )

st.header(f':blue[Datos stock]')

file_stock = st.file_uploader("Please upload an xls, xlsx", type=["xls","xlsx"])  
if file_stock:
    data_stock = preprocessing_get_assistant(get_data_stock(file_stock))
    
    # Filtros
    c1, c2 = st.columns([1,2],vertical_alignment="top")
    categories = data_stock['category'].unique()    
    category_selected = c1.selectbox("Selecciona una categoría",
                                    categories,
                                    index=None)
    # Filtrar por grupo de depositos 
    if category_selected:
        data_stock_filtrado = data_stock[data_stock['category'] == category_selected]
        stores = data_stock_filtrado['name_cluster_store'].unique()
        store_selected = c2.multiselect("Selecciona un grupo de depositos:",
                                        stores,
                                        default=stores)
        if store_selected:
            data_stock_filtrado = data_stock_filtrado[data_stock_filtrado["name_cluster_store"].isin(store_selected)]
        else:
             data_stock_filtrado = data_stock_filtrado[data_stock_filtrado["name_cluster_store"].isin(store_selected)]
             
        clusters = data_stock_filtrado['cluster'].unique() 
        cluster_selected = c1.selectbox("Selecciona un grupo",
                                    clusters,
                                    index=None)
        if cluster_selected:
            data_stock_filtrado = data_stock_filtrado[data_stock_filtrado['cluster'] == cluster_selected]
           
    else:
         data_stock_filtrado = data_stock        
     
    st.write(data_stock_filtrado)