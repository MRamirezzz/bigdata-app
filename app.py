import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from scipy.stats import poisson

# Configuración de la página web
st.set_page_config(page_title="Big Data Over 1.5 - Central de Apuestas", page_icon="⚽", layout="wide")

st.title("⚽ CENTRAL DE APUESTAS BIG DATA - OVER 1.5")
st.markdown("### Sistema Autónomo: Escáner de 3 Días (Hoy + 2 días) + Validación Matemática")

@st.cache_data(ttl=3600)
def cargar_datos_partidos():
    hoy = datetime.now()
    fechas_buscar = [(hoy + timedelta(days=i)).strftime("%Y%m%d") for i in range(3)]

    ligas_reales = [
        {"id": "CHAMPIONS", "espn": "uefa.champions"},
        {"id": "EUROPA_L", "espn": "uefa.europa"},
        {"id": "ING1 (Premier)", "espn": "eng.1"},
        {"id": "ESP1 (LaLiga)", "espn": "esp.1"},
        {"id": "ALE1 (Bundesliga)", "espn": "ger.1"},
        {"id": "ITA1 (Serie A)", "espn": "ita.1"},
        {"id": "FRA1 (Ligue 1)", "espn": "fra.1"},
        {"id": "HOL1 (Eredivisie)", "espn": "ned.1"}
    ]

    partidos_auditados = []

    for liga in ligas_reales:
        for f in fechas_buscar:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga['espn']}/scoreboard?dates={f}"
            try:
                data = requests.get(url, timeout=5).json()
                for ev in data.get("events", []):
                    comp = ev["competitions"][0]
                    fecha_hora = ev["date"].replace("T", " ")[:16]
                    eq_l, eq_v = comp["competitors"][0], comp["competitors"][1]

                    nom_l = eq_l["team"]["displayName"]
                    nom_v = eq_v["team"]["displayName"]

                    rec_l = eq_l.get("records", [{}])[0].get("summary", "1-0-1")
                    rec_v = eq_v.get("records", [{}])[0].get("summary", "1-0-1")

                    linea_casa = float(comp.get("odds", [{}])[0].get("overUnder", 2.75) or 2.75)

                    partes_l = [int(x) for x in rec_l.split("-") if x.isdigit()]
                    partes_v = [int(x) for x in rec_v.split("-") if x.isdigit()]

                    juegos_l = max(sum(partes_l), 1)
                    juegos_v = max(sum(partes_v), 1)

                    fuerza_ataque_l = (partes_l[0] / juegos_l) * 1.8 + 0.9 if len(partes_l)==3 else 1.5
                    colador_visita = (partes_v[2] / juegos_v) * 1.9 + 0.8 if len(partes_v)==3 else 1.3

                    goles_esp_exactos = round(((fuerza_ataque_l + colador_visita) * 0.60) + (linea_casa * 0.40), 2)
                    prob_o15 = round((1 - (poisson.pmf(0, goles_esp_exactos) + poisson.pmf(1, goles_esp_exactos))) * 100, 1)

                    semaforo = "🟢 METER FICHA" if prob_o15 >= 82.0 else "🟡 PRECAUCIÓN"

                    partidos_auditados.append({
                        "Fecha": fecha_hora,
                        "Torneo": liga["id"],
                        "Partido": f"{nom_l} vs {nom_v}",
                        "⚽ Goles Esp.": goles_esp_exactos,
                        "🔥 Prob. Over 1.5": f"{prob_o15}%",
                        "Cuota Justa": round(100 / prob_o15, 2),
                        "Veredicto": semaforo
                    })
            except:
                pass

    return pd.DataFrame(partidos_auditados)

# Botón para actualizar en vivo
if st.button("🔄 Escanear Partidos en Vivo (Hoy + 2 Días)"):
    with st.spinner("Escaneando calendarios y calculando Poisson..."):
        df_app = cargar_datos_partidos()

    if not df_app.empty:
        st.success(f"¡{len(df_app)} partidos encontrados y auditados!")
        st.dataframe(df_app, use_container_width=True)
    else:
        st.warning("No se encontraron partidos en este rango o la API está cargando. Intenta de nuevo en unos segundos.")
else:
    st.info("👈 Dale clic al botón de arriba para iniciar el escaneo automático.")
