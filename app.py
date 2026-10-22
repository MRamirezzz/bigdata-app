import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import unicodedata
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from scipy.stats import poisson

# Configuración principal con la marca MRFUTBOL
st.set_page_config(page_title="MRFUTBOL - Miguel Ramirez", page_icon="⚽", layout="wide")

# =============================================================================
# 1. MEMORIA INDIVIDUAL POR CADA USUARIO / NAVEGADOR (COMO CUALQUIER APP DE FÚTBOL)
# =============================================================================
if "seguidos_usuario" not in st.session_state:
    st.session_state["seguidos_usuario"] = []
if "memoria_eventos_usuario" not in st.session_state:
    st.session_state["memoria_eventos_usuario"] = {}
if "historial_notificaciones_usuario" not in st.session_state:
    st.session_state["historial_notificaciones_usuario"] = []

# =============================================================================
# 2. BÓVEDA OCULTA EN EL SERVIDOR (SOLO PARA EL ENTRENAMIENTO DEL OVER 0.5 DEL JEFE)
# =============================================================================
ARCHIVO_BITACORA_OCULTA = ".boveda_ml_over05_mrfutbol.json"

@st.cache_resource
def obtener_boveda_ml_servidor():
    """
    Guarda en silencio las señales Over 0.5 (Min 18+) las 24 horas en el servidor.
    Nadie del público puede verla; solo se muestra en el navegador donde se ingrese la clave.
    """
    if os.path.exists(ARCHIVO_BITACORA_OCULTA):
        try:
            with open(ARCHIVO_BITACORA_OCULTA, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def guardar_boveda_ml_servidor(boveda):
    try:
        with open(ARCHIVO_BITACORA_OCULTA, "w", encoding="utf-8") as f:
            json.dump(boveda, f, ensure_ascii=False, indent=2)
    except:
        pass

boveda_ml_05 = obtener_boveda_ml_servidor()

# ESTILOS CSS COMPACTOS + TARJETAS ANCHAS DE TRADING PARA SCRAPING
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
.trading-card {
    background-color: #0f1015;
    border: 1px solid #262b3d;
    border-left: 4px solid #00ffcc;
    border-radius: 8px;
    padding: 12px 15px;
    margin-bottom: 10px;
    color: #e0e0e0;
}
.trading-card-hot {
    background-color: #12161f;
    border: 1px solid #00ffcc;
    border-left: 5px solid #00ffcc;
    border-radius: 8px;
    padding: 12px 15px;
    margin-bottom: 10px;
    color: #ffffff;
    box-shadow: 0 2px 10px rgba(0, 255, 204, 0.12);
}
.trading-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #1f222d;
    padding-bottom: 6px;
    margin-bottom: 8px;
    flex-wrap: wrap;
    gap: 6px;
}
.trading-metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
    gap: 8px;
    margin-bottom: 8px;
}
.metric-pill {
    background-color: #16181f;
    border: 1px solid #1f222d;
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 12px;
    text-align: center;
}
.metric-pill span {
    display: block;
    font-size: 10px;
    color: #9ba1b0;
    text-transform: uppercase;
}
.metric-pill strong {
    font-size: 13px;
    color: #00ffcc;
}
.veredicto-box-hot {
    background: linear-gradient(90deg, rgba(0,255,204,0.16) 0%, rgba(22,24,31,0.95) 100%);
    border: 1px solid #00ffcc;
    color: #ffffff;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    line-height: 1.4;
}
.veredicto-box-wait {
    background-color: #16181f;
    border: 1px solid #ff9800;
    color: #ffd180;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    line-height: 1.4;
}
.veredicto-box-green {
    background-color: rgba(0, 200, 83, 0.15);
    border: 1px solid #00c853;
    color: #69f0ae;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
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
# 2DA FUENTE DE AUDITORÍA EN VIVO (MARCA BLANCA MRFUTBOL)
# =============================================================================
def _fetch_secondary_event_stats(sec_id):
    url_st = f"https://api.sofascore.com/api/v1/event/{sec_id}/statistics"
    stats_sec = {
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
                            stats_sec["toth_l"] = int(float(h_val))
                            stats_sec["toth_v"] = int(float(a_val))
                            stats_sec["toth_tot"] = stats_sec["toth_l"] + stats_sec["toth_v"]
                        elif name in ("shots on target", "shots on goal"):
                            stats_sec["tmeta_l"] = int(float(h_val))
                            stats_sec["tmeta_v"] = int(float(a_val))
                            stats_sec["tmeta_tot"] = stats_sec["tmeta_l"] + stats_sec["tmeta_v"]
                        elif name == "corner kicks":
                            stats_sec["esquinas_l"] = int(float(h_val))
                            stats_sec["esquinas_v"] = int(float(a_val))
                        elif name == "expected goals":
                            stats_sec["xg_l"] = float(h_val)
                            stats_sec["xg_v"] = float(a_val)
                        elif name == "big chances":
                            stats_sec["big_chances_tot"] = int(float(h_val)) + int(float(a_val))
                    except:
                        pass
            return sec_id, stats_sec
    except:
        pass
    return sec_id, None

@st.cache_data(ttl=20)
def obtener_datos_segunda_fuente():
    url_live = "https://api.sofascore.com/api/v1/sport/football/events/live"
    partidos_sec = []
    try:
        res = requests.get(url_live, headers=HEADERS_BROWSER, timeout=3)
        if res.status_code == 200:
            eventos_sec = res.json().get("events", [])
            ids_para_stats = []
            mapa_basico = {}
            for ev in eventos_sec:
                sec_id = ev.get("id")
                h_name = ev.get("homeTeam", {}).get("name", "")
                a_name = ev.get("awayTeam", {}).get("name", "")
                h_score = ev.get("homeScore", {}).get("current", 0)
                a_score = ev.get("awayScore", {}).get("current", 0)
                if sec_id and h_name and a_name:
                    ids_para_stats.append(sec_id)
                    mapa_basico[sec_id] = {
                        "sec_id": sec_id,
                        "home": h_name,
                        "away": a_name,
                        "gol_l": int(h_score or 0),
                        "gol_v": int(a_score or 0),
                        "stats": None
                    }
            if ids_para_stats:
                with ThreadPoolExecutor(max_workers=10) as executor:
                    resultados_st = list(executor.map(_fetch_secondary_event_stats, ids_para_stats[:45]))
                for s_id, st_dict in resultados_st:
                    if s_id in mapa_basico and st_dict:
                        mapa_basico[s_id]["stats"] = st_dict
            partidos_sec = list(mapa_basico.values())
    except:
        pass
    return partidos_sec

def cruzar_validacion_doble_fuente(nom_l, nom_v, stats_f1, lista_f2):
    match_f2 = None
    for item in lista_f2:
        if nombres_coinciden(nom_l, item["home"]) and nombres_coinciden(nom_v, item["away"]):
            match_f2 = item
            break

    if not match_f2:
        return (
            "📡 Radar Oficial MRFUTBOL Activo",
            "ESTÁNDAR (F1)",
            stats_f1,
            None
        )

    st_f2 = match_f2.get("stats")
    if not st_f2:
        return (
            "🔗 Doble Fuente Conectada (Marcador Validado)",
            "MEDIA (Dual)",
            stats_f1,
            match_f2
        )

    stats_combinadas = dict(stats_f1)
    if stats_combinadas["toth_tot"] == 0 and st_f2["toth_tot"] > 0:
        stats_combinadas["toth_l"] = st_f2["toth_l"]
        stats_combinadas["toth_v"] = st_f2["toth_v"]
        stats_combinadas["toth_tot"] = st_f2["toth_tot"]
        stats_combinadas["tmeta_l"] = st_f2["tmeta_l"]
        stats_combinadas["tmeta_v"] = st_f2["tmeta_v"]
        stats_combinadas["tmeta_tot"] = st_f2["tmeta_tot"]
        stats_combinadas["tfuera_l"] = max(0, st_f2["toth_l"] - st_f2["tmeta_l"])
        stats_combinadas["tfuera_v"] = max(0, st_f2["toth_v"] - st_f2["tmeta_v"])
        stats_combinadas["tfuera_tot"] = stats_combinadas["tfuera_l"] + stats_combinadas["tfuera_v"]

    diff_shots = abs(stats_f1["toth_tot"] - st_f2["toth_tot"])
    xg_f2_tot = round(st_f2["xg_l"] + st_f2["xg_v"], 2)
    extra_xg = f" | xG Vivo: {xg_f2_tot}" if xg_f2_tot > 0 else ""

    if diff_shots <= 2:
        sello = f"✅ Doble Validación OK (F1: {stats_f1['toth_tot']} | F2: {st_f2['toth_tot']} Disp{extra_xg})"
        nivel = "BLINDADA"
    else:
        sello = f"⚖️ Línea Auditada (F1: {stats_f1['toth_tot']} vs F2: {st_f2['toth_tot']} Disp{extra_xg})"
        nivel = "AUDITADA"

    return sello, nivel, stats_combinadas, st_f2

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
        fuente_tag = f"✅ Estadística Oficial ({real_l['gf_prom']} GF / {real_v['gf_prom']} GF)"
    else:
        bono_col = 0.30 if (col_l or col_v) else 0.0
        xg_base = round(xg_ini + bono_col, 2)
        fuente_tag = f"📊 Base MRFUTBOL ({tag_l} vs {tag_v})"

    if cer_l or cer_v:
        xg_base = max(1.25, round(xg_base - 0.30, 2))

    prob_poisson = (1 - poisson.cdf(1, xg_base)) * 100
    prob_final = round(min(95.0, max(42.0, prob_poisson)), 1)
    cuota_justa = round(100 / prob_final, 2)
    return prob_final, cuota_justa, xg_base, fuente_tag

def calcular_tasas_tiempos_y_franja(xg_total_pre, disparos_tot, tiros_arco, corneres_tot, min_actual):
    bono_presion = (disparos_tot * 0.032) + (tiros_arco * 0.075) + (corneres_tot * 0.018)

    xg_1t = (xg_total_pre * 0.43) + (bono_presion * 0.65)
    prob_1t = (1 - poisson.cdf(0, xg_1t)) * 100
    tasa_1t = round(min(91.0, max(38.0, prob_1t)), 1)

    xg_2t = (xg_total_pre * 0.57) + bono_presion
    if min_actual > 45:
        minutos_restantes_2t = max(8, 94 - min_actual)
        factor_tiempo = (minutos_restantes_2t / 45.0) * 1.22
        xg_2t = xg_2t * min(1.15, factor_tiempo)
    prob_2t = (1 - poisson.cdf(0, xg_2t)) * 100
    tasa_2t = round(min(94.0, max(50.0, prob_2t)), 1)

    xg_franja_38_45 = (xg_1t * 0.52) + (tiros_arco * 0.04)
    prob_franja = (1 - poisson.cdf(0, xg_franja_38_45)) * 100
    tasa_38_45 = round(min(82.0, max(28.0, prob_franja)), 1)

    return tasa_1t, tasa_2t, tasa_38_45

def extraer_primer_minuto_gol(detalles_partido, min_actual_fallback):
    minutos_goles = []
    for d in detalles_partido:
        if d.get("scoringPlay", False):
            clk = str(d.get("clock", {}).get("displayValue", ""))
            try:
                m_int = int(clk.replace("'", "").split("+")[0])
                minutos_goles.append(m_int)
            except:
                pass
    if minutos_goles:
        return min(minutos_goles)
    return max(1, min_actual_fallback)

def actualizar_bitacora_oculta_over05(
    ev_id, nombre_liga, nombre_cruce, st_state, es_ht, min_num,
    goles_tot, stats, prob_pre, tasa_1t, tasa_2t, tasa_38_45,
    senal_activada, motivo_senal, detalles_partido
):
    hubo_cambio = False
    ahora_str = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M")

    if senal_activada and goles_tot == 0 and min_num >= 18 and ev_id not in boveda_ml_05:
        boveda_ml_05[ev_id] = {
            "Fecha_Hora": ahora_str,
            "Liga": nombre_liga,
            "Partido": nombre_cruce,
            "Min_Alerta": min_num,
            "Motivo_Decision": motivo_senal,
            "Disparos_Al_Activar": f"{stats['toth_l']}-{stats['toth_v']} (Tot: {stats['toth_tot']})",
            "Arco_Al_Activar": f"{stats['tmeta_l']}-{stats['tmeta_v']} (Tot: {stats['tmeta_tot']})",
            "Corneres_Al_Activar": f"{stats['esquinas_l']}-{stats['esquinas_v']} (Tot: {stats['esquinas_tot']})",
            "Posesion_Al_Activar": f"{stats['pos_l']}% - {stats['pos_v']}%",
            "Prob_Pre_Over15": f"{prob_pre}%",
            "Tasa_Gol_1T": f"{tasa_1t}%",
            "Tasa_Gol_2T": f"{tasa_2t}%",
            "Tasa_Franja_38_45": f"{tasa_38_45}%",
            "Estado_Apuesta_05": "⏳ EN CURSO (0-0)",
            "Minuto_Gol": "Pendiente",
            "Minutos_Despues_De_18": "Pendiente",
            "Tiempo_Espera_Desde_Alerta": "Pendiente",
            "Marcador_Actual": "0 - 0"
        }
        hubo_cambio = True

    if ev_id in boveda_ml_05:
        reg = boveda_ml_05[ev_id]
        if goles_tot >= 1 and reg["Estado_Apuesta_05"].startswith("⏳"):
            min_gol = extraer_primer_minuto_gol(detalles_partido, min_num)
            min_despues_18 = max(1, min_gol - 18)
            min_desde_alerta = max(1, min_gol - int(reg["Min_Alerta"]))
            reg["Estado_Apuesta_05"] = "✅ GANADA (VERDE)"
            reg["Minuto_Gol"] = f"{min_gol}'"
            reg["Minutos_Despues_De_18"] = f"+{min_despues_18} min después del 18'"
            reg["Tiempo_Espera_Desde_Alerta"] = f"+{min_desde_alerta} min tras alerta ({reg['Min_Alerta']}')"
            hubo_cambio = True
        elif st_state == "post" and goles_tot == 0 and reg["Estado_Apuesta_05"] != "❌ FALLO (0-0 Final)":
            reg["Estado_Apuesta_05"] = "❌ FALLO (0-0 Final)"
            reg["Minuto_Gol"] = "Sin Gol (90')"
            reg["Minutos_Despues_De_18"] = "No cubrió línea"
            reg["Tiempo_Espera_Desde_Alerta"] = "Finalizó 0-0"
            hubo_cambio = True

    if hubo_cambio:
        guardar_boveda_ml_servidor(boveda_ml_05)

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
    if pos_l == 0 and pos_v == 0:
        pos_l, pos_v = 50, 50
    
    return {
        "toth_l": toth_l, "toth_v": toth_v, "toth_tot": toth_l + toth_v,
        "tmeta_l": tmeta_l, "tmeta_v": tmeta_v, "tmeta_tot": tmeta_l + tmeta_v,
        "tfuera_l": tfuera_l, "tfuera_v": tfuera_v, "tfuera_tot": tfuera_l + tfuera_v,
        "esquinas_l": esquinas_l, "esquinas_v": esquinas_v, "esquinas_tot": esquinas_l + esquinas_v,
        "pos_l": pos_l, "pos_v": pos_v
    }

def generar_boletin_html_imprimible(df_datos, titulo_reporte, subtitulo_reporte):
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

def enviar_bitacora_por_correo_privado(df_bitacora, password_app_gmail):
    remitente = "angelramirezzmiguel2@gmail.com"
    destinatario = "angelramirezzmiguel2@gmail.com"
    fecha_str = (datetime.utcnow() - timedelta(hours=6)).strftime("%d/%m/%Y %H:%M")

    msg = MIMEMultipart()
    msg["From"] = remitente
    msg["To"] = destinatario
    msg["Subject"] = f"🔒 [PRIVADO MRFUTBOL] Bitácora Entrenamiento Over 0.5 - {fecha_str}"

    cuerpo = (
        f"Hola Jefe Miguel Ramirez,\n\n"
        f"Adjunto el reporte privado de recolección en vivo del mercado Over 0.5 (Minuto 18+).\n"
        f"Total de partidos auditados en el servidor: {len(df_bitacora)}\n\n"
        f"Este reporte es confidencial y exclusivo para el entrenamiento del algoritmo MRFUTBOL."
    )
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    csv_bytes = df_bitacora.to_csv(index=False).encode("utf-8-sig")
    adjunto = MIMEBase("application", "octet-stream")
    adjunto.set_payload(csv_bytes)
    encoders.encode_base64(adjunto)
    adjunto.add_header("Content-Disposition", "attachment; filename=Bitacora_Over05_MRFUTBOL.csv")
    msg.attach(adjunto)

    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
    server.starttls()
    server.login(remitente, password_app_gmail.strip())
    server.send_message(msg)
    server.quit()

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

@st.cache_data(ttl=18)
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

# =============================================================================
# CONTROLES INDIVIDUALES DE ALERTAS Y FRAGMENTO EN VIVO SIN RECARGAR PÁGINA
# =============================================================================
col_master1, col_master2, col_master3 = st.columns([2.5, 1, 1])
with col_master2:
    master_sound = st.toggle("🔔 Mis Alertas Activas", value=True, key="master_sound_key")
with col_master3:
    auto_refresh = st.toggle("⚡ Refresco en Vivo (25s)", value=True, key="auto_refresh_key")

def disparar_alerta_individual(titulo, mensaje, icono="🔔"):
    """Dispara alerta sonora y visual ÚNICAMENTE en el navegador del usuario que sigue el partido"""
    if not master_sound:
        return
    hora_actual = (datetime.utcnow() - timedelta(hours=6)).strftime("%H:%M:%S")
    registro = f"[{hora_actual}] {icono} **{titulo}**: {mensaje}"
    hist_user = st.session_state["historial_notificaciones_usuario"]
    if not hist_user or hist_user[0] != registro:
        st.toast(f"**{titulo}**\n\n{mensaje}", icon=icono)
        hist_user.insert(0, registro)
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

def alternar_seguimiento_individual(ev_id, nombre_cruce, st_state, es_ht, gol_l, gol_v, rojas_actuales):
    """Activa o desactiva la campana de un partido solo para el usuario actual"""
    seguidos = st.session_state["seguidos_usuario"]
    if ev_id in seguidos:
        seguidos.remove(ev_id)
    else:
        seguidos.append(ev_id)
        st.session_state["memoria_eventos_usuario"][ev_id] = {
            "state": st_state,
            "ht_notificado": es_ht,
            "goles_l": gol_l,
            "goles_v": gol_v,
            "rojas": rojas_actuales
        }
        disparar_alerta_individual(f"Siguiendo: {nombre_cruce}", "Recibirás alertas de este partido en tu dispositivo.", "✅")

_fragment_fn = getattr(st, "fragment", getattr(st, "experimental_fragment", None))
intervalo_fragmento = 25 if auto_refresh else None

def _envolver_fragmento(func):
    if _fragment_fn is not None:
        return _fragment_fn(run_every=intervalo_fragmento)(func)
    return func

@_envolver_fragmento
def renderizar_central_mrfutbol():
    ahora_hn_dt = datetime.utcnow() - timedelta(hours=6)
    ahora_hn_str = ahora_hn_dt.strftime("%d/%m/%Y %H:%M:%S")
    str_hoy = ahora_hn_dt.strftime("%Y-%m-%d")
    str_manana = (ahora_hn_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    with col_master1:
        st.caption(
            f"💡 Central de Trading Deportivo MRFUTBOL | 🕒 Sincronizado: **{ahora_hn_str}** | "
            f"🔔 Mis Partidos Seguidos: **{len(st.session_state['seguidos_usuario'])}**"
        )

    codigos_todas = [l["code"] for l in LIGAS_BIG_DATA]
    datos_globales = obtener_partidos_ligas(codigos_todas)
    stats_temporada_api, eficiencias_ligas_api = obtener_estadisticas_temporada_reales(codigos_todas)
    lista_segunda_fuente = obtener_datos_segunda_fuente()

    def obtener_eficiencia_dinamica_liga(meta_liga):
        code = meta_liga["code"]
        efec_base = float(meta_liga["efec"])
        if code in eficiencias_ligas_api:
            efec_viva = round((efec_base * 0.65) + (eficiencias_ligas_api[code] * 0.35), 1)
            return f"{efec_viva}% (Activa)"
        return f"{efec_base}%"

    # 1. MONITOREO EN SEGUNDO PLANO:
    # - Recolecta en silencio la bitácora Over 0.5 para el Admin (sin sonar jamás).
    # - Revisa únicamente los partidos que ESTE usuario marcó con su campana individual.
    for nombre_liga, contenido in datos_globales.items():
        for evento in contenido["eventos"]:
            ev_id = str(evento.get("id"))
            comp = evento.get("competitions", [{}])[0]
            st_state, es_ht, min_num, _, _ = detectar_estado_partido(comp, evento.get("date", ""))
            competitors = comp.get("competitors", [])
            if len(competitors) != 2:
                continue

            loc, vis = competitors[0], competitors[1]
            nom_l_full = loc.get("team", {}).get("displayName", "Local")
            nom_v_full = vis.get("team", {}).get("displayName", "Visita")
            nom_l = loc.get("team", {}).get("shortDisplayName", nom_l_full)
            nom_v = vis.get("team", {}).get("shortDisplayName", nom_v_full)
            nombre_cruce = f"{nom_l} vs {nom_v}"

            gol_l = int(loc.get("score", 0) or 0)
            gol_v = int(vis.get("score", 0) or 0)
            goles_tot = gol_l + gol_v
            detalles_partido = comp.get("details", [])
            rojas_actuales = sum(1 for d in detalles_partido if d.get("redCard", False))

            # Recolector silencioso de Bóveda Over 0.5 (Min 18+)
            if st_state == "in" or es_ht or ev_id in boveda_ml_05:
                prob_pre, _, xg_pre, _ = calcular_pre_poisson_real(nom_l_full, nom_v_full, stats_temporada_api)
                stats_raw = extraer_metricas_partido_reales(loc, vis)
                _, _, stats, _ = cruzar_validacion_doble_fuente(nom_l_full, nom_v_full, stats_raw, lista_segunda_fuente)
                toth_l, toth_v, toth_tot = stats["toth_l"], stats["toth_v"], stats["toth_tot"]
                tmeta_tot = stats["tmeta_tot"]
                esq_tot = stats["esquinas_tot"]
                max_disp_equipo = max(toth_l, toth_v)
                equipo_dominante = nom_l if toth_l >= toth_v else nom_v

                tasa_1t, tasa_2t, tasa_38_45 = calcular_tasas_tiempos_y_franja(xg_pre, toth_tot, tmeta_tot, esq_tot, min_num)
                senal_bitacora_05 = (
                    (st_state == "in" or es_ht)
                    and goles_tot == 0
                    and (min_num >= 18 or es_ht)
                    and (max_disp_equipo >= 3 or tmeta_tot >= 2 or toth_tot >= 5 or (35 <= min_num <= 45 and tasa_38_45 >= 52.0 and toth_tot >= 3))
                )
                motivo_bitacora = f"{equipo_dominante} {max_disp_equipo} Disp ({toth_tot} Tot, {tmeta_tot} Arco, {esq_tot} Córn)"
                actualizar_bitacora_oculta_over05(
                    ev_id, nombre_liga, nombre_cruce, st_state, es_ht, min_num,
                    goles_tot, stats, prob_pre, tasa_1t, tasa_2t, tasa_38_45,
                    senal_bitacora_05, motivo_bitacora, detalles_partido
                )

            # Verificación de alertas INDIVIDUALES de este usuario
            if ev_id in st.session_state["seguidos_usuario"] and ev_id in st.session_state["memoria_eventos_usuario"]:
                mem = st.session_state["memoria_eventos_usuario"][ev_id]
                if mem["state"] == "pre" and st_state == "in":
                    disparar_alerta_individual("⏳ ¡ARRANCÓ EL PARTIDO!", f"{nombre_cruce} (0-0)", "🟢")
                if es_ht and not mem.get("ht_notificado", False):
                    disparar_alerta_individual("⏸️ ENTRETIEMPO (HT)", f"{nombre_cruce} | Marcador: {gol_l}-{gol_v}", "⏱️")
                    mem["ht_notificado"] = True
                if (gol_l + gol_v) > (mem["goles_l"] + mem["goles_v"]):
                    disparar_alerta_individual(f"⚽ ¡GOL EN {nombre_cruce}!", f"Nuevo marcador: {gol_l}-{gol_v}", "⚽")
                elif (gol_l + gol_v) < (mem["goles_l"] + mem["goles_v"]):
                    disparar_alerta_individual("❌ ¡GOL ANULADO (VAR)!", f"{nombre_cruce} vuelve a {gol_l}-{gol_v}", "🚫")
                if rojas_actuales > mem["rojas"]:
                    disparar_alerta_individual("🟥 ¡TARJETA ROJA!", f"Expulsión en {nombre_cruce}", "🟥")
                if mem["state"] != "post" and st_state == "post":
                    disparar_alerta_individual("🏁 FINAL DEL PARTIDO", f"{nombre_cruce} terminó {gol_l}-{gol_v}", "🏁")

                mem.update({
                    "state": st_state,
                    "goles_l": gol_l,
                    "goles_v": gol_v,
                    "rojas": rojas_actuales
                })

    sec_resultados, sec_en_vivo, sec_apuestas, sec_scraping = st.tabs([
        "⚽ 1. CARTELERA DE HOY", 
        "🔴 2. PARTIDOS EN VIVO", 
        "🎯 3. PRE-APUESTAS Y REPORTES", 
        "🚨 4. SCRAPING Y TERMINAL 0.5"
    ])

    # -------------------------------------------------------------------------
    # SECCIÓN 1: CARTELERA DE HOY / MAÑANA (ALERTAS INDIVIDUALES EN VIVO O POR INICIAR)
    # -------------------------------------------------------------------------
    with sec_resultados:
        col_menu, col_contenido = st.columns([1.2, 3.8])

        with col_menu:
            st.markdown("##### 📅 Cartelera Activa")
            opciones_dia = {
                f"🟢 Hoy ({ahora_hn_dt.strftime('%d/%m')})": str_hoy,
                f"⏭️ Mañana ({(ahora_hn_dt + timedelta(days=1)).strftime('%d/%m')})": str_manana,
            }
            etiqueta_dia_sel = st.radio("Seleccionar Día:", list(opciones_dia.keys()), index=0, label_visibility="collapsed")
            fecha_objetivo_portada = opciones_dia[etiqueta_dia_sel]

            ocultar_finalizados = st.toggle("👁️ Ocultar Finalizados", value=True)

            st.markdown("##### 📌 Ligas Disponibles")
            nombres_ligas = [l["id"] for l in LIGAS_BIG_DATA]
            liga_seleccionada_panel = st.selectbox("Filtrar Liga:", ["🌍 Todas las Ligas"] + nombres_ligas, label_visibility="collapsed")
            texto_busqueda_raw = st.text_input("🔍 Buscar Equipo...", "", placeholder="Ej. Real Madrid, Barcelona...")
            if st.button("🔄 Forzar Refresco Manual", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

            st.caption(f"📡 Eventos en vivo respaldados por 2da Fuente: **{len(lista_segunda_fuente)}**")

            # MODO CAMUFLAJE + EXPANDER: Si escribes MR2026 en el buscador o en la bóveda, solo se abre en TU navegador
            modo_admin_buscador = (texto_busqueda_raw.strip() == "MR2026")
            texto_busqueda = "" if modo_admin_buscador else texto_busqueda_raw

            with st.expander("🔐 Bóveda Privada (Admin)", expanded=modo_admin_buscador):
                pin_admin = st.text_input("Clave de Dueño:", type="password", key="pin_admin_input")
                if pin_admin == "MR2026" or modo_admin_buscador:
                    st.success("🔓 Acceso Exclusivo en tu Navegador: Miguel Ramirez")
                    registros_ml = list(boveda_ml_05.values())
                    st.caption(f"📊 Señales Over 0.5 recolectadas (Min 18+): **{len(registros_ml)}**")
                    if registros_ml:
                        df_ml_privado = pd.DataFrame(registros_ml)
                        ganadas_ml = sum(1 for r in registros_ml if "GANADA" in r["Estado_Apuesta_05"])
                        fallos_ml = sum(1 for r in registros_ml if "FALLO" in r["Estado_Apuesta_05"])
                        st.metric("🎯 Efectividad Over 0.5", f"{ganadas_ml} Verdes / {fallos_ml} Rojos")

                        st.download_button(
                            label="📥 Descargar Bitácora Privada (.CSV)",
                            data=df_ml_privado.to_csv(index=False).encode("utf-8-sig"),
                            file_name=f"Bitacora_Privada_Over05_{str_hoy}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

                        clave_gmail = st.text_input(
                            "Clave de Aplicación Gmail (para envío directo):",
                            type="password",
                            help="Ingresa tu contraseña de aplicación de 16 letras de Google para enviar el CSV directo a angelramirezzmiguel2@gmail.com"
                        )
                        if st.button("✉️ Enviar Bitácora a mi Correo", use_container_width=True):
                            if clave_gmail:
                                try:
                                    enviar_bitacora_por_correo_privado(df_ml_privado, clave_gmail)
                                    st.success("✅ Enviado con éxito a angelramirezzmiguel2@gmail.com")
                                except Exception as e:
                                    st.error(f"No se pudo conectar al servidor SMTP: {e}")
                            else:
                                st.warning("Ingresa tu Clave de Aplicación de Gmail o usa el botón de descarga directa arriba.")
                    else:
                        st.info("Aún no se han disparado señales de Over 0.5 (Min 18+) en esta jornada.")

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
                    sello_val, nivel_val, stats, _ = cruzar_validacion_doble_fuente(nom_l_full, nom_v_full, stats_raw, lista_segunda_fuente)

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
                                st.caption(f"🛡️ **Auditoría MRFUTBOL:** {sello_val} | Confianza: **{nivel_val}**")
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
                        # SOLO SE PUEDE ACTIVAR ALERTA EN PARTIDOS EN VIVO O POR INICIAR (COMO CUALQUIER APP DE FÚTBOL)
                        if st_state in ("pre", "in") or es_ht:
                            ya_seguido = ev_id in st.session_state["seguidos_usuario"]
                            st.checkbox(
                                "🔔 Seguir",
                                value=ya_seguido,
                                key=f"bell_tab1_{ev_id}_{ya_seguido}",
                                on_change=alternar_seguimiento_individual,
                                args=(ev_id, nombre_cruce, st_state, es_ht, gol_l, gol_v, rojas_actuales)
                            )
                        else:
                            st.caption("🏁 Final")

            if not hay_partidos_jornada:
                st.info(f"No hay partidos en vivo o programados para {etiqueta_dia_sel}.")

        if st.session_state["historial_notificaciones_usuario"]:
            with st.expander("📲 Mis Alertas Recientes (Solo en mi dispositivo)", expanded=False):
                for notif in st.session_state["historial_notificaciones_usuario"][:8]:
                    st.info(notif)

    # -------------------------------------------------------------------------
    # SECCIÓN 2: PARTIDOS EN VIVO (CON OPCIÓN DE SEGUIMIENTO INDIVIDUAL)
    # -------------------------------------------------------------------------
    with sec_en_vivo:
        st.subheader("🔴 Partidos en Vivo y Auditoría Cruzada MRFUTBOL")
        st.caption("Puedes activar tu campana individual 🔔 en cualquier partido en curso para recibir alertas de gol en tu dispositivo.")
        
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

                st_state, es_ht, _, badge_vivo, _ = detectar_estado_partido(comp, ev.get("date", ""))
                detalles_partido = comp.get("details", [])
                rojas_actuales = sum(1 for d in detalles_partido if d.get("redCard", False))
                stats_raw = extraer_metricas_partido_reales(loc, vis)
                sello_val, nivel_val, stats, _ = cruzar_validacion_doble_fuente(nom_l_full, nom_v_full, stats_raw, lista_segunda_fuente)

                col_v_card, col_v_bell = st.columns([10, 2])
                with col_v_card:
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
                with col_v_bell:
                    ya_seguido_vivo = ev_id in st.session_state["seguidos_usuario"]
                    st.checkbox(
                        "🔔 Seguir",
                        value=ya_seguido_vivo,
                        key=f"bell_tab2_{ev_id}_{ya_seguido_vivo}",
                        on_change=alternar_seguimiento_individual,
                        args=(ev_id, nombre_cruce, st_state, es_ht, gol_l, gol_v, rojas_actuales)
                    )

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

    # -------------------------------------------------------------------------
    # SECCIÓN 3: PRE-APUESTAS OVER 1.5 (CON % 1T, % 2T Y FRANJA 38'-45')
    # -------------------------------------------------------------------------
    with sec_apuestas:
        st.subheader("🎯 Laboratorio Pre-Apuesta Over 1.5 y Tasas por Tiempo (1T / 2T)")
        st.caption("Cruza los goles reales de temporada con la base MRFUTBOL y desglosa la probabilidad de gol en el 1er Tiempo, cierre del 1T (38'-45') y 2do Tiempo.")

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
                    tasa_1t, tasa_2t, tasa_38_45 = calcular_tasas_tiempos_y_franja(xg_base, 0, 0, 0, 0)

                    if prob_final >= umbral_minimo:
                        if 64.0 <= prob_final <= 75.5:
                            veredicto = "💎 ENTRAR OVER 1.5 (Cuota de Valor / Stake 2%)"
                        elif prob_final > 75.5:
                            veredicto = "🟢 ENTRAR OVER 1.5 (Fijo Alta Probabilidad / Stake 3%)"
                        else:
                            veredicto = "🟡 VALOR MODERADO (Ideal Operar 0.5 en Vivo)"

                        reporte_pre.append({
                            "Fecha": fecha_legible,
                            "Liga": nombre_liga,
                            "Partido": f"{nom_local} vs {nom_visita}",
                            "xG": xg_base,
                            "Prob. Over 1.5": f"{prob_final}%",
                            "⏱️ Gol 1T": f"{tasa_1t}%",
                            "⚡ Cierre 38'-45'": f"{tasa_38_45}%",
                            "🔥 Gol 2T": f"{tasa_2t}%",
                            "Cuota Justa": cuota_justa,
                            "Respaldo": fuente_tag,
                            "Veredicto": veredicto
                        })

        if reporte_pre:
            df_pre = pd.DataFrame(reporte_pre)
            st.dataframe(df_pre, use_container_width=True, hide_index=True)

            col_rep1, col_rep2 = st.columns(2)
            with col_rep1:
                html_boletin_pre = generar_boletin_html_imprimible(
                    df_pre,
                    "REPORTE PRE-APUESTAS OVER 1.5 Y TASAS 1T/2T",
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

    # -------------------------------------------------------------------------
    # SECCIÓN 4: TERMINAL DE TRADING Y SCRAPING EN VIVO (100% LIBRE DE ALERTAS)
    # -------------------------------------------------------------------------
    with sec_scraping:
        st.subheader("🚨 Terminal de Trading en Vivo (Mercado Over 0.5 / 1.5 por Franjas de Tiempo)")
        st.markdown(
            "**Modo Silencioso de Trading:** Aquí no existen campanas ni alertas molestas. "
            "Los partidos **`0 - 0`** se mantienen fijos en la cima y la ventana se actualiza sola cada **25 segundos** sin mover tu pantalla."
        )

        tabla_scraping = []

        for nombre_liga, contenido in datos_globales.items():
            for evento in contenido["eventos"]:
                ev_id = str(evento.get("id"))
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
                    nombre_cruce = f"{nom_l} vs {nom_v}"

                    goles_l = int(loc.get("score", 0) or 0)
                    goles_v = int(vis.get("score", 0) or 0)
                    goles_tot = goles_l + goles_v

                    prob_pre, _, xg_pre, _ = calcular_pre_poisson_real(nom_l_full, nom_v_full, stats_temporada_api)
                    stats_raw = extraer_metricas_partido_reales(loc, vis)
                    sello_val, nivel_val, stats, _ = cruzar_validacion_doble_fuente(
                        nom_l_full, nom_v_full, stats_raw, lista_segunda_fuente
                    )

                    toth_l, toth_v, toth_tot = stats["toth_l"], stats["toth_v"], stats["toth_tot"]
                    tmeta_l, tmeta_v, tmeta_tot = stats["tmeta_l"], stats["tmeta_v"], stats["tmeta_tot"]
                    esq_l, esq_v, esq_tot = stats["esquinas_l"], stats["esquinas_v"], stats["esquinas_tot"]
                    pos_l, pos_v = stats["pos_l"], stats["pos_v"]

                    max_disp_equipo = max(toth_l, toth_v)
                    equipo_dominante = nom_l if toth_l >= toth_v else nom_v
                    posesion_pareja = (42 <= pos_l <= 58)

                    tasa_1t, tasa_2t, tasa_38_45 = calcular_tasas_tiempos_y_franja(
                        xg_pre, toth_tot, tmeta_tot, esq_tot, min_num
                    )

                    clase_caja_veredicto = "veredicto-box-wait"
                    es_oportunidad_caliente = False

                    if goles_tot == 0:
                        if min_num < 18 and not es_ht:
                            if posesion_pareja and tmeta_tot <= 1 and esq_tot <= 2:
                                veredicto_vivo = (
                                    f"⏳ Min {min_num}' (Estudio Parejo: Pos {pos_l}%-{pos_v}%, {tmeta_tot} Arco, {esq_tot} Córn). "
                                    f"AGUANTAR: Estos rivales registran {tasa_1t}% Gol en 1T (Pico 38'-45': {tasa_38_45}%) y {tasa_2t}% en 2T. Esperar min 18+."
                                )
                            else:
                                veredicto_vivo = (
                                    f"⚡ Arranque con Ritmo ({toth_tot} Disp, {tmeta_tot} Arco, {esq_tot} Córn) | "
                                    f"Tasa 1T: {tasa_1t}% (Franja 38'-45': {tasa_38_45}%) | Tasa 2T: {tasa_2t}%. Esperando confirmación min 18."
                                )
                        else:
                            if max_disp_equipo >= 3 or tmeta_tot >= 2 or toth_tot >= 5 or (35 <= min_num <= 45 and tasa_38_45 >= 52.0 and toth_tot >= 3):
                                es_oportunidad_caliente = True
                                clase_caja_veredicto = "veredicto-box-hot"

                                if 35 <= min_num <= 45 and not es_ht:
                                    veredicto_vivo = (
                                        f"🚨 ¡ENTRAR OVER 0.5 (ZONA CALIENTE 38'-45')! {equipo_dominante} suma {max_disp_equipo} disp "
                                        f"(Tot: {toth_tot} Disp, {tmeta_tot} Arco, {esq_tot} Córn) 👉 Pico de Cierre 1T: {tasa_38_45}% | Respaldo 2T: {tasa_2t}%."
                                    )
                                elif es_ht or min_num > 45:
                                    veredicto_vivo = (
                                        f"🚨 ¡ENTRAR AL OVER 0.5 GOLES EN 2T! ({equipo_dominante} lleva {max_disp_equipo} disp | "
                                        f"Tot: {toth_tot} Disp, {tmeta_tot} Arco, {esq_tot} Córn) 👉 ¡SIN MIEDO AL 0-0! Tasa de Gol en 2do Tiempo: {tasa_2t}%."
                                    )
                                else:
                                    veredicto_vivo = (
                                        f"🚨 ¡ENTRAR AL OVER 0.5 GOLES! ({equipo_dominante} ya suma {max_disp_equipo} disp | "
                                        f"Tot: {toth_tot} Disp, {tmeta_tot} Arco, {esq_tot} Córn) 👉 Tasa 1T: {tasa_1t}% (Cierre 38'-45': {tasa_38_45}%) | Tasa 2T: {tasa_2t}%."
                                    )
                            else:
                                if tasa_38_45 >= 48.0 or tasa_2t >= 74.0:
                                    veredicto_vivo = (
                                        f"⏸️ Trámite Trabado al {reloj_txt} (Pos {pos_l}%-{pos_v}%, {tmeta_tot} Arco, {esq_tot} Córn). "
                                        f"AGUANTAR CUOTA: Rivales fuertes en el cierre 38'-45' ({tasa_38_45}%) y en el 2T ({tasa_2t}%). Esperar que suba el momio."
                                    )
                                else:
                                    veredicto_vivo = (
                                        f"🚫 PRECAUCIÓN / NO ENTRAR AÚN ({toth_tot} Disp, {tmeta_tot} Arco, {esq_tot} Córn) | "
                                        f"Ritmo bajo en cancha. Solo operar si despiertan los disparos en el 2T ({tasa_2t}%)."
                                    )
                    elif goles_tot == 1:
                        if min_num <= 82 and (max_disp_equipo >= 3 or tmeta_tot >= 3 or toth_tot >= 6):
                            clase_caja_veredicto = "veredicto-box-hot"
                            veredicto_vivo = (
                                f"🔥 ¡OVER 0.5 COBRADO! Oportunidad en OVER 1.5 GOLES ({toth_tot} Disp, {tmeta_tot} Arco, {esq_tot} Córn | "
                                f"Tasa de Gol en 2T: {tasa_2t}%)."
                            )
                        else:
                            clase_caja_veredicto = "veredicto-box-green"
                            veredicto_vivo = f"✅ ¡OVER 0.5 YA COBRADO EN VERDE ({goles_l}-{goles_v})! Ritmo moderado ({toth_tot} Disp | Potencial 2T: {tasa_2t}%)."
                    else:
                        clase_caja_veredicto = "veredicto-box-green"
                        veredicto_vivo = f"✅ ¡LÍNEAS OVER 0.5 Y OVER 1.5 COBRADAS EN VERDE! ({goles_l}-{goles_v})"

                    item_ordenado = {
                        "_goles_tot": goles_tot,
                        "_es_caliente": 0 if es_oportunidad_caliente else 1,
                        "_prob_pre": prob_pre,
                        "Reloj": reloj_txt,
                        "Liga": nombre_liga,
                        "Partido": nombre_cruce,
                        "Marcador": f"{goles_l} - {goles_v}",
                        "📈 Pre Over 1.5": f"{prob_pre}% (xG {xg_pre})",
                        "⏱️ Gol 1T": f"{tasa_1t}%",
                        "⚡ Cierre 38'-45'": f"{tasa_38_45}%",
                        "🔥 Gol 2T": f"{tasa_2t}%",
                        "🎯 Disparos": f"{toth_l}-{toth_v} (Tot: {toth_tot})",
                        "🥅 Al Arco": f"{tmeta_l}-{tmeta_v} (Tot: {tmeta_tot})",
                        "🚩 Córn | Pos": f"{esq_l}-{esq_v} | {pos_l}%-{pos_v}%",
                        "🛡️ Auditoría MRFUTBOL": sello_val,
                        "💡 Veredicto Táctico": veredicto_vivo,
                        "_clase_caja": clase_caja_veredicto,
                        "_card_hot": es_oportunidad_caliente
                    }
                    tabla_scraping.append(item_ordenado)

        if tabla_scraping:
            tabla_scraping.sort(key=lambda x: (x["_goles_tot"], x["_es_caliente"], -x["_prob_pre"]))

            st.markdown("#### 🖥️ Monitor Amplio de Decisiones en Vivo (Prioridad `0 - 0` Arriba)")
            for item in tabla_scraping:
                card_cls = "trading-card-hot" if item["_card_hot"] else "trading-card"
                st.markdown(f"""
                <div class="{card_cls}">
                    <div class="trading-header">
                        <div>
                            <span style="background:#ff2a4b; color:#fff; padding:3px 8px; border-radius:4px; font-weight:800; font-size:12px;">{item['Reloj']}</span>
                            &nbsp; <strong style="font-size:15px; color:#ffffff;">{item['Partido']}</strong>
                            &nbsp; <span style="background:#16181f; color:#00ffcc; padding:3px 10px; border-radius:4px; font-weight:900; font-size:14px; border:1px solid #00ffcc;">{item['Marcador']}</span>
                        </div>
                        <div style="font-size:12px; color:#9ba1b0;">
                            {item['Liga']} &nbsp;|&nbsp; {item['🛡️ Auditoría MRFUTBOL']}
                        </div>
                    </div>
                    <div class="trading-metrics-grid">
                        <div class="metric-pill"><span>📈 Esperado Pre</span><strong>{item['📈 Pre Over 1.5']}</strong></div>
                        <div class="metric-pill"><span>⏱️ Tasa Gol 1T</span><strong>{item['⏱️ Gol 1T']}</strong></div>
                        <div class="metric-pill"><span>⚡ Cierre 38'-45'</span><strong>{item['⚡ Cierre 38\'-45\'']}</strong></div>
                        <div class="metric-pill"><span>🔥 Tasa Gol 2T</span><strong>{item['🔥 Gol 2T']}</strong></div>
                        <div class="metric-pill"><span>🎯 Disparos (L-V)</span><strong>{item['🎯 Disparos']}</strong></div>
                        <div class="metric-pill"><span>🥅 Tiros al Arco</span><strong>{item['🥅 Al Arco']}</strong></div>
                        <div class="metric-pill"><span>🚩 Córn | Posesión</span><strong>{item['🚩 Córn | Pos']}</strong></div>
                    </div>
                    <div class="{item['_clase_caja']}">
                        {item['💡 Veredicto Táctico']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            filas_limpias = []
            for fila in tabla_scraping:
                copia = {k: v for k, v in fila.items() if not k.startswith("_")}
                filas_limpias.append(copia)

            df_scr = pd.DataFrame(filas_limpias)
            with st.expander("📋 Ver en Formato Tabla Completa y Descargar Reportes", expanded=False):
                st.dataframe(df_scr, use_container_width=True, hide_index=True)

                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    html_boletin_vivo = generar_boletin_html_imprimible(
                        df_scr,
                        "REPORTE DE TRADING EN VIVO (OVER 0.5 / 1.5)",
                        "Auditoría Dual MRFUTBOL"
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

renderizar_central_mrfutbol()
