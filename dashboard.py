import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
import numpy as np

st.set_page_config(
    page_title="Dashboard KPI — Servicio Técnico ECC",
    page_icon="📊",
    layout="wide"
)

# =============================================
# SEMÁFOROS POR KPI
# =============================================
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
    else:  # utilizacion
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

archivo = st.file_uploader("📁 Sube el archivo Dashboard_KPI_MesAño.xlsx", type="xlsx")

if archivo:
    resumen   = pd.read_excel(archivo, sheet_name="Resumen_Agentes")
    jefatura  = pd.read_excel(archivo, sheet_name="Resumen_Jefatura")
    jp_semana = pd.read_excel(archivo, sheet_name="JP_Semana")
    jp_dia    = pd.read_excel(archivo, sheet_name="JP_Dia")
    historico = pd.read_excel(archivo, sheet_name="Historico")
    criticos  = pd.read_excel(archivo, sheet_name="Agentes_Criticos")
    hist_ag   = pd.read_excel(archivo, sheet_name="Historico_Agente")
    semanal   = pd.read_excel(archivo, sheet_name="Resumen_Semanal")
    diario    = pd.read_excel(archivo, sheet_name="Detalle_Diario")

    # Semáforos por KPI
    resumen["Semaforo"]     = resumen["Utilizacion"].apply(lambda x: semaforo(x, "utilizacion"))
    resumen["Semaforo_Adh"] = resumen["Adhesion"].apply(lambda x: semaforo(x, "adhesion"))
    resumen["Semaforo_Ocu"] = resumen["Ocupacion"].apply(lambda x: semaforo(x, "ocupacion"))

    # =============================================
    # FILTROS SIDEBAR
    # =============================================
    st.sidebar.title("🔍 Filtros Globales")
    supervisores = ["Todos"] + sorted(resumen["JP"].dropna().unique().tolist())
    supervisor_sel = st.sidebar.selectbox("Supervisor", supervisores)
    contratos = ["Todos"] + sorted(resumen["HRS_CONTRATO"].dropna().unique().tolist())
    contrato_sel = st.sidebar.selectbox("Horas Contrato", contratos)
    antiguedades = ["Todos"] + sorted(resumen["Tramo_Antiguedad"].dropna().unique().tolist())
    antiguedad_sel = st.sidebar.selectbox("Antigüedad", antiguedades)

    df = resumen.copy()
    if supervisor_sel != "Todos":
        df = df[df["JP"] == supervisor_sel]
    if contrato_sel != "Todos":
        df = df[df["HRS_CONTRATO"] == contrato_sel]
    if antiguedad_sel != "Todos":
        df = df[df["Tramo_Antiguedad"] == antiguedad_sel]

    # =============================================
    # MÉTRICAS PRINCIPALES
    # =============================================
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

    # =============================================
    # TABS
    # =============================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Resumen Mensual",
        "🏅 Ranking y Acumulado",
        "👤 Evolución por Agente",
        "🔴 Agentes Críticos"
    ])

    # ══════════════════════════════════════════
    # TAB 1 — RESUMEN MENSUAL
    # ══════════════════════════════════════════
    with tab1:
        col_izq, col_der = st.columns(2)

        with col_izq:
            st.subheader("🏆 Ranking Utilización por Agente")
            ranking = df.sort_values("Utilizacion", ascending=True).copy()
            fig1 = px.bar(
                ranking, x="Utilizacion", y="NOMBRE",
                color="Semaforo", color_discrete_map=colores_semaforo,
                orientation="h", text="Utilizacion"
            )
            fig1.add_vline(x=75, line_dash="dash", line_color="orange",
                          annotation_text="Meta 75%")
            fig1.add_vline(x=86, line_dash="dash", line_color="green",
                          annotation_text="Óptimo 86%")
            fig1.update_traces(texttemplate="%{text:.1f}%",
                              textposition="outside",
                              textfont=dict(size=11))
            fig1.update_layout(height=600, plot_bgcolor="white")
            st.plotly_chart(fig1, use_container_width=True)

        with col_der:
            st.subheader("🚦 Distribución Semáforo — Utilización")
            dist = df["Semaforo"].value_counts().reset_index()
            dist.columns = ["Nivel", "Agentes"]
            fig2 = px.pie(dist, values="Agentes", names="Nivel",
                         color="Nivel", color_discrete_map=colores_semaforo,
                         hole=0.4)
            fig2.update_traces(textinfo="label+percent+value",
                              textfont=dict(size=12))
            fig2.update_layout(height=300)
            st.plotly_chart(fig2, use_container_width=True)

            st.subheader("👥 KPIs por Jefatura")
            fig3 = go.Figure()
            for kpi, color in zip(["Utilizacion","Adhesion","Ocupacion"],
                                   ["#3498db","#2ecc71","#e67e22"]):
                fig3.add_trace(go.Bar(
                    name=kpi, x=jefatura["JP"], y=jefatura[kpi],
                    text=jefatura[kpi],
                    texttemplate="%{text:.1f}%",
                    textposition="outside",
                    textfont=dict(size=11),
                    marker_color=color
                ))
            fig3.add_hline(y=75, line_dash="dash", line_color="orange",
                          annotation_text="Meta Util 75%")
            fig3.update_layout(barmode="group", height=350,
                              xaxis_tickangle=-45, plot_bgcolor="white")
            st.plotly_chart(fig3, use_container_width=True)

        # Evolución histórica
        st.subheader("📈 Evolución Histórica del Servicio")
        meses_disp = [m for m in meses_orden if m in historico.columns]
        promedios  = historico[meses_disp].mean() * 100

        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(
            x=meses_disp, y=promedios.tolist(),
            mode="lines+markers+text",
            text=[f"{v:.1f}%" for v in promedios],
            textposition="top center",
            textfont=dict(size=12, color="white"),
            line=dict(color="#3498db", width=3),
            marker=dict(size=12,
                       color=[colores_semaforo[semaforo(v,"utilizacion")]
                              for v in promedios],
                       line=dict(width=2, color="white")),
            name="Real"
        ))
        X = np.arange(len(promedios)).reshape(-1,1)
        modelo = LinearRegression().fit(X, promedios.values)
        meses_fut = ["Abril","Mayo","Junio"]
        preds = modelo.predict(
            np.arange(len(promedios), len(promedios)+3).reshape(-1,1)
        )
        fig4.add_trace(go.Scatter(
            x=meses_fut, y=preds.tolist(),
            mode="lines+markers+text",
            text=[f"{v:.1f}%" for v in preds],
            textposition="top center",
            textfont=dict(size=12, color="white"),
            name="Proyección",
            line=dict(color="#9b59b6", dash="dash", width=3),
            marker=dict(size=12, symbol="diamond")
        ))
        fig4.add_hrect(y0=0,  y1=75,  fillcolor="#e74c3c", opacity=0.05)
        fig4.add_hrect(y0=75, y1=86,  fillcolor="#f1c40f", opacity=0.05)
        fig4.add_hrect(y0=86, y1=100, fillcolor="#2ecc71", opacity=0.05)
        fig4.add_hline(y=75, line_dash="dash", line_color="orange",
                      annotation_text="Meta 75%")
        fig4.add_hline(y=86, line_dash="dash", line_color="green",
                      annotation_text="Óptimo 86%")
        fig4.update_layout(height=450, plot_bgcolor="white")
        st.plotly_chart(fig4, use_container_width=True)

        # Tabla resumen con los 3 semáforos
        st.subheader("📋 Resumen Completo por Agente")
        cols_tabla = ["NOMBRE","JP","HRS_CONTRATO","ESTADO","Tramo_Antiguedad",
                      "Utilizacion","Semaforo",
                      "Adhesion","Semaforo_Adh",
                      "Ocupacion","Semaforo_Ocu"]
        tabla = df[cols_tabla].sort_values("Utilizacion", ascending=False).copy()
        for col in ["Utilizacion","Adhesion","Ocupacion"]:
            tabla[col] = tabla[col].apply(
                lambda x: f"{x:.1f}%" if pd.notna(x) else ""
            )
        st.dataframe(tabla, use_container_width=True)

    # ══════════════════════════════════════════
    # TAB 2 — RANKING Y ACUMULADO
    # ══════════════════════════════════════════
    with tab2:
        st.subheader("🏅 Ranking y Acumulado por Período")
        periodo = st.radio("Ver por:", ["Mes","Semana","Día"], horizontal=True)

        if periodo == "Mes":
            data_jp = jefatura.copy()
            data_ag = resumen.copy()
            titulo_periodo = "Marzo 2026"
        elif periodo == "Semana":
            semanas_disp = sorted(jp_semana["Semana"].dropna().unique().tolist())
            semana_sel = st.selectbox("Selecciona semana", semanas_disp)
            data_jp = jp_semana[jp_semana["Semana"] == semana_sel].copy()
            data_ag = semanal[semanal["Semana"] == semana_sel].copy()
            titulo_periodo = semana_sel
        else:
            fechas_disp = sorted(jp_dia["Fecha"].dropna().unique().tolist())
            fecha_sel = st.selectbox("Selecciona fecha", fechas_disp)
            data_jp = jp_dia[jp_dia["Fecha"] == fecha_sel].copy()
            data_ag = diario[diario["Fecha"] == fecha_sel].dropna(
                subset=["Utilizacion"]).copy()
            titulo_periodo = str(fecha_sel)

        data_jp["Semaforo"] = data_jp["Utilizacion"].apply(
            lambda x: semaforo(x, "utilizacion"))
        data_ag["Semaforo"] = data_ag["Utilizacion"].apply(
            lambda x: semaforo(x, "utilizacion"))

        # Ranking supervisores
        st.markdown(f"### 👔 Ranking Supervisores — {titulo_periodo}")
        col_r1, col_r2 = st.columns([2,1])

        with col_r1:
            jp_rank = data_jp.sort_values("Utilizacion", ascending=True)
            fig_jp = px.bar(
                jp_rank, x="Utilizacion", y="JP",
                color="Semaforo", color_discrete_map=colores_semaforo,
                orientation="h", text="Utilizacion",
                title=f"Utilización por Supervisor — {titulo_periodo}"
            )
            fig_jp.add_vline(x=75, line_dash="dash", line_color="orange",
                            annotation_text="Meta 75%")
            fig_jp.add_vline(x=86, line_dash="dash", line_color="green",
                            annotation_text="Óptimo 86%")
            fig_jp.update_traces(texttemplate="%{text:.1f}%",
                                textposition="outside",
                                textfont=dict(size=11))
            fig_jp.update_layout(height=450, plot_bgcolor="white")
            st.plotly_chart(fig_jp, use_container_width=True)

        with col_r2:
            st.markdown("#### 🥇 Top 3 Mejor Performance")
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
                </div>
                """, unsafe_allow_html=True)

            st.markdown("#### ⚠️ Top 3 Menor Performance")
            bot3 = data_jp.sort_values("Utilizacion").head(3)
            for _, row in bot3.iterrows():
                color = colores_semaforo[semaforo(row["Utilizacion"],"utilizacion")]
                nombre_corto = " ".join(row["JP"].split()[:2])
                st.markdown(f"""
                <div style='background:{color}20; border-left:4px solid {color};
                            padding:8px; border-radius:5px; margin-bottom:8px'>
                    <b>⚠️ {nombre_corto}</b><br>
                    Utilización: <b>{row['Utilizacion']:.1f}%</b>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        # Ranking agentes
        st.markdown(f"### 👤 Ranking Agentes — {titulo_periodo}")
        jp_opciones = ["Todos"] + sorted(data_ag["JP"].dropna().unique().tolist())
        jp_filtro = st.selectbox("Filtrar por supervisor", jp_opciones, key="jp_rank")

        data_ag_fil = data_ag.copy()
        if jp_filtro != "Todos":
            data_ag_fil = data_ag_fil[data_ag_fil["JP"] == jp_filtro]
        data_ag_fil = data_ag_fil.sort_values("Utilizacion", ascending=True)

        fig_ag = px.bar(
            data_ag_fil, x="Utilizacion", y="NOMBRE",
            color="Semaforo", color_discrete_map=colores_semaforo,
            orientation="h", text="Utilizacion",
            title=f"Ranking Agentes — {jp_filtro} — {titulo_periodo}"
        )
        fig_ag.add_vline(x=75, line_dash="dash", line_color="orange",
                        annotation_text="Meta 75%")
        fig_ag.add_vline(x=86, line_dash="dash", line_color="green",
                        annotation_text="Óptimo 86%")
        fig_ag.update_traces(texttemplate="%{text:.1f}%",
                            textposition="outside",
                            textfont=dict(size=11))
        fig_ag.update_layout(height=600, plot_bgcolor="white")
        st.plotly_chart(fig_ag, use_container_width=True)

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("👥 Agentes", len(data_ag_fil))
        metrica_color(col_m2, "📈 Utilización",
                     data_ag_fil["Utilizacion"].mean(), "utilizacion")
        metrica_color(col_m3, "✅ Adhesión",
                     data_ag_fil["Adhesion"].mean(), "adhesion")
        metrica_color(col_m4, "⚡ Ocupación",
                     data_ag_fil["Ocupacion"].mean(), "ocupacion")

    # ══════════════════════════════════════════
    # TAB 3 — EVOLUCIÓN POR AGENTE
    # ══════════════════════════════════════════
    with tab3:
        st.subheader("👤 Evolución Histórica por Agente")

        col_a, col_b = st.columns(2)
        with col_a:
            sup_ag = st.selectbox(
                "Filtrar supervisor",
                ["Todos"] + sorted(hist_ag["Jefe_de_plataforma"].dropna().unique().tolist()),
                key="sup_ag"
            )
        hist_fil = hist_ag.copy()
        if sup_ag != "Todos":
            hist_fil = hist_fil[hist_fil["Jefe_de_plataforma"] == sup_ag]

        with col_b:
            agente_sel = st.selectbox(
                "Selecciona agente",
                sorted(hist_fil["Nombre_agente"].dropna().unique().tolist()),
                key="agente_sel"
            )

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
        </div>
        """, unsafe_allow_html=True)

        # Gráfico 1 — Histórico mensual
        st.markdown("#### 📅 Evolución Mensual")
        meses_ag = [m for m in meses_orden if m in hist_ag.columns]
        vals_ag  = [ag[m] if pd.notna(ag.get(m)) else None for m in meses_ag]

        fig_m = go.Figure()
        fig_m.add_trace(go.Scatter(
            x=meses_ag, y=vals_ag,
            mode="lines+markers+text",
            text=[f"{v:.1f}%" if v else "" for v in vals_ag],
            textposition="top center",
            textfont=dict(size=12, color="white"),
            line=dict(color=color_ag, width=3),
            marker=dict(size=14,
                       color=[colores_semaforo[semaforo(v,"utilizacion")]
                              if v else "#95a5a6" for v in vals_ag],
                       line=dict(width=2, color="white")),
            name=agente_sel
        ))
        fig_m.add_hrect(y0=0,  y1=75,  fillcolor="#e74c3c", opacity=0.05)
        fig_m.add_hrect(y0=75, y1=86,  fillcolor="#f1c40f", opacity=0.05)
        fig_m.add_hrect(y0=86, y1=100, fillcolor="#2ecc71", opacity=0.05)
        fig_m.add_hline(y=75, line_dash="dash", line_color="orange",
                       annotation_text="Meta 75%")
        fig_m.add_hline(y=86, line_dash="dash", line_color="green",
                       annotation_text="Óptimo 86%")
        fig_m.update_layout(height=380, plot_bgcolor="white", yaxis_range=[0,115])
        st.plotly_chart(fig_m, use_container_width=True)

        # Gráfico 2 — Evolución semanal
        st.markdown("#### 📆 Evolución Semanal — Mes Actual")
        ag_sem = semanal[semanal["NOMBRE"] == agente_sel].sort_values("Semana")

        if not ag_sem.empty:
            fig_s = go.Figure()
            fig_s.add_trace(go.Bar(
                x=ag_sem["Semana"], y=ag_sem["Utilizacion"],
                text=ag_sem["Utilizacion"],
                texttemplate="%{text:.1f}%",
                textposition="outside",
                textfont=dict(size=12, color="white"),
                marker_color=[colores_semaforo[semaforo(v,"utilizacion")]
                             for v in ag_sem["Utilizacion"]],
                name="Utilización"
            ))
            fig_s.add_hline(y=75, line_dash="dash", line_color="orange",
                           annotation_text="Meta 75%")
            fig_s.add_hline(y=86, line_dash="dash", line_color="green",
                           annotation_text="Óptimo 86%")
            fig_s.add_hrect(y0=0,  y1=75,  fillcolor="#e74c3c", opacity=0.05)
            fig_s.add_hrect(y0=75, y1=86,  fillcolor="#f1c40f", opacity=0.05)
            fig_s.add_hrect(y0=86, y1=100, fillcolor="#2ecc71", opacity=0.05)
            fig_s.update_layout(height=350, plot_bgcolor="white",
                               yaxis_range=[0,115])
            st.plotly_chart(fig_s, use_container_width=True)
        else:
            st.info("No hay datos semanales para este agente")

        # Gráfico 3 — Evolución diaria
        st.markdown("#### 📊 Evolución Diaria — Mes Actual")
        ag_dia = diario[diario["NOMBRE"] == agente_sel].dropna(
            subset=["Utilizacion"]
        ).sort_values("Fecha")

        if not ag_dia.empty:
            fig_d = go.Figure()
            fig_d.add_trace(go.Scatter(
                x=ag_dia["Fecha"].astype(str),
                y=ag_dia["Utilizacion"],
                mode="lines+markers+text",
                text=[f"{v:.1f}%" for v in ag_dia["Utilizacion"]],
                textposition="top center",
                textfont=dict(size=11, color="white"),
                line=dict(color=color_ag, width=2),
                marker=dict(size=10,
                           color=[colores_semaforo[semaforo(v,"utilizacion")]
                                  for v in ag_dia["Utilizacion"]],
                           line=dict(width=2, color="white")),
                name="Utilización diaria"
            ))
            fig_d.add_hrect(y0=0,  y1=75,  fillcolor="#e74c3c", opacity=0.05)
            fig_d.add_hrect(y0=75, y1=86,  fillcolor="#f1c40f", opacity=0.05)
            fig_d.add_hrect(y0=86, y1=100, fillcolor="#2ecc71", opacity=0.05)
            fig_d.add_hline(y=75, line_dash="dash", line_color="orange",
                           annotation_text="Meta 75%")
            fig_d.add_hline(y=86, line_dash="dash", line_color="green",
                           annotation_text="Óptimo 86%")
            fig_d.update_layout(height=400, plot_bgcolor="white",
                               yaxis_range=[0,115], xaxis_tickangle=-45)
            st.plotly_chart(fig_d, use_container_width=True)
        else:
            st.info("No hay datos diarios para este agente")

    # ══════════════════════════════════════════
    # TAB 4 — AGENTES CRÍTICOS
    # ══════════════════════════════════════════
    with tab4:
        criticos_fil = criticos.copy()
        if supervisor_sel != "Todos":
            criticos_fil = criticos_fil[criticos_fil["JP"] == supervisor_sel]

        st.subheader(f"🔴 Agentes en Estado Crítico ({len(criticos_fil)})")
        criticos_mostrar = criticos_fil.copy()
        for col in ["Utilizacion","Adhesion","Ocupacion"]:
            if col in criticos_mostrar.columns:
                criticos_mostrar[col] = criticos_mostrar[col].apply(
                    lambda x: f"{x:.1f}%" if pd.notna(x) else ""
                )
        st.dataframe(criticos_mostrar, use_container_width=True)

        st.markdown("---")
        st.subheader("📋 Tabla Completa")
        cols_tabla = ["NOMBRE","JP","HRS_CONTRATO","ESTADO",
                      "Tramo_Antiguedad",
                      "Utilizacion","Semaforo",
                      "Adhesion","Semaforo_Adh",
                      "Ocupacion","Semaforo_Ocu"]
        tabla_mostrar = df[cols_tabla].sort_values(
            "Utilizacion", ascending=False
        ).copy()
        for col in ["Utilizacion","Adhesion","Ocupacion"]:
            tabla_mostrar[col] = tabla_mostrar[col].apply(
                lambda x: f"{x:.1f}%" if pd.notna(x) else ""
            )
        st.dataframe(tabla_mostrar, use_container_width=True)

else:
    st.info("👆 Sube el archivo Excel para ver el dashboard")