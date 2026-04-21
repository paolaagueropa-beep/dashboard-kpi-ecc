import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
import numpy as np
import requests
from io import BytesIO
from datetime import date, datetime

st.set_page_config(
    page_title="Dashboard KPI — Servicio Técnico ECC",
    page_icon="📊",
    layout="wide"
)

DRIVE_ID = "12zc9C9pw8ltG8yXZfHtBBX_EJaEYobgE"

@st.cache_data(ttl=3600)
def cargar_datos():
    url = f"https://drive.google.com/uc?export=download&id={DRIVE_ID}"
    response = requests.get(url)
    contenido = BytesIO(response.content)
    hojas = ['Resumen_Agentes','Resumen_Jefatura','JP_Semana','JP_Dia',
             'Historico_Agente','Historico_Mensual','Dist_Cuartiles',
             'Resumen_Semanal','Detalle_Diario','Agentes_Criticos',
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

def hhmmss_a_min(t):
    try:
        partes = str(t).split(':')
        return int(partes[0])*60 + int(partes[1]) + float(partes[2])/60
    except: return 0

def min_a_hhmmss(minutos):
    try:
        h = int(minutos // 60)
        m = int(minutos % 60)
        s = int((minutos % 1) * 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    except: return "00:00:00"

def antiguedad_texto(fecha_ingreso):
    try:
        if pd.isna(fecha_ingreso): return "Sin dato"
        if isinstance(fecha_ingreso, str):
            fecha_ingreso = pd.to_datetime(fecha_ingreso)
        hoy = date.today()
        if hasattr(fecha_ingreso, 'date'):
            fecha_ingreso = fecha_ingreso.date()
        años = hoy.year - fecha_ingreso.year
        meses = hoy.month - fecha_ingreso.month
        dias = hoy.day - fecha_ingreso.day
        if dias < 0:
            meses -= 1
            dias += 30
        if meses < 0:
            años -= 1
            meses += 12
        partes = []
        if años > 0: partes.append(f"{años} año{'s' if años > 1 else ''}")
        if meses > 0: partes.append(f"{meses} mes{'es' if meses > 1 else ''}")
        if dias > 0 and años == 0: partes.append(f"{dias} día{'s' if dias > 1 else ''}")
        return ", ".join(partes) if partes else "Recién ingresado"
    except: return "Sin dato"

def regresion_3meses(valores, meses):
    try:
        datos = [(i, v) for i, v in enumerate(valores) if pd.notna(v)]
        if len(datos) < 2: return [], []
        X = np.array([d[0] for d in datos]).reshape(-1,1)
        y = np.array([d[1] for d in datos])
        modelo = LinearRegression().fit(X, y)
        ultimo_idx = max(d[0] for d in datos)
        X_fut = np.array([ultimo_idx+1, ultimo_idx+2, ultimo_idx+3]).reshape(-1,1)
        preds = modelo.predict(X_fut)
        return [f"Proj. {i+1}" for i in range(3)], preds.tolist()
    except: return [], []

# =============================================
# TÍTULO Y SUBTÍTULO DINÁMICO
# =============================================
st.title("📊 Dashboard KPI — Servicio Técnico ECC")
hoy = datetime.now()
st.markdown(f"""
<div style='background:#2c3e5020; border-left:5px solid #3498db;
            padding:10px; border-radius:5px; margin-bottom:10px'>
    <span style='font-size:16px'>
        📅 <b>Mes actual:</b> {hoy.strftime('%B %Y')} &nbsp;|&nbsp;
        🕐 <b>Actualizado:</b> {hoy.strftime('%d/%m/%Y %H:%M')} &nbsp;|&nbsp;
        👩‍💼 <b>Creado por:</b> Paola Agüero — Analista de Control
    </span>
</div>
""", unsafe_allow_html=True)
st.markdown("---")

with st.spinner("⏳ Cargando datos desde Drive..."):
    try:
        datos = cargar_datos()
        resumen      = datos['Resumen_Agentes']
        jefatura     = datos['Resumen_Jefatura']
        jp_semana    = datos['JP_Semana']
        jp_dia       = datos['JP_Dia']
        hist_ag      = datos['Historico_Agente']
        hist_mensual = datos['Historico_Mensual']
        dist_cuartil = datos['Dist_Cuartiles']
        semanal      = datos['Resumen_Semanal']
        diario       = datos['Detalle_Diario']
        criticos     = datos['Agentes_Criticos']
        hrs_mes      = datos['Horas_Agente_Mes']
        hrs_sem      = datos['Horas_Agente_Semana']
        hrs_dia      = datos['Horas_Agente_Dia']
        hrs_jp       = datos['Horas_JP_Mes']
        st.success("✅ Datos cargados correctamente")
    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.stop()

resumen["Semaforo"]     = resumen["Utilizacion"].apply(lambda x: semaforo(x,"utilizacion"))
resumen["Semaforo_Adh"] = resumen["Adhesion"].apply(lambda x: semaforo(x,"adhesion"))
resumen["Semaforo_Ocu"] = resumen["Ocupacion"].apply(lambda x: semaforo(x,"ocupacion"))

# Sidebar
st.sidebar.title("🔍 Filtros")
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
if supervisor_sel != "Todos": df = df[df["JP"] == supervisor_sel]
if contrato_sel != "Todos": df = df[df["HRS_CONTRATO"] == contrato_sel]
if antiguedad_sel != "Todos": df = df[df["Tramo_Antiguedad"] == antiguedad_sel]

util_prom = df["Utilizacion"].mean()
adh_prom  = df["Adhesion"].mean()
ocu_prom  = df["Ocupacion"].mean()
ocu_min   = (ocu_prom / 100) * 60

col1, col2, col3, col4 = st.columns(4)
col1.metric("👥 Agentes", len(df))

def metrica_color(col, label, valor, tipo="utilizacion", extra=""):
    nivel = semaforo(valor, tipo)
    color = colores_semaforo[nivel]
    col.markdown(f"""
    <div style='background-color:{color}20; border-left:5px solid {color};
                padding:10px; border-radius:5px'>
        <p style='margin:0; font-size:13px; color:gray'>{label}</p>
        <p style='margin:0; font-size:28px; font-weight:bold'>{valor:.1f}%</p>
        <p style='margin:0; font-size:12px'>{nivel}</p>
        {f"<p style='margin:0; font-size:11px; color:gray'>{extra}</p>" if extra else ""}
    </div>""", unsafe_allow_html=True)

metrica_color(col2, "📈 Utilización", util_prom, "utilizacion")
metrica_color(col3, "✅ Adhesión", adh_prom, "adhesion")
metrica_color(col4, "⚡ Ocupación", ocu_prom, "ocupacion",
             extra=f"≈ {ocu_min:.1f} min hablados/hora")
st.markdown("---")

meses_orden = ["Septiembre","Octubre","Noviembre","Diciembre",
               "Enero","Febrero","Marzo","Abril"]

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Resumen Mensual",
    "🏅 Ranking y Acumulado",
    "👤 Evolución por Agente",
    "🔴 Agentes Críticos",
    "⏱️ Control de Horas"
])

# ══════════════════════════════════════════
# TAB 1 — RESUMEN MENSUAL
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
        dist.columns = ["Nivel","Agentes"]
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

    # Evolución histórica con regresión dinámica
    st.subheader("📈 Evolución Histórica del Servicio")
    meses_disp = [m for m in meses_orden if m in hist_ag.columns]
    promedios  = [hist_ag[m].mean() * 100 if hist_ag[m].max() <= 1
                  else hist_ag[m].mean()
                  for m in meses_disp]

    meses_fut, preds = regresion_3meses(promedios, meses_disp)

    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(
        x=meses_disp, y=promedios, mode="lines+markers+text",
        text=[f"{v:.1f}%" for v in promedios], textposition="top center",
        textfont=dict(size=12, color="white"), line=dict(color="#3498db", width=3),
        marker=dict(size=12, color=[colores_semaforo[semaforo(v,"utilizacion")] for v in promedios],
                   line=dict(width=2, color="white")), name="Real"
    ))
    if preds:
        fig4.add_trace(go.Scatter(
            x=meses_fut, y=preds, mode="lines+markers+text",
            text=[f"{v:.1f}%" for v in preds], textposition="top center",
            textfont=dict(size=12, color="white"), name="Proyección 3 meses",
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

    # Tabla horas históricas
    st.subheader("⏱️ Horas Históricas del Servicio")
    if 'Hrs_Conectado' in hist_mensual.columns:
        hrs_hist = hist_mensual.groupby(['Mes','Orden_Mes']).agg(
            Hrs_Programadas=('Hrs_Turno','sum'),
            Hrs_Productivas=('Hrs_Productivas','sum'),
            Hrs_Improductivas=('Hrs_Improductivas','sum'),
            Hrs_Conectado=('Hrs_Conectado','sum')
        ).reset_index().sort_values('Orden_Mes')
        for col in ['Hrs_Programadas','Hrs_Productivas','Hrs_Improductivas','Hrs_Conectado']:
            hrs_hist[col] = hrs_hist[col].apply(lambda x: f"{int(x):,} hrs")
        st.dataframe(hrs_hist[['Mes','Hrs_Programadas','Hrs_Conectado',
                                'Hrs_Productivas','Hrs_Improductivas']],
                    use_container_width=True, key="tabla_hrs_hist")

    # Distribución cuartiles histórica
    st.subheader("📊 Movimiento de Dotación por Cuartil")
    colores_cuartil = {
        'Q1 — Crítico 🔴': '#e74c3c',
        'Q2 — Bajo meta ⚠️': '#f39c12',
        'Q3 — Sobre meta ✅': '#3498db',
        'Q4 — Óptimo 🟢': '#2ecc71'
    }
    fig_cuartil = px.bar(
        dist_cuartil.sort_values('Orden_Mes'),
        x='Mes', y='Agentes', color='Cuartil_Util',
        color_discrete_map=colores_cuartil,
        barmode='stack', text='Agentes',
        title='Distribución de agentes por cuartil — Historia completa'
    )
    fig_cuartil.update_traces(textposition='inside', textfont=dict(size=11))
    fig_cuartil.update_layout(height=400, plot_bgcolor="white")
    st.plotly_chart(fig_cuartil, use_container_width=True, key="fig_cuartil")

    # Tabla completa
    st.subheader("📋 Resumen Completo por Agente")
    cols_tabla = ["NOMBRE","JP","HRS_CONTRATO","ESTADO","Tramo_Antiguedad",
                  "Utilizacion","Semaforo","Adhesion","Semaforo_Adh",
                  "Ocupacion","Semaforo_Ocu","Cuartil_Util","Cuartil_Adh"]
    tabla = df[[c for c in cols_tabla if c in df.columns]].sort_values(
        "Utilizacion", ascending=False).copy()
    for col in ["Utilizacion","Adhesion","Ocupacion"]:
        if col in tabla.columns:
            tabla[col] = tabla[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "")
    st.dataframe(tabla, use_container_width=True, key="tabla1")

# ══════════════════════════════════════════
# TAB 2 — RANKING Y ACUMULADO
# ══════════════════════════════════════════
with tab2:
    st.subheader("🏅 Ranking y Acumulado por Período")
    periodo = st.radio("Ver por:", ["Mes","Semana","Día"], horizontal=True, key="periodo_tab2")

    if periodo == "Mes":
        data_jp = jefatura.copy()
        data_ag = resumen.copy()
        titulo_periodo = hoy.strftime('%B %Y')
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

    # Ranking supervisores
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
        for i, (_, row) in enumerate(data_jp.sort_values("Utilizacion", ascending=False).head(3).iterrows()):
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
        for _, row in data_jp.sort_values("Utilizacion").head(3).iterrows():
            color = colores_semaforo[semaforo(row["Utilizacion"],"utilizacion")]
            nombre_corto = " ".join(row["JP"].split()[:2])
            st.markdown(f"""
            <div style='background:{color}20; border-left:4px solid {color};
                        padding:8px; border-radius:5px; margin-bottom:8px'>
                <b>⚠️ {nombre_corto}</b><br>
                Utilización: <b>{row['Utilizacion']:.1f}%</b>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Top 10 agentes
    st.markdown(f"### 👤 Top 10 Agentes — {titulo_periodo}")
    col_t1, col_t2 = st.columns(2)

    with col_t1:
        st.markdown("#### 🥇 Top 10 Mejor Performance")
        top10_mejor = data_ag.sort_values("Utilizacion", ascending=False).head(10)
        top10_mejor["Semaforo"] = top10_mejor["Utilizacion"].apply(lambda x: semaforo(x,"utilizacion"))
        fig_top10m = px.bar(top10_mejor, x="Utilizacion", y="NOMBRE",
                           color="Semaforo", color_discrete_map=colores_semaforo,
                           orientation="h", text="Utilizacion")
        fig_top10m.add_vline(x=75, line_dash="dash", line_color="orange")
        fig_top10m.add_vline(x=86, line_dash="dash", line_color="green")
        fig_top10m.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_top10m.update_layout(height=400, plot_bgcolor="white", showlegend=False)
        st.plotly_chart(fig_top10m, use_container_width=True, key="fig_top10m")

    with col_t2:
        st.markdown("#### ⚠️ Top 10 Menor Performance")
        top10_menor = data_ag.sort_values("Utilizacion").head(10)
        top10_menor["Semaforo"] = top10_menor["Utilizacion"].apply(lambda x: semaforo(x,"utilizacion"))
        fig_top10mn = px.bar(top10_menor, x="Utilizacion", y="NOMBRE",
                            color="Semaforo", color_discrete_map=colores_semaforo,
                            orientation="h", text="Utilizacion")
        fig_top10mn.add_vline(x=75, line_dash="dash", line_color="orange")
        fig_top10mn.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_top10mn.update_layout(height=400, plot_bgcolor="white", showlegend=False)
        st.plotly_chart(fig_top10mn, use_container_width=True, key="fig_top10mn")

    st.markdown("---")

    # Ranking completo agentes
    st.markdown(f"### 📋 Ranking Completo Agentes — {titulo_periodo}")
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
# TAB 3 — EVOLUCIÓN POR AGENTE
# ══════════════════════════════════════════
with tab3:
    st.subheader("👤 Evolución Histórica por Agente")
    col_a, col_b = st.columns(2)
    with col_a:
        sup_ag = st.selectbox("Filtrar supervisor",
            ["Todos"] + sorted(hist_ag["JP"].dropna().unique().tolist()),
            key="sup_ag")
    hist_fil = hist_ag[hist_ag["JP"] == sup_ag].copy() if sup_ag != "Todos" else hist_ag.copy()
    with col_b:
        agente_sel = st.selectbox("Selecciona agente",
            sorted(hist_fil["NOMBRE"].dropna().unique().tolist()), key="agente_sel")

    ag = hist_fil[hist_fil["NOMBRE"] == agente_sel].iloc[0]
    estado    = ag.get("ESTADO","Sin dato")
    contrato  = ag.get("HRS_CONTRATO","Sin dato")
    fecha_ing = ag.get("FECHA_INGRESO", None)
    ant_texto = antiguedad_texto(fecha_ing)
    promedio  = ag.get("Promedio_historico", 0)
    tendencia = ag.get("Tendencia","Sin dato")
    sem_ag    = ag.get("Semaforo_historico","Sin datos")
    color_ag  = colores_semaforo.get(sem_ag,"#95a5a6")
    veces_crit = ag.get("Veces_Critico", 0)
    meses_crit = ag.get("Meses_Critico","—")

    # Horas del agente
    ag_hrs = hrs_mes[hrs_mes["NOMBRE"] == agente_sel]
    hrs_conectado = hrs_programadas = hrs_productivas = hrs_improductivas = "—"
    if not ag_hrs.empty:
        r = ag_hrs.iloc[0]
        hrs_conectado     = r.get("Conectado_hrs","—")
        hrs_programadas   = r.get("Turno_hrs","—")
        hrs_productivas   = r.get("Hrs_Productivas","—")
        hrs_improductivas = r.get("Hrs_Improductivas","—")

    st.markdown(f"""
    <div style='background:{color_ag}20; border-left:5px solid {color_ag};
                padding:15px; border-radius:8px; margin-bottom:15px'>
        <h4 style='margin:0'>{agente_sel}</h4>
        <p style='margin:5px 0'>
            📋 Estado: <b>{estado}</b> &nbsp;|&nbsp;
            ⏰ Contrato: <b>{contrato} hrs</b> &nbsp;|&nbsp;
            📅 Antigüedad: <b>{ant_texto}</b> &nbsp;|&nbsp;
            📊 Promedio histórico: <b>{promedio:.1f}%</b> &nbsp;|&nbsp;
            {tendencia} &nbsp;|&nbsp; {sem_ag}
        </p>
        <p style='margin:5px 0; font-size:13px'>
            🔌 Conectado: <b>{hrs_conectado}</b> &nbsp;|&nbsp;
            📅 Programado: <b>{hrs_programadas}</b> &nbsp;|&nbsp;
            ✅ Productivas: <b>{hrs_productivas}</b> &nbsp;|&nbsp;
            ❌ Improductivas: <b>{hrs_improductivas}</b>
        </p>
        <p style='margin:5px 0; font-size:13px'>
            🔴 Veces en crítico: <b>{int(veces_crit)}</b> &nbsp;|&nbsp;
            📆 Meses: <b>{meses_crit}</b>
        </p>
    </div>""", unsafe_allow_html=True)

    # Evolución mensual con regresión
    st.markdown("#### 📅 Evolución Mensual")
    meses_ag  = [m for m in meses_orden if m in hist_ag.columns]
    vals_ag   = []
    for m in meses_ag:
        val = ag.get(m)
        if pd.notna(val):
            vals_ag.append(float(val) if float(val) > 1 else float(val)*100)
        else:
            vals_ag.append(None)

    meses_fut_ag, preds_ag = regresion_3meses(vals_ag, meses_ag)

    fig_m = go.Figure()
    fig_m.add_trace(go.Scatter(
        x=meses_ag, y=vals_ag, mode="lines+markers+text",
        text=[f"{v:.1f}%" if v else "" for v in vals_ag],
        textposition="top center", textfont=dict(size=12, color="white"),
        line=dict(color=color_ag, width=3),
        marker=dict(size=14, color=[colores_semaforo[semaforo(v,"utilizacion")] if v else "#95a5a6" for v in vals_ag],
                   line=dict(width=2, color="white")), name=agente_sel
    ))
    if preds_ag:
        fig_m.add_trace(go.Scatter(
            x=meses_fut_ag, y=preds_ag, mode="lines+markers+text",
            text=[f"{v:.1f}%" for v in preds_ag], textposition="top center",
            textfont=dict(size=11, color="white"), name="Proyección",
            line=dict(color="#9b59b6", dash="dash", width=2),
            marker=dict(size=10, symbol="diamond")
        ))
    fig_m.add_hrect(y0=0,  y1=75,  fillcolor="#e74c3c", opacity=0.05)
    fig_m.add_hrect(y0=75, y1=86,  fillcolor="#f1c40f", opacity=0.05)
    fig_m.add_hrect(y0=86, y1=100, fillcolor="#2ecc71", opacity=0.05)
    fig_m.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Meta 75%")
    fig_m.add_hline(y=86, line_dash="dash", line_color="green", annotation_text="Óptimo 86%")
    fig_m.update_layout(height=400, plot_bgcolor="white", yaxis_range=[0,115])
    st.plotly_chart(fig_m, use_container_width=True, key="fig_m")

    # Evolución semanal con regresión
    st.markdown("#### 📆 Evolución Semanal")
    ag_sem = semanal[semanal["NOMBRE"] == agente_sel].sort_values("Semana")
    if not ag_sem.empty:
        semanas_list = ag_sem["Semana"].tolist()
        vals_sem = ag_sem["Utilizacion"].tolist()
        meses_fut_sem, preds_sem = regresion_3meses(vals_sem, semanas_list)

        fig_s = go.Figure()
        fig_s.add_trace(go.Bar(
            x=semanas_list, y=vals_sem, text=vals_sem,
            texttemplate="%{text:.1f}%", textposition="outside",
            textfont=dict(size=12, color="white"),
            marker_color=[colores_semaforo[semaforo(v,"utilizacion")] for v in vals_sem],
            name="Utilización"
        ))
        if preds_sem:
            fig_s.add_trace(go.Scatter(
                x=meses_fut_sem, y=preds_sem, mode="lines+markers+text",
                text=[f"{v:.1f}%" for v in preds_sem], textposition="top center",
                name="Proyección", line=dict(color="#9b59b6", dash="dash", width=2),
                marker=dict(size=10, symbol="diamond")
            ))
        fig_s.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Meta 75%")
        fig_s.add_hline(y=86, line_dash="dash", line_color="green", annotation_text="Óptimo 86%")
        fig_s.add_hrect(y0=0,  y1=75,  fillcolor="#e74c3c", opacity=0.05)
        fig_s.add_hrect(y0=75, y1=86,  fillcolor="#f1c40f", opacity=0.05)
        fig_s.add_hrect(y0=86, y1=100, fillcolor="#2ecc71", opacity=0.05)
        fig_s.update_layout(height=380, plot_bgcolor="white", yaxis_range=[0,115])
        st.plotly_chart(fig_s, use_container_width=True, key="fig_s")

    # Evolución diaria
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
# TAB 4 — AGENTES CRÍTICOS
# ══════════════════════════════════════════
with tab4:
    st.subheader("🔴 Agentes en Estado Crítico")

    # Histórico de críticos
    criticos_hist = hist_mensual[hist_mensual['Cuartil_Util'] == 'Q1 — Crítico 🔴'].copy()
    if supervisor_sel != "Todos":
        criticos_hist = criticos_hist[criticos_hist["JP"] == supervisor_sel]

    # Métricas
    col_c1, col_c2, col_c3 = st.columns(3)
    col_c1.metric("🔴 Críticos mes actual", len(criticos[criticos["JP"] == supervisor_sel]) if supervisor_sel != "Todos" else len(criticos))
    col_c2.metric("📅 Total apariciones crítico", len(criticos_hist))
    col_c3.metric("👥 Agentes únicos en crítico", criticos_hist["RUT"].nunique() if "RUT" in criticos_hist.columns else "—")

    # Gráfico histórico críticos por mes
    st.markdown("#### 📈 Evolución Agentes Críticos por Mes")
    criticos_mes = criticos_hist.groupby(['Mes','Orden_Mes']).agg(
        Agentes=('NOMBRE','nunique')
    ).reset_index().sort_values('Orden_Mes')

    fig_crit = go.Figure()
    fig_crit.add_trace(go.Bar(
        x=criticos_mes['Mes'], y=criticos_mes['Agentes'],
        text=criticos_mes['Agentes'], textposition='outside',
        marker_color='#e74c3c', name='Agentes críticos'
    ))
    fig_crit.update_layout(height=350, plot_bgcolor="white",
                          title="Agentes en estado crítico por mes")
    st.plotly_chart(fig_crit, use_container_width=True, key="fig_crit")

    # Tabla críticos con veces repetidas
    st.markdown("#### 📋 Detalle Agentes Críticos — Mes Actual")
    criticos_fil = criticos.copy()
    if supervisor_sel != "Todos":
        criticos_fil = criticos_fil[criticos_fil["JP"] == supervisor_sel]

    # Agregar veces en crítico
    if "NOMBRE" in hist_ag.columns and "Veces_Critico" in hist_ag.columns:
        criticos_fil = criticos_fil.merge(
            hist_ag[["NOMBRE","Veces_Critico","Meses_Critico"]],
            on="NOMBRE", how="left"
        )

    criticos_mostrar = criticos_fil.copy()
    for col in ["Utilizacion","Adhesion","Ocupacion"]:
        if col in criticos_mostrar.columns:
            criticos_mostrar[col] = criticos_mostrar[col].apply(
                lambda x: f"{x:.1f}%" if pd.notna(x) else "")
    st.dataframe(criticos_mostrar, use_container_width=True, key="tabla_criticos")

    # Histórico completo críticos
    st.markdown("#### 📅 Histórico Completo — Apariciones en Crítico")
    cols_crit_hist = ["NOMBRE","JP","Mes","Utilizacion","Adhesion","Ocupacion"]
    cols_disp = [c for c in cols_crit_hist if c in criticos_hist.columns]
    tabla_crit_hist = criticos_hist[cols_disp].sort_values(
        ["NOMBRE","Orden_Mes"] if "Orden_Mes" in criticos_hist.columns else ["NOMBRE"]
    ).copy()
    for col in ["Utilizacion","Adhesion","Ocupacion"]:
        if col in tabla_crit_hist.columns:
            tabla_crit_hist[col] = tabla_crit_hist[col].apply(
                lambda x: f"{x:.1f}%" if pd.notna(x) else "")
    st.dataframe(tabla_crit_hist, use_container_width=True, key="tabla_crit_hist")

# ══════════════════════════════════════════
# TAB 5 — CONTROL DE HORAS
# ══════════════════════════════════════════
with tab5:
    st.subheader("⏱️ Control de Horas — Análisis de Fuga")

    vista_hrs = st.radio("Ver por:", ["Mes","Semana","Día"], horizontal=True, key="vista_hrs")
    jp_hrs = ["Todos"] + sorted(hrs_mes["JP"].dropna().unique().tolist())
    jp_sel_hrs = st.selectbox("Filtrar supervisor", jp_hrs, key="jp_hrs")

    if vista_hrs == "Mes":
        data_hrs = hrs_mes.copy()
        titulo_hrs = hoy.strftime('%B %Y')
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

    estados_nombres = {
        'Conectado_hrs':      '🔌 Conectado',
        'Turno_hrs':          '📅 Turno Programado',
        'Hrs_Productivas':    '✅ Total Productivas',
        'Hrs_Improductivas':  '❌ Total Improductivas',
        'EnCola_hrs':         '📞 En Cola',
        'Ocioso_hrs':         '💤 Ocioso',
        'Interactuando_hrs':  '🗣️ Interactuando',
        'Bano_hrs':           '🚽 Baño',
        'AusenteOcupado_hrs': '🚫 Ausente Ocupado',
        'Descanso_hrs':       '☕ Descanso',
        'Comida_hrs':         '🍽️ Comida',
        'Reunion_hrs':        '👥 Reunión',
        'Capacitacion_hrs':   '📚 Capacitación',
        'NoResponde_hrs':     '📵 No Responde',
        'FueraCola_hrs':      '🚪 Fuera de Cola',
        'Gestion_hrs':        '📝 Gestión',
        'LlamadaManual_hrs':  '📲 Llamada Manual',
        'PausaActiva_hrs':    '🏃 Pausa Activa'
    }

    if agente_sel_hrs != "Todos" and len(data_hrs) > 0:
        row_hrs = data_hrs.iloc[0]
        col_h1, col_h2, col_h3, col_h4 = st.columns(4)
        for col_h, label, key_h, color_h in [
            (col_h1, "🔌 Hrs Conexión", "Conectado_hrs", "#3498db"),
            (col_h2, "📅 Hrs Programadas", "Turno_hrs", "#9b59b6"),
            (col_h3, "✅ Hrs Productivas", "Hrs_Productivas", "#2ecc71"),
            (col_h4, "❌ Hrs Improductivas", "Hrs_Improductivas", "#e74c3c")
        ]:
            col_h.markdown(f"""
            <div style='background:{color_h}20; border-left:5px solid {color_h}; padding:10px; border-radius:5px'>
                <p style='margin:0; font-size:13px; color:gray'>{label}</p>
                <p style='margin:0; font-size:18px; font-weight:bold'>{row_hrs.get(key_h,'—')}</p>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")

        estados_graf = {v: row_hrs.get(k,'00:00:00')
                       for k,v in estados_nombres.items()
                       if k not in ['Conectado_hrs','Turno_hrs','Hrs_Productivas','Hrs_Improductivas']}

        estados_min = {k: hhmmss_a_min(v) for k,v in estados_graf.items()}
        total_min = sum(estados_min.values())
        estados_min = {k: v for k,v in estados_min.items() if v > 0}
        estados_sorted = dict(sorted(estados_min.items(), key=lambda x: x[1], reverse=True))

        productivas_labels = ['📞 En Cola','💤 Ocioso','🗣️ Interactuando']
        colores_barra = ['#2ecc71' if k in productivas_labels else '#e74c3c'
                        for k in estados_sorted.keys()]

        textos_barra = [f"{min_a_hhmmss(v)} ({v/total_min*100:.1f}%)" if total_min > 0 else min_a_hhmmss(v)
                       for v in estados_sorted.values()]

        fig_hrs = go.Figure(go.Bar(
            x=list(estados_sorted.values()), y=list(estados_sorted.keys()),
            orientation='h', marker_color=colores_barra,
            text=textos_barra, textposition='outside', textfont=dict(size=11)
        ))
        fig_hrs.update_layout(
            title=f"Horas por Estado — {agente_sel_hrs} — {titulo_hrs}",
            height=520, plot_bgcolor="white", xaxis_title="Minutos"
        )
        st.plotly_chart(fig_hrs, use_container_width=True, key="fig_hrs")

        col_pie1, col_pie2 = st.columns(2)
        with col_pie1:
            prod_min   = sum(v for k,v in estados_min.items() if k in productivas_labels)
            improd_min = sum(v for k,v in estados_min.items() if k not in productivas_labels)
            fig_pie = go.Figure(go.Pie(
                labels=[f'✅ Productivas\n{min_a_hhmmss(prod_min)}',
                        f'❌ Improductivas\n{min_a_hhmmss(improd_min)}'],
                values=[prod_min, improd_min], hole=0.4,
                marker_colors=['#2ecc71','#e74c3c']
            ))
            fig_pie.update_traces(textinfo='label+percent', textfont=dict(size=12))
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
                fig_pie2.update_traces(textinfo='label+percent', textfont=dict(size=11))
                fig_pie2.update_layout(title="🔍 Desglose Improductivas", height=400)
                st.plotly_chart(fig_pie2, use_container_width=True, key="fig_pie2")

    st.markdown("---")
    st.markdown("#### 📋 Tabla Detalle por Estado")
    cols_disp = [c for c in estados_nombres.keys() if c in data_hrs.columns]
    tabla_horas = data_hrs[['NOMBRE'] + cols_disp].copy()
    tabla_horas = tabla_horas.rename(columns=estados_nombres)
    st.dataframe(tabla_horas, use_container_width=True, key="tabla_horas")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align:center; color:gray; font-size:12px'>
    📊 Dashboard KPI — Servicio Técnico ECC &nbsp;|&nbsp;
    👩‍💼 Desarrollado por: <b>Paola Agüero — Analista de Control ECC</b> &nbsp;|&nbsp;
    🐍 Powered by Python & Streamlit
</div>""", unsafe_allow_html=True)
