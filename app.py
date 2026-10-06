"""
LogiAndes S.A. — Monitor de KPIs (Taller 2, Grupo 5). Prototipo de dashboard en Streamlit.

Ejecutar:  streamlit run app.py

Todos los KPIs, tablas y gráficos provienen de kpis_grupo5.py, el mismo módulo que usa
el Notebook Taller_2_Grupo5.ipynb. Así lo que se ve aquí coincide con lo calculado allá.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import kpis_grupo5 as kg

st.set_page_config(page_title="LogiAndes · Monitor de KPIs", page_icon="🚚", layout="wide")

RUTA_REFERENCIA = Path(__file__).parent / "outputs" / "kpis_referencia.json"
CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}

st.markdown("""
<style>
.block-container {padding-top: 2rem;}
.kpi {border: 1px solid rgba(11,11,11,.12); border-radius: 10px; padding: 12px 14px; background: #fcfcfb;
      min-height: 205px;}
.kpi.clave {border: 2px solid #1f4e79;}
.kpi .tag {font-size: .68rem; color: #1f4e79; font-weight: 700; text-transform: uppercase; letter-spacing: .03em;
           min-height: 1em;}
.kpi .cod {font-size: .75rem; color: #898781;}
.kpi .nombre {font-size: .88rem; color: #52514e; margin: 0 0 4px; min-height: 2.4em;}
.kpi .valor {font-size: 1.7rem; font-weight: 650; color: #0b0b0b; line-height: 1.15;}
.kpi .estado {font-size: .85rem; font-weight: 600; margin-top: 3px;}
.kpi .meta {font-size: .75rem; color: #6b6a66; margin-top: 6px; line-height: 1.45;}
.pregunta {background: #eef4fc; border-left: 4px solid #1f4e79; padding: 10px 14px; border-radius: 6px; margin-bottom: 14px;}
.alerta {padding: 6px 0; border-bottom: 1px solid #e1e0d9; font-size: .88rem;}
.nota {font-size: .78rem; color: #898781;}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def datos() -> pd.DataFrame:
    return kg.cargar_datos()


df_total = datos()
FILTROS = ["f_region", "f_provincia", "f_canal", "f_cliente"]


def restablecer():
    for k in FILTROS:
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# Barra lateral: audiencia, mes evaluado y filtros (un único lugar para filtrar)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🚚 LogiAndes S.A.")
    audiencia = st.selectbox("Vista para", list(kg.AUDIENCIAS), key="audiencia",
                             help="Ordena y resalta los KPIs de cada área. Los datos no cambian.")
    mes = st.radio("Mes evaluado", [2, 3], index=1, format_func=kg.MESES.get, horizontal=True, key="mes",
                   help="Los KPIs son mensuales. Enero es la línea base de los KPI 1 y 2, por eso no se evalúa.")
    st.divider()
    st.markdown("**Filtros**")
    regiones = st.multiselect("Región", sorted(df_total["region"].unique()), key="f_region", placeholder="Todas")
    prov_disp = sorted(df_total.loc[df_total["region"].isin(regiones) if regiones else slice(None), "provincia"].unique())
    provincias = st.multiselect("Provincia", prov_disp, key="f_provincia", placeholder="Todas")
    canales = st.multiselect("Canal de entrega", list(kg.COLOR_CANAL), key="f_canal", placeholder="Todos")
    clientes = st.multiselect("Tipo de cliente", sorted(df_total["tipo_cliente"].unique()), key="f_cliente",
                              placeholder="Todos")
    st.button("↺ Restablecer filtros", on_click=restablecer, use_container_width=True)

df = df_total
for col, sel in [("region", regiones), ("provincia", [p for p in provincias if p in prov_disp]),
                 ("canal_entrega", canales), ("tipo_cliente", clientes)]:
    if sel:
        df = df[df[col].isin(sel)]
df_mes = df[df["mes_num"] == mes]
activos = [f"{n}: {', '.join(v)}" for n, v in [("Región", regiones), ("Provincia", provincias),
                                                 ("Canal", canales), ("Cliente", clientes)] if v]

with st.sidebar:
    st.divider()
    st.metric(f"Pedidos de {kg.MESES[mes].lower()}", f"{len(df_mes):,}")
    st.caption(f"{len(df):,} pedidos en el trimestre ({len(df) / len(df_total):.0%} del total)")
    st.markdown(f"<div class='nota'>Fuente: {kg.FUENTE}.<br>Unidad de análisis: pedido.<br>"
                f"Metas propuestas con fines académicos.</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Encabezado y validaciones de la selección
# ---------------------------------------------------------------------------
st.title("Monitor de KPIs · LogiAndes S.A.")
st.caption(f"Mes evaluado: {kg.MESES[mes]} 2026 (comparado con {kg.MESES[mes - 1].lower()}) · "
           f"Filtros activos: {' | '.join(activos) if activos else 'ninguno'} · Grupo 5")

if df_mes.empty:
    st.error("La combinación de filtros no tiene pedidos en el mes evaluado. Use **↺ Restablecer filtros**.")
    st.stop()
if len(df_mes) < kg.N_MINIMO:
    st.warning(f"⚠️ Muestra pequeña ({len(df_mes)} pedidos en {kg.MESES[mes].lower()} < {kg.N_MINIMO}). "
               "Las tasas y porcentajes son inestables: no los use para comparar ni para decidir.")

tab_ej, tab_terr, tab_op, tab_gob = st.tabs(
    ["📊 Vista ejecutiva", "🗺️ Análisis territorial", "⚙️ Detalle operativo", "📘 KPIs y gobernanza"])


def color_estado(e: str) -> str:
    return "#9a6f00" if e == "amarillo" else kg.ESTADOS[e]["color"]


def tarjeta(k: str, fila: pd.Series, ticket: float, trim_estado: str | None, clave: bool) -> str:
    d = kg.KPIS[k]
    e = fila["estado"]
    delta = ""
    if pd.notna(fila["variacion"]):
        dif = fila["variacion"]
        mejora = (dif >= 0) == (d["sentido"] == "mayor")
        unidad = "min" if d["unidad"] == "min" else "p.p."
        delta = (f"<span style='color:{'#006300' if mejora else '#c0392b'}'>{'▲' if dif >= 0 else '▼'} "
                 f"{abs(dif):.1f} {unidad}</span> vs {kg.MESES[mes - 1].lower()}")
    elif k in ("k1", "k2") and mes == 2:
        delta = "Primer mes evaluado (enero = línea base)"
    extra = f"Ticket: ${ticket:.2f}<br>" if k == "k2" and pd.notna(ticket) else ""
    if pd.notna(fila["trimestre"]):
        extra += f"Trimestre: {kg.formatear(k, fila['trimestre'])} {kg.ESTADOS[trim_estado]['emoji']}<br>"
    tag = "Clave para su área" if clave else "&nbsp;"
    return (f"<div class='kpi {'clave' if clave else ''}'><div class='tag'>{tag}</div>"
            f"<div class='cod'>{d['codigo']}</div><div class='nombre'>{d['nombre']}</div>"
            f"<div class='valor'>{kg.formatear(k, fila['valor'])}</div>"
            f"<div class='estado' style='color:{color_estado(e)}'>{kg.etiqueta_estado(e)}</div>"
            f"<div class='meta'>Meta {d['umbral_txt'].split('|')[0].strip()[2:]}<br>{extra}{delta}</div></div>")


# ---------------------------------------------------------------------------
# 1. Vista ejecutiva
# ---------------------------------------------------------------------------
with tab_ej:
    info = kg.AUDIENCIAS[audiencia]
    st.markdown(f"<div class='pregunta'><b>{audiencia}</b> · {info['pregunta']}</div>", unsafe_allow_html=True)

    resumen = kg.kpis_empresa(df, mes)
    periodo = kg.tabla_periodo(df).iloc[0]
    ticket_mes = kg.tabla_mensual(df).set_index("mes_num").loc[mes, "ticket_usd"]
    orden = info["kpis"] + [k for k in kg.KPIS if k not in info["kpis"]]
    for c, k in zip(st.columns(5), orden):
        trim_e = periodo.get(f"estado_{k}") if k in ("k3", "k4", "k5") else None
        c.markdown(tarjeta(k, resumen.loc[k], ticket_mes, trim_e, k in info["kpis"]), unsafe_allow_html=True)
    st.markdown("<div class='nota'>Valores de la selección en el mes evaluado. Semáforo: 🟢 Cumple · 🟡 Atención · "
                "🔴 Crítico. KPI 1 y 2 se comparan con enero (línea base); KPI 3–5 incluyen la lectura trimestral "
                "para confirmar tendencias.</div>", unsafe_allow_html=True)
    st.divider()

    st.markdown(f"##### Tablero de semáforos por provincia · {kg.MESES[mes]}")
    matriz = kg.matriz_semaforo(df, mes)
    st.dataframe(matriz, use_container_width=True, height=38 * (len(matriz) + 1) + 4)
    st.caption("Ordenado por número de KPIs en rojo y en atención. El KPI 2 muestra el ticket; su semáforo "
               "compara con el ticket de enero de cada provincia.")
    st.divider()

    c1, c2 = st.columns([2, 3], gap="large")
    with c2:
        st.plotly_chart(kg.fig_matriz_priorizacion(df), use_container_width=True, config=CONFIG)
        st.caption("Arriba a la derecha: mucho volumen y tasa alta (prioridad por impacto). Arriba a la izquierda: "
                   "tasa alta con poco volumen (prioridad por calidad).")
    with c1:
        st.markdown("##### Alertas priorizadas")
        al = kg.alertas(df, mes)
        if al.empty:
            st.success("🟢 Todas las provincias de la selección cumplen las metas.")
        for _, a in al.head(9).iterrows():
            conf = "✔ confirmada" if a["Confirmada"] else "a vigilar (1 mes)"
            lect = "" if a["Lectura"] == "Mes evaluado" else " · <i>trimestre</i>"
            st.markdown(f"<div class='alerta'><span style='color:{color_estado(a['estado'])}'>{a['Estado']}</span> · "
                        f"<b>{a['Provincia']}</b> — {a['KPI']} {kg.KPIS[a['kpi']]['corto']}: <b>{a['Valor']}</b>{lect} "
                        f"<span class='nota'>({conf})</span></div>", unsafe_allow_html=True)
        if len(al) > 9:
            st.caption(f"+ {len(al) - 9} alertas más en Análisis territorial.")
        st.caption("Confirmada: se repite el mes anterior o en la lectura trimestral.")

    st.divider()
    opciones = {"KPI 3 · Reclamos": "k3", "KPI 4 · Mediana de entrega": "k4", "KPI 5 · A tiempo": "k5",
                "Ventas por día": "ventas_dia"}
    preferida = next((n for n, v in opciones.items() if v in info["kpis"]), "KPI 3 · Reclamos")
    sel = st.segmented_control("Seguimiento semanal", list(opciones), default=preferida, key="tend")
    c3, c4 = st.columns([3, 2], gap="large")
    with c3:
        st.plotly_chart(kg.fig_tendencia_semanal(df, opciones[sel or preferida]), use_container_width=True,
                        config=CONFIG)
    with c4:
        st.plotly_chart(kg.fig_ventas_por_dia(df), use_container_width=True, config=CONFIG)
        st.caption("Por eso la meta del KPI 1 se prorratea por días: febrero tiene 28 días y marzo 31.")

# ---------------------------------------------------------------------------
# 2. Análisis territorial
# ---------------------------------------------------------------------------
with tab_terr:
    st.markdown("<div class='pregunta'>¿Qué provincias están fuera de meta y por qué? "
                "Haga clic en la barra de una provincia para ver su detalle.</div>", unsafe_allow_html=True)
    kpi = st.selectbox("Indicador", list(kg.KPIS), index=list(kg.KPIS).index(info["kpis"][0]),
                       format_func=lambda k: f"{kg.KPIS[k]['codigo']} – {kg.KPIS[k]['nombre']}", key="kpi_terr")
    evento = st.plotly_chart(kg.fig_kpi(df, kpi, mes), use_container_width=True, config=CONFIG,
                             on_select="rerun", selection_mode="points", key="barras_kpi")

    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        cruce = st.radio("Cruzar provincia con", ["canal_entrega", "tipo_cliente", "tramo_distancia"], horizontal=True,
                         format_func=lambda x: x.replace("_", " ").capitalize(), key="cruce")
        st.plotly_chart(kg.fig_heatmap(df, kpi, cruce), use_container_width=True, config=CONFIG)
        st.caption(f"Lectura del trimestre completo, más estable que la mensual. Celdas marcadas con \\* tienen "
                   f"menos de {kg.N_MINIMO} pedidos. El tramo de distancia ayuda a separar la geografía del desempeño.")
    with c2:
        provs = sorted(df["provincia"].unique())
        puntos = evento.selection.points if evento and evento.selection else []
        clic = next((p.get("x") for p in puntos if p.get("x") in provs), None)
        elegida = st.selectbox("Detalle de provincia", provs, index=provs.index(clic) if clic in provs else 0,
                               key="prov_detalle")
        sub = df[df["provincia"] == elegida]
        comp = kg.kpis_empresa(sub, mes)[["KPI", "Valor", "Estado"]].rename(
            columns={"Valor": elegida, "Estado": "Estado"})
        comp[kg.TOTAL] = kg.kpis_empresa(df, mes)["Valor"]
        comp["Trimestre"] = [kg.formatear(k, v) for k, v in kg.kpis_empresa(sub, mes)["trimestre"].items()]
        st.dataframe(comp, hide_index=True, use_container_width=True)
        st.caption(f"{len(sub[sub['mes_num'] == mes]):,} pedidos en {kg.MESES[mes].lower()} · "
                   f"motivo principal de reclamo: {kg.tabla_periodo(sub).iloc[0]['motivo_principal']}")
        st.plotly_chart(kg.fig_evolucion(df, kpi, elegida), use_container_width=True, config=CONFIG)

    with st.expander("Tabla mensual de KPIs por provincia (exportable)"):
        t = kg.tabla_mensual(df, "provincia")[["provincia", "mes", "pedidos", "ventas_usd", "ventas_dia", "k1",
                                               "ticket_usd", "k2", "k3", "k3_ic_inf", "k3_ic_sup", "k4",
                                               "ric_min", "k5", "fuera_plazo"]].round(2)
        st.dataframe(t, hide_index=True, use_container_width=True)
        st.download_button("Descargar CSV", t.to_csv(index=False).encode("utf-8-sig"), "kpis_provincia.csv", "text/csv")

# ---------------------------------------------------------------------------
# 3. Detalle operativo
# ---------------------------------------------------------------------------
with tab_op:
    st.markdown("<div class='pregunta'>¿Dónde y cuándo falla el plazo de entrega, y qué motivos generan "
                "los reclamos?</div>", unsafe_allow_html=True)
    st.plotly_chart(kg.fig_histograma_plazo(df_mes), use_container_width=True, config=CONFIG)

    canal = kg.tabla_periodo(df_mes, "canal_entrega")
    st.dataframe(canal[["pedidos", "pct_a_tiempo", "fuera_plazo", "mediana_min", "ric_min", "tasa_reclamos",
                        "ticket_usd"]].rename(columns={
        "pedidos": "Pedidos", "pct_a_tiempo": "KPI 5 · A tiempo %", "fuera_plazo": "Fuera de plazo",
        "mediana_min": "KPI 4 · Mediana (min)", "ric_min": "RIC (min)", "tasa_reclamos": "KPI 3 · Reclamos %",
        "ticket_usd": "Ticket USD"}).round(1), use_container_width=True)
    st.caption(f"{kg.MESES[mes]} · Programado incumple más el plazo único de {kg.SLA_MIN} min porque su ventana "
               "acordada es distinta (limitación documentada del KPI 5).")

    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        por_box = st.radio("Distribución de entrega por", ["provincia", "tipo_cliente"], horizontal=True,
                           format_func=lambda x: x.replace("_", " ").capitalize(), key="box")
        st.plotly_chart(kg.fig_boxplot_entrega(df_mes, por_box), use_container_width=True, config=CONFIG)
    with c2:
        st.plotly_chart(kg.fig_reclamos_segun_plazo(df), use_container_width=True, config=CONFIG)
        st.caption("Trimestre completo. Los pedidos fuera de plazo reclaman más del doble: el KPI 5 anticipa al KPI 3.")
        if df["con_reclamo"].any():
            st.plotly_chart(kg.fig_pareto(df), use_container_width=True, config=CONFIG)
    st.plotly_chart(kg.fig_demanda_hora_dia(df), use_container_width=True, config=CONFIG)

    st.divider()
    st.markdown(f"##### Pedidos para gestión · {kg.MESES[mes]}")
    f1, f2, f3 = st.columns([1, 1, 2])
    solo_rec = f1.toggle("Solo con reclamo", value=True, key="solo_rec")
    solo_tarde = f2.toggle(f"Solo fuera de plazo (> {kg.SLA_MIN} min)", value=False, key="solo_tarde")
    buscar = f3.text_input("Buscar pedido", placeholder="LA-000123", key="buscar")
    det = df_mes
    if solo_rec:
        det = det[det["con_reclamo"]]
    if solo_tarde:
        det = det[det["a_tiempo"] == 0]
    if buscar:
        det = det[det["pedido_id"].str.contains(buscar.strip(), case=False, regex=False)]
    cols = ["pedido_id", "fecha_pedido", "provincia", "canal_entrega", "tipo_cliente", "tiempo_individual_entrega_min",
            "a_tiempo", "distancia_km", "ventas_asociadas_usd", "motivo_reclamo"]
    st.dataframe(det[cols].sort_values("fecha_pedido", ascending=False), hide_index=True, use_container_width=True,
                 height=320, column_config={
                     "fecha_pedido": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
                     "tiempo_individual_entrega_min": st.column_config.NumberColumn("Entrega (min)", format="%.0f"),
                     "a_tiempo": st.column_config.CheckboxColumn("A tiempo"),
                     "ventas_asociadas_usd": st.column_config.NumberColumn("Ventas", format="$%.2f"),
                 })
    st.caption(f"{len(det):,} pedidos. Uso interno: datos seudonimizados por pedido_id; no compartir fuera del área.")
    st.download_button("Descargar lista (CSV)", det[cols].to_csv(index=False).encode("utf-8-sig"),
                       "pedidos_gestion.csv", "text/csv")

# ---------------------------------------------------------------------------
# 4. KPIs y gobernanza
# ---------------------------------------------------------------------------
with tab_gob:
    st.markdown("#### Ficha técnica de los KPIs")
    for k, d in kg.KPIS.items():
        with st.expander(f"{d['codigo']} – {d['nombre']}  ·  {d['umbral_txt']}"):
            st.markdown(f"**Objetivo:** {d['objetivo']}  \n**Fórmula:** {d['formula']}  \n"
                        f"**Fuente:** {kg.FUENTE} — columnas `{d['fuente']}`  \n**Frecuencia:** {d['frecuencia']}  \n"
                        f"**Meta:** {d['meta_txt']}  \n**Umbral:** {d['umbral_txt']}  \n"
                        f"**Interpretación:** {d['interpretacion']}  \n**Responsable:** {d['responsable']}")

    g1, g2 = st.columns(2, gap="large")
    with g1:
        st.markdown("#### Verificación contra el Notebook")
        if RUTA_REFERENCIA.exists():
            ref = json.loads(RUTA_REFERENCIA.read_text(encoding="utf-8"))
            actual = kg.tabla_mensual(df_total).set_index("mes")
            filas = []
            for k, por_mes in ref["kpis"].items():
                for m, v in por_mes.items():
                    if v is None:
                        continue
                    filas.append({"KPI": kg.KPIS[k]["codigo"], "Mes": m, "Notebook": v,
                                  "Dashboard": round(float(actual.loc[m, k]), 6)})
            ver = pd.DataFrame(filas)
            ver["Coincide"] = (ver["Notebook"] - ver["Dashboard"]).abs() < 1e-3
            st.dataframe(ver, hide_index=True, use_container_width=True, height=300)
            if ver["Coincide"].all() and ref.get("ajuste_calendario") == kg.AJUSTE_CALENDARIO:
                st.success(f"✔ Los {len(ver)} valores coinciden con el Notebook (generado {ref['generado']}, "
                           f"{ref['registros']:,} registros). Comparación sin filtros.")
            else:
                st.error("✖ Hay diferencias con el Notebook: vuelva a ejecutarlo.")
        else:
            st.warning("No se encontró outputs/kpis_referencia.json. Ejecute el Notebook para generarlo.")
    with g2:
        st.markdown("#### Calidad de datos")
        cal = kg.calidad_datos(df_total)
        cal["Cumple"] = cal["Cumple"].map({True: "✔", False: "✖"})
        st.dataframe(cal, hide_index=True, use_container_width=True)

    st.markdown("#### Uso responsable")
    st.markdown(f"""
- **Asociación no es causalidad:** las diferencias entre provincias señalan dónde investigar, no la causa.
- **Muestras pequeñas:** con menos de {kg.N_MINIMO} pedidos se muestra una advertencia y las celdas se marcan con \\*. Los KPI 3 y 5 incluyen un margen de error (IC 95 %).
- **Alertas confirmadas:** una señal se confirma si se repite el mes anterior o en el trimestre, para no reaccionar ante el azar.
- **Supuestos:** crecimiento de {kg.CRECIMIENTO_META:.0%}, plazo de {kg.SLA_MIN} min, metas y ajuste por calendario {'activo' if kg.AJUSTE_CALENDARIO else 'inactivo'}. Son propuestas académicas que debe aprobar cada responsable.
- **Privacidad (LOPDP):** la base no contiene datos personales directos. La lista de pedidos es de uso interno y, en producción, requiere control de acceso por rol.
- **Horizonte:** tres meses no permiten separar la tendencia de la estacionalidad.
""")
