"""
kpis_grupo5.py — Capa semántica de la solución BI de LogiAndes S.A. (Taller 2, Grupo 5).

Única fuente de verdad para:
  * carga y preparación de los datos,
  * la ficha técnica y el cálculo de los 5 KPIs definidos por el grupo,
  * las tablas por mes, provincia y periodo,
  * los gráficos Plotly del análisis y del dashboard de Streamlit.

El análisis y app.py importan estas mismas funciones: un KPI siempre se calcula
con el mismo código, se muestre donde se muestre.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# 1. Parámetros de negocio (documentados y fáciles de ajustar)
# ---------------------------------------------------------------------------
RUTA_DATOS = Path(__file__).parent / "data" / "logiandes.csv"
FUENTE = "Base de pedidos LogiAndes S.A. (logiandes.csv), enero–marzo 2026"

CRECIMIENTO_META = 0.05        # KPI 1: crecer 5 % sobre la línea base de enero
AJUSTE_CALENDARIO = True       # KPI 1: prorratear la meta por días del mes (febrero tiene 28 días)
SLA_MIN = 180                  # KPI 5: plazo máximo aceptable por pedido (minutos)
N_MINIMO = 30                  # bajo este número de pedidos una tasa se considera poco confiable

MESES = {1: "Enero", 2: "Febrero", 3: "Marzo"}
DIAS_MES = {1: 31, 2: 28, 3: 31}
DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
TRAMOS_KM = [0, 5, 10, 15, 20, 50]
TRAMOS_ETIQUETAS = ["0–5 km", "5–10 km", "10–15 km", "15–20 km", "> 20 km"]
TOTAL = "Total empresa"
T = "tiempo_individual_entrega_min"

# ---------------------------------------------------------------------------
# 2. Colores (los del Taller del grupo) y estilo común
# ---------------------------------------------------------------------------
ESTADOS = {
    "verde":    {"emoji": "🟢", "etiqueta": "Cumple", "color": "#2e8b57"},
    "amarillo": {"emoji": "🟡", "etiqueta": "Atención", "color": "#e0a100"},
    "rojo":     {"emoji": "🔴", "etiqueta": "Crítico", "color": "#c0392b"},
    "base":     {"emoji": "⚪", "etiqueta": "Línea base", "color": "#9aa5b1"},
    "sd":       {"emoji": "⚪", "etiqueta": "Sin dato", "color": "#9aa5b1"},
}
AZUL_CLARO, AZUL_OSCURO, GRIS = "#9dbbe0", "#1f4e79", "#c9ced6"
COLOR_CANAL = {"Estándar urbano": "#2a78d6", "Express": "#eb6834", "Programado": "#1baf7a"}
SECUENCIAL = ["#deebf7", "#b7d3f6", "#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"]
TEXTO, TEXTO_2, REJILLA = "#0b0b0b", "#52514e", "#eeeeee"


def estilo(fig: go.Figure, alto: int = 420, leyenda_abajo: bool = True) -> go.Figure:
    fig.update_layout(
        template="plotly_white", height=alto, plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", size=13, color=TEXTO),
        title=dict(x=0.01, xanchor="left", font=dict(size=15)),
        margin=dict(l=60, r=20, t=80, b=60), hoverlabel=dict(bgcolor="white", font_size=12),
    )
    if leyenda_abajo:
        fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="left", x=0,
                                      font=dict(size=11), title_text=""))
    fig.update_xaxes(gridcolor=REJILLA, zeroline=False)
    fig.update_yaxes(gridcolor=REJILLA, zeroline=False)
    return fig


# ---------------------------------------------------------------------------
# 3. Carga y preparación
# ---------------------------------------------------------------------------
def cargar_datos(ruta: str | Path = RUTA_DATOS) -> pd.DataFrame:
    """Lee el CSV y agrega variables derivadas, sin modificar los valores originales."""
    df = pd.read_csv(ruta, encoding="utf-8-sig", parse_dates=["fecha_pedido"])
    df["fecha"] = df["fecha_pedido"].dt.normalize()
    df["mes_num"] = df["fecha_pedido"].dt.month
    df["mes"] = df["mes_num"].map(MESES)
    df["semana"] = df["fecha"] - pd.to_timedelta(df["fecha"].dt.dayofweek, unit="D")
    df["hora"] = df["fecha_pedido"].dt.hour
    df["dia_semana"] = pd.Categorical(df["fecha_pedido"].dt.dayofweek.map(dict(enumerate(DIAS_SEMANA))),
                                      categories=DIAS_SEMANA, ordered=True)
    df["a_tiempo"] = (df[T] <= SLA_MIN).astype(int)
    df["con_reclamo"] = df["reclamos_registrados"] > 0
    df["tramo_distancia"] = pd.cut(df["distancia_km"], bins=TRAMOS_KM, labels=TRAMOS_ETIQUETAS)
    df["motivo_reclamo"] = df["motivo_reclamo"].fillna("Sin reclamo")
    return df


def calidad_datos(df: pd.DataFrame) -> pd.DataFrame:
    """Controles de calidad que respaldan la confianza en los KPIs."""
    rec = df["con_reclamo"]
    controles = [
        ("Identificador de pedido único", df["pedido_id"].is_unique, f"{df['pedido_id'].nunique():,} ids únicos"),
        ("Sin pedidos duplicados", not df.duplicated(subset=["pedido_id", "fecha_pedido"]).any(), "0 duplicados"),
        ("Fechas dentro de enero–marzo 2026", df["fecha_pedido"].between("2026-01-01", "2026-03-31 23:59:59").all(),
         f"{df['fecha_pedido'].min():%d-%m-%Y} a {df['fecha_pedido'].max():%d-%m-%Y}"),
        ("Todos los días del trimestre tienen pedidos", df["fecha"].nunique() == 90, f"{df['fecha'].nunique()} de 90 días"),
        ("Tiempos, distancias y ventas positivos",
         (df[["tiempo_atencion_min", T, "distancia_km", "ventas_asociadas_usd"]] > 0).all().all(), "mín > 0"),
        ("Reclamos binarios (0/1)", df["reclamos_registrados"].isin([0, 1]).all(), "valores {0, 1}"),
        ("Todo reclamo tiene motivo y viceversa",
         (df.loc[rec, "motivo_reclamo"] != "Sin reclamo").all() and (df.loc[~rec, "motivo_reclamo"] == "Sin reclamo").all(),
         f"{int(rec.sum())} reclamos con motivo"),
        ("Región coherente con provincia", (df.groupby("provincia")["region"].nunique() == 1).all(), "1 región por provincia"),
    ]
    return pd.DataFrame(controles, columns=["Control", "Cumple", "Detalle"])


# ---------------------------------------------------------------------------
# 4. Ficha técnica de los KPIs (definidos por el Grupo 5)
# ---------------------------------------------------------------------------
# sentido "mayor": verde si valor ≥ verde; amarillo si ≥ amarillo; rojo en otro caso.
# sentido "menor": verde si valor ≤ verde; amarillo si ≤ amarillo; rojo en otro caso.
KPIS: dict[str, dict] = {
    "k1": dict(
        codigo="KPI 1", nombre="Cumplimiento de meta de ventas mensuales", corto="Meta de ventas",
        unidad="%", sentido="mayor", verde=95, amarillo=80, base_enero=True, ic=False,
        fmt="{:.1f} %", fmt_barra="{:.0f}%", eje="Cumplimiento de la meta (%)",
        objetivo="Evaluar si las ventas de cada mes alcanzan la meta de crecimiento definida, a nivel empresa y por provincia.",
        formula="Ventas del mes (Σ ventas_asociadas_usd) ÷ Meta del mes × 100. "
                "Meta del mes = venta diaria de enero × 1,05 × días del mes (enero = línea base).",
        fuente="ventas_asociadas_usd, fecha_pedido, provincia",
        frecuencia="Mensual.",
        meta_txt="100 %: crecer 5 % sobre la venta diaria de enero (meta propuesta con fines académicos, a validar con gerencia).",
        umbral_txt="🟢 ≥ 95 %  |  🟡 80 % – 94,9 %  |  🔴 < 80 %",
        interpretacion="Mayor es mejor. Bajo 95 % indica rezago frente a la meta. Enero no se evalúa (línea base). "
                       "La meta se prorratea por días porque febrero tiene 28 días y marzo 31. "
                       "Mide volumen de ingreso, no rentabilidad (la base no incluye costos).",
        responsable="Gerencia comercial", audiencias=["Gerencia general", "Área comercial", "Finanzas"],
    ),
    "k2": dict(
        codigo="KPI 2", nombre="Ticket promedio por pedido", corto="Ticket promedio",
        unidad="%", sentido="mayor", verde=100, amarillo=95, base_enero=True, ic=False,
        fmt="{:.1f} %", fmt_barra="${:.2f}", eje="Ticket promedio por pedido (USD)",
        objetivo="Detectar si el ingreso crece por más pedidos o por pedidos de mayor valor, a nivel empresa y por provincia.",
        formula="Ticket = Σ ventas_asociadas_usd ÷ N.º de pedidos del mes. Índice = Ticket del mes ÷ Ticket de enero × 100.",
        fuente="ventas_asociadas_usd, pedido_id, fecha_pedido, provincia",
        frecuencia="Mensual.",
        meta_txt="Mantener o superar el ticket de enero (índice ≥ 100 %). Cada provincia se compara con su propio enero.",
        umbral_txt="🟢 ≥ 100 %  |  🟡 95 % – 99,9 %  |  🔴 < 95 %",
        interpretacion="Mayor es mejor. Bajo 100 % el valor por pedido cae frente a la línea base. Se complementa con la "
                       "mediana porque el promedio es sensible a pedidos de alto valor. No mide rentabilidad.",
        responsable="Área comercial y finanzas", audiencias=["Área comercial", "Finanzas"],
    ),
    "k3": dict(
        codigo="KPI 3", nombre="Tasa de reclamos", corto="Tasa de reclamos",
        unidad="%", sentido="menor", verde=3.0, amarillo=5.0, base_enero=False, ic=True,
        fmt="{:.2f} %", fmt_barra="{:.1f}%", eje="Reclamos por cada 100 pedidos (%)",
        objetivo="Monitorear la calidad del servicio desde la experiencia del cliente, sin el efecto del volumen de pedidos.",
        formula="Σ reclamos_registrados ÷ N.º de pedidos × 100, con intervalo de confianza de Wilson al 95 %.",
        fuente="reclamos_registrados, motivo_reclamo, pedido_id, fecha_pedido, provincia",
        frecuencia="Mensual, con lectura acumulada trimestral para confirmar tendencias.",
        meta_txt="≤ 3 reclamos por cada 100 pedidos, igual para todas las provincias (estándar de servicio).",
        umbral_txt="🟢 ≤ 3 %  |  🟡 3 % – 5 %  |  🔴 > 5 %",
        interpretacion="Menor es mejor. Sobre 5 % indica un problema de servicio. Con pocos reclamos por mes la tasa varía "
                       "por azar: confirmar con el intervalo de confianza y con la tasa trimestral antes de actuar.",
        responsable="Atención al cliente, con operaciones", audiencias=["Gerencia general", "Atención al cliente", "Operaciones"],
    ),
    "k4": dict(
        codigo="KPI 4", nombre="Mediana del tiempo de entrega", corto="Mediana de entrega",
        unidad="min", sentido="menor", verde=120, amarillo=150, base_enero=False, ic=False,
        fmt="{:.0f} min", fmt_barra="{:.0f}", eje="Mediana del tiempo de entrega (min)",
        objetivo="Monitorear la rapidez de la entrega por provincia y mes frente al estándar operativo.",
        formula="Mediana de tiempo_individual_entrega_min del mes. Complemento: RIC = Q3 − Q1 (variabilidad).",
        fuente="tiempo_individual_entrega_min, canal_entrega, fecha_pedido, provincia",
        frecuencia="Mensual (seguimiento semanal en operaciones).",
        meta_txt="Mediana ≤ 120 minutos, nivel que ya alcanzan Azuay y Tungurahua (exigente pero alcanzable).",
        umbral_txt="🟢 ≤ 120 min  |  🟡 120 – 150 min  |  🔴 > 150 min",
        interpretacion="Menor es mejor. Se usa la mediana porque los tiempos tienen casos extremos. Sobre 150 min indica un "
                       "problema operativo. El RIC muestra si las entregas son regulares o impredecibles.",
        responsable="Operaciones y logística", audiencias=["Gerencia general", "Operaciones"],
    ),
    "k5": dict(
        codigo="KPI 5", nombre="Porcentaje de entregas a tiempo", corto="Entregas a tiempo",
        unidad="%", sentido="mayor", verde=90, amarillo=80, base_enero=False, ic=True,
        fmt="{:.1f} %", fmt_barra="{:.0f}%", eje=f"Pedidos entregados en ≤ {SLA_MIN} min (%)",
        objetivo="Medir qué proporción de pedidos llega dentro del plazo máximo aceptable: lo que percibe cada cliente.",
        formula=f"Pedidos con tiempo_individual_entrega_min ≤ {SLA_MIN} ÷ Total de pedidos del mes × 100 (IC de Wilson 95 %).",
        fuente="tiempo_individual_entrega_min, pedido_id, fecha_pedido, provincia",
        frecuencia="Mensual (seguimiento semanal en operaciones).",
        meta_txt=f"≥ 90 % de pedidos en {SLA_MIN} min o menos (2 h = tiempo ideal del KPI 4; 3 h = máximo aceptable).",
        umbral_txt="🟢 ≥ 90 %  |  🟡 80 % – 89,9 %  |  🔴 < 80 %",
        interpretacion="Mayor es mejor. Complementa al KPI 4: la mediana muestra el tiempo típico y este KPI cuántos pedidos "
                       "se salen del plazo. El plazo es único para todos los canales; Programado podría requerir otra ventana.",
        responsable="Operaciones, con seguimiento de atención al cliente",
        audiencias=["Gerencia general", "Operaciones", "Atención al cliente"],
    ),
}

AUDIENCIAS = {
    "Gerencia general": dict(
        pregunta="¿Crecemos sin deteriorar el servicio? ¿Qué provincias requieren intervención primero?",
        kpis=["k1", "k3", "k5", "k4", "k2"], seccion="Vista ejecutiva"),
    "Área comercial": dict(
        pregunta="¿Qué provincias cumplen la meta de ventas y crecen en valor por pedido, no solo en volumen?",
        kpis=["k1", "k2"], seccion="Vista ejecutiva y Análisis territorial"),
    "Operaciones": dict(
        pregunta="¿Dónde se incumple el plazo de entrega y dónde las entregas son lentas o irregulares?",
        kpis=["k4", "k5"], seccion="Detalle operativo"),
    "Finanzas": dict(
        pregunta="¿El ingreso crece de forma sostenida y por qué vía: más pedidos o pedidos de mayor valor?",
        kpis=["k1", "k2"], seccion="Vista ejecutiva"),
    "Atención al cliente": dict(
        pregunta="¿Qué provincias y motivos concentran los reclamos, y cuánto se relacionan con entregas tardías?",
        kpis=["k3", "k5"], seccion="Detalle operativo"),
}


def ficha_tecnica() -> pd.DataFrame:
    """Ficha técnica completa en formato tabla (una fila por KPI)."""
    return pd.DataFrame([{
        "KPI": d["codigo"], "Nombre": d["nombre"], "Objetivo": d["objetivo"], "Fórmula": d["formula"],
        "Fuente (columnas)": d["fuente"], "Frecuencia": d["frecuencia"], "Meta": d["meta_txt"],
        "Umbral": d["umbral_txt"], "Interpretación": d["interpretacion"], "Responsable": d["responsable"],
    } for d in KPIS.values()]).set_index("KPI")


def mostrar_ficha(kpi: str):
    """Ficha de un KPI como tabla de dos columnas (formato del Taller del grupo)."""
    d = KPIS[kpi]
    campos = {"Nombre": f"{d['codigo']} – {d['nombre']}", "Objetivo": d["objetivo"], "Fórmula": d["formula"],
              "Fuente": f"{FUENTE}: columnas {d['fuente']}.", "Frecuencia": d["frecuencia"], "Meta": d["meta_txt"],
              "Umbral": d["umbral_txt"], "Interpretación": d["interpretacion"], "Responsable": d["responsable"]}
    return (pd.DataFrame(campos.items(), columns=["Campo", "Descripción"]).style.hide(axis="index")
            .set_properties(**{"text-align": "left", "white-space": "normal"})
            .set_table_styles([{"selector": "th", "props": [("text-align", "left")]}]))


def estado(kpi: str, valor: float, es_base: bool = False) -> str:
    """Semáforo del KPI: 'verde', 'amarillo', 'rojo', 'base' (enero en KPI 1 y 2) o 'sd'."""
    if es_base:
        return "base"
    if valor is None or pd.isna(valor):
        return "sd"
    d = KPIS[kpi]
    if d["sentido"] == "mayor":
        return "verde" if valor >= d["verde"] else ("amarillo" if valor >= d["amarillo"] else "rojo")
    return "verde" if valor <= d["verde"] else ("amarillo" if valor <= d["amarillo"] else "rojo")


def etiqueta_estado(e: str) -> str:
    return f"{ESTADOS[e]['emoji']} {ESTADOS[e]['etiqueta']}"


def formatear(kpi: str, valor: float) -> str:
    return "—" if valor is None or pd.isna(valor) else KPIS[kpi]["fmt"].format(valor)


def rango_estados(kpi: str) -> dict[str, str]:
    """Texto de cada zona del semáforo para leyendas: {'verde': '≥ 95%', ...}."""
    d = KPIS[kpi]
    u = " min" if d["unidad"] == "min" else "%"
    if d["sentido"] == "mayor":
        return {"verde": f"≥ {d['verde']:g}{u}", "amarillo": f"{d['amarillo']:g}–{d['verde']:g}{u}",
                "rojo": f"< {d['amarillo']:g}{u}"}
    return {"verde": f"≤ {d['verde']:g}{u}", "amarillo": f"{d['verde']:g}–{d['amarillo']:g}{u}",
            "rojo": f"> {d['amarillo']:g}{u}"}


# ---------------------------------------------------------------------------
# 5. Cálculo de los KPIs
# ---------------------------------------------------------------------------
def ic_wilson(exitos, n, z: float = 1.96):
    """Intervalo de confianza de Wilson (95 %) para una proporción, en %."""
    n = np.asarray(n, dtype=float)
    p = np.asarray(exitos, dtype=float) / n
    centro = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    margen = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return (centro - margen) * 100, (centro + margen) * 100


def _claves(por) -> list[str]:
    if por is None:
        return []
    return [por] if isinstance(por, str) else list(por)


def tabla_mensual(df: pd.DataFrame, por=None) -> pd.DataFrame:
    """Los 5 KPIs por mes (y opcionalmente por provincia, canal...). Cada grupo usa su propio enero como base."""
    claves = _claves(por) or ["grupo"]
    d = df.assign(grupo=TOTAL) if not _claves(por) else df
    t = (d.groupby(claves + ["mes_num"], observed=True)
          .agg(pedidos=("pedido_id", "count"), ventas_usd=("ventas_asociadas_usd", "sum"),
               mediana_usd=("ventas_asociadas_usd", "median"), reclamos=("reclamos_registrados", "sum"),
               a_tiempo=("a_tiempo", "sum"), mediana_min=(T, "median"),
               q1=(T, lambda s: s.quantile(0.25)), q3=(T, lambda s: s.quantile(0.75)),
               pct_express=("canal_entrega", lambda s: (s == "Express").mean() * 100))
          .reset_index())
    t["mes"] = t["mes_num"].map(MESES)
    t["dias"] = t["mes_num"].map(DIAS_MES)
    t["ventas_dia"] = t["ventas_usd"] / t["dias"]
    t["ticket_usd"] = t["ventas_usd"] / t["pedidos"]
    t["ric_min"] = t["q3"] - t["q1"]
    base = (t[t["mes_num"] == 1].set_index(claves)[["ventas_usd", "ventas_dia", "ticket_usd"]]
            .rename(columns=lambda c: f"base_{c}"))
    t = t.merge(base, left_on=claves, right_index=True, how="left")
    es_base = t["mes_num"] == 1
    # KPI 1 — meta prorrateada por días (o fija, si AJUSTE_CALENDARIO = False)
    if AJUSTE_CALENDARIO:
        t["meta_usd"] = t["base_ventas_dia"] * (1 + CRECIMIENTO_META) * t["dias"]
    else:
        t["meta_usd"] = t["base_ventas_usd"] * (1 + CRECIMIENTO_META)
    t["k1"] = np.where(es_base, np.nan, t["ventas_usd"] / t["meta_usd"] * 100)
    # KPI 2 — índice del ticket frente a enero
    t["meta_ticket"] = t["base_ticket_usd"]
    t["k2"] = np.where(es_base, np.nan, t["ticket_usd"] / t["base_ticket_usd"] * 100)
    # KPI 3 — tasa de reclamos con IC
    t["k3"] = t["reclamos"] / t["pedidos"] * 100
    t["k3_ic_inf"], t["k3_ic_sup"] = ic_wilson(t["reclamos"], t["pedidos"])
    # KPI 4 — mediana del tiempo de entrega
    t["k4"] = t["mediana_min"]
    # KPI 5 — % a tiempo con IC
    t["k5"] = t["a_tiempo"] / t["pedidos"] * 100
    t["k5_ic_inf"], t["k5_ic_sup"] = ic_wilson(t["a_tiempo"], t["pedidos"])
    t["fuera_plazo"] = t["pedidos"] - t["a_tiempo"]
    for k in KPIS:
        t[f"estado_{k}"] = [estado(k, v, b and KPIS[k]["base_enero"]) for v, b in zip(t[k], es_base)]
    t["variacion_ventas_pct"] = t.groupby(claves)["ventas_usd"].pct_change() * 100
    t["variacion_ventas_dia_pct"] = t.groupby(claves)["ventas_dia"].pct_change() * 100
    t["muestra_pequena"] = t["pedidos"] < N_MINIMO
    if not _claves(por):
        t = t.drop(columns="grupo")
    return t


def tabla_periodo(df: pd.DataFrame, por=None) -> pd.DataFrame:
    """Lectura acumulada del periodo (trimestre) por grupo: más estable que la mensual."""
    claves = _claves(por) or ["grupo"]
    d = df.assign(grupo=TOTAL) if not _claves(por) else df
    g = d.groupby(claves, observed=True)
    t = g.agg(pedidos=("pedido_id", "count"), ventas_usd=("ventas_asociadas_usd", "sum"),
              mediana_usd=("ventas_asociadas_usd", "median"), reclamos=("reclamos_registrados", "sum"),
              a_tiempo=("a_tiempo", "sum"), mediana_min=(T, "median"),
              ric_min=(T, lambda s: s.quantile(0.75) - s.quantile(0.25)),
              distancia_mediana=("distancia_km", "median"),
              pct_express=("canal_entrega", lambda s: (s == "Express").mean() * 100))
    t["ticket_usd"] = t["ventas_usd"] / t["pedidos"]
    t["participacion_ventas"] = t["ventas_usd"] / t["ventas_usd"].sum() * 100
    t["tasa_reclamos"] = t["reclamos"] / t["pedidos"] * 100
    t["k3_ic_inf"], t["k3_ic_sup"] = ic_wilson(t["reclamos"], t["pedidos"])
    t["pct_a_tiempo"] = t["a_tiempo"] / t["pedidos"] * 100
    t["k5_ic_inf"], t["k5_ic_sup"] = ic_wilson(t["a_tiempo"], t["pedidos"])
    t["fuera_plazo"] = t["pedidos"] - t["a_tiempo"]
    t["estado_k3"] = [estado("k3", v) for v in t["tasa_reclamos"]]
    t["estado_k4"] = [estado("k4", v) for v in t["mediana_min"]]
    t["estado_k5"] = [estado("k5", v) for v in t["pct_a_tiempo"]]
    motivos = (d[d["con_reclamo"]].groupby(claves, observed=True)["motivo_reclamo"]
               .agg(lambda s: f"{s.value_counts().index[0]} ({s.value_counts().iloc[0]})"))
    t["motivo_principal"] = motivos.reindex(t.index).fillna("—")
    t["muestra_pequena"] = t["pedidos"] < N_MINIMO
    if not _claves(por):
        t = t.reset_index(drop=True)
    return t


def kpis_empresa(df: pd.DataFrame, mes: int) -> pd.DataFrame:
    """Los 5 KPIs de la selección para el mes evaluado, con mes anterior, variación y lectura trimestral."""
    m = tabla_mensual(df).set_index("mes_num")
    p = tabla_periodo(df).iloc[0] if len(df) else None
    filas = []
    for k, d in KPIS.items():
        actual = m.loc[mes, k] if mes in m.index else np.nan
        previo = m.loc[mes - 1, k] if (mes - 1) in m.index else np.nan
        if k == "k1" and mes - 1 == 1:
            previo = np.nan  # enero es línea base
        trimestral = {"k1": np.nan, "k2": np.nan,
                      "k3": p["tasa_reclamos"] if p is not None else np.nan,
                      "k4": p["mediana_min"] if p is not None else np.nan,
                      "k5": p["pct_a_tiempo"] if p is not None else np.nan}[k]
        filas.append({"kpi": k, "KPI": d["codigo"], "Indicador": d["nombre"], "valor": actual,
                      "Valor": formatear(k, actual), "previo": previo,
                      "variacion": actual - previo if pd.notna(previo) else np.nan,
                      "trimestre": trimestral, "estado": estado(k, actual),
                      "Estado": etiqueta_estado(estado(k, actual)), "Meta": d["umbral_txt"].split("|")[0].strip()})
    return pd.DataFrame(filas).set_index("kpi")


def matriz_semaforo(df: pd.DataFrame, mes: int) -> pd.DataFrame:
    """Tablero: provincias (filas) × KPI (columnas) en el mes evaluado, con emoji de estado y valor."""
    prov = tabla_mensual(df, "provincia")
    prov = prov[prov["mes_num"] == mes].set_index("provincia")
    emp = tabla_mensual(df)
    emp = emp[emp["mes_num"] == mes]
    emp.index = [TOTAL]
    t = pd.concat([emp, prov])
    out = pd.DataFrame(index=t.index)
    for k, d in KPIS.items():
        col = "ticket_usd" if k == "k2" else k
        valor = t[col].map(lambda v: f"${v:.2f}") if k == "k2" else t[k].map(lambda v: formatear(k, v))
        out[f"{d['codigo']} · {d['corto']}"] = [f"{ESTADOS[e]['emoji']} {v}" for e, v in zip(t[f"estado_{k}"], valor)]
    out["Pedidos"] = t["pedidos"].astype(int)
    out["_rojos"] = sum((t[f"estado_{k}"] == "rojo").astype(int) for k in KPIS)
    out["_amarillos"] = sum((t[f"estado_{k}"] == "amarillo").astype(int) for k in KPIS)
    total = out.loc[[TOTAL]]
    resto = out.drop(index=TOTAL).sort_values(["_rojos", "_amarillos"], ascending=False)
    return pd.concat([total, resto]).drop(columns=["_rojos", "_amarillos"])


def alertas(df: pd.DataFrame, mes: int) -> pd.DataFrame:
    """Provincias fuera de meta en el mes evaluado. 'Confirmada' si el mes anterior o el trimestre también
    están fuera de meta (recomendación del Taller: no reaccionar ante variaciones aleatorias)."""
    prov = tabla_mensual(df, "provincia").set_index(["provincia", "mes_num"])
    trim = tabla_periodo(df, "provincia")
    filas = []
    for (provincia, m), r in prov.iterrows():
        if m != mes:
            continue
        for k, d in KPIS.items():
            e = r[f"estado_{k}"]
            prev = prov[f"estado_{k}"].get((provincia, mes - 1), "sd")
            trim_e = trim.loc[provincia, f"estado_{k}"] if f"estado_{k}" in trim.columns else "sd"
            if e in ("rojo", "amarillo"):
                lectura = "Mes evaluado"
                confirmada = prev in ("rojo", "amarillo") or trim_e in ("rojo", "amarillo")
            elif e == "verde" and trim_e in ("rojo", "amarillo"):
                # Señal oculta: el mes luce bien, pero el trimestre sigue fuera de meta (caso Loja en el KPI 3)
                e, lectura, confirmada = trim_e, "Trimestre (el mes está en meta)", True
            else:
                continue
            valor_txt = formatear(k, r[k]) if lectura == "Mes evaluado" else formatear(
                k, trim.loc[provincia, {"k3": "tasa_reclamos", "k4": "mediana_min", "k5": "pct_a_tiempo"}[k]])
            filas.append({"Provincia": provincia, "KPI": d["codigo"], "Indicador": d["nombre"], "kpi": k,
                          "Valor": valor_txt, "estado": e, "Estado": etiqueta_estado(e), "Lectura": lectura,
                          "Confirmada": confirmada, "Pedidos": int(r["pedidos"])})
    out = pd.DataFrame(filas, columns=["Provincia", "KPI", "Indicador", "kpi", "Valor", "estado", "Estado",
                                       "Lectura", "Confirmada", "Pedidos"])
    out["_o"] = out["estado"].map({"rojo": 0, "amarillo": 1})
    return (out.sort_values(["_o", "Confirmada", "Pedidos"], ascending=[True, False, False])
               .drop(columns="_o").reset_index(drop=True))


def pareto_motivos(df: pd.DataFrame) -> pd.DataFrame:
    m = df.loc[df["con_reclamo"], "motivo_reclamo"].value_counts().rename("reclamos").to_frame()
    m["pct"] = m["reclamos"] / m["reclamos"].sum() * 100
    m["pct_acum"] = m["pct"].cumsum()
    return m


def reclamos_segun_plazo(df: pd.DataFrame) -> pd.DataFrame:
    r = (df.groupby("a_tiempo").agg(pedidos=("pedido_id", "count"), reclamos=("reclamos_registrados", "sum"))
           .rename(index={1: f"A tiempo (≤ {SLA_MIN} min)", 0: f"Fuera de plazo (> {SLA_MIN} min)"}))
    r["tasa_reclamos"] = r["reclamos"] / r["pedidos"] * 100
    r["ic_inf"], r["ic_sup"] = ic_wilson(r["reclamos"], r["pedidos"])
    return r.sort_values("tasa_reclamos")


# ---------------------------------------------------------------------------
# 6. Gráficos
# ---------------------------------------------------------------------------
def titulo_automatico(df: pd.DataFrame, kpi: str, mes: int) -> str:
    """Título interpretativo generado a partir de los datos (se actualiza con los filtros)."""
    t = tabla_mensual(df, "provincia")
    t = t[t["mes_num"] == mes]
    rojos = t.loc[t[f"estado_{kpi}"] == "rojo", "provincia"].tolist()
    amar = t.loc[t[f"estado_{kpi}"] == "amarillo", "provincia"].tolist()
    if rojos:
        txt = f"En rojo: {', '.join(rojos)}"
    elif amar:
        txt = f"Sin provincias en rojo; en atención: {', '.join(amar)}"
    else:
        txt = "Todas las provincias cumplen la meta"
    return f"<b>{txt}</b>"


def fig_kpi(df: pd.DataFrame, kpi: str, mes: int = 3, titulo: str | None = None,
            leyenda_abajo: bool = True) -> go.Figure:
    """Gráfico del Taller generalizado a los 5 KPIs: Total empresa (azul) y provincias;
    mes anterior en gris y mes evaluado con el color del semáforo; meta y umbral como líneas."""
    d = KPIS[kpi]
    ant = mes - 1
    col_y = "ticket_usd" if kpi == "k2" else kpi
    prov = tabla_mensual(df, "provincia")
    emp = tabla_mensual(df).set_index("mes_num")
    cur = prov[prov["mes_num"] == mes].set_index("provincia")
    prv = prov[prov["mes_num"] == ant].set_index("provincia")
    # De mejor a peor desempeño (como en el Taller)
    orden = cur.sort_values(col_y, ascending=d["sentido"] == "menor").index.tolist()
    fmt = d["fmt_barra"]
    hover_extra = {
        "k1": "Ventas: $%{customdata[0]:,.0f}<br>Meta: $%{customdata[1]:,.0f}<br>Ventas por día: $%{customdata[2]:,.0f}",
        "k2": "Índice vs. enero: %{customdata[0]:.1f}%<br>Meta (ticket enero): $%{customdata[1]:.2f}<br>Mediana: $%{customdata[2]:.2f}",
        "k3": "Reclamos / pedidos: %{customdata[0]:.0f} / %{customdata[1]:,.0f}<br>IC 95%: %{customdata[2]:.1f}% – %{customdata[3]:.1f}%",
        "k4": "Variabilidad (RIC): %{customdata[0]:.0f} min<br>Pedidos: %{customdata[1]:,.0f}<br>Pedidos Express: %{customdata[2]:.0f}%",
        "k5": "Fuera de plazo: %{customdata[0]:,.0f} de %{customdata[1]:,.0f}<br>IC 95%: %{customdata[2]:.1f}% – %{customdata[3]:.1f}%",
    }[kpi]
    cols_cd = {"k1": ["ventas_usd", "meta_usd", "ventas_dia"], "k2": ["k2", "meta_ticket", "mediana_usd"],
               "k3": ["reclamos", "pedidos", "k3_ic_inf", "k3_ic_sup"], "k4": ["ric_min", "pedidos", "pct_express"],
               "k5": ["fuera_plazo", "pedidos", "k5_ic_inf", "k5_ic_sup"]}[kpi]
    y_txt = "$%{y:.2f}" if kpi == "k2" else ("%{y:.0f} min" if kpi == "k4" else "%{y:.1f}%")

    def barra_error(sub):
        if not d["ic"]:
            return None
        return dict(type="data", symmetric=False, array=sub[f"{kpi}_ic_sup"] - sub[kpi],
                    arrayminus=sub[kpi] - sub[f"{kpi}_ic_inf"], color="#444", thickness=1.2, width=4)

    # Con margen de error, la etiqueta del mes evaluado va dentro de la barra para no chocar con el bigote
    etiqueta_cur = (dict(textposition="inside", insidetextanchor="end", textfont=dict(size=10, color="white"))
                    if d["ic"] else dict(textposition="outside", textfont=dict(size=10)))

    fig = go.Figure()
    # Total empresa (gerencia general)
    for m, color, grupo in [(ant, AZUL_CLARO, "ant"), (mes, AZUL_OSCURO, "cur")]:
        if m not in emp.index or pd.isna(emp.loc[m, col_y]):
            continue
        r = emp.loc[[m]]
        pos = etiqueta_cur if m == mes else dict(textposition="outside", textfont=dict(size=10))
        fig.add_bar(x=[TOTAL], y=r[col_y], name=f"Total empresa – {MESES[m]}", offsetgroup=grupo,
                    marker_color=color, text=[fmt.format(r[col_y].iloc[0])], **pos,
                    error_y=barra_error(r) if m == mes else None,
                    customdata=r[cols_cd].values,
                    hovertemplate=f"<b>Total empresa</b> – {MESES[m]}<br>{d['nombre']}: {y_txt}<br>{hover_extra}<extra></extra>")
    fig.add_vline(x=0.5, line_color="#999", line_width=1)
    # Provincias — mes anterior (gris)
    if ant in prov["mes_num"].values and prv[col_y].notna().any():
        p = prv.reindex(orden)
        fig.add_bar(x=orden, y=p[col_y], name=f"Provincias – {MESES[ant]}", offsetgroup="ant", marker_color=GRIS,
                    text=p[col_y].map(lambda v: "" if pd.isna(v) else fmt.format(v)), textposition="outside",
                    textfont=dict(size=9, color="#666"), customdata=p[cols_cd].values,
                    hovertemplate=f"<b>%{{x}}</b> – {MESES[ant]}<br>{d['nombre']}: {y_txt}<br>{hover_extra}<extra></extra>")
    # Provincias — mes evaluado, una serie por estado (leyenda con texto, no solo color)
    zonas = rango_estados(kpi)
    for e in ["verde", "amarillo", "rojo"]:
        sub = cur[cur[f"estado_{kpi}"] == e].reindex([o for o in orden if o in cur.index and cur.loc[o, f"estado_{kpi}"] == e])
        if sub.empty:
            continue
        fig.add_bar(x=sub.index, y=sub[col_y], name=f"Provincias – {MESES[mes]}: {ESTADOS[e]['etiqueta'].lower()} ({zonas[e]})",
                    offsetgroup="cur", marker_color=ESTADOS[e]["color"], error_y=barra_error(sub),
                    text=sub[col_y].map(fmt.format), **etiqueta_cur,
                    customdata=sub[cols_cd].values,
                    hovertemplate=f"<b>%{{x}}</b> – {MESES[mes]}<br>{d['nombre']}: {y_txt}<br>{hover_extra}<extra></extra>")
    # Líneas de referencia
    if kpi == "k2":
        metas = pd.concat([pd.Series({TOTAL: emp.loc[1, "ticket_usd"]}) if 1 in emp.index else pd.Series(dtype=float),
                           cur.reindex(orden)["meta_ticket"]])
        fig.add_scatter(x=metas.index, y=metas.values, mode="markers", name="Meta (ticket de enero)",
                        marker=dict(symbol="line-ew", size=34, line=dict(width=3, color="black")),
                        hovertemplate="<b>%{x}</b><br>Meta (ticket de enero): $%{y:.2f}<extra></extra>")
        y_max = float(np.nanmax([cur["ticket_usd"].max(), emp["ticket_usd"].max(), metas.max()])) * 1.2
    else:
        lineas = [(100, "Meta (100%)", "dash", "black")] if kpi == "k1" else []
        lineas += [(d["verde"], f"{'Umbral verde' if kpi == 'k1' else 'Meta'} ({rango_estados(kpi)['verde']})",
                    "dot" if kpi == "k1" else "dash", "#2e8b57" if kpi == "k1" else "black"),
                   (d["amarillo"], f"Umbral crítico ({d['amarillo']:g}{' min' if kpi == 'k4' else '%'})", "dot", "#c0392b")]
        for valor, nombre, estilo_l, color in lineas:
            fig.add_hline(y=valor, line_dash=estilo_l, line_color=color, line_width=1.4)
            fig.add_scatter(x=[None], y=[None], mode="lines", name=nombre, line=dict(dash=estilo_l, color=color, width=1.4))
        candidatos = [cur[f"{kpi}_ic_sup"].max() if d["ic"] else cur[kpi].max(),
                      prv[col_y].max() if len(prv) else np.nan, emp[col_y].max(),
                      d["amarillo"], d["verde"], 100 if kpi == "k1" else 0]
        tope = float(np.nanmax(np.array(candidatos, dtype=float)))
        y_max = min(tope * 1.18, 115) if kpi == "k5" else tope * 1.18
    if d["ic"]:
        fig.add_scatter(x=[None], y=[None], mode="lines", name="Margen de error (IC 95%)", line=dict(color="#444", width=1.2))
    sub_t = (f"<span style='font-size:12px;color:gray'>{d['codigo']} – {d['nombre']}, {MESES.get(ant, '')} y "
             f"{MESES[mes]} 2026. {'Mayor' if d['sentido'] == 'mayor' else 'Menor'} es mejor.</span>")
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.05,
                      title=dict(text=f"{titulo or titulo_automatico(df, kpi, mes)}<br>{sub_t}"),
                      yaxis=dict(title=d["eje"], range=[0, y_max],
                                 ticksuffix="" if kpi in ("k2", "k4") else "%", tickprefix="$" if kpi == "k2" else ""),
                      xaxis=dict(title="", categoryorder="array", categoryarray=[TOTAL] + orden))
    estilo(fig, 520, leyenda_abajo)
    if leyenda_abajo:
        fig.update_layout(margin=dict(b=150), legend=dict(y=-0.12))
    else:
        fig.update_layout(legend=dict(orientation="v", x=1.01, y=1, font=dict(size=11)), margin=dict(r=290))
    return fig


def fig_evolucion(df: pd.DataFrame, kpi: str, provincia: str) -> go.Figure:
    """Evolución enero–marzo de un KPI para una provincia frente al total de la empresa."""
    d = KPIS[kpi]
    col = "ticket_usd" if kpi == "k2" else kpi
    emp = tabla_mensual(df)
    prov = tabla_mensual(df[df["provincia"] == provincia])
    fig = go.Figure()
    for t, nombre, color, dash in [(emp, TOTAL, "#898781", "dot"), (prov, provincia, "#2a78d6", "solid")]:
        t = t.dropna(subset=[col])
        fig.add_scatter(x=t["mes"], y=t[col], name=nombre, mode="lines+markers+text",
                        line=dict(color=color, width=2, dash=dash), marker=dict(size=9, line=dict(color="white", width=2)),
                        text=[d["fmt_barra"].format(v) if nombre != TOTAL else "" for v in t[col]],
                        textposition="top center",
                        textfont=dict(size=11, color=TEXTO_2),
                        hovertemplate=f"{nombre} · %{{x}}: %{{y:.2f}}<extra></extra>")
    if kpi != "k2":
        fig.add_hline(y=d["verde"], line_dash="dash", line_color="black", line_width=1,
                      annotation_text=f"Meta {rango_estados(kpi)['verde']}", annotation_position="top left",
                      annotation_font=dict(size=11, color=TEXTO_2))
    fig.update_layout(title=f"{d['codigo']} – {d['corto']}: {provincia} vs. total empresa", yaxis_title=d["eje"],
                      xaxis_title=None)
    fig.update_yaxes(rangemode="tozero")
    return estilo(fig, 360)


def fig_tendencia_semanal(df: pd.DataFrame, metrica: str) -> go.Figure:
    """Seguimiento semanal (frecuencia operativa propuesta en las fichas)."""
    s = df.groupby("semana").agg(pedidos=("pedido_id", "count"), ventas=("ventas_asociadas_usd", "sum"),
                                 reclamos=("reclamos_registrados", "sum"), a_tiempo=("a_tiempo", "mean"),
                                 mediana=(T, "median"), dias=("fecha", "nunique")).reset_index()
    cfg = {
        "ventas_dia": ("Ventas promedio por día, por semana", "USD por día", s["ventas"] / s["dias"], None, "$,.0f"),
        "k3": ("KPI 3 · Tasa de reclamos semanal", "Reclamos por 100 pedidos (%)", s["reclamos"] / s["pedidos"] * 100, 3, ".1f"),
        "k4": ("KPI 4 · Mediana de entrega semanal", "Minutos", s["mediana"], 120, ".0f"),
        "k5": ("KPI 5 · Entregas a tiempo semanal", f"% en ≤ {SLA_MIN} min", s["a_tiempo"] * 100, 90, ".1f"),
    }
    titulo, eje, y, meta, f = cfg[metrica]
    s["completa"] = np.where(s["dias"] < 7, "semana incompleta", "semana completa")
    fig = go.Figure(go.Scatter(
        x=s["semana"], y=y, mode="lines+markers", line=dict(color="#2a78d6", width=2),
        marker=dict(size=8, line=dict(color="white", width=2)),
        customdata=np.stack([s["pedidos"], s["dias"], s["completa"]], axis=-1),
        hovertemplate=f"Semana del %{{x|%d-%b}}<br>{eje}: %{{y:{f}}}<br>Pedidos: %{{customdata[0]}}"
                      "<br>Días: %{customdata[1]} (%{customdata[2]})<extra></extra>"))
    if meta is not None:
        fig.add_hline(y=meta, line_dash="dash", line_color="black", line_width=1,
                      annotation_text=f"Meta {meta:g}", annotation_position="top left",
                      annotation_font=dict(size=11, color=TEXTO_2))
    fig.update_layout(title=titulo, yaxis_title=eje, xaxis_title=None, showlegend=False)
    if metrica == "ventas_dia":
        fig.update_yaxes(rangemode="tozero")
    return estilo(fig, 330)


def fig_ventas_por_dia(df: pd.DataFrame) -> go.Figure:
    """Ventas totales vs. ventas por día de cada mes: muestra el efecto calendario (febrero = 28 días)."""
    m = tabla_mensual(df)
    fig = go.Figure()
    fig.add_bar(x=m["mes"], y=m["ventas_dia"], marker_color=AZUL_OSCURO, name="Ventas por día",
                text=[f"${v:,.0f}/día" for v in m["ventas_dia"]], textposition="outside",
                customdata=np.stack([m["ventas_usd"], m["dias"]], axis=-1),
                hovertemplate="%{x}<br>Ventas por día: $%{y:,.0f}<br>Ventas del mes: $%{customdata[0]:,.0f} "
                              "(%{customdata[1]} días)<extra></extra>")
    fig.update_layout(title="<b>Por día, las ventas de marzo son iguales a las de febrero</b><br>"
                            "<span style='font-size:12px;color:gray'>Ventas promedio por día calendario "
                            "(febrero tiene 28 días)</span>",
                      yaxis_title="USD por día", showlegend=False)
    fig.update_yaxes(rangemode="tozero", range=[0, m["ventas_dia"].max() * 1.2])
    return estilo(fig, 360)


def fig_heatmap(df: pd.DataFrame, kpi: str, columnas: str = "canal_entrega") -> go.Figure:
    """Métrica base del KPI en el trimestre: provincia × otra dimensión (n < 30 marcado con *)."""
    metrica = {"k1": ("ventas_usd", "Ventas (USD)", "$,.0f"), "k2": ("ticket_usd", "Ticket (USD)", "$.2f"),
               "k3": ("tasa_reclamos", "Tasa de reclamos (%)", ".1f"), "k4": ("mediana_min", "Mediana de entrega (min)", ".0f"),
               "k5": ("pct_a_tiempo", "Entregas a tiempo (%)", ".1f")}[kpi]
    col, etiqueta, f = metrica
    t = tabla_periodo(df, ["provincia", columnas]).reset_index()
    z = t.pivot(index="provincia", columns=columnas, values=col)
    n = t.pivot(index="provincia", columns=columnas, values="pedidos").reindex_like(z)
    peor_arriba = KPIS[kpi]["sentido"] == "menor"
    z = z.loc[z.mean(axis=1).sort_values(ascending=not peor_arriba).index]
    n = n.loc[z.index]
    f_txt = f.replace("$", "")
    texto = [[("—" if pd.isna(v) else f"{'$' if '$' in f else ''}{v:{f_txt}}{'*' if (nn or 0) < N_MINIMO else ''}")
              for v, nn in zip(fila_z, fila_n)] for fila_z, fila_n in zip(z.values, n.values)]
    escala = SECUENCIAL if peor_arriba or kpi in ("k1", "k2") else SECUENCIAL[::-1]
    fig = go.Figure(go.Heatmap(z=z.values, x=[str(c) for c in z.columns], y=z.index, colorscale=escala, text=texto,
                               texttemplate="%{text}", customdata=n.values, xgap=2, ygap=2,
                               colorbar=dict(thickness=12, title=dict(text=etiqueta.split(" (")[0], side="right")),
                               hovertemplate=f"%{{y}} · %{{x}}<br>{etiqueta}: %{{z:{f}}}<br>Pedidos: %{{customdata:,}}<extra></extra>"))
    fig.update_layout(title=f"{etiqueta}: provincia × {columnas.replace('_', ' ')} (trimestre)", xaxis_title=None,
                      yaxis_title=None, margin=dict(t=90))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=False, side="top")
    return estilo(fig, 60 * len(z) + 150, leyenda_abajo=False)


def fig_matriz_priorizacion(df: pd.DataFrame) -> go.Figure:
    """Volumen (x) vs. tasa de reclamos del trimestre (y), tamaño = ventas, color = estado KPI 3."""
    r = tabla_periodo(df, "provincia").reset_index()
    fig = go.Figure()
    for e in ["verde", "amarillo", "rojo"]:
        s = r[r["estado_k3"] == e]
        if s.empty:
            continue
        fig.add_scatter(x=s["pedidos"], y=s["tasa_reclamos"], mode="markers+text", name=ESTADOS[e]["etiqueta"],
                        text=s["provincia"], textposition="top center", textfont=dict(size=12, color=TEXTO),
                        marker=dict(size=np.sqrt(s["ventas_usd"]) / 4.5, sizemin=10, color=ESTADOS[e]["color"],
                                    opacity=0.85, line=dict(color="white", width=2)),
                        customdata=np.stack([s["ventas_usd"], s["reclamos"], s["k3_ic_inf"], s["k3_ic_sup"],
                                             s["motivo_principal"]], axis=-1),
                        hovertemplate="<b>%{text}</b><br>Pedidos: %{x:,}<br>Tasa: %{y:.1f}% (IC 95% "
                                      "%{customdata[2]:.1f}–%{customdata[3]:.1f}%)<br>Reclamos: %{customdata[1]}"
                                      "<br>Ventas: $%{customdata[0]:,.0f}<br>Motivo principal: %{customdata[4]}<extra></extra>")
    for y, txt, color in [(3, "Meta 3%", "black"), (5, "Umbral crítico 5%", "#c0392b")]:
        fig.add_hline(y=y, line_dash="dash" if y == 3 else "dot", line_color=color, line_width=1,
                      annotation_text=txt, annotation_position="top left", annotation_font=dict(size=11, color=TEXTO_2))
    fig.update_layout(title="Matriz de priorización · trimestre (tamaño = ventas)",
                      xaxis_title="Pedidos del trimestre", yaxis_title="Reclamos por cada 100 pedidos (%)")
    fig.update_xaxes(rangemode="tozero")
    fig.update_yaxes(rangemode="tozero")
    return estilo(fig, 430)


def fig_boxplot_entrega(df: pd.DataFrame, por: str = "provincia") -> go.Figure:
    """Distribución del tiempo de entrega por canal, con meta del KPI 4 (120) y plazo del KPI 5 (180)."""
    orden = df.groupby(por, observed=True)[T].median().sort_values().index.tolist()
    fig = go.Figure()
    for canal, color in COLOR_CANAL.items():
        s = df[df["canal_entrega"] == canal]
        if s.empty:
            continue
        fig.add_trace(go.Box(y=s[por], x=s[T], name=canal, orientation="h", marker=dict(color=color, size=3, opacity=0.5),
                             line=dict(width=1.5), boxpoints="outliers",
                             hovertemplate="%{y}: %{x:.0f} min<extra>" + canal + "</extra>"))
    for x, txt, dash, pos in [(120, "Meta KPI 4 (120)", "dash", "top left"),
                              (SLA_MIN, f"Plazo KPI 5 ({SLA_MIN})", "dot", "top right")]:
        fig.add_vline(x=x, line_dash=dash, line_color="black", line_width=1, annotation_text=txt,
                      annotation_position=pos, annotation_font=dict(size=11, color=TEXTO_2))
    fig.update_layout(boxmode="group", title=f"Distribución del tiempo de entrega por {por.replace('_', ' ')} y canal",
                      xaxis_title="Minutos desde el pedido hasta la entrega", yaxis_title=None)
    fig.update_yaxes(categoryorder="array", categoryarray=orden)
    estilo(fig, max(480, 85 * len(orden) + 170))
    fig.update_layout(legend=dict(y=-0.13), margin=dict(b=110, t=90))
    return fig


def fig_histograma_plazo(df: pd.DataFrame) -> go.Figure:
    """Histograma por canal con el plazo único del KPI 5: evidencia que Programado queda penalizado."""
    canales = [c for c in COLOR_CANAL if c in df["canal_entrega"].unique()]
    fig = px.histogram(df, x=T, facet_col="canal_entrega", color="canal_entrega", color_discrete_map=COLOR_CANAL,
                       category_orders={"canal_entrega": canales}, nbins=60, facet_col_spacing=0.05)
    for i, canal in enumerate(canales, start=1):
        pct = df.loc[df["canal_entrega"] == canal, "a_tiempo"].mean() * 100
        fig.add_vline(x=SLA_MIN, col=i, line_dash="dot", line_color="black", line_width=1,
                      annotation_text=f"{SLA_MIN} min · {pct:.0f}% a tiempo", annotation_position="top right",
                      annotation_font=dict(size=11, color=TEXTO_2))
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]) if "=" in a.text else None)
    fig.update_traces(marker_line_width=0, hovertemplate="%{x} min<br>Pedidos: %{y}<extra></extra>")
    fig.update_layout(title="KPI 5 por canal: distribución del tiempo de entrega frente al plazo de 180 min",
                      showlegend=False, bargap=0.05)
    fig.update_xaxes(title_text="Minutos", matches=None)
    fig.update_yaxes(title_text=None)
    fig.update_yaxes(title_text="Pedidos", col=1)
    return estilo(fig, 350, leyenda_abajo=False)


def fig_reclamos_segun_plazo(df: pd.DataFrame) -> go.Figure:
    r = reclamos_segun_plazo(df).reset_index(names="grupo")
    fig = go.Figure(go.Bar(
        y=r["grupo"], x=r["tasa_reclamos"], orientation="h", marker_color=[AZUL_CLARO, AZUL_OSCURO][: len(r)],
        error_x=dict(type="data", symmetric=False, array=r["ic_sup"] - r["tasa_reclamos"],
                     arrayminus=r["tasa_reclamos"] - r["ic_inf"], color="#444", thickness=1.2, width=4),
        customdata=np.stack([r["reclamos"], r["pedidos"]], axis=-1),
        hovertemplate="%{y}<br>Tasa: %{x:.2f}%<br>Reclamos / pedidos: %{customdata[0]} / %{customdata[1]:,}<extra></extra>"))
    for _, fila in r.iterrows():
        fig.add_annotation(x=fila["ic_sup"], y=fila["grupo"], text=f"{fila['tasa_reclamos']:.1f}%", showarrow=False,
                           xanchor="left", xshift=8, font=dict(size=12))
    fig.add_vline(x=3, line_dash="dash", line_color="black", line_width=1, annotation_text="Meta KPI 3",
                  annotation_position="top", annotation_font=dict(size=11, color=TEXTO_2))
    fig.update_layout(title="Reclamos según plazo de entrega",
                      xaxis_title="Reclamos por cada 100 pedidos (%)", yaxis_title=None)
    fig.update_xaxes(range=[0, r["ic_sup"].max() * 1.3])
    return estilo(fig, 260)


def fig_pareto(df: pd.DataFrame) -> go.Figure:
    m = pareto_motivos(df).reset_index().sort_values("reclamos")
    fig = go.Figure(go.Bar(y=m["motivo_reclamo"], x=m["reclamos"], orientation="h", marker_color="#2a78d6",
                           text=[f"{r} · acum. {a:.0f} %" for r, a in zip(m["reclamos"], m["pct_acum"])],
                           textposition="outside", cliponaxis=False, customdata=m["pct"],
                           hovertemplate="%{y}<br>Reclamos: %{x} (%{customdata:.0f} %)<extra></extra>"))
    fig.update_layout(title="Motivos de reclamo (Pareto)", xaxis_title="Número de reclamos", yaxis_title=None)
    fig.update_xaxes(range=[0, max(m["reclamos"].max(), 1) * 1.7])
    return estilo(fig, 60 * max(len(m), 1) + 140)


def fig_demanda_hora_dia(df: pd.DataFrame) -> go.Figure:
    t = df.pivot_table(index="dia_semana", columns="hora", values="pedido_id", aggfunc="count", observed=False).fillna(0)
    fig = go.Figure(go.Heatmap(z=t.values, x=[f"{h}:00" for h in t.columns], y=t.index.astype(str),
                               colorscale=SECUENCIAL, xgap=2, ygap=2,
                               colorbar=dict(thickness=12, title=dict(text="Pedidos", side="right")),
                               hovertemplate="%{y} %{x}<br>Pedidos: %{z:.0f}<extra></extra>"))
    fig.update_layout(title="Pedidos por día y hora", xaxis_title="Hora del pedido", yaxis_title=None)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=False)
    return estilo(fig, 330, leyenda_abajo=False)
