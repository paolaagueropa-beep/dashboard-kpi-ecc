import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
import numpy as np
import requests
from io import BytesIO
from datetime import date, datetime
import time

st.set_page_config(
    page_title="Dashboard KPI — Servicio Técnico ECC",
    page_icon="📊",
    layout="wide"
)

DRIVE_ID = "1aHTXVmo8zChZTJVMNEKVkjSJkeg1aDJ9"

@st.cache_data(ttl=0)   # TTL=0: Streamlit no expira por tiempo; la invalidación la maneja cache_key
def cargar_datos(cache_key):
    """cache_key cambia cada 5 minutos → refresco automático sin intervención del usuario."""
    # Añadir timestamp al URL para evitar que el CDN de Google Drive sirva versión cacheada
    url = f"https://drive.google.com/uc?export=download&confirm=t&id={DRIVE_ID}&t={cache_key}"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    contenido = BytesIO(response.content)
    hojas = ['Resumen_Agentes','Resumen_Jefatura','JP_Semana','JP_Dia',
             'Historico_Agente','Historico_Mensual','Dist_Cuartiles',
             'Resumen_Semanal','Detalle_Diario','Agentes_Criticos',
             'Horas_Agente_Mes','Horas_Agente_Semana',
             'Horas_Agente_Dia','Horas_JP_Mes','Metadata']
    datos = {}
    for hoja in hojas:
        contenido.seek(0)
        datos[hoja] = pd.read_excel(contenido, sheet_name=hoja)
    return datos

def semaforo_util(val):
    if pd.isna(val): return "Sin datos"
    if val >= 85:    return "🟢 Óptimo"
    elif val >= 75:  return "🟡 Medio"
    else:            return "🔴 Crítico"

def semaforo_adh(val):
    if pd.isna(val):   return "Sin datos"
    if val >= 95:      return "🟢 Óptimo"
    elif val >= 90:    return "🟡 Medio"
    else:              return "🔴 Crítico"

def semaforo_ocu(val):
    if pd.isna(val):   return "Sin datos"
    if 50 <= val <= 55: return "🟢 Óptimo"
    elif (40 <= val < 50) or (55 < val <= 65): return "🟡 Medio"
    else:              return "🔴 Crítico"

def semaforo_rec(val):
    if pd.isna(val): return "Sin datos"
    if val >= 95:    return "🟢 Óptimo"
    elif val >= 85:  return "🟡 Medio"
    else:            return "🔴 Crítico"

colores_semaforo = {
    "🟢 Óptimo": "#2ecc71",
    "🟡 Medio":  "#f1c40f",
    "🔴 Crítico":"#e74c3c",
    "Sin datos": "#95a5a6"
}

def hhmmss_a_min(t):
    try:
        p = str(t).split(':')
        return int(p[0])*60 + int(p[1]) + float(p[2])/60
    except: return 0

def min_a_hhmmss(m):
    try:
        h = int(m//60); mi = int(m%60); s = int((m%1)*60)
        return f"{h:02d}:{mi:02d}:{s:02d}"
    except: return "00:00:00"

def agregar_horas_grupo(df, cols):
    result = {}
    for col in cols:
        if col in df.columns:
            result[col] = df[col].apply(hhmmss_a_min).sum()
        else:
            result[col] = 0
    return result

def antiguedad_texto(fi):
    try:
        if pd.isna(fi): return "Sin dato"
        if isinstance(fi, str): fi = pd.to_datetime(fi)
        hoy = date.today()
        if hasattr(fi, 'date'): fi = fi.date()
        a = hoy.year-fi.year; m = hoy.month-fi.month; d = hoy.day-fi.day
        if d < 0: m -= 1; d += 30
        if m < 0: a -= 1; m += 12
        partes = []
        if a > 0: partes.append(f"{a} año{'s' if a>1 else ''}")
        if m > 0: partes.append(f"{m} mes{'es' if m>1 else ''}")
        if d > 0 and a == 0: partes.append(f"{d} día{'s' if d>1 else ''}")
        return ", ".join(partes) if partes else "Recién ingresado"
    except: return "Sin dato"

def regresion_3meses(valores, meses):
    try:
        datos = [(i,v) for i,v in enumerate(valores) if pd.notna(v)]
        if len(datos) < 2: return [], []
        X = np.array([d[0] for d in datos]).reshape(-1,1)
        y = np.array([d[1] for d in datos])
        mod = LinearRegression().fit(X, y)
        ui = max(d[0] for d in datos)
        preds = mod.predict(np.array([ui+1,ui+2,ui+3]).reshape(-1,1))
        return [f"Proj. {i+1}" for i in range(3)], preds.tolist()
    except: return [], []

def cuartil_rec(v):
    if pd.isna(v):  return 'Sin datos'
    if v >= 85:     return 'Q4 — Óptimo 🟢'
    elif v >= 75:   return 'Q3 — Sobre meta ✅'
    elif v >= 70:   return 'Q2 — Bajo meta ⚠️'
    else:           return 'Q1 — Crítico 🔴'

# ── Header ──
st.title("📊 Dashboard KPI — Servicio Técnico ECC")
hoy = datetime.now()
st.markdown(f"""
<div style='background:#2c3e5020; border-left:5px solid #3498db;
            padding:10px; border-radius:5px; margin-bottom:10px'>
    <span style='font-size:16px'>
        📅 <b>Mes actual:</b> {hoy.strftime('%B %Y')} &nbsp;|&nbsp;
        🕐 <b>Actualizado:</b> {hoy.strftime('%d/%m/%Y %H:%M')} &nbsp;|&nbsp;
        👩‍💼 <b>Creado por:</b> Paola Agüero — Owner Capacidad Operativa
    </span>
</div>""", unsafe_allow_html=True)
st.markdown("---")

# ── Carga de datos con auto-refresh cada 5 minutos ──
# cache_key cambia cada 300 segundos → Streamlit descarga el Excel actualizado
# sin que el usuario tenga que hacer nada
import math
_cache_key_auto = math.floor(time.time() / 300)

# Botón para forzar refresco inmediato (ignora los 5 min y fuerza nueva descarga)
if 'force_refresh' not in st.session_state:
    st.session_state.force_refresh = 0

with st.spinner("⏳ Cargando datos..."):
    try:
        # Usar _cache_key_auto + force_refresh como clave compuesta
        cache_key_final = _cache_key_auto * 10000 + st.session_state.force_refresh
        datos        = cargar_datos(cache_key_final)
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
        meta         = datos['Metadata'].iloc[0]
        techo_p90    = float(meta.get('Techo_Real_P90', 0))
        meses_techo  = meta.get('Meses_Calculados', '')

        # ── Normalizar meses numéricos → nombres ────────────────
        # Defensa extra: si el Excel trae "05" en vez de "Mayo", convertir aquí
        _meses_map = {
            '01':'Enero','02':'Febrero','03':'Marzo','04':'Abril',
            '05':'Mayo','06':'Junio','07':'Julio','08':'Agosto',
            '09':'Septiembre','10':'Octubre','11':'Noviembre','12':'Diciembre',
            '1':'Enero','2':'Febrero','3':'Marzo','4':'Abril',
            '5':'Mayo','6':'Junio','7':'Julio','8':'Agosto',
            '9':'Septiembre',
        }
        def norm_mes(v):
            s = str(v).strip()
            return _meses_map.get(s, s)

        for hoja_mes in ['Dist_Cuartiles','Historico_Mensual']:
            if 'Mes' in datos[hoja_mes].columns:
                datos[hoja_mes]['Mes'] = datos[hoja_mes]['Mes'].apply(norm_mes)
        # ──────────────────────────────────────────────────────────

        st.success("✅ Datos cargados")
    except Exception as e:
        st.error(f"❌ Error: {e}"); st.stop()

# ── Meses en orden (todos los meses del año) ──
meses_orden = ["Septiembre","Octubre","Noviembre","Diciembre",
               "Enero","Febrero","Marzo","Abril",
               "Mayo","Junio","Julio","Agosto"]
ultimos_3 = [m for m in meses_orden if m in hist_ag.columns][-3:]

# ── Calcular Utilizacion_Rec por agente ──
if ultimos_3 and 'Techo_Perfil' in hist_ag.columns:
    hist_ag['Prom_3m']        = hist_ag[ultimos_3].mean(axis=1)
    hist_ag['Utilizacion_Rec'] = (hist_ag['Prom_3m'] / hist_ag['Techo_Perfil'] * 100).round(1).clip(upper=100)
else:
    hist_ag['Prom_3m'] = None; hist_ag['Utilizacion_Rec'] = None

resumen = resumen.merge(
    hist_ag[['NOMBRE','Prom_3m','Utilizacion_Rec','Techo_Perfil']],
    on='NOMBRE', how='left')
if 'Utilizacion_Rec' in resumen.columns:
    resumen['Utilizacion_Rec'] = resumen['Utilizacion_Rec'].clip(upper=100)

# Promedio últimos 3 meses del servicio
top3_meses = [m for m in meses_orden if m in hist_ag.columns][-3:]
if top3_meses:
    sample_val = hist_ag[top3_meses[0]].dropna().mean() if len(hist_ag[top3_meses[0]].dropna()) > 0 else 0
    prom_3m_servicio = round(hist_ag[top3_meses].mean().mean() * (100 if sample_val <= 1 else 1), 1)
else:
    prom_3m_servicio = 0

resumen["Semaforo"]     = resumen["Utilizacion"].apply(semaforo_util)
resumen["Semaforo_Adh"] = resumen["Adhesion"].apply(semaforo_adh)
resumen["Semaforo_Ocu"] = resumen["Ocupacion"].apply(semaforo_ocu)
resumen["Semaforo_Rec"] = resumen["Utilizacion_Rec"].apply(semaforo_util)
resumen["Cuartil_Rec"]  = resumen["Utilizacion_Rec"].apply(cuartil_rec)

# Jefatura Util.Rec y semaforo
if 'Utilizacion_Rec' in resumen.columns and 'JP' in resumen.columns:
    jp_util_rec = resumen.groupby('JP')['Utilizacion_Rec'].mean().reset_index()
    jp_util_rec.columns = ['JP','Utilizacion_Rec']
    jefatura = jefatura.merge(jp_util_rec, on='JP', how='left')
    jefatura['Utilizacion_Rec'] = jefatura['Utilizacion_Rec'].clip(upper=100)
jefatura['Semaforo']     = jefatura['Utilizacion'].apply(semaforo_util)
jefatura['Semaforo_Rec'] = jefatura['Utilizacion_Rec'].apply(semaforo_util)

# ── Sidebar ──
st.sidebar.title("🔍 Filtros")
supervisores   = ["Todos"] + sorted(resumen["JP"].dropna().unique().tolist())
supervisor_sel = st.sidebar.selectbox("Supervisor", supervisores)
contratos      = ["Todos"] + sorted(resumen["HRS_CONTRATO"].dropna().unique().tolist())
contrato_sel   = st.sidebar.selectbox("Horas Contrato", contratos)
antiguedades   = ["Todos"] + sorted(resumen["Tramo_Antiguedad"].dropna().unique().tolist())
antiguedad_sel = st.sidebar.selectbox("Antigüedad", antiguedades)

st.sidebar.markdown("---")
st.sidebar.markdown(f"""
<div style='background:#9b59b620; border-left:4px solid #9b59b6; padding:8px; border-radius:5px'>
    <p style='margin:0; font-size:12px; color:gray'>📊 Techo real servicio (ponderado)</p>
    <p style='margin:0; font-size:22px; font-weight:bold'>{techo_p90:.1f}%</p>
    <p style='margin:0; font-size:11px; color:gray'>Ponderado por perfil | Obj. 86%<br>{meses_techo}</p>
</div>""", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style='background:#1e1e2e; border:1px solid #444; padding:10px; border-radius:8px'>
    <p style='margin:0 0 6px 0; font-size:12px; font-weight:bold; color:#aaa'>📋 Umbrales Semáforo Util.</p>
    <p style='margin:2px 0; font-size:12px'>🟢 <b>Óptimo</b> → ≥ 85%</p>
    <p style='margin:2px 0; font-size:12px'>🟡 <b>Medio</b> → 75% – 84%</p>
    <p style='margin:2px 0; font-size:12px'>🔴 <b>Crítico</b> → &lt; 75%</p>
</div>""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style='background:#1e1e2e; border:1px solid #444; padding:10px; border-radius:8px; margin-top:8px'>
    <p style='margin:0 0 6px 0; font-size:12px; font-weight:bold; color:#aaa'>📊 Umbrales Cuartilización</p>
    <p style='margin:2px 0; font-size:12px'>🟢 <b>Q4 — Óptimo</b> → ≥ 85%</p>
    <p style='margin:2px 0; font-size:12px'>✅ <b>Q3 — Sobre meta</b> → 75%–84%</p>
    <p style='margin:2px 0; font-size:12px'>⚠️ <b>Q2 — Bajo meta</b> → 70%–74%</p>
    <p style='margin:2px 0; font-size:12px'>🔴 <b>Q1 — Crítico</b> → &lt; 70%</p>
</div>""", unsafe_allow_html=True)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refrescar datos ahora"):
    st.session_state.force_refresh = st.session_state.get('force_refresh', 0) + 1
    st.cache_data.clear()
    st.rerun()

df = resumen.copy()
if supervisor_sel != "Todos": df = df[df["JP"] == supervisor_sel]
if contrato_sel   != "Todos": df = df[df["HRS_CONTRATO"] == contrato_sel]
if antiguedad_sel != "Todos": df = df[df["Tramo_Antiguedad"] == antiguedad_sel]

util_prom = df["Utilizacion"].mean()
adh_prom  = df["Adhesion"].mean()
ocu_prom  = df["Ocupacion"].mean()
ocu_min   = (ocu_prom / 100) * 60

# ── Métricas principales ──
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("👥 Agentes", len(df))

niv_util = semaforo_util(util_prom); color_util = colores_semaforo[niv_util]
col2.markdown(f"""
<div style='background:{color_util}20; border-left:5px solid {color_util}; padding:10px; border-radius:5px'>
    <p style='margin:0; font-size:13px; color:gray'>📈 Utilización</p>
    <p style='margin:0; font-size:26px; font-weight:bold'>{util_prom:.1f}%</p>
    <p style='margin:0; font-size:12px'>{niv_util}</p>
    <p style='margin:0; font-size:11px; color:gray'>🎯 Objetivo Cap. Op.: 86%</p>
    <p style='margin:0; font-size:11px; color:#9b59b6'>📊 Techo servicio: {techo_p90:.1f}%</p>
</div>""", unsafe_allow_html=True)

niv_adh = semaforo_adh(adh_prom); color_adh = colores_semaforo[niv_adh]
col3.markdown(f"""
<div style='background:{color_adh}20; border-left:5px solid {color_adh}; padding:10px; border-radius:5px'>
    <p style='margin:0; font-size:13px; color:gray'>✅ Adhesión</p>
    <p style='margin:0; font-size:26px; font-weight:bold'>{adh_prom:.1f}%</p>
    <p style='margin:0; font-size:12px'>{niv_adh}</p>
    <p style='margin:0; font-size:11px; color:gray'>🎯 Objetivo: ≥ 95%</p>
</div>""", unsafe_allow_html=True)

niv_ocu = semaforo_ocu(ocu_prom); color_ocu = colores_semaforo[niv_ocu]
col4.markdown(f"""
<div style='background:{color_ocu}20; border-left:5px solid {color_ocu}; padding:10px; border-radius:5px'>
    <p style='margin:0; font-size:13px; color:gray'>⚡ Ocupación</p>
    <p style='margin:0; font-size:26px; font-weight:bold'>{ocu_prom:.1f}%</p>
    <p style='margin:0; font-size:12px'>{niv_ocu}</p>
    <p style='margin:0; font-size:11px; color:gray'>🎯 Objetivo: 50-55% (≈{ocu_min:.1f} min/hora)</p>
</div>""", unsafe_allow_html=True)

niv_p3m = semaforo_util(prom_3m_servicio); color_p3m = colores_semaforo[niv_p3m]
col5.markdown(f"""
<div style='background:{color_p3m}20; border-left:5px solid {color_p3m}; padding:10px; border-radius:5px'>
    <p style='margin:0; font-size:13px; color:gray'>📅 Prom. últimos 3 meses</p>
    <p style='margin:0; font-size:26px; font-weight:bold'>{prom_3m_servicio:.1f}%</p>
    <p style='margin:0; font-size:12px'>{niv_p3m}</p>
    <p style='margin:0; font-size:11px; color:gray'>{", ".join(ultimos_3)}</p>
</div>""", unsafe_allow_html=True)

st.markdown("---")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Resumen Mensual","🏅 Ranking y Acumulado",
    "👤 Evolución por Agente","🔴 Agentes Críticos",
    "⏱️ Control de Horas","📖 Glosario de Métricas"
])

# ══════════════════════════════════════════
# TAB 1
# ══════════════════════════════════════════
with tab1:
    # Ranking + Semáforo con Utilizacion bruta
    col_izq, col_der = st.columns([3, 2])
    with col_izq:
        st.subheader("🏆 Ranking Utilización por Agente")
        ranking = df.sort_values("Utilizacion", ascending=True).copy()
        fig1 = px.bar(ranking, x="Utilizacion", y="NOMBRE",
                     color="Semaforo", color_discrete_map=colores_semaforo,
                     orientation="h", text="Utilizacion")
        fig1.add_vline(x=75, line_dash="dash", line_color="orange", annotation_text="Mín 75%")
        fig1.add_vline(x=85, line_dash="dash", line_color="green", annotation_text="Óptimo 85%")
        if techo_p90 > 0:
            fig1.add_vline(x=techo_p90, line_dash="dot", line_color="#9b59b6",
                          annotation_text=f"Techo {techo_p90:.1f}%")
        fig1.update_traces(texttemplate="%{text:.1f}%", textposition="outside", textfont=dict(size=11))
        fig1.update_layout(height=620, plot_bgcolor="white", xaxis_title="Utilización (%)")
        st.plotly_chart(fig1, use_container_width=True, key="fig1")

    with col_der:
        st.subheader("🚦 Distribución Semáforo")
        dist = df["Semaforo"].value_counts().reset_index()
        dist.columns = ["Nivel","Agentes"]
        fig2 = px.pie(dist, values="Agentes", names="Nivel",
                     color="Nivel", color_discrete_map=colores_semaforo, hole=0.4)
        fig2.update_traces(textinfo="label+percent+value", textfont=dict(size=12))
        fig2.update_layout(height=320)
        st.plotly_chart(fig2, use_container_width=True, key="fig2")

    # KPIs por jefatura — ancho completo, más espacio
    st.markdown("---")
    st.subheader("👥 KPIs por Jefatura")
    fig3 = go.Figure()
    for kpi, color, label in zip(
        ["Utilizacion","Adhesion","Ocupacion"],
        ["#3498db","#2ecc71","#e67e22"],
        ["Utilización","Adhesión","Ocupación"]
    ):
        if kpi in jefatura.columns:
            fig3.add_trace(go.Bar(name=label, x=jefatura["JP"], y=jefatura[kpi],
                                 text=jefatura[kpi], texttemplate="%{text:.1f}%",
                                 textposition="outside", marker_color=color))
    fig3.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Mín 75%")
    fig3.add_hline(y=85, line_dash="dash", line_color="green",  annotation_text="Óptimo 85%")
    fig3.update_layout(barmode="group", height=420, xaxis_tickangle=-30,
                       plot_bgcolor="white", margin=dict(b=120))
    st.plotly_chart(fig3, use_container_width=True, key="fig3")

    st.markdown("---")
    st.subheader("📈 Evolución Histórica del Servicio")
    meses_disp = [m for m in meses_orden if m in hist_ag.columns]
    promedios  = []
    for m in meses_disp:
        vals = hist_ag[m].dropna()
        if len(vals) > 0:
            v = vals.mean()
            promedios.append(v if v > 1 else v*100)
        else: promedios.append(None)

    meses_fut, preds = regresion_3meses(promedios, meses_disp)
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(
        x=meses_disp, y=promedios, mode="lines+markers+text",
        text=[f"{v:.1f}%" if v else "" for v in promedios],
        textposition="top center", textfont=dict(size=12, color="white"),
        line=dict(color="#3498db", width=3),
        marker=dict(size=12, color=[colores_semaforo[semaforo_util(v)] if v else "#95a5a6" for v in promedios],
                   line=dict(width=2, color="white")), name="Real"))
    if preds:
        fig4.add_trace(go.Scatter(
            x=meses_fut, y=preds, mode="lines+markers+text",
            text=[f"{v:.1f}%" for v in preds], textposition="top center",
            textfont=dict(size=12, color="white"), name="Proyección 3 meses",
            line=dict(color="#9b59b6", dash="dash", width=3),
            marker=dict(size=12, symbol="diamond")))
    fig4.add_hrect(y0=0,  y1=75,  fillcolor="#e74c3c", opacity=0.05)
    fig4.add_hrect(y0=75, y1=85,  fillcolor="#f1c40f", opacity=0.05)
    fig4.add_hrect(y0=85, y1=100, fillcolor="#2ecc71", opacity=0.05)
    fig4.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Mín 75%")
    fig4.add_hline(y=85, line_dash="dash", line_color="green",  annotation_text="Óptimo 85%")
    fig4.add_hline(y=86, line_dash="dot",  line_color="#3498db", annotation_text="Obj. Cap. Op. 86%")
    if techo_p90 > 0:
        fig4.add_hline(y=techo_p90, line_dash="dot", line_color="#9b59b6",
                      annotation_text=f"Techo ponderado {techo_p90:.1f}%")
    fig4.update_layout(height=450, plot_bgcolor="white")
    st.plotly_chart(fig4, use_container_width=True, key="fig4")

    st.subheader("📊 Movimiento de Dotación por Cuartil")
    colores_cuartil = {
        'Q1 — Crítico 🔴':'#e74c3c','Q2 — Bajo meta ⚠️':'#f39c12',
        'Q3 — Sobre meta ✅':'#3498db','Q4 — Óptimo 🟢':'#2ecc71'
    }
    fig_cuartil = px.bar(dist_cuartil.sort_values('Orden_Mes'),
        x='Mes', y='Agentes', color='Cuartil_Util',
        color_discrete_map=colores_cuartil, barmode='stack', text='Agentes')
    fig_cuartil.update_traces(textposition='inside', textfont=dict(size=11))
    fig_cuartil.update_layout(height=400, plot_bgcolor="white")
    st.plotly_chart(fig_cuartil, use_container_width=True, key="fig_cuartil")

    # ── Tabla completa ──
    st.subheader("📋 Resumen Completo por Agente")
    # Merge horas desde hrs_mes para Hrs_Prod_Contrato y Hrs_Productivas
    cols_horas_merge = ['NOMBRE']
    if 'Hrs_Prod_Contrato' in hrs_mes.columns: cols_horas_merge.append('Hrs_Prod_Contrato')
    if 'Hrs_Productivas'   in hrs_mes.columns: cols_horas_merge.append('Hrs_Productivas')
    df_tabla = df.merge(hrs_mes[cols_horas_merge], on='NOMBRE', how='left')

    cols_t = ["NOMBRE","JP","HRS_CONTRATO","ESTADO","Tramo_Antiguedad",
              "Dias_trabajados","Utilizacion","Util. Rec. (%techo)",
              "Hrs. Prod. Cont.","Hrs. Prod. Reales",
              "Adhesion","Ocupacion","Cuartil"]

    # Preparar columnas
    if "Utilizacion_Rec" in df_tabla.columns:
        df_tabla["Util. Rec. (%techo)"] = df_tabla["Utilizacion_Rec"].apply(
            lambda x: f"{min(float(x),100.0):.1f}%" if pd.notna(x) else "")
    if "Hrs_Prod_Contrato_y" in df_tabla.columns:
        df_tabla["Hrs. Prod. Cont."] = df_tabla["Hrs_Prod_Contrato_y"]
    elif "Hrs_Prod_Contrato" in df_tabla.columns:
        df_tabla["Hrs. Prod. Cont."] = df_tabla["Hrs_Prod_Contrato"]
    if "Hrs_Productivas" in df_tabla.columns:
        df_tabla["Hrs. Prod. Reales"] = df_tabla["Hrs_Productivas"]
    if "Cuartil_Rec" in df_tabla.columns:
        df_tabla["Cuartil"] = df_tabla["Cuartil_Rec"]
    elif "Cuartil_Util" in df_tabla.columns:
        df_tabla["Cuartil"] = df_tabla["Cuartil_Util"]

    df_tabla = df_tabla.sort_values("Utilizacion", ascending=False)
    for col in ["Utilizacion","Adhesion","Ocupacion"]:
        if col in df_tabla.columns:
            df_tabla[col] = df_tabla[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "")

    cols_show = [c for c in cols_t if c in df_tabla.columns]
    st.dataframe(df_tabla[cols_show], use_container_width=True, key="tabla1")

# ══════════════════════════════════════════
# TAB 2
# ══════════════════════════════════════════
with tab2:
    st.subheader("🏅 Ranking y Acumulado por Período")
    periodo = st.radio("Ver por:", ["Mes","Semana","Día"], horizontal=True, key="periodo_tab2")

    if periodo == "Mes":
        data_jp = jefatura.copy(); data_ag = resumen.copy()
        titulo_periodo = hoy.strftime('%B %Y')
        kpi_util = "Utilizacion"; kpi_label = "Utilización (%)"; sfn_tab2 = semaforo_util
    elif periodo == "Semana":
        semanas_disp = sorted(jp_semana["Semana"].dropna().unique().tolist())
        semana_sel = st.selectbox("Selecciona semana", semanas_disp, key="semana_tab2")
        data_jp = jp_semana[jp_semana["Semana"]==semana_sel].copy()
        data_ag = semanal[semanal["Semana"]==semana_sel].copy()
        titulo_periodo = semana_sel
        kpi_util = "Utilizacion"; kpi_label = "Utilización (%)"; sfn_tab2 = semaforo_util
    else:
        fechas_disp = sorted(jp_dia["Fecha"].dropna().unique().tolist())
        fecha_sel = st.selectbox("Selecciona fecha", fechas_disp, key="fecha_tab2")
        data_jp = jp_dia[jp_dia["Fecha"]==fecha_sel].copy()
        data_ag = diario[diario["Fecha"]==fecha_sel].dropna(subset=["Utilizacion"]).copy()
        titulo_periodo = str(fecha_sel)
        kpi_util = "Utilizacion"; kpi_label = "Utilización (%)"; sfn_tab2 = semaforo_util

    sem_col = "Sem_t2"
    if kpi_util in data_jp.columns: data_jp[sem_col] = data_jp[kpi_util].apply(sfn_tab2)
    if kpi_util in data_ag.columns: data_ag[sem_col] = data_ag[kpi_util].apply(sfn_tab2)

    st.markdown(f"### 👔 Ranking Supervisores — {titulo_periodo}")
    col_r1, col_r2 = st.columns([2,1])
    with col_r1:
        if kpi_util in data_jp.columns:
            fig_jp = px.bar(data_jp.sort_values(kpi_util, ascending=True),
                           x=kpi_util, y="JP", color=sem_col,
                           color_discrete_map=colores_semaforo, orientation="h", text=kpi_util)
            fig_jp.add_vline(x=75, line_dash="dash", line_color="orange", annotation_text="Mín 75%")
            fig_jp.add_vline(x=85, line_dash="dash", line_color="green", annotation_text="Óptimo 85%")
            fig_jp.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_jp.update_layout(height=450, plot_bgcolor="white", xaxis_title=kpi_label)
            st.plotly_chart(fig_jp, use_container_width=True, key="fig_jp")

    with col_r2:
        if kpi_util in data_jp.columns:
            st.markdown("#### 🥇 Top 3 Mejor")
            for i,(_, row) in enumerate(data_jp.sort_values(kpi_util, ascending=False).head(3).iterrows()):
                val = row.get(kpi_util, 0) or 0; c = colores_semaforo[sfn_tab2(val)]
                st.markdown(f"""<div style='background:{c}20; border-left:4px solid {c};
                    padding:8px; border-radius:5px; margin-bottom:8px'>
                    <b>{"🥇🥈🥉"[i]} {" ".join(str(row["JP"]).split()[:2])}</b><br>
                    {kpi_label}: <b>{val:.1f}%</b></div>""", unsafe_allow_html=True)
            st.markdown("#### ⚠️ Top 3 Menor")
            for _, row in data_jp.sort_values(kpi_util).head(3).iterrows():
                val = row.get(kpi_util, 0) or 0; c = colores_semaforo[sfn_tab2(val)]
                st.markdown(f"""<div style='background:{c}20; border-left:4px solid {c};
                    padding:8px; border-radius:5px; margin-bottom:8px'>
                    <b>⚠️ {" ".join(str(row["JP"]).split()[:2])}</b><br>
                    {kpi_label}: <b>{val:.1f}%</b></div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"### 👤 Top 10 Agentes — {titulo_periodo}")
    if kpi_util in data_ag.columns:
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown("#### 🥇 Top 10 Mejor Performance")
            top10m = data_ag.sort_values(kpi_util, ascending=False).head(10).copy()
            top10m[sem_col] = top10m[kpi_util].apply(sfn_tab2)
            fig10m = px.bar(top10m, x=kpi_util, y="NOMBRE", color=sem_col,
                           color_discrete_map=colores_semaforo, orientation="h", text=kpi_util)
            fig10m.add_vline(x=75, line_dash="dash", line_color="orange")
            fig10m.add_vline(x=85, line_dash="dash", line_color="green")
            fig10m.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig10m.update_layout(height=400, plot_bgcolor="white", showlegend=False)
            st.plotly_chart(fig10m, use_container_width=True, key="fig_top10m")
        with col_t2:
            st.markdown("#### ⚠️ Top 10 Menor Performance")
            top10mn = data_ag.sort_values(kpi_util).head(10).copy()
            top10mn[sem_col] = top10mn[kpi_util].apply(sfn_tab2)
            fig10mn = px.bar(top10mn, x=kpi_util, y="NOMBRE", color=sem_col,
                            color_discrete_map=colores_semaforo, orientation="h", text=kpi_util)
            fig10mn.add_vline(x=75, line_dash="dash", line_color="orange")
            fig10mn.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig10mn.update_layout(height=400, plot_bgcolor="white", showlegend=False)
            st.plotly_chart(fig10mn, use_container_width=True, key="fig_top10mn")

    st.markdown("---")
    st.markdown(f"### 📋 Ranking Completo — {titulo_periodo}")
    if kpi_util in data_ag.columns:
        jp_opc = ["Todos"] + sorted(data_ag["JP"].dropna().unique().tolist())
        jp_fil = st.selectbox("Filtrar supervisor", jp_opc, key="jp_rank")
        dag = data_ag[data_ag["JP"]==jp_fil].copy() if jp_fil != "Todos" else data_ag.copy()
        dag[sem_col] = dag[kpi_util].apply(sfn_tab2)
        dag = dag.sort_values(kpi_util, ascending=True)
        fig_ag = px.bar(dag, x=kpi_util, y="NOMBRE", color=sem_col,
                       color_discrete_map=colores_semaforo, orientation="h", text=kpi_util)
        fig_ag.add_vline(x=75, line_dash="dash", line_color="orange", annotation_text="Mín 75%")
        fig_ag.add_vline(x=85, line_dash="dash", line_color="green", annotation_text="Óptimo 85%")
        fig_ag.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_ag.update_layout(height=600, plot_bgcolor="white", xaxis_title=kpi_label)
        st.plotly_chart(fig_ag, use_container_width=True, key="fig_ag")

        col_m1,col_m2,col_m3,col_m4 = st.columns(4)
        col_m1.metric("👥 Agentes", len(dag))
        for cm, lb, kpi, sfn in [
            (col_m2,"📈 Utilización","Utilizacion",semaforo_util),
            (col_m3,"✅ Adhesión","Adhesion",semaforo_adh),
            (col_m4,"⚡ Ocupación","Ocupacion",semaforo_ocu)
        ]:
            if kpi in dag.columns:
                v = dag[kpi].mean(); nv = sfn(v); cv = colores_semaforo[nv]
                cm.markdown(f"""<div style='background:{cv}20; border-left:5px solid {cv}; padding:10px; border-radius:5px'>
                    <p style='margin:0; font-size:13px; color:gray'>{lb}</p>
                    <p style='margin:0; font-size:24px; font-weight:bold'>{v:.1f}%</p>
                    <p style='margin:0; font-size:12px'>{nv}</p></div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════
# TAB 3
# ══════════════════════════════════════════
with tab3:
    st.subheader("👤 Evolución Histórica por Agente")
    col_a, col_b = st.columns(2)
    with col_a:
        sup_ag = st.selectbox("Filtrar supervisor",
            ["Todos"] + sorted(hist_ag["JP"].dropna().unique().tolist()), key="sup_ag")
    hist_fil = hist_ag[hist_ag["JP"]==sup_ag].copy() if sup_ag != "Todos" else hist_ag.copy()
    with col_b:
        agente_sel = st.selectbox("Selecciona agente",
            sorted(hist_fil["NOMBRE"].dropna().unique().tolist()), key="agente_sel")

    ag = hist_fil[hist_fil["NOMBRE"]==agente_sel].iloc[0]
    estado    = ag.get("ESTADO","Sin dato")
    contrato  = ag.get("HRS_CONTRATO","Sin dato")
    ant_texto = antiguedad_texto(ag.get("FECHA_INGRESO"))
    promedio  = ag.get("Promedio_historico", 0)
    tendencia = ag.get("Tendencia","Sin dato")
    sem_ag    = ag.get("Semaforo_historico","Sin datos")
    color_ag  = colores_semaforo.get(sem_ag,"#95a5a6")
    veces_crit = ag.get("Veces_Critico", 0)
    meses_crit = ag.get("Meses_Critico","—")
    techo_ag   = ag.get("Techo_Perfil", None)

    # Utilización mes en curso (bruta) — semaforo_util
    ag_resumen = resumen[resumen["NOMBRE"]==agente_sel]
    if not ag_resumen.empty and "Utilizacion" in ag_resumen.columns:
        util_mes_raw = ag_resumen["Utilizacion"].values[0]
        util_mes_bruta = float(util_mes_raw) if pd.notna(util_mes_raw) else None
    else:
        util_mes_bruta = None
    util_mes_txt = f"{util_mes_bruta:.1f}%" if util_mes_bruta is not None else "—"
    sem_actual   = semaforo_util(util_mes_bruta) if util_mes_bruta is not None else "Sin datos"
    color_actual = colores_semaforo.get(sem_actual, "#95a5a6")

    ag_hrs = hrs_mes[hrs_mes["NOMBRE"]==agente_sel]
    h_con = h_pro = h_imp = h_tur = h_dis = h_des = h_exc = h_prod_cont = "—"
    if not ag_hrs.empty:
        r = ag_hrs.iloc[0]
        h_con  = r.get("Conectado_hrs","—"); h_tur = r.get("Turno_hrs","—")
        h_pro  = r.get("Hrs_Productivas","—"); h_imp = r.get("Hrs_Improductivas","—")
        h_dis  = r.get("Disponible_hrs","—"); h_des = r.get("Desconexion_hrs","—")
        h_exc  = r.get("Descanso_Exceso_hrs","—")
        h_prod_cont = r.get("Hrs_Prod_Contrato","—")

    techo_txt = f"{techo_ag:.1f}%" if techo_ag and pd.notna(techo_ag) else "—"

    st.markdown(f"""
    <div style='background:{color_actual}20; border-left:5px solid {color_actual};
                padding:15px; border-radius:8px; margin-bottom:15px'>
        <h4 style='margin:0'>{agente_sel} &nbsp;
            <span style='font-size:14px; font-weight:normal; color:gray'>
            | Utilización mes en curso: <b style='color:white'>{util_mes_txt}</b>
            &nbsp; {sem_actual}
            </span>
        </h4>
        <p style='margin:5px 0'>
            📋 Estado: <b>{estado}</b> &nbsp;|&nbsp;
            ⏰ Contrato: <b>{contrato} hrs</b> &nbsp;|&nbsp;
            📅 Antigüedad: <b>{ant_texto}</b> &nbsp;|&nbsp;
            📊 Prom. histórico: <b>{promedio:.1f}%</b> ({sem_ag}) &nbsp;|&nbsp;
            🎯 Techo perfil: <b>{techo_txt}</b> &nbsp;|&nbsp;
            🎯 Obj. Cap.Op.: <b>86%</b> &nbsp;|&nbsp;
            📊 Techo servicio: <b>{techo_p90:.1f}%</b> &nbsp;|&nbsp;
            {tendencia}
        </p>
        <p style='margin:5px 0; font-size:13px'>
            🔌 Conectado: <b>{h_con}</b> &nbsp;|&nbsp;
            📅 Programado: <b>{h_tur}</b> &nbsp;|&nbsp;
            📋 Prod. Contrato: <b>{h_prod_cont}</b> &nbsp;|&nbsp;
            ✅ Prod. Reales: <b>{h_pro}</b> &nbsp;|&nbsp;
            ❌ Improductivas: <b>{h_imp}</b>
        </p>
        <p style='margin:5px 0; font-size:13px'>
            🟡 Disponible: <b>{h_dis}</b> &nbsp;|&nbsp;
            ⚫ Desconexión: <b>{h_des}</b> &nbsp;|&nbsp;
            ⏰ Exceso descanso: <b>{h_exc}</b> &nbsp;|&nbsp;
            🔴 Veces crítico: <b>{int(veces_crit)}</b> ({meses_crit})
        </p>
    </div>""", unsafe_allow_html=True)

    st.markdown("#### 📅 Evolución Mensual")
    meses_ag = [m for m in meses_orden if m in hist_ag.columns]
    vals_ag  = []
    for m in meses_ag:
        val = ag.get(m)
        vals_ag.append(float(val) if pd.notna(val) and float(val) > 1 else float(val)*100 if pd.notna(val) else None)

    meses_fut_ag, preds_ag = regresion_3meses(vals_ag, meses_ag)
    fig_m = go.Figure()
    fig_m.add_trace(go.Scatter(
        x=meses_ag, y=vals_ag, mode="lines+markers+text",
        text=[f"{v:.1f}%" if v else "" for v in vals_ag],
        textposition="top center", textfont=dict(size=12, color="white"),
        line=dict(color=color_ag, width=3),
        marker=dict(size=14, color=[colores_semaforo[semaforo_util(v)] if v else "#95a5a6" for v in vals_ag],
                   line=dict(width=2, color="white")), name=agente_sel))
    if preds_ag:
        fig_m.add_trace(go.Scatter(
            x=meses_fut_ag, y=preds_ag, mode="lines+markers+text",
            text=[f"{v:.1f}%" for v in preds_ag], textposition="top center",
            textfont=dict(size=11), name="Proyección",
            line=dict(color="#9b59b6", dash="dash", width=2),
            marker=dict(size=10, symbol="diamond")))
    if techo_ag and pd.notna(techo_ag):
        fig_m.add_hline(y=float(techo_ag), line_dash="dot", line_color="#9b59b6",
                       annotation_text=f"Techo perfil {techo_ag:.1f}%")
    fig_m.add_hrect(y0=0,  y1=75,  fillcolor="#e74c3c", opacity=0.05)
    fig_m.add_hrect(y0=75, y1=85,  fillcolor="#f1c40f", opacity=0.05)
    fig_m.add_hrect(y0=85, y1=100, fillcolor="#2ecc71", opacity=0.05)
    fig_m.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Mín 75%")
    fig_m.add_hline(y=85, line_dash="dash", line_color="green",  annotation_text="Óptimo 85%")
    fig_m.update_layout(height=400, plot_bgcolor="white", yaxis_range=[0,115])
    st.plotly_chart(fig_m, use_container_width=True, key="fig_m")

    st.markdown("#### 📆 Evolución Semanal")
    ag_sem = semanal[semanal["NOMBRE"]==agente_sel].sort_values("Semana")
    if not ag_sem.empty:
        sl = ag_sem["Semana"].tolist(); vs = ag_sem["Utilizacion"].tolist()
        mf_s, pr_s = regresion_3meses(vs, sl)
        fig_s = go.Figure()
        fig_s.add_trace(go.Bar(x=sl, y=vs, text=vs, texttemplate="%{text:.1f}%",
            textposition="outside",
            marker_color=[colores_semaforo[semaforo_util(v)] for v in vs], name="Utilización"))
        if pr_s:
            fig_s.add_trace(go.Scatter(x=mf_s, y=pr_s, mode="lines+markers+text",
                text=[f"{v:.1f}%" for v in pr_s], textposition="top center",
                name="Proyección", line=dict(color="#9b59b6", dash="dash", width=2),
                marker=dict(size=10, symbol="diamond")))
        fig_s.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Mín 75%")
        fig_s.add_hline(y=85, line_dash="dash", line_color="green", annotation_text="Óptimo 85%")
        fig_s.add_hrect(y0=0, y1=75, fillcolor="#e74c3c", opacity=0.05)
        fig_s.add_hrect(y0=75,y1=85, fillcolor="#f1c40f", opacity=0.05)
        fig_s.add_hrect(y0=85,y1=100,fillcolor="#2ecc71", opacity=0.05)
        fig_s.update_layout(height=380, plot_bgcolor="white", yaxis_range=[0,115])
        st.plotly_chart(fig_s, use_container_width=True, key="fig_s")

    st.markdown("#### 📊 Evolución Diaria")
    ag_dia = diario[diario["NOMBRE"]==agente_sel].dropna(subset=["Utilizacion"]).sort_values("Fecha")
    if not ag_dia.empty:
        fig_d = go.Figure()
        fig_d.add_trace(go.Scatter(
            x=ag_dia["Fecha"].astype(str), y=ag_dia["Utilizacion"],
            mode="lines+markers+text", text=[f"{v:.1f}%" for v in ag_dia["Utilizacion"]],
            textposition="top center", line=dict(color=color_ag, width=2),
            marker=dict(size=10, color=[colores_semaforo[semaforo_util(v)] for v in ag_dia["Utilizacion"]],
                       line=dict(width=2, color="white"))))
        fig_d.add_hrect(y0=0, y1=75, fillcolor="#e74c3c", opacity=0.05)
        fig_d.add_hrect(y0=75,y1=85, fillcolor="#f1c40f", opacity=0.05)
        fig_d.add_hrect(y0=85,y1=100,fillcolor="#2ecc71", opacity=0.05)
        fig_d.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Mín 75%")
        fig_d.add_hline(y=85, line_dash="dash", line_color="green",  annotation_text="Óptimo 85%")
        fig_d.update_layout(height=400, plot_bgcolor="white", yaxis_range=[0,115], xaxis_tickangle=-45)
        st.plotly_chart(fig_d, use_container_width=True, key="fig_d")

# ══════════════════════════════════════════
# TAB 4
# ══════════════════════════════════════════
with tab4:
    st.subheader("🔴 Agentes en Estado Crítico")
    crit_hist = hist_mensual[hist_mensual['Cuartil_Util']=='Q1 — Crítico 🔴'].copy()
    if supervisor_sel != "Todos": crit_hist = crit_hist[crit_hist["JP"]==supervisor_sel]
    crit_fil = criticos.copy()
    if supervisor_sel != "Todos": crit_fil = crit_fil[crit_fil["JP"]==supervisor_sel]

    st.metric("🔴 Críticos mes actual", len(crit_fil))

    st.markdown("#### 📈 Evolución Críticos por Mes")
    cm = crit_hist.groupby(['Mes','Orden_Mes']).agg(Agentes=('NOMBRE','nunique')).reset_index().sort_values('Orden_Mes')
    fig_crit = go.Figure()
    fig_crit.add_trace(go.Bar(x=cm['Mes'], y=cm['Agentes'], text=cm['Agentes'],
                             textposition='outside', marker_color='#e74c3c'))
    fig_crit.update_layout(height=350, plot_bgcolor="white")
    st.plotly_chart(fig_crit, use_container_width=True, key="fig_crit")

    st.markdown("#### 📋 Detalle Críticos — Mes Actual")
    if "NOMBRE" in hist_ag.columns and "Veces_Critico" in hist_ag.columns:
        crit_fil = crit_fil.merge(hist_ag[["NOMBRE","Veces_Critico","Meses_Critico"]],
                                  on="NOMBRE", how="left")
    if "Utilizacion_Rec" in resumen.columns:
        crit_fil = crit_fil.merge(resumen[["NOMBRE","Utilizacion_Rec"]], on="NOMBRE", how="left")
        crit_fil["Utilizacion_Rec"] = crit_fil["Utilizacion_Rec"].clip(upper=100)

    cols_crit = ["NOMBRE","JP","Utilizacion","Utilizacion_Rec","Adhesion","Ocupacion","Veces_Critico","Meses_Critico"]
    cm2 = crit_fil[[c for c in cols_crit if c in crit_fil.columns]].copy()
    cm2 = cm2.rename(columns={"Utilizacion":"Util. (%)","Utilizacion_Rec":"Util.Rec.(%techo)"})
    for col in ["Util. (%)","Adhesion","Ocupacion"]:
        if col in cm2.columns: cm2[col] = cm2[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "")
    if "Util.Rec.(%techo)" in cm2.columns:
        cm2["Util.Rec.(%techo)"] = cm2["Util.Rec.(%techo)"].apply(
            lambda x: f"{min(float(x),100.0):.1f}%" if pd.notna(x) else "")
    st.dataframe(cm2, use_container_width=True, key="tabla_criticos")

    st.markdown("#### 📅 Histórico Completo — Apariciones en Crítico")
    cols_ch = ["NOMBRE","JP","Mes","Utilizacion","Adhesion","Ocupacion"]
    tch = crit_hist[[c for c in cols_ch if c in crit_hist.columns]].sort_values(["NOMBRE"]).copy()
    tch = tch.rename(columns={"Utilizacion":"Util. ese mes"})
    for col in ["Util. ese mes","Adhesion","Ocupacion"]:
        if col in tch.columns: tch[col] = tch[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "")
    st.dataframe(tch, use_container_width=True, key="tabla_crit_hist")

# ══════════════════════════════════════════
# TAB 5
# ══════════════════════════════════════════
with tab5:
    st.subheader("⏱️ Control de Horas — Análisis de Fuga")

    vista = st.radio("Ver por:", ["Mes","Semana","Día"], horizontal=True, key="vista_hrs")
    jp_h  = ["Todos"] + sorted(hrs_mes["JP"].dropna().unique().tolist())
    jp_sel = st.selectbox("Filtrar supervisor", jp_h, key="jp_hrs")

    if vista == "Mes":
        dh = hrs_mes.copy(); th = hoy.strftime('%B %Y')
    elif vista == "Semana":
        sems = sorted(hrs_sem["Semana"].dropna().unique().tolist())
        ss = st.selectbox("Selecciona semana", sems, key="sem_hrs")
        dh = hrs_sem[hrs_sem["Semana"]==ss].copy(); th = ss
    else:
        fecs = sorted(hrs_dia["Fecha"].dropna().unique().tolist())
        fs = st.selectbox("Selecciona fecha", fecs, key="fecha_hrs")
        dh = hrs_dia[hrs_dia["Fecha"]==fs].copy(); th = str(fs)

    if jp_sel != "Todos": dh = dh[dh["JP"]==jp_sel]
    ags_h  = ["Todos"] + sorted(dh["NOMBRE"].dropna().unique().tolist())
    ag_sel = st.selectbox("Filtrar agente", ags_h, key="agente_hrs")
    if ag_sel != "Todos": dh = dh[dh["NOMBRE"]==ag_sel]

    estados_graf = {
        'EnCola_hrs':           '📞 En Cola',
        'Ocioso_hrs':           '💤 Ocioso',
        'Interactuando_hrs':    '🗣️ Interactuando',
        'Disponible_hrs':       '🟡 Disponible',
        'Bano_hrs':             '🚽 Baño',
        'AusenteOcupado_hrs':   '🚫 Ausente Ocupado',
        'Descanso_Exceso_hrs':  '⚠️ Exceso Descanso/Comida',
        'Reunion_hrs':          '👥 Reunión',
        'Capacitacion_hrs':     '📚 Capacitación',
        'NoResponde_hrs':       '📵 No Responde',
        'Gestion_hrs':          '📝 Gestión',
        'LlamadaManual_hrs':    '📲 Llamada Manual',
        'PausaActiva_hrs':      '🏃 Pausa Activa',
        'Desconexion_hrs':      '⚫ Desconexión Total'
    }

    # Tabla con orden y columnas actualizadas
    estados_tabla = {
        'Turno_hrs':          '📅 Hrs turno prog.',
        'Conectado_hrs':      '🔌 Hrs. Conexión total',
        'Hrs_Prod_Contrato':  '📋 Hrs prod. Cont.',
        'Hrs_Productivas':    '✅ Hrs. Prod. Reales',
        'Hrs_Improductivas':  '❌ Hrs. Improd. Reales',
        'Desconexion_hrs':    '⚫ Desconexión',
        'Disponible_hrs':     '🟡 Disponible',
        'EnCola_hrs':         '📞 En Cola',
        'Ocioso_hrs':         '💤 Ocioso',
        'Interactuando_hrs':  '🗣️ Interactuando',
        'Descanso_hrs':       '☕ Descanso real',
        'Comida_hrs':         '🍽️ Comida real',
        'Descanso_Exceso_hrs':'⚠️ Exceso descanso',
        'Bano_hrs':           '🚽 Baño',
        'AusenteOcupado_hrs': '🚫 Ausente Ocupado',
        'Reunion_hrs':        '👥 Reunión',
        'Capacitacion_hrs':   '📚 Capacitación',
        'NoResponde_hrs':     '📵 No Responde',
        'Gestion_hrs':        '📝 Gestión',
        'LlamadaManual_hrs':  '📲 Llamada Manual',
        'PausaActiva_hrs':    '🏃 Pausa Activa'
    }

    prod_labels = ['📞 En Cola','💤 Ocioso','🗣️ Interactuando']

    def render_graficos_horas(row_data_min, titulo_graf, key_prefix):
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        metricas_orden = [
            (c1,"📅 Programado",     "Turno_hrs",          "#9b59b6"),
            (c2,"🔌 Conectado",      "Conectado_hrs",      "#3498db"),
            (c3,"✅ Productivas",    "Hrs_Productivas",    "#2ecc71"),
            (c4,"❌ Improductivas",  "Hrs_Improductivas",  "#e74c3c"),
            (c5,"🟡 Disponible",     "Disponible_hrs",     "#f39c12"),
            (c6,"⚫ Desconexión",    "Desconexion_hrs",    "#7f8c8d")
        ]
        for ch, lb, kh, co in metricas_orden:
            val_min = row_data_min.get(kh, 0)
            ch.markdown(f"""<div style='background:{co}20; border-left:4px solid {co};
                padding:8px; border-radius:5px'>
                <p style='margin:0; font-size:11px; color:gray'>{lb}</p>
                <p style='margin:0; font-size:15px; font-weight:bold'>{min_a_hhmmss(val_min)}</p>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")

        estados_min = {}
        for k, v in estados_graf.items():
            mv = row_data_min.get(k, 0)
            if mv > 0: estados_min[v] = mv

        total_min = sum(estados_min.values())
        est_sort = dict(sorted(estados_min.items(), key=lambda x: x[1], reverse=True))
        est_sort_hrs = {k: v/60 for k,v in est_sort.items()}

        colores_b = []
        for k in est_sort_hrs:
            if k in prod_labels:              colores_b.append('#2ecc71')
            elif k == '⚫ Desconexión Total': colores_b.append('#7f8c8d')
            elif k == '🟡 Disponible':        colores_b.append('#f39c12')
            elif k == '⚠️ Exceso Descanso/Comida': colores_b.append('#e67e22')
            else:                              colores_b.append('#e74c3c')

        textos_b = [f"{min_a_hhmmss(v*60)} ({v*60/total_min*100:.1f}%)" if total_min > 0 else min_a_hhmmss(v*60)
                   for v in est_sort_hrs.values()]

        fig_hrs = go.Figure(go.Bar(
            x=list(est_sort_hrs.values()), y=list(est_sort_hrs.keys()),
            orientation='h', marker_color=colores_b,
            text=textos_b, textposition='outside', textfont=dict(size=11)))
        fig_hrs.update_layout(title=f"Horas por Estado — {titulo_graf}",
            height=560, plot_bgcolor="white", xaxis_title="Horas", margin=dict(t=60))
        st.plotly_chart(fig_hrs, use_container_width=True, key=f"fig_hrs_{key_prefix}")

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            pm  = row_data_min.get('Hrs_Productivas', 0)
            im  = row_data_min.get('Hrs_Improductivas', 0)
            dm  = row_data_min.get('Desconexion_hrs', 0)
            dm2 = row_data_min.get('Disponible_hrs', 0)
            fig_pie = go.Figure(go.Pie(
                labels=[f'✅ Productivas\n{min_a_hhmmss(pm)}',
                        f'❌ Improductivas\n{min_a_hhmmss(im)}',
                        f'🟡 Disponible\n{min_a_hhmmss(dm2)}',
                        f'⚫ Desconexión\n{min_a_hhmmss(dm)}'],
                values=[pm, im, dm2, dm], hole=0.4,
                marker_colors=['#2ecc71','#e74c3c','#f39c12','#7f8c8d']))
            fig_pie.update_traces(textinfo='label+percent', textfont=dict(size=11))
            fig_pie.update_layout(title="Distribución de Horas", height=450, margin=dict(t=60))
            st.plotly_chart(fig_pie, use_container_width=True, key=f"fig_pie_{key_prefix}")

        with col_p2:
            imp_est = {k:v for k,v in estados_min.items()
                      if k not in prod_labels
                      and k not in ['⚫ Desconexión Total','🟡 Disponible']
                      and v > 0}
            if imp_est:
                labels_imp = [f"{k}\n{min_a_hhmmss(v)}" for k,v in imp_est.items()]
                fig_p2 = go.Figure(go.Pie(labels=labels_imp, values=list(imp_est.values()), hole=0.4))
                fig_p2.update_traces(textinfo='label+percent', textfont=dict(size=11),
                                    hovertemplate='%{label}<br>%{percent}')
                fig_p2.update_layout(title="🔍 Desglose Improductivas",
                    height=450, margin=dict(t=60), showlegend=True)
                st.plotly_chart(fig_p2, use_container_width=True, key=f"fig_pie2_{key_prefix}")

        # Nota contextual No Responde — al final
        st.markdown("""
<div style='background:#2c3e5020; border-left:4px solid #3498db;
            padding:10px; border-radius:5px; margin-top:12px; font-size:13px'>
    📵 <b>Nota — Estado "No Responde":</b> Activado <b>automáticamente por el sistema IVR</b>
    cuando una llamada queda en espera y el agente no retorna a la cola.
    <b>No es seleccionado manualmente.</b> Un volumen elevado puede indicar
    una falla puntual de Genesys Cloud o falta de alerta del agente. &nbsp;
    ⚠️ <b>Este tiempo NO afecta el cálculo de Utilización.</b>
</div>""", unsafe_allow_html=True)

    all_cols_hrs = list(estados_graf.keys()) + ["Conectado_hrs","Turno_hrs",
                   "Hrs_Productivas","Hrs_Improductivas","Disponible_hrs","Desconexion_hrs",
                   "Hrs_Prod_Contrato"]

    if ag_sel != "Todos" and len(dh) > 0:
        rh = dh.iloc[0]
        row_min = {col: hhmmss_a_min(rh.get(col,'00:00:00')) for col in all_cols_hrs}
        render_graficos_horas(row_min, f"{ag_sel} — {th}", "ag")

    elif ag_sel == "Todos" and len(dh) > 0:
        titulo_agg = f"{jp_sel} — {th}" if jp_sel != "Todos" else f"Servicio completo — {th}"
        alcance_txt = f"Supervisor: **{jp_sel}**" if jp_sel != "Todos" else "**Todo el servicio**"
        st.info(f"📊 Vista agregada — {alcance_txt} | {len(dh)} agentes")
        row_min_agg = agregar_horas_grupo(dh, all_cols_hrs)
        render_graficos_horas(row_min_agg, titulo_agg, "agg")

    st.markdown("---")
    st.markdown("#### 📋 Tabla Detalle por Estado")
    cols_d = [c for c in estados_tabla if c in dh.columns]
    th_tabla = dh[['NOMBRE'] + cols_d].copy().rename(columns=estados_tabla)
    st.dataframe(th_tabla, use_container_width=True, key="tabla_horas")

# ══════════════════════════════════════════
# TAB 6 — GLOSARIO
# ══════════════════════════════════════════
with tab6:
    st.subheader("📖 Glosario de Métricas — Indicadores de Eficiencia")
    st.markdown("Referencia oficial de cálculos y definiciones utilizadas en este dashboard, según metodología de Capacidad Operativa ECC.")
    st.markdown("---")

    st.markdown("### 🕐 Estructura de Tiempos")
    st.markdown("""
<div style='display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px'>
  <div style='flex:1; min-width:200px; background:#2ecc7120; border:2px solid #2ecc71; border-radius:10px; padding:14px; text-align:center'>
    <p style='margin:0; font-size:13px; color:#2ecc71; font-weight:bold'>1️⃣ TIEMPO OCUPADO</p>
    <p style='margin:6px 0 0 0; font-size:12px; color:#ccc'>🗣️ Talking — Conversando<br>⏸️ HOLD — En espera<br>📝 ACW — Post llamada</p>
  </div>
  <div style='flex:1; min-width:200px; background:#3498db20; border:2px solid #3498db; border-radius:10px; padding:14px; text-align:center'>
    <p style='margin:0; font-size:13px; color:#3498db; font-weight:bold'>2️⃣ TIEMPO PRODUCTIVO</p>
    <p style='margin:6px 0 0 0; font-size:12px; color:#ccc'>= Tiempo Ocupado<br>+ 🟡 Disponible (En Cola / Ocioso)</p>
  </div>
  <div style='flex:1; min-width:200px; background:#9b59b620; border:2px solid #9b59b6; border-radius:10px; padding:14px; text-align:center'>
    <p style='margin:0; font-size:13px; color:#9b59b6; font-weight:bold'>3️⃣ TIEMPO LOGUEADO</p>
    <p style='margin:6px 0 0 0; font-size:12px; color:#ccc'>= Tiempo Productivo<br>+ ⚠️ Tiempos Improductivos</p>
  </div>
  <div style='flex:1; min-width:200px; background:#e74c3c20; border:2px solid #e74c3c; border-radius:10px; padding:14px; text-align:center'>
    <p style='margin:0; font-size:13px; color:#e74c3c; font-weight:bold'>📅 TIEMPO PROGRAMADO</p>
    <p style='margin:6px 0 0 0; font-size:12px; color:#ccc'>Turno planificado por WFM<br>Base para cálculo de Adhesión</p>
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown("### 🔄 Auxiliares — Tiempos Not Ready")
    col_aux1, col_aux2 = st.columns(2)
    with col_aux1:
        st.markdown("""
<div style='background:#2ecc7115; border-left:4px solid #2ecc71; padding:12px; border-radius:8px'>
    <p style='margin:0; font-size:13px; font-weight:bold; color:#2ecc71'>✅ Auxiliares Productivos</p>
    <p style='margin:6px 0 0 0; font-size:12px; color:#ccc'>
        👥 Reunión / Formación<br>📚 Coaching / Capacitación<br>📝 Back office / Gestión<br>🏃 Pausa Activa
    </p>
</div>""", unsafe_allow_html=True)
    with col_aux2:
        st.markdown("""
<div style='background:#e74c3c15; border-left:4px solid #e74c3c; padding:12px; border-radius:8px'>
    <p style='margin:0; font-size:13px; font-weight:bold; color:#e74c3c'>❌ Auxiliares Improductivos</p>
    <p style='margin:6px 0 0 0; font-size:12px; color:#ccc'>
        ☕ Descanso / Almuerzo (exceso sobre planificado)<br>🚽 Baño<br>🚫 Ausente Ocupado<br>📵 No Responde (automático IVR)<br>📲 Llamada Manual
    </p>
</div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📐 Fórmulas de Cálculo")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.markdown("""
<div style='background:#3498db15; border:1px solid #3498db; border-radius:10px; padding:16px'>
    <p style='margin:0; font-size:14px; font-weight:bold; color:#3498db'>📈 Utilización (%)</p>
    <div style='background:#ffffff15; border-radius:6px; padding:10px; margin:10px 0; text-align:center'>
        <p style='margin:0; font-size:13px; color:white'>Tiempos Productivos</p>
        <hr style='border-color:#555; margin:4px 0'>
        <p style='margin:0; font-size:13px; color:white'>Tiempos Logueados</p>
    </div>
    <p style='margin:0; font-size:12px; color:#aaa'>
        🎯 <b>Objetivo:</b> ≥ 85% (Óptimo)<br>🟡 <b>Medio:</b> 75%–84%<br>🔴 <b>Crítico:</b> &lt; 75%
    </p>
</div>""", unsafe_allow_html=True)
    with col_f2:
        st.markdown("""
<div style='background:#2ecc7115; border:1px solid #2ecc71; border-radius:10px; padding:16px'>
    <p style='margin:0; font-size:14px; font-weight:bold; color:#2ecc71'>✅ Adhesión (%)</p>
    <div style='background:#ffffff15; border-radius:6px; padding:10px; margin:10px 0; text-align:center'>
        <p style='margin:0; font-size:13px; color:white'>Tiempos Logueados</p>
        <hr style='border-color:#555; margin:4px 0'>
        <p style='margin:0; font-size:13px; color:white'>Tiempo Programado</p>
    </div>
    <p style='margin:0; font-size:12px; color:#aaa'>
        🎯 <b>Objetivo:</b> ≥ 99% (Óptimo)<br>🟡 <b>Medio:</b> 96.5%–98.9%<br>🔴 <b>Crítico:</b> &lt; 96.5%
    </p>
</div>""", unsafe_allow_html=True)
    with col_f3:
        st.markdown("""
<div style='background:#e67e2215; border:1px solid #e67e22; border-radius:10px; padding:16px'>
    <p style='margin:0; font-size:14px; font-weight:bold; color:#e67e22'>⚡ Ocupación (%)</p>
    <div style='background:#ffffff15; border-radius:6px; padding:10px; margin:10px 0; text-align:center'>
        <p style='margin:0; font-size:13px; color:white'>Tiempo Ocupado</p>
        <hr style='border-color:#555; margin:4px 0'>
        <p style='margin:0; font-size:13px; color:white'>Tiempos Productivos</p>
    </div>
    <p style='margin:0; font-size:12px; color:#aaa'>
        🎯 <b>Objetivo:</b> 50%–55% (Óptimo)<br>🟡 <b>Medio:</b> 40%–49% o 56%–65%<br>🔴 <b>Crítico:</b> &lt;40% o &gt;65%
    </p>
</div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.caption("📌 Fuente: Metodología Capacidad Operativa ECC | Sistema Genesys Cloud")

st.markdown("---")
st.markdown("""
<div style='text-align:center; color:gray; font-size:12px'>
    📊 Dashboard KPI — Servicio Técnico ECC &nbsp;|&nbsp;
    👩‍💼 Desarrollado por: <b>Paola Agüero — Owner Capacidad Operativa</b> &nbsp;|&nbsp;
    🐍 Powered by Python & Streamlit
</div>""", unsafe_allow_html=True)
