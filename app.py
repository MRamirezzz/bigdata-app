import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from scipy.stats import poisson

# Configuración principal con la marca MRFUTBOL
st.set_page_config(page_title="MRFUTBOL - Miguel Ramirez", page_icon="⚽", layout="wide")

if "seguidos_portada" not in st.session_state:
    st.session_state["seguidos_portada"] = []
if "memoria_eventos" not in st.session_state:
    st.session_state["memoria_eventos"] = {}
if "historial_notificaciones" not in st.session_state:
    st.session_state["historial_notificaciones"] = []

# ESTILOS CSS COMPACTOS (ESTILO APP DE ÉLITE / MÓVIL OPTIMIZADO)
st.markdown("""
<style>
.titulo-mrfutbol {
    text-align: center;
    font-size: 32px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: 2px;
    margin-bottom: 0px;
}
.subtitulo-autor {
    text-align: center;
    font-size: 12px;
    font-weight: 600;
    color: #00ffcc;
    margin-top: 1px;
    margin-bottom: 10px;
    letter-spacing: 1px;
}
.liga-header {
    background-color: #16181f;
    color: #00ffcc;
    padding: 6px 12px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 14px;
    border-left: 3px solid #00ffcc;
    margin-top: 10px;
    margin-bottom: 4px;
}
.match-card {
    background-color: #0f1015;
    padding: 6px 10px;
    border-radius: 5px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: #e0e0e0;
    border: 1px solid #1f222d;
    margin-bottom: 3px;
}
.status-badge {
    background-color: #1f222d;
    color: #9ba1b0;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
    min-width: 60px;
    text-align: center;
}
.status-live {
    background-color: #ff2a4b;
    color: #ffffff;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
    min-width: 60px;
    text-align: center;
}
.teams-container {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-grow: 1;
    gap: 8px;
}
.team-home {
    text-align: right;
    width: 40%;
    font-weight: 500;
    font-size: 13px;
}
.team-away {
    text-align: left;
    width: 40%;
    font-weight: 500;
    font-size: 13px;
}
.score-box {
    background-color: #16181f;
    padding: 2px 8px;
    border-radius: 5px;
    font-weight: 700;
    font-size: 13px;
    color: #00ffcc;
    min-width: 55px;
    text-align: center;
}
.team-logo {
    width: 20px;
    height: 20px;
    object-fit: contain;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='titulo-mrfutbol'>⚽ MRFUTBOL</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitulo-autor'>Miguel Ramirez &nbsp;|&nbsp; ✉️ angelramirezzmiguel2@gmail.com</div>", unsafe_allow_html=True)

col_master1, col_master2 = st.columns([3, 1])
with col_master1:
    st.caption("💡 Central de Análisis MRFUTBOL optimizada.")
with col_master2:
    master_sound = st.toggle("🔔 Alertas Activas", value=True)

def disparar_alerta_celular(titulo, mensaje, icono="🔔"):
    if not master_sound:
        return
    st.toast(f"**{titulo}**\n\n{mensaje}", icon=icono)
    hora_actual = (datetime.utcnow() - timedelta(hours=6)).strftime("%H:%M:%S")
    st.session_state["historial_notificaciones"].insert(0, f"[{hora_actual}] {icono} **{titulo}**: {mensaje}")
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
    "Bayern Munich": {"sot": 7.8, "xg_shot": 0.16, "tag": "👑 Rey Casa"},
    "Celtic": {"sot": 8.0, "xg_shot": 0.16, "tag": "👑 Rey Casa"},
    "PSV Eindhoven": {"sot": 7.5, "xg_shot": 0.15, "tag": "👑 Rey Casa"},
    "Barcelona": {"sot": 7.4, "xg_shot": 0.15, "tag": "👑 Rey Casa"},
    "Manchester City": {"sot": 7.2, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "Toluca": {"sot": 6.6, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "Real Madrid": {"sot": 6.8, "xg_shot": 0.15, "tag": "👑 Rey Casa"},
}

def auditar_equipo_bd(nombre_equipo):
    sot_base = 4.8
    xg_shot = 0.11
    etiqueta = "Estándar"
    for k, val in TOP_DISPARADORES.items():
        if k.lower() in nombre_equipo.lower():
            sot_base = val["sot"]
            xg_shot = val["xg_shot"]
            etiqueta = val["tag"]
            break
    return sot_base, xg_shot, etiqueta

def extraer_stat_espn(team_dict, stat_names):
    for st_item in team_dict.get("statistics", []):
        if st_item.get("name") in stat_names:
            try:
                return str(st_item.get("displayValue", "0"))
            except:
                return "0"
    return "0"

def formatear_fecha_local(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (dt - timedelta(hours=6)).strftime("%d/%m %H:%M")
    except:
        return "Programado"

@st.cache_data(ttl=30)
def obtener_partidos_rapido(codigos_espn):
    hoy = datetime.now().strftime("%Y%m%d")
    mapa_ligas = {l["espn"]: l for l in LIGAS_BIG_DATA}
    datos_por_liga = {mapa_ligas[c]["id"]: {"meta": mapa_ligas[c], "eventos": []} for c in codigos_espn if c in mapa_ligas}
    
    for c in codigos_espn:
        if c not in mapa_ligas:
            continue
        liga_obj = mapa_ligas[c]
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{c}/scoreboard?dates={hoy}"
        try:
            res = requests.get(url, timeout=2)
            if res.status_code == 200:
                datos_por_liga[liga_obj["id"]]["eventos"] = res.json().get("events", [])
        except:
            pass
    return datos_por_liga

sec_resultados, sec_en_vivo, sec_apuestas, sec_scraping = st.tabs([
    "⚽ 1. RESULTADOS", 
    "🔴 2. PARTIDOS EN VIVO", 
    "🎯 3. PRE-APUESTAS", 
    "🚨 4. SCRAPING Y ALERTAS"
])

# -----------------------------------------------------------------------------
# SECCIÓN 1: RESULTADOS
# -----------------------------------------------------------------------------
with sec_resultados:
    col_menu, col_contenido = st.columns([1.2, 3.8])
    with col_menu:
        st.markdown("##### 📌 Ligas Disponibles")
        nombres_ligas = [l["id"] for l in LIGAS_BIG_DATA]
        liga_seleccionada_panel = st.selectbox("Filtrar Liga:", ["🌍 Todas las 19 Ligas"] + nombres_ligas, label_visibility="collapsed")
        texto_busqueda = st.text_input("🔍 Buscar Equipo...", "", placeholder="Ej. Real Madrid, Guadalajara...")

    with col_contenido:
        codigos_portada = [l["espn"] for l in LIGAS_BIG_DATA]
        datos_portada = obtener_partidos_rapido(codigos_portada)

        for nombre_liga, contenido in datos_portada.items():
            if liga_seleccionada_panel != "🌍 Todas las 19 Ligas" and liga_seleccionada_panel != nombre_liga:
                continue
            eventos = contenido["eventos"]
            if not eventos:
                continue

            st.markdown(f"<div class='liga-header'>{nombre_liga}</div>", unsafe_allow_html=True)
            for ev in eventos:
                comp = ev.get("competitions", [{}])[0]
                competitors = comp.get("competitors", [])
                if len(competitors) == 2:
                    nom_l = competitors[0].get("team", {}).get("shortDisplayName", "Local")
                    nom_v = competitors[1].get("team", {}).get("shortDisplayName", "Visita")
                    if texto_busqueda and texto_busqueda.lower() not in nom_l.lower() and texto_busqueda.lower() not in nom_v.lower():
                        continue

                    ev_id = ev.get("id")
                    st_state = comp.get("status", {}).get("type", {}).get("state", "pre")
                    reloj = comp.get("status", {}).get("displayClock", "")
                    gol_l = int(competitors[0].get("score", 0) or 0)
                    gol_v = int(competitors[1].get("score", 0) or 0)

                    badge = f"<div class='status-live'>🔴 {reloj}</div>" if st_state == "in" else ("<div class='status-badge'>FINAL</div>" if st_state == "post" else f"<div class='status-badge'>{formatear_fecha_local(ev.get('date', ''))}</div>")
                    score_txt = f"{gol_l} - {gol_v}" if st_state != "pre" else "vs"

                    st.markdown(f"""
                    <div class="match-card">
                        {badge}
                        <div class="teams-container">
                            <div class="team-home">{nom_l}</div>
                            <div class="score-box">{score_txt}</div>
                            <div class="team-away">{nom_v}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SECCIÓN 2: PARTIDOS EN VIVO
# -----------------------------------------------------------------------------
with sec_en_vivo:
    st.subheader("🔴 Partidos en Juego en Tiempo Real")
    codigos_todas = [l["espn"] for l in LIGAS_BIG_DATA]
    datos_vivo = obtener_partidos_rapido(codigos_todas)
    hay_en_vivo = False

    for nombre_liga, contenido in datos_vivo.items():
        for ev in contenido["eventos"]:
            comp = ev.get("competitions", [{}])[0]
            st_state = comp.get("status", {}).get("type", {}).get("state", "pre")
            short_det = comp.get("status", {}).get("type", {}).get("shortDetail", "")
            
            if st_state == "in" or "HT" in short_det or "Medio" in short_det:
                hay_en_vivo = True
                competitors = comp.get("competitors", [])
                if len(competitors) == 2:
                    nom_l = competitors[0].get("team", {}).get("shortDisplayName", "Local")
                    nom_v = competitors[1].get("team", {}).get("shortDisplayName", "Visita")
                    gol_l = int(competitors[0].get("score", 0) or 0)
                    gol_v = int(competitors[1].get("score", 0) or 0)
                    
                    toth_l = int(extraer_stat_espn(competitors[0], ["shots", "totalShots"]) or 0)
                    toth_v = int(extraer_stat_espn(competitors[1], ["shots", "totalShots"]) or 0)
                    tmeta_l = int(extraer_stat_espn(competitors[0], ["shotsOnTarget"]) or 0)
                    tmeta_v = int(extraer_stat_espn(competitors[1], ["shotsOnTarget"]) or 0)

                    st.markdown(f"""
                    <div class="match-card">
                        <div class='status-live'>🔴 En Juego</div>
                        <div class="teams-container">
                            <div class="team-home">{nom_l}</div>
                            <div class="score-box">{gol_l} - {gol_v}</div>
                            <div class="team-away">{nom_v}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"📊 **{nom_l} vs {nom_v}** | Tiros Totales: {toth_l + toth_v} | Al Arco: {tmeta_l + tmeta_v}")

    if not hay_en_vivo:
        st.info("No hay partidos en juego en este momento.")

# -----------------------------------------------------------------------------
# SECCIÓN 3: PRE-APUESTAS (FILTRO FLEXIBLE CON MEJORES CUOTAS)
# -----------------------------------------------------------------------------
with sec_apuestas:
    st.subheader("🎯 Laboratorio de Pre-Apuestas Over 1.5 (Filtro Optimizado)")
    if st.button("🚀 GENERAR REPORTE FLEXIBLE"):
        codigos_pre = [l["espn"] for l in LIGAS_BIG_DATA]
        datos_pre = obtener_partidos_rapido(codigos_pre)
        reporte = []

        for nombre_liga, contenido in datos_pre.items():
            for evento in contenido["eventos"]:
                comp = evento.get("competitions", [{}])[0]
                if comp.get("status", {}).get("type", {}).get("state", "pre") != "pre":
                    continue
                competitors = comp.get("competitors", [])
                if len(competitors) == 2:
                    nom_l = competitors[0].get("team", {}).get("displayName", "Local")
                    nom_v = competitors[1].get("team", {}).get("displayName", "Visita")
                    
                    sot_l, xgs_l, _ = auditar_equipo_bd(nom_l)
                    sot_v, xgs_v, _ = auditar_equipo_bd(nom_v)
                    xg_base = round((sot_l * xgs_l * 1.1) + (sot_v * xgs_v), 2)
                    
                    prob = round((1 - poisson.cdf(1, xg_base)) * 100, 1)
                    # Filtro flexible optimizado: desde 65% para encontrar cuotas más rentables y atractivas
                    if prob >= 65.0:
                        cuota = round(100 / prob, 2)
                        reporte.append({
                            "Liga": nombre_liga,
                            "Partido": f"{nom_l} vs {nom_v}",
                            "Probabilidad Over 1.5": f"{prob}%",
                            "Cuota Estimada": cuota,
                            "Veredicto": "🔥 BUENA CUOTA" if cuota <= 1.55 else "🟢 ENTRAR"
                        })

        if reporte:
            st.dataframe(pd.DataFrame(reporte), use_container_width=True, hide_index=True)
        else:
            st.info("Sin partidos bajo el nuevo rango flexible.")

# -----------------------------------------------------------------------------
# SECCIÓN 4: SCRAPING Y ALERTAS (FLEXIBLE)
# -----------------------------------------------------------------------------
with sec_scraping:
    st.subheader("🚨 Motor de Scraping (Umbral Flexible)")
    codigos_todas = [l["espn"] for l in LIGAS_BIG_DATA]
    datos_scrap = obtener_partidos_rapido(codigos_todas)
    tabla = []

    for nombre_liga, contenido in datos_scrap.items():
        for evento in contenido["eventos"]:
            comp = evento.get("competitions", [{}])[0]
            if comp.get("status", {}).get("type", {}).get("state", "pre") != "in":
                continue
            reloj = comp.get("status", {}).get("displayClock", "0'")
            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                goles = int(competitors[0].get("score", 0) or 0) + int(competitors[1].get("score", 0) or 0)
                toth = int(extraer_stat_espn(competitors[0], ["shots"]) or 0) + int(extraer_stat_espn(competitors[1], ["shots"]) or 0)
                
                try:
                    minuto = int(reloj.replace("'", "").split("+")[0])
                except:
                    minuto = 0

                veredicto = "Esperando..."
                if minuto >= 15:
                    if goles == 0 and toth >= 4:
                        veredicto = "🚨 ¡ENTRAR OVER 0.5!"
                        disparar_alerta_celular("ALERTA VIVA", f"Disparos: {toth} -> Entrar Over 0.5", "🚨")
                    elif goles == 1 and toth >= 6:
                        veredicto = "🔥 ¡ENTRAR OVER 1.5!"
                        disparar_alerta_celular("ALERTA VIVA", f"Disparos: {toth} -> Entrar Over 1.5", "🔥")

                tabla.append({
                    "Reloj": reloj,
                    "Partido": f"{competitors[0].get('team', {}).get('shortDisplayName')} vs {competitors[1].get('team', {}).get('shortDisplayName')}",
                    "Goles": goles,
                    "Disparos Totales": toth,
                    "Señal": veredicto
                })

    if tabla:
        st.dataframe(pd.DataFrame(tabla), use_container_width=True, hide_index=True)
    else:
        st.info("Sin partidos activos para el motor de scraping en este momento.")
