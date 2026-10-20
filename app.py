import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from scipy.stats import poisson

# Configuración principal con el nuevo nombre MRFUTBOL
st.set_page_config(page_title="MRFUTBOL - Miguel Ramirez", page_icon="⚽", layout="wide")

# Memoria de sesión para que las notificaciones funcionen con 1 solo clic en celular y PC
if "seguidos_portada" not in st.session_state:
    st.session_state["seguidos_portada"] = []
if "memoria_eventos" not in st.session_state:
    st.session_state["memoria_eventos"] = {}
if "historial_notificaciones" not in st.session_state:
    st.session_state["historial_notificaciones"] = []

# Estilos visuales oscuros y limpios
st.markdown("""
<style>
.titulo-mrfutbol {
    text-align: center;
    font-size: 42px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: 3px;
    margin-bottom: 0px;
}
.subtitulo-autor {
    text-align: center;
    font-size: 14px;
    font-weight: 600;
    color: #00ffcc;
    margin-top: 2px;
    margin-bottom: 18px;
    letter-spacing: 1px;
}
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

# CABECERA OFICIAL: MRFUTBOL + TU NOMBRE Y CORREO EN PEQUEÑO PERO VISIBLE
st.markdown("<div class='titulo-mrfutbol'>⚽ MRFUTBOL</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitulo-autor'>Miguel Ramirez &nbsp;|&nbsp; ✉️ angelramirezzmiguel2@gmail.com</div>", unsafe_allow_html=True)

# Función para disparar alerta emergente en pantalla (Celular/PC) + Pitido sonoro
def disparar_alerta_celular(titulo, mensaje, icono="🔔"):
    st.toast(f"**{titulo}**\n\n{mensaje}", icon=icono)
    hora_actual = datetime.now().strftime("%H:%M:%S")
    st.session_state["historial_notificaciones"].insert(0, f"[{hora_actual}] {icono} **{titulo}**: {mensaje}")
    # Sonido corto compatible con navegadores móviles y escritorio
    components.html("""
    <script>
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.25);
    } catch(e) {}
    </script>
    """, height=0)

# =============================================================================
# LAS 19 LIGAS OFICIALES DEL ARCHIVO BIG DATA (.INI) + CHAMPIONS LEAGUE
# =============================================================================
LIGAS_BIG_DATA = [
    {"id": "🏆 Champions League", "espn": "uefa.champions", "efec": "85%"},
    {"id": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League (ING1)", "espn": "eng.1", "efec": "80%"},
    {"id": "🇪🇸 LaLiga (ESP1)", "espn": "esp.1", "efec": "79%"},
    {"id": "🇮🇹 Serie A (ITA1)", "espn": "ita.1", "efec": "81%"},
    {"id": "🇩🇪 Bundesliga (ALE1)", "espn": "ger.1", "efec": "86%"},
    {"id": "🇫🇷 Ligue 1 (FRA1)", "espn": "fra.1", "efec": "80%"},
    {"id": "🇨🇭 Challenge League (SUI2)", "espn": "sui.2", "efec": "91%"},
    {"id": "🇨🇭 Super League (SUI1)", "espn": "sui.1", "efec": "89%"},
    {"id": "🇳🇱 Eredivisie (HOL1)", "espn": "ned.1", "efec": "88%"},
    {"id": "🇳🇱 Eerste Divisie (HOL2)", "espn": "ned.2", "efec": "85%"},
    {"id": "🇳🇴 Eliteserien (NOR1)", "espn": "nor.1", "efec": "87%"},
    {"id": "🇳🇴 1. Division (NOR2)", "espn": "nor.2", "efec": "86%"},
    {"id": "🇩🇪 2. Bundesliga (ALE2)", "espn": "ger.2", "efec": "84%"},
    {"id": "🇦🇹 Bundesliga (AUT1)", "espn": "aut.1", "efec": "84%"},
    {"id": "🇧🇪 Jupiler Pro League (BEL1)", "espn": "bel.1", "efec": "83%"},
    {"id": "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Premiership (ESC1)", "espn": "sco.1", "efec": "83%"},
    {"id": "🇹🇷 Süper Lig (TUR1)", "espn": "tur.1", "efec": "82%"},
    {"id": "🇵🇹 Primeira Liga (POR1)", "espn": "por.1", "efec": "81%"},
    {"id": "🇺🇸 MLS (USA1)", "espn": "usa.1", "efec": "84%"},
    {"id": "🇲🇽 Liga MX (MEX1)", "espn": "mex.1", "efec": "80%"},
]

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

def calcular_grandes_chances(sot, tiros_totales, goles):
    # Extrae o estima matemáticamente las Grandes Chances Creadas y Perdidas según presión al arco
    creadas = max(goles, int(round((sot * 0.55) + (tiros_totales * 0.12))))
    perdidas = max(0, creadas - goles)
    return creadas, perdidas

@st.cache_data(ttl=60)
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
    "⚽ 1. RESULTADOS Y NOTIFICACIONES DE PARTIDO", 
    "🎯 2. PRE-APUESTAS OVER 1.5 (BIG DATA)", 
    "🚨 3. SCRAPING EN VIVO (MIN 18+ CADA 2 MIN)"
])

# -----------------------------------------------------------------------------
# SECCIÓN 1: PORTADA + GRANDES CHANCES PERDIDAS + NOTIFICACIÓN DE EVENTOS (1 CLIC)
# -----------------------------------------------------------------------------
with sec_futbol:
    col_f1, col_f2 = st.columns([2, 2])
    with col_f1:
        modo_ligas_portada = st.radio(
            "Mostrar en Portada:",
            ["⭐ Champions + 5 Grandes Ligas", "🌍 Todas las 19 Ligas del Big Data"],
            horizontal=True
        )
    with col_f2:
        st.markdown("🔔 **Dale clic en `Sí` al lado de cualquier partido** y recibirás alertas automáticas de: **Inicio, Medio Tiempo, Goles, Gol Anulado (VAR), Roja y Final**.")

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
            ev_id = ev.get("id")
            comp = ev.get("competitions", [{}])[0]
            st_state = comp.get("status", {}).get("type", {}).get("state", "pre")
            detalle_corto = comp.get("status", {}).get("type", {}).get("shortDetail", "")
            desc_estado = comp.get("status", {}).get("type", {}).get("description", "")
            reloj = comp.get("status", {}).get("displayClock", "")

            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                loc = competitors[0]
                vis = competitors[1]

                nom_l = loc.get("team", {}).get("shortDisplayName", loc.get("team", {}).get("displayName", "Local"))
                nom_v = vis.get("team", {}).get("shortDisplayName", vis.get("team", {}).get("displayName", "Visita"))
                logo_l = loc.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
                logo_v = vis.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
                gol_l = int(loc.get("score", 0) or 0)
                gol_v = int(vis.get("score", 0) or 0)
                nombre_cruce = f"{nom_l} vs {nom_v}"

                # Contar tarjetas rojas para detector de eventos
                detalles_partido = comp.get("details", [])
                rojas_actuales = sum(1 for d in detalles_partido if d.get("redCard", False))

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

                    # DESPLEGABLE CON GRANDES CHANCES PERDIDAS Y EVENTOS DEL PARTIDO
                    with st.expander(f"📊 Ver qué pasó: Goles, Rojas y Grandes Chances Perdidas ({nombre_cruce})"):
                        eventos_texto = []
                        for d in detalles_partido:
                            min_ev = d.get("clock", {}).get("displayValue", "")
                            tipo_ev = d.get("type", {}).get("text", "")
                            jugadores = d.get("athletesInvolved", [])
                            nom_jug = jugadores[0].get("displayName", "Jugador") if jugadores else ""
                            if d.get("scoringPlay", False):
                                eventos_texto.append(f"⚽ **GOL ({min_ev})**: {nom_jug} ({tipo_ev})")
                            elif d.get("redCard", False):
                                eventos_texto.append(f"🟥 **TARJETA ROJA ({min_ev})**: {nom_jug}")
                            elif d.get("yellowCard", False):
                                eventos_texto.append(f"🟨 **Amarilla ({min_ev})**: {nom_jug}")

                        if eventos_texto:
                            st.markdown("**📋 Incidencias Oficiales (Minuto a Minuto):**")
                            for ev_linea in eventos_texto:
                                st.markdown(f"- {ev_linea}")
                        else:
                            st.caption("Sin goles ni tarjetas registradas hasta el momento.")

                        pos_l = extraer_stat_live(loc, ["possessionPct"])
                        pos_v = extraer_stat_live(vis, ["possessionPct"])
                        sot_l = int(extraer_stat_live(loc, ["shotsOnTarget", "shotsOnGoal"]))
                        sot_v = int(extraer_stat_live(vis, ["shotsOnTarget", "shotsOnGoal"]))
                        tir_l = int(extraer_stat_live(loc, ["totalShots", "shots"]))
                        tir_v = int(extraer_stat_live(vis, ["totalShots", "shots"]))
                        cor_l = int(extraer_stat_live(loc, ["wonCorners", "corners"]))
                        cor_v = int(extraer_stat_live(vis, ["wonCorners", "corners"]))

                        # Cálculo de Grandes Chances Creadas y Perdidas
                        gc_creadas_l, gc_perdidas_l = calcular_grandes_chances(sot_l, tir_l, gol_l)
                        gc_creadas_v, gc_perdidas_v = calcular_grandes_chances(sot_v, tir_v, gol_v)

                        df_stats_partido = pd.DataFrame([
                            {"Estadística del Partido": "🔥 Grandes Chances Creadas", nom_l: gc_creadas_l, nom_v: gc_creadas_v},
                            {"Estadística del Partido": "❌ Grandes Chances Perdidas (Falladas)", nom_l: gc_perdidas_l, nom_v: gc_perdidas_v},
                            {"Estadística del Partido": "🎯 Tiros al Arco (SoT)", nom_l: sot_l, nom_v: sot_v},
                            {"Estadística del Partido": "💥 Disparos Totales", nom_l: tir_l, nom_v: tir_v},
                            {"Estadística del Partido": "🚩 Tiros de Esquina (Córners)", nom_l: cor_l, nom_v: cor_v},
                            {"Estadística del Partido": "⚽ Posesión de Balón", nom_l: f"{pos_l}%", nom_v: f"{pos_v}%"},
                        ])
                        st.table(df_stats_partido)

                with col_bell:
                    ya_seguido = ev_id in st.session_state["seguidos_portada"]
                    activar_si = st.checkbox("🔔 Sí", value=ya_seguido, key=f"portada_bell_{ev_id}")
                    
                    if activar_si and not ya_seguido:
                        st.session_state["seguidos_portada"].append(ev_id)
                        st.session_state["memoria_eventos"][ev_id] = {
                            "state": st_state,
                            "ht_notificado": ("Halftime" in desc_estado or "HT" in detalle_corto),
                            "goles_l": gol_l,
                            "goles_v": gol_v,
                            "rojas": rojas_actuales
                        }
                        disparar_alerta_celular(
                            f"Seguimiento Activado: {nombre_cruce}",
                            "Te avisaremos al instante: Inicio, Medio Tiempo, Goles, Gol Anulado, Rojas y Final.",
                            "✅"
                        )
                    elif not activar_si and ya_seguido:
                        st.session_state["seguidos_portada"].remove(ev_id)

                    # MOTOR DE NOTIFICACIONES DE EVENTOS DEL PARTIDO (SI ESTÁ EN "SÍ")
                    if activar_si and ev_id in st.session_state["memoria_eventos"]:
                        mem = st.session_state["memoria_eventos"][ev_id]
                        
                        # 1. Empezó el partido
                        if mem["state"] == "pre" and st_state == "in":
                            disparar_alerta_celular(f"⏳ ¡EMPEZÓ EL PARTIDO!", f"{nombre_cruce} (0 - 0)", "🟢")
                        
                        # 2. Medio Tiempo (HT)
                        es_ht = ("Halftime" in desc_estado or "HT" in detalle_corto or "Medio" in detalle_corto)
                        if es_ht and not mem["ht_notificado"]:
                            disparar_alerta_celular(f"⏸️ MEDIO TIEMPO", f"{nombre_cruce} | Marcador: {gol_l} - {gol_v}", "⏱️")
                            mem["ht_notificado"] = True

                        # 3. Gol o Gol Anulado (VAR)
                        if (gol_l + gol_v) > (mem["goles_l"] + mem["goles_v"]):
                            disparar_alerta_celular(f"⚽ ¡GOOOOL EN {nombre_cruce}!", f"Nuevo Marcador: {nom_l} {gol_l} - {gol_v} {nom_v} ({reloj})", "⚽")
                        elif (gol_l + gol_v) < (mem["goles_l"] + mem["goles_v"]):
                            disparar_alerta_celular(f"❌ ¡GOL ANULADO (VAR)!", f"Se corrige el marcador en {nombre_cruce}: {gol_l} - {gol_v} ({reloj})", "🚫")

                        # 4. Tarjeta Roja
                        if rojas_actuales > mem["rojas"]:
                            disparar_alerta_celular(f"🟥 ¡TARJETA ROJA!", f"Expulsión en {nombre_cruce} ({reloj}) | Marcador: {gol_l}-{gol_v}", "🟥")

                        # 5. Terminó el partido
                        if mem["state"] != "post" and st_state == "post":
                            disparar_alerta_celular(f"🏁 FINAL DEL PARTIDO", f"{nombre_cruce} terminó {gol_l} - {gol_v}", "🏁")

                        # Actualizar memoria
                        st.session_state["memoria_eventos"][ev_id].update({
                            "state": st_state,
                            "goles_l": gol_l,
                            "goles_v": gol_v,
                            "rojas": rojas_actuales
                        })

    # Bandeja visible de notificaciones caídas en tu celular/PC
    if st.session_state["historial_notificaciones"]:
        with st.expander("📲 Bandeja de Notificaciones Recientes (Eventos y Alertas)", expanded=True):
            for notif in st.session_state["historial_notificaciones"][:8]:
                st.info(notif)

# -----------------------------------------------------------------------------
# SECCIÓN 2: PRE-APUESTAS OVER 1.5 (LAS 19 LIGAS - EXCLUSIVO PRE-PARTIDO)
# -----------------------------------------------------------------------------
with sec_apuestas:
    st.subheader("🎯 Laboratorio de Pre-Apuesta Over 1.5 (Las 19 Ligas Oficiales Big Data)")
    st.markdown("Filtra **únicamente partidos antes de empezar (Pre-Apuesta)** con las reglas de tu archivo `.ini`: **SoT >= 5.5**, **xG/Shot >= 0.12**, **Reyes de Casa vs Coladores** y **Anti-Cerrojo**.")

    opciones_ligas_pre = [l["id"] for l in LIGAS_BIG_DATA]
    ligas_seleccionadas_pre = st.multiselect(
        "📌 Ligas a auditar (Las 19 ligas + Champions activas):",
        options=opciones_ligas_pre,
        default=opciones_ligas_pre
    )

    if st.button("🚀 BUSCAR FIJOS DE PRE-APUESTA OVER 1.5"):
        codigos_pre = [l["espn"] for l in LIGAS_BIG_DATA if l["id"] in ligas_seleccionadas_pre]
        with st.spinner("Cruzando las 19 ligas contra tu base de datos de eficiencia xG/Shot..."):
            datos_pre = obtener_partidos_ligas(codigos_pre, dias=4)
            reporte_pre = []

            for nombre_liga, contenido in datos_pre.items():
                efec_liga = contenido["meta"]["efec"]
                for evento in contenido["eventos"]:
                    comp = evento.get("competitions", [{}])[0]
                    st_state = comp.get("status", {}).get("type", {}).get("state", "pre")

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
                            "Cuota Mín.": cuota_justa,
                            "Regla Big Data": regla_aplicada,
                            "Veredicto Pre-Apuesta": veredicto_pre
                        })

            if reporte_pre:
                st.success(f"✅ {len(reporte_pre)} encuentros auditados para Pre-Apuesta.")
                st.dataframe(pd.DataFrame(reporte_pre), use_container_width=True, hide_index=True)
            else:
                st.info("No hay partidos pendientes por iniciar en este rango.")

# -----------------------------------------------------------------------------
# SECCIÓN 3: SCRAPING EN VIVO DISTINTO (MINUTO 18+ Y REPORTE CADA 2 MINUTOS)
# -----------------------------------------------------------------------------
with sec_live:
    st.subheader("🚨 Scraping en Vivo Automático (Minuto 18+ | Reporte cada 2 Minutos)")
    st.markdown("Este motor es **exclusivo para apuestas en vivo**: monitorea desde el **minuto 18 en adelante** y se actualiza **cada 2 minutos (120 seg)** reportando cómo van los **Disparos, Tiros al Arco, Grandes Chances Creadas y Perdidas**.")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        activar_scraping_2min = st.checkbox("🔄 Activar Notificaciones de Scraping cada 2 Minutos (Min 18+)", value=True)
    with col_s2:
        solo_en_vivo = st.checkbox("🔴 Filtrar tabla solo con partidos En Juego", value=False)

    codigos_todas = [l["espn"] for l in LIGAS_BIG_DATA]
    datos_live_todas = obtener_partidos_ligas(codigos_todas, dias=1)

    tabla_scraping = []
    reportes_minuto_18 = []

    for nombre_liga, contenido in datos_live_todas.items():
        for evento in contenido["eventos"]:
            comp = evento.get("competitions", [{}])[0]
            status_type = comp.get("status", {}).get("type", {}).get("state", "pre")
            reloj = comp.get("status", {}).get("displayClock", "0'")
            detalle = comp.get("status", {}).get("type", {}).get("shortDetail", "Programado")

            if solo_en_vivo and status_type != "in":
                continue

            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                local = competitors[0]
                visita = competitors[1]
                nom_l = local.get("team", {}).get("shortDisplayName", "Local")
                nom_v = visita.get("team", {}).get("shortDisplayName", "Visita")
                goles_l = int(local.get("score", 0) or 0)
                goles_v = int(visita.get("score", 0) or 0)
                goles_tot = goles_l + goles_v

                tiros_l = int(extraer_stat_live(local, ["totalShots", "shots"]))
                tiros_v = int(extraer_stat_live(visita, ["totalShots", "shots"]))
                sot_l = int(extraer_stat_live(local, ["shotsOnTarget", "shotsOnGoal"]))
                sot_v = int(extraer_stat_live(visita, ["shotsOnTarget", "shotsOnGoal"]))

                sot_live = sot_l + sot_v
                tiros_live = tiros_l + tiros_v

                # Grandes Chances en vivo
                gc_creadas_l, gc_perdidas_l = calcular_grandes_chances(sot_l, tiros_l, goles_l)
                gc_creadas_v, gc_perdidas_v = calcular_grandes_chances(sot_v, tiros_v, goles_v)
                gc_totales = gc_creadas_l + gc_creadas_v
                gc_perdidas_tot = gc_perdidas_l + gc_perdidas_v

                sot_h_l, xgs_l, tag_l, col_l, cer_l = auditar_equipo_bd(nom_l)
                sot_h_v, xgs_v, tag_v, col_v, cer_v = auditar_equipo_bd(nom_v)

                min_num = 0
                try:
                    min_num = int(reloj.replace("'", "").split("+")[0])
                except:
                    min_num = 0

                veredicto_scraping = "⏳ Esperando Minuto 18'"
                if status_type == "in":
                    if min_num < 18:
                        veredicto_scraping = f"🕒 Calentando ({reloj} < 18')"
                    else:
                        # A partir del minuto 18 reporta cada 2 minutos cómo van los disparos y grandes chances
                        if goles_tot == 0:
                            if sot_live >= 3 or gc_totales >= 2 or tiros_live >= 6 or sot_h_l >= 6.5 or col_v:
                                veredicto_scraping = "🚨 ¡METER OVER 0.5 HT / 1.5 LIVE! (0-0 con Grandes Chances)"
                                msg_scrap = (
                                    f"⏱️ Min {reloj} | {nom_l} 0-0 {nom_v} ({nombre_liga}) -> "
                                    f"💥 Disparos: {tiros_live} | 🎯 Al Arco: {sot_live} | "
                                    f"🔥 Grandes Chances: {gc_totales} ({gc_perdidas_tot} falladas) -> ¡METER OVER 0.5 / 1.5!"
                                )
                                reportes_minuto_18.append(msg_scrap)
                                disparar_alerta_celular(f"SCRAPING MIN 18+ ({nom_l} vs {nom_v})", msg_scrap, "🚨")
                            else:
                                veredicto_scraping = f"👀 Monitoreando 0-0 ({reloj}) | {tiros_live} disp, {gc_totales} Grandes Chances"
                        elif goles_tot == 1 and min_num <= 78:
                            if sot_live >= 4 or gc_totales >= 3 or tiros_live >= 8:
                                veredicto_scraping = "🔥 ¡METER OVER 1.5 / 2.5 LIVE! (1 Gol y Sigue el Asedio)"
                                msg_scrap = (
                                    f"⏱️ Min {reloj} | {nom_l} {goles_l}-{goles_v} {nom_v} -> "
                                    f"💥 Disparos: {tiros_live} | 🎯 Al Arco: {sot_live} | "
                                    f"🔥 Grandes Chances: {gc_totales} ({gc_perdidas_tot} falladas) -> ¡METER OVER 1.5 / 2.5!"
                                )
                                reportes_minuto_18.append(msg_scrap)
                                disparar_alerta_celular(f"SCRAPING MIN 18+ ({nom_l} vs {nom_v})", msg_scrap, "🔥")
                            else:
                                veredicto_scraping = f"🟢 {goles_l}-{goles_v} ({reloj}) | Ritmo estable"
                        elif goles_tot >= 2:
                            veredicto_scraping = "✅ OVER 1.5 COBRADO"
                elif status_type == "pre":
                    veredicto_scraping = "⏳ Por iniciar"
                else:
                    veredicto_scraping = "🏁 Finalizado"

                tabla_scraping.append({
                    "Reloj": f"🔴 {reloj}" if status_type == "in" else detalle,
                    "Liga": nombre_liga,
                    "Partido": f"{nom_l} vs {nom_v}",
                    "Marcador": f"{goles_l} - {goles_v}",
                    "💥 Disparos": tiros_live,
                    "🎯 Tiros al Arco": sot_live,
                    "🔥 Grandes Chances": gc_totales,
                    "❌ Chances Perdidas": gc_perdidas_tot,
                    "⚡ VEREDICTO SCRAPING (MIN 18+)": veredicto_scraping
                })

    if reportes_minuto_18:
        st.markdown("### 🚨 REPORTES EN VIVO DEL SCRAPING (ACTUALIZADO CADA 2 MINUTOS):")
        for rep in reportes_minuto_18:
            st.error(rep)
    else:
        st.info("📡 Escáner Minuto 18+ activo. Cada 2 minutos audita los disparos y Grandes Chances de los partidos en curso.")

    if tabla_scraping:
        st.dataframe(pd.DataFrame(tabla_scraping), use_container_width=True, hide_index=True)

    # Ciclo exacto de 2 minutos (120 segundos) para el Scraping en vivo
    if activar_scraping_2min:
        time.sleep(120)
        st.rerun()
