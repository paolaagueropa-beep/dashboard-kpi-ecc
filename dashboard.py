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
import math
import hashlib
import hmac

st.set_page_config(
    page_title="Dashboard KPI — Servicio Técnico ECC",
    page_icon="📊",
    layout="wide"
)

# ════════════════════════════════════════════════════════════
# CONFIGURACIÓN — ACTUALIZA DRIVE_ID CON EL ID DE Dashboard_KPI_ECC.xlsx
# ════════════════════════════════════════════════════════════
DRIVE_ID = "1n37x4ufR_u5IcDGXqhm13FYyaY48NGjX"   # ← reemplazar por ID del archivo fijo
OBJETIVO_COPC_DEFAULT = 86.0

# ════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ════════════════════════════════════════════════════════════
def make_hash(password: str) -> str:
    return hashlib.sha256(str(password).encode()).hexdigest()

def check_login(username: str, password: str):
    """Verifica credenciales contra st.secrets. Devuelve (ok, user_dict)."""
    try:
        users = dict(st.secrets.get("users", {}))
    except Exception:
        users = {}
    username_key = username.strip().lower().replace(".", "_").replace("-", "_").replace(" ", "_")
    if username_key in users:
        user = dict(users[username_key])
        stored = user.get("password_hash", "")
        if hmac.compare_digest(make_hash(password), stored):
            return True, user
    return False, {}

def mostrar_login():
    """Pantalla de login. Detiene la app hasta que el usuario se autentique."""
    st.markdown("""
    <div style='display:flex; justify-content:center; align-items:center;
                min-height:80vh; flex-direction:column'>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div style='text-align:center; margin-bottom:30px'>
            <h1 style='font-size:28px'>📊 Dashboard KPI</h1>
            <p style='color:gray; font-size:15px'>Servicio Técnico ECC</p>
        </div>
        """, unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("👤 Usuario", placeholder="tu.usuario")
            password = st.text_input("🔑 Contraseña", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Ingresar →", use_container_width=True)
            if submitted:
                if not username or not password:
                    st.warning("Ingresa tu usuario y contraseña.")
                else:
                    ok, user = check_login(username.strip().lower(), password)
                    if ok:
                        st.session_state.authenticated = True
                        st.session_state.user_name     = user.get("name", username)
                        st.session_state.user_role     = user.get("role", "supervisor")
                        st.session_state.user_jp       = user.get("jp", "")
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos.")
        st.markdown("""
        <p style='text-align:center; color:gray; font-size:12px; margin-top:20px'>
            ¿Olvidaste tu contraseña? Contacta a tu administrador.
        </p>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.user_jp = ""

if not st.session_state.authenticated:
    mostrar_login()
    st.stop()

user_name = st.session_state.user_name
user_role = st.session_state.user_role
user_jp   = st.session_state.user_jp
is_admin  = user_role in ("admin", "jefe")

# ════════════════════════════════════════════════════════════
# CARGA DE DATOS
# ════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def cargar_datos(cache_key):
    """Descarga el Excel desde Google Drive y carga hojas requeridas/opcionales."""
    session = requests.Session()
    url_base = f"https://drive.google.com/uc?export=download&id={DRIVE_ID}"
    response = session.get(url_base, timeout=60)

    token = None
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            token = value
            break
    if token:
        response = session.get(f"{url_base}&confirm={token}", timeout=60)

    content_type = response.headers.get("Content-Type", "")
    if "html" in content_type or len(response.content) < 5000:
        raise ValueError(
            "Google Drive no entregó el archivo Excel. Verifica que esté compartido como "
            "'Cualquier persona con el enlace puede ver'."
        )

    contenido = BytesIO(response.content)
    xl = pd.ExcelFile(contenido, engine="openpyxl")
    hojas_requeridas = [
        'Resumen_Agentes','Resumen_Jefatura','JP_Semana','JP_Dia',
        'Historico_Agente','Historico_Mensual','Dist_Cuartiles',
        'Resumen_Semanal','Detalle_Diario','Agentes_Criticos',
        'Horas_Agente_Mes','Horas_Agente_Semana','Horas_Agente_Dia',
        'Horas_JP_Mes','Metadata'
    ]
    hojas_opcionales = [
        'Capacidad_Servicio','Capacidad_Jefatura','Capacidad_Perfil','Dist_Cuartiles_Techo'
    ]
    datos = {}
    for hoja in hojas_requeridas:
        if hoja not in xl.sheet_names:
            raise ValueError(f"No existe la hoja requerida: {hoja}")
        datos[hoja] = pd.read_excel(xl, sheet_name=hoja)
    for hoja in hojas_opcionales:
        datos[hoja] = pd.read_excel(xl, sheet_name=hoja) if hoja in xl.sheet_names else pd.DataFrame()
    return datos

# ════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ════════════════════════════════════════════════════════════
def semaforo_util(val):
    if pd.isna(val): return "Sin datos"
    if val >= 85:    return "🟢 Óptimo"
    elif val >= 75:  return "🟡 Medio"
    else:            return "🔴 Crítico"

def semaforo_adh(val):
    if pd.isna(val):  return "Sin datos"
    if val >= 99:     return "🟢 Óptimo"
    elif val >= 96.5: return "🟡 Medio"
    else:             return "🔴 Crítico"

def semaforo_ocu(val):
    if pd.isna(val):    return "Sin datos"
    if 50 <= val <= 55: return "🟢 Óptimo"
    elif (40 <= val < 50) or (55 < val <= 65): return "🟡 Medio"
    else:               return "🔴 Crítico"

def cuartil_techo(v):
    if pd.isna(v): return "Sin datos"
    if v >= 95:    return "Q4 — Excelente 🏆"
    elif v >= 90:  return "Q3 — Muy buen trabajo 🚀"
    elif v >= 85:  return "Q2 — Buen resultado 👍"
    elif v >= 75:  return "Q1 — Oportunidad mejora ⚠️"
    else:          return "Q0 — Requiere seguimiento 🔍"

def cuartil_rec(v):
    if pd.isna(v):  return 'Sin datos'
    if v >= 85:     return 'Q4 — Óptimo 🟢'
    elif v >= 75:   return 'Q3 — Sobre meta ✅'
    elif v >= 70:   return 'Q2 — Bajo meta ⚠️'
    else:           return 'Q1 — Crítico 🔴'

def ordenar_cuartil(valor):
    s = str(valor)
    if s.startswith("Q0") or "Requiere" in s: return 0
    if s.startswith("Q1"): return 1
    if s.startswith("Q2"): return 2
    if s.startswith("Q3"): return 3
    if s.startswith("Q4"): return 4
    return 9

colores_semaforo = {
    "🟢 Óptimo": "#2ecc71",
    "🟡 Medio":  "#f1c40f",
    "🔴 Crítico":"#e74c3c",
    "Sin datos": "#95a5a6"
}
colores_score = {
    "🏆 Excelente gestión operacional": "#2ecc71",
    "🚀 Muy buen trabajo": "#27ae60",
    "👍 Buen resultado": "#3498db",
    "⚠️ Oportunidad de mejora": "#f39c12",
    "🔍 Requiere seguimiento": "#e74c3c",
    "Sin datos": "#95a5a6"
}

def hhmmss_a_min(t):
    try:
        p = str(t).split(':')
        return int(p[0])*60 + int(p[1]) + float(p[2])/60
    except Exception:
        return 0

def min_a_hhmmss(m):
    try:
        h = int(m//60); mi = int(m%60); s = int((m%1)*60)
        return f"{h:02d}:{mi:02d}:{s:02d}"
    except Exception:
        return "00:00:00"

def agregar_horas_grupo(df, cols):
    return {col: df[col].apply(hhmmss_a_min).sum() if col in df.columns else 0 for col in cols}

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
    except Exception:
        return "Sin dato"

def regresion_3meses(valores, meses, techo=None):
    """
    Proyección lineal a 3 meses, limitada por techo estructural/perfil cuando existe.
    Retorna meses futuros, predicciones finales y predicciones lineales originales.
    """
    try:
        datos = [(i, float(v)) for i, v in enumerate(valores) if pd.notna(v)]
        if len(datos) < 2:
            return [], [], []
        X = np.array([d[0] for d in datos]).reshape(-1, 1)
        y = np.array([d[1] for d in datos])
        mod = LinearRegression().fit(X, y)
        ui = max(d[0] for d in datos)
        preds_raw = mod.predict(np.array([ui+1, ui+2, ui+3]).reshape(-1, 1)).tolist()
        if techo is not None and pd.notna(techo) and float(techo) > 0:
            preds_final = [min(float(v), float(techo)) for v in preds_raw]
        else:
            preds_final = preds_raw
        return [f"Proj. {i+1}" for i in range(3)], preds_final, preds_raw
    except Exception:
        return [], [], []

def pendiente_lineal(valores):
    try:
        datos = [(i, float(v)) for i, v in enumerate(valores) if pd.notna(v)]
        if len(datos) < 2: return None
        X = np.array([d[0] for d in datos]).reshape(-1, 1)
        y = np.array([d[1] for d in datos])
        return float(LinearRegression().fit(X, y).coef_[0])
    except Exception:
        return None

def comentario_tendencia_agente(pendiente, cumplimiento=None):
    if pendiente is None:
        return "Sin datos suficientes para interpretar tendencia."
    if pendiente >= 1.0 and (cumplimiento is None or cumplimiento >= 90):
        return "Agente con tendencia sostenida al alza y buen aprovechamiento de su capacidad estructural."
    if pendiente >= 0.3:
        return "Tendencia al alza. Se observa avance positivo en la utilización."
    if -0.3 < pendiente < 0.3:
        return "Tendencia estable. Conviene monitorear para sostener o acelerar la mejora."
    if pendiente <= -1.0:
        return "Tendencia a la baja. Requiere seguimiento constante e intervención."
    return "Leve tendencia a la baja. Se recomienda revisar causas operativas."

def lectura_proyeccion(nombre_entidad, actual, techo, cumplimiento, brecha, pendiente, preds, contexto="servicio"):
    """Genera lectura automática simple para servicio, JP o agente."""
    actual_txt = fmt_pct(actual)
    techo_txt = fmt_pct(techo)
    cumplimiento_txt = fmt_pct(cumplimiento)
    brecha_txt = fmt_pp(brecha) if pd.notna(brecha) else "—"
    pendiente_txt = fmt_pp(pendiente) if pendiente is not None else "—"
    if preds:
        proy_txt = f"Mes +1: {fmt_pct(preds[0])} | Mes +2: {fmt_pct(preds[1])} | Mes +3: {fmt_pct(preds[2])}"
    else:
        proy_txt = "Sin datos suficientes para proyectar 3 meses."

    if pd.isna(actual) or pd.isna(techo) or not techo:
        interpretacion = "No hay datos suficientes para interpretar la capacidad estructural."
    elif brecha <= 1:
        interpretacion = "Está prácticamente en su techo máximo: el foco debe ser sostener el resultado."
    elif cumplimiento >= 95:
        interpretacion = "Está muy cerca de su techo máximo: la gestión actual muestra alto aprovechamiento de capacidad."
    elif cumplimiento >= 90:
        interpretacion = "Tiene buen aprovechamiento de su capacidad, pero aún existe espacio de mejora."
    else:
        interpretacion = "Existe capacidad disponible relevante: se recomienda intervención y seguimiento operacional."

    return (
        f"{nombre_entidad}: la utilización actual es {actual_txt}, lo que representa {cumplimiento_txt} "
        f"del techo máximo alcanzable ({techo_txt}). La distancia actual al techo es {brecha_txt}; "
        f"mientras mayor sea esta brecha, más lejos está de su máximo posible. "
        f"La tendencia estimada es {pendiente_txt} por mes. {proy_txt}. {interpretacion}"
    )

def fmt_pct(x, dec=1):
    try:
        if pd.isna(x): return "—"
        return f"{float(x):.{dec}f}%"
    except Exception:
        return "—"

def fmt_pp(x, dec=1):
    try:
        if pd.isna(x): return "—"
        return f"{float(x):.{dec}f} pp"
    except Exception:
        return "—"

def fmt_brecha_clara(x, dec=1):
    """Texto a prueba de interpretaciones: brecha positiva = faltan puntos para llegar al techo."""
    try:
        if pd.isna(x): return "—"
        v = float(x)
        if v > 0:
            return f"Faltan {v:.{dec}f} pp"
        if v < 0:
            return f"Supera por {abs(v):.{dec}f} pp"
        return "En su techo"
    except Exception:
        return "—"

def card_metric(col, titulo, valor, subtitulo, color="#3498db", icon="📌"):
    col.markdown(f"""
    <div style='background:{color}20; border-left:5px solid {color}; padding:10px; border-radius:7px; min-height:96px'>
        <p style='margin:0; font-size:12px; color:gray'>{icon} {titulo}</p>
        <p style='margin:0; font-size:24px; font-weight:bold'>{valor}</p>
        <p style='margin:0; font-size:11px; color:gray'>{subtitulo}</p>
    </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# HEADER + CARGA
# ════════════════════════════════════════════════════════════
st.title("📊 Dashboard KPI — Servicio Técnico ECC")
hoy = datetime.now()
st.markdown(f"""
<div style='background:#2c3e5020; border-left:5px solid #3498db;
            padding:10px; border-radius:5px; margin-bottom:10px'>
    <span style='font-size:16px'>
        📅 <b>Consulta:</b> Modelo de capacidad operacional &nbsp;|&nbsp;
        🕐 <b>Actualizado:</b> {hoy.strftime('%d/%m/%Y %H:%M')} &nbsp;|&nbsp;
        👩‍💼 <b>Creado por:</b> Paola Agüero — Owner Capacidad Operativa
    </span>
</div>""", unsafe_allow_html=True)
st.markdown("---")

_cache_key_auto = math.floor(time.time() / 300)
if 'force_refresh' not in st.session_state:
    st.session_state.force_refresh = 0
cache_key_final = _cache_key_auto * 10000 + st.session_state.force_refresh

with st.spinner("⏳ Cargando datos..."):
    try:
        datos        = cargar_datos(cache_key_final)
        resumen_raw  = datos['Resumen_Agentes']
        jefatura_raw = datos['Resumen_Jefatura']
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
        cap_serv     = datos.get('Capacidad_Servicio', pd.DataFrame())
        cap_jef      = datos.get('Capacidad_Jefatura', pd.DataFrame())
        cap_perfil   = datos.get('Capacidad_Perfil', pd.DataFrame())
        dist_techo   = datos.get('Dist_Cuartiles_Techo', pd.DataFrame())

        _meses_map = {
            '01':'Enero','02':'Febrero','03':'Marzo','04':'Abril','05':'Mayo','06':'Junio',
            '07':'Julio','08':'Agosto','09':'Septiembre','10':'Octubre','11':'Noviembre','12':'Diciembre',
            '1':'Enero','2':'Febrero','3':'Marzo','4':'Abril','5':'Mayo','6':'Junio','7':'Julio','8':'Agosto','9':'Septiembre'
        }
        def norm_mes(v):
            s = str(v).strip()
            return _meses_map.get(s, s)
        for df_tmp in [hist_mensual, dist_cuartil, dist_techo, resumen_raw]:
            if isinstance(df_tmp, pd.DataFrame) and 'Mes' in df_tmp.columns:
                df_tmp['Mes'] = df_tmp['Mes'].apply(norm_mes)
        st.success("✅ Datos cargados")
    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.stop()

meses_orden = ["Septiembre","Octubre","Noviembre","Diciembre","Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto"]

# ════════════════════════════════════════════════════════════
# SIDEBAR — filtros principales
# ════════════════════════════════════════════════════════════
st.sidebar.title("🔍 Filtros")
rol_label = {"admin":"👑 Administrador","jefe":"👔 Jefe/Coordinador","supervisor":"👤 Supervisor"}.get(user_role, user_role)
st.sidebar.markdown(f"""
<div style='background:#2c3e5030; border-left:4px solid #3498db;
            padding:8px; border-radius:5px; margin-bottom:12px'>
    <p style='margin:0; font-size:12px; color:gray'>Sesión activa</p>
    <p style='margin:0; font-size:14px; font-weight:bold'>{user_name}</p>
    <p style='margin:0; font-size:12px; color:#3498db'>{rol_label}</p>
</div>""", unsafe_allow_html=True)

# Mes disponible desde histórico mensual; por defecto el último mes por Orden_Mes
if 'Orden_Mes' in hist_mensual.columns and 'Mes' in hist_mensual.columns:
    meses_df = hist_mensual[['Mes','Orden_Mes']].dropna().drop_duplicates().sort_values('Orden_Mes')
    meses_disponibles = meses_df['Mes'].tolist()
else:
    meses_df = pd.DataFrame(columns=['Mes','Orden_Mes'])
    meses_disponibles = [m for m in meses_orden if m in hist_ag.columns]
if not meses_disponibles:
    meses_disponibles = [str(meta.get('Mes_Actual', 'Mes actual'))]
mes_default_idx = len(meses_disponibles) - 1
mes_sel = st.sidebar.selectbox("Mes", meses_disponibles, index=mes_default_idx)
mes_actual_datos = str(meta.get('Mes_Actual', meses_disponibles[-1]))

# Filtro de mes global: todo lo que tenga Mes, Orden_Mes o Fecha se filtra;
# si una hoja no tiene referencia mensual y se consulta un mes pasado, se deja vacía para no mostrar datos del mes actual por error.
def filtrar_df_por_mes(df_base, mes_consulta):
    if not isinstance(df_base, pd.DataFrame) or df_base.empty:
        return pd.DataFrame() if isinstance(df_base, pd.DataFrame) else df_base
    df2 = df_base.copy()
    if 'Mes' in df2.columns:
        return df2[df2['Mes'].apply(norm_mes).astype(str) == str(mes_consulta)].copy()
    if 'Orden_Mes' in df2.columns and 'Orden_Mes' in meses_df.columns:
        ordenes = meses_df[meses_df['Mes'].astype(str) == str(mes_consulta)]['Orden_Mes'].unique().tolist()
        return df2[df2['Orden_Mes'].isin(ordenes)].copy() if ordenes else df2.iloc[0:0].copy()
    if 'Fecha' in df2.columns:
        fechas = pd.to_datetime(df2['Fecha'], errors='coerce')
        meses_fecha = fechas.dt.month.astype('Int64').astype(str).map(_meses_map).fillna(df2['Fecha'].astype(str))
        return df2[meses_fecha == str(mes_consulta)].copy()
    return df2.copy() if str(mes_consulta) == str(mes_actual_datos) else df2.iloc[0:0].copy()

# Crear resumen del mes seleccionado: usa Resumen_Agentes si es el mes actual, histórico si se consulta mes previo
if 'Mes' in resumen_raw.columns and mes_sel in resumen_raw['Mes'].astype(str).unique():
    resumen_mes = resumen_raw[resumen_raw['Mes'].astype(str) == mes_sel].copy()
elif mes_sel == mes_actual_datos:
    resumen_mes = resumen_raw.copy()
else:
    resumen_mes = hist_mensual[hist_mensual['Mes'].astype(str) == mes_sel].copy() if 'Mes' in hist_mensual.columns else resumen_raw.copy()

# Completar columnas de capacidad si vienen con nombres antiguos/faltantes
if 'Techo_Perfil' not in resumen_mes.columns and 'Utilizacion Maxima Perfil' in resumen_mes.columns:
    resumen_mes['Techo_Perfil'] = resumen_mes['Utilizacion Maxima Perfil']
if 'Cumplimiento_Techo' not in resumen_mes.columns and {'Utilizacion','Techo_Perfil'}.issubset(resumen_mes.columns):
    resumen_mes['Cumplimiento_Techo'] = (resumen_mes['Utilizacion'] / resumen_mes['Techo_Perfil'] * 100).round(1).clip(upper=100)
if 'Brecha_vs_Techo' not in resumen_mes.columns and {'Techo_Perfil','Utilizacion'}.issubset(resumen_mes.columns):
    resumen_mes['Brecha_vs_Techo'] = (resumen_mes['Techo_Perfil'] - resumen_mes['Utilizacion']).round(1)
if 'Brecha_vs_COPC' not in resumen_mes.columns and 'Utilizacion' in resumen_mes.columns:
    resumen_mes['Brecha_vs_COPC'] = (OBJETIVO_COPC_DEFAULT - resumen_mes['Utilizacion']).round(1)
if 'Cuartil_Techo' not in resumen_mes.columns and 'Cumplimiento_Techo' in resumen_mes.columns:
    resumen_mes['Cuartil_Techo'] = resumen_mes['Cumplimiento_Techo'].apply(cuartil_techo)
if 'Cuartil_Rec' not in resumen_mes.columns and 'Cumplimiento_Techo' in resumen_mes.columns:
    resumen_mes['Cuartil_Rec'] = resumen_mes['Cumplimiento_Techo'].apply(cuartil_techo)

# Jefatura del mes seleccionado
if mes_sel == mes_actual_datos:
    jefatura_mes = jefatura_raw.copy()
else:
    # Fallback: resumen histórico por JP. Score sólo disponible si el Colab exporta histórico por jefatura.
    if {'JP','Utilizacion'}.issubset(resumen_mes.columns):
        agg_dict = {'Utilizacion': 'mean'}
        if 'Adhesion' in resumen_mes.columns: agg_dict['Adhesion'] = 'mean'
        if 'Ocupacion' in resumen_mes.columns: agg_dict['Ocupacion'] = 'mean'
        if 'NOMBRE' in resumen_mes.columns: agg_dict['NOMBRE'] = 'nunique'
        jefatura_mes = resumen_mes.groupby('JP').agg(agg_dict).reset_index()
        if 'NOMBRE' in jefatura_mes.columns:
            jefatura_mes = jefatura_mes.rename(columns={'NOMBRE':'Agentes'})
        if 'Techo_Perfil' in resumen_mes.columns:
            techo_jp = resumen_mes.groupby('JP')['Techo_Perfil'].mean().reset_index(name='Techo_Estructural_JP')
            jefatura_mes = jefatura_mes.merge(techo_jp, on='JP', how='left')
    else:
        jefatura_mes = jefatura_raw.copy()

if 'Techo_Estructural_JP' not in jefatura_mes.columns and 'Techo_Perfil' in resumen_mes.columns:
    techo_jp = resumen_mes.groupby('JP')['Techo_Perfil'].mean().reset_index(name='Techo_Estructural_JP')
    jefatura_mes = jefatura_mes.merge(techo_jp, on='JP', how='left') if 'JP' in jefatura_mes.columns else jefatura_mes
if 'Cumplimiento_Techo_JP' not in jefatura_mes.columns and {'Utilizacion','Techo_Estructural_JP'}.issubset(jefatura_mes.columns):
    jefatura_mes['Cumplimiento_Techo_JP'] = (jefatura_mes['Utilizacion'] / jefatura_mes['Techo_Estructural_JP'] * 100).round(1).clip(upper=100)
if 'Brecha_vs_Techo_JP' not in jefatura_mes.columns and {'Techo_Estructural_JP','Utilizacion'}.issubset(jefatura_mes.columns):
    jefatura_mes['Brecha_vs_Techo_JP'] = (jefatura_mes['Techo_Estructural_JP'] - jefatura_mes['Utilizacion']).round(1)
if 'Categoria_Gestion_JP' not in jefatura_mes.columns:
    jefatura_mes['Categoria_Gestion_JP'] = 'Sin datos'
if 'Comentario_Gestion_JP' not in jefatura_mes.columns:
    jefatura_mes['Comentario_Gestion_JP'] = ''

# Semáforos
for tmp in [resumen_mes, jefatura_mes]:
    if 'Utilizacion' in tmp.columns: tmp['Semaforo'] = tmp['Utilizacion'].apply(semaforo_util)
    if 'Adhesion' in tmp.columns: tmp['Semaforo_Adh'] = tmp['Adhesion'].apply(semaforo_adh)
    if 'Ocupacion' in tmp.columns: tmp['Semaforo_Ocu'] = tmp['Ocupacion'].apply(semaforo_ocu)

# Hojas filtradas globalmente por mes seleccionado
semanal_mes = filtrar_df_por_mes(semanal, mes_sel)
diario_mes = filtrar_df_por_mes(diario, mes_sel)
jp_semana_mes = filtrar_df_por_mes(jp_semana, mes_sel)
jp_dia_mes = filtrar_df_por_mes(jp_dia, mes_sel)
hrs_mes_filtrado = filtrar_df_por_mes(hrs_mes, mes_sel)
hrs_sem_filtrado = filtrar_df_por_mes(hrs_sem, mes_sel)
hrs_dia_filtrado = filtrar_df_por_mes(hrs_dia, mes_sel)
criticos_mes = filtrar_df_por_mes(criticos, mes_sel)

# Control de acceso
resumen_full = resumen_mes.copy()
hist_ag_full = hist_ag.copy()
jefatura_full = jefatura_mes.copy()

if is_admin:
    resumen_scope = resumen_full.copy()
    hist_ag_scope = hist_ag_full.copy()
    jefatura_scope = jefatura_full.copy()
    semanal_scope = semanal_mes.copy()
    diario_scope = diario_mes.copy()
    criticos_scope = criticos_mes.copy()
    hrs_mes_scope = hrs_mes_filtrado.copy()
    hrs_sem_scope = hrs_sem_filtrado.copy()
    hrs_dia_scope = hrs_dia_filtrado.copy()
    jp_sem_scope = jp_semana_mes.copy()
    jp_dia_scope = jp_dia_mes.copy()
else:
    resumen_scope = resumen_full[resumen_full['JP'] == user_jp].copy() if 'JP' in resumen_full.columns else resumen_full.copy()
    hist_ag_scope = hist_ag_full[hist_ag_full['JP'] == user_jp].copy() if 'JP' in hist_ag_full.columns else hist_ag_full.copy()
    jefatura_scope = jefatura_full[jefatura_full['JP'] == user_jp].copy() if 'JP' in jefatura_full.columns else jefatura_full.copy()
    semanal_scope = semanal_mes[semanal_mes['JP'] == user_jp].copy() if 'JP' in semanal_mes.columns else semanal_mes.copy()
    diario_scope = diario_mes[diario_mes['JP'] == user_jp].copy() if 'JP' in diario_mes.columns else diario_mes.copy()
    criticos_scope = criticos_mes[criticos_mes['JP'] == user_jp].copy() if 'JP' in criticos_mes.columns else criticos_mes.copy()
    hrs_mes_scope = hrs_mes_filtrado[hrs_mes_filtrado['JP'] == user_jp].copy() if 'JP' in hrs_mes_filtrado.columns else hrs_mes_filtrado.copy()
    hrs_sem_scope = hrs_sem_filtrado[hrs_sem_filtrado['JP'] == user_jp].copy() if 'JP' in hrs_sem_filtrado.columns else hrs_sem_filtrado.copy()
    hrs_dia_scope = hrs_dia_filtrado[hrs_dia_filtrado['JP'] == user_jp].copy() if 'JP' in hrs_dia_filtrado.columns else hrs_dia_filtrado.copy()
    jp_sem_scope = jp_semana_mes[jp_semana_mes['JP'] == user_jp].copy() if 'JP' in jp_semana_mes.columns else jp_semana_mes.copy()
    jp_dia_scope = jp_dia_mes[jp_dia_mes['JP'] == user_jp].copy() if 'JP' in jp_dia_mes.columns else jp_dia_mes.copy()

# Sidebar filtro supervisor reemplaza Horas Contrato. Sin antigüedad.
if is_admin:
    supervisores = ["Todos"] + sorted(resumen_full['JP'].dropna().unique().tolist()) if 'JP' in resumen_full.columns else ["Todos"]
    supervisor_sel = st.sidebar.selectbox("Supervisor", supervisores)
    df = resumen_scope.copy()
    if supervisor_sel != "Todos" and 'JP' in df.columns:
        df = df[df['JP'] == supervisor_sel]
        resumen_scope = resumen_scope[resumen_scope['JP'] == supervisor_sel].copy() if 'JP' in resumen_scope.columns else resumen_scope
        hist_ag_scope = hist_ag_scope[hist_ag_scope['JP'] == supervisor_sel].copy() if 'JP' in hist_ag_scope.columns else hist_ag_scope
        jefatura_scope = jefatura_scope[jefatura_scope['JP'] == supervisor_sel].copy() if 'JP' in jefatura_scope.columns else jefatura_scope
        semanal_scope = semanal_scope[semanal_scope['JP'] == supervisor_sel].copy() if 'JP' in semanal_scope.columns else semanal_scope
        diario_scope = diario_scope[diario_scope['JP'] == supervisor_sel].copy() if 'JP' in diario_scope.columns else diario_scope
        criticos_scope = criticos_scope[criticos_scope['JP'] == supervisor_sel].copy() if 'JP' in criticos_scope.columns else criticos_scope
        hrs_mes_scope = hrs_mes_scope[hrs_mes_scope['JP'] == supervisor_sel].copy() if 'JP' in hrs_mes_scope.columns else hrs_mes_scope
        hrs_sem_scope = hrs_sem_scope[hrs_sem_scope['JP'] == supervisor_sel].copy() if 'JP' in hrs_sem_scope.columns else hrs_sem_scope
        hrs_dia_scope = hrs_dia_scope[hrs_dia_scope['JP'] == supervisor_sel].copy() if 'JP' in hrs_dia_scope.columns else hrs_dia_scope
        jp_sem_scope = jp_sem_scope[jp_sem_scope['JP'] == supervisor_sel].copy() if 'JP' in jp_sem_scope.columns else jp_sem_scope
        jp_dia_scope = jp_dia_scope[jp_dia_scope['JP'] == supervisor_sel].copy() if 'JP' in jp_dia_scope.columns else jp_dia_scope
else:
    st.sidebar.info(f"👤 Viendo equipo de:\n**{user_jp}**")
    supervisor_sel = user_jp
    df = resumen_scope.copy()

# Indicadores de capacidad servicio
objetivo_copc = float(meta.get('Objetivo_COPC', meta.get('Objetivo_Util', OBJETIVO_COPC_DEFAULT)))
techo_estructural_servicio = float(meta.get('Techo_Estructural_Servicio', meta.get('Techo_Real_P90', 0)))
cumplimiento_techo_servicio = float(meta.get('Cumplimiento_Techo_Servicio', 0)) if 'Cumplimiento_Techo_Servicio' in meta.index else None
if cumplimiento_techo_servicio is None or cumplimiento_techo_servicio == 0:
    if 'Utilizacion' in resumen_full.columns and techo_estructural_servicio:
        cumplimiento_techo_servicio = min((resumen_full['Utilizacion'].mean() / techo_estructural_servicio) * 100, 100)
    else:
        cumplimiento_techo_servicio = 0
brecha_servicio = techo_estructural_servicio - resumen_full['Utilizacion'].mean() if 'Utilizacion' in resumen_full.columns and techo_estructural_servicio else 0

st.sidebar.markdown("---")
util_actual_servicio = resumen_full['Utilizacion'].mean() if 'Utilizacion' in resumen_full.columns and len(resumen_full) else 0
st.sidebar.markdown(f"""
<div style='background:#3498db20; border-left:4px solid #3498db; padding:8px; border-radius:5px; margin-top:8px'>
    <p style='margin:0; font-size:12px; color:gray'>🎯 Objetivo COPC</p>
    <p style='margin:0; font-size:20px; font-weight:bold'>{objetivo_copc:.1f}%</p>
    <p style='margin:0; font-size:11px; color:gray'>Referencia corporativa de capacidad operativa</p>
</div>""", unsafe_allow_html=True)
st.sidebar.markdown(f"""
<div style='background:#9b59b620; border-left:4px solid #9b59b6; padding:8px; border-radius:5px; margin-top:8px'>
    <p style='margin:0; font-size:12px; color:gray'>📊 Capacidad estructural del servicio</p>
    <p style='margin:0; font-size:22px; font-weight:bold'>{techo_estructural_servicio:.1f}%</p>
    <p style='margin:0; font-size:11px; color:gray'>Máximo alcanzable según composición contractual de la dotación</p>
</div>""", unsafe_allow_html=True)
st.sidebar.markdown(f"""
<div style='background:#2ecc7120; border-left:4px solid #2ecc71; padding:8px; border-radius:5px; margin-top:8px'>
    <p style='margin:0; font-size:12px; color:gray'>✅ Avance hacia capacidad máxima</p>
    <p style='margin:0; font-size:20px; font-weight:bold'>{cumplimiento_techo_servicio:.1f}%</p>
    <p style='margin:0; font-size:11px; color:gray'>La utilización actual ({util_actual_servicio:.1f}%) equivale al {cumplimiento_techo_servicio:.1f}% del techo máximo del servicio. Brecha por cerrar: {brecha_servicio:.1f} pp.</p>
</div>""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style='background:#1e1e2e; border:1px solid #444; padding:10px; border-radius:8px; margin-top:8px'>
    <p style='margin:0 0 6px 0; font-size:12px; font-weight:bold; color:#aaa'>📋 Semáforo Utilización Bruta</p>
    <p style='margin:2px 0; font-size:12px'>🟢 <b>Óptimo</b> → ≥ 85%</p>
    <p style='margin:2px 0; font-size:12px'>🟡 <b>Medio</b> → 75% – 84%</p>
    <p style='margin:2px 0; font-size:12px'>🔴 <b>Crítico</b> → &lt; 75%</p>
</div>""", unsafe_allow_html=True)
st.sidebar.markdown("""
<div style='background:#1e1e2e; border:1px solid #444; padding:10px; border-radius:8px; margin-top:8px'>
    <p style='margin:0 0 6px 0; font-size:12px; font-weight:bold; color:#aaa'>🏆 Score Gestión JP</p>
    <p style='margin:2px 0; font-size:12px'>🏆 ≥95 → Excelente gestión</p>
    <p style='margin:2px 0; font-size:12px'>🚀 90–94 → Muy buen trabajo</p>
    <p style='margin:2px 0; font-size:12px'>👍 85–89 → Buen resultado</p>
    <p style='margin:2px 0; font-size:12px'>⚠️ 75–84 → Oportunidad mejora</p>
    <p style='margin:2px 0; font-size:12px'>🔍 &lt;75 → Requiere seguimiento</p>
</div>""", unsafe_allow_html=True)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refrescar datos ahora"):
    st.session_state.force_refresh = st.session_state.get('force_refresh', 0) + 1
    st.cache_data.clear(); st.rerun()
if st.sidebar.button("🚪 Cerrar sesión"):
    for k in ["authenticated","user_name","user_role","user_jp","force_refresh"]:
        st.session_state.pop(k, None)
    st.rerun()

# Header KPIs
resumen_kpi = resumen_full.copy()
util_prom = resumen_kpi['Utilizacion'].mean() if 'Utilizacion' in resumen_kpi.columns else 0
adh_prom  = resumen_kpi['Adhesion'].mean() if 'Adhesion' in resumen_kpi.columns else 0
ocu_prom  = resumen_kpi['Ocupacion'].mean() if 'Ocupacion' in resumen_kpi.columns else 0
ocu_min   = (ocu_prom / 100) * 60 if pd.notna(ocu_prom) else 0
n_agentes = len(df)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("👥 Agentes" + (" visibles" if is_admin else " (tu equipo)"), n_agentes)
for col, icon, label, val, sfn, extra in [
    (col2,"📈","Utilización bruta",util_prom,semaforo_util, f"🎯 COPC: {objetivo_copc:.1f}% | Techo: {techo_estructural_servicio:.1f}%"),
    (col3,"✅","Adhesión",adh_prom,semaforo_adh,"🎯 Objetivo: ≥ 99%"),
    (col4,"⚡","Ocupación",ocu_prom,semaforo_ocu,f"🎯 Obj.: 50–55% (≈{ocu_min:.1f} min/h)"),
]:
    nv = sfn(val); cv = colores_semaforo.get(nv, "#95a5a6")
    col.markdown(f"""
    <div style='background:{cv}20; border-left:5px solid {cv}; padding:10px; border-radius:5px'>
        <p style='margin:0; font-size:13px; color:gray'>{icon} {label}</p>
        <p style='margin:0; font-size:26px; font-weight:bold'>{val:.1f}%</p>
        <p style='margin:0; font-size:12px'>{nv}</p>
        <p style='margin:0; font-size:11px; color:gray'>{extra}</p>
    </div>""", unsafe_allow_html=True)
card_metric(col5, "Cumplimiento techo", f"{cumplimiento_techo_servicio:.1f}%", "Utilización real / techo estructural", "#2ecc71", "🏆")
st.markdown("---")

# ════════════════════════════════════════════════════════════
# TABS
# ════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Resumen", "🏅 Ranking y Acumulado", "👤 Evolución por Agente",
    "🔴 Agentes Críticos", "⏱️ Control de Horas", "📖 Glosario de Métricas"
])

# ══════════════════════════════════════════
# TAB 1 — RESUMEN
# ══════════════════════════════════════════
with tab1:
    st.subheader("📊 Resumen")
    vista_resumen = st.radio("Ver resumen por:", ["Mes", "Semana", "Día"], horizontal=True, key="vista_resumen_tab1")

    data_resumen = df.copy()
    titulo_vista = f"{mes_sel}"
    if vista_resumen == "Semana":
        if len(semanal_scope) > 0 and 'Semana' in semanal_scope.columns:
            sems = sorted(semanal_scope['Semana'].dropna().unique().tolist())
            ss = st.selectbox("Selecciona semana", sems, key="tab1_semana")
            data_resumen = semanal_scope[semanal_scope['Semana'] == ss].copy()
            titulo_vista = ss
            if 'Semaforo' not in data_resumen.columns and 'Utilizacion' in data_resumen.columns:
                data_resumen['Semaforo'] = data_resumen['Utilizacion'].apply(semaforo_util)
        else:
            st.warning("No hay detalle semanal disponible para esta consulta.")
    elif vista_resumen == "Día":
        if len(diario_scope) > 0 and 'Fecha' in diario_scope.columns:
            fechas = sorted(diario_scope['Fecha'].dropna().unique().tolist())
            fs = st.selectbox("Selecciona fecha", fechas, key="tab1_dia")
            data_resumen = diario_scope[diario_scope['Fecha'] == fs].copy()
            titulo_vista = str(fs)
            if 'Semaforo' not in data_resumen.columns and 'Utilizacion' in data_resumen.columns:
                data_resumen['Semaforo'] = data_resumen['Utilizacion'].apply(semaforo_util)
        else:
            st.warning("No hay detalle diario disponible para esta consulta.")

    c1, c2, c3, c4 = st.columns(4)
    util_v = data_resumen['Utilizacion'].mean() if 'Utilizacion' in data_resumen.columns else 0
    adh_v = data_resumen['Adhesion'].mean() if 'Adhesion' in data_resumen.columns else 0
    ocu_v = data_resumen['Ocupacion'].mean() if 'Ocupacion' in data_resumen.columns else 0
    cump_v = data_resumen['Cumplimiento_Techo'].mean() if 'Cumplimiento_Techo' in data_resumen.columns else (util_v / techo_estructural_servicio * 100 if techo_estructural_servicio else 0)
    card_metric(c1, f"Utilización — {titulo_vista}", fmt_pct(util_v), semaforo_util(util_v), colores_semaforo.get(semaforo_util(util_v), "#95a5a6"), "📈")
    card_metric(c2, "Cumplimiento techo", fmt_pct(cump_v), "Uso de capacidad estructural", "#2ecc71", "🏆")
    card_metric(c3, "Adhesión", fmt_pct(adh_v), semaforo_adh(adh_v), colores_semaforo.get(semaforo_adh(adh_v), "#95a5a6"), "✅")
    card_metric(c4, "Ocupación", fmt_pct(ocu_v), semaforo_ocu(ocu_v), colores_semaforo.get(semaforo_ocu(ocu_v), "#95a5a6"), "⚡")

    st.markdown("---")
    col_dist, col_techo = st.columns([1, 1.4])
    with col_dist:
        st.subheader("🚦 Distribución Semáforo")
        if 'Semaforo' in data_resumen.columns and len(data_resumen) > 0:
            dist = data_resumen['Semaforo'].value_counts().reset_index()
            dist.columns = ['Nivel','Agentes']
            fig2 = px.pie(dist, values='Agentes', names='Nivel', color='Nivel', color_discrete_map=colores_semaforo, hole=0.4)
            fig2.update_traces(textinfo="label+percent+value", textfont=dict(size=12))
            fig2.update_layout(height=430, margin=dict(t=60,b=40,l=20,r=20), legend=dict(orientation='h', y=-0.1))
            st.plotly_chart(fig2, use_container_width=True, key="fig2_resumen")
        else:
            st.info("Sin datos para distribución.")
    with col_techo:
        st.subheader("🏗️ Utilización real vs techo por jefatura")
        if {'JP','Utilizacion','Techo_Estructural_JP'}.issubset(jefatura_scope.columns):
            jt = jefatura_scope.sort_values('Cumplimiento_Techo_JP' if 'Cumplimiento_Techo_JP' in jefatura_scope.columns else 'Utilizacion', ascending=True).copy()
            fig_techo = go.Figure()
            fig_techo.add_trace(go.Bar(name='Utilización real', y=jt['JP'], x=jt['Utilizacion'], orientation='h', marker_color='#3498db', text=jt['Utilizacion'], texttemplate='%{text:.1f}%'))
            fig_techo.add_trace(go.Bar(name='Techo equipo', y=jt['JP'], x=jt['Techo_Estructural_JP'], orientation='h', marker_color='#9b59b6', text=jt['Techo_Estructural_JP'], texttemplate='%{text:.1f}%'))
            fig_techo.update_traces(textposition='outside', textfont=dict(size=11)); fig_techo.update_layout(barmode='group', height=max(520, 42*len(jt)), plot_bgcolor='white', xaxis_title='Porcentaje (%)', margin=dict(l=180,r=80,t=70,b=40))
            st.plotly_chart(fig_techo, use_container_width=True, key="fig_techo_jp")
        else:
            st.info("El techo por jefatura no está disponible para esta selección.")

    st.markdown("---")
    st.subheader("📈 Evolución Histórica del Servicio")
    meses_disp = [m for m in meses_orden if m in hist_ag.columns]
    promedios = []
    for m in meses_disp:
        vals = hist_ag[m].dropna()
        promedios.append(vals.mean() if len(vals) > 0 else None)
    meses_fut, preds, preds_raw = regresion_3meses(promedios, meses_disp, techo_estructural_servicio)
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(x=meses_disp, y=promedios, mode='lines+markers+text', text=[f"{v:.1f}%" if pd.notna(v) else "" for v in promedios], textposition='top center', line=dict(color='#3498db', width=3), marker=dict(size=12), name='Real'))
    if preds:
        fig4.add_trace(go.Scatter(x=meses_fut, y=preds, mode='lines+markers+text', text=[f"{v:.1f}%" for v in preds], textposition='top center', name='Proyección', line=dict(color='#9b59b6', dash='dash', width=3), marker=dict(size=12, symbol='diamond')))
    fig4.add_hline(y=objetivo_copc, line_dash='dash', line_color='green', annotation_text=f'COPC {objetivo_copc:.1f}%')
    fig4.add_hline(y=techo_estructural_servicio, line_dash='dot', line_color='#9b59b6', annotation_text=f'Techo estructural {techo_estructural_servicio:.1f}%')
    fig4.update_layout(height=460, plot_bgcolor='white', yaxis_title='Utilización (%)')
    st.plotly_chart(fig4, use_container_width=True, key="fig4_servicio")

    util_actual_servicio = next((v for v in reversed(promedios) if pd.notna(v)), np.nan)
    brecha_servicio = techo_estructural_servicio - util_actual_servicio if pd.notna(util_actual_servicio) and pd.notna(techo_estructural_servicio) else np.nan
    cumplimiento_servicio_calc = (util_actual_servicio / techo_estructural_servicio * 100) if pd.notna(util_actual_servicio) and pd.notna(techo_estructural_servicio) and techo_estructural_servicio else np.nan
    pendiente_servicio = pendiente_lineal(promedios)
    lectura_serv = lectura_proyeccion(
        'Servicio', util_actual_servicio, techo_estructural_servicio, cumplimiento_servicio_calc,
        brecha_servicio, pendiente_servicio, preds, contexto='servicio'
    )
    st.markdown(f"""
    <div style='background:#2c3e5018; border-left:4px solid #9b59b6; padding:12px; border-radius:8px; margin-top:8px; margin-bottom:18px'>
        <h4 style='margin:0 0 6px 0'>🧭 Lectura automática contra techo estructural</h4>
        <p style='margin:0; font-size:13px'>{lectura_serv}</p>
        <p style='margin:6px 0 0 0; font-size:11px; color:gray'>Nota: la proyección mantiene la tendencia lineal, pero se limita al techo estructural para no mostrar resultados imposibles.</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("📊 Movimiento de Dotación por Cuartil")
    dist_plot = dist_techo if isinstance(dist_techo, pd.DataFrame) and len(dist_techo) > 0 else dist_cuartil
    color_col = 'Cuartil_Techo' if 'Cuartil_Techo' in dist_plot.columns else 'Cuartil_Util'
    if len(dist_plot) > 0 and color_col in dist_plot.columns:
        colores_cuartil = {
            'Q0 — Requiere seguimiento 🔍':'#c0392b', 'Q1 — Oportunidad mejora ⚠️':'#f39c12',
            'Q2 — Buen resultado 👍':'#3498db', 'Q3 — Muy buen trabajo 🚀':'#27ae60', 'Q4 — Excelente 🏆':'#2ecc71',
            'Q1 — Crítico 🔴':'#e74c3c','Q2 — Bajo meta ⚠️':'#f39c12','Q3 — Sobre meta ✅':'#3498db','Q4 — Óptimo 🟢':'#2ecc71'
        }
        fig_cuartil = px.bar(dist_plot.sort_values('Orden_Mes'), x='Mes', y='Agentes', color=color_col, color_discrete_map=colores_cuartil, barmode='stack', text='Agentes')
        fig_cuartil.update_traces(textposition='inside', textfont=dict(size=11))
        fig_cuartil.update_layout(height=380, plot_bgcolor='white')
        st.plotly_chart(fig_cuartil, use_container_width=True, key="fig_cuartil")

    st.markdown("---")
    st.subheader("📋 Resumen Completo por Agente")
    df_tabla = df.copy()
    if 'Cumplimiento_Techo' not in df_tabla.columns and {'Utilizacion','Techo_Perfil'}.issubset(df_tabla.columns):
        df_tabla['Cumplimiento_Techo'] = (df_tabla['Utilizacion'] / df_tabla['Techo_Perfil'] * 100).round(1).clip(upper=100)
    if 'Brecha_vs_Techo' not in df_tabla.columns and {'Techo_Perfil','Utilizacion'}.issubset(df_tabla.columns):
        df_tabla['Brecha_vs_Techo'] = (df_tabla['Techo_Perfil'] - df_tabla['Utilizacion']).round(1)
    if 'Cuartil_Techo' not in df_tabla.columns:
        df_tabla['Cuartil_Techo'] = df_tabla['Cumplimiento_Techo'].apply(cuartil_techo) if 'Cumplimiento_Techo' in df_tabla.columns else df_tabla.get('Cuartil_Util', 'Sin datos')

    cuartiles_opc = ['Todos'] + sorted(df_tabla['Cuartil_Techo'].dropna().unique().tolist(), key=ordenar_cuartil) if 'Cuartil_Techo' in df_tabla.columns else ['Todos']
    cuartil_sel = st.selectbox("Filtrar por cuartil/cumplimiento techo", cuartiles_opc, key="cuartil_tab1")
    explicacion_cuartil = {
        'Q0': 'Q0 - Requiere seguimiento: cumplimiento de techo menor a 75%. El agente está muy lejos de su máximo posible.',
        'Q1': 'Q1 - Oportunidad de mejora: cumplimiento de techo entre 75% y 84%. Aún hay brecha importante por trabajar.',
        'Q2': 'Q2 - Buen resultado: cumplimiento de techo entre 85% y 89%. Está acercándose a su máximo posible.',
        'Q3': 'Q3 - Muy buen trabajo: cumplimiento de techo entre 90% y 94%. Opera cerca de su capacidad estructural.',
        'Q4': 'Q4 - Excelente: cumplimiento de techo de 95% o más. Opera prácticamente en su máximo posible.'
    }
    if cuartil_sel != 'Todos':
        st.caption(explicacion_cuartil.get(str(cuartil_sel)[:2], 'La cuartilización se calcula sobre Cumplimiento de Techo = Utilización actual / Utilización máxima por perfil.'))
    else:
        st.caption('Cuartil calculado sobre Cumplimiento de Techo = Utilización actual / Utilización máxima por perfil. Mientras más alto el cuartil, más cerca está el agente de su máximo posible.')
    if cuartil_sel != 'Todos' and 'Cuartil_Techo' in df_tabla.columns:
        df_tabla = df_tabla[df_tabla['Cuartil_Techo'] == cuartil_sel]

    if 'Hrs_Prod_Contrato' in hrs_mes.columns and 'NOMBRE' in hrs_mes.columns and 'Hrs_Prod_Contrato' not in df_tabla.columns:
        df_tabla = df_tabla.merge(hrs_mes[['NOMBRE','Hrs_Prod_Contrato']], on='NOMBRE', how='left')

    df_tabla['Utilización Máxima Perfil'] = df_tabla['Techo_Perfil'].apply(fmt_pct) if 'Techo_Perfil' in df_tabla.columns else '—'
    df_tabla['Utilización'] = df_tabla['Utilizacion'].apply(fmt_pct) if 'Utilizacion' in df_tabla.columns else '—'
    df_tabla['Puntos faltantes al techo'] = df_tabla['Brecha_vs_Techo'].apply(fmt_brecha_clara) if 'Brecha_vs_Techo' in df_tabla.columns else '—'
    df_tabla['Adhesión'] = df_tabla['Adhesion'].apply(fmt_pct) if 'Adhesion' in df_tabla.columns else '—'
    df_tabla['Ocupación'] = df_tabla['Ocupacion'].apply(fmt_pct) if 'Ocupacion' in df_tabla.columns else '—'
    df_tabla['Cuartil'] = df_tabla['Cuartil_Techo'] if 'Cuartil_Techo' in df_tabla.columns else df_tabla.get('Cuartil_Util', '')
    if 'Hrs_Prod_Contrato' in df_tabla.columns:
        df_tabla['Hrs. Prod. Cont.'] = df_tabla['Hrs_Prod_Contrato']

    sort_col = 'Cuartil_Techo'
    if sort_col in df_tabla.columns:
        df_tabla['_orden_cuartil'] = df_tabla[sort_col].apply(ordenar_cuartil)
        df_tabla = df_tabla.sort_values(['_orden_cuartil','Brecha_vs_Techo' if 'Brecha_vs_Techo' in df_tabla.columns else '_orden_cuartil'], ascending=[True, False])

    cols_t = ['NOMBRE','JP','Tramo_Antiguedad','HRS_CONTRATO','Hrs. Prod. Cont.','Dias_trabajados',
              'Utilización Máxima Perfil','Utilización','Puntos faltantes al techo','Adhesión','Ocupación','Cuartil']
    cols_show = [c for c in cols_t if c in df_tabla.columns]
    if not is_admin and 'JP' in cols_show:
        cols_show.remove('JP')
    st.caption('En la columna Puntos faltantes al techo, un número mayor significa que el agente está más lejos de su utilización máxima posible. La meta es reducir esa brecha.')
    st.dataframe(df_tabla[cols_show], use_container_width=True, key="tabla_resumen_agentes")

# ══════════════════════════════════════════
# TAB 2 — RANKING Y ACUMULADO
# ══════════════════════════════════════════
with tab2:
    st.subheader("🏅 Ranking y Acumulado por Período")
    periodo = st.radio("Ver por:", ["Mes", "Semana", "Día"], horizontal=True, key="periodo_tab2")

    if periodo == "Mes":
        data_jp = jefatura_scope.copy(); data_ag = resumen_scope.copy(); titulo_periodo = mes_sel
    elif periodo == "Semana":
        semanas_disp = sorted(jp_sem_scope['Semana'].dropna().unique().tolist()) if 'Semana' in jp_sem_scope.columns else []
        semana_sel = st.selectbox("Selecciona semana", semanas_disp, key="semana_tab2") if semanas_disp else None
        data_jp = jp_sem_scope[jp_sem_scope['Semana'] == semana_sel].copy() if semana_sel else pd.DataFrame()
        data_ag = semanal_scope[semanal_scope['Semana'] == semana_sel].copy() if semana_sel and 'Semana' in semanal_scope.columns else pd.DataFrame()
        titulo_periodo = semana_sel or "Semana"
    else:
        fechas_disp = sorted(jp_dia_scope['Fecha'].dropna().unique().tolist()) if 'Fecha' in jp_dia_scope.columns else []
        fecha_sel = st.selectbox("Selecciona fecha", fechas_disp, key="fecha_tab2") if fechas_disp else None
        data_jp = jp_dia_scope[jp_dia_scope['Fecha'] == fecha_sel].copy() if fecha_sel else pd.DataFrame()
        data_ag = diario_scope[diario_scope['Fecha'] == fecha_sel].dropna(subset=['Utilizacion']).copy() if fecha_sel and 'Fecha' in diario_scope.columns else pd.DataFrame()
        titulo_periodo = str(fecha_sel) if fecha_sel else "Día"

    tab2a, tab2b, tab2c = st.tabs(["📈 Ranking Agentes", "🏆 Ranking Supervisor", "🧭 Lecturas de gestión"])

    with tab2a:
        st.markdown(f"### Ranking Agentes — {titulo_periodo}")
        if len(data_ag) > 0 and 'Utilizacion' in data_ag.columns:
            if is_admin and 'JP' in data_ag.columns:
                jp_opc = ['Todos'] + sorted(data_ag['JP'].dropna().unique().tolist())
                jp_fil = st.selectbox("Filtrar supervisor", jp_opc, key="jp_rank")
                dag = data_ag[data_ag['JP'] == jp_fil].copy() if jp_fil != 'Todos' else data_ag.copy()
            else:
                dag = data_ag.copy()

            if 'Cumplimiento_Techo' not in dag.columns and {'Utilizacion','Techo_Perfil'}.issubset(dag.columns):
                dag['Cumplimiento_Techo'] = (dag['Utilizacion'] / dag['Techo_Perfil'] * 100).round(1).clip(upper=100)
            if 'Brecha_vs_Techo' not in dag.columns and {'Techo_Perfil','Utilizacion'}.issubset(dag.columns):
                dag['Brecha_vs_Techo'] = (dag['Techo_Perfil'] - dag['Utilizacion']).round(1)
            dag['Sem_t2'] = dag['Utilizacion'].apply(semaforo_util)

            fig_ag = px.bar(dag.sort_values('Utilizacion', ascending=True), x='Utilizacion', y='NOMBRE', color='Sem_t2', color_discrete_map=colores_semaforo, orientation='h', text='Utilizacion')
            fig_ag.add_vline(x=75, line_dash='dash', line_color='orange', annotation_text='Mín 75%')
            fig_ag.add_vline(x=85, line_dash='dash', line_color='green', annotation_text='Óptimo 85%')
            fig_ag.update_traces(texttemplate='%{text:.1f}%', textposition='outside', textfont=dict(size=11))
            fig_ag.update_layout(height=max(580, 24*len(dag)), plot_bgcolor='white', xaxis_title='Utilización (%)', margin=dict(l=190,r=80,t=60,b=40))
            st.plotly_chart(fig_ag, use_container_width=True, key="fig_ag_clasico")

            st.markdown("#### Lecturas automáticas de agentes")
            ca1, ca2, ca3 = st.columns(3)
            def lista_agentes_card(col, titulo, data, campo, color, subtitulo):
                if len(data) == 0 or campo not in data.columns:
                    col.info("Sin datos")
                    return
                top = data.sort_values(campo, ascending=False).head(6)
                nombres = '<br>'.join([str(x) for x in top.get('NOMBRE', pd.Series(dtype=str)).tolist()])
                valor = top.iloc[0].get(campo, np.nan)
                valor_txt = fmt_pct(valor) if 'Cumplimiento' in campo or 'Utilizacion' in campo else fmt_brecha_clara(valor)
                col.markdown(f"""
                <div style='background:{color}20; border-left:5px solid {color}; padding:12px; border-radius:8px; min-height:180px'>
                    <h4 style='margin:0'>{titulo}</h4>
                    <p style='margin:6px 0; font-size:12px; color:gray'>{subtitulo}</p>
                    <p style='margin:4px 0; font-size:12px'>Referencia superior: <b>{valor_txt}</b></p>
                    <div style='font-size:12px; line-height:1.45'>{nombres}</div>
                </div>""", unsafe_allow_html=True)
            lista_agentes_card(ca1, "🏆 Mejor gestión operacional", dag, 'Cumplimiento_Techo', '#2ecc71', 'Agentes más cerca de su techo máximo')
            lista_agentes_card(ca2, "🚀 Mejor utilización actual", dag, 'Utilizacion', '#3498db', 'Agentes con mayor utilización bruta')
            if 'Brecha_vs_Techo' in dag.columns:
                # Para capacidad disponible interesa la brecha mayor: está más lejos de su techo.
                lista_agentes_card(ca3, "⚠️ Mayor capacidad disponible", dag, 'Brecha_vs_Techo', '#f39c12', 'Agentes con más puntos por cerrar hacia su techo')
        else:
            st.info("Sin datos de agentes para esta selección.")

    with tab2b:
        st.markdown(f"### Ranking Supervisor por Score de Gestión JP — {titulo_periodo}")
        if periodo != "Mes":
            st.info("El Score de Gestión JP se calcula a nivel mensual porque requiere tendencia y techo estructural de equipo.")
        score_df = jefatura_scope.copy()
        if 'Score_Gestion_JP' in score_df.columns and len(score_df) > 0:
            score_df = score_df.sort_values('Score_Gestion_JP', ascending=True)
            score_df['Categoria_Gestion_JP'] = score_df['Categoria_Gestion_JP'].fillna('Sin datos')
            fig_score = px.bar(score_df, x='Score_Gestion_JP', y='JP', color='Categoria_Gestion_JP', color_discrete_map=colores_score, orientation='h', text='Score_Gestion_JP')
            fig_score.update_traces(texttemplate='%{text:.1f}', textposition='outside')
            fig_score.update_layout(height=500, plot_bgcolor='white', xaxis_title='Score Gestión JP (0-100)')
            st.plotly_chart(fig_score, use_container_width=True, key="fig_score_jp")

            cols_score = ['Ranking_Gestion_JP','JP','Utilizacion','Techo_Estructural_JP','Cumplimiento_Techo_JP','Tendencia_Util_JP','Score_Gestion_JP','Categoria_Gestion_JP','Comentario_Gestion_JP']
            tabla_score = score_df[[c for c in cols_score if c in score_df.columns]].copy().sort_values('Score_Gestion_JP', ascending=False)
            for c in ['Utilizacion','Techo_Estructural_JP','Cumplimiento_Techo_JP']:
                if c in tabla_score.columns: tabla_score[c] = tabla_score[c].apply(fmt_pct)
            if 'Tendencia_Util_JP' in tabla_score.columns: tabla_score['Tendencia_Util_JP'] = tabla_score['Tendencia_Util_JP'].apply(fmt_pp)
            st.dataframe(tabla_score, use_container_width=True, key="tabla_score_jp")
        else:
            st.warning("No se encontró Score_Gestion_JP en la hoja Resumen_Jefatura. Ejecuta el Colab v3 con score de gestión.")

    with tab2c:
        st.markdown("### Lecturas automáticas de gestión")
        score_df = jefatura_scope.copy()
        if len(score_df) > 0 and 'JP' in score_df.columns:
            c1, c2, c3 = st.columns(3)
            if 'Score_Gestion_JP' in score_df.columns:
                mejor = score_df.sort_values('Score_Gestion_JP', ascending=False).head(1)
                if not mejor.empty:
                    r = mejor.iloc[0]; color = colores_score.get(r.get('Categoria_Gestion_JP','Sin datos'), '#2ecc71')
                    c1.markdown(f"""
                    <div style='background:{color}20; border-left:5px solid {color}; padding:12px; border-radius:8px'>
                        <h4 style='margin:0'>🏆 Mejor gestión operacional</h4>
                        <p style='margin:5px 0'><b>{r.get('JP','')}</b></p>
                        <p style='margin:0'>Score: <b>{r.get('Score_Gestion_JP',0):.1f}</b></p>
                        <p style='margin:0; font-size:12px'>{r.get('Categoria_Gestion_JP','')}</p>
                    </div>""", unsafe_allow_html=True)
            if 'Tendencia_Util_JP' in score_df.columns:
                crecimiento = score_df.sort_values('Tendencia_Util_JP', ascending=False).head(1)
                if not crecimiento.empty:
                    r = crecimiento.iloc[0]
                    c2.markdown(f"""
                    <div style='background:#3498db20; border-left:5px solid #3498db; padding:12px; border-radius:8px'>
                        <h4 style='margin:0'>🚀 Mayor crecimiento</h4>
                        <p style='margin:5px 0'><b>{r.get('JP','')}</b></p>
                        <p style='margin:0'>Tendencia: <b>{fmt_pp(r.get('Tendencia_Util_JP'))}</b></p>
                        <p style='margin:0; font-size:12px'>Variación vs promedio previo</p>
                    </div>""", unsafe_allow_html=True)
            if 'Brecha_vs_Techo_JP' in score_df.columns:
                brecha = score_df.sort_values('Brecha_vs_Techo_JP', ascending=False).head(1)
                if not brecha.empty:
                    r = brecha.iloc[0]
                    c3.markdown(f"""
                    <div style='background:#f39c1220; border-left:5px solid #f39c12; padding:12px; border-radius:8px'>
                        <h4 style='margin:0'>⚠️ Mayor capacidad disponible</h4>
                        <p style='margin:5px 0'><b>{r.get('JP','')}</b></p>
                        <p style='margin:0'>Brecha: <b>{fmt_pp(r.get('Brecha_vs_Techo_JP'))}</b></p>
                        <p style='margin:0; font-size:12px'>Potencial estructural por desarrollar</p>
                    </div>""", unsafe_allow_html=True)
            st.markdown("---")
            for _, r in score_df.sort_values('Score_Gestion_JP' if 'Score_Gestion_JP' in score_df.columns else 'JP', ascending=False).iterrows():
                cat = r.get('Categoria_Gestion_JP','Sin datos')
                color = colores_score.get(cat, '#95a5a6')
                st.markdown(f"""
                <div style='background:{color}15; border-left:4px solid {color}; padding:10px; border-radius:6px; margin-bottom:8px'>
                    <b>{r.get('JP','')}</b> — {cat}<br>
                    <span style='font-size:12px; color:gray'>{r.get('Comentario_Gestion_JP','')}</span>
                </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════
# TAB 3 — EVOLUCIÓN POR AGENTE
# ══════════════════════════════════════════
with tab3:
    st.subheader("👤 Evolución Histórica por Agente")
    col_a, col_b = st.columns(2)
    if is_admin:
        with col_a:
            sup_ag = st.selectbox("Filtrar supervisor", ["Todos"] + sorted(hist_ag_full['JP'].dropna().unique().tolist()), key="sup_ag") if 'JP' in hist_ag_full.columns else 'Todos'
        hist_fil = hist_ag_full[hist_ag_full['JP'] == sup_ag].copy() if sup_ag != 'Todos' and 'JP' in hist_ag_full.columns else hist_ag_full.copy()
    else:
        hist_fil = hist_ag_scope.copy()
        with col_a:
            st.info(f"👤 Mostrando agentes de: **{user_jp}**")
    with col_b:
        agente_sel = st.selectbox("Selecciona agente", sorted(hist_fil['NOMBRE'].dropna().unique().tolist()), key="agente_sel") if 'NOMBRE' in hist_fil.columns and len(hist_fil) > 0 else None

    if agente_sel and not hist_fil[hist_fil['NOMBRE'] == agente_sel].empty:
        ag = hist_fil[hist_fil['NOMBRE'] == agente_sel].iloc[0]
        ag_resumen = resumen_full[resumen_full['NOMBRE'] == agente_sel] if 'NOMBRE' in resumen_full.columns else pd.DataFrame()
        ag_actual = ag_resumen.iloc[0] if not ag_resumen.empty else ag

        estado = ag_actual.get('ESTADO', ag.get('ESTADO','Sin dato'))
        contrato = ag_actual.get('HRS_CONTRATO', ag.get('HRS_CONTRATO','Sin dato'))
        ant_texto = antiguedad_texto(ag_actual.get('FECHA_INGRESO', ag.get('FECHA_INGRESO', None)))
        promedio = ag.get('Promedio_historico', np.nan)
        tendencia_ag = ag.get('Tendencia','Sin dato')
        techo_ag = ag_actual.get('Techo_Perfil', ag.get('Techo_Perfil', np.nan))
        util_mes = ag_actual.get('Utilizacion', np.nan)
        cumplimiento_ag = ag_actual.get('Cumplimiento_Techo', (util_mes/techo_ag*100 if pd.notna(util_mes) and pd.notna(techo_ag) and techo_ag else np.nan))
        brecha_techo = ag_actual.get('Brecha_vs_Techo', (techo_ag-util_mes if pd.notna(util_mes) and pd.notna(techo_ag) else np.nan))
        brecha_copc = ag_actual.get('Brecha_vs_COPC', (objetivo_copc-util_mes if pd.notna(util_mes) else np.nan))
        sem_actual = semaforo_util(util_mes)
        color_actual = colores_semaforo.get(sem_actual, '#95a5a6')

        st.markdown(f"""
        <div style='background:{color_actual}20; border-left:5px solid {color_actual}; padding:15px; border-radius:8px; margin-bottom:15px'>
            <h4 style='margin:0'>{agente_sel} &nbsp;
                <span style='font-size:14px; font-weight:normal; color:gray'>| Utilización actual: <b>{fmt_pct(util_mes)}</b> {sem_actual}</span>
            </h4>
            <p style='margin:5px 0; font-size:13px'>
                📋 Estado: <b>{estado}</b> &nbsp;|&nbsp;
                ⏰ Contrato: <b>{contrato} hrs</b> &nbsp;|&nbsp;
                📅 Antigüedad: <b>{ant_texto}</b> &nbsp;|&nbsp;
                📊 Prom. hist.: <b>{fmt_pct(promedio)}</b> &nbsp;|&nbsp;
                🏗️ Techo según perfil: <b>{fmt_pct(techo_ag)}</b> &nbsp;|&nbsp;
                🎯 Obj. Cap. Operativa: <b>{objetivo_copc:.1f}%</b> &nbsp;|&nbsp;
                {tendencia_ag}
            </p>
        </div>""", unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        card_metric(c1, "Techo perfil", fmt_pct(techo_ag), "Máximo según condición contractual", "#9b59b6", "🏗️")
        card_metric(c2, "Utilización actual", fmt_pct(util_mes), "Resultado real del mes seleccionado", "#2ecc71", "📈")
        card_metric(c3, "Distancia al techo", fmt_brecha_clara(brecha_techo), "Mientras más alto, más lejos de su techo máximo", "#f39c12", "📉")

        meses_ag = [m for m in meses_orden if m in hist_ag_full.columns]
        vals_ag = [float(ag.get(m)) if pd.notna(ag.get(m)) else None for m in meses_ag]
        pendiente = pendiente_lineal(vals_ag)
        meses_fut_ag, preds_ag, preds_raw_ag = regresion_3meses(vals_ag, meses_ag, techo_ag)
        comentario = comentario_tendencia_agente(pendiente, cumplimiento_ag)
        lectura_ag = lectura_proyeccion(agente_sel, util_mes, techo_ag, cumplimiento_ag, brecha_techo, pendiente, preds_ag, contexto='agente')
        st.markdown(f"""
        <div style='background:#3498db15; border-left:4px solid #3498db; padding:12px; border-radius:8px; margin-top:10px; margin-bottom:12px'>
            <h4 style='margin:0'>📈 Tendencia y proyección contra techo</h4>
            <p style='margin:4px 0'>{comentario}</p>
            <p style='margin:4px 0; font-size:13px'>{lectura_ag}</p>
            <p style='margin:0; font-size:12px; color:gray'>La proyección conserva la línea de tendencia, pero se limita al techo del perfil para no mostrar resultados imposibles.</p>
        </div>""", unsafe_allow_html=True)

        # Gráfico atractivo de horas separado
        ag_hrs = hrs_mes_scope[hrs_mes_scope['NOMBRE'] == agente_sel] if 'NOMBRE' in hrs_mes_scope.columns else pd.DataFrame()
        if not ag_hrs.empty:
            r = ag_hrs.iloc[0]
            horas_items = {
                'Programado': r.get('Turno_hrs','00:00:00'),
                'Conectado': r.get('Conectado_hrs','00:00:00'),
                'Prod. Reales': r.get('Hrs_Productivas','00:00:00'),
                'Improductivas': r.get('Hrs_Improductivas','00:00:00'),
                'Disponible': r.get('Disponible_hrs','00:00:00'),
                'Desconexión': r.get('Desconexion_hrs','00:00:00'),
                'Exceso descanso': r.get('Descanso_Exceso_hrs','00:00:00')
            }
            horas_df = pd.DataFrame({'Concepto': list(horas_items.keys()), 'Minutos': [hhmmss_a_min(v) for v in horas_items.values()]})
            horas_df['Horas'] = horas_df['Minutos'] / 60
            horas_df['HHMMSS'] = horas_df['Minutos'].apply(min_a_hhmmss)
            fig_horas_ag = px.bar(horas_df.sort_values('Horas'), x='Horas', y='Concepto', orientation='h', text='HHMMSS', title='Detalle de horas del agente')
            fig_horas_ag.update_traces(textposition='outside', textfont=dict(size=12))
            fig_horas_ag.update_layout(height=400, plot_bgcolor='white', margin=dict(l=150,r=80,t=60,b=40))
            st.plotly_chart(fig_horas_ag, use_container_width=True, key="fig_horas_agente")

        st.markdown('### 📊 Gráfico tendencia')
        fig_m = go.Figure()
        fig_m.add_trace(go.Scatter(x=meses_ag, y=vals_ag, mode='lines+markers+text', text=[f"{v:.1f}%" if v else "" for v in vals_ag], textposition='top center', line=dict(color=color_actual, width=3), marker=dict(size=12), name=agente_sel))
        if preds_ag:
            fig_m.add_trace(go.Scatter(x=meses_fut_ag, y=preds_ag, mode='lines+markers+text', text=[f"{v:.1f}%" for v in preds_ag], textposition='top center', name='Proyección', line=dict(color='#9b59b6', dash='dash', width=2), marker=dict(size=10, symbol='diamond')))
        if pd.notna(techo_ag): fig_m.add_hline(y=float(techo_ag), line_dash='dot', line_color='#9b59b6', annotation_text=f'Techo perfil {float(techo_ag):.1f}%')
        fig_m.add_hline(y=objetivo_copc, line_dash='dash', line_color='green', annotation_text=f'COPC {objetivo_copc:.1f}%')
        fig_m.update_layout(height=400, plot_bgcolor='white', yaxis_range=[0,115])
        st.plotly_chart(fig_m, use_container_width=True, key="fig_m_agente")

# ══════════════════════════════════════════
# TAB 4 — AGENTES CRÍTICOS
# ══════════════════════════════════════════
with tab4:
    st.subheader("🔴 Agentes críticos: lectura bruta vs techo")
    base_crit = resumen_scope.copy()
    if is_admin and supervisor_sel == "Todos" and 'JP' in base_crit.columns:
        sup_crit = st.selectbox("Filtrar supervisor", ['Todos'] + sorted(base_crit['JP'].dropna().unique().tolist()), key='sup_tab4')
        if sup_crit != 'Todos':
            base_crit = base_crit[base_crit['JP'] == sup_crit].copy()

    if 'Cumplimiento_Techo' not in base_crit.columns and {'Utilizacion','Techo_Perfil'}.issubset(base_crit.columns):
        base_crit['Cumplimiento_Techo'] = (base_crit['Utilizacion']/base_crit['Techo_Perfil']*100).round(1).clip(upper=100)
    if 'Brecha_vs_Techo' not in base_crit.columns and {'Techo_Perfil','Utilizacion'}.issubset(base_crit.columns):
        base_crit['Brecha_vs_Techo'] = (base_crit['Techo_Perfil'] - base_crit['Utilizacion']).round(1)
    if 'Cuartil_Techo' not in base_crit.columns and 'Cumplimiento_Techo' in base_crit.columns:
        base_crit['Cuartil_Techo'] = base_crit['Cumplimiento_Techo'].apply(cuartil_techo)

    crit_bruto = base_crit[base_crit['Utilizacion'] < 75].copy() if 'Utilizacion' in base_crit.columns else pd.DataFrame()
    # En este tab sólo se muestran agentes en estado crítico o bajo meta respecto a su techo.
    if 'Cuartil_Techo' in base_crit.columns:
        crit_techo = base_crit[base_crit['Cuartil_Techo'].astype(str).str.startswith(('Q0','Q1'))].copy()
    else:
        crit_techo = base_crit[(base_crit['Cumplimiento_Techo'] < 85) | (base_crit['Brecha_vs_Techo'] > 5)].copy() if {'Cumplimiento_Techo','Brecha_vs_Techo'}.issubset(base_crit.columns) else pd.DataFrame()

    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Crítico bruto", len(crit_bruto), "Utilización < 75%")
    c2.metric("🎯 Crítico/Bajo meta vs techo", len(crit_techo), "Q0 o Q1 por cumplimiento de techo")
    c3.metric("👥 Base visible", len(base_crit), "Agentes evaluados")

    st.markdown("#### 🎯 Críticos reales vs techo")
    st.caption("Sólo se muestran agentes críticos o bajo meta respecto a su techo. La utilización bruta queda como referencia dentro de la misma tabla.")
    cols_crit = ['NOMBRE','JP','Tramo_Antiguedad','HRS_CONTRATO','Techo_Perfil','Utilizacion','Cumplimiento_Techo','Brecha_vs_Techo','Cuartil_Techo']
    cm2 = crit_techo[[c for c in cols_crit if c in crit_techo.columns]].copy()
    if 'NOMBRE' in hist_ag_full.columns and 'Veces_Critico' in hist_ag_full.columns:
        extra_hist = hist_ag_full[['NOMBRE','Veces_Critico','Meses_Critico']].drop_duplicates('NOMBRE')
        cm2 = cm2.merge(extra_hist, on='NOMBRE', how='left')
    if not is_admin and 'JP' in cm2.columns:
        cm2 = cm2.drop(columns=['JP'])
    if 'Cumplimiento_Techo' in cm2.columns:
        cm2 = cm2.sort_values(['Cumplimiento_Techo','Brecha_vs_Techo'] if 'Brecha_vs_Techo' in cm2.columns else ['Cumplimiento_Techo'], ascending=[True, False] if 'Brecha_vs_Techo' in cm2.columns else [True])
    rename_crit = {
        'Techo_Perfil':'Utilización Máxima Perfil',
        'Utilizacion':'Utilización Bruta',
        'Cumplimiento_Techo':'Cumplimiento Techo',
        'Brecha_vs_Techo':'Puntos faltantes al techo',
        'Cuartil_Techo':'Clasificación',
        'Veces_Critico':'Veces crítico histórico',
        'Meses_Critico':'Meses crítico histórico'
    }
    cm2 = cm2.rename(columns=rename_crit)
    for c in ['Utilización Máxima Perfil','Utilización Bruta','Cumplimiento Techo']:
        if c in cm2.columns: cm2[c] = cm2[c].apply(fmt_pct)
    if 'Puntos faltantes al techo' in cm2.columns:
        cm2['Puntos faltantes al techo'] = cm2['Puntos faltantes al techo'].apply(fmt_brecha_clara)
    st.dataframe(cm2, use_container_width=True, key="tabla_criticos_techo")

# ══════════════════════════════════════════
# TAB 5 — CONTROL DE HORAS
# ══════════════════════════════════════════
with tab5:
    st.subheader("⏱️ Control de Horas — Análisis de Fuga")
    vista  = st.radio("Ver por:", ["Mes","Semana","Día"], horizontal=True, key="vista_hrs")
    jp_h   = ["Todos"] + sorted(hrs_mes_scope['JP'].dropna().unique().tolist()) if 'JP' in hrs_mes_scope.columns else ['Todos']
    jp_sel = st.selectbox("Filtrar supervisor", jp_h, key="jp_hrs") if is_admin else None

    if vista == "Mes":
        dh = hrs_mes_scope.copy(); th = mes_sel
    elif vista == "Semana":
        sems = sorted(hrs_sem_scope['Semana'].dropna().unique().tolist()) if 'Semana' in hrs_sem_scope.columns else []
        ss = st.selectbox("Selecciona semana", sems, key="sem_hrs") if sems else None
        dh = hrs_sem_scope[hrs_sem_scope['Semana'] == ss].copy() if ss else pd.DataFrame(); th = ss or "Semana"
    else:
        fecs = sorted(hrs_dia_scope['Fecha'].dropna().unique().tolist()) if 'Fecha' in hrs_dia_scope.columns else []
        fs = st.selectbox("Selecciona fecha", fecs, key="fecha_hrs") if fecs else None
        dh = hrs_dia_scope[hrs_dia_scope['Fecha'] == fs].copy() if fs else pd.DataFrame(); th = str(fs) if fs else "Día"

    if is_admin and jp_sel and jp_sel != "Todos" and 'JP' in dh.columns:
        dh = dh[dh['JP'] == jp_sel]

    ags_h = ["Todos"] + sorted(dh['NOMBRE'].dropna().unique().tolist()) if 'NOMBRE' in dh.columns and len(dh) > 0 else ['Todos']
    ag_sel = st.selectbox("Filtrar agente", ags_h, key="agente_hrs")
    if ag_sel != "Todos" and 'NOMBRE' in dh.columns:
        dh = dh[dh['NOMBRE'] == ag_sel]

    estados_graf = {
        'EnCola_hrs':'📞 En Cola','Ocioso_hrs':'💤 Ocioso','Interactuando_hrs':'🗣️ Interactuando','Disponible_hrs':'🟡 Disponible',
        'Bano_hrs':'🚽 Baño','AusenteOcupado_hrs':'🚫 Ausente Ocupado','Descanso_Exceso_hrs':'⚠️ Exceso Descanso/Comida',
        'Reunion_hrs':'👥 Reunión','Capacitacion_hrs':'📚 Capacitación','NoResponde_hrs':'📵 No Responde','Gestion_hrs':'📝 Gestión',
        'LlamadaManual_hrs':'📲 Llamada Manual','PausaActiva_hrs':'🏃 Pausa Activa','Desconexion_hrs':'⚫ Desconexión Total'
    }
    estados_tabla = {
        'Turno_hrs':'📅 Hrs turno prog.','Conectado_hrs':'🔌 Hrs. Conexión total','Hrs_Prod_Contrato':'📋 Hrs prod. Cont.',
        'Hrs_Productivas':'✅ Hrs. Prod. Reales','Hrs_Improductivas':'❌ Hrs. Improd. Reales','Desconexion_hrs':'⚫ Desconexión',
        'Disponible_hrs':'🟡 Disponible','EnCola_hrs':'📞 En Cola','Ocioso_hrs':'💤 Ocioso','Interactuando_hrs':'🗣️ Interactuando',
        'Descanso_hrs':'☕ Descanso real','Comida_hrs':'🍽️ Comida real','Descanso_Exceso_hrs':'⚠️ Exceso descanso','Bano_hrs':'🚽 Baño',
        'AusenteOcupado_hrs':'🚫 Ausente Ocupado','Reunion_hrs':'👥 Reunión','Capacitacion_hrs':'📚 Capacitación','NoResponde_hrs':'📵 No Responde',
        'Gestion_hrs':'📝 Gestión','LlamadaManual_hrs':'📲 Llamada Manual','PausaActiva_hrs':'🏃 Pausa Activa'
    }
    prod_labels = ['📞 En Cola','💤 Ocioso','🗣️ Interactuando']
    all_cols_hrs = list(estados_graf.keys()) + ['Conectado_hrs','Turno_hrs','Hrs_Productivas','Hrs_Improductivas','Disponible_hrs','Desconexion_hrs','Hrs_Prod_Contrato']

    def render_graficos_horas(row_data_min, titulo_graf, key_prefix):
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        for ch, lb, kh, co in [
            (c1,'📅 Programado','Turno_hrs','#9b59b6'),(c2,'🔌 Conectado','Conectado_hrs','#3498db'),
            (c3,'✅ Productivas','Hrs_Productivas','#2ecc71'),(c4,'❌ Improductivas','Hrs_Improductivas','#e74c3c'),
            (c5,'🟡 Disponible','Disponible_hrs','#f39c12'),(c6,'⚫ Desconexión','Desconexion_hrs','#7f8c8d')]:
            val_min = row_data_min.get(kh, 0)
            ch.markdown(f"""<div style='background:{co}20; border-left:4px solid {co}; padding:8px; border-radius:5px'>
                <p style='margin:0; font-size:11px; color:gray'>{lb}</p><p style='margin:0; font-size:15px; font-weight:bold'>{min_a_hhmmss(val_min)}</p></div>""", unsafe_allow_html=True)
        st.markdown('---')
        estados_min = {v: row_data_min.get(k, 0) for k,v in estados_graf.items() if row_data_min.get(k, 0) > 0}
        total_min = sum(estados_min.values())
        est_sort = dict(sorted(estados_min.items(), key=lambda x: x[1], reverse=True))
        est_hrs = {k: v/60 for k,v in est_sort.items()}
        colores_b = []
        for k in est_hrs:
            if k in prod_labels: colores_b.append('#2ecc71')
            elif k == '⚫ Desconexión Total': colores_b.append('#7f8c8d')
            elif k == '🟡 Disponible': colores_b.append('#f39c12')
            elif k == '⚠️ Exceso Descanso/Comida': colores_b.append('#e67e22')
            else: colores_b.append('#e74c3c')
        textos_b = [f"{min_a_hhmmss(v*60)} ({v*60/total_min*100:.1f}%)" if total_min > 0 else min_a_hhmmss(v*60) for v in est_hrs.values()]
        fig_hrs = go.Figure(go.Bar(x=list(est_hrs.values()), y=list(est_hrs.keys()), orientation='h', marker_color=colores_b, text=textos_b, textposition='outside', textfont=dict(size=11)))
        fig_hrs.update_layout(title=f"Horas por Estado — {titulo_graf}", height=560, plot_bgcolor='white', xaxis_title='Horas', margin=dict(t=60))
        st.plotly_chart(fig_hrs, use_container_width=True, key=f"fig_hrs_{key_prefix}")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            pm=row_data_min.get('Hrs_Productivas',0); im=row_data_min.get('Hrs_Improductivas',0); dm=row_data_min.get('Desconexion_hrs',0); dm2=row_data_min.get('Disponible_hrs',0)
            fig_pie = go.Figure(go.Pie(labels=[f'✅ Productivas\n{min_a_hhmmss(pm)}',f'❌ Improductivas\n{min_a_hhmmss(im)}',f'🟡 Disponible\n{min_a_hhmmss(dm2)}',f'⚫ Desconexión\n{min_a_hhmmss(dm)}'], values=[pm,im,dm2,dm], hole=0.4, marker_colors=['#2ecc71','#e74c3c','#f39c12','#7f8c8d']))
            fig_pie.update_traces(textinfo='label+percent', textfont=dict(size=11)); fig_pie.update_layout(title='Distribución de Horas', height=450, margin=dict(t=60))
            st.plotly_chart(fig_pie, use_container_width=True, key=f"fig_pie_{key_prefix}")
        with col_p2:
            imp_est = {k:v for k,v in estados_min.items() if k not in prod_labels and k not in ['⚫ Desconexión Total','🟡 Disponible'] and v > 0}
            if imp_est:
                labels_imp = [f"{k}\n{min_a_hhmmss(v)}" for k,v in imp_est.items()]
                fig_p2 = go.Figure(go.Pie(labels=labels_imp, values=list(imp_est.values()), hole=0.4))
                fig_p2.update_traces(textinfo='label+percent', textfont=dict(size=11)); fig_p2.update_layout(title='🔍 Desglose Improductivas', height=450, margin=dict(t=60))
                st.plotly_chart(fig_p2, use_container_width=True, key=f"fig_pie2_{key_prefix}")
        st.markdown("""<div style='background:#2c3e5020; border-left:4px solid #3498db; padding:10px; border-radius:5px; margin-top:12px; font-size:13px'>
            📵 <b>Nota — "No Responde":</b> Activado automáticamente por el sistema IVR. No es seleccionado manualmente. ⚠️ <b>NO afecta el cálculo de Utilización.</b></div>""", unsafe_allow_html=True)

    if len(dh) > 0 and ag_sel != 'Todos':
        rh = dh.iloc[0]
        row_min = {col: hhmmss_a_min(rh.get(col,'00:00:00')) for col in all_cols_hrs}
        render_graficos_horas(row_min, f"{ag_sel} — {th}", "ag")
    elif len(dh) > 0:
        titulo_agg = f"{jp_sel or user_jp} — {th}" if (jp_sel or not is_admin) else f"Servicio completo — {th}"
        st.info(f"📊 Vista agregada — {len(dh)} agentes")
        row_min_agg = agregar_horas_grupo(dh, all_cols_hrs)
        render_graficos_horas(row_min_agg, titulo_agg, "agg")
    else:
        st.info("Sin datos de horas para esta selección.")

    st.markdown('---')
    st.markdown('#### 📋 Tabla Detalle por Estado')
    if len(dh) > 0:
        cols_d = [c for c in estados_tabla if c in dh.columns]
        th_tabla = dh[['NOMBRE'] + cols_d].copy().rename(columns=estados_tabla) if 'NOMBRE' in dh.columns else dh[cols_d].copy().rename(columns=estados_tabla)
        st.dataframe(th_tabla, use_container_width=True, key='tabla_horas')

# ══════════════════════════════════════════
# TAB 6 — GLOSARIO
# ══════════════════════════════════════════
with tab6:
    st.subheader("📖 Glosario de Métricas — Indicadores de Eficiencia")
    st.markdown("Referencia oficial de cálculos, definiciones y simbología utilizadas en este dashboard.")
    st.markdown('---')
    st.markdown("### 🕐 Estructura de Tiempos")
    st.markdown("""
<div style='display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px'>
  <div style='flex:1; min-width:200px; background:#2ecc7120; border:2px solid #2ecc71; border-radius:10px; padding:14px; text-align:center'><p style='margin:0; font-size:13px; color:#2ecc71; font-weight:bold'>1️⃣ TIEMPO OCUPADO</p><p style='margin:6px 0 0 0; font-size:12px; color:#ccc'>🗣️ Talking — Conversando<br>⏸️ HOLD — En espera<br>📝 ACW — Post llamada</p></div>
  <div style='flex:1; min-width:200px; background:#3498db20; border:2px solid #3498db; border-radius:10px; padding:14px; text-align:center'><p style='margin:0; font-size:13px; color:#3498db; font-weight:bold'>2️⃣ TIEMPO PRODUCTIVO</p><p style='margin:6px 0 0 0; font-size:12px; color:#ccc'>= Tiempo Ocupado<br>+ 🟡 Disponible (En Cola / Ocioso)</p></div>
  <div style='flex:1; min-width:200px; background:#9b59b620; border:2px solid #9b59b6; border-radius:10px; padding:14px; text-align:center'><p style='margin:0; font-size:13px; color:#9b59b6; font-weight:bold'>3️⃣ TIEMPO LOGUEADO</p><p style='margin:6px 0 0 0; font-size:12px; color:#ccc'>= Tiempo Productivo<br>+ ⚠️ Tiempos Improductivos</p></div>
  <div style='flex:1; min-width:200px; background:#e74c3c20; border:2px solid #e74c3c; border-radius:10px; padding:14px; text-align:center'><p style='margin:0; font-size:13px; color:#e74c3c; font-weight:bold'>📅 TIEMPO PROGRAMADO</p><p style='margin:6px 0 0 0; font-size:12px; color:#ccc'>Turno planificado por WFM<br>Base para cálculo de Adhesión</p></div>
</div>""", unsafe_allow_html=True)

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.markdown("""<div style='background:#3498db15; border:1px solid #3498db; border-radius:10px; padding:16px'><p style='margin:0; font-size:14px; font-weight:bold; color:#3498db'>📈 Utilización Bruta (%)</p><div style='background:#ffffff15; border-radius:6px; padding:10px; margin:10px 0; text-align:center'><p style='margin:0; color:white'>Tiempos Productivos</p><hr style='border-color:#555; margin:4px 0'><p style='margin:0; color:white'>Tiempos Logueados</p></div><p style='margin:0; font-size:12px; color:#aaa'>Es la utilización real calculada en base a tiempos productivos y logueo.</p></div>""", unsafe_allow_html=True)
    with col_f2:
        st.markdown("""<div style='background:#2ecc7115; border:1px solid #2ecc71; border-radius:10px; padding:16px'><p style='margin:0; font-size:14px; font-weight:bold; color:#2ecc71'>✅ Adhesión (%)</p><div style='background:#ffffff15; border-radius:6px; padding:10px; margin:10px 0; text-align:center'><p style='margin:0; color:white'>Tiempos Logueados</p><hr style='border-color:#555; margin:4px 0'><p style='margin:0; color:white'>Tiempo Programado</p></div><p style='margin:0; font-size:12px; color:#aaa'>🎯 ≥ 99% Óptimo | 96.5–98.9% Medio | &lt;96.5% Crítico</p></div>""", unsafe_allow_html=True)
    with col_f3:
        st.markdown("""<div style='background:#e67e2215; border:1px solid #e67e22; border-radius:10px; padding:16px'><p style='margin:0; font-size:14px; font-weight:bold; color:#e67e22'>⚡ Ocupación (%)</p><div style='background:#ffffff15; border-radius:6px; padding:10px; margin:10px 0; text-align:center'><p style='margin:0; color:white'>Tiempo Ocupado</p><hr style='border-color:#555; margin:4px 0'><p style='margin:0; color:white'>Tiempos Productivos</p></div><p style='margin:0; font-size:12px; color:#aaa'>🎯 50–55% Óptimo | 40–49% o 56–65% Medio | &lt;40% o &gt;65% Crítico</p></div>""", unsafe_allow_html=True)

    st.markdown('---')
    st.markdown('### 📚 Términos del modelo de capacidad')
    glosario = pd.DataFrame([
        ['Techo por perfil', 'Utilización máxima que un agente puede alcanzar según condición contractual, convenio, descansos extendidos, lactancia u otras restricciones estructurales.'],
        ['Techo estructural del servicio', 'Máximo alcanzable del servicio considerando la mezcla real de agentes y sus perfiles contractuales.'],
        ['Techo estructural JP', 'Máximo alcanzable del equipo de un supervisor según la composición real de su dotación.'],
        ['Cumplimiento de techo', 'Relación entre la utilización real y el techo máximo posible. Permite evaluar si el agente/equipo está cerca de su capacidad real.'],
        ['Brecha vs techo', 'Puntos porcentuales entre la utilización real y la utilización máxima posible. Mide capacidad disponible por desarrollar.'],
        ['Brecha vs COPC', 'Diferencia entre la utilización real y el objetivo corporativo COPC de 86%. Se muestra como referencia, no como único criterio de evaluación.'],
        ['Tendencia', 'Dirección del comportamiento del indicador en el tiempo. En agentes se estima con la pendiente lineal mes a mes; en JP compara el mes actual contra el promedio previo.'],
        ['Score de Gestión JP', 'Índice de 0 a 100 que combina 60% cumplimiento del techo del equipo y 40% tendencia al alza. Busca reconocer gestión justa según capacidad estructural.'],
        ['Mejor gestión operacional', 'Supervisor con mayor Score de Gestión JP del período.'],
        ['Mayor crecimiento', 'Supervisor con mayor tendencia positiva de utilización.'],
        ['Mayor capacidad disponible', 'Supervisor con mayor brecha entre utilización real y techo estructural de equipo.'],
        ['Crítico bruto', 'Agente con utilización menor a 75% sin considerar su techo por perfil.'],
        ['Crítico vs techo', 'Agente lejano a su máximo posible, medido por bajo cumplimiento de techo o alta brecha vs techo.'],
        ['No Responde', 'Estado automático del sistema IVR. No es seleccionado manualmente y no afecta el cálculo de utilización.']
    ], columns=['Término','Definición'])
    st.dataframe(glosario, use_container_width=True, hide_index=True)

st.markdown('---')
st.markdown("""
<div style='text-align:center; color:gray; font-size:12px'>
    📊 Dashboard KPI — Servicio Técnico ECC &nbsp;|&nbsp;
    👩‍💼 Desarrollado por: <b>Paola Agüero — Owner Capacidad Operativa</b>
</div>""", unsafe_allow_html=True)
