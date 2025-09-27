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
        "Hora entrada mañana": st.column_config.TextColumn(help="HH:MM"),
        "Hora salida mañana": st.column_config.TextColumn(help="HH:MM"),
        "Hora entrada tarde": st.column_config.TextColumn(help="HH:MM"),
        "Hora salida tarde": st.column_config.TextColumn(help="HH:MM"),
        "Pausa (min)": st.column_config.NumberColumn(min_value=0, step=5),
    }
)

# ── Cálculo de horas por día ──
calc = base.set_index("FechaStr").copy()
for col in edited.columns:
    calc[col] = edited[col]

rows = []
for _, r in calc.reset_index().iterrows():
    man = hours_between(r["Hora entrada mañana"], r["Hora salida mañana"])
    tar = hours_between(r["Hora entrada tarde"], r["Hora salida tarde"])
    try:
        pausa = float(r["Pausa (min)"]) if r["Pausa (min)"] not in ("", None) else 0.0
    except:
        pausa = 0.0
    horas = round(max(0.0, man + tar - pausa/60.0), 2)
    rows.append({
        "Fecha": r["Fecha"],
        "FechaStr": r["FechaStr"],
        "SemanaISO": r["SemanaISO"],
        "Hora entrada mañana": r["Hora entrada mañana"],
        "Hora salida mañana": r["Hora salida mañana"],
        "Hora entrada tarde": r["Hora entrada tarde"],
        "Hora salida tarde": r["Hora salida tarde"],
        "Pausa (min)": r["Pausa (min)"],
        "HorasDía": horas
    })
calc = pd.DataFrame(rows)

# ── Resúmenes ──
sem = calc.groupby("SemanaISO", as_index=False).agg(
    Dias=("Fecha","count"),
    TotalSemana=("HorasDía","sum")
)
sem["ObjetivoSemana"] = (sem["Dias"] * OBJETIVO_DIARIO).round(2)
sem["TotalSemana"] = sem["TotalSemana"].round(2)
sem["Balance"] = (sem["TotalSemana"] - sem["ObjetivoSemana"]).round(2)

total_mes = round(calc["HorasDía"].sum(), 2)
dias_lab_mes = len(calc)
meta_mes = round(dias_lab_mes * OBJETIVO_DIARIO, 2)
faltante_mes = max(0.0, round(meta_mes - total_mes, 2))

fin_mes = date(year, month, calendar.monthrange(year, month)[1])
hist = calc[(calc["Fecha"] >= INICIO_ANUAL) & (calc["Fecha"] <= fin_mes)]
total_anual = round(hist["HorasDía"].sum(), 2)
rango_total = pd.date_range(INICIO_ANUAL, fin_mes, freq="D")
dias_lab_anual = sum(1 for d in rango_total if d.weekday() != 1)
dias_efectivos = max(0, dias_lab_anual - VAC_DIAS_EQ)
meta_anual = round(dias_efectivos * OBJETIVO_DIARIO, 2)
faltante_anual = max(0.0, round(meta_anual - total_anual, 2))

st.markdown("---")
c1, c2, c3 = st.columns(3)
c1.metric("Acumulado mensual (h)", f"{total_mes:.2f}")
c2.metric("Meta mensual (h)", f"{meta_mes:.2f}")
c3.metric("Faltante mensual (h)", f"{faltante_mes:.2f}")

st.markdown("### Resumen semanal (ISO)")
st.dataframe(sem, use_container_width=True, hide_index=True)

st.markdown("### Resumen anual (desde 04/09/2025)")
cc1, cc2, cc3 = st.columns(3)
cc1.metric("Total anual (h)", f"{total_anual:.2f}")
cc2.metric("Meta anual (h)", f"{meta_anual:.2f}")
cc3.metric("Faltante anual (h)", f"{faltante_anual:.2f}")

# ── Guardar CSV ──
out = calc.copy()
out["Fecha"] = pd.to_datetime(out["Fecha"]).dt.strftime("%Y-%m-%d")
st.download_button(
    "💾 Guardar como CSV",
    data=out.to_csv(index=False).encode("utf-8"),
    file_name=f"horas_{year}_{month:02d}.csv",
    mime="text/csv"
)
