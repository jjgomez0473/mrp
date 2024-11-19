import streamlit as st
import pandas as pd
from helper import get_data_stock, get_data_material, get_data_requirements, preprocessing_get_assistant
from datetime import datetime, date
from io import BytesIO

st.set_page_config(
        page_title="MRP",  # Título para esta página
        page_icon= "images/roles.png"  # Icono para esta página
    )

def calculate_order_date(row):
    # Obtener la fecha inicial de la semana analizada
    need_week = row["year_week"]
    year = need_week // 100
    week = need_week % 100    
    # Calcular el primer día de la semana (lunes)
    first_day_of_week = datetime.strptime(f'{year}-W{week}-1', "%G-W%V-%u")
    
    # Sumar el lead time
    lead_time = row['suppier_lead_time']  # Asegúrate de que esta columna esté en tu DataFrame
    if pd.isna(lead_time):
        # Si lead_time es NaN, puedes decidir qué hacer
        # Por ejemplo, retornar None o un mensaje
        return None  # O podrías asignar un valor predeterminado
    order_date = first_day_of_week + pd.Timedelta(days=lead_time)
    
    return order_date

def adjust_orders_recursive(df, material):
    # Filtrar el grupo de materiales
    group = df[df['material'] == material]
    
    # Verificar si hay valores negativos en stock_final
    negative_indices = group[group['stock_final'] < 0].index
    
    if not negative_indices.empty:
        # Actualizar order_quantity para el primer negativo
        first_negative_index = negative_indices[0]
        stock_final_value = df.loc[first_negative_index, 'stock_final']
        
        # Obtener el lote mínimo
        lote_minimo = df.loc[first_negative_index, 'supplier_min_lot']  # Asegúrate de que esta columna esté en tu DataFrame
                
        if pd.notna(lote_minimo):
            adjustment = lote_minimo
        else:
            adjustment = stock_final_value * -1
            # Agregar nota sobre la falta de lote mínimo
            df.at[first_negative_index, 'notes'] += "No se tiene lote mínimo. Ajuste basado en stock final. "

        df.at[first_negative_index, 'quantity'] += adjustment
        
        # Buscar si hay registros posteriores con order_quantity para este material
        future_orders = df[(df['material'] == material) & 
                           (df.index > first_negative_index) & 
                           (df['quantity'] > 0)]
        
        if not future_orders.empty:
            total_future_orders = future_orders['quantity'].sum()
            # Sugerir adelantar el pedido en base a las órdenes futuras
            suggestion = f"Sugerencia: Adelantar pedido de {material}. Total de órdenes futuras: {total_future_orders}."
            df.at[first_negative_index, 'notes'] += suggestion + " "

        # Calcular fecha de pedido
        order_date = calculate_order_date(df.loc[first_negative_index])
        if order_date is not None:
            df.at[first_negative_index, 'date'] = order_date
        else:
            df.at[first_negative_index, 'notes'] += "Lead time desconocido. No se puede calcular la fecha de pedido. "

        # Recalcular order_quantity_accum y stock_final
        df['quantity_accum'] = df.groupby('material')['quantity'].cumsum()
        df['stock_final'] = df['need_accum'] + df['stock'] + df['quantity_accum']
        
        # Llamar recursivamente a la función
        return adjust_orders_recursive(df, material)
    
    return df

def adjust_orders(df):
    # Crear una copia del DataFrame original
    result_df = df.copy()
    
    # Agrupar por material
    grouped = result_df['material'].unique()
    
    for material in grouped:
        result_df = adjust_orders_recursive(result_df, material)
    
    return result_df

# Función para exportar el DataFrame a un archivo de Excel en memoria
def to_excel(dataframe):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        dataframe.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

def find_missing_materials(dataframe):
    # Filtra las filas donde 'description' esté vacía o sea nula
    unique_missing_materials = dataframe[dataframe['description'].isnull() | (dataframe['description'] == '')]

    # Si existen materiales sin descripción, muestra la lista y avisa al usuario
    if not unique_missing_materials.empty:
        st.warning("⚠️ Advertencia: Los siguientes materiales no tienen datos auxiliares:")
        st.write(unique_missing_materials['material'].unique().tolist())
    else:
        st.success("✅ Todos los materiales tienen datos auxiliares.")

    return unique_missing_materials

def find_missing_supplier_info(dataframe):
    # Selecciona las columnas que comienzan con 'supplier', excluyendo 'supplier_notes'
    supplier_columns = [col for col in dataframe.columns if col.startswith('supplier') and col != 'supplier_notes']
    
    # Filtra los materiales donde alguna columna de supplier esté vacía o nula
    missing_supplier_info = dataframe[dataframe[supplier_columns].isnull().any(axis=1)]['material'].unique().tolist()

    # Muestra advertencia si hay materiales con información incompleta del proveedor
    if missing_supplier_info:
        st.warning("⚠️ Advertencia: Los siguientes materiales tienen información incompleta de proveedor:")
        st.write(missing_supplier_info)
    else:
        st.success("✅ Todos los materiales tienen información completa de proveedor.")

    return missing_supplier_info


st.header(f':blue[Requerimiento de materiales]')

st.subheader("Datos stock")
file_stock = st.file_uploader("Please upload an xls, xlsx", type=["xls","xlsx"], key="stock")  
# Datos de stock
if file_stock:
    value= datetime.now()
    year = value.year
    min_value=date(year - 1, 1, 1)
    max_value=date(year, 12, 31)

    data_stock = get_data_stock(file_stock) 
    
    if data_stock is not None:
               
        c1, c2 = st.columns([1,2],vertical_alignment="top")
        initial_stock_date = c1.date_input("Stock Inicial?",value = value, min_value=min_value, max_value=max_value)
        
        if initial_stock_date:
            year_stock = initial_stock_date.isocalendar().year
            week_stock = initial_stock_date.isocalendar().week
            year_week = year_stock  * 100 + week_stock            
            c1.write(year_week)
        else:
            year_stock = initial_stock_date.isocalendar().year
            week_stock = initial_stock_date.isocalendar().week
            
        unique_stores = data_stock['name_cluster_store'].unique()
        default_stores = ["Principal insumos", "Secundario cámaras", "Producción", "Secundario insumos"]
        selected_stores = c2.multiselect("Selecciona los stores:", unique_stores, default=default_stores)
        if selected_stores:
            filtered_stock = data_stock[data_stock['name_cluster_store'].isin(selected_stores)]
        else:
            filtered_stock = data_stock[data_stock['name_cluster_store'].isin(selected_stores)]
            
        grouped_stock = filtered_stock.groupby('material', as_index=False)['stock'].sum()
        grouped_stock["closing_date"] = initial_stock_date
        grouped_stock["year_week"] = year_week
        st.write(grouped_stock) 
        
        # Datos de compras
        st.subheader("Datos compras")
        file_requirements = st.file_uploader("Please upload an xls, xlsx", type=["xls","xlsx"], key="requirenments")    
        if file_requirements:
            data_requirements =get_data_requirements(file_requirements)
            # Verifica requerimientos de compras anteriores a la fecha de análisis en estado Pedido    
            data_requirenments_filtrado = data_requirements[data_requirements["year_week"] < year_week]
            
            if not data_requirenments_filtrado.empty:
                st.warning("Existen registros de requerimientos anteriores a la semana de análisis.")
                st.write(data_requirenments_filtrado)
            else:
                grouped_requirements = data_requirements.groupby(["material", "year_week"], as_index=False).agg({
                        "order": "first",
                        "status": "first",
                        "registration": "first",
                        "quantity": "sum", 
                        "notes": "first",
                        "date":"first"
                        })
                # grouped_requirenments = data_requirements.groupby(["material","year_week"], as_index=False)["quantity"].sum()
                grouped_requirements["notes"] = grouped_requirements["notes"].fillna("")
                st.write(grouped_requirements)
            
                #Datos consumos , datso integrados
                st.subheader("Datos consumos")
                file_material = st.file_uploader("Please upload an xls, xlsx", type=["xls","xlsx"], key="material")    
                if file_material:
                    data_material = get_data_material(file_material)
                    # Unir los DataFrames de material y stock por columnas "material" y "year_week"
                    merged_stock = data_material.merge( grouped_stock,how="left", on=["material", "year_week"])
                    # Replicar el valor de stock y clising_date a todos los registros del mismo material
                    merged_stock["stock"] = merged_stock.groupby("material")["stock"].transform(lambda x: x.ffill())
                    merged_stock['closing_date'] = pd.to_datetime(merged_stock['closing_date'], errors='coerce')
                    merged_stock["closing_date"] = merged_stock.groupby("material")["closing_date"].transform(lambda x: x.ffill())
                    # Unir los DataFrames de material_stock y compras por columnas "material" y "year_week"
                    merged_requirenmets = merged_stock.merge(grouped_requirements, how="left", on=["material", "year_week"])
                    
                    merged_requirenmets["stock"] = merged_requirenmets["stock"].fillna(0)  # Reemplazar valores nulos por 0
                    merged_requirenmets["quantity"] = merged_requirenmets["quantity"].fillna(0)  # Reemplazar valores nulos por 0
                    # Calcular el acumulado de material_need por material y semana
                    merged_requirenmets["quantity_accum"] = merged_requirenmets.groupby("material")["quantity"].cumsum() 
                    merged_requirenmets["stock_final"] = merged_requirenmets["need_accum"] + merged_requirenmets["stock"] + merged_requirenmets["quantity_accum"] # Calcula stock final 
                    # Une con datos auxiliares de materiales
                    merged_assinstant = preprocessing_get_assistant(merged_requirenmets)
                    merged_assinstant["notes"] = merged_assinstant["notes"].fillna("").astype(str)            
                    new_df = adjust_orders(merged_assinstant)
                    # st.write(new_df)
                    new_requirenments = new_df[new_df["quantity"] > 0][["material", "description", "um", "date", "year_week", "quantity",
                                                             "supplier_currency", "supplier_price", "supplier_notes", "notes", "status", "registration",
                                                             "supplier", "supplier_name", "supplier_peyment_term"]]
                    # st.write(new_requirenments)
                    # # TODO verificar que el material existe en el auxiliar, y que tenga todos los datos obligatorios para poder seguir con el proceso
                     # Call the function to find missing descriptions
                    missing = find_missing_materials(new_requirenments)
                    missing_supplier_materials = find_missing_supplier_info(new_requirenments )
                    
                    # # Generar el archivo Excel
                    # excel_data = to_excel(new_requirenments)
                    # # Crear un botón de descarga en Streamlit
                    # st.download_button(
                    #     label="Descargar datos en Excel",
                    #     data=excel_data,
                    #     file_name="data.xlsx",
                    #     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
  
       