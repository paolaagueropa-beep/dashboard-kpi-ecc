import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
import numpy as np
import requests
from io import BytesIO

st.set_page_config(
    page_title="Dashboard KPI — Servicio Técnico ECC",
    page_icon="📊",
    layout="wide"
)

DRIVE_ID = "11wg3Jp8xDARmxeK1NzNxXWl_XfVUqXjZ"

@st.cache_data(ttl=3600)
def cargar_datos():
    url = f"https://drive.google.com/uc?export=download&id={DRIVE_ID}"
    response = requests.get(url)
    contenido = BytesIO(response.content)
    hojas = ['Resumen_Agentes','Resumen_Jefatura','JP_Semana','JP_Dia',
             'Historico','Agentes_Criticos','Historico_Agente',
             'Resumen_Semanal','Detalle_Diario',
             'Horas_Agente_Mes','Horas_Agente_Semana',
             'Horas_Agente_Dia','Horas_JP_Mes']
    datos = {}
    for hoja in hojas:
        contenido.seek(0)
        datos[hoja] = pd.read_excel(contenido, sheet_name=hoja)
    return datos

def semaforo(val, tipo="utilizacion"):
    if pd.isna(val): return "Sin datos"
    if tipo == "ocupacion":
        if val >= 68: return "🟢 Óptimo"
        elif val >= 56.5: return "🟡 Medio"
        else: return "🔴 Crítico"
    elif tipo == "adhesion":
        if val >= 99: return "🟢 Óptimo"
        elif val >= 96.5: return "🟡 Medio"
        else: return "🔴 Crítico"
    else:
        if val >= 86: return "🟢 Óptimo"
        elif val >= 75: return "🟡 Medio"
        else: return "🔴 Crítico"

colores_semaforo = {
    "🟢 Óptimo": "#2ecc71",
    "🟡 Medio": "#f1c40f",
    "🔴 Crítico": "#e74c3c",
    "Sin datos": "#95a5a6"
}

st.title("📊 Dashboard KPI — Servicio Técnico ECC")
st.markdown("---")

with st.spinner("⏳ Cargando datos desde Drive..."):
    try:
        datos = cargar_datos()
        resumen   = datos['Resumen_Agentes']
        jefatura  = datos['Resumen_Jefatura']
        jp_semana = datos['JP_Semana']
        jp_dia    = datos['JP_Dia']
        historico = datos['Historico']
        criticos  = datos['Agentes_Criticos']
        hist_ag   = datos['Historico_Agente']
        semanal   = datos['Resumen_Semanal']
        diario    = datos['Detalle_Diario']
        hrs_mes   = datos['Horas_Agente_Mes']
        hrs_sem   = datos['Horas_Agente_Semana']
        hrs_dia   = datos['Horas_Agente_Dia']
        hrs_jp    = datos['Horas_JP_Mes']
        st.success("✅ Datos cargados correctamente")
    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.stop()

resumen["Semaforo"]     = resumen["Utilizacion"].apply(lambda x: semaforo(x,"utilizacion"))
resumen["Semaforo_Adh"] = resumen["Adhesion"].apply(lambda x: semaforo(x,"adhesion"))
resumen["Semaforo_Ocu"] = resumen["Ocupacion"].apply(lambda x: semaforo(x,"ocupacion"))

st.sidebar.title("🔍 Filtros Globales")
supervisores = ["Todos"] + sorted(resumen["JP"].dropna().unique().tolist())
supervisor_sel = st.sidebar.selectbox("Supervisor", supervisores)
contratos = ["Todos"] + sorted(resumen["HRS_CONTRATO"].dropna().unique().tolist())
contrato_sel = st.sidebar.selectbox("Horas Contrato", contratos)
antiguedades = ["Todos"] + sorted(resumen["Tramo_Antiguedad"].dropna().unique().tolist())
antiguedad_sel = st.sidebar.selectbox("Antigüedad", antiguedades)
if st.sidebar.button("🔄 Refrescar datos"):
    st.cache_data.clear()
    st.rerun()

df = resumen.copy()
if supervisor_sel != "Todos":
    df = df[df["JP"] == supervisor_sel]
if contrato_sel != "Todos":
    df = df[df["HRS_CONTRATO"] == contrato_sel]
if antiguedad_sel != "Todos":
    df = df[df["Tramo_Antiguedad"] == antiguedad_sel]

util_prom = df["Utilizacion"].mean()
adh_prom  = df["Adhesion"].mean()
ocu_prom  = df["Ocupacion"].mean()

col1, col2, col3, col4 = st.columns(4)
col1.metric("👥 Agentes", len(df))

def metrica_color(col, label, valor, tipo="utilizacion"):
    nivel = semaforo(valor, tipo)
    color = colores_semaforo[nivel]
    col.markdown(f"""
    <div style='background-color:{color}20; border-left:5px solid {color};
                padding:10px; border-radius:5px'>
        <p style='margin:0; font-size:13px; color:gray'>{label}</p>
        <p style='margin:0; font-size:28px; font-weight:bold'>{valor:.1f}%</p>
        <p style='margin:0; font-size:12px'>{nivel}</p>
    </div>
    """, unsafe_allow_html=True)

metrica_color(col2, "📈 Utilización", util_prom, "utilizacion")
metrica_color(col3, "✅ Adhesión",    adh_prom,  "adhesion")
metrica_color(col4, "⚡ Ocupación",   ocu_prom,  "ocupacion")
st.markdown("---")

meses_orden = ["Septiembre","Octubre","Noviembre","Diciembre",
               "Enero","Febrero","Marzo"]

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Resumen Mensual",
    "🏅 Ranking y Acumulado",
    "👤 Evolución por Agente",
    "🔴 Agentes Críticos",
    "⏱️ Control de Horas"
])

# ══════════════════════════════════════════
# TAB 1
# ══════════════════════════════════════════
with tab1:
    col_izq, col_der = st.columns(2)
    with col_izq:
        st.subheader("🏆 Ranking Utilización por Agente")
        ranking = df.sort_values("Utilizacion", ascending=True).copy()
        fig1 = px.bar(ranking, x="Utilizacion", y="NOMBRE",
                     color="Semaforo", color_discrete_map=colores_semaforo,
                     orientation="h", text="Utilizacion")
        fig1.add_vline(x=75, line_dash="dash", line_color="orange", annotation_text="Meta 75%")
        fig1.add_vline(x=86, line_dash="dash", line_color="green", annotation_text="Óptimo 86%")
        fig1.update_traces(texttemplate="%{text:.1f}%", textposition="outside", textfont=dict(size=11))
        fig1.update_layout(height=600, plot_bgcolor="white")
        st.plotly_chart(fig1, use_container_width=True, key="fig1")

    with col_der:
        st.subheader("🚦 Distribución Semáforo")
        dist = df["Semaforo"].value_counts().reset_index()
        dist.columns = ["Nivel", "Agentes"]
        fig2 = px.pie(dist, values="Agentes", names="Nivel",
                     color="Nivel", color_discrete_map=colores_semaforo, hole=0.4)
        fig2.update_traces(textinfo="label+percent+value", textfont=dict(size=12))
        fig2.update_layout(height=300)
        st.plotly_chart(fig2, use_container_width=True, key="fig2")

        st.subheader("👥 KPIs por Jefatura")
        fig3 = go.Figure()
        for kpi, color in zip(["Utilizacion","Adhesion","Ocupacion"],
                               ["#3498db","#2ecc71","#e67e22"]):
            fig3.add_trace(go.Bar(name=kpi, x=jefatura["JP"], y=jefatura[kpi],
                                 text=jefatura[kpi], texttemplate="%{text:.1f}%",
                                 textposition="outside", textfont=dict(size=11),
                                 marker_color=color))
        fig3.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Meta 75%")
        fig3.update_layout(barmode="group", height=350, xaxis_tickangle=-45, plot_bgcolor="white")
        st.plotly_chart(fig3, use_container_width=True, key="fig3")

    st.subheader("📈 Evolución Histórica del Servicio")
    meses_disp = [m for m in meses_orden if m in historico.columns]
    promedios  = historico[meses_disp].mean() * 100
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(
        x=meses_disp, y=promedios.tolist(), mode="lines+markers+text",
        text=[f"{v:.1f}%" for v in promedios], textposition="top center",
        textfont=dict(size=12, color="white"), line=dict(color="#3498db", width=3),
        marker=dict(size=12, color=[colores_semaforo[semaforo(v,"utilizacion")] for v in promedios],
                   line=dict(width=2, color="white")), name="Real"
    ))
    X = np.arange(len(promedios)).reshape(-1,1)
    modelo = LinearRegression().fit(X, promedios.values)
    meses_fut = ["Abril","Mayo","Junio"]
    preds = modelo.predict(np.arange(len(promedios), len(promedios)+3).reshape(-1,1))
    fig4.add_trace(go.Scatter(
        x=meses_fut, y=preds.tolist(), mode="lines+markers+text",
        text=[f"{v:.1f}%" for v in preds], textposition="top center",
        textfont=dict(size=12, color="white"), name="Proyección",
        line=dict(color="#9b59b6", dash="dash", width=3),
        marker=dict(size=12, symbol="diamond")
    ))
    fig4.add_hrect(y0=0,  y1=75,  fillcolor="#e74c3c", opacity=0.05)
    fig4.add_hrect(y0=75, y1=86,  fillcolor="#f1c40f", opacity=0.05)
    fig4.add_hrect(y0=86, y1=100, fillcolor="#2ecc71", opacity=0.05)
    fig4.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Meta 75%")
    fig4.add_hline(y=86, line_dash="dash", line_color="green", annotation_text="Óptimo 86%")
    fig4.update_layout(height=450, plot_bgcolor="white")
    st.plotly_chart(fig4, use_container_width=True, key="fig4")

    st.subheader("📋 Resumen Completo por Agente")
    cols_tabla = ["NOMBRE","JP","HRS_CONTRATO","ESTADO","Tramo_Antiguedad",
                  "Utilizacion","Semaforo","Adhesion","Semaforo_Adh","Ocupacion","Semaforo_Ocu"]
    tabla = df[cols_tabla].sort_values("Utilizacion", ascending=False).copy()
    for col in ["Utilizacion","Adhesion","Ocupacion"]:
        tabla[col] = tabla[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "")
    st.dataframe(tabla, use_container_width=True, key="tabla1")

# ══════════════════════════════════════════
# TAB 2
# ══════════════════════════════════════════
with tab2:
    st.subheader("🏅 Ranking y Acumulado por Período")
    periodo = st.radio("Ver por:", ["Mes","Semana","Día"], horizontal=True, key="periodo_tab2")

    if periodo == "Mes":
        data_jp = jefatura.copy()
        data_ag = resumen.copy()
        titulo_periodo = "Marzo 2026"
    elif periodo == "Semana":
        semanas_disp = sorted(jp_semana["Semana"].dropna().unique().tolist())
        semana_sel = st.selectbox("Selecciona semana", semanas_disp, key="semana_tab2")
        data_jp = jp_semana[jp_semana["Semana"] == semana_sel].copy()
        data_ag = semanal[semanal["Semana"] == semana_sel].copy()
        titulo_periodo = semana_sel
    else:
        fechas_disp = sorted(jp_dia["Fecha"].dropna().unique().tolist())
        fecha_sel = st.selectbox("Selecciona fecha", fechas_disp, key="fecha_tab2")
        data_jp = jp_dia[jp_dia["Fecha"] == fecha_sel].copy()
        data_ag = diario[diario["Fecha"] == fecha_sel].dropna(subset=["Utilizacion"]).copy()
        titulo_periodo = str(fecha_sel)

    data_jp["Semaforo"] = data_jp["Utilizacion"].apply(lambda x: semaforo(x,"utilizacion"))
    data_ag["Semaforo"] = data_ag["Utilizacion"].apply(lambda x: semaforo(x,"utilizacion"))

    st.markdown(f"### 👔 Ranking Supervisores — {titulo_periodo}")
    col_r1, col_r2 = st.columns([2,1])
    with col_r1:
        jp_rank = data_jp.sort_values("Utilizacion", ascending=True)
        fig_jp = px.bar(jp_rank, x="Utilizacion", y="JP",
                       color="Semaforo", color_discrete_map=colores_semaforo,
                       orientation="h", text="Utilizacion")
        fig_jp.add_vline(x=75, line_dash="dash", line_color="orange", annotation_text="Meta 75%")
        fig_jp.add_vline(x=86, line_dash="dash", line_color="green", annotation_text="Óptimo 86%")
        fig_jp.update_traces(texttemplate="%{text:.1f}%", textposition="outside", textfont=dict(size=11))
        fig_jp.update_layout(height=450, plot_bgcolor="white")
        st.plotly_chart(fig_jp, use_container_width=True, key="fig_jp")

    with col_r2:
        st.markdown("#### 🥇 Top 3 Mejor")
        top3 = data_jp.sort_values("Utilizacion", ascending=False).head(3)
        for i, (_, row) in enumerate(top3.iterrows()):
            medalla = ["🥇","🥈","🥉"][i]
            color = colores_semaforo[semaforo(row["Utilizacion"],"utilizacion")]
            nombre_corto = " ".join(row["JP"].split()[:2])
            st.markdown(f"""
            <div style='background:{color}20; border-left:4px solid {color};
                        padding:8px; border-radius:5px; margin-bottom:8px'>
                <b>{medalla} {nombre_corto}</b><br>
                Utilización: <b>{row['Utilizacion']:.1f}%</b>
            </div>""", unsafe_allow_html=True)

        st.markdown("#### ⚠️ Top 3 Menor")
        bot3 = data_jp.sort_values("Utilizacion").head(3)
        for _, row in bot3.iterrows():
            color = colores_semaforo[semaforo(row["Utilizacion"],"utilizacion")]
            nombre_corto = " ".join(row["JP"].split()[:2])
            st.markdown(f"""
            <div style='background:{color}20; border-left:4px solid {color};
                        padding:8px; border-radius:5px; margin-bottom:8px'>
                <b>⚠️ {nombre_corto}</b><br>
                Utilización: <b>{row['Utilizacion']:.1f}%</b>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"### 👤 Ranking Agentes — {titulo_periodo}")
    jp_opciones = ["Todos"] + sorted(data_ag["JP"].dropna().unique().tolist())
    jp_filtro = st.selectbox("Filtrar por supervisor", jp_opciones, key="jp_rank")
    data_ag_fil = data_ag[data_ag["JP"] == jp_filtro].copy() if jp_filtro != "Todos" else data_ag.copy()
    data_ag_fil = data_ag_fil.sort_values("Utilizacion", ascending=True)

    fig_ag = px.bar(data_ag_fil, x="Utilizacion", y="NOMBRE",
                   color="Semaforo", color_discrete_map=colores_semaforo,
                   orientation="h", text="Utilizacion")
    fig_ag.add_vline(x=75, line_dash="dash", line_color="orange", annotation_text="Meta 75%")
    fig_ag.add_vline(x=86, line_dash="dash", line_color="green", annotation_text="Óptimo 86%")
    fig_ag.update_traces(texttemplate="%{text:.1f}%", textposition="outside", textfont=dict(size=11))
    fig_ag.update_layout(height=600, plot_bgcolor="white")
    st.plotly_chart(fig_ag, use_container_width=True, key="fig_ag")

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("👥 Agentes", len(data_ag_fil))
    metrica_color(col_m2, "📈 Utilización", data_ag_fil["Utilizacion"].mean(), "utilizacion")
    metrica_color(col_m3, "✅ Adhesión", data_ag_fil["Adhesion"].mean(), "adhesion")
    metrica_color(col_m4, "⚡ Ocupación", data_ag_fil["Ocupacion"].mean(), "ocupacion")

# ══════════════════════════════════════════
# TAB 3
# ══════════════════════════════════════════
with tab3:
    st.subheader("👤 Evolución Histórica por Agente")
    col_a, col_b = st.columns(2)
    with col_a:
        sup_ag = st.selectbox("Filtrar supervisor",
            ["Todos"] + sorted(hist_ag["Jefe_de_plataforma"].dropna().unique().tolist()),
            key="sup_ag")
    hist_fil = hist_ag[hist_ag["Jefe_de_plataforma"] == sup_ag].copy() if sup_ag != "Todos" else hist_ag.copy()
    with col_b:
        agente_sel = st.selectbox("Selecciona agente",
            sorted(hist_fil["Nombre_agente"].dropna().unique().tolist()), key="agente_sel")

    ag = hist_fil[hist_fil["Nombre_agente"] == agente_sel].iloc[0]
    estado    = ag.get("ESTADO", "Sin dato")
    contrato  = ag.get("HRS_CONTRATO", "Sin dato")
    ant_meses = ag.get("Antiguedad_meses", None)
    ant_str   = f"{int(ant_meses)} meses" if pd.notna(ant_meses) else "Sin dato"
    tramo     = ag.get("Tramo_Antiguedad", "") if "Tramo_Antiguedad" in ag else ""
    promedio  = ag.get("Promedio_historico", 0)
    tendencia = ag.get("Tendencia", "Sin dato")
    sem_ag    = ag.get("Semaforo_historico", "Sin datos")
    color_ag  = colores_semaforo.get(sem_ag, "#95a5a6")

    st.markdown(f"""
    <div style='background:{color_ag}20; border-left:5px solid {color_ag};
                padding:15px; border-radius:8px; margin-bottom:15px'>
        <h4 style='margin:0'>{agente_sel}</h4>
        <p style='margin:5px 0'>
            📋 Estado: <b>{estado}</b> &nbsp;|&nbsp;
            ⏰ Contrato: <b>{contrato} hrs</b> &nbsp;|&nbsp;
            📅 Antigüedad: <b>{ant_str}</b> ({tramo}) &nbsp;|&nbsp;
            📊 Promedio histórico: <b>{promedio:.1f}%</b> &nbsp;|&nbsp;
            {tendencia} &nbsp;|&nbsp; {sem_ag}
        </p>
    </div>""", unsafe_allow_html=True)

    st.markdown("#### 📅 Evolución Mensual")
    meses_ag = [m for m in meses_orden if m in hist_ag.columns]
    vals_ag  = [ag[m] if pd.notna(ag.get(m)) else None for m in meses_ag]
    fig_m = go.Figure()
    fig_m.add_trace(go.Scatter(
        x=meses_ag, y=vals_ag, mode="lines+markers+text",
        text=[f"{v:.1f}%" if v else "" for v in vals_ag],
        textposition="top center", textfont=dict(size=12, color="white"),
        line=dict(color=color_ag, width=3),
        marker=dict(size=14, color=[colores_semaforo[semaforo(v,"utilizacion")] if v else "#95a5a6" for v in vals_ag],
                   line=dict(width=2, color="white")), name=agente_sel
    ))
    fig_m.add_hrect(y0=0,  y1=75,  fillcolor="#e74c3c", opacity=0.05)
    fig_m.add_hrect(y0=75, y1=86,  fillcolor="#f1c40f", opacity=0.05)
    fig_m.add_hrect(y0=86, y1=100, fillcolor="#2ecc71", opacity=0.05)
    fig_m.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Meta 75%")
    fig_m.add_hline(y=86, line_dash="dash", line_color="green", annotation_text="Óptimo 86%")
    fig_m.update_layout(height=380, plot_bgcolor="white", yaxis_range=[0,115])
    st.plotly_chart(fig_m, use_container_width=True, key="fig_m")

    st.markdown("#### 📆 Evolución Semanal")
    ag_sem = semanal[semanal["NOMBRE"] == agente_sel].sort_values("Semana")
    if not ag_sem.empty:
        fig_s = go.Figure()
        fig_s.add_trace(go.Bar(
            x=ag_sem["Semana"], y=ag_sem["Utilizacion"],
            text=ag_sem["Utilizacion"], texttemplate="%{text:.1f}%",
            textposition="outside", textfont=dict(size=12, color="white"),
            marker_color=[colores_semaforo[semaforo(v,"utilizacion")] for v in ag_sem["Utilizacion"]]
        ))
        fig_s.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Meta 75%")
        fig_s.add_hline(y=86, line_dash="dash", line_color="green", annotation_text="Óptimo 86%")
        fig_s.add_hrect(y0=0,  y1=75,  fillcolor="#e74c3c", opacity=0.05)
        fig_s.add_hrect(y0=75, y1=86,  fillcolor="#f1c40f", opacity=0.05)
        fig_s.add_hrect(y0=86, y1=100, fillcolor="#2ecc71", opacity=0.05)
        fig_s.update_layout(height=350, plot_bgcolor="white", yaxis_range=[0,115])
        st.plotly_chart(fig_s, use_container_width=True, key="fig_s")

    st.markdown("#### 📊 Evolución Diaria")
    ag_dia = diario[diario["NOMBRE"] == agente_sel].dropna(subset=["Utilizacion"]).sort_values("Fecha")
    if not ag_dia.empty:
        fig_d = go.Figure()
        fig_d.add_trace(go.Scatter(
            x=ag_dia["Fecha"].astype(str), y=ag_dia["Utilizacion"],
            mode="lines+markers+text",
            text=[f"{v:.1f}%" for v in ag_dia["Utilizacion"]],
            textposition="top center", textfont=dict(size=11, color="white"),
            line=dict(color=color_ag, width=2),
            marker=dict(size=10, color=[colores_semaforo[semaforo(v,"utilizacion")] for v in ag_dia["Utilizacion"]],
                       line=dict(width=2, color="white"))
        ))
        fig_d.add_hrect(y0=0,  y1=75,  fillcolor="#e74c3c", opacity=0.05)
        fig_d.add_hrect(y0=75, y1=86,  fillcolor="#f1c40f", opacity=0.05)
        fig_d.add_hrect(y0=86, y1=100, fillcolor="#2ecc71", opacity=0.05)
        fig_d.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Meta 75%")
        fig_d.add_hline(y=86, line_dash="dash", line_color="green", annotation_text="Óptimo 86%")
        fig_d.update_layout(height=400, plot_bgcolor="white", yaxis_range=[0,115], xaxis_tickangle=-45)
        st.plotly_chart(fig_d, use_container_width=True, key="fig_d")

# ══════════════════════════════════════════
# TAB 4
# ══════════════════════════════════════════
with tab4:
    criticos_fil = criticos[criticos["JP"] == supervisor_sel].copy() if supervisor_sel != "Todos" else criticos.copy()
    st.subheader(f"🔴 Agentes en Estado Crítico ({len(criticos_fil)})")
    criticos_mostrar = criticos_fil.copy()
    for col in ["Utilizacion","Adhesion","Ocupacion"]:
        if col in criticos_mostrar.columns:
            criticos_mostrar[col] = criticos_mostrar[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "")
    st.dataframe(criticos_mostrar, use_container_width=True, key="tabla_criticos")

    st.markdown("---")
    st.subheader("📋 Tabla Completa")
    cols_tabla = ["NOMBRE","JP","HRS_CONTRATO","ESTADO","Tramo_Antiguedad",
                  "Utilizacion","Semaforo","Adhesion","Semaforo_Adh","Ocupacion","Semaforo_Ocu"]
    tabla_mostrar = df[cols_tabla].sort_values("Utilizacion", ascending=False).copy()
    for col in ["Utilizacion","Adhesion","Ocupacion"]:
        tabla_mostrar[col] = tabla_mostrar[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "")
    st.dataframe(tabla_mostrar, use_container_width=True, key="tabla_completa")

# ══════════════════════════════════════════
# TAB 5
# ══════════════════════════════════════════
with tab5:
    st.subheader("⏱️ Control de Horas — Análisis de Fuga")

    vista_hrs = st.radio("Ver por:", ["Mes","Semana","Día"], horizontal=True, key="vista_hrs")
    jp_hrs = ["Todos"] + sorted(hrs_mes["JP"].dropna().unique().tolist())
    jp_sel_hrs = st.selectbox("Filtrar supervisor", jp_hrs, key="jp_hrs")

    if vista_hrs == "Mes":
        data_hrs = hrs_mes.copy()
        titulo_hrs = "Marzo 2026"
    elif vista_hrs == "Semana":
        semanas_hrs = sorted(hrs_sem["Semana"].dropna().unique().tolist())
        sem_sel_hrs = st.selectbox("Selecciona semana", semanas_hrs, key="sem_hrs")
        data_hrs = hrs_sem[hrs_sem["Semana"] == sem_sel_hrs].copy()
        titulo_hrs = sem_sel_hrs
    else:
        fechas_hrs = sorted(hrs_dia["Fecha"].dropna().unique().tolist())
        fecha_sel_hrs = st.selectbox("Selecciona fecha", fechas_hrs, key="fecha_hrs")
        data_hrs = hrs_dia[hrs_dia["Fecha"] == fecha_sel_hrs].copy()
        titulo_hrs = str(fecha_sel_hrs)

    if jp_sel_hrs != "Todos":
        data_hrs = data_hrs[data_hrs["JP"] == jp_sel_hrs]

    agentes_hrs = ["Todos"] + sorted(data_hrs["NOMBRE"].dropna().unique().tolist())
    agente_sel_hrs = st.selectbox("Filtrar agente", agentes_hrs, key="agente_hrs")
    if agente_sel_hrs != "Todos":
        data_hrs = data_hrs[data_hrs["NOMBRE"] == agente_sel_hrs]

    st.markdown(f"### 📊 Resumen de Horas — {titulo_hrs}")

    if agente_sel_hrs != "Todos" and len(data_hrs) > 0:
        row_hrs = data_hrs.iloc[0]
        col_h1, col_h2, col_h3, col_h4 = st.columns(4)
        col_h1.markdown(f"""
        <div style='background:#3498db20; border-left:5px solid #3498db; padding:10px; border-radius:5px'>
            <p style='margin:0; font-size:13px; color:gray'>🔌 Hrs Conexión</p>
            <p style='margin:0; font-size:20px; font-weight:bold'>{row_hrs.get('Conectado_hrs','—')}</p>
        </div>""", unsafe_allow_html=True)
        col_h2.markdown(f"""
        <div style='background:#9b59b620; border-left:5px solid #9b59b6; padding:10px; border-radius:5px'>
            <p style='margin:0; font-size:13px; color:gray'>📅 Hrs Programadas</p>
            <p style='margin:0; font-size:20px; font-weight:bold'>{row_hrs.get('Turno_hrs','—')}</p>
        </div>""", unsafe_allow_html=True)
        col_h3.markdown(f"""
        <div style='background:#2ecc7120; border-left:5px solid #2ecc71; padding:10px; border-radius:5px'>
            <p style='margin:0; font-size:13px; color:gray'>✅ Hrs Productivas</p>
            <p style='margin:0; font-size:20px; font-weight:bold'>{row_hrs.get('Hrs_Productivas','—')}</p>
        </div>""", unsafe_allow_html=True)
        col_h4.markdown(f"""
        <div style='background:#e74c3c20; border-left:5px solid #e74c3c; padding:10px; border-radius:5px'>
            <p style='margin:0; font-size:13px; color:gray'>❌ Hrs Improductivas</p>
            <p style='margin:0; font-size:20px; font-weight:bold'>{row_hrs.get('Hrs_Improductivas','—')}</p>
        </div>""", unsafe_allow_html=True)

        st.markdown("---")

        estados_nombres = {
            'EnCola_hrs': '📞 En Cola',
            'Inactivo_hrs': '💤 Inactivo/Disponible',
            'Interactuando_hrs': '🗣️ Interactuando',
            'Ausente_hrs': '🚫 Ausente',
            'NoResponde_hrs': '📵 No Responde',
            'FueraCola_hrs': '🚪 Fuera de Cola',
            'Descanso_hrs': '☕ Descanso',
            'Comida_hrs': '🍽️ Comida',
            'Reunion_hrs': '👥 Reunión',
            'Capacitacion_hrs': '📚 Capacitación',
            'Gestion_hrs': '📝 Gestión',
            'LlamadaManual_hrs': '📲 Llamada Manual',
            'Bano_hrs': '🚽 Baño',
            'Descanso2_hrs': '😴 Descanso 2',
            'PausaActiva_hrs': '🏃 Pausa Activa'
        }

        def hhmmss_a_min(t):
            try:
                partes = str(t).split(':')
                return int(partes[0])*60 + int(partes[1]) + int(partes[2])/60
            except: return 0

        estados_min = {v: hhmmss_a_min(row_hrs.get(k, '00:00:00'))
                      for k, v in estados_nombres.items()}
        estados_min = {k: v for k, v in estados_min.items() if v > 0}
        estados_sorted = dict(sorted(estados_min.items(), key=lambda x: x[1], reverse=True))

        productivas_labels = ['📞 En Cola','💤 Inactivo/Disponible','🗣️ Interactuando']
        colores_barra = ['#2ecc71' if k in productivas_labels else '#e74c3c'
                        for k in estados_sorted.keys()]

        fig_hrs = go.Figure(go.Bar(
            x=list(estados_sorted.values()),
            y=list(estados_sorted.keys()),
            orientation='h',
            marker_color=colores_barra,
            text=[f"{v:.0f} min" for v in estados_sorted.values()],
            textposition='outside', textfont=dict(size=11)
        ))
        fig_hrs.update_layout(
            title=f"Minutos por Estado — {agente_sel_hrs} — {titulo_hrs}",
            height=500, plot_bgcolor="white", xaxis_title="Minutos"
        )
        st.plotly_chart(fig_hrs, use_container_width=True, key="fig_hrs")

        col_pie1, col_pie2 = st.columns(2)
        with col_pie1:
            prod_min   = sum(v for k,v in estados_min.items() if k in productivas_labels)
            improd_min = sum(v for k,v in estados_min.items() if k not in productivas_labels)
            fig_pie = go.Figure(go.Pie(
                labels=['✅ Productivas','❌ Improductivas'],
                values=[prod_min, improd_min], hole=0.4,
                marker_colors=['#2ecc71','#e74c3c']
            ))
            fig_pie.update_traces(textinfo='label+percent+value',
                                 texttemplate='%{label}<br>%{percent}<br>%{value:.0f} min')
            fig_pie.update_layout(title="Productivo vs Improductivo", height=400)
            st.plotly_chart(fig_pie, use_container_width=True, key="fig_pie")

        with col_pie2:
            improd_estados = {k:v for k,v in estados_min.items()
                             if k not in productivas_labels and v > 0}
            if improd_estados:
                fig_pie2 = go.Figure(go.Pie(
                    labels=list(improd_estados.keys()),
                    values=list(improd_estados.values()), hole=0.4
                ))
                fig_pie2.update_traces(textinfo='label+percent')
                fig_pie2.update_layout(title="🔍 Desglose Improductivas", height=400)
                st.plotly_chart(fig_pie2, use_container_width=True, key="fig_pie2")

    st.markdown("---")
    st.markdown("#### 📋 Tabla Detalle por Estado")
    estados_nombres_tabla = {
        'Conectado_hrs': '🔌 Conectado',
        'Turno_hrs': '📅 Turno',
        'Hrs_Productivas': '✅ Productivas',
        'Hrs_Improductivas': '❌ Improductivas',
        'EnCola_hrs': '📞 En Cola',
        'Inactivo_hrs': '💤 Inactivo',
        'Interactuando_hrs': '🗣️ Interactuando',
        'Ausente_hrs': '🚫 Ausente',
        'NoResponde_hrs': '📵 No Responde',
        'FueraCola_hrs': '🚪 Fuera Cola',
        'Descanso_hrs': '☕ Descanso',
        'Comida_hrs': '🍽️ Comida',
        'Reunion_hrs': '👥 Reunión',
        'Capacitacion_hrs': '📚 Capacitación',
        'Gestion_hrs': '📝 Gestión',
        'LlamadaManual_hrs': '📲 Llamada Manual',
        'Bano_hrs': '🚽 Baño',
        'Descanso2_hrs': '😴 Descanso 2',
        'PausaActiva_hrs': '🏃 Pausa Activa'
    }
    cols_disp = [c for c in estados_nombres_tabla.keys() if c in data_hrs.columns]
    tabla_horas = data_hrs[['NOMBRE'] + cols_disp].copy()
    tabla_horas = tabla_horas.rename(columns=estados_nombres_tabla)
    st.dataframe(tabla_horas, use_container_width=True, key="tabla_horas")