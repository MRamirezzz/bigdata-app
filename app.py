import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from scipy.stats import poisson

# Configuración principal
st.set_page_config(page_title="Portal Fútbol & Big Data - Miguel Ramirez", page_icon="⚽", layout="wide")

if "seguidos" not in st.session_state:
    st.session_state["seguidos"] = []

# Estilos visuales oscuros para tarjetas y detalles del partido
st.markdown("""
<style>
.liga-header {
    background-color: #1a1c23;
    color: #ffffff;
    padding: 10px 16px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 16px;
    border-left: 4px solid #00ffcc;
    margin-top: 16px;
    margin-bottom: 6px;
}
.match-card {
    background-color: #121318;
    padding: 8px 14px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: #e0e0e0;
    border: 1px solid #222530;
}
.status-badge {
    background-color: #262936;
    color: #9ba1b0;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: bold;
    min-width: 75px;
    text-align: center;
}
.status-live {
    background-color: #ff2a4b;
    color: #ffffff;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: bold;
    min-width: 75px;
    text-align: center;
}
.teams-container {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-grow: 1;
    gap: 12px;
}
.team-home {
    text-align: right;
    width: 38%;
    font-weight: 600;
    font-size: 15px;
}
.team-away {
    text-align: left;
    width: 38%;
    font-weight: 600;
    font-size: 15px;
}
.score-box {
    background-color: #1f222d;
    padding: 4px 12px;
    border-radius: 6px;
    font-weight: 800;
    font-size: 15px;
    color: #00ffcc;
    min-width: 70px;
    text-align: center;
}
.team-logo {
    width: 24px;
    height: 24px;
    object-fit: contain;
}
</style>
""", unsafe_allow_html=True)

# Cabecera limpia con tu nombre
st.title("⚽ PORTAL DE FÚTBOL & CENTRAL BIG DATA")
st.markdown("<h2 style='text-align: center; color: #00ffcc; letter-spacing: 2px;'>CREADO POR MIGUEL RAMIREZ</h2>", unsafe_allow_html=True)

# Botón para autorizar notificaciones del navegador
components.html("""
<div style="display: flex; justify-content: flex-end; align-items: center; font-family: sans-serif;">
    <button id="btn-permiso" onclick="pedirPermiso()" style="background-color: #1f222d; color: #00ffcc; border: 1px solid #00ffcc; padding: 6px 14px; border-radius: 8px; font-weight: bold; cursor: pointer;">
        🔔 Habilitar Avisos en este Dispositivo
    </button>
</div>
<script>
function pedirPermiso() {
    if (!("Notification" in window)) {
        alert("Tu navegador no soporta notificaciones web.");
    } else {
        Notification.requestPermission().then(function (permission) {
            if (permission === "granted") {
                document.getElementById("btn-permiso").innerText = "✅ Avisos Activados";
                new Notification("⚽ Central Big Data - Miguel Ramirez", {
                    body: "Marca la casilla 🔔 Seguir en los partidos que quieras monitorear."
                });
            }
        });
    }
}
</script>
""", height=40)

def enviar_notificacion_legible(partido, detalle_alerta):
    components.html(f"""
    <script>
    if ("Notification" in window && Notification.permission === "granted") {{
        new Notification("🚨 ALERTA EN VIVO: {partido}", {{
            body: "{detalle_alerta}"
        }});
    }}
    </script>
    """, height=0)

# =============================================================================
# LAS 19 LIGAS OFICIALES DEL ARCHIVO BIG DATA (.INI) + CHAMPIONS LEAGUE
# =============================================================================
LIGAS_BIG_DATA = [
    {"id": "🏆 Champions League", "espn": "uefa.champions", "efec": "85%", "bloque": "Élite"},
    {"id": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League (ING1)", "espn": "eng.1", "efec": "80%", "bloque": "Top 5"},
    {"id": "🇪🇸 LaLiga (ESP1)", "espn": "esp.1", "efec": "79%", "bloque": "Top 5"},
    {"id": "🇮🇹 Serie A (ITA1)", "espn": "ita.1", "efec": "81%", "bloque": "Top 5"},
    {"id": "🇩🇪 Bundesliga (ALE1)", "espn": "ger.1", "efec": "86%", "bloque": "Hiper-Ofensiva"},
    {"id": "🇫🇷 Ligue 1 (FRA1)", "espn": "fra.1", "efec": "80%", "bloque": "Top 5"},
    {"id": "🇨🇭 Challenge League (SUI2)", "espn": "sui.2", "efec": "91%", "bloque": "Hiper-Ofensiva"},
    {"id": "🇨🇭 Super League (SUI1)", "espn": "sui.1", "efec": "89%", "bloque": "Hiper-Ofensiva"},
    {"id": "🇳🇱 Eredivisie (HOL1)", "espn": "ned.1", "efec": "88%", "bloque": "Hiper-Ofensiva"},
    {"id": "🇳🇱 Eerste Divisie (HOL2)", "espn": "ned.2", "efec": "85%", "bloque": "Hiper-Ofensiva"},
    {"id": "🇳🇴 Eliteserien (NOR1)", "espn": "nor.1", "efec": "87%", "bloque": "Hiper-Ofensiva"},
    {"id": "🇳🇴 1. Division (NOR2)", "espn": "nor.2", "efec": "86%", "bloque": "Hiper-Ofensiva"},
    {"id": "🇩🇪 2. Bundesliga (ALE2)", "espn": "ger.2", "efec": "84%", "bloque": "Hiper-Ofensiva"},
    {"id": "🇦🇹 Bundesliga (AUT1)", "espn": "aut.1", "efec": "84%", "bloque": "Hiper-Ofensiva"},
    {"id": "🇧🇪 Jupiler Pro League (BEL1)", "espn": "bel.1", "efec": "83%", "bloque": "Élite"},
    {"id": "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Premiership (ESC1)", "espn": "sco.1", "efec": "83%", "bloque": "Élite"},
    {"id": "🇹🇷 Süper Lig (TUR1)", "espn": "tur.1", "efec": "82%", "bloque": "Élite"},
    {"id": "🇵🇹 Primeira Liga (POR1)", "espn": "por.1", "efec": "81%", "bloque": "Élite"},
    {"id": "🇺🇸 MLS (USA1)", "espn": "usa.1", "efec": "84%", "bloque": "América"},
    {"id": "🇲🇽 Liga MX (MEX1)", "espn": "mex.1", "efec": "80%", "bloque": "América"},
]

# Base de datos completa del Paso 1 de tu archivo .ini
TOP_DISPARADORES = {
    "Bayern Munich": {"sot": 7.8, "xg_shot": 0.16, "tag": "👑 Rey Casa / Top SoT"},
    "Celtic": {"sot": 8.0, "xg_shot": 0.16, "tag": "👑 Rey Casa / Top SoT"},
    "PSV Eindhoven": {"sot": 7.5, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top SoT"},
    "Barcelona": {"sot": 7.4, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top SoT"},
    "Manchester City": {"sot": 7.2, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"},
    "Sporting CP": {"sot": 7.1, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top SoT"},
    "Bodo/Glimt": {"sot": 7.0, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"},
    "Galatasaray": {"sot": 7.0, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"},
    "Young Boys": {"sot": 6.8, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"},
    "Toluca": {"sot": 6.6, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"},
    "Inter Miami": {"sot": 6.5, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top SoT"},
    "Atalanta": {"sot": 6.5, "xg_shot": 0.13, "tag": "👑 Rey Casa / Top SoT"},
    "Salzburg": {"sot": 6.4, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"},
    "Thun": {"sot": 6.3, "xg_shot": 0.13, "tag": "👑 Rey Casa / Top SoT"},
    "Jong Ajax": {"sot": 6.2, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Kongsvinger": {"sot": 6.1, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Karlsruher": {"sot": 6.1, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Tottenham": {"sot": 6.2, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Union SG": {"sot": 6.2, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Fenerbahce": {"sot": 6.5, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "Benfica": {"sot": 6.6, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "Inter": {"sot": 6.3, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "Paris Saint-Germain": {"sot": 7.1, "xg_shot": 0.15, "tag": "👑 Rey Casa"},
    "AS Monaco": {"sot": 6.1, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Real Madrid": {"sot": 6.8, "xg_shot": 0.15, "tag": "👑 Rey Casa"},
    "Wil": {"sot": 5.8, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "St. Gallen": {"sot": 5.8, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Ajax": {"sot": 6.2, "xg_shot": 0.14, "tag": "👹 Monstruo Visita"},
    "Dordrecht": {"sot": 5.8, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Molde": {"sot": 6.0, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Raufoss": {"sot": 5.7, "xg_shot": 0.12, "tag": "👹 Monstruo Visita"},
    "Hoffenheim": {"sot": 5.7, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Magdeburg": {"sot": 5.8, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Wolfsberger": {"sot": 5.7, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Aston Villa": {"sot": 5.8, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Genk": {"sot": 5.9, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Rangers": {"sot": 6.1, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Trabzonspor": {"sot": 5.7, "xg_shot": 0.12, "tag": "👹 Monstruo Visita"},
    "Braga": {"sot": 5.9, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Portland Timbers": {"sot": 5.8, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "AC Milan": {"sot": 6.0, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Rennes": {"sot": 5.7, "xg_shot": 0.12, "tag": "👹 Monstruo Visita"},
    "Villarreal": {"sot": 5.9, "xg_shot": 0.14, "tag": "👹 Monstruo Visita"},
    "Santos": {"sot": 5.6, "xg_shot": 0.12, "tag": "👹 Monstruo Visita"},
}

DEFENSAS_COLADOR = [
    "Baden", "Schaffhausen", "Yverdon", "Grasshopper", "Waalwijk", "Almere City",
    "TOP Oss", "Jong Utrecht", "Sandefjord", "Haugesund", "Levanger", "Raufoss",
    "Bochum", "Augsburg", "Braunschweig", "Regensburg", "Tirol", "Blau-Weiss Linz",
    "Southampton", "Ipswich", "Leicester", "Kortrijk", "Eupen", "Ross County",
    "St. Johnstone", "Hatayspor", "Konyaspor", "Estrela", "Farense", "San Jose",
    "Chicago Fire", "Hellas Verona", "Venezia", "Angers", "Saint-Etienne",
    "Espanyol", "Valladolid", "Puebla", "Mazatlan"
]

BLOQUES_CERROJO = ["Getafe", "Mallorca", "Empoli", "Everton"]

def auditar_equipo_bd(nombre_equipo):
    sot_base = 4.9
    xg_shot = 0.11
    etiqueta = "Estándar"
    es_colador = False
    es_cerrojo = False

    for k, val in TOP_DISPARADORES.items():
        if k.lower() in nombre_equipo.lower():
            sot_base = val["sot"]
            xg_shot = val["xg_shot"]
            etiqueta = val["tag"]
            break

    for col in DEFENSAS_COLADOR:
        if col.lower() in nombre_equipo.lower():
            es_colador = True
            etiqueta = "🧀 Defensa Colador" if etiqueta == "Estándar" else etiqueta + " / 🧀 Colador"
            break

    for cer in BLOQUES_CERROJO:
        if cer.lower() in nombre_equipo.lower():
            es_cerrojo = True
            etiqueta = "🧱 Bloque Bajo (Cerrojo)"
            break

    return sot_base, xg_shot, etiqueta, es_colador, es_cerrojo

def extraer_stat_live(team_dict, stat_names):
    for st_item in team_dict.get("statistics", []):
        if st_item.get("name") in stat_names:
            try:
                return float(st_item.get("displayValue", 0))
            except:
                return 0.0
    return 0.0

@st.cache_data(ttl=90)
def obtener_partidos_ligas(codigos_espn, dias=4):
    hoy = datetime.now()
    fechas = [(hoy + timedelta(days=i)).strftime("%Y%m%d") for i in range(dias)]
    mapa_ligas = {l["espn"]: l for l in LIGAS_BIG_DATA}
    datos_por_liga = {mapa_ligas[c]["id"]: {"meta": mapa_ligas[c], "eventos": []} for c in codigos_espn if c in mapa_ligas}
    ids_vistos = set()

    for c in codigos_espn:
        if c not in mapa_ligas:
            continue
        liga_obj = mapa_ligas[c]
        for f_str in fechas:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{c}/scoreboard?dates={f_str}"
            try:
                res = requests.get(url, timeout=3)
                if res.status_code == 200:
                    for ev in res.json().get("events", []):
                        ev_id = ev.get("id")
                        if ev_id not in ids_vistos:
                            ids_vistos.add(ev_id)
                            datos_por_liga[liga_obj["id"]]["eventos"].append(ev)
            except Exception:
                pass
    return datos_por_liga

# =============================================================================
# ESTRUCTURA DE LAS 3 SECCIONES
# =============================================================================
sec_futbol, sec_apuestas, sec_live = st.tabs([
    "⚽ 1. RESULTADOS Y DETALLES (PORTADA)", 
    "🎯 2. PRE-APUESTAS OVER 1.5 (MOTOR BIG DATA)", 
    "🚨 3. SCRAPING EN VIVO (MINUTO 18+)"
])

# -----------------------------------------------------------------------------
# SECCIÓN 1: PORTADA CON DESPLEGABLE DE GOLES, EVENTOS Y ESTADÍSTICAS AL CLIC
# -----------------------------------------------------------------------------
with sec_futbol:
    col_filtro1, col_filtro2 = st.columns([2, 2])
    with col_filtro1:
        modo_ligas_portada = st.radio(
            "Ligas en Portada:",
            ["⭐ Champions + 5 Grandes Ligas", "🌍 Todas las 19 Ligas del Big Data"],
            horizontal=True
        )
    with col_filtro2:
        st.caption("💡 **Haz clic sobre la barra de detalles debajo de cualquier partido** para abrir goles, minutos y estadísticas.")

    if modo_ligas_portada == "⭐ Champions + 5 Grandes Ligas":
        codigos_portada = ["uefa.champions", "eng.1", "esp.1", "ita.1", "ger.1", "fra.1"]
    else:
        codigos_portada = [l["espn"] for l in LIGAS_BIG_DATA]

    datos_portada = obtener_partidos_ligas(codigos_portada, dias=4)

    for nombre_liga, contenido in datos_portada.items():
        eventos = contenido["eventos"]
        if not eventos:
            continue

        st.markdown(f"<div class='liga-header'>{nombre_liga}</div>", unsafe_allow_html=True)

        for ev in eventos:
            comp = ev.get("competitions", [{}])[0]
            st_state = comp.get("status", {}).get("type", {}).get("state", "pre")
            detalle_corto = comp.get("status", {}).get("type", {}).get("shortDetail", "")
            reloj = comp.get("status", {}).get("displayClock", "")

            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                loc = competitors[0]
                vis = competitors[1]

                nom_l = loc.get("team", {}).get("shortDisplayName", loc.get("team", {}).get("displayName", "Local"))
                nom_v = vis.get("team", {}).get("shortDisplayName", vis.get("team", {}).get("displayName", "Visita"))
                logo_l = loc.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
                logo_v = vis.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
                gol_l = loc.get("score", "0")
                gol_v = vis.get("score", "0")
                id_unico_partido = f"{nom_l} vs {nom_v} ({nombre_liga})"

                if st_state == "in":
                    badge_html = f"<div class='status-live'>🔴 {reloj}</div>"
                    centro_html = f"{gol_l} - {gol_v}"
                elif st_state == "post":
                    badge_html = "<div class='status-badge'>FINAL</div>"
                    centro_html = f"{gol_l} - {gol_v}"
                else:
                    try:
                        dt = datetime.fromisoformat(ev.get("date", "").replace("Z", "+00:00"))
                        badge_html = f"<div class='status-badge'>{dt.strftime('%d/%m')}</div>"
                        centro_html = dt.strftime("%H:%M")
                    except:
                        badge_html = f"<div class='status-badge'>{detalle_corto}</div>"
                        centro_html = "vs"

                col_card, col_bell = st.columns([10, 2])
                with col_card:
                    st.markdown(f"""
                    <div class="match-card">
                        {badge_html}
                        <div class="teams-container">
                            <div class="team-home">{nom_l}</div>
                            <img src="{logo_l}" class="team-logo">
                            <div class="score-box">{centro_html}</div>
                            <img src="{logo_v}" class="team-logo">
                            <div class="team-away">{nom_v}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # DESPLEGABLE INTERACTIVO AL DAR CLIC PARA VER QUÉ PASÓ EN EL PARTIDO
                    with st.expander(f"📊 Ver qué pasó en el partido: Goles, Minutos y Estadísticas ({nom_l} vs {nom_v})"):
                        # 1. Extraer Goles y Tarjetas (comp.details)
                        detalles_partido = comp.get("details", [])
                        eventos_texto = []
                        for d in detalles_partido:
                            min_ev = d.get("clock", {}).get("displayValue", "")
                            tipo_ev = d.get("type", {}).get("text", "")
                            jugadores = d.get("athletesInvolved", [])
                            nom_jug = jugadores[0].get("displayName", "Jugador") if jugadores else ""
                            es_gol = d.get("scoringPlay", False)
                            es_tarjeta = d.get("yellowCard", False) or d.get("redCard", False)

                            if es_gol:
                                eventos_texto.append(f"⚽ **GOL ({min_ev})**: {nom_jug} ({tipo_ev})")
                            elif d.get("redCard", False):
                                eventos_texto.append(f"🟥 **Tarjeta Roja ({min_ev})**: {nom_jug}")
                            elif d.get("yellowCard", False):
                                eventos_texto.append(f"🟨 ** Amarilla ({min_ev})**: {nom_jug}")

                        if eventos_texto:
                            st.markdown("**📋 Resumen de Acciones del Partido:**")
                            for ev_linea in eventos_texto:
                                st.markdown(f"- {ev_linea}")
                        else:
                            if st_state == "pre":
                                st.info("⏳ El partido aún no ha comenzado. Aquí verás los goles y estadísticas apenas inicie.")
                            else:
                                st.write("Sin goles o incidencias registradas en el acta hasta el momento.")

                        # 2. Extraer Estadísticas Cara a Cara
                        pos_l = extraer_stat_live(loc, ["possessionPct"])
                        pos_v = extraer_stat_live(vis, ["possessionPct"])
                        sot_l = int(extraer_stat_live(loc, ["shotsOnTarget", "shotsOnGoal"]))
                        sot_v = int(extraer_stat_live(vis, ["shotsOnTarget", "shotsOnGoal"]))
                        tir_l = int(extraer_stat_live(loc, ["totalShots", "shots"]))
                        tir_v = int(extraer_stat_live(vis, ["totalShots", "shots"]))
                        cor_l = int(extraer_stat_live(loc, ["wonCorners", "corners"]))
                        cor_v = int(extraer_stat_live(vis, ["wonCorners", "corners"]))

                        df_stats_partido = pd.DataFrame([
                            {"Métrica": "Posesión (%)", nom_l: f"{pos_l}%", nom_v: f"{pos_v}%"},
                            {"Métrica": "🎯 Tiros al Arco (SoT)", nom_l: sot_l, nom_v: sot_v},
                            {"Métrica": "💥 Disparos Totales", nom_l: tir_l, nom_v: tir_v},
                            {"Métrica": "🚩 Tiros de Esquina", nom_l: cor_l, nom_v: cor_v},
                        ])
                        st.table(df_stats_partido)

                with col_bell:
                    ya_seguido = id_unico_partido in st.session_state["seguidos"]
                    chk = st.checkbox("🔔 Seguir", value=ya_seguido, key=f"bell_{ev.get('id')}")
                    if chk and not ya_seguido:
                        st.session_state["seguidos"].append(id_unico_partido)
                    elif not chk and ya_seguido:
                        st.session_state["seguidos"].remove(id_unico_partido)

# -----------------------------------------------------------------------------
# SECCIÓN 2: PRE-APUESTAS OVER 1.5 (BAJO DEMANDA Y SIN VEREDICTO EN VIVO)
# -----------------------------------------------------------------------------
with sec_apuestas:
    st.subheader("🎯 Laboratorio de Pre-Apuesta Over 1.5 (Las 19 Ligas Oficiales Big Data)")
    st.markdown("Analiza **únicamente partidos antes de iniciar (Pre-Partido)** aplicando tus 6 pasos: **SoT >= 5.5**, **xG/Shot >= 0.12**, **Cruces de Oro** y bloqueo por **Cerrojo**.")

    opciones_ligas_pre = [l["id"] for l in LIGAS_BIG_DATA]
    ligas_seleccionadas_pre = st.multiselect(
        "📌 Selecciona las Ligas que deseas auditar para Pre-Apuesta (Por defecto están las 19 ligas + Champions):",
        options=opciones_ligas_pre,
        default=opciones_ligas_pre
    )

    if st.button("🚀 GENERAR REPORTE DE PRE-APUESTA OVER 1.5"):
        codigos_pre = [l["espn"] for l in LIGAS_BIG_DATA if l["id"] in ligas_seleccionadas_pre]
        with st.spinner("Auditando las 19 ligas del archivo Big Data para Pre-Apuesta..."):
            datos_pre = obtener_partidos_ligas(codigos_pre, dias=4)
            reporte_pre = []

            for nombre_liga, contenido in datos_pre.items():
                efec_liga = contenido["meta"]["efec"]
                for evento in contenido["eventos"]:
                    comp = evento.get("competitions", [{}])[0]
                    st_state = comp.get("status", {}).get("type", {}).get("state", "pre")

                    # FILTRO ESTRICTO: SOLO PARTIDOS PRE-APUESTA (QUE NO HAN EMPEZADO)
                    if st_state != "pre":
                        continue

                    competitors = comp.get("competitors", [])
                    if len(competitors) == 2:
                        nom_local = competitors[0].get("team", {}).get("displayName", "Local")
                        nom_visita = competitors[1].get("team", {}).get("displayName", "Visita")
                        fecha_iso = evento.get("date", "")
                        try:
                            dt = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00"))
                            fecha_str = dt.strftime("%d/%m %H:%M")
                        except:
                            fecha_str = "Próximo"

                        sot_l, xgs_l, tag_l, col_l, cer_l = auditar_equipo_bd(nom_local)
                        sot_v, xgs_v, tag_v, col_v, cer_v = auditar_equipo_bd(nom_visita)

                        sot_combinado = round((sot_l + sot_v) / 1.6, 1)
                        calidad_disparo = round(max(xgs_l, xgs_v), 2)
                        xg_base = round((sot_l * xgs_l * 1.2) + (sot_v * xgs_v), 2)
                        
                        regla_aplicada = "Análisis Estándar Pre-Partido"
                        bono_prob = 0.0

                        if (sot_l >= 6.0 and col_v):
                            xg_base += 0.65
                            bono_prob += 7.0
                            regla_aplicada = "🔥 REGLA A: Rey Casa vs Defensa Colador"
                        elif (sot_v >= 5.7 and col_l):
                            xg_base += 0.50
                            bono_prob += 5.0
                            regla_aplicada = "⚡ REGLA B: Monstruo Visita vs Colador"
                        elif (sot_l >= 6.2 and sot_v >= 6.0):
                            xg_base += 0.70
                            bono_prob += 6.0
                            regla_aplicada = "💥 REGLA C: Choque Top Disparadores (Monitor 2.5)"

                        if cer_l or cer_v:
                            xg_base = max(1.35, xg_base - 0.55)
                            bono_prob -= 10.0
                            regla_aplicada = "🧱 ALERTA KRIPTONITA: Bloque Bajo Cerrojo (-10%)"

                        prob_poisson = (1 - poisson.cdf(1, xg_base)) * 100
                        prob_final = round(min(98.5, max(45.0, prob_poisson + bono_prob)), 1)
                        cuota_justa = round(100 / prob_final, 2)

                        # VEREDICTOS EXCLUSIVOS DE PRE-APUESTA (SIN MENCIONAR EN VIVO)
                        if cer_l or cer_v:
                            veredicto_pre = "🛑 ABORTAR PRE-APUESTA (Riesgo Cerrojo)"
                        elif prob_final >= 85.0 and calidad_disparo >= 0.13:
                            veredicto_pre = "🟢 METER FICHA PRE-PARTIDO (Prioritaria 95%+)"
                        elif prob_final >= 78.0:
                            veredicto_pre = "🟢 METER FICHA PRE-PARTIDO (Over 1.5)"
                        else:
                            veredicto_pre = "⚪ DESCARTAR PRE-APUESTA (Bajo Voltaje)"

                        reporte_pre.append({
                            "Fecha / Hora": fecha_str,
                            "Liga (Efectividad)": f"{nombre_liga} ({efec_liga})",
                            "Partido": f"{nom_local} vs {nom_visita}",
                            "🎯 SoT Proy.": sot_combinado,
                            "💎 xG/Shot": calidad_disparo,
                            "⚽ xG Esp.": round(xg_base, 2),
                            "🔥 Prob. Over 1.5": f"{prob_final}%",
                            "Cuota Mín. Valor": cuota_justa,
                            "Regla Big Data": regla_aplicada,
                            "Veredicto Pre-Apuesta": veredicto_pre
                        })

            if reporte_pre:
                st.success(f"✅ {len(reporte_pre)} partidos Pre-Partido auditados en las ligas seleccionadas.")
                st.dataframe(pd.DataFrame(reporte_pre), use_container_width=True, hide_index=True)
            else:
                st.info("No hay partidos pendientes por iniciar en este rango para las ligas seleccionadas.")
    else:
        st.info("👆 Selecciona tus ligas y presiona el botón para generar la tabla de Pre-Apuestas.")

# -----------------------------------------------------------------------------
# SECCIÓN 3: SCRAPING EN VIVO AUTOMÁTICO (DESPUÉS DEL MINUTO 18 EN TODAS LAS LIGAS)
# -----------------------------------------------------------------------------
with sec_live:
    st.subheader("🚨 Radar de Scraping en Vivo Automático (Activación Minuto 18+)")
    st.markdown("Escanea en automático las **19 Ligas del Big Data + Champions**. En cuanto el reloj supera el **minuto 18**, audita los tiros al arco y emite el **Veredicto En Vivo** para cazar el **Over 0.5 HT / Over 1.5 Live**.")

    col_l1, col_l2 = st.columns(2)
    with col_l1:
        auto_monitor = st.checkbox("🔄 Scraping Automático Continuo (Refresca cada 60 seg)", value=True)
    with col_l2:
        solo_en_juego = st.checkbox("🔴 Mostrar únicamente partidos En Juego actualmente", value=False)

    # Escanear hoy para todas las 19 ligas + Champions
    codigos_todas = [l["espn"] for l in LIGAS_BIG_DATA]
    datos_live_todas = obtener_partidos_ligas(codigos_todas, dias=1)

    partidos_monitoreados = []
    alertas_minuto_18 = []

    for nombre_liga, contenido in datos_live_todas.items():
        for evento in contenido["eventos"]:
            comp = evento.get("competitions", [{}])[0]
            status_type = comp.get("status", {}).get("type", {}).get("state", "pre")
            reloj = comp.get("status", {}).get("displayClock", "0'")
            detalle = comp.get("status", {}).get("type", {}).get("shortDetail", "Programado")

            if solo_en_juego and status_type != "in":
                continue

            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                local = competitors[0]
                visita = competitors[1]
                nom_l = local.get("team", {}).get("shortDisplayName", "Local")
                nom_v = visita.get("team", {}).get("shortDisplayName", "Visita")
                id_unico = f"{nom_l} vs {nom_v} ({nombre_liga})"

                goles_l = int(local.get("score", 0) or 0)
                goles_v = int(visita.get("score", 0) or 0)
                goles_tot = goles_l + goles_v

                tiros_l = extraer_stat_live(local, ["totalShots", "shots"])
                tiros_v = extraer_stat_live(visita, ["totalShots", "shots"])
                sot_l = extraer_stat_live(local, ["shotsOnTarget", "shotsOnGoal"])
                sot_v = extraer_stat_live(visita, ["shotsOnTarget", "shotsOnGoal"])

                sot_live = int(sot_l + sot_v)
                tiros_live = int(tiros_l + tiros_v)

                sot_h_l, xgs_l, tag_l, col_l, cer_l = auditar_equipo_bd(nom_l)
                sot_h_v, xgs_v, tag_v, col_v, cer_v = auditar_equipo_bd(nom_v)

                min_num = 0
                try:
                    min_num = int(reloj.replace("'", "").split("+")[0])
                except:
                    min_num = 0

                tiene_campanita = id_unico in st.session_state["seguidos"]
                icono_campana = "🔔 Sí" if tiene_campanita else "🔕 No"

                # VEREDICTO EN VIVO AUTOMÁTICO DESPUÉS DEL MINUTO 18
                veredicto_en_vivo = "⏳ Esperando Minuto 18'"
                if status_type == "in":
                    if min_num < 18:
                        veredicto_en_vivo = f"🕒 Calentando ({reloj} < 18')"
                    else:
                        if goles_tot == 0:
                            if sot_live >= 3 or tiros_live >= 6 or sot_h_l >= 6.5 or col_v:
                                veredicto_en_vivo = "🚨 METER OVER 0.5 HT / OVER 1.5 LIVE (0-0 con Asedio)"
                                txt_alerta = (
                                    f"⚽ {nom_l} vs {nom_v} ({nombre_liga}) | ⏱️ Minuto {reloj} (0-0) | "
                                    f"🎯 Tiros al arco: {sot_live} | 💥 Disparos: {tiros_live} | "
                                    f"👉 VEREDICTO EN VIVO: METER OVER 0.5 / 1.5"
                                )
                                alertas_minuto_18.append(txt_alerta)
                                if tiene_campanita:
                                    enviar_notificacion_legible(f"{nom_l} vs {nom_v}", txt_alerta)
                            else:
                                veredicto_en_vivo = f"👀 0-0 en observación ({reloj} - Faltan tiros al arco)"
                        elif goles_tot == 1 and min_num <= 78:
                            if sot_live >= 4 or tiros_live >= 8 or sot_h_l >= 6.5:
                                veredicto_en_vivo = "🔥 METER OVER 1.5 / 2.5 EN VIVO (Partido Roto)"
                                txt_alerta = (
                                    f"⚽ {nom_l} vs {nom_v} ({nombre_liga}) | ⏱️ Minuto {reloj} ({goles_l}-{goles_v}) | "
                                    f"🎯 Tiros al arco: {sot_live} | 👉 VEREDICTO EN VIVO: METER OVER 1.5 / 2.5"
                                )
                                alertas_minuto_18.append(txt_alerta)
                                if tiene_campanita:
                                    enviar_notificacion_legible(f"{nom_l} vs {nom_v}", txt_alerta)
                            else:
                                veredicto_en_vivo = "🟡 1 Gol adentro - Ritmo moderado"
                        elif goles_tot >= 2:
                            veredicto_en_vivo = "✅ OVER 1.5 CUMPLIDO EN CANCHA"
                elif status_type == "pre":
                    veredicto_en_vivo = "⏳ Pendiente de inicio"
                else:
                    veredicto_en_vivo = "🏁 Partido Finalizado"

                partidos_monitoreados.append({
                    "Alerta 🔔": icono_campana,
                    "Reloj / Estado": f"🔴 {reloj}" if status_type == "in" else detalle,
                    "Liga": nombre_liga,
                    "Partido": f"{nom_l} vs {nom_v}",
                    "Marcador": f"{goles_l} - {goles_v}",
                    "🎯 Tiros al Arco (Live)": sot_live,
                    "💥 Disparos Totales": tiros_live,
                    "Perfil Big Data": f"{tag_l} vs {tag_v}",
                    "⚡ VEREDICTO EN VIVO (MIN 18+)": veredicto_en_vivo
                })

    if alertas_minuto_18:
        st.markdown("### 🚨 SEÑALES AUTOMÁTICAS ACTIVAS (MINUTO 18+):")
        for al in alertas_minuto_18:
            st.error(al)
    else:
        st.success("📡 Escáner Minuto 18+ activo en las 19 ligas. En cuanto un partido en juego supere el minuto 18 con presión de tiros, saltará aquí la orden.")

    if partidos_monitoreados:
        st.dataframe(pd.DataFrame(partidos_monitoreados), use_container_width=True, hide_index=True)

    if auto_monitor:
        time.sleep(60)
        st.rerun()
