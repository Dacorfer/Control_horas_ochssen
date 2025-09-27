import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta

st.set_page_config(page_title="Control de Horas", page_icon="⏱️", layout="wide")
st.title("⏱️ Control de Horas – Tabla editable (martes excluido)")

# ---------- Parámetros contrato ----------
OBJETIVO_SEMANAL = 42.0
DIAS_TRABAJO_SEMANA = 6                  # se trabaja 6 días (martes libre)
OBJETIVO_DIARIO = OBJETIVO_SEMANAL / DIAS_TRABAJO_SEMANA  # 7.0 h
INICIO_ANUAL = date(2025, 9, 4)          # inicio de cómputo anual
VAC_DIAS_EQ = 18                         # 3 semanas * 6 días = 18 días (año parcial)

# ---------- Utilidades ----------
def is_tuesday(d: date) -> bool:
    return d.weekday() == 1  # 0=Lun ... 1=Mar ... 6=Dom

def month_dates(year: int, month: int):
    ndays = calendar.monthrange(year, month)[1]
    return [date(year, month, d) for d in range(1, ndays+1)]

def parse_range_to_hours(text: str) -> float:
    """Convierte '16:30 a 23:00' o '16:30-23:00' a horas decimales."""
    if not text:
        return 0.0
    s = str(text).strip().lower().replace(" a ", "-").replace("–", "-").replace("—", "-")
    if "-" not in s:
        return 0.0
    a, b = [t.strip() for t in s.split("-", 1)]
    try:
        t1 = datetime.strptime(a, "%H:%M")
        t2 = datetime.strptime(b, "%H:%M")
        if t2 < t1:  # cruza medianoche
            t2 = t2 + timedelta(days=1)
        return round((t2 - t1).total_seconds()/3600.0, 2)
    except Exception:
        return 0.0

def iso_week_str(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"

def day_name_es(d: date) -> str:
    dias = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    return dias[d.weekday()]

# ---------- Selección de mes ----------
st.sidebar.header("Parámetros")
year = st.sidebar.number_input("Año", 2024, 2035, value=date.today().year, step=1)
month = st.sidebar.selectbox(
    "Mes",
    list(range(1,13)),
    index=date.today().month-1,
    format_func=lambda m: calendar.month_name[m].capitalize()
)

# ---------- Construcción de la tabla del mes ----------
fechas_mes = [d for d in month_dates(year, month) if not is_tuesday(d)]
base = pd.DataFrame({
    "Fecha": fechas_mes,
    "Día": [d.day for d in fechas_mes],
    "DíaSemana": [day_name_es(d) for d in fechas_mes],
    "SemanaISO": [iso_week_str(d) for d in fechas_mes],
    "Rango1": "",
    "Rango2": "",
    "PausaMin": 0,
    "Obs": ""
})

st.caption("Escribe rangos como **16:30-23:00** o **16:30 a 23:00**. "
           "La columna **HorasDía** se calcula automáticamente (R1+R2−Pausa/60).")

# ---------- Importar CSV (opcional) ----------
csv_in = st.file_uploader("Cargar CSV guardado previamente (opcional)", type=["csv"])
if csv_in is not None:
    try:
        prev = pd.read_csv(csv_in)
        if "Fecha" in prev.columns:
            prev["Fecha"] = pd.to_datetime(prev["Fecha"], errors="coerce").dt.date
            # fusionar por Fecha si coincide con el mes seleccionado
            mask_mes = [(d.month == month and d.year == year) if pd.notna(d) else False for d in prev["Fecha"]]
            prev_mes = prev.loc[mask_mes]
            for col in ["Rango1","Rango2","PausaMin","Obs"]:
                if col in prev_mes.columns:
                    base = base.merge(prev_mes[["Fecha", col]], on="Fecha", how="left", suffixes=("","_prev"))
                    base[col] = base[col+"_prev"].combine_first(base[col])
                    base.drop(columns=[c for c in base.columns if c.endswith("_prev")], inplace=True)
    except Exception as e:
        st.warning(f"No se pudo leer el CSV: {e}")

# ---------- Editor de tabla ----------
edited = st.data_editor(
    base,
    use_container_width=True,
    num_rows="fixed",
    hide_index=True,
    column_config={
        "Fecha": st.column_config.DateColumn(format="DD.MM.YYYY", step="d"),
        "PausaMin": st.column_config.NumberColumn(min_value=0, step=5),
    }
)

# ---------- Cálculo por día ----------
rows = []
for _, r in edited.iterrows():
    h1 = parse_range_to_hours(r["Rango1"])
    h2 = parse_range_to_hours(r["Rango2"])
    try:
        pausa = float(r["PausaMin"]) if r["PausaMin"] not in (None, "") else 0.0
    except:
        pausa = 0.0
    horas = round(max(0.0, h1 + h2 - pausa/60.0), 2)
    rows.append({**r.to_dict(), "HorasDía": horas})

calc = pd.DataFrame(rows)

st.markdown("### Tabla calculada")
st.dataframe(calc, use_container_width=True, hide_index=True)

# ---------- Totales semanales ----------
sem = calc.groupby("SemanaISO", as_index=False).agg(
    Días=("Fecha","count"),
    TotalSemana=("HorasDía","sum")
)
sem["ObjetivoSemana"] = (sem["Días"] * OBJETIVO_DIARIO).round(2)
sem["TotalSemana"] = sem["TotalSemana"].round(2)
sem["Balance"] = (sem["TotalSemana"] - sem["ObjetivoSemana"]).round(2)

st.markdown("### Resumen por semana (ISO)")
st.dataframe(sem, use_container_width=True, hide_index=True)

# ---------- Totales mensuales ----------
total_mes = round(calc["HorasDía"].sum(), 2)
dias_lab_mes = len(calc)
meta_mes = round(dias_lab_mes * OBJETIVO_DIARIO, 2)
faltante_mes = max(0.0, round(meta_mes - total_mes, 2))

st.markdown("### Resumen mensual")
st.write(f"- **Días laborables del mes (sin martes):** {dias_lab_mes}")
st.write(f"- **Meta mensual:** {meta_mes:.2f} h")
st.write(f"- **Acumulado mensual:** {total_mes:.2f} h")
st.write(f"- **Faltante mensual:** {faltante_mes:.2f} h")

# ---------- Resumen anual desde 04/09/2025 ----------
fin_mes = date(year, month, calendar.monthrange(year, month)[1])

# histórico anual = solo las filas del mes actual (si cargaste CSV, ya se fusionó)
hist = calc[(calc["Fecha"] >= INICIO_ANUAL) & (calc["Fecha"] <= fin_mes)]

total_anual = round(hist["HorasDía"].sum(), 2)
rango_total = pd.date_range(INICIO_ANUAL, fin_mes, freq="D")
dias_lab_anual = sum(1 for d in rango_total if d.weekday() != 1)  # sin martes
dias_efectivos = max(0, dias_lab_anual - VAC_DIAS_EQ)
meta_anual = round(dias_efectivos * OBJETIVO_DIARIO, 2)
faltante_anual = max(0.0, round(meta_anual - total_anual, 2))

st.markdown("### Resumen anual (desde 04/09/2025)")
c1, c2, c3 = st.columns(3)
with c1:
    st.write(f"- Días laborables teóricos: **{dias_lab_anual}**")
    st.write(f"- Vacaciones equivalentes: **{VAC_DIAS_EQ}**")
with c2:
    st.write(f"- Días efectivos: **{dias_efectivos}**")
    st.write(f"- Meta anual: **{meta_anual:.2f} h**")
with c3:
    st.write(f"- Total anual: **{total_anual:.2f} h**")
    st.write(f"- Faltante anual: **{faltante_anual:.2f} h**")

# ---------- Guardar CSV ----------
st.markdown("### Guardar")
out = calc.copy()
out["Fecha"] = pd.to_datetime(out["Fecha"]).dt.strftime("%Y-%m-%d")
st.download_button(
    "💾 Guardar como CSV",
    data=out.to_csv(index=False).encode("utf-8"),
    file_name=f"horas_{year}_{month:02d}.csv",
    mime="text/csv"
    )
