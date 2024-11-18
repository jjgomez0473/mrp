import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

APP_PATH_DATA = os.getenv("APP_PATH_DATA")

# Carga el archivo excel de trabajo
def load_data(file, columns, attributes):
    df=None
    concatenated_string  = ' '.join(map(str, columns))
    try:
        df = pd.read_excel(file)
        concatenated_names = ' '.join(df.columns[:5])
        if df.shape[1] != attributes:
            raise ValueError (f"Error: El DataFrame debe tener { attributes} columnas, pero tiene { df.shape[1]}.")
        if concatenated_string != concatenated_names:
            raise ValueError ("Error: No coinciden los atributos.")
        return df
    except ValueError as e:
        st.error(e)
        df = pd.DataFrame()            
        return df
    
# Carga el archivo excel auxiliar
def load_assistant(file, sheet):   
    try:
        df = pd.read_excel(APP_PATH_DATA + file, sheet_name=sheet)
        return df
    except FileNotFoundError:
        st.error(f"El archivo '{file}' no se encontró en la ruta: {APP_PATH_DATA}")
    except PermissionError:
        st.error(f"El archivo '{file}' está abierto o no se puede acceder.")
        return None
    except Exception as e:
        st.error(f"Ocurrió un error inesperado: {e}")
        return None 

# Completar serie por material 
def material_series(df):
    df_grouped = df.groupby(["material", "year_week"], as_index=False).agg({
        "sku": lambda x: ", ".join(x.unique()),  # Concatenar los SKU únicos
        "material_need": "sum",  # Sumar las necesidades de material
        "category": "first"
        })
    df_sorted = df_grouped.sort_values(by=["material", "year_week"]).reset_index(drop=True)
    
    # Obtener la fecha mínima y máxima de release_date
    min_date = df["release_date"].min()
    max_date = df["release_date"].max()    
    
     # Obtener los años y semanas dentro del rango de fechas
    weeks = []
    current_date = min_date
    while current_date <= max_date:
        year = current_date.isocalendar().year
        week = current_date.isocalendar().week
        year_week = year * 100 + week
        # weeks.append((year, week))
        weeks.append((year_week)) 
        # Avanzar a la siguiente semana
        current_date += pd.DateOffset(weeks=1)

    # Crear un DataFrame con todas las semanas dentro del rango
    all_weeks = pd.DataFrame(weeks, columns=["year_week"])
    # Obtener materiales únicos
    materials = df_sorted["material"].unique()
    combinations = []   
    # Generar combinaciones considerando mes único para cada año
    for material in materials:
        for _, row in all_weeks.iterrows():
            combinations.append({
                "material": material,
                "year_week": row["year_week"]
                # "week": row["week"]
   
            })
            
    all_combinations = pd.DataFrame(combinations)     
    # Realizar un merge para identificar semanas faltantes
    df_completed = all_combinations.merge( df_sorted, how="left", on=["material", "year_week"]) 
    
    # Asignar 0 a material_need en las filas donde sea NaN
    df_completed["material_need"] = df_completed["material_need"].fillna(0) 
    
    # # Rellenar las otras columnas con valores de semanas anteriores o posteriores
    for column in ["sku", "category"]:
        df_completed[column] = df_completed[column].combine_first(df_completed.groupby("material")[column].transform("first"))
    
     # Calcular el acumulado de material_need por material y semana
    df_completed["need_accum"] = df_completed.groupby("material")["material_need"].cumsum() * -1
    
    return df_completed
    
# Agrupa los depósitos
def load_group_store(df):
    file_assistant = r"data_support.xlsx"
    sheet_store = "store"
    group_store = load_assistant(file_assistant, sheet_store)
    group_store["list"] = group_store["list"].str.split(",")
    exploded_group = group_store.explode('list').reset_index(drop=True)
    exploded_group.rename(columns={'list': 'store'}, inplace=True)
    exploded_group.rename(columns={'cluster': 'cluster_store'}, inplace=True)
    exploded_group.rename(columns={'name': 'name_cluster_store'}, inplace=True)    
    merged_df = pd.merge(df, exploded_group, on='store', how='left')
    return merged_df 

# Preprocesamiento de datso de stock, incorporar datos del maestro de materiales
def preprocessing_get_assistant(df):
    file_assistant = r"data_support.xlsx"
    sheet_assistant = "material"
    assistant = load_assistant(file_assistant, sheet_assistant)
    df= pd.merge(df, assistant, on="material", how='left') 
    return df

# Cargar data archivo stock
def get_data_stock(file):
    # Control de selección de archivo
    five_columns = ["COD_ART", "DES_ART", "UNIDAD", "DEPÓSITO", "EN_STOCK"]
    stock = load_data(file, five_columns,8) 
    
    if not stock.empty:
        stock= stock[["COD_ART", "DEPÓSITO", "EN_STOCK"]]
        stock.columns = ["material", "store", "stock"]
        stock["closing_date"] = None  
        stock["year_week"] = None 
        stock = stock[stock["stock"] > 0] 
        stock = load_group_store(stock)
        stock_sorted = stock.sort_values(by=["store", "material"]).reset_index(drop=True)
        return stock_sorted       
    else:
        return None
 
# Cargar data archivo consumos
def get_data_material(file):
    # Control de selección de archivo
    five_columns = ["N_RENGLON", "ACTIVO", "COD_ARTICU", "CAT", "DESCRIPCIO"]
    material = load_data(file, five_columns,20)
        
    if not material.empty:
        material= material[["COD_ARTICU", "CAT", "NECESIDAD", "FECHA_ENTR", "N_COMP"]]
        material.columns = ["material", "category", "material_need", "release_date", "sku"]
        
        material["release_date"] = pd.to_datetime(material["release_date"])
        material['sku'] = material['sku'].str.replace(r'\s+', '', regex=True)
        material['category'] = material['category'].str.strip()
        year = material["release_date"].dt.isocalendar().year
        week = material["release_date"].dt.isocalendar().week
        material['year_week'] = year * 100 + week 
        material = material[material['category'] == 'IN'] 
        
        material = material_series(material)
        
        material_sorted = material.sort_values(by=["material", "year_week"]).reset_index(drop=True)
        return material_sorted     
    else:
        return None
    
# Cargar data archivo compras    
def get_data_requirements(file):   
    five_columns = ["process_date", "order", "material", "description", "um"]
    requirements = load_data(file, five_columns,20)
    
    # Convertir la columna order_status a mayúsculas
    requirements["order_status"] = requirements["status"].str.upper()
    # Filtrar el DataFrame por order_status igual a "pedido"
    requirements = requirements[requirements["status"] == "PEDIDO"]
    return requirements

    
    