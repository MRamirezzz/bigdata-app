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

# ENCABEZADO OFICIAL COMPACTO
st.markdown("<div class='titulo-mrfutbol'>⚽ MRFUTBOL</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitulo-autor'>Miguel Ramirez &nbsp;|&nbsp; ✉️ angelramirezzmiguel2@gmail.com</div>", unsafe_allow_html=True)

# Barra de control general de alertas (Interruptor Maestro)
col_master1, col_master2 = st.columns([3, 1])
with col_master1:
    st.caption("💡 Panel compacto optimizado para móviles y PC.")
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

def extraer_stat_espn(team_dict, stat_names):
    for st_item in team_dict.get("statistics", []):
        if st_item.get("name") in stat_names:
            try:
                val = st_item.get("displayValue", "0")
                return str(val)
            except:
                return "0"
    return "0"

def formatear_fecha_local(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_local = dt - timedelta(hours=6)
        return dt_local.strftime("%d/%m %H:%M")
    except:
        return "Programado"

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
    "⚽ 1. RESULTADOS", 
    "🎯 2. PRE-APUESTAS", 
    "🚨 3. SCRAPING EN VIVO"
])

# -----------------------------------------------------------------------------
# SECCIÓN 1: PORTADA COMPACTA + FILTRO LATERAL DE LIGAS + BUSCADOR
# -----------------------------------------------------------------------------
with sec_futbol:
    col_menu, col_contenido = st.columns([1.2, 3.8])

    # PANEL LATERAL IZQUIERDO: SELECCIÓN RÁPIDA DE LIGAS (ESTILO APP DE ÉLITE)
    with col_menu:
        st.markdown("##### 📌 Ligas Disponibles")
        nombres_ligas = [l["id"] for l in LIGAS_BIG_DATA]
        liga_seleccionada_panel = st.selectbox("Filtrar Liga:", ["🌍 Todas las 19 Ligas"] + nombres_ligas, label_visibility="collapsed")
        texto_busqueda = st.text_input("🔍 Buscar Equipo...", "", placeholder="Ej. Real Madrid, PSV...")

    # PANEL DERECHO: TARJETAS COMPACTAS DE RESULTADOS
    with col_contenido:
        codigos_portada = [l["espn"] for l in LIGAS_BIG_DATA]
        datos_portada = obtener_partidos_ligas(codigos_portada, dias=4)

        for nombre_liga, contenido in datos_portada.items():
            if liga_seleccionada_panel != "🌍 Todas las 19 Ligas" and liga_seleccionada_panel != nombre_liga:
                continue

            eventos = contenido["eventos"]
            if not eventos:
                continue

            eventos_filtrados = []
            for ev in eventos:
                comp = ev.get("competitions", [{}])[0]
                competitors = comp.get("competitors", [])
                if len(competitors) == 2:
                    nom_l = competitors[0].get("team", {}).get("displayName", "")
                    nom_v = competitors[1].get("team", {}).get("displayName", "")
                    if not texto_busqueda or (texto_busqueda.lower() in nom_l.lower() or texto_busqueda.lower() in nom_v.lower()):
                        eventos_filtrados.append(ev)

            if not eventos_filtrados:
                continue

            st.markdown(f"<div class='liga-header'>{nombre_liga}</div>", unsafe_allow_html=True)

            for ev in eventos_filtrados:
                ev_id = ev.get("id")
                comp = ev.get("competitions", [{}])[0]
                st_state = comp.get("status", {}).get("type", {}).get("state", "pre")
                desc_estado = comp.get("status", {}).get("type", {}).get("description", "")
                reloj = comp.get("status", {}).get("displayClock", "")
                iso_fecha = ev.get("date", "")

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

                    detalles_partido = comp.get("details", [])
                    rojas_actuales = sum(1 for d in detalles_partido if d.get("redCard", False))

                    if st_state == "in":
                        badge_html = f"<div class='status-live'>🔴 {reloj}</div>"
                        centro_html = f"{gol_l} - {gol_v}"
                    elif st_state == "post":
                        badge_html = "<div class='status-badge'>FINAL</div>"
                        centro_html = f"{gol_l} - {gol_v}"
                    else:
                        fecha_legible = formatear_fecha_local(iso_fecha)
                        badge_html = f"<div class='status-badge'>{fecha_legible}</div>"
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

                        with st.expander(f"📊 Resumen Clave ({nombre_cruce})"):
                            eventos_texto = []
                            for d in detalles_partido:
                                min_ev = d.get("clock", {}).get("displayValue", "")
                                tipo_ev = d.get("type", {}).get("text", "")
                                jugadores = d.get("athletesInvolved", [])
                                nom_jug = jugadores[0].get("displayName", "Jugador") if jugadores else ""
                                if d.get("scoringPlay", False):
                                    eventos_texto.append(f"⚽ **GOL ({min_ev})**: {nom_jug} ({tipo_ev})")
                                elif d.get("redCard", False):
                                    eventos_texto.append(f"🟥 **ROJA ({min_ev})**: {nom_jug}")
                                elif d.get("yellowCard", False):
                                    eventos_texto.append(f"🟨 **Amarilla ({min_ev})**: {nom_jug}")

                            if eventos_texto:
                                for ev_linea in eventos_texto:
                                    st.markdown(f"- {ev_linea}")
                            else:
                                st.caption("Sin goles ni tarjetas registradas.")

                            pos_l = extraer_stat_espn(loc, ["possessionPct"])
                            pos_v = extraer_stat_espn(vis, ["possessionPct"])
                            esquinas_l = extraer_stat_espn(loc, ["wonCorners", "corners"])
                            esquinas_v = extraer_stat_espn(vis, ["wonCorners", "corners"])

                            df_resumen = pd.DataFrame([
                                {"Dato": "Posesión", nom_l: f"{pos_l}%" if "%" not in pos_l else pos_l, nom_v: f"{pos_v}%" if "%" not in pos_v else pos_v},
                                {"Dato": "Córneres", nom_l: esquinas_l, nom_v: esquinas_v},
                            ])
                            st.table(df_resumen)

                    with col_bell:
                        ya_seguido = ev_id in st.session_state["seguidos_portada"]
                        activar_si = st.checkbox("🔔 Sí", value=ya_seguido, key=f"portada_bell_{ev_id}")
                        
                        if activar_si and not ya_seguido:
                            st.session_state["seguidos_portada"].append(ev_id)
                            st.session_state["memoria_eventos"][ev_id] = {
                                "state": st_state,
                                "ht_notificado": ("Halftime" in desc_estado or "HT" in comp.get("status", {}).get("type", {}).get("shortDetail", "")),
                                "goles_l": gol_l,
                                "goles_v": gol_v,
                                "rojas": rojas_actuales
                            }
                            disparar_alerta_celular(f"Seguimiento: {nombre_cruce}", "Avisos activos.", "✅")
                        elif not activar_si and ya_seguido:
                            st.session_state["seguidos_portada"].remove(ev_id)

                        if activar_si and ev_id in st.session_state["memoria_eventos"]:
                            mem = st.session_state["memoria_eventos"][ev_id]
                            if mem["state"] == "pre" and st_state == "in":
                                disparar_alerta_celular(f"⏳ ¡EMPEZÓ!", f"{nombre_cruce} (0-0)", "🟢")
                            
                            es_ht = ("Halftime" in desc_estado or "HT" in comp.get("status", {}).get("type", {}).get("shortDetail", "") or "Medio" in desc_estado)
                            if es_ht and not mem["ht_notificado"]:
                                disparar_alerta_celular(f"⏸️ MEDIO TIEMPO", f"{nombre_cruce} | {gol_l}-{gol_v}", "⏱️")
                                mem["ht_notificado"] = True

                            if (gol_l + gol_v) > (mem["goles_l"] + mem["goles_v"]):
                                disparar_alerta_celular(f"⚽ ¡GOL!", f"{nombre_cruce}: {gol_l}-{gol_v}", "⚽")
                            elif (gol_l + gol_v) < (mem["goles_l"] + mem["goles_v"]):
                                disparar_alerta_celular(f"❌ ¡GOL ANULADO (VAR)!", f"{nombre_cruce}: {gol_l}-{gol_v}", "🚫")

                            if rojas_actuales > mem["rojas"]:
                                disparar_alerta_celular(f"🟥 ¡ROJA!", f"{nombre_cruce}", "🟥")

                            if mem["state"] != "post" and st_state == "post":
                                disparar_alerta_celular(f"🏁 FINAL", f"{nombre_cruce} terminó {gol_l}-{gol_v}", "🏁")

                            st.session_state["memoria_eventos"][ev_id].update({
                                "state": st_state,
                                "goles_l": gol_l,
                                "goles_v": gol_v,
                                "rojas": rojas_actuales
                            })

    if st.session_state["historial_notificaciones"]:
        with st.expander("📲 Bandeja de Notificaciones", expanded=False):
            for notif in st.session_state["historial_notificaciones"][:6]:
                st.info(notif)

# -----------------------------------------------------------------------------
# SECCIÓN 2: PRE-APUESTAS OVER 1.5 (COMPACTO)
# -----------------------------------------------------------------------------
with sec_apuestas:
    st.subheader("🎯 Pre-Apuesta Over 1.5 (Big Data)")
    opciones_ligas_pre = [l["id"] for l in LIGAS_BIG_DATA]
    ligas_seleccionadas_pre = st.multiselect("Ligas a auditar:", options=opciones_ligas_pre, default=opciones_ligas_pre)

    if st.button("🚀 GENERAR REPORTE PRE-APUESTA"):
        codigos_pre = [l["espn"] for l in LIGAS_BIG_DATA if l["id"] in ligas_seleccionadas_pre]
        with st.spinner("Analizando..."):
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
                        fecha_str = formatear_fecha_local(evento.get("date", ""))

                        sot_l, xgs_l, tag_l, col_l, cer_l = auditar_equipo_bd(nom_local)
                        sot_v, xgs_v, tag_v, col_v, cer_v = auditar_equipo_bd(nom_visita)
                        xg_base = round((sot_l * xgs_l * 1.2) + (sot_v * xgs_v), 2)
                        
                        if cer_l or cer_v:
                            xg_base = max(1.35, xg_base - 0.55)

                        prob_poisson = (1 - poisson.cdf(1, xg_base)) * 100
                        prob_final = round(min(98.5, max(45.0, prob_poisson)), 1)
                        cuota_justa = round(100 / prob_final, 2)
                        veredicto = "🟢 METER FICHA" if prob_final >= 78 else "⚪ DESCARTAR"

                        reporte_pre.append({
                            "Fecha": fecha_str,
                            "Liga": nombre_liga,
                            "Partido": f"{nom_local} vs {nom_visita}",
                            "Prob. Over 1.5": f"{prob_final}%",
                            "Cuota": cuota_justa,
                            "Veredicto": veredicto
                        })

            if reporte_pre:
                st.dataframe(pd.DataFrame(reporte_pre), use_container_width=True, hide_index=True)
            else:
                st.info("Sin partidos pendientes.")

# -----------------------------------------------------------------------------
# SECCIÓN 3: SCRAPING EN VIVO (MINUTO 18+)
# -----------------------------------------------------------------------------
with sec_live:
    st.subheader("🚨 Scraping En Vivo (Minuto 18+)")
    activar_scraping_2min = st.checkbox("🔄 Actualizar cada 2 minutos", value=True)

    codigos_todas = [l["espn"] for l in LIGAS_BIG_DATA]
    datos_live_todas = obtener_partidos_ligas(codigos_todas, dias=1)
    tabla_scraping = []

    for nombre_liga, contenido in datos_live_todas.items():
        for evento in contenido["eventos"]:
            comp = evento.get("competitions", [{}])[0]
            status_type = comp.get("status", {}).get("type", {}).get("state", "pre")
            reloj = comp.get("status", {}).get("displayClock", "0'")

            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                local = competitors[0]
                visita = competitors[1]
                nom_l = local.get("team", {}).get("shortDisplayName", "Local")
                nom_v = visita.get("team", {}).get("shortDisplayName", "Visita")
                goles_tot = int(local.get("score", 0) or 0) + int(visita.get("score", 0) or 0)
                tmeta = int(extraer_stat_espn(local, ["shotsOnTarget"]) or 0) + int(extraer_stat_espn(visita, ["shotsOnTarget"]) or 0)

                min_num = 0
                try:
                    min_num = int(reloj.replace("'", "").split("+")[0])
                except:
                    min_num = 0

                veredicto = "Esperando Min 18'"
                if status_type == "in" and min_num >= 18 and goles_tot == 0 and tmeta >= 3:
                    veredicto = "🚨 ¡METER OVER 0.5 / 1.5!"
                    disparar_alerta_celular(f"SCRAPING LIVE ({nom_l} vs {nom_v})", f"Min {reloj} | Tiros meta: {tmeta}", "🚨")

                tabla_scraping.append({
                    "Reloj": f"🔴 {reloj}" if status_type == "in" else "Programado",
                    "Liga": nombre_liga,
                    "Partido": f"{nom_l} vs {nom_v}",
                    "Tiros a Meta": tmeta,
                    "Veredicto": veredicto
                })

    if tabla_scraping:
        st.dataframe(pd.DataFrame(tabla_scraping), use_container_width=True, hide_index=True)

    if activar_scraping_2min:
        time.sleep(120)
        st.rerun()
