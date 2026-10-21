import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor
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

# ESTILOS CSS COMPACTOS (OPTIMIZADO PARA MÓVIL Y PC)
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
    min-width: 72px;
    text-align: center;
}
.status-live {
    background-color: #ff2a4b;
    color: #ffffff;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
    min-width: 72px;
    text-align: center;
}
.status-ht {
    background-color: #ff9800;
    color: #000000;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 800;
    min-width: 72px;
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

# ENCABEZADO OFICIAL MRFUTBOL
st.markdown("<div class='titulo-mrfutbol'>⚽ MRFUTBOL</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitulo-autor'>Miguel Ramirez &nbsp;|&nbsp; ✉️ angelramirezzmiguel2@gmail.com</div>", unsafe_allow_html=True)

col_master1, col_master2, col_master3 = st.columns([2.5, 1, 1])
with col_master1:
    st.caption("💡 Central de Inteligencia y Algoritmo en Vivo MRFUTBOL.")
with col_master2:
    master_sound = st.toggle("🔔 Alertas Activas", value=True)
with col_master3:
    auto_refresh = st.toggle("🔄 Auto-Refresco (2m)", value=True)

def disparar_alerta_celular(titulo, mensaje, icono="🔔"):
    if not master_sound:
        return
    hora_actual = (datetime.utcnow() - timedelta(hours=6)).strftime("%H:%M:%S")
    registro = f"[{hora_actual}] {icono} **{titulo}**: {mensaje}"
    # Evitar duplicar exactamente la misma alerta en el mismo minuto
    if not st.session_state["historial_notificaciones"] or st.session_state["historial_notificaciones"][0] != registro:
        st.toast(f"**{titulo}**\n\n{mensaje}", icon=icono)
        st.session_state["historial_notificaciones"].insert(0, registro)
        components.html("""
        <script>
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, ctx.currentTime);
            gain.gain.setValueAtTime(0.12, ctx.currentTime);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.3);
        } catch(e) {}
        </script>
        """, height=0)

# =============================================================================
# LAS 19 LIGAS OFICIALES DEL ARCHIVO BIG DATA (.INI) + CHAMPIONS LEAGUE
# =============================================================================
LIGAS_BIG_DATA = [
    {"id": "🏆 Champions League", "code": "uefa.champions", "efec": "85%"},
    {"id": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League (ING1)", "code": "eng.1", "efec": "80%"},
    {"id": "🇪🇸 LaLiga (ESP1)", "code": "esp.1", "efec": "79%"},
    {"id": "🇮🇹 Serie A (ITA1)", "code": "ita.1", "efec": "81%"},
    {"id": "🇩🇪 Bundesliga (ALE1)", "code": "ger.1", "efec": "86%"},
    {"id": "🇫🇷 Ligue 1 (FRA1)", "code": "fra.1", "efec": "80%"},
    {"id": "🇨🇭 Challenge League (SUI2)", "code": "sui.2", "efec": "91%"},
    {"id": "🇨🇭 Super League (SUI1)", "code": "sui.1", "efec": "89%"},
    {"id": "🇳🇱 Eredivisie (HOL1)", "code": "ned.1", "efec": "88%"},
    {"id": "🇳🇱 Eerste Divisie (HOL2)", "code": "ned.2", "efec": "85%"},
    {"id": "🇳🇴 Eliteserien (NOR1)", "code": "nor.1", "efec": "87%"},
    {"id": "🇳🇴 1. Division (NOR2)", "code": "nor.2", "efec": "86%"},
    {"id": "🇩🇪 2. Bundesliga (ALE2)", "code": "ger.2", "efec": "84%"},
    {"id": "🇦🇹 Bundesliga (AUT1)", "code": "aut.1", "efec": "84%"},
    {"id": "🇧🇪 Jupiler Pro League (BEL1)", "code": "bel.1", "efec": "83%"},
    {"id": "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Premiership (ESC1)", "code": "sco.1", "efec": "83%"},
    {"id": "🇹🇷 Süper Lig (TUR1)", "code": "tur.1", "efec": "82%"},
    {"id": "🇵🇹 Primeira Liga (POR1)", "code": "por.1", "efec": "81%"},
    {"id": "🇺🇸 MLS (USA1)", "code": "usa.1", "efec": "84%"},
    {"id": "🇲🇽 Liga MX (MEX1)", "code": "mex.1", "efec": "80%"},
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
    "Guadalajara": {"sot": 5.8, "xg_shot": 0.13, "tag": "⚡ Ofensivo Local"},
    "Cruz Azul": {"sot": 6.2, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "America": {"sot": 6.3, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "Monterrey": {"sot": 6.0, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Tigres": {"sot": 5.9, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
}

DEFENSAS_COLADOR = [
    "Baden", "Schaffhausen", "Yverdon", "Grasshopper", "Waalwijk", "Almere City",
    "TOP Oss", "Jong Utrecht", "Sandefjord", "Haugesund", "Levanger", "Raufoss",
    "Bochum", "Augsburg", "Braunschweig", "Regensburg", "Tirol", "Blau-Weiss Linz",
    "Southampton", "Ipswich", "Leicester", "Kortrijk", "Eupen", "Ross County",
    "St. Johnstone", "Hatayspor", "Konyaspor", "Estrela", "Farense", "San Jose",
    "Chicago Fire", "Hellas Verona", "Venezia", "Angers", "Saint-Etienne",
    "Espanyol", "Valladolid", "Puebla", "Mazatlan", "Santos", "Necaxa", "Juarez"
]

BLOQUES_CERROJO = ["Getafe", "Mallorca", "Empoli", "Everton"]

def auditar_equipo_bd(nombre_equipo):
    sot_base = 4.9
    xg_shot = 0.115
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
            etiqueta = "🧱 Bloque Bajo"
            break

    return sot_base, xg_shot, etiqueta, es_colador, es_cerrojo

def calcular_pre_poisson(nom_local, nom_visita):
    sot_l, xgs_l, tag_l, col_l, cer_l = auditar_equipo_bd(nom_local)
    sot_v, xgs_v, tag_v, col_v, cer_v = auditar_equipo_bd(nom_visita)
    
    # Bono ofensivo si enfrenta a una Defensa Colador
    bono_colador = 0.35 if (col_l or col_v) else 0.0
    xg_base = round((sot_l * xgs_l * 1.18) + (sot_v * xgs_v) + bono_colador, 2)
    
    if cer_l or cer_v:
        xg_base = max(1.30, xg_base - 0.35)

    prob_poisson = (1 - poisson.cdf(1, xg_base)) * 100
    prob_final = round(min(96.0, max(45.0, prob_poisson)), 1)
    cuota_justa = round(100 / prob_final, 2)
    return prob_final, cuota_justa, xg_base, f"{tag_l} vs {tag_v}"

def extraer_stat(team_dict, stat_names):
    for st_item in team_dict.get("statistics", []):
        if st_item.get("name") in stat_names:
            try:
                val = st_item.get("displayValue", "0").replace("%", "").strip()
                return float(val) if "." in val else int(val)
            except:
                return 0
    return 0

def extraer_metricas_partido(loc, vis):
    toth_l = int(extraer_stat(loc, ["totalShots", "shots"]))
    toth_v = int(extraer_stat(vis, ["totalShots", "shots"]))
    
    tmeta_l = int(extraer_stat(loc, ["shotsOnTarget", "shotsOnGoal"]))
    tmeta_v = int(extraer_stat(vis, ["shotsOnTarget", "shotsOnGoal"]))
    
    esquinas_l = int(extraer_stat(loc, ["wonCorners", "corners", "cornerKicks"]))
    esquinas_v = int(extraer_stat(vis, ["wonCorners", "corners", "cornerKicks"]))
    
    pos_l = extraer_stat(loc, ["possessionPct"])
    pos_v = extraer_stat(vis, ["possessionPct"])
    
    # Cálculo de Ocasiones Claras (remates francos al arco + presión de tiros/córneres)
    claras_raw_l = int(extraer_stat(loc, ["bigChances", "bigChancesCreated", "shotsInsideBox"]))
    claras_raw_v = int(extraer_stat(vis, ["bigChances", "bigChancesCreated", "shotsInsideBox"]))
    
    claras_l = claras_raw_l if claras_raw_l > 0 else max(0, int(round(tmeta_l * 0.65 + max(0, toth_l - tmeta_l) * 0.22 + esquinas_l * 0.1)))
    claras_v = claras_raw_v if claras_raw_v > 0 else max(0, int(round(tmeta_v * 0.65 + max(0, toth_v - tmeta_v) * 0.22 + esquinas_v * 0.1)))
    
    return {
        "toth_l": toth_l, "toth_v": toth_v, "toth_tot": toth_l + toth_v,
        "tmeta_l": tmeta_l, "tmeta_v": tmeta_v, "tmeta_tot": tmeta_l + tmeta_v,
        "claras_l": claras_l, "claras_v": claras_v, "claras_tot": claras_l + claras_v,
        "esquinas_l": esquinas_l, "esquinas_v": esquinas_v,
        "pos_l": pos_l, "pos_v": pos_v
    }

def detectar_estado_partido(comp, iso_fecha):
    status_obj = comp.get("status", {})
    type_obj = status_obj.get("type", {})
    st_state = type_obj.get("state", "pre")
    st_name = type_obj.get("name", "").upper()
    short_det = type_obj.get("shortDetail", "").upper()
    desc_det = type_obj.get("description", "").upper()
    reloj = status_obj.get("displayClock", "0'")

    es_ht = (
        "HALFTIME" in st_name or 
        "HT" in short_det or 
        "HALFTIME" in desc_det or 
        "MEDIO" in short_det or 
        "DESCANSO" in desc_det
    )

    min_num = 0
    try:
        min_num = int(reloj.replace("'", "").split("+")[0])
    except:
        min_num = 45 if es_ht else 0

    if es_ht:
        badge_html = "<div class='status-ht'>⏸️ ENTRETIEMPO</div>"
        reloj_txt = "⏸️ HT (45')"
    elif st_state == "in":
        badge_html = f"<div class='status-live'>🔴 {reloj}</div>"
        reloj_txt = f"🔴 {reloj}"
    elif st_state == "post":
        badge_html = "<div class='status-badge'>FINAL</div>"
        reloj_txt = "FINAL"
    else:
        try:
            dt = datetime.fromisoformat(iso_fecha.replace("Z", "+00:00")) - timedelta(hours=6)
            fecha_legible = dt.strftime("%d/%m %H:%M")
        except:
            fecha_legible = "Programado"
        badge_html = f"<div class='status-badge'>{fecha_legible}</div>"
        reloj_txt = fecha_legible

    return st_state, es_ht, min_num, badge_html, reloj_txt

# DESCARGA PARALELA ULTRARRÁPIDA (EVITA CAÍDAS Y BLOQUEOS EN LAS PESTAÑAS)
def _fetch_url(args):
    code, f_str = args
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={f_str}"
    try:
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            return code, res.json().get("events", [])
    except:
        pass
    return code, []

@st.cache_data(ttl=20)
def obtener_partidos_ligas(codigos_liga):
    hoy_hn = datetime.utcnow() - timedelta(hours=6)
    fechas = [(hoy_hn + timedelta(days=i)).strftime("%Y%m%d") for i in (-1, 0, 1)]
    mapa_ligas = {l["code"]: l for l in LIGAS_BIG_DATA}
    datos_por_liga = {mapa_ligas[c]["id"]: {"meta": mapa_ligas[c], "eventos": []} for c in codigos_liga if c in mapa_ligas}
    ids_vistos = set()

    tareas = [(c, f_str) for c in codigos_liga if c in mapa_ligas for f_str in fechas]
    with ThreadPoolExecutor(max_workers=16) as executor:
        resultados = list(executor.map(_fetch_url, tareas))

    for code, eventos in resultados:
        liga_id = mapa_ligas[code]["id"]
        for ev in eventos:
            ev_id = ev.get("id")
            if ev_id and ev_id not in ids_vistos:
                ids_vistos.add(ev_id)
                datos_por_liga[liga_id]["eventos"].append(ev)

    return datos_por_liga

# =============================================================================
# DATOS GLOBALES Y ESTRUCTURA DE LAS 4 PESTAÑAS
# =============================================================================
codigos_todas = [l["code"] for l in LIGAS_BIG_DATA]
datos_globales = obtener_partidos_ligas(codigos_todas)

sec_resultados, sec_en_vivo, sec_apuestas, sec_scraping = st.tabs([
    "⚽ 1. RESULTADOS", 
    "🔴 2. PARTIDOS EN VIVO", 
    "🎯 3. PRE-APUESTAS", 
    "🚨 4. SCRAPING Y ALERTAS"
])

# -----------------------------------------------------------------------------
# SECCIÓN 1: RESULTADOS GENERALES Y CAMPANITA DE SEGUIMIENTO
# -----------------------------------------------------------------------------
with sec_resultados:
    col_menu, col_contenido = st.columns([1.2, 3.8])

    with col_menu:
        st.markdown("##### 📌 Ligas Disponibles")
        nombres_ligas = [l["id"] for l in LIGAS_BIG_DATA]
        liga_seleccionada_panel = st.selectbox("Filtrar Liga:", ["🌍 Todas las Ligas"] + nombres_ligas, label_visibility="collapsed")
        texto_busqueda = st.text_input("🔍 Buscar Equipo...", "", placeholder="Ej. Real Madrid, Guadalajara...")
        if st.button("🔄 Refrescar Marcadores", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with col_contenido:
        for nombre_liga, contenido in datos_globales.items():
            if liga_seleccionada_panel != "🌍 Todas las Ligas" and liga_seleccionada_panel != nombre_liga:
                continue

            eventos_filtrados = []
            for ev in contenido["eventos"]:
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
                ev_id = str(ev.get("id"))
                comp = ev.get("competitions", [{}])[0]
                competitors = comp.get("competitors", [])
                if len(competitors) != 2:
                    continue

                loc, vis = competitors[0], competitors[1]
                nom_l = loc.get("team", {}).get("shortDisplayName", loc.get("team", {}).get("displayName", "Local"))
                nom_v = vis.get("team", {}).get("shortDisplayName", vis.get("team", {}).get("displayName", "Visita"))
                logo_l = loc.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
                logo_v = vis.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
                gol_l = int(loc.get("score", 0) or 0)
                gol_v = int(vis.get("score", 0) or 0)
                nombre_cruce = f"{nom_l} vs {nom_v}"

                st_state, es_ht, min_num, badge_html, _ = detectar_estado_partido(comp, ev.get("date", ""))
                centro_html = f"{gol_l} - {gol_v}" if (st_state != "pre" or es_ht) else "vs"

                detalles_partido = comp.get("details", [])
                rojas_actuales = sum(1 for d in detalles_partido if d.get("redCard", False))
                stats = extraer_metricas_partido(loc, vis)

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

                    with st.expander(f"📊 Resumen Clave ({nombre_cruce})", expanded=False):
                        df_resumen = pd.DataFrame([
                            {"Métrica": "🎯 Disparos Totales", nom_l: stats["toth_l"], nom_v: stats["toth_v"]},
                            {"Métrica": "🥅 Tiros al Arco", nom_l: stats["tmeta_l"], nom_v: stats["tmeta_v"]},
                            {"Métrica": "🔥 Ocasiones Claras", nom_l: stats["claras_l"], nom_v: stats["claras_v"]},
                            {"Métrica": "⏱️ Posesión", nom_l: f"{stats['pos_l']}%", nom_v: f"{stats['pos_v']}%"},
                            {"Métrica": "🚩 Córneres", nom_l: stats["esquinas_l"], nom_v: stats["esquinas_v"]},
                        ])
                        st.dataframe(df_resumen, use_container_width=True, hide_index=True, key=f"tbl_res_{ev_id}")

                        eventos_texto = []
                        for d in detalles_partido:
                            min_ev = d.get("clock", {}).get("displayValue", "")
                            jugadores = d.get("athletesInvolved", [])
                            nom_jug = jugadores[0].get("displayName", "Jugador") if jugadores else ""
                            if d.get("scoringPlay", False):
                                eventos_texto.append(f"⚽ **GOL ({min_ev})**: {nom_jug}")
                            elif d.get("redCard", False):
                                eventos_texto.append(f"🟥 **ROJA ({min_ev})**: {nom_jug}")
                            elif d.get("yellowCard", False):
                                eventos_texto.append(f"🟨 **Amarilla ({min_ev})**: {nom_jug}")

                        if eventos_texto:
                            for ev_linea in eventos_texto:
                                st.markdown(f"- {ev_linea}")
                        else:
                            st.caption("Sin goles ni tarjetas registradas en este partido.")

                with col_bell:
                    ya_seguido = ev_id in st.session_state["seguidos_portada"]
                    activar_si = st.checkbox("🔔 Sí", value=ya_seguido, key=f"portada_bell_{ev_id}")

                    if activar_si and not ya_seguido:
                        st.session_state["seguidos_portada"].append(ev_id)
                        st.session_state["memoria_eventos"][ev_id] = {
                            "state": st_state,
                            "ht_notificado": es_ht,
                            "goles_l": gol_l,
                            "goles_v": gol_v,
                            "rojas": rojas_actuales
                        }
                        disparar_alerta_celular(f"Seguimiento: {nombre_cruce}", "Alertas activadas para este partido.", "✅")
                    elif not activar_si and ya_seguido:
                        st.session_state["seguidos_portada"].remove(ev_id)

                    if activar_si and ev_id in st.session_state["memoria_eventos"]:
                        mem = st.session_state["memoria_eventos"][ev_id]
                        if mem["state"] == "pre" and st_state == "in":
                            disparar_alerta_celular("⏳ ¡ARRANCÓ EL PARTIDO!", f"{nombre_cruce} (0-0)", "🟢")
                        if es_ht and not mem["ht_notificado"]:
                            disparar_alerta_celular("⏸️ ENTRETIEMPO (HT)", f"{nombre_cruce} | Marcador: {gol_l}-{gol_v}", "⏱️")
                            mem["ht_notificado"] = True
                        if (gol_l + gol_v) > (mem["goles_l"] + mem["goles_v"]):
                            disparar_alerta_celular(f"⚽ ¡GOL EN {nombre_cruce}!", f"Nuevo marcador: {gol_l}-{gol_v}", "⚽")
                        elif (gol_l + gol_v) < (mem["goles_l"] + mem["goles_v"]):
                            disparar_alerta_celular("❌ ¡GOL ANULADO (VAR)!", f"{nombre_cruce} vuelve a {gol_l}-{gol_v}", "🚫")
                        if rojas_actuales > mem["rojas"]:
                            disparar_alerta_celular("🟥 ¡TARJETA ROJA!", f"Expulsión en {nombre_cruce}", "🟥")
                        if mem["state"] != "post" and st_state == "post":
                            disparar_alerta_celular("🏁 FINAL DEL PARTIDO", f"{nombre_cruce} terminó {gol_l}-{gol_v}", "🏁")

                        st.session_state["memoria_eventos"][ev_id].update({
                            "state": st_state,
                            "goles_l": gol_l,
                            "goles_v": gol_v,
                            "rojas": rojas_actuales
                        })

    if st.session_state["historial_notificaciones"]:
        with st.expander("📲 Bandeja de Alertas Recientes", expanded=False):
            for notif in st.session_state["historial_notificaciones"][:8]:
                st.info(notif)

# -----------------------------------------------------------------------------
# SECCIÓN 2: PARTIDOS EN VIVO (PANTALLA EXCLUSIVA CON MÉTRICAS COMPLETAS)
# -----------------------------------------------------------------------------
with sec_en_vivo:
    st.subheader("🔴 Partidos en Vivo y Entretiempo")
    st.caption("Visualización limpia de todos los partidos activos en cancha con Disparos Totales, Tiros al Arco y Ocasiones Claras.")
    
    hay_en_vivo = False
    for nombre_liga, contenido in datos_globales.items():
        eventos_en_vivo = []
        for ev in contenido["eventos"]:
            comp = ev.get("competitions", [{}])[0]
            st_state, es_ht, _, _, _ = detectar_estado_partido(comp, ev.get("date", ""))
            if st_state == "in" or es_ht:
                eventos_en_vivo.append(ev)

        if not eventos_en_vivo:
            continue

        hay_en_vivo = True
        st.markdown(f"<div class='liga-header'>{nombre_liga}</div>", unsafe_allow_html=True)

        for ev in eventos_en_vivo:
            ev_id = str(ev.get("id"))
            comp = ev.get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])
            if len(competitors) != 2:
                continue

            loc, vis = competitors[0], competitors[1]
            nom_l = loc.get("team", {}).get("shortDisplayName", loc.get("team", {}).get("displayName", "Local"))
            nom_v = vis.get("team", {}).get("shortDisplayName", vis.get("team", {}).get("displayName", "Visita"))
            logo_l = loc.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
            logo_v = vis.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
            gol_l = int(loc.get("score", 0) or 0)
            gol_v = int(vis.get("score", 0) or 0)
            nombre_cruce = f"{nom_l} vs {nom_v}"

            _, _, _, badge_vivo, _ = detectar_estado_partido(comp, ev.get("date", ""))
            stats = extraer_metricas_partido(loc, vis)

            st.markdown(f"""
            <div class="match-card">
                {badge_vivo}
                <div class="teams-container">
                    <div class="team-home">{nom_l}</div>
                    <img src="{logo_l}" class="team-logo">
                    <div class="score-box">{gol_l} - {gol_v}</div>
                    <img src="{logo_v}" class="team-logo">
                    <div class="team-away">{nom_v}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander(f"📊 Estadísticas en Cancha ({nombre_cruce})", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("🎯 Disparos Totales", f"{stats['toth_l']} - {stats['toth_v']}", f"Total: {stats['toth_tot']}")
                with c2:
                    st.metric("🥅 Tiros al Arco", f"{stats['tmeta_l']} - {stats['tmeta_v']}", f"Total: {stats['tmeta_tot']}")
                with c3:
                    st.metric("🔥 Ocasiones Claras", f"{stats['claras_l']} - {stats['claras_v']}", f"Peligro: {stats['claras_tot']}")
                with c4:
                    st.metric("🚩 Córneres | Posesión", f"{stats['esquinas_l']} - {stats['esquinas_v']}", f"Pos: {stats['pos_l']}% - {stats['pos_v']}%")

                detalles_partido = comp.get("details", [])
                eventos_texto = []
                for d in detalles_partido:
                    min_ev = d.get("clock", {}).get("displayValue", "")
                    jugadores = d.get("athletesInvolved", [])
                    nom_jug = jugadores[0].get("displayName", "Jugador") if jugadores else ""
                    if d.get("scoringPlay", False):
                        eventos_texto.append(f"⚽ **GOL ({min_ev})**: {nom_jug}")
                    elif d.get("redCard", False):
                        eventos_texto.append(f"🟥 **ROJA ({min_ev})**: {nom_jug}")
                    elif d.get("yellowCard", False):
                        eventos_texto.append(f"🟨 **Amarilla ({min_ev})**: {nom_jug}")

                if eventos_texto:
                    st.markdown("**Incidentes:** " + " &nbsp;|&nbsp; ".join(eventos_texto))

    if not hay_en_vivo:
        st.info("No hay partidos en curso en este preciso instante en las 19 ligas.")

# -----------------------------------------------------------------------------
# SECCIÓN 3: PRE-APUESTAS OVER 1.5 (FILTRO FLEXIBLE CON CUOTAS DE VALOR)
# -----------------------------------------------------------------------------
with sec_apuestas:
    st.subheader("🎯 Laboratorio Pre-Apuesta Over 1.5 (Filtro Optimizado para Mejores Cuotas)")
    st.caption("Ajustamos la exigencia del filtro para detectar partidos con cuotas rentables que sí pagan bien en la casa de apuestas.")

    col_f1, col_f2 = st.columns([2.5, 1.5])
    with col_f1:
        opciones_ligas_pre = [l["id"] for l in LIGAS_BIG_DATA]
        ligas_seleccionadas_pre = st.multiselect("Ligas a auditar:", options=opciones_ligas_pre, default=opciones_ligas_pre)
    with col_f2:
        umbral_minimo = st.slider("Umbral Mínimo de Probabilidad (%):", min_value=58, max_value=82, value=64, step=2)

    reporte_pre = []
    for nombre_liga, contenido in datos_globales.items():
        if nombre_liga not in ligas_seleccionadas_pre:
            continue
        for evento in contenido["eventos"]:
            comp = evento.get("competitions", [{}])[0]
            st_state, es_ht, _, _, fecha_str = detectar_estado_partido(comp, evento.get("date", ""))
            if st_state != "pre" or es_ht:
                continue

            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                nom_local = competitors[0].get("team", {}).get("displayName", "Local")
                nom_visita = competitors[1].get("team", {}).get("displayName", "Visita")

                prob_final, cuota_justa, xg_base, perfil_cruce = calcular_pre_poisson(nom_local, nom_visita)
                if prob_final >= umbral_minimo:
                    if 64.0 <= prob_final <= 75.5:
                        veredicto = "💎 ENTRAR OVER 1.5 (Cuota de Valor / Paga Bien)"
                    elif prob_final > 75.5:
                        veredicto = "🟢 ENTRAR OVER 1.5 (Fijo Alta Probabilidad)"
                    else:
                        veredicto = "🟡 VALOR MODERADO (Ideal para En Vivo)"

                    reporte_pre.append({
                        "Fecha": fecha_str,
                        "Liga": nombre_liga,
                        "Partido": f"{nom_local} vs {nom_visita}",
                        "xG Esperado": xg_base,
                        "Prob. Pre Over 1.5": f"{prob_final}%",
                        "Cuota Estimada": cuota_justa,
                        "Perfil": perfil_cruce,
                        "Veredicto": veredicto
                    })

    if reporte_pre:
        st.dataframe(pd.DataFrame(reporte_pre), use_container_width=True, hide_index=True)
    else:
        st.info("No hay partidos programados que cumplan el filtro actual. Puedes bajar el deslizador de porcentaje.")

# -----------------------------------------------------------------------------
# SECCIÓN 4: SCRAPING Y ALERTAS EN VIVO (CRUZA % PRE-APUESTA + VOLUMEN EN VIVO)
# -----------------------------------------------------------------------------
with sec_scraping:
    st.subheader("🚨 Motor de Scraping y Recomendación en Vivo")
    st.markdown(
        "Cruza el **% esperado en Pre-Apuesta** con **Disparos Totales, Tiros al Arco y Ocasiones Claras** en vivo "
        "para indicarte si debes entrar a **Over 0.5** o **Over 1.5**."
    )

    tabla_scraping = []
    for nombre_liga, contenido in datos_globales.items():
        for evento in contenido["eventos"]:
            comp = evento.get("competitions", [{}])[0]
            st_state, es_ht, min_num, _, reloj_txt = detectar_estado_partido(comp, evento.get("date", ""))
            if st_state != "in" and not es_ht:
                continue

            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                loc, vis = competitors[0], competitors[1]
                nom_l_full = loc.get("team", {}).get("displayName", "Local")
                nom_v_full = vis.get("team", {}).get("displayName", "Visita")
                nom_l = loc.get("team", {}).get("shortDisplayName", nom_l_full)
                nom_v = vis.get("team", {}).get("shortDisplayName", nom_v_full)

                goles_l = int(loc.get("score", 0) or 0)
                goles_v = int(vis.get("score", 0) or 0)
                goles_tot = goles_l + goles_v

                # 1. Obtenemos el % que se esperaba en la Pre-Apuesta
                prob_pre, _, xg_pre, _ = calcular_pre_poisson(nom_l_full, nom_v_full)

                # 2. Obtenemos Disparos Totales, Tiros al Arco y Ocasiones Claras en vivo
                stats = extraer_metricas_partido(loc, vis)
                toth_tot = stats["toth_tot"]
                tmeta_tot = stats["tmeta_tot"]
                claras_tot = stats["claras_tot"]

                # 3. Veredicto inteligente con filtros más flexibles desde el minuto 15
                veredicto_vivo = f"⏳ Calentando ({prob_pre}% Pre | Esperando Min 15+)"
                if min_num >= 15 or es_ht:
                    if goles_tot == 0:
                        if tmeta_tot >= 2 or toth_tot >= 5 or claras_tot >= 2 or (prob_pre >= 68 and toth_tot >= 4):
                            veredicto_vivo = (
                                f"🚨 ¡ENTRAR AL OVER 0.5 GOLES! "
                                f"(Recomendado: {prob_pre}% Pre + Confirma en vivo con {toth_tot} Disp, {tmeta_tot} Arco, {claras_tot} Claras)"
                            )
                            disparar_alerta_celular(
                                f"ENTRAR OVER 0.5: {nom_l} vs {nom_v}",
                                f"Pre: {prob_pre}% | Vivo ({reloj_txt}): {toth_tot} Disp, {tmeta_tot} Arco, {claras_tot} Claras",
                                "🚨"
                            )
                        else:
                            veredicto_vivo = f"⚪ Monitoreando 0-0 (Pre: {prob_pre}% | Ritmo bajo: {toth_tot} Disp)"
                    elif goles_tot == 1:
                        if min_num <= 82 and (tmeta_tot >= 3 or toth_tot >= 6 or claras_tot >= 3 or (prob_pre >= 68 and toth_tot >= 5)):
                            veredicto_vivo = (
                                f"🔥 ¡ENTRAR AL OVER 1.5 GOLES! "
                                f"(Recomendado: {prob_pre}% Pre + Confirma en vivo con {toth_tot} Disp, {tmeta_tot} Arco, {claras_tot} Claras)"
                            )
                            disparar_alerta_celular(
                                f"ENTRAR OVER 1.5: {nom_l} vs {nom_v}",
                                f"Pre: {prob_pre}% | Vivo ({reloj_txt}): {toth_tot} Disp, {tmeta_tot} Arco, {claras_tot} Claras",
                                "🔥"
                            )
                        else:
                            veredicto_vivo = f"🟢 1 Gol en cancha (Pre: {prob_pre}% | Esperando 1 remate más)"
                    else:
                        veredicto_vivo = f"✅ ¡LÍNEA OVER 1.5 COBRADA EN VERDE! ({goles_l}-{goles_v})"

                tabla_scraping.append({
                    "Reloj": reloj_txt,
                    "Liga": nombre_liga,
                    "Partido": f"{nom_l} vs {nom_v}",
                    "Marcador": f"{goles_l} - {goles_v}",
                    "📈 Esperado Pre": f"{prob_pre}% (xG {xg_pre})",
                    "🎯 Disparos": toth_tot,
                    "🥅 Al Arco": tmeta_tot,
                    "🔥 Ocasiones Claras": claras_tot,
                    "💡 Veredicto para el Cliente": veredicto_vivo
                })

    if tabla_scraping:
        st.dataframe(pd.DataFrame(tabla_scraping), use_container_width=True, hide_index=True)
    else:
        st.info("No hay partidos en vivo en este momento para evaluar en el motor de scraping.")

# TEMPORIZADOR NO BLOQUEANTE AL FINAL DEL ARCHIVO (EVITA CONGELAR LAS PESTAÑAS Y EVITA LETRAS GRISES)
if auto_refresh:
    components.html("""
    <script>
    setTimeout(function() {
        window.parent.location.reload();
    }, 120000);
    </script>
    """, height=0)
