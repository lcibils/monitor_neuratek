import os
import pandas as pd
import time
from datetime import datetime, timedelta, timezone
import configparser
import streamlit as st
from redminelib import Redmine

# from icecream import ic
from  sla_class import SLA

def read_parameters(file_path):
    config = configparser.ConfigParser()
    config.read(file_path)
    return config

def get_client(id):
    user = redmine.user.get(id)
    try:
        client = [f['value'] for f in user.custom_fields if f['name'] == "Cliente"]
        client = client[0] if client else ""
    except:
        client = ""
    return client

def get_fecha_estimada_id(name):
    fields = redmine.custom_field.all()
    return [f['id'] for f in fields if f['name'] == name][0]

def get_fecha_prevista(issue):
    fields = issue.custom_fields
    try:
        field = [f['value'] for f in fields if f['id'] == id_fecha_estimada][0]
    except:
        field = ''
    return field

def format_date(dt):
    if pd.isnull(dt):
        return dt
    return pd.to_datetime(dt, utc=True).strftime(date_fmt)

def get_status_id(status):
    a = [s.id for s in redmine.issue_status.all() if s.name == status][0]
    return str(a)

def obtener_fechas_en_curso_resuelta(issue, id_en_curso, id_resuelta):
    f_en_curso = f_resuelta = pd.NaT
    for j in issue.journals:
        if len(j.details) > 0:
            for d in j.details:
                if pd.isnull(f_en_curso) and d['name'] == 'status_id' and d['new_value'] == id_en_curso:
                    f_en_curso = format_date(j.created_on)
                elif pd.isnull(f_resuelta) and d['name'] == 'status_id' and d['new_value'] == id_resuelta:
                    f_resuelta = format_date(j.created_on)
                if pd.notnull(f_en_curso) and pd.notnull(f_resuelta):
                    break
        if pd.notnull(f_en_curso) and pd.notnull(f_resuelta):
            break
    return f_en_curso, f_resuelta

def load_issues(query, id_en_curso, id_resuelta):
    rows = []
    for issue in query:
        client = get_client(issue.author.id)
        f_creacion = pd.to_datetime(format_date(issue.created_on))
        f_en_curso, f_resuelta = obtener_fechas_en_curso_resuelta(issue, id_en_curso, id_resuelta)
        category = issue.category.name if hasattr(issue, 'category') else ''
        
        f_sla1, f_sla2 = pd.NaT, pd.NaT
        if client != '' and category != '':
            f_sla1 = sla.add(client, f_creacion, category, "t_resp_inic")
            if category == 'Mejora o Consulta':
                f_sla2 = sla.m_c(client, get_fecha_prevista(issue))
            else:
                f_sla2 = sla.add(client, f_creacion, category, "t_resp_est")

        rows.append({
            "Id": issue.id,
            "Recibido": f_creacion.strftime(date_fmt),
            # "Recibido": f_creacion.strftime(date_fmt),
            "Cliente": client,
            "Autor": issue.author.name,
            "Categoria": category,
            # "descripcion": issue.subject,
            "Estado": issue.status.name,
            "Fecha Estado": format_date(issue.updated_on) if hasattr(issue, 'updated_on') else pd.NaT,
            "SLA TRI": format_date(f_sla1),
            "En Curso": f_en_curso,
            "SLA TRE": format_date(f_sla2),
            "Resuelta": f_resuelta
        })
        df = pd.DataFrame(rows)
    return df

def apply_color_to_html(df):
    def set_cell_style(row, col):
        if col == 'SLA TRI':
            if pd.isnull(row['SLA TRI']):
                return style_sla('none')
            if pd.isnull(row['En Curso']):
                if pd.to_datetime(row['SLA TRI'])< now:
                    return style_sla('alert') 
                elif pd.to_datetime(row['SLA TRI']) >= now + timedelta(hours=1):
                    return style_sla('ok')
                else:
                    return style_sla.get('warning')
        elif col == 'SLA TRE':
            if pd.isnull(row['SLA TRE']):
                return style_sla('none')
            if pd.isnull(row['Resuelta']):
                if pd.to_datetime(row['SLA TRE']) < now:
                    return style_sla('alert')
                elif pd.to_datetime(row['SLA TRE']) >= now + timedelta(hours=1):
                    return style_sla('ok')
                else:
                    return style_sla.get('warning')
        elif col == 'En Curso':
            if pd.notnull(row['En Curso']):
                if pd.notnull(row['SLA TRI']):
                    return style_sla('alert') if pd.to_datetime(row['SLA TRI']) < pd.to_datetime(row['En Curso']) else style_sla('ok')
                return style_sla('none')
        elif col == 'Resuelta':
            if pd.notnull(row['Resuelta']):
                if pd.notnull(row['SLA TRE']):
                    return style_sla('alert') if pd.to_datetime(row['SLA TRE']) < pd.to_datetime(row['Resuelta']) else style_sla('ok')
                return style_sla('none')
        elif col == 'Categoria':
            if row['Categoria'] !='':
                return style_category(row['Categoria'])
        elif col == 'Estado':
            if row['Estado'] !='':
                return style_status(row['Estado'])
        elif col == 'Cliente':
            if row['Cliente'] !='':
                return style_customer(row['Cliente'])              
        return ""
    

    # Create the HTML table with styles
    html_table = f"<table style='{style_table('general')}'>"
    # Add header
    html_table += "<thead><tr>"
    for col in df.columns:
        html_table += f"<th style='{style_table('header')}'>{col}</th>"
    html_table += "</tr></thead>"
    # Add rows
    html_table += "<tbody>"
    for _, row in df.iterrows():
        html_table += "<tr>"
        for col in df.columns:
            style = set_cell_style(row, col)
            data = '' if pd.isnull(row[col]) else row[col]
            html_table += f"<td style='{style_table('cell')}; {style}'> {data} </td>"
        html_table += "</tr>"
    html_table += "</tbody></table>"

    return html_table

if __name__ == "__main__":
    if 'initialized' not in st.session_state:
        parameters_file = os.getenv('MONITOR_REDMINE', 'parameters.ini')
        cfg = read_parameters(parameters_file)
        st.set_page_config(layout=cfg['misc']['screen_layout'])
        date_fmt = cfg['misc']['date_format']
        sla = SLA(cfg['sla']['file'], date_fmt)

        st.session_state.style_table = sla.style_table
        st.session_state.style_category = sla.style_category
        st.session_state.style_sla = sla.style_sla    
        st.session_state.style_status = sla.style_status
        st.session_state.style_customer = sla.style_customer  

        st.session_state.redmine = Redmine(cfg['Redmine']['url'], key=cfg['Redmine']['key'])
        st.session_state.id_fecha_estimada = get_fecha_estimada_id('Fecha estimada', 
                                                                   st.session_state.redmine)

        st.session_state.cfg = cfg
        st.session_state.date_fmt = date_fmt
        st.session_state.sla = sla

        st.session_state.initialized = True

    cfg = st.session_state.cfg
    date_fmt = st.session_state.date_fmt
    sla = st.session_state.sla
    style_table = st.session_state.style_table
    style_category = st.session_state.style_category
    style_sla = st.session_state.style_sla    
    style_status = st.session_state.style_status
    style_customer = st.session_state.style_customer  
    redmine = st.session_state.redmine
    id_fecha_estimada = st.session_state.id_fecha_estimada

    query = redmine.issue.filter(project_id=cfg['Redmine']['project_id'], status_id=cfg['Redmine']['issues'])
    now = datetime.now()

    # st.set_page_config(layout=cfg['misc']['screen_layout'])
    st.title(cfg['misc']['title'])
    st.subheader(f'{now.strftime(date_fmt)} - total tickets: {len(query)}')

    df = load_issues(query, get_status_id('En curso'), get_status_id('Resuelta'))

    # Convert the DataFrame to a styled HTML table
    html_table = apply_color_to_html(df)

    # Display the table using st.markdown
    table_placeholder = st.empty()
    table_placeholder.markdown(html_table, unsafe_allow_html=True)
    # st.markdown(html_table, unsafe_allow_html=True)

    time.sleep(int(cfg['misc']['loop_time']))
    st.rerun()

    hola