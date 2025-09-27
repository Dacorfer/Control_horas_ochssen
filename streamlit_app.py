import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta

st.set_page_config(page_title="Control de Horas", page_icon="⏱️", layout="centered")
st.title("⏱️ Control de Horas")

OBJETIVO_SEMANAL = 42.0
DIAS_TRABAJO_SEMANA = 6
OBJETIVO_DIARIO = OBJETIVO_SEMANAL / DIAS_TRABAJO_SEMANA  # 7.0 h
INICIO_ANUAL = date(2025, 9, 4)
VAC_DIAS_EQ = 18  # 3 semanas * 6 días

def is_tuesday(d: date) -> bool:
    return d.weekday() == 1

def month_dates(y: int, m: int):
    nd = calendar.monthrange(y, m)[1]
    return [date(y, m, d) for d in range(1, nd+1)]

def parse_hhmm(txt: str):
    if not txt: return None
    try:
        return datetime.strptime(txt.strip(), "%H:%M")
    except: 
        return None

def hours_between(a: str, b: str) -> float:
    t1, t2 = parse_hhmm(a), parse_hhmm(b)
    if t1 is None or t2 is None: return 0.0
    if t2 < t1: t2 = t2 + timedelta(days=1)  # por si cruza medianoche
    return round((t2 - t1).total_seconds()/3600.0, 2)

def iso_week_str(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"

# ── Controles arriba ──
c1, c2 = st.columns(2)
with c1:
    year = st.number_input("Año", 2024, 2035, value=date.today().year, step=1)
with c2:
    month = st.selectbox("Mes", list(range(1,13)),
                         index=date.today().month-1,
                         format_func=lambda m: calendar.month_name[m].capitalize())

st.caption("Introduce horas en formato **HH:MM**. Ejemplo: 09:00 / 13:30 / 16:00 / 22:00.")

# ── Base del mes ──
fechas_mes = [d for d in month_dates(year, month) if not is_tuesday(d)]
base = pd.DataFrame({
    "Fecha": fechas_mes,
    "FechaStr": [d.strftime("%a %d.%m.%Y") for d in fechas_mes],
    "SemanaISO": [iso_week_str(d) for d in fechas_mes],
    "Hora entrada mañana": "",
    "Hora salida mañana": "",
    "Hora entrada tarde": "",
    "Hora salida tarde": "",
    "Pausa (min)": 0,
    "Obs": ""
})

# ── Importar CSV (opcional) ──
csv_in = st.file_uploader("Cargar CSV previo (opcional)", type=["csv"])
if csv_in is not None:
    try:
        prev = pd.read_csv(csv_in)
        if "Fecha" in prev.columns:
            prev["Fecha"] = pd.to_datetime(prev["Fecha"], errors="coerce").dt.date
            prev["FechaStr"] = pd.to_datetime(prev["Fecha"]).dt.strftime("%a %d.%m.%Y")
            prev_mes = prev[(pd.to_datetime(prev["Fecha"]).dt.year == year) &
                            (pd.to_datetime(prev["Fecha"]).dt.month == month)]
            for col in ["Hora entrada mañana","Hora salida mañana","Hora entrada tarde","Hora salida tarde","Pausa (min)","Obs"]:
                if col in prev_mes.columns:
                    base = base.merge(prev_mes[["FechaStr", col]],
                                      on="FechaStr", how="left", suffixes=("","_prev"))
                    base[col] = base[f"{col}_prev"].combine_first(base[col])
                    base.drop(columns=[c for c in base.columns if c.endswith("_prev")], inplace=True)
    except Exception as e:
        st.warning(f"No se pudo leer el CSV: {e}")

# ── Editor minimalista ──
display = base.set_index("FechaStr")[[
    "Hora entrada mañana","Hora salida mañana","Hora entrada tarde","Hora salida tarde","Pausa (min)"
]].copy()

edited = st.data_editor(
    display,
    use_container_width=True,
    hide_index=False,
    num_rows="fixed",
    column_config={
        "Hora entrada mañana": st.column_config.TextColumn
