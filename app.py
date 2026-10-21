import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import unicodedata
from difflib import SequenceMatcher
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
    display: flex;
    justify-content: space-between;
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
    color: #00ffcc;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
    min-width: 72px;
    text-align: center;
}
.status-final {
    background-color: #16181f;
    color: #6c727f;
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
.footer-fijo {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    background-color: #0f1015;
    color: #9ba1b0;
    text-align: center;
    padding: 6px 0;
    font-size: 11px;
    border-top: 1px solid #1f222d;
    z-index: 9999;
}
</style>
""", unsafe_allow_html=True)

# ENCABEZADO OFICIAL MRFUTBOL
st.markdown("<div class='titulo-mrfutbol'>⚽ MRFUTBOL</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitulo-autor'>Miguel Ramirez &nbsp;|&nbsp; ✉️ angelramirezzmiguel2@gmail.com</div>", unsafe_allow_html=True)

# PIE DE PÁGINA FIJO SIEMPRE ABAJO
st.markdown(
    "<div class='footer-fijo'>Miguel Ramirez &nbsp;|&nbsp; ✉️ <a href='mailto:angelramirezzmiguel2@gmail.com' style='color:#00ffcc; text-decoration:none;'>angelramirezzmiguel2@gmail.com</a></div>",
    unsafe_allow_html=True
)

col_master1, col_master2, col_master3 = st.columns([2.5, 1, 1])
with col_master1:
    ahora_hn_str = (datetime.utcnow() - timedelta(hours=6)).strftime("%d/%m/%Y %H:%M")
    st.caption(f"💡 Central de Inteligencia y Auditoría Real (ESPN + SofaScore) | 🕒 Hora Oficial: **{ahora_hn_str}**")
with col_master2:
    master_sound = st.toggle("🔔 Alertas Activas", value=True, key="master_sound_key")
with col_master3:
    auto_refresh = st.toggle("🔄 Auto-Refresco (2m)", value=True, key="auto_refresh_key")

def disparar_alerta_celular(titulo, mensaje, icono="🔔"):
    if not master_sound:
        return
    hora_actual = (datetime.utcnow() - timedelta(hours=6)).strftime("%H:%M:%S")
    registro = f"[{hora_actual}] {icono} **{titulo}**: {mensaje}"
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
    {"id": "🏆 Champions League", "code": "uefa.champions", "efec": 85.0},
    {"id": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League (ING1)", "code": "eng.1", "efec": 80.0},
    {"id": "🇪🇸 LaLiga (ESP1)", "code": "esp.1", "efec": 79.0},
    {"id": "🇮🇹 Serie A (ITA1)", "code": "ita.1", "efec": 81.0},
    {"id": "🇩🇪 Bundesliga (ALE1)", "code": "ger.1", "efec": 86.0},
    {"id": "🇫🇷 Ligue 1 (FRA1)", "code": "fra.1", "efec": 80.0},
    {"id": "🇨🇭 Challenge League (SUI2)", "code": "sui.2", "efec": 91.0},
    {"id": "🇨🇭 Super League (SUI1)", "code": "sui.1", "efec": 89.0},
    {"id": "🇳🇱 Eredivisie (HOL1)", "code": "ned.1", "efec": 88.0},
    {"id": "🇳🇱 Eerste Divisie (HOL2)", "code": "ned.2", "efec": 85.0},
    {"id": "🇳🇴 Eliteserien (NOR1)", "code": "nor.1", "efec": 87.0},
    {"id": "🇳🇴 1. Division (NOR2)", "code": "nor.2", "efec": 86.0},
    {"id": "🇩🇪 2. Bundesliga (ALE2)", "code": "ger.2", "efec": 84.0},
    {"id": "🇦🇹 Bundesliga (AUT1)", "code": "aut.1", "efec": 84.0},
    {"id": "🇧🇪 Jupiler Pro League (BEL1)", "code": "bel.1", "efec": 83.0},
    {"id": "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Premiership (ESC1)", "code": "sco.1", "efec": 83.0},
    {"id": "🇹🇷 Süper Lig (TUR1)", "code": "tur.1", "efec": 82.0},
    {"id": "🇵🇹 Primeira Liga (POR1)", "code": "por.1", "efec": 81.0},
    {"id": "🇺🇸 MLS (USA1)", "code": "usa.1", "efec": 84.0},
    {"id": "🇲🇽 Liga MX (MEX1)", "code": "mex.1", "efec": 80.0},
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
    "Espanyol", "Valladolid", "Puebla", "Mazatlan"
]

BLOQUES_CERROJO = ["Getafe", "Mallorca", "Empoli", "Everton"]

HEADERS_BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com"
}

def normalizar_nombre(texto):
    if not texto:
        return ""
    txt = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8").lower()
    for palabra in ["fc", "cf", "sc", "ac", "cd", "club", "deportivo", "real", "sporting", "united", "city"]:
        txt = txt.replace(f" {palabra} ", " ").replace(f"^{palabra} ", "").replace(f" {palabra}$", "")
    return txt.strip()

def nombres_coinciden(nom1, nom2):
    n1, n2 = normalizar_nombre(nom1), normalizar_nombre(nom2)
    if not n1 or not n2:
        return False
    if n1 in n2 or n2 in n1:
        return True
    return SequenceMatcher(None, n1, n2).ratio() >= 0.72

def obtener_fecha_local_evento(iso_fecha):
    if not iso_fecha:
        return "1970-01-01", "Programado", "--:--", datetime(1970, 1, 1)
    try:
        limpio = iso_fecha.strip()[:16]
        dt_utc = datetime.strptime(limpio, "%Y-%m-%dT%H:%M")
        dt_local = dt_utc - timedelta(hours=6)
        return dt_local.strftime("%Y-%m-%d"), dt_local.strftime("%d/%m %H:%M"), dt_local.strftime("%H:%M"), dt_local
    except:
        return "1970-01-01", "Programado", "--:--", datetime(1970, 1, 1)

# =============================================================================
# 2DA FUENTE REAL: SCRAPING DIRECTO A SOFASCORE API (COMO SCRAPERFC)
# =============================================================================
def _fetch_sofascore_event_stats(ss_id):
    url_st = f"https://api.sofascore.com/api/v1/event/{ss_id}/statistics"
    stats_ss = {
        "toth_l": 0, "toth_v": 0, "toth_tot": 0,
        "tmeta_l": 0, "tmeta_v": 0, "tmeta_tot": 0,
        "esquinas_l": 0, "esquinas_v": 0,
        "xg_l": 0.0, "xg_v": 0.0, "big_chances_tot": 0
    }
    try:
        res = requests.get(url_st, headers=HEADERS_BROWSER, timeout=2.5)
        if res.status_code == 200:
            bloques = res.json().get("statistics", [])
            bloque_all = next((b for b in bloques if b.get("period") == "ALL"), bloques[0] if bloques else {})
            for grp in bloque_all.get("groups", []):
                for item in grp.get("statisticsItems", []):
                    name = item.get("name", "").lower()
                    h_val = str(item.get("home", "0")).replace("%", "").strip()
                    a_val = str(item.get("away", "0")).replace("%", "").strip()
                    try:
                        if name == "total shots":
                            stats_ss["toth_l"] = int(float(h_val))
                            stats_ss["toth_v"] = int(float(a_val))
                            stats_ss["toth_tot"] = stats_ss["toth_l"] + stats_ss["toth_v"]
                        elif name in ("shots on target", "shots on goal"):
                            stats_ss["tmeta_l"] = int(float(h_val))
                            stats_ss["tmeta_v"] = int(float(a_val))
                            stats_ss["tmeta_tot"] = stats_ss["tmeta_l"] + stats_ss["tmeta_v"]
                        elif name == "corner kicks":
                            stats_ss["esquinas_l"] = int(float(h_val))
                            stats_ss["esquinas_v"] = int(float(a_val))
                        elif name == "expected goals":
                            stats_ss["xg_l"] = float(h_val)
                            stats_ss["xg_v"] = float(a_val)
                        elif name == "big chances":
                            stats_ss["big_chances_tot"] = int(float(h_val)) + int(float(a_val))
                    except:
                        pass
            return ss_id, stats_ss
    except:
        pass
    return ss_id, None

@st.cache_data(ttl=25)
def obtener_datos_en_vivo_sofascore():
    """
    Consulta los partidos en vivo reales de SofaScore y extrae sus métricas detalladas.
    Si SofaScore responde, sirve como 2da fuente real de validación.
    """
    url_live = "https://api.sofascore.com/api/v1/sport/football/events/live"
    partidos_ss = []
    try:
        res = requests.get(url_live, headers=HEADERS_BROWSER, timeout=3)
        if res.status_code == 200:
            eventos_ss = res.json().get("events", [])
            ids_para_stats = []
            mapa_basico = {}
            for ev in eventos_ss:
                ss_id = ev.get("id")
                h_name = ev.get("homeTeam", {}).get("name", "")
                a_name = ev.get("awayTeam", {}).get("name", "")
                h_score = ev.get("homeScore", {}).get("current", 0)
                a_score = ev.get("awayScore", {}).get("current", 0)
                if ss_id and h_name and a_name:
                    ids_para_stats.append(ss_id)
                    mapa_basico[ss_id] = {
                        "ss_id": ss_id,
                        "home": h_name,
                        "away": a_name,
                        "gol_l": int(h_score or 0),
                        "gol_v": int(a_score or 0),
                        "stats": None
                    }
            # Descargamos estadísticas de los partidos en vivo en paralelo
            if ids_para_stats:
                with ThreadPoolExecutor(max_workers=10) as executor:
                    resultados_st = list(executor.map(_fetch_sofascore_event_stats, ids_para_stats[:45]))
                for s_id, st_dict in resultados_st:
                    if s_id in mapa_basico and st_dict:
                        mapa_basico[s_id]["stats"] = st_dict
            partidos_ss = list(mapa_basico.values())
    except:
        pass
    return partidos_ss

def cruzar_validacion_real_sofascore(nom_l, nom_v, stats_espn, lista_sofascore):
    """
    Cruza los datos reales de ESPN con los datos reales extraídos de SofaScore.
    CERO SIMULACIÓN: Si SofaScore tiene el partido, compara tiro por tiro.
    Si SofaScore no devolvió ese partido, informa con total honestidad.
    """
    match_ss = None
    for item in lista_sofascore:
        if nombres_coinciden(nom_l, item["home"]) and nombres_coinciden(nom_v, item["away"]):
            match_ss = item
            break

    if not match_ss:
        return (
            "📡 1ra Fuente Oficial (ESPN) | SofaScore sin cruce en vivo",
            "ESTÁNDAR (1 Fuente)",
            stats_espn,
            None
        )

    st_ss = match_ss.get("stats")
    if not st_ss:
        return (
            "🔗 Cruce Confirmado en SofaScore (Marcador Validado)",
            "MEDIA (Marcador Dual)",
            stats_espn,
            match_ss
        )

    # Si ESPN viene en 0 en alguna liga secundaria pero SofaScore sí tiene disparos reales, enriquecemos con SofaScore
    stats_combinadas = dict(stats_espn)
    if stats_combinadas["toth_tot"] == 0 and st_ss["toth_tot"] > 0:
        stats_combinadas["toth_l"] = st_ss["toth_l"]
        stats_combinadas["toth_v"] = st_ss["toth_v"]
        stats_combinadas["toth_tot"] = st_ss["toth_tot"]
        stats_combinadas["tmeta_l"] = st_ss["tmeta_l"]
        stats_combinadas["tmeta_v"] = st_ss["tmeta_v"]
        stats_combinadas["tmeta_tot"] = st_ss["tmeta_tot"]
        stats_combinadas["tfuera_l"] = max(0, st_ss["toth_l"] - st_ss["tmeta_l"])
        stats_combinadas["tfuera_v"] = max(0, st_ss["toth_v"] - st_ss["tmeta_v"])
        stats_combinadas["tfuera_tot"] = stats_combinadas["tfuera_l"] + stats_combinadas["tfuera_v"]

    diff_shots = abs(stats_espn["toth_tot"] - st_ss["toth_tot"])
    xg_ss_tot = round(st_ss["xg_l"] + st_ss["xg_v"], 2)
    extra_xg = f" | xG Vivo SS: {xg_ss_tot}" if xg_ss_tot > 0 else ""

    if diff_shots <= 2:
        sello = f"✅ Validado Dual Real (ESPN: {stats_espn['toth_tot']} Disp | SofaScore: {st_ss['toth_tot']} Disp{extra_xg})"
        nivel = "BLINDADA (Doble Confirmación)"
    else:
        sello = f"⚖️ Discrepancia Detectada (ESPN: {stats_espn['toth_tot']} Disp vs SofaScore: {st_ss['toth_tot']} Disp{extra_xg})"
        nivel = "AUDITADA (Usando Mayor Volumen)"

    return sello, nivel, stats_combinadas, st_ss

def _fetch_standings(code):
    url = f"https://site.api.espn.com/apis/v2/sports/soccer/{code}/standings"
    equipos_stats = {}
    goles_liga_tot = 0.0
    partidos_liga_tot = 0.0
    try:
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            entries = []
            if "children" in data:
                for ch in data["children"]:
                    entries.extend(ch.get("standings", {}).get("entries", []))
            else:
                entries = data.get("standings", {}).get("entries", [])

            for ent in entries:
                t_name = ent.get("team", {}).get("displayName", "")
                t_short = ent.get("team", {}).get("shortDisplayName", "")
                stats_dict = {s.get("name"): s.get("value", 0) for s in ent.get("stats", [])}
                pj = float(stats_dict.get("gamesPlayed", 0) or 0)
                gf = float(stats_dict.get("pointsFor", 0) or 0)
                gc = float(stats_dict.get("pointsAgainst", 0) or 0)
                if pj > 0:
                    goles_liga_tot += gf
                    partidos_liga_tot += (pj / 2.0)
                    info = {"pj": int(pj), "gf_prom": round(gf / pj, 2), "gc_prom": round(gc / pj, 2)}
                    if t_name:
                        equipos_stats[t_name.lower()] = info
                    if t_short:
                        equipos_stats[t_short.lower()] = info
    except:
        pass
    
    eficiencia_real_liga = None
    if partidos_liga_tot > 5:
        media_goles_liga = goles_liga_tot / partidos_liga_tot
        eficiencia_real_liga = round((1 - poisson.cdf(1, media_goles_liga)) * 100, 1)

    return code, equipos_stats, eficiencia_real_liga

@st.cache_data(ttl=900)
def obtener_estadisticas_temporada_reales(codigos_liga):
    tabla_global = {}
    eficiencias_ligas = {}
    with ThreadPoolExecutor(max_workers=12) as executor:
        resultados = list(executor.map(_fetch_standings, codigos_liga))
    for code, eq_dict, efec_real in resultados:
        tabla_global.update(eq_dict)
        if efec_real is not None:
            eficiencias_ligas[code] = efec_real
    return tabla_global, eficiencias_ligas

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

def calcular_pre_poisson_real(nom_local, nom_visita, stats_temporada):
    sot_l, xgs_l, tag_l, col_l, cer_l = auditar_equipo_bd(nom_local)
    sot_v, xgs_v, tag_v, col_v, cer_v = auditar_equipo_bd(nom_visita)
    
    xg_ini = (sot_l * xgs_l * 1.15) + (sot_v * xgs_v)
    real_l = stats_temporada.get(nom_local.lower())
    real_v = stats_temporada.get(nom_visita.lower())

    if real_l and real_v:
        xg_real_api = ((real_l["gf_prom"] + real_v["gc_prom"]) / 2.0) * 1.08 + ((real_v["gf_prom"] + real_l["gc_prom"]) / 2.0)
        xg_base = round((xg_real_api * 0.70) + (xg_ini * 0.30), 2)
        fuente_tag = f"✅ Tablas Oficiales ({real_l['gf_prom']} GF / {real_v['gf_prom']} GF)"
    else:
        bono_col = 0.30 if (col_l or col_v) else 0.0
        xg_base = round(xg_ini + bono_col, 2)
        fuente_tag = f"📊 Base BigData ({tag_l} vs {tag_v})"

    if cer_l or cer_v:
        xg_base = max(1.25, round(xg_base - 0.30, 2))

    prob_poisson = (1 - poisson.cdf(1, xg_base)) * 100
    prob_final = round(min(95.0, max(42.0, prob_poisson)), 1)
    cuota_justa = round(100 / prob_final, 2)
    return prob_final, cuota_justa, xg_base, fuente_tag

def calcular_tasa_gol_segundo_tiempo(xg_total_pre, disparos_totales, tiros_arco, min_actual):
    xg_2t_base = xg_total_pre * 0.57
    bono_presion = (disparos_totales * 0.035) + (tiros_arco * 0.08)
    xg_2t_ajustado = xg_2t_base + bono_presion

    if min_actual > 45:
        minutos_restantes_2t = max(8, 94 - min_actual)
        factor_tiempo = (minutos_restantes_2t / 45.0) * 1.22
        xg_2t_ajustado = xg_2t_ajustado * min(1.15, factor_tiempo)

    prob_gol_2t = (1 - poisson.cdf(0, xg_2t_ajustado)) * 100
    return round(min(94.0, max(50.0, prob_gol_2t)), 1)

def extraer_stat(team_dict, stat_names):
    for st_item in team_dict.get("statistics", []):
        if st_item.get("name") in stat_names:
            try:
                val = st_item.get("displayValue", "0").replace("%", "").strip()
                return float(val) if "." in val else int(val)
            except:
                return 0
    return 0

def extraer_metricas_partido_reales(loc, vis):
    toth_l = int(extraer_stat(loc, ["totalShots", "shots"]))
    toth_v = int(extraer_stat(vis, ["totalShots", "shots"]))
    
    tmeta_l = int(extraer_stat(loc, ["shotsOnTarget", "shotsOnGoal"]))
    tmeta_v = int(extraer_stat(vis, ["shotsOnTarget", "shotsOnGoal"]))
    
    tfuera_l = max(0, toth_l - tmeta_l)
    tfuera_v = max(0, toth_v - tmeta_v)
    
    esquinas_l = int(extraer_stat(loc, ["wonCorners", "corners", "cornerKicks"]))
    esquinas_v = int(extraer_stat(vis, ["wonCorners", "corners", "cornerKicks"]))
    
    pos_l = extraer_stat(loc, ["possessionPct"])
    pos_v = extraer_stat(vis, ["possessionPct"])
    
    return {
        "toth_l": toth_l, "toth_v": toth_v, "toth_tot": toth_l + toth_v,
        "tmeta_l": tmeta_l, "tmeta_v": tmeta_v, "tmeta_tot": tmeta_l + tmeta_v,
        "tfuera_l": tfuera_l, "tfuera_v": tfuera_v, "tfuera_tot": tfuera_l + tfuera_v,
        "esquinas_l": esquinas_l, "esquinas_v": esquinas_v, "esquinas_tot": esquinas_l + esquinas_v,
        "pos_l": pos_l, "pos_v": pos_v
    }

def generar_boletin_html_imprimible(df_datos, titulo_reporte, subtitulo_reporte):
    """Genera un Boletín Oficial VIP en HTML listo para imprimir o guardar como PDF con 1 clic"""
    fecha_emision = (datetime.utcnow() - timedelta(hours=6)).strftime("%d/%m/%Y %H:%M")
    tabla_html = df_datos.to_html(index=False, border=0, classes="tabla-boletin")
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>{titulo_reporte} - MRFUTBOL</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #0f1015; color: #e0e0e0; padding: 24px; }}
            .header {{ text-align: center; border-bottom: 2px solid #00ffcc; padding-bottom: 12px; margin-bottom: 18px; }}
            .header h1 {{ margin: 0; color: #ffffff; letter-spacing: 2px; }}
            .header p {{ margin: 4px 0; color: #00ffcc; font-weight: bold; font-size: 13px; }}
            .meta {{ font-size: 12px; color: #9ba1b0; margin-bottom: 15px; display: flex; justify-content: space-between; }}
            .tabla-boletin {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 20px; }}
            .tabla-boletin th {{ background-color: #16181f; color: #00ffcc; padding: 8px; text-align: left; border-bottom: 2px solid #00ffcc; }}
            .tabla-boletin td {{ padding: 8px; border-bottom: 1px solid #1f222d; color: #e0e0e0; }}
            .footer {{ text-align: center; font-size: 12px; color: #00ffcc; border-top: 1px solid #1f222d; padding-top: 12px; margin-top: 25px; }}
            .btn-print {{ background: #00ffcc; color: #000; padding: 8px 16px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; margin-bottom: 15px; }}
            @media print {{ .btn-print {{ display: none; }} body {{ background-color: #ffffff; color: #000000; }} .tabla-boletin td, .tabla-boletin th {{ color: #000000; border-color: #cccccc; }} }}
        </style>
    </head>
    <body>
        <button class="btn-print" onclick="window.print()">🖨️ Imprimir / Guardar Boletín en PDF</button>
        <div class="header">
            <h1>⚽ MRFUTBOL - BOLETÍN OFICIAL VIP</h1>
            <p>Autoría Oficial: Miguel Ramirez | ✉️ angelramirezzmiguel2@gmail.com</p>
        </div>
        <div class="meta">
            <span><strong>Reporte:</strong> {titulo_reporte} ({subtitulo_reporte})</span>
            <span><strong>Emisión (UTC-6):</strong> {fecha_emision} | <strong>Gestión de Banca Recomendada:</strong> Stake 2% - 3%</span>
        </div>
        {tabla_html}
        <div class="footer">
            ⚽ MRFUTBOL Central de Inteligencia | Creado por Miguel Ramirez (angelramirezzmiguel2@gmail.com)
        </div>
    </body>
    </html>
    """

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

    _, fecha_corta, hora_sola, _ = obtener_fecha_local_evento(iso_fecha)

    if es_ht:
        badge_html = "<div class='status-ht'>⏸️ ENTRETIEMPO</div>"
        reloj_txt = "⏸️ HT (45')"
    elif st_state == "in":
        badge_html = f"<div class='status-live'>🔴 {reloj}</div>"
        reloj_txt = f"🔴 {reloj}"
    elif st_state == "post":
        badge_html = "<div class='status-final'>FINAL</div>"
        reloj_txt = "FINAL"
    else:
        badge_html = f"<div class='status-badge'>🕒 {hora_sola}</div>"
        reloj_txt = fecha_corta

    return st_state, es_ht, min_num, badge_html, reloj_txt

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
    fechas = [(hoy_hn + timedelta(days=i)).strftime("%Y%m%d") for i in (0, 1)]
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

# FECHAS LOCALES EXACTAS EN HONDURAS (UTC-6)
hoy_hn_dt = datetime.utcnow() - timedelta(hours=6)
str_hoy = hoy_hn_dt.strftime("%Y-%m-%d")
str_manana = (hoy_hn_dt + timedelta(days=1)).strftime("%Y-%m-%d")

codigos_todas = [l["code"] for l in LIGAS_BIG_DATA]
datos_globales = obtener_partidos_ligas(codigos_todas)
stats_temporada_api, eficiencias_ligas_api = obtener_estadisticas_temporada_reales(codigos_todas)
lista_vivo_sofascore = obtener_datos_en_vivo_sofascore()

def obtener_eficiencia_dinamica_liga(meta_liga):
    code = meta_liga["code"]
    efec_base = float(meta_liga["efec"])
    if code in eficiencias_ligas_api:
        efec_viva = round((efec_base * 0.65) + (eficiencias_ligas_api[code] * 0.35), 1)
        return f"{efec_viva}% (API Activa)"
    return f"{efec_base}%"

sec_resultados, sec_en_vivo, sec_apuestas, sec_scraping = st.tabs([
    "⚽ 1. CARTELERA DE HOY", 
    "🔴 2. PARTIDOS EN VIVO", 
    "🎯 3. PRE-APUESTAS Y REPORTES", 
    "🚨 4. SCRAPING Y VALIDACIÓN DUAL"
])

# -----------------------------------------------------------------------------
# SECCIÓN 1: CARTELERA EXCLUSIVA DE HOY / MAÑANA (CON INCIDENTES COMPLETOS)
# -----------------------------------------------------------------------------
with sec_resultados:
    col_menu, col_contenido = st.columns([1.2, 3.8])

    with col_menu:
        st.markdown("##### 📅 Cartelera Activa")
        opciones_dia = {
            f"🟢 Hoy ({hoy_hn_dt.strftime('%d/%m')})": str_hoy,
            f"⏭️ Mañana ({(hoy_hn_dt + timedelta(days=1)).strftime('%d/%m')})": str_manana,
        }
        etiqueta_dia_sel = st.radio("Seleccionar Día:", list(opciones_dia.keys()), index=0, label_visibility="collapsed")
        fecha_objetivo_portada = opciones_dia[etiqueta_dia_sel]

        ocultar_finalizados = st.toggle("👁️ Ocultar Finalizados", value=True)

        st.markdown("##### 📌 Ligas Disponibles")
        nombres_ligas = [l["id"] for l in LIGAS_BIG_DATA]
        liga_seleccionada_panel = st.selectbox("Filtrar Liga:", ["🌍 Todas las Ligas"] + nombres_ligas, label_visibility="collapsed")
        texto_busqueda = st.text_input("🔍 Buscar Equipo...", "", placeholder="Ej. Real Madrid, Barcelona...")
        if st.button("🔄 Actualizar Datos Ahora", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.caption(f"📡 Partidos en vivo detectados en 2da Fuente (SofaScore): **{len(lista_vivo_sofascore)}**")

    with col_contenido:
        hay_partidos_jornada = False
        for nombre_liga, contenido in datos_globales.items():
            if liga_seleccionada_panel != "🌍 Todas las Ligas" and liga_seleccionada_panel != nombre_liga:
                continue

            eventos_filtrados = []
            for ev in contenido["eventos"]:
                fecha_ev_local, _, _, dt_local_obj = obtener_fecha_local_evento(ev.get("date", ""))
                comp = ev.get("competitions", [{}])[0]
                st_state_ev, es_ht_ev, _, _, _ = detectar_estado_partido(comp, ev.get("date", ""))

                if fecha_ev_local != fecha_objetivo_portada:
                    continue

                if ocultar_finalizados and st_state_ev == "post":
                    continue

                competitors = comp.get("competitors", [])
                if len(competitors) == 2:
                    nom_l = competitors[0].get("team", {}).get("displayName", "")
                    nom_v = competitors[1].get("team", {}).get("displayName", "")
                    if not texto_busqueda or (texto_busqueda.lower() in nom_l.lower() or texto_busqueda.lower() in nom_v.lower()):
                        prioridad = 0 if (st_state_ev == "in" or es_ht_ev) else (1 if st_state_ev == "pre" else 2)
                        eventos_filtrados.append((prioridad, dt_local_obj, ev))

            if not eventos_filtrados:
                continue

            eventos_filtrados.sort(key=lambda x: (x[0], x[1]))

            hay_partidos_jornada = True
            efec_txt = obtener_eficiencia_dinamica_liga(contenido["meta"])
            st.markdown(
                f"<div class='liga-header'><span>{nombre_liga}</span><span style='font-size:12px; color:#9ba1b0;'>Eficiencia Gol: {efec_txt}</span></div>",
                unsafe_allow_html=True
            )

            for _, _, ev in eventos_filtrados:
                ev_id = str(ev.get("id"))
                comp = ev.get("competitions", [{}])[0]
                competitors = comp.get("competitors", [])
                if len(competitors) != 2:
                    continue

                loc, vis = competitors[0], competitors[1]
                nom_l_full = loc.get("team", {}).get("displayName", "Local")
                nom_v_full = vis.get("team", {}).get("displayName", "Visita")
                nom_l = loc.get("team", {}).get("shortDisplayName", nom_l_full)
                nom_v = vis.get("team", {}).get("shortDisplayName", nom_v_full)
                logo_l = loc.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
                logo_v = vis.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
                gol_l = int(loc.get("score", 0) or 0)
                gol_v = int(vis.get("score", 0) or 0)
                nombre_cruce = f"{nom_l} vs {nom_v}"

                st_state, es_ht, min_num, badge_html, _ = detectar_estado_partido(comp, ev.get("date", ""))
                centro_html = f"{gol_l} - {gol_v}" if (st_state != "pre" or es_ht) else "vs"

                detalles_partido = comp.get("details", [])
                rojas_actuales = sum(1 for d in detalles_partido if d.get("redCard", False))
                stats_raw = extraer_metricas_partido_reales(loc, vis)
                sello_val, nivel_val, stats, _ = cruzar_validacion_real_sofascore(nom_l_full, nom_v_full, stats_raw, lista_vivo_sofascore)

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
                        if st_state == "in" or es_ht:
                            st.caption(f"🛡️ **Auditoría en Vivo:** {sello_val} | Nivel: **{nivel_val}**")
                        df_resumen = pd.DataFrame([
                            {"Métrica Oficial": "🎯 Disparos Totales", nom_l: stats["toth_l"], nom_v: stats["toth_v"]},
                            {"Métrica Oficial": "🥅 Tiros al Arco", nom_l: stats["tmeta_l"], nom_v: stats["tmeta_v"]},
                            {"Métrica Oficial": "💥 Disparos Fuera / Bloq.", nom_l: stats["tfuera_l"], nom_v: stats["tfuera_v"]},
                            {"Métrica Oficial": "⏱️ Posesión", nom_l: f"{stats['pos_l']}%", nom_v: f"{stats['pos_v']}%"},
                            {"Métrica Oficial": "🚩 Córneres", nom_l: stats["esquinas_l"], nom_v: stats["esquinas_v"]},
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

        if not hay_partidos_jornada:
            st.info(f"No hay partidos en vivo o programados para {etiqueta_dia_sel}.")

    if st.session_state["historial_notificaciones"]:
        with st.expander("📲 Bandeja de Alertas Recientes", expanded=False):
            for notif in st.session_state["historial_notificaciones"][:8]:
                st.info(notif)

# -----------------------------------------------------------------------------
# SECCIÓN 2: PARTIDOS EN VIVO CON AUDITORÍA REAL (ESPN + SOFASCORE)
# -----------------------------------------------------------------------------
with sec_en_vivo:
    st.subheader("🔴 Partidos en Vivo y Auditoría Cruzada Real (ESPN vs SofaScore)")
    st.caption("Contrasta en tiempo real las métricas de ESPN con los datos extraídos de la API de SofaScore.")
    
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
        efec_txt = obtener_eficiencia_dinamica_liga(contenido["meta"])
        st.markdown(
            f"<div class='liga-header'><span>{nombre_liga}</span><span style='font-size:12px; color:#9ba1b0;'>Eficiencia Gol: {efec_txt}</span></div>",
            unsafe_allow_html=True
        )

        for ev in eventos_en_vivo:
            ev_id = str(ev.get("id"))
            comp = ev.get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])
            if len(competitors) != 2:
                continue

            loc, vis = competitors[0], competitors[1]
            nom_l_full = loc.get("team", {}).get("displayName", "Local")
            nom_v_full = vis.get("team", {}).get("displayName", "Visita")
            nom_l = loc.get("team", {}).get("shortDisplayName", nom_l_full)
            nom_v = vis.get("team", {}).get("shortDisplayName", nom_v_full)
            logo_l = loc.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
            logo_v = vis.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
            gol_l = int(loc.get("score", 0) or 0)
            gol_v = int(vis.get("score", 0) or 0)
            nombre_cruce = f"{nom_l} vs {nom_v}"

            _, _, _, badge_vivo, _ = detectar_estado_partido(comp, ev.get("date", ""))
            stats_raw = extraer_metricas_partido_reales(loc, vis)
            sello_val, nivel_val, stats, st_ss = cruzar_validacion_real_sofascore(nom_l_full, nom_v_full, stats_raw, lista_vivo_sofascore)

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

            with st.expander(f"📊 Estadísticas en Cancha y Validación ({nombre_cruce})", expanded=True):
                st.caption(f"🛡️ **Estado de Validación:** {sello_val} | **Confianza:** {nivel_val}")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("🎯 Disparos Totales", f"{stats['toth_l']} - {stats['toth_v']}", f"Total: {stats['toth_tot']}")
                with c2:
                    st.metric("🥅 Tiros al Arco", f"{stats['tmeta_l']} - {stats['tmeta_v']}", f"Total: {stats['tmeta_tot']}")
                with c3:
                    st.metric("💥 Disparos Fuera", f"{stats['tfuera_l']} - {stats['tfuera_v']}", f"Total: {stats['tfuera_tot']}")
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
# SECCIÓN 3: PRE-APUESTAS OVER 1.5 Y EXPORTACIÓN DE REPORTES OFICIALES
# -----------------------------------------------------------------------------
with sec_apuestas:
    st.subheader("🎯 Laboratorio Pre-Apuesta Over 1.5 y Generador de Reportes VIP")
    st.caption("Cruza los goles reales de la tabla oficial de ESPN con tu base de datos y exporta el Boletín Oficial para tus clientes.")

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
            fecha_ev_local, fecha_legible, _, _ = obtener_fecha_local_evento(evento.get("date", ""))
            if fecha_ev_local not in (str_hoy, str_manana):
                continue

            comp = evento.get("competitions", [{}])[0]
            st_state, es_ht, _, _, _ = detectar_estado_partido(comp, evento.get("date", ""))
            if st_state != "pre" or es_ht:
                continue

            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                nom_local = competitors[0].get("team", {}).get("displayName", "Local")
                nom_visita = competitors[1].get("team", {}).get("displayName", "Visita")

                prob_final, cuota_justa, xg_base, fuente_tag = calcular_pre_poisson_real(
                    nom_local, nom_visita, stats_temporada_api
                )
                tasa_2t = calcular_tasa_gol_segundo_tiempo(xg_base, 0, 0, 0)

                if prob_final >= umbral_minimo:
                    if 64.0 <= prob_final <= 75.5:
                        veredicto = "💎 ENTRAR OVER 1.5 (Cuota de Valor / Stake 2%)"
                    elif prob_final > 75.5:
                        veredicto = "🟢 ENTRAR OVER 1.5 (Fijo Alta Probabilidad / Stake 3%)"
                    else:
                        veredicto = "🟡 VALOR MODERADO (Buscar en Vivo)"

                    reporte_pre.append({
                        "Fecha": fecha_legible,
                        "Liga": nombre_liga,
                        "Partido": f"{nom_local} vs {nom_visita}",
                        "xG Esperado": xg_base,
                        "Prob. Pre Over 1.5": f"{prob_final}%",
                        "🔥 Tasa Gol 2T": f"{tasa_2t}%",
                        "Cuota Justa": cuota_justa,
                        "Fuente de Validación": fuente_tag,
                        "Veredicto": veredicto
                    })

    if reporte_pre:
        df_pre = pd.DataFrame(reporte_pre)
        st.dataframe(df_pre, use_container_width=True, hide_index=True)

        # BOTONES REALES DE EXPORTACIÓN DE REPORTES (BOLETÍN PDF/HTML Y CSV)
        col_rep1, col_rep2 = st.columns(2)
        with col_rep1:
            html_boletin_pre = generar_boletin_html_imprimible(
                df_pre,
                "REPORTE PRE-APUESTAS OVER 1.5",
                f"Filtro >= {umbral_minimo}% | Hoy y Mañana"
            )
            st.download_button(
                label="📄 Descargar Boletín Oficial VIP (Imprimible / Guardar PDF)",
                data=html_boletin_pre.encode("utf-8"),
                file_name=f"Boletin_PreApuestas_MRFUTBOL_{str_hoy}.html",
                mime="text/html",
                use_container_width=True
            )
        with col_rep2:
            st.download_button(
                label="📊 Exportar Reporte Pre-Apuestas en Excel / CSV",
                data=df_pre.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"Reporte_PreApuestas_MRFUTBOL_{str_hoy}.csv",
                mime="text/csv",
                use_container_width=True
            )
    else:
        st.info("No hay partidos programados que cumplan el filtro actual. Puedes bajar el deslizador de porcentaje.")

# -----------------------------------------------------------------------------
# SECCIÓN 4: SCRAPING EN VIVO, TASA 2DO TIEMPO, VALIDACIÓN DUAL Y REPORTE
# -----------------------------------------------------------------------------
with sec_scraping:
    st.subheader("🚨 Motor de Scraping en Vivo + Validación Dual Real (ESPN + SofaScore)")
    st.markdown(
        "Cruza el **% esperado en Pre-Apuesta** con los **Disparos reales auditados (ESPN + SofaScore)** y la **Tasa de Gol en el 2do Tiempo (2T)** "
        "para respaldar tu entrada al **Over 0.5 / Over 1.5** cuando un equipo ya suma **3+ disparos**."
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

                prob_pre, _, xg_pre, _ = calcular_pre_poisson_real(nom_l_full, nom_v_full, stats_temporada_api)
                stats_raw = extraer_metricas_partido_reales(loc, vis)
                sello_val, nivel_val, stats, _ = cruzar_validacion_real_sofascore(
                    nom_l_full, nom_v_full, stats_raw, lista_vivo_sofascore
                )

                toth_l, toth_v, toth_tot = stats["toth_l"], stats["toth_v"], stats["toth_tot"]
                tmeta_tot = stats["tmeta_tot"]
                max_disp_equipo = max(toth_l, toth_v)
                equipo_dominante = nom_l if toth_l >= toth_v else nom_v

                tasa_gol_2t = calcular_tasa_gol_segundo_tiempo(xg_pre, toth_tot, tmeta_tot, min_num)

                veredicto_vivo = f"⏳ Calentando ({prob_pre}% Pre | Tasa Gol 2T: {tasa_gol_2t}%)"
                if min_num >= 15 or es_ht:
                    if goles_tot == 0:
                        if max_disp_equipo >= 3 or tmeta_tot >= 2 or toth_tot >= 5:
                            aviso_2t = (
                                f"🔥 ¡SIN MIEDO AL 0-0! Rivales con {tasa_gol_2t}% de Tasa de Gol en 2T"
                                if tasa_gol_2t >= 72.0 else
                                f"📈 Tasa de Gol en 2T: {tasa_gol_2t}%"
                            )
                            veredicto_vivo = (
                                f"🚨 ¡ENTRAR AL OVER 0.5 GOLES! ({equipo_dominante} suma {max_disp_equipo} disp | "
                                f"Totales: {toth_tot} Disp, {tmeta_tot} Arco) 👉 {aviso_2t}"
                            )
                            disparar_alerta_celular(
                                f"ENTRAR OVER 0.5: {nom_l} vs {nom_v}",
                                f"0-0 ({reloj_txt}) | {equipo_dominante} lleva {max_disp_equipo} disp | Tasa 2T: {tasa_gol_2t}%",
                                "🚨"
                            )
                        else:
                            veredicto_vivo = (
                                f"⚪ Monitoreando 0-0 ({toth_tot} Disp) | Si va 0-0 al descanso, "
                                f"rivales registran {tasa_gol_2t}% de Tasa de Gol en 2T"
                            )
                    elif goles_tot == 1:
                        if min_num <= 82 and (max_disp_equipo >= 3 or tmeta_tot >= 3 or toth_tot >= 6):
                            veredicto_vivo = (
                                f"🔥 ¡ENTRAR AL OVER 1.5 GOLES! (Ritmo alto: {toth_tot} Disp, {tmeta_tot} Arco | "
                                f"Tasa de Gol en 2T: {tasa_gol_2t}%)"
                            )
                            disparar_alerta_celular(
                                f"ENTRAR OVER 1.5: {nom_l} vs {nom_v}",
                                f"Marcador {goles_l}-{goles_v} ({reloj_txt}) | {toth_tot} Disp | Tasa 2T: {tasa_gol_2t}%",
                                "🔥"
                            )
                        else:
                            veredicto_vivo = f"🟢 1 Gol en cancha ({toth_tot} Disp, {tmeta_tot} Arco | Potencial 2T: {tasa_gol_2t}%)"
                    else:
                        veredicto_vivo = f"✅ ¡LÍNEA OVER 1.5 COBRADA EN VERDE! ({goles_l}-{goles_v})"

                tabla_scraping.append({
                    "Reloj": reloj_txt,
                    "Liga": nombre_liga,
                    "Partido": f"{nom_l} vs {nom_v}",
                    "Marcador": f"{goles_l} - {goles_v}",
                    "📈 Esperado Pre": f"{prob_pre}% (xG {xg_pre})",
                    "🔥 Tasa Gol 2T": f"{tasa_gol_2t}%",
                    "🎯 Disparos (L-V)": f"{toth_l} - {toth_v} (Tot: {toth_tot})",
                    "🥅 Al Arco (L-V)": f"{stats['tmeta_l']} - {stats['tmeta_v']} (Tot: {tmeta_tot})",
                    "🛡️ Auditoría 2da Fuente": sello_val,
                    "💡 Veredicto y Confianza 2T": veredicto_vivo
                })

    if tabla_scraping:
        df_scr = pd.DataFrame(tabla_scraping)
        st.dataframe(df_scr, use_container_width=True, hide_index=True)

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            html_boletin_vivo = generar_boletin_html_imprimible(
                df_scr,
                "REPORTE DE SCRAPING Y SEÑALES EN VIVO",
                "Auditoría Dual ESPN + SofaScore"
            )
            st.download_button(
                label="📄 Descargar Reporte de Señales en Vivo (Imprimible / PDF)",
                data=html_boletin_vivo.encode("utf-8"),
                file_name=f"Boletin_EnVivo_MRFUTBOL_{str_hoy}.html",
                mime="text/html",
                use_container_width=True
            )
        with col_s2:
            st.download_button(
                label="📊 Exportar Señales en Vivo en Excel / CSV",
                data=df_scr.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"Senales_EnVivo_MRFUTBOL_{str_hoy}.csv",
                mime="text/csv",
                use_container_width=True
            )
    else:
        st.info("No hay partidos en vivo en este momento para evaluar en el motor de scraping.")

if auto_refresh:
    components.html("""
    <script>
    setTimeout(function() {
        window.parent.location.reload();
    }, 120000);
    </script>
    """, height=0)
