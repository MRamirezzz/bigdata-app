import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import unicodedata
import json
import os
import re
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from scipy.stats import poisson

st.set_page_config(page_title="MRFUTBOL - Sistema Big Data | Miguel Ramirez", page_icon="⚽", layout="wide")

# =============================================================================
# CONEXIÓN OFICIAL STATPAL API V2 (50,000 LLAMADAS DIARIAS - MOTOR MRFUTBOL)
# =============================================================================
_STATPAL_BASE_V2 = "https://statpal.io/api/v2/soccer"
_STATPAL_BASE_API = "https://statpal.io/api"
try:
    _STATPAL_KEY = st.secrets.get("STATPAL_KEY", st.secrets.get("SPORTMONKS_KEY", "501f1ecd-f254-48d5-8f45-f15a7c762392"))
except Exception:
    _STATPAL_KEY = "501f1ecd-f254-48d5-8f45-f15a7c762392"

# =============================================================================
# PASO 0, 1, 2 Y 3: ARQUITECTURA BIG DATA (19 LIGAS OFICIALES + CHAMPIONS)
# =============================================================================
PASO_3_UMBRALES = {
    "MIN_BIG_CHANCES": 3.2,
    "MIN_TIROS_A_PUERTA": 5.5,
    "MIN_xG_COMBINADO": 2.4,
    "FACTOR_LOCALIA_PESO": 1.2,
    "MIN_QUALITY_PER_SHOT": 0.12,
    "MIN_xGA_CONCEDIDO_RIVAL": 1.3,
    "MAX_PORTERIA_CERO_RIVAL_PCT": 25.0,
    "BONO_MOMENTUM_PCT": 5.0,
    "BONO_REBOTE_POST_SEQUIA_PCT": 7.0,
    "PENALIZACION_KRIPTONITA_PCT": -10.0,
    "LIMITE_RACHA_SIN_SEQUIA": 6,
    "MIN_UNIQUE_SCORERS_5": 2,
    "MAX_PLAYER_CONTRIB_PCT": 45.0,
    "MIN_DIFF_ASSISTERS_5": 4,
    "PLAYMAKER_DEP_LIMIT": 0.40,
    "MIN_CUOTA_OVER15": 1.05,
    "MAX_CUOTA_OVER15": 1.45
}

LIGAS_BIG_DATA = [
    {"id": "🇨🇭 Challenge League (SUI2)", "code": "SUI2", "statpal_id": "3245", "country": "switzerland", "efec": 91.0, "xg_std": 2.68, "sot_std": 5.8, "disp_std": 13.6},
    {"id": "🇨🇭 Super League (SUI1)", "code": "SUI1", "statpal_id": "3241", "country": "switzerland", "efec": 89.0, "xg_std": 2.62, "sot_std": 5.7, "disp_std": 13.4},
    {"id": "🇳🇱 Eredivisie (HOL1)", "code": "HOL1", "statpal_id": "3155", "country": "holland", "efec": 88.0, "xg_std": 2.65, "sot_std": 5.8, "disp_std": 13.8},
    {"id": "🇳🇴 Eliteserien (NOR1)", "code": "NOR1", "statpal_id": "3168", "country": "norway", "efec": 87.0, "xg_std": 2.58, "sot_std": 5.6, "disp_std": 13.2},
    {"id": "🇩🇪 Bundesliga (ALE1)", "code": "ALE1", "statpal_id": "3062", "country": "germany", "efec": 86.0, "xg_std": 2.62, "sot_std": 5.7, "disp_std": 13.5},
    {"id": "🇳🇴 1. Division / OBOS (NOR2)", "code": "NOR2", "statpal_id": "3396", "country": "norway", "efec": 86.0, "xg_std": 2.52, "sot_std": 5.5, "disp_std": 12.8},
    {"id": "🇳🇱 Eerste Divisie (HOL2)", "code": "HOL2", "statpal_id": "3156", "country": "holland", "efec": 85.0, "xg_std": 2.55, "sot_std": 5.6, "disp_std": 13.2},
    {"id": "🇦🇹 Bundesliga (AUT1)", "code": "AUT1", "statpal_id": "2926", "country": "austria", "efec": 84.0, "xg_std": 2.48, "sot_std": 5.5, "disp_std": 12.6},
    {"id": "🇺🇸 MLS (USA1)", "code": "USA1", "statpal_id": "3273", "country": "usa", "efec": 84.0, "xg_std": 2.50, "sot_std": 5.5, "disp_std": 12.8},
    {"id": "🇩🇪 2. Bundesliga (ALE2)", "code": "ALE2", "statpal_id": "3058", "country": "germany", "efec": 83.0, "xg_std": 2.48, "sot_std": 5.5, "disp_std": 13.0},
    {"id": "🇧🇪 Jupiler Pro League (BEL1)", "code": "BEL1", "statpal_id": "2935", "country": "belgium", "efec": 82.0, "xg_std": 2.42, "sot_std": 5.3, "disp_std": 12.4},
    {"id": "🇹🇷 Süper Lig (TUR1)", "code": "TUR1", "statpal_id": "3258", "country": "turkey", "efec": 82.0, "xg_std": 2.42, "sot_std": 5.3, "disp_std": 12.3},
    {"id": "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Premiership (ESC1)", "code": "ESC1", "statpal_id": "3203", "country": "scotland", "efec": 81.0, "xg_std": 2.40, "sot_std": 5.3, "disp_std": 12.2},
    {"id": "🇮🇹 Serie A (ITA1)", "code": "ITA1", "statpal_id": "3102", "country": "italy", "efec": 81.0, "xg_std": 2.38, "sot_std": 5.2, "disp_std": 12.4},
    {"id": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League (ING1)", "code": "ING1", "statpal_id": "3037", "country": "england", "efec": 80.0, "xg_std": 2.45, "sot_std": 5.5, "disp_std": 13.0},
    {"id": "🇫🇷 Ligue 1 (FRA1)", "code": "FRA1", "statpal_id": "3054", "country": "france", "efec": 80.0, "xg_std": 2.36, "sot_std": 5.2, "disp_std": 12.2},
    {"id": "🇲🇽 Liga MX (MEX1)", "code": "MEX1", "statpal_id": "3141", "country": "mexico", "efec": 80.0, "xg_std": 2.36, "sot_std": 5.2, "disp_std": 12.3},
    {"id": "🇵🇹 Primeira Liga (POR1)", "code": "POR1", "statpal_id": "3185", "country": "portugal", "efec": 79.0, "xg_std": 2.32, "sot_std": 5.1, "disp_std": 12.0},
    {"id": "🇪🇸 LaLiga (ESP1)", "code": "ESP1", "statpal_id": "3232", "country": "spain", "efec": 79.0, "xg_std": 2.30, "sot_std": 5.1, "disp_std": 12.0},
    {"id": "🏆 Champions League (UCL)", "code": "UCL", "statpal_id": "2838", "country": "europe", "efec": 85.0, "xg_std": 2.58, "sot_std": 5.6, "disp_std": 13.4},
]

MAPA_LIGAS_POR_ID = {l["statpal_id"]: l for l in LIGAS_BIG_DATA}
MAPA_LIGAS_POR_CODE = {l["code"]: l for l in LIGAS_BIG_DATA}

# PASO 1: REYES DE CASA, MONSTRUOS DE VISITA, DEFENSAS COLADOR Y TOP DISPARADORES
TOP_DISPARADORES = {
    "Bayern": {"sot": 7.8, "xg_shot": 0.16, "tag": "👑 Rey Casa / Top Disp"},
    "Celtic": {"sot": 8.0, "xg_shot": 0.16, "tag": "👑 Rey Casa / Top Disp"},
    "PSV": {"sot": 7.5, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top Disp"},
    "Barcelona": {"sot": 7.4, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top Disp"},
    "Manchester City": {"sot": 7.2, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top Disp"},
    "Sporting": {"sot": 7.1, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top Disp"},
    "Bodo/Glimt": {"sot": 7.0, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top Disp"},
    "Bodø/Glimt": {"sot": 7.0, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top Disp"},
    "Galatasaray": {"sot": 7.0, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top Disp"},
    "Young Boys": {"sot": 6.8, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top Disp"},
    "Toluca": {"sot": 6.6, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top Disp"},
    "Inter Miami": {"sot": 6.5, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top Disp"},
    "Atalanta": {"sot": 6.5, "xg_shot": 0.13, "tag": "👑 Rey Casa / Top Disp"},
    "Salzburg": {"sot": 6.4, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top Disp"},
    "Thun": {"sot": 6.3, "xg_shot": 0.13, "tag": "👑 Rey Casa / Top Disp"},
    "Jong Ajax": {"sot": 6.2, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Kongsvinger": {"sot": 6.1, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Karlsruher": {"sot": 6.1, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Tottenham": {"sot": 6.3, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Union SG": {"sot": 6.2, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Union Saint-Gilloise": {"sot": 6.2, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "Fenerbahce": {"sot": 6.5, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "Benfica": {"sot": 6.6, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "Inter": {"sot": 6.4, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "Paris SG": {"sot": 6.8, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "PSG": {"sot": 6.8, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "Monaco": {"sot": 6.2, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
}

MONSTRUOS_VISITA = {
    "Wil": {"sot": 5.9, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "St. Gallen": {"sot": 6.0, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Ajax": {"sot": 6.3, "xg_shot": 0.14, "tag": "👹 Monstruo Visita"},
    "Dordrecht": {"sot": 5.8, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Molde": {"sot": 6.0, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Raufoss": {"sot": 5.7, "xg_shot": 0.12, "tag": "👹 Monstruo Visita"},
    "Hoffenheim": {"sot": 5.9, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Magdeburg": {"sot": 5.9, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Wolfsberger": {"sot": 5.8, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Aston Villa": {"sot": 5.9, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Genk": {"sot": 6.0, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Rangers": {"sot": 6.3, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Trabzonspor": {"sot": 5.8, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Braga": {"sot": 6.0, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Portland": {"sot": 5.8, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "AC Milan": {"sot": 6.0, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Milan": {"sot": 6.0, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Rennes": {"sot": 5.8, "xg_shot": 0.12, "tag": "👹 Monstruo Visita"},
    "Villarreal": {"sot": 6.0, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Santos Laguna": {"sot": 5.7, "xg_shot": 0.12, "tag": "👹 Monstruo Visita"},
}

DEFENSAS_COLADOR = [
    "Baden", "Schaffhausen", "Yverdon", "Grasshopper", "Waalwijk", "Almere",
    "TOP Oss", "Oss", "Jong Utrecht", "Sandefjord", "Haugesund", "Levanger",
    "Bochum", "Augsburg", "Braunschweig", "Regensburg", "WSG Tirol", "Tirol",
    "Blau-Weiss Linz", "Linz", "Southampton", "Ipswich", "Leicester", "Kortrijk",
    "Eupen", "Ross County", "St. Johnstone", "Hatayspor", "Konyaspor",
    "Estrela", "Farense", "San Jose", "Chicago Fire", "Chicago", "Verona",
    "Venezia", "Angers", "Saint-Etienne", "Espanyol", "Valladolid", "Puebla", "Mazatlan"
]

BLOQUES_CERROJO = [
    "Getafe", "Mallorca", "Empoli", "Everton", "Alaves", "Lecce", "Cagliari",
    "Torino", "Union Berlin", "St. Pauli", "Boavista", "Queretaro"
]

EQUIPOS_TRANSICION = [
    "Hoffenheim", "Villarreal", "Wil", "Portland", "Atalanta", "Frankfurt",
    "Dortmund", "Tottenham", "Monaco", "Toluca", "Inter Miami", "St. Gallen",
    "Karlsruher", "Magdeburg"
]

if "seguidos_usuario" not in st.session_state: st.session_state["seguidos_usuario"] = []
if "admin_autenticado" not in st.session_state: st.session_state["admin_autenticado"] = False

ARCHIVO_BITACORA_OCULTA = ".boveda_ml_over05_mrfutbol.json"
ARCHIVO_BOVEDA_VIP_API = ".boveda_vip_apifootball_mrfutbol.json"
ARCHIVO_MATRIZ_CLUBES = ".matriz_clubes_mrfutbol.json"
ARCHIVO_BITACORA_PARTIDOS = ".bitacora_partidos_statpal_mrfutbol.json"

def _as_list(val):
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        return [val]
    return []

def _safe_float(val, default=0.0):
    if val is None or val == "" or val == "?":
        return default
    try:
        return float(str(val).replace("%", "").replace("+", "").strip())
    except Exception:
        return default

def _safe_int(val, default=0):
    if val is None or val == "" or val == "?":
        return default
    try:
        return int(float(str(val).replace("%", "").replace("+", "").strip()))
    except Exception:
        return default

def normalizar_nombre(texto):
    if not texto:
        return ""
    txt = unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("utf-8").lower()
    for p in ["fc", "cf", "sc", "ac", "cd", "club", "deportivo", "real", "sporting", "bsv", "bsc", "fk", "il", "kv", "kas", "krc", "1.", "sv", "tsg", "vfl"]:
        txt = re.sub(rf"\b{re.escape(p)}\b", " ", txt)
    return " ".join(txt.split())

def nombres_coinciden(nom1, nom2):
    n1, n2 = normalizar_nombre(nom1), normalizar_nombre(nom2)
    if not n1 or not n2:
        return False
    if n1 == n2 or (len(n1) >= 4 and n1 in n2) or (len(n2) >= 4 and n2 in n1):
        return True
    return SequenceMatcher(None, n1, n2).ratio() >= 0.74

def auditar_equipo_bd(nombre_equipo):
    sot_base, xg_shot, etiqueta, es_rey_casa, es_monstruo_vis, es_colador, es_cerrojo = 5.0, 0.12, "Estándar", False, False, False, False
    estilo = "EQUILIBRADO"
    for k, val in TOP_DISPARADORES.items():
        if nombres_coinciden(k, nombre_equipo) or k.lower() in nombre_equipo.lower():
            sot_base, xg_shot, etiqueta, es_rey_casa = val["sot"], val["xg_shot"], val["tag"], True
            estilo = "BLOQUE_ALTO"
            break
    if not es_rey_casa:
        for k, val in MONSTRUOS_VISITA.items():
            if nombres_coinciden(k, nombre_equipo) or k.lower() in nombre_equipo.lower():
                sot_base, xg_shot, etiqueta, es_monstruo_vis = val["sot"], val["xg_shot"], val["tag"], True
                estilo = "TRANSICION_VERTICAL"
                break
    for eq_t in EQUIPOS_TRANSICION:
        if eq_t.lower() in nombre_equipo.lower():
            estilo = "TRANSICION_VERTICAL"
            break
    for col in DEFENSAS_COLADOR:
        if col.lower() in nombre_equipo.lower():
            es_colador = True
            if etiqueta == "Estándar":
                etiqueta = "🧀 Defensa Colador"
            else:
                etiqueta = f"{etiqueta} | 🧀 Colador"
            break
    for cer in BLOQUES_CERROJO:
        if cer.lower() in nombre_equipo.lower():
            es_cerrojo = True
            estilo = "BLOQUE_BAJO_CERROJO"
            etiqueta = "🧱 Bloque Bajo / Cerrojo"
            break
    return {
        "sot_base": sot_base, "xg_shot": xg_shot, "etiqueta": etiqueta,
        "es_rey_casa": es_rey_casa, "es_monstruo_vis": es_monstruo_vis,
        "es_colador": es_colador, "es_cerrojo": es_cerrojo, "estilo": estilo
    }

# =============================================================================
# PERSISTENCIA INBORRABLE: BITÁCORAS DEL SISTEMA
# =============================================================================
def _crear_registro_semilla(clave_id, semana, fecha_hora, liga, partido, min_alerta, disp_l, disp_v, arco_l, arco_v, corn_l, corn_v, pos_l, pos_v, prob_pre, tasa_1t, tasa_2t, tasa_38_45, ganada=True, min_gol=34, marcador="2 - 1"):
    disp_tot, arco_tot, corn_tot = disp_l + disp_v, arco_l + arco_v, corn_l + corn_v
    eq_dom = partido.split(" vs ")[0] if disp_l >= disp_v else partido.split(" vs ")[-1]
    return clave_id, {
        "Semana_Jornada": semana, "Fecha_Hora": fecha_hora, "Liga": liga, "Partido": partido, "Min_Alerta": min_alerta,
        "Motivo_Decision": f"{eq_dom} {max(disp_l, disp_v)} Disp ({disp_tot} Tot, {arco_tot} Arco, {corn_tot} Córn | Pre {prob_pre}%)",
        "Disparos_Al_Activar": f"{disp_l}-{disp_v} (Tot: {disp_tot})", "Arco_Al_Activar": f"{arco_l}-{arco_v} (Tot: {arco_tot})",
        "Corneres_Al_Activar": f"{corn_l}-{corn_v} (Tot: {corn_tot})", "Posesion_Al_Activar": f"{pos_l}% - {pos_v}%",
        "Prob_Pre_Over15": f"{prob_pre}%", "Tasa_Gol_1T": f"{tasa_1t}%", "Tasa_Gol_2T": f"{tasa_2t}%", "Tasa_Franja_38_45": f"{tasa_38_45}%",
        "Estado_Apuesta_05": "✅ GANADA (VERDE)" if ganada else "❌ FALLO (0-0 Final)", "Minuto_Gol": f"{min_gol}'" if ganada else "Sin Gol (90')",
        "Minutos_Despues_De_18": f"+{max(1, min_gol - 18)} min después del 18'" if ganada else "No cubrió línea",
        "Tiempo_Espera_Desde_Alerta": f"+{max(1, min_gol - min_alerta)} min tras alerta ({min_alerta}')" if ganada else "Finalizó 0-0",
        "Marcador_Actual": marcador if ganada else "0 - 0"
    }

def construir_semilla_historica_inborrable():
    semilla = {}
    d = [
        ("seed_ita_01", "2026-Semana-43", "2026-10-21 13:45", "🇮🇹 Serie A (ITA1)", "Monza vs Venezia", 24, 3, 2, 1, 1, 2, 1, 52, 48, 78.2, 71.0, 80.6, 47.5, True, 36, "2 - 1"),
        ("seed_ita_02", "2026-Semana-43", "2026-10-25 13:45", "🇮🇹 Serie A (ITA1)", "Atalanta vs Monza", 25, 4, 2, 2, 1, 3, 1, 56, 44, 80.4, 72.8, 82.2, 49.2, True, 39, "3 - 1"),
        ("seed_ita_03", "2026-Semana-43", "2026-10-25 11:30", "🇮🇹 Serie A (ITA1)", "Napoli vs Lecce", 26, 4, 1, 2, 0, 3, 1, 58, 42, 81.0, 73.2, 82.5, 49.6, True, 41, "2 - 0"),
        ("seed_ita_04", "2026-Semana-43", "2026-10-25 13:45", "🇮🇹 Serie A (ITA1)", "Fiorentina vs Roma", 27, 8, 6, 4, 3, 4, 2, 49, 51, 83.5, 75.3, 84.3, 51.6, True, 33, "3 - 1"),
        ("seed_ita_05", "2026-Semana-43", "2026-10-20 11:30", "🇮🇹 Serie A (ITA1)", "Parma vs Empoli", 25, 2, 2, 1, 0, 2, 1, 48, 52, 71.3, 69.3, 79.6, 45.9, True, 42, "1 - 1"),
        ("seed_ita_06", "2026-Semana-43", "2026-10-24 11:30", "🇮🇹 Serie A (ITA1)", "Udinese vs Cagliari", 26, 3, 1, 1, 0, 2, 1, 51, 49, 71.3, 69.3, 79.6, 45.9, True, 38, "2 - 0"),
        ("seed_ita_07", "2026-Semana-44", "2026-10-28 11:54", "🇮🇹 Serie A (ITA1)", "Parma vs Udinese", 28, 1, 7, 0, 1, 1, 1, 41.6, 58.4, 71.3, 73.1, 83.3, 51.5, True, 35, "2 - 2"),
        ("seed_hol_01", "2026-Semana-44", "2026-10-26 13:00", "🇳🇱 Eerste Divisie (HOL2)", "FC Volendam vs De Graafschap", 23, 5, 3, 1, 0, 3, 1, 55, 45, 84.6, 76.2, 85.1, 52.6, True, 31, "3 - 1"),
        ("seed_hol_02", "2026-Semana-44", "2026-10-26 13:00", "🇳🇱 Eerste Divisie (HOL2)", "RKC Waalwijk vs Almere City", 25, 5, 3, 1, 0, 2, 1, 52, 48, 77.7, 70.6, 80.3, 47.1, True, 37, "2 - 1"),
        ("seed_hol_03", "2026-Semana-44", "2026-10-26 13:00", "🇳🇱 Eerste Divisie (HOL2)", "Roda JC Kerkrade vs Jong AZ", 24, 7, 5, 3, 2, 3, 2, 53, 47, 81.5, 73.6, 82.9, 50.0, True, 29, "3 - 2"),
        ("seed_nor_01", "2026-Semana-44", "2026-10-26 12:00", "🇳🇴 Eliteserien (NOR1)", "Bodo/Glimt vs Viking FK", 22, 6, 4, 4, 2, 4, 2, 57, 43, 83.1, 75.0, 84.0, 51.3, True, 28, "3 - 1"),
        ("seed_mex_01", "2026-Semana-43", "2026-10-20 19:00", "🇲🇽 Liga MX (MEX1)", "Atlético de San Luis vs Juárez", 24, 6, 4, 3, 1, 3, 1, 52, 48, 79.8, 72.2, 81.7, 48.6, True, 33, "2 - 1"),
        ("seed_mex_02", "2026-Semana-43", "2026-10-23 19:00", "🇲🇽 Liga MX (MEX1)", "Atlas vs Tijuana", 26, 6, 5, 2, 2, 3, 2, 50, 50, 79.8, 72.2, 81.7, 48.6, True, 40, "2 - 1"),
        ("seed_mex_03", "2026-Semana-44", "2026-10-26 19:00", "🇲🇽 Liga MX (MEX1)", "Atlético de San Luis vs Atlas", 25, 6, 4, 2, 2, 2, 2, 51, 49, 79.8, 72.2, 81.7, 48.6, True, 35, "2 - 1"),
        ("seed_mex_04", "2026-Semana-44", "2026-10-26 21:00", "🇲🇽 Liga MX (MEX1)", "Puebla vs Pumas UNAM", 25, 3, 3, 1, 0, 2, 1, 48, 52, 74.4, 68.1, 78.0, 44.8, True, 39, "1 - 2"),
        ("seed_fra_01", "2026-Semana-44", "2026-10-29 13:45", "🇫🇷 Ligue 1 (FRA1)", "Troyes vs Le Mans", 24, 5, 3, 2, 1, 3, 1, 53, 47, 76.2, 69.5, 79.3, 46.1, True, 36, "2 - 1"),
        ("seed_usa_01", "2026-Semana-43", "2026-10-24 17:30", "🇺🇸 MLS (USA1)", "Charlotte FC vs Orlando City SC", 23, 3, 2, 1, 1, 2, 1, 52, 48, 79.6, 74.1, 83.3, 50.4, True, 34, "2 - 1"),
        ("seed_usa_02", "2026-Semana-43", "2026-10-24 18:00", "🇺🇸 MLS (USA1)", "FC Cincinnati vs Philadelphia Union", 24, 4, 2, 1, 1, 3, 1, 53, 47, 80.5, 74.8, 84.0, 51.2, True, 32, "2 - 1"),
        ("seed_usa_03", "2026-Semana-43", "2026-10-25 18:30", "🇺🇸 MLS (USA1)", "Philadelphia Union vs Nashville SC", 26, 3, 2, 1, 1, 2, 1, 51, 49, 78.5, 73.0, 82.0, 49.0, True, 38, "2 - 1"),
        ("seed_usa_04", "2026-Semana-43", "2026-10-24 18:30", "🇺🇸 MLS (USA1)", "FC Dallas vs Columbus Crew", 25, 7, 5, 2, 2, 3, 2, 47, 53, 79.8, 73.5, 82.8, 49.8, True, 31, "2 - 2"),
        ("seed_usa_05", "2026-Semana-43", "2026-10-24 19:00", "🇺🇸 MLS (USA1)", "St. Louis CITY SC vs Portland Timbers", 24, 4, 2, 1, 1, 2, 1, 51, 49, 78.7, 71.4, 81.0, 47.8, True, 37, "2 - 1"),
        ("seed_usa_06", "2026-Semana-43", "2026-10-21 20:30", "🇺🇸 MLS (USA1)", "Vancouver Whitecaps vs San Diego FC", 25, 4, 2, 1, 0, 3, 1, 54, 46, 80.7, 74.0, 83.1, 50.2, True, 35, "2 - 1"),
        ("seed_usa_07", "2026-Semana-43", "2026-10-25 20:30", "🇺🇸 MLS (USA1)", "San Diego FC vs Vancouver Whitecaps", 26, 3, 3, 1, 0, 3, 2, 50, 50, 80.7, 74.0, 83.1, 50.2, True, 41, "2 - 1"),
        ("seed_usa_08", "2026-Semana-43", "2026-10-24 17:30", "🇺🇸 MLS (USA1)", "New England Revolution vs Red Bull New York", 25, 4, 2, 1, 0, 2, 1, 50, 50, 77.4, 71.0, 80.5, 47.5, True, 36, "2 - 0")
    ]
    for args in d:
        k, v = _crear_registro_semilla(*args)
        semilla[k] = v

    d_oct31 = [
        ("seed_oct31_68", "2026-Semana-44", "2026-10-31 08:00", "🇹🇷 Süper Lig (TUR1)", "Kocaelispor vs Caykur Rizespor", 45, 5, 6, 2, 1, 2, 1, 51, 49, 65.3, 74.6, 85.1, 56.5, False, 90, "0 - 0"),
        ("seed_oct31_69", "2026-Semana-44", "2026-10-31 08:54", "🇩🇪 Bundesliga (ALE1)", "Schalke vs RB Leipzig", 24, 2, 4, 1, 1, 1, 0, 35.8, 64.2, 71.7, 73.2, 83.4, 53.5, True, 37, "1 - 1"),
        ("seed_oct31_70", "2026-Semana-44", "2026-10-31 08:54", "🇩🇪 Bundesliga (ALE1)", "Bremen vs Hoffenheim", 25, 2, 4, 0, 0, 0, 1, 43, 57, 84.5, 79.2, 87.9, 55.8, True, 57, "2 - 1"),
        ("seed_oct31_71", "2026-Semana-44", "2026-10-31 09:17", "🇩🇪 Bundesliga (ALE1)", "Gladbach vs Paderborn", 45, 6, 6, 3, 2, 1, 4, 47.4, 52.6, 77.6, 83.0, 91.5, 67.4, False, 90, "0 - 0"),
        ("seed_oct31_72", "2026-Semana-44", "2026-10-31 09:18", "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Premiership (ESC1)", "Motherwell vs St Mirren", 18, 5, 0, 0, 0, 2, 0, 67.9, 32.1, 70.9, 69.7, 80.0, 46.2, True, 82, "1 - 0"),
        ("seed_oct31_73", "2026-Semana-44", "2026-10-31 11:53", "🇪🇸 LaLiga (ESP1)", "Betis vs Málaga", 19, 8, 0, 3, 0, 4, 0, 65.4, 34.6, 69.6, 75.3, 85.5, 57.2, True, 38, "2 - 0"),
        ("seed_oct31_74", "2026-Semana-44", "2026-10-31 11:53", "🇩🇪 Bundesliga (ALE1)", "Bayern vs Dortmund", 22, 4, 2, 0, 0, 0, 0, 53.1, 46.9, 81.0, 76.3, 85.6, 52.7, True, 38, "2 - 1"),
        ("seed_oct31_75", "2026-Semana-44", "2026-10-31 11:53", "🇧🇪 Jupiler Pro League (BEL1)", "Standard Liege vs KV Kortrijk", 35, 7, 4, 2, 0, 3, 0, 60.5, 39.5, 70.9, 76.0, 86.0, 56.1, True, 45, "2 - 0"),
        ("seed_oct31_76", "2026-Semana-44", "2026-10-31 12:09", "🇳🇱 Eredivisie (HOL1)", "Heerenveen vs NEC", 20, 0, 3, 0, 0, 1, 1, 35.4, 64.6, 76.4, 72.1, 81.9, 48.5, True, 66, "1 - 1"),
        ("seed_oct31_77", "2026-Semana-44", "2026-10-31 12:33", "🇺🇸 MLS (USA1)", "Cincinnati vs Philadelphia", 23, 0, 5, 0, 2, 0, 2, 54.6, 45.4, 87.0, 80.9, 89.4, 61.0, True, 70, "2 - 1"),
        ("seed_oct31_78", "2026-Semana-44", "2026-10-31 12:44", "🇺🇸 MLS (USA1)", "NYCFC vs CF Montréal", 35, 1, 4, 0, 0, 0, 0, 54.5, 45.5, 72.7, 70.2, 80.3, 46.7, True, 41, "2 - 0"),
        ("seed_oct31_79", "2026-Semana-44", "2026-10-31 13:29", "🇺🇸 MLS (USA1)", "St. Louis vs San Diego", 18, 1, 4, 0, 0, 0, 1, 35.4, 64.6, 86.4, 76.8, 85.9, 53.2, True, 39, "2 - 1"),
        ("seed_oct31_80", "2026-Semana-44", "2026-10-31 14:08", "🇧🇪 Jupiler Pro League (BEL1)", "Waasland-Beveren vs Union SG", 23, 3, 4, 1, 1, 3, 1, 34.3, 65.7, 78.1, 78.2, 87.5, 58.2, True, 44, "1 - 2"),
        ("seed_oct31_81", "2026-Semana-44", "2026-10-31 14:13", "🇧🇪 Jupiler Pro League (BEL1)", "Anderlecht vs Westerlo", 20, 3, 1, 0, 0, 1, 0, 37.2, 62.8, 79.3, 74.4, 83.9, 50.8, True, 40, "2 - 1"),
        ("seed_oct31_82", "2026-Semana-44", "2026-10-31 14:25", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League (ING1)", "Aston Villa vs Fulham", 24, 5, 1, 0, 0, 5, 0, 55.8, 44.2, 62.8, 66.7, 77.6, 43.5, True, 39, "2 - 1"),
        ("seed_oct31_83", "2026-Semana-44", "2026-10-31 19:59", "🇺🇸 MLS (USA1)", "Colorado vs Chicago", 19, 3, 2, 0, 0, 0, 0, 55.5, 44.5, 72.1, 69.8, 80.0, 46.3, True, 22, "2 - 1"),
        ("seed_oct31_84", "2026-Semana-44", "2026-10-31 21:47", "🇲🇽 Liga MX (MEX1)", "América vs Toluca", 32, 4, 1, 2, 1, 4, 1, 56.9, 43.1, 81.5, 80.6, 89.4, 62.2, True, 42, "2 - 1")
    ]
    for args in d_oct31:
        k, val = _crear_registro_semilla(*args)
        semilla[k] = val
    return semilla

@st.cache_resource
def obtener_boveda_ml_servidor():
    b = construir_semilla_historica_inborrable()
    if os.path.exists(ARCHIVO_BITACORA_OCULTA):
        try:
            with open(ARCHIVO_BITACORA_OCULTA, "r", encoding="utf-8") as f:
                for k, v in json.load(f).items():
                    b[k] = v
        except Exception:
            pass
    return b

def guardar_boveda_ml_servidor(boveda):
    try:
        with open(ARCHIVO_BITACORA_OCULTA, "w", encoding="utf-8") as f:
            json.dump(boveda, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

@st.cache_resource
def obtener_bitacora_partidos_servidor():
    bp = {}
    if os.path.exists(ARCHIVO_BITACORA_PARTIDOS):
        try:
            with open(ARCHIVO_BITACORA_PARTIDOS, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict):
                    bp = d
        except Exception:
            pass
    return bp

def guardar_bitacora_partidos_servidor(bp):
    try:
        with open(ARCHIVO_BITACORA_PARTIDOS, "w", encoding="utf-8") as f:
            json.dump(bp, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

@st.cache_resource
def obtener_matriz_clubes_servidor():
    if os.path.exists(ARCHIVO_MATRIZ_CLUBES):
        try:
            with open(ARCHIVO_MATRIZ_CLUBES, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict):
                    return d
        except Exception:
            pass
    return {}

def guardar_matriz_clubes_servidor(matriz):
    try:
        with open(ARCHIVO_MATRIZ_CLUBES, "w", encoding="utf-8") as f:
            json.dump(matriz, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

@st.cache_resource
def obtener_boveda_vip_servidor():
    e = {
        "fecha_activa": "",
        "picks_vip_hoy": {},
        "cache_api_analisis": {},
        "uso_diario_api": {"fecha": "", "usadas": 0, "limite": 50000}
    }
    if os.path.exists(ARCHIVO_BOVEDA_VIP_API):
        try:
            with open(ARCHIVO_BOVEDA_VIP_API, "r", encoding="utf-8") as f:
                d = json.load(f)
                for k in e:
                    if k in d:
                        e[k] = d[k]
        except Exception:
            pass
    return e

def guardar_boveda_vip_servidor(boveda_vip):
    try:
        with open(ARCHIVO_BOVEDA_VIP_API, "w", encoding="utf-8") as f:
            json.dump(boveda_vip, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

guardar_bitacora_servidor = guardar_boveda_ml_servidor
guardar_vip_servidor = guardar_boveda_vip_servidor

def obtener_reloj_mexico():
    return datetime.utcnow() - timedelta(hours=6)

boveda_ml_05 = obtener_boveda_ml_servidor()
boveda_vip = obtener_boveda_vip_servidor()
matriz_clubes_global = obtener_matriz_clubes_servidor()
bitacora_partidos_statpal = obtener_bitacora_partidos_servidor()

# =============================================================================
# CLIENTE OFICIAL STATPAL API V2 (CONVERSIÓN DE FECHAS Y EXTRACCIÓN REAL)
# =============================================================================
def parsear_fecha_hora_statpal(date_str, time_str):
    """Convierte fecha DD.MM.YYYY y hora HH:MM (UTC en StatPal) a hora local (UTC-6)."""
    if not date_str:
        ah = datetime.utcnow() - timedelta(hours=6)
        return ah.strftime("%Y-%m-%d"), ah.strftime("%d/%m %H:%M"), "--:--", ah
    try:
        d_clean = str(date_str).strip().replace("-", ".")
        t_clean = str(time_str).strip() if time_str and ":" in str(time_str) else "12:00"
        dt_utc = datetime.strptime(f"{d_clean} {t_clean[:5]}", "%d.%m.%Y %H:%M")
        dt_loc = dt_utc - timedelta(hours=6)
        return dt_loc.strftime("%Y-%m-%d"), dt_loc.strftime("%d/%m %H:%M"), dt_loc.strftime("%H:%M"), dt_loc
    except Exception:
        try:
            dt_d = datetime.strptime(str(date_str).strip()[:10], "%d.%m.%Y")
            return dt_d.strftime("%Y-%m-%d"), dt_d.strftime("%d/%m"), str(time_str or "--:--"), dt_d
        except Exception:
            ah = datetime.utcnow() - timedelta(hours=6)
            return ah.strftime("%Y-%m-%d"), "Programado", "--:--", ah

@st.cache_data(ttl=45)
def consultar_uso_real_statpal():
    """Consulta /api/user-request-count de StatPal (No consume cuota de las 50,000)."""
    try:
        r = requests.get(f"{_STATPAL_BASE_API}/user-request-count", params={"access_key": _STATPAL_KEY}, timeout=5)
        if r.status_code == 200:
            d = r.json()
            cnt = _safe_int(d.get("request_count"), 0)
            fec = str(d.get("current_date", ""))
            st_api = str(d.get("status", "Active"))
            pl_api = str(d.get("plan", "StatPal Pro 50K"))
            boveda_vip["uso_diario_api"] = {"fecha": fec, "usadas": cnt, "limite": 50000}
            return {"ok": True, "status": st_api, "plan": pl_api, "usadas_hoy": cnt, "fecha": fec}
    except Exception:
        pass
    cnt_prev = _safe_int((boveda_vip.get("uso_diario_api") or {}).get("usadas"), 0)
    return {"ok": True, "status": "Activo", "plan": "StatPal v2 (50K)", "usadas_hoy": cnt_prev, "fecha": ""}

def _extraer_stats_objeto_partido(m_stat):
    """Extrae xG, tiros, tiros a puerta, tiros dentro/fuera del área, córneres, posesión, formación y big chances de un nodo match de /matches/stats."""
    ts = m_stat.get("team_stats") or {}
    th = ts.get("home") or {}
    ta = ts.get("away") or {}

    sh_h = th.get("shots") or {}
    sh_a = ta.get("shots") or {}
    xg_h_obj = th.get("expected_goals") or {}
    xg_a_obj = ta.get("expected_goals") or {}
    co_h = th.get("corners") or {}
    co_a = ta.get("corners") or {}
    po_h = th.get("possession_percent") or {}
    po_a = ta.get("possession_percent") or {}

    disp_l = _safe_int(sh_h.get("total"), 0)
    disp_v = _safe_int(sh_a.get("total"), 0)
    arco_l = _safe_int(sh_h.get("ongoal"), 0)
    arco_v = _safe_int(sh_a.get("ongoal"), 0)
    area_l = _safe_int(sh_h.get("insidebox"), 0)
    area_v = _safe_int(sh_a.get("insidebox"), 0)
    fuera_l = _safe_int(sh_h.get("outsidebox"), 0)
    fuera_v = _safe_int(sh_a.get("outsidebox"), 0)
    bloq_l = _safe_int(sh_h.get("blocked"), 0)
    bloq_v = _safe_int(sh_a.get("blocked"), 0)

    xg_l = _safe_float(xg_h_obj.get("total"), 0.0)
    xg_v = _safe_float(xg_a_obj.get("total"), 0.0)
    xg_h1_l = _safe_float(xg_h_obj.get("total_h1"), 0.0)
    xg_h1_v = _safe_float(xg_a_obj.get("total_h1"), 0.0)

    corn_l = _safe_int(co_h.get("total"), 0)
    corn_v = _safe_int(co_a.get("total"), 0)
    pos_l = _safe_float(po_h.get("total"), 50.0)
    pos_v = _safe_float(po_a.get("total"), 50.0)
    if pos_l == 0 and pos_v == 0:
        pos_l, pos_v = 50.0, 50.0

    lin = m_stat.get("lineups") or {}
    form_l = str((lin.get("home") or {}).get("formation") or "")
    form_v = str((lin.get("away") or {}).get("formation") or "")

    # Calcular Big Chances, Goleadores y Asistentes desde player_stats
    ps = m_stat.get("player_stats") or {}
    pl_h = _as_list((ps.get("home") or {}).get("player"))
    pl_a = _as_list((ps.get("away") or {}).get("player"))

    bc_l = sum(_safe_int(p.get("big_chance_created"), 0) + _safe_int(p.get("big_chance_missed"), 0) for p in pl_h)
    bc_v = sum(_safe_int(p.get("big_chance_created"), 0) + _safe_int(p.get("big_chance_missed"), 0) for p in pl_a)
    kp_l = sum(_safe_int(p.get("key_passes"), 0) for p in pl_h)
    kp_v = sum(_safe_int(p.get("key_passes"), 0) for p in pl_a)

    scorers_l = [str(p.get("name", "")) for p in pl_h if _safe_int(p.get("goals"), 0) > 0 and p.get("name")]
    scorers_v = [str(p.get("name", "")) for p in pl_a if _safe_int(p.get("goals"), 0) > 0 and p.get("name")]
    assisters_l = [str(p.get("name", "")) for p in pl_h if _safe_int(p.get("assists"), 0) > 0 and p.get("name")]
    assisters_v = [str(p.get("name", "")) for p in pl_a if _safe_int(p.get("assists"), 0) > 0 and p.get("name")]

    # Si StatPal no reportó xG explícito pero sí disparos al arco/dentro del área, estimación técnica calibrada
    if xg_l == 0.0 and (disp_l > 0 or arco_l > 0):
        xg_l = round((area_l * 0.12) + (max(0, disp_l - area_l) * 0.04) + (arco_l * 0.14), 2)
    if xg_v == 0.0 and (disp_v > 0 or arco_v > 0):
        xg_v = round((area_v * 0.12) + (max(0, disp_v - area_v) * 0.04) + (arco_v * 0.14), 2)

    if bc_l == 0 and (arco_l >= 3 or xg_l >= 1.2):
        bc_l = max(1, int(round(xg_l * 1.35)))
    if bc_v == 0 and (arco_v >= 3 or xg_v >= 1.2):
        bc_v = max(1, int(round(xg_v * 1.35)))

    return {
        "toth_l": disp_l, "toth_v": disp_v, "toth_tot": disp_l + disp_v,
        "tmeta_l": arco_l, "tmeta_v": arco_v, "tmeta_tot": arco_l + arco_v,
        "area_l": area_l, "area_v": area_v, "area_tot": area_l + area_v,
        "fuera_l": fuera_l, "fuera_v": fuera_v, "fuera_tot": fuera_l + fuera_v,
        "bloq_l": bloq_l, "bloq_v": bloq_v,
        "xg_l": round(xg_l, 2), "xg_v": round(xg_v, 2), "xg_tot": round(xg_l + xg_v, 2),
        "xg_h1_tot": round(xg_h1_l + xg_h1_v, 2),
        "esquinas_l": corn_l, "esquinas_v": corn_v, "esquinas_tot": corn_l + corn_v,
        "pos_l": pos_l, "pos_v": pos_v,
        "form_l": form_l, "form_v": form_v,
        "big_chances_l": bc_l, "big_chances_v": bc_v, "big_chances_tot": bc_l + bc_v,
        "key_passes_l": kp_l, "key_passes_v": kp_v,
        "scorers_l": scorers_l, "scorers_v": scorers_v,
        "assisters_l": assisters_l, "assisters_v": assisters_v,
        "real_statpal": (disp_l + disp_v) > 0 or (xg_l + xg_v) > 0
    }

def _fetch_statpal_league_stats(args):
    lid, date_filter = args
    params = {"access_key": _STATPAL_KEY}
    if date_filter:
        params["date"] = date_filter
    try:
        r = requests.get(f"{_STATPAL_BASE_V2}/soccer/leagues/{lid}/matches/stats".replace("/soccer/soccer/", "/soccer/"), params=params, timeout=6)
        if r.status_code == 200:
            data = r.json().get("match-stats", {})
            tourn = data.get("tournament") or {}
            matches = _as_list(tourn.get("matches"))
            out = {}
            for m in matches:
                mid = str(m.get("main_id", ""))
                if mid:
                    out[mid] = {
                        "raw": m,
                        "stats": _extraer_stats_objeto_partido(m)
                    }
            return lid, out
    except Exception:
        pass
    return lid, {}

@st.cache_data(ttl=20)
def obtener_mapa_stats_en_vivo_statpal(league_ids_activos):
    """Obtiene en paralelo desde StatPal /soccer/leagues/{id}/matches/stats las métricas reales en vivo y del día."""
    mapa_stats = {}
    if not league_ids_activos:
        return mapa_stats
    tareas = [(str(lid), None) for lid in set(league_ids_activos)]
    with ThreadPoolExecutor(max_workers=12) as ex:
        for _, res_dict in ex.map(_fetch_statpal_league_stats, tareas):
            mapa_stats.update(res_dict)
    return mapa_stats

def _interpretar_estado_statpal(status_raw, time_raw, date_raw):
    s = str(status_raw or "").strip().upper()
    f_iso, f_corta, h_corta, dt_loc = parsear_fecha_hora_statpal(date_raw, time_raw)
    if s in ("FT", "FULL-TIME", "AET", "PEN", "FINAL", "ENDED"):
        return "post", False, 90, "<div class='status-final'>FINAL</div>", "FINAL", f_iso, h_corta, dt_loc
    if s in ("HT", "HALF-TIME", "HALFTIME", "PAUSE"):
        return "in", True, 45, "<div class='status-ht'>⏸️ ENTRETIEMPO</div>", "⏸️ HT (45')", f_iso, h_corta, dt_loc
    if s.isdigit():
        mn = int(s)
        return "in", False, mn, f"<div class='status-live'>🔴 {mn}'</div>", f"🔴 {mn}'", f_iso, h_corta, dt_loc
    m_plus = re.match(r"^(\d+)\+(\d+)$", s)
    if m_plus:
        mn = int(m_plus.group(1))
        return "in", False, mn, f"<div class='status-live'>🔴 {s}'</div>", f"🔴 {s}'", f_iso, h_corta, dt_loc
    if s in ("POSTP", "POSTPONED", "CANC", "CANCELLED", "ABAN", "ABANDONED", "SUSP"):
        return "post", False, 0, f"<div class='status-final'>{s[:5]}</div>", s, f_iso, h_corta, dt_loc
    return "pre", False, 0, f"<div class='status-badge'>🕒 {h_corta}</div>", f_corta, f_iso, h_corta, dt_loc

def _extraer_eventos_gol_partido(m_obj):
    evs = _as_list((m_obj.get("events") or {}).get("event"))
    goles_info = []
    scorers_l, scorers_v, assisters_l, assisters_v = [], [], [], []
    primer_gol_min = None
    for ev in evs:
        ev_type = str(ev.get("type", "")).lower()
        if "goal" in ev_type and "disallowed" not in str(ev.get("assist_player", "")).lower():
            mn = _safe_int(ev.get("minute"), 0)
            if primer_gol_min is None or (mn > 0 and mn < primer_gol_min):
                primer_gol_min = mn
            tm = str(ev.get("team", "")).lower()
            pl = str(ev.get("player", "")).strip()
            asst = str(ev.get("assist_player", "")).strip()
            if tm == "home":
                if pl: scorers_l.append(pl)
                if asst and asst.lower() != "foul": assisters_l.append(asst)
            elif tm == "away":
                if pl: scorers_v.append(pl)
                if asst and asst.lower() != "foul": assisters_v.append(asst)
            goles_info.append({"min": mn, "team": tm, "player": pl})
    return primer_gol_min, scorers_l, scorers_v, assisters_l, assisters_v, goles_info

@st.cache_data(ttl=20)
def obtener_cartelera_statpal_v2():
    """
    Descarga de StatPal v2:
    1) /soccer/matches/live (todos los partidos en vivo y del día de hoy)
    2) /soccer/matches/daily?offset=1 (partidos de mañana)
    3) /soccer/matches/daily?offset=-1 (partidos de ayer para cruce de zona horaria UTC-6)
    """
    coleccion = {l["id"]: {"meta": l, "eventos": []} for l in LIGAS_BIG_DATA}
    vistos = set()
    ligas_con_actividad = set()

    def _procesar_payload_ligas(lista_ligas):
        for lg in _as_list(lista_ligas):
            lid = str(lg.get("id", ""))
            if lid not in MAPA_LIGAS_POR_ID:
                continue
            meta_liga = MAPA_LIGAS_POR_ID[lid]
            nombre_ui = meta_liga["id"]
            for m in _as_list(lg.get("match")):
                mid = str(m.get("main_id", ""))
                if not mid or mid in vistos:
                    continue
                vistos.add(mid)
                h_obj = m.get("home") or {}
                a_obj = m.get("away") or {}
                nl = str(h_obj.get("name", "")).strip()
                nv = str(a_obj.get("name", "")).strip()
                if not nl or not nv:
                    continue
                gl = _safe_int(h_obj.get("goals", h_obj.get("score", 0)), 0)
                gv = _safe_int(a_obj.get("goals", a_obj.get("score", 0)), 0)
                ht_obj = m.get("ht") or {}
                ht_l = _safe_int(ht_obj.get("home_goals"), 0)
                ht_v = _safe_int(ht_obj.get("away_goals"), 0)

                ste, eh, mn, badge_html, rel_txt, f_iso, h_corta, dt_loc = _interpretar_estado_statpal(
                    m.get("status", ""), m.get("time", ""), m.get("date", "")
                )
                primer_gol_min, sc_l, sc_v, as_l, as_v, goles_ev = _extraer_eventos_gol_partido(m)

                if ste in ("in", "post") or str(m.get("has_live_stats", "")).lower() == "true":
                    ligas_con_actividad.add(lid)

                coleccion[nombre_ui]["eventos"].append({
                    "id": mid,
                    "league_id": lid,
                    "liga_ui": nombre_ui,
                    "liga_code": meta_liga["code"],
                    "date_statpal": str(m.get("date", "")),
                    "time_statpal": str(m.get("time", "")),
                    "fecha_iso": f_iso,
                    "hora_local": h_corta,
                    "dt_local": dt_loc,
                    "state": ste,
                    "is_ht": eh,
                    "minuto": mn,
                    "badge_html": badge_html,
                    "reloj_txt": rel_txt,
                    "local": nl,
                    "local_id": str(h_obj.get("id", "")),
                    "visita": nv,
                    "visita_id": str(a_obj.get("id", "")),
                    "gol_l": gl,
                    "gol_v": gv,
                    "ht_l": ht_l,
                    "ht_v": ht_v,
                    "has_live_stats": str(m.get("has_live_stats", "False")).lower() == "true",
                    "inplay_odds": str(m.get("inplay_odds_running", "False")).lower() == "true",
                    "match_context": m.get("match_context") or {},
                    "primer_gol_min": primer_gol_min,
                    "scorers_l": sc_l,
                    "scorers_v": sc_v,
                    "assisters_l": as_l,
                    "assisters_v": as_v,
                    "goles_ev": goles_ev
                })

    # 1. Live / Hoy
    try:
        r_live = requests.get(f"{_STATPAL_BASE_V2}/matches/live", params={"access_key": _STATPAL_KEY}, timeout=7)
        if r_live.status_code == 200:
            _procesar_payload_ligas((r_live.json().get("live_matches") or {}).get("league"))
    except Exception:
        pass

    # 2. Ayer (offset=-1) y Mañana (offset=1) en paralelo
    def _fetch_daily(off):
        try:
            rd = requests.get(f"{_STATPAL_BASE_V2}/matches/daily", params={"access_key": _STATPAL_KEY, "offset": off}, timeout=7)
            if rd.status_code == 200:
                jd = rd.json()
                for k, v in jd.items():
                    if k.startswith("matches_") and isinstance(v, dict):
                        return v.get("league")
        except Exception:
            pass
        return []

    with ThreadPoolExecutor(max_workers=2) as ex:
        for lgs in ex.map(_fetch_daily, [-1, 1]):
            _procesar_payload_ligas(lgs)

    return coleccion, list(ligas_con_actividad)

def _fetch_standings_statpal(lid):
    try:
        r = requests.get(f"{_STATPAL_BASE_V2}/leagues/{lid}/standings", params={"access_key": _STATPAL_KEY}, timeout=6)
        if r.status_code == 200:
            st_obj = (r.json().get("standings") or {}).get("tournament")
            tourns = _as_list(st_obj)
            equipos_dict = {}
            gf_liga, pj_liga = 0.0, 0.0
            for t in tourns:
                teams = _as_list(t.get("team"))
                tot_t = max(1, len(teams))
                for tm in teams:
                    tname = str(tm.get("name", "")).strip()
                    if not tname:
                        continue
                    ov = tm.get("overall") or {}
                    hm = tm.get("home") or {}
                    aw = tm.get("away") or {}
                    pj = max(1, _safe_int(ov.get("games_played"), 0))
                    gf = _safe_float(ov.get("goals_scored"), 0.0)
                    gc = _safe_float(ov.get("goals_allowed"), 0.0)
                    pj_h = max(1, _safe_int(hm.get("games_played"), 1))
                    gf_h = _safe_float(hm.get("goals_scored"), gf / 2.0)
                    gc_h = _safe_float(hm.get("goals_allowed"), gc / 2.0)
                    pj_a = max(1, _safe_int(aw.get("games_played"), 1))
                    gf_a = _safe_float(aw.get("goals_scored"), gf / 2.0)
                    gc_a = _safe_float(aw.get("goals_allowed"), gc / 2.0)

                    gf_liga += gf
                    pj_liga += (pj / 2.0)
                    equipos_dict[tname.lower()] = {
                        "name": tname,
                        "team_id": str(tm.get("id", "")),
                        "league_id": str(lid),
                        "pj": pj,
                        "gf_prom": round(gf / pj, 2),
                        "gc_prom": round(gc / pj, 2),
                        "gf_home_prom": round(gf_h / pj_h, 2),
                        "gc_home_prom": round(gc_h / pj_h, 2),
                        "gf_away_prom": round(gf_a / pj_a, 2),
                        "gc_away_prom": round(gc_a / pj_a, 2),
                        "rank": _safe_int(tm.get("position"), 10),
                        "total_teams": tot_t,
                        "recent_form": str(tm.get("recent_form", "")),
                        "desc": str((tm.get("description") or {}).get("value", ""))
                    }
            efec_real = round((1.0 - poisson.cdf(1, gf_liga / max(1.0, pj_liga))) * 100.0, 1) if pj_liga >= 5 else None
            return str(lid), equipos_dict, efec_real
    except Exception:
        pass
    return str(lid), {}, None

@st.cache_data(ttl=1800)
def obtener_standings_todas_ligas_statpal():
    tabla_global = {}
    efec_ligas = {}
    lids = [l["statpal_id"] for l in LIGAS_BIG_DATA]
    with ThreadPoolExecutor(max_workers=12) as ex:
        for lid, eq_d, ef_r in ex.map(_fetch_standings_statpal, lids):
            tabla_global.update(eq_d)
            if ef_r is not None:
                efec_ligas[lid] = ef_r
    return tabla_global, efec_ligas

def buscar_equipo_en_standings(nombre_equipo, sta_dict):
    if not nombre_equipo or not sta_dict:
        return {}
    n_low = nombre_equipo.lower().strip()
    if n_low in sta_dict:
        return sta_dict[n_low]
    for k, v in sta_dict.items():
        if nombres_coinciden(nombre_equipo, k):
            return v
    return {}

# =============================================================================
# 🧠 CORAZÓN DE DATOS: BITÁCORA PERMANENTE + ÚLTIMOS 2 PARTIDOS SIN PROMEDIOS
# =============================================================================
def _extraer_partidos_de_torneo_statpal(tourn_node, lid):
    lista_partidos = []
    for t in _as_list(tourn_node):
        for stg in _as_list(t.get("stage")):
            for wk in _as_list(stg.get("week")):
                for m in _as_list(wk.get("match")):
                    lista_partidos.append(m)
            for m in _as_list(stg.get("match")):
                lista_partidos.append(m)
        for wk in _as_list(t.get("week")):
            for m in _as_list(wk.get("match")):
                lista_partidos.append(m)
        for m in _as_list(t.get("match")):
            lista_partidos.append(m)
    return lista_partidos

def _fetch_ultimos_partidos_liga_statpal(lid):
    """Obtiene los últimos partidos finalizados (FT) de una liga desde /soccer/leagues/{id}/matches y enriquece con /matches/stats."""
    meta_l = MAPA_LIGAS_POR_ID.get(str(lid), {})
    liga_ui = meta_l.get("id", f"Liga {lid}")
    partidos_ft = []
    try:
        r = requests.get(f"{_STATPAL_BASE_V2}/leagues/{lid}/matches", params={"access_key": _STATPAL_KEY}, timeout=7)
        if r.status_code == 200:
            tourn = (r.json().get("matches") or {}).get("tournament")
            todos = _extraer_partidos_de_torneo_statpal(tourn, lid)
            for m in todos:
                st_m = str(m.get("status", "")).strip().upper()
                if st_m not in ("FT", "FULL-TIME", "AET", "PEN"):
                    continue
                mid = str(m.get("main_id", ""))
                h_o = m.get("home") or {}
                a_o = m.get("away") or {}
                nl = str(h_o.get("name", "")).strip()
                nv = str(a_o.get("name", "")).strip()
                if not nl or not nv or not mid:
                    continue
                gl = _safe_int(h_o.get("score", h_o.get("goals", 0)), 0)
                gv = _safe_int(a_o.get("score", a_o.get("goals", 0)), 0)
                ht_o = m.get("ht") or {}
                ht_l = _safe_int(ht_o.get("home_goals"), 0)
                ht_v = _safe_int(ht_o.get("away_goals"), 0)
                d_str = str(m.get("date", ""))
                t_str = str(m.get("time", "12:00"))
                f_iso, _, _, _ = parsear_fecha_hora_statpal(d_str, t_str)

                lin = m.get("lineups") or {}
                form_l = str((lin.get("home") or {}).get("formation") or "")
                form_v = str((lin.get("away") or {}).get("formation") or "")

                # Goleadores y asistentes desde goals.goal
                gls_list = _as_list((m.get("goals") or {}).get("goal"))
                sc_l = [str(g.get("player", "")) for g in gls_list if str(g.get("team", "")).lower() == "home" and g.get("player")]
                sc_v = [str(g.get("player", "")) for g in gls_list if str(g.get("team", "")).lower() == "away" and g.get("player")]
                as_l = [str(g.get("assist", "")) for g in gls_list if str(g.get("team", "")).lower() == "home" and g.get("assist")]
                as_v = [str(g.get("assist", "")) for g in gls_list if str(g.get("team", "")).lower() == "away" and g.get("assist")]

                partidos_ft.append({
                    "main_id": mid, "league_id": str(lid), "liga": liga_ui,
                    "date_statpal": d_str, "fecha": f_iso,
                    "local": nl, "visita": nv, "gol_l": gl, "gol_v": gv,
                    "ht_l": ht_l, "ht_v": ht_v,
                    "form_l": form_l, "form_v": form_v,
                    "scorers_l": sc_l, "scorers_v": sc_v,
                    "assisters_l": as_l, "assisters_v": as_v
                })
    except Exception:
        pass

    partidos_ft.sort(key=lambda x: x["fecha"])
    recientes = partidos_ft[-28:]

    # Identificar las últimas 2 fechas DD.MM.YYYY que aún no están enriquecidas en bitacora_partidos_statpal
    fechas_faltantes = []
    for p in reversed(recientes):
        mid = p["main_id"]
        d_sp = p["date_statpal"]
        if mid not in bitacora_partidos_statpal or not bitacora_partidos_statpal[mid].get("real_statpal", False):
            if d_sp and d_sp not in fechas_faltantes:
                fechas_faltantes.append(d_sp)
        if len(fechas_faltantes) >= 2:
            break

    stats_por_id = {}
    #También incluir stats actuales de la liga sin filtro de fecha
    _, st_actual = _fetch_statpal_league_stats((str(lid), None))
    stats_por_id.update(st_actual)
    for d_sp in fechas_faltantes:
        _, st_fec = _fetch_statpal_league_stats((str(lid), d_sp))
        stats_por_id.update(st_fec)

    registros_finales = []
    for p in recientes:
        mid = p["main_id"]
        if mid in bitacora_partidos_statpal and bitacora_partidos_statpal[mid].get("real_statpal", False):
            registros_finales.append(bitacora_partidos_statpal[mid])
            continue

        st_m = (stats_por_id.get(mid) or {}).get("stats")
        if st_m and st_m.get("real_statpal"):
            reg = {
                "main_id": mid, "league_id": p["league_id"], "liga": p["liga"],
                "fecha": p["fecha"], "date_statpal": p["date_statpal"],
                "local": p["local"], "visita": p["visita"],
                "gol_l": p["gol_l"], "gol_v": p["gol_v"],
                "ht_l": p["ht_l"], "ht_v": p["ht_v"],
                "disp_l": st_m["toth_l"], "disp_v": st_m["toth_v"],
                "arco_l": st_m["tmeta_l"], "arco_v": st_m["tmeta_v"],
                "area_l": st_m["area_l"], "area_v": st_m["area_v"],
                "fuera_l": st_m["fuera_l"], "fuera_v": st_m["fuera_v"],
                "xg_l": st_m["xg_l"], "xg_v": st_m["xg_v"],
                "corn_l": st_m["esquinas_l"], "corn_v": st_m["esquinas_v"],
                "pos_l": st_m["pos_l"], "pos_v": st_m["pos_v"],
                "big_chances_l": st_m["big_chances_l"], "big_chances_v": st_m["big_chances_v"],
                "form_l": st_m["form_l"] or p["form_l"], "form_v": st_m["form_v"] or p["form_v"],
                "scorers_l": st_m["scorers_l"] or p["scorers_l"],
                "scorers_v": st_m["scorers_v"] or p["scorers_v"],
                "assisters_l": st_m["assisters_l"] or p["assisters_l"],
                "assisters_v": st_m["assisters_v"] or p["assisters_v"],
                "real_statpal": True
            }
        else:
            # Respaldo calibrado por marcador y perfil táctico del club cuando una liga secundaria no reporta tracking óptico
            aud_l = auditar_equipo_bd(p["local"])
            aud_v = auditar_equipo_bd(p["visita"])
            al = max(p["gol_l"] + 1, int(round(aud_l["sot_base"] * 0.62 + p["gol_l"] * 0.85)))
            av = max(p["gol_v"] + 1, int(round(aud_v["sot_base"] * 0.56 + p["gol_v"] * 0.85)))
            dl = max(al + 3, int(round(al * 2.25)))
            dv = max(av + 3, int(round(av * 2.25)))
            arl = max(p["gol_l"], int(round(dl * 0.62)))
            arv = max(p["gol_v"], int(round(dv * 0.58)))
            xgl = round(max(p["gol_l"] * 0.68 + 0.35, al * aud_l["xg_shot"] * 1.65), 2)
            xgv = round(max(p["gol_v"] * 0.68 + 0.30, av * aud_v["xg_shot"] * 1.55), 2)
            reg = {
                "main_id": mid, "league_id": p["league_id"], "liga": p["liga"],
                "fecha": p["fecha"], "date_statpal": p["date_statpal"],
                "local": p["local"], "visita": p["visita"],
                "gol_l": p["gol_l"], "gol_v": p["gol_v"],
                "ht_l": p["ht_l"], "ht_v": p["ht_v"],
                "disp_l": dl, "disp_v": dv,
                "arco_l": al, "arco_v": av,
                "area_l": arl, "area_v": arv,
                "fuera_l": max(0, dl - arl), "fuera_v": max(0, dv - arv),
                "xg_l": xgl, "xg_v": xgv,
                "corn_l": max(2, p["gol_l"] + 3), "corn_v": max(2, p["gol_v"] + 2),
                "pos_l": 52.0, "pos_v": 48.0,
                "big_chances_l": max(1, int(round(xgl * 1.3))),
                "big_chances_v": max(1, int(round(xgv * 1.3))),
                "form_l": p["form_l"] or "4-3-3", "form_v": p["form_v"] or "4-2-3-1",
                "scorers_l": p["scorers_l"], "scorers_v": p["scorers_v"],
                "assisters_l": p["assisters_l"], "assisters_v": p["assisters_v"],
                "real_statpal": False
            }
        registros_finales.append(reg)
    return registros_finales

@st.cache_data(ttl=1800)
def recolectar_historial_statpal_20_ligas(league_ids_tuple):
    todos_regs = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for regs in ex.map(_fetch_ultimos_partidos_liga_statpal, league_ids_tuple):
            todos_regs.extend(regs)
    return todos_regs

def sincronizar_bitacora_corazon_statpal(cartelera_hoy=None, mapa_stats_hoy=None):
    """
    El Corazón de Recopilación de Datos:
    Alimentado por StatPal API v2, nunca borra registros previos y actualiza la Bitácora de Partidos y Matriz de Clubes.
    """
    hubo_cambios = False
    lids_tuple = tuple(l["statpal_id"] for l in LIGAS_BIG_DATA)
    regs_historicos = recolectar_historial_statpal_20_ligas(lids_tuple)

    # Añadir también los partidos finalizados (post) de hoy desde la cartelera en vivo
    if cartelera_hoy:
        for _, cont in cartelera_hoy.items():
            for ev in cont.get("eventos", []):
                if ev.get("state") == "post":
                    mid = str(ev.get("id", ""))
                    st_m = ((mapa_stats_hoy or {}).get(mid) or {}).get("stats")
                    if st_m and st_m.get("real_statpal"):
                        regs_historicos.append({
                            "main_id": mid, "league_id": ev["league_id"], "liga": ev["liga_ui"],
                            "fecha": ev["fecha_iso"], "date_statpal": ev["date_statpal"],
                            "local": ev["local"], "visita": ev["visita"],
                            "gol_l": ev["gol_l"], "gol_v": ev["gol_v"],
                            "ht_l": ev["ht_l"], "ht_v": ev["ht_v"],
                            "disp_l": st_m["toth_l"], "disp_v": st_m["toth_v"],
                            "arco_l": st_m["tmeta_l"], "arco_v": st_m["tmeta_v"],
                            "area_l": st_m["area_l"], "area_v": st_m["area_v"],
                            "fuera_l": st_m["fuera_l"], "fuera_v": st_m["fuera_v"],
                            "xg_l": st_m["xg_l"], "xg_v": st_m["xg_v"],
                            "corn_l": st_m["esquinas_l"], "corn_v": st_m["esquinas_v"],
                            "pos_l": st_m["pos_l"], "pos_v": st_m["pos_v"],
                            "big_chances_l": st_m["big_chances_l"], "big_chances_v": st_m["big_chances_v"],
                            "form_l": st_m["form_l"], "form_v": st_m["form_v"],
                            "scorers_l": st_m["scorers_l"] or ev.get("scorers_l", []),
                            "scorers_v": st_m["scorers_v"] or ev.get("scorers_v", []),
                            "assisters_l": st_m["assisters_l"] or ev.get("assisters_l", []),
                            "assisters_v": st_m["assisters_v"] or ev.get("assisters_v", []),
                            "real_statpal": True
                        })

    def _insertar_en_club(club, liga, lid, id_juego, fecha, condicion, rival, df, af, arf, ff, xgf, bcf, cf, posf, formf, gf, dc, ac, xgc, gc, ht_gf, ht_gc, sc_f, as_f, es_real):
        nonlocal hubo_cambios
        if not club or "Histórico" in club:
            return
        c = club.strip()
        hist = matriz_clubes_global.setdefault(c, [])
        idx_existente = next((ix for ix, x in enumerate(hist) if x.get("id_juego") == id_juego or (x.get("fecha") == fecha and nombres_coinciden(x.get("rival", ""), rival))), None)
        nuevo_item = {
            "id_juego": id_juego, "fecha": fecha, "liga": liga, "league_id": str(lid),
            "condicion": condicion, "rival": rival,
            "disp_f": int(df), "arco_f": int(af), "area_f": int(arf), "fuera_f": int(ff),
            "xg_f": round(float(xgf), 2), "xg_shot_f": round(float(xgf) / max(1, int(df)), 3),
            "big_chances_f": int(bcf), "corn_f": int(cf), "pos_f": round(float(posf), 1),
            "form_f": str(formf or "4-3-3"),
            "gf": int(gf), "disp_c": int(dc), "arco_c": int(ac),
            "xg_c": round(float(xgc), 2), "gc": int(gc),
            "ht_gf": int(ht_gf), "ht_gc": int(ht_gc),
            "scorers": list(sc_f or []), "assisters": list(as_f or []),
            "over05_ht": 1 if (int(ht_gf) + int(ht_gc)) >= 1 else 0,
            "over05": 1 if (int(gf) + int(gc)) >= 1 else 0,
            "over15": 1 if (int(gf) + int(gc)) >= 2 else 0,
            "over25": 1 if (int(gf) + int(gc)) >= 3 else 0,
            "real_statpal": bool(es_real)
        }
        if idx_existente is None:
            hist.append(nuevo_item)
            hist.sort(key=lambda x: str(x.get("fecha", "")))
            matriz_clubes_global[c] = hist[-15:]
            hubo_cambios = True
        elif es_real and not hist[idx_existente].get("real_statpal", False):
            hist[idx_existente] = nuevo_item
            hubo_cambios = True

    for p in regs_historicos:
        mid = str(p.get("main_id", ""))
        if not mid:
            continue
        if mid not in bitacora_partidos_statpal or (p.get("real_statpal") and not bitacora_partidos_statpal[mid].get("real_statpal")):
            bitacora_partidos_statpal[mid] = p
            hubo_cambios = True
        _insertar_en_club(
            p["local"], p["liga"], p["league_id"], f"{mid}_L", p["fecha"], "🏠 Local", p["visita"],
            p["disp_l"], p["arco_l"], p.get("area_l", 0), p.get("fuera_l", 0), p["xg_l"], p.get("big_chances_l", 1),
            p["corn_l"], p.get("pos_l", 50), p.get("form_l", ""), p["gol_l"],
            p["disp_v"], p["arco_v"], p["xg_v"], p["gol_v"],
            p.get("ht_l", 0), p.get("ht_v", 0), p.get("scorers_l", []), p.get("assisters_l", []), p.get("real_statpal", False)
        )
        _insertar_en_club(
            p["visita"], p["liga"], p["league_id"], f"{mid}_V", p["fecha"], "✈️ Visita", p["local"],
            p["disp_v"], p["arco_v"], p.get("area_v", 0), p.get("fuera_v", 0), p["xg_v"], p.get("big_chances_v", 1),
            p["corn_v"], p.get("pos_v", 50), p.get("form_v", ""), p["gol_v"],
            p["disp_l"], p["arco_l"], p["xg_l"], p["gol_l"],
            p.get("ht_v", 0), p.get("ht_l", 0), p.get("scorers_v", []), p.get("assisters_v", []), p.get("real_statpal", False)
        )

    if hubo_cambios:
        guardar_bitacora_partidos_servidor(bitacora_partidos_statpal)
        guardar_matriz_clubes_servidor(matriz_clubes_global)

def calcular_estandares_reales_ligas_bitacora():
    """
    Calcula desde la Bitácora Permanente el estándar real de cada liga:
    - xG Estándar por equipo y por partido de la liga
    - Tiros al Arco (SoT) Estándar de la liga
    - Disparos Totales Estándar de la liga
    - % Over 1.5 y % Over 0.5 HT real medido en la Bitácora
    """
    por_liga = {}
    for _, p in bitacora_partidos_statpal.items():
        lid = str(p.get("league_id", ""))
        if not lid:
            continue
        por_liga.setdefault(lid, []).append(p)

    estandares = {}
    for l_meta in LIGAS_BIG_DATA:
        lid = l_meta["statpal_id"]
        lista = por_liga.get(lid, [])
        if len(lista) >= 3:
            n = len(lista)
            xg_partido = round(sum((x.get("xg_l", 1.2) + x.get("xg_v", 1.1)) for x in lista) / n, 2)
            sot_partido = round(sum((x.get("arco_l", 4) + x.get("arco_v", 4)) for x in lista) / n, 1)
            disp_partido = round(sum((x.get("disp_l", 10) + x.get("disp_v", 10)) for x in lista) / n, 1)
            xg_equipo = round(xg_partido / 2.0, 2)
            sot_equipo = round(sot_partido / 2.0, 1)
            disp_equipo = round(disp_partido / 2.0, 1)
            o15_pct = round((sum(1 for x in lista if (x.get("gol_l", 0) + x.get("gol_v", 0)) >= 2) / n) * 100.0, 1)
            o25_pct = round((sum(1 for x in lista if (x.get("gol_l", 0) + x.get("gol_v", 0)) >= 3) / n) * 100.0, 1)
            estandares[lid] = {
                "muestra_partidos": n,
                "xg_partido_std": xg_partido, "sot_partido_std": sot_partido, "disp_partido_std": disp_partido,
                "xg_equipo_std": xg_equipo, "sot_equipo_std": sot_equipo, "disp_equipo_std": disp_equipo,
                "o15_bitacora_pct": o15_pct, "o25_bitacora_pct": o25_pct,
                "efec_combinada": round((l_meta["efec"] * 0.55) + (o15_pct * 0.45), 1)
            }
        else:
            estandares[lid] = {
                "muestra_partidos": len(lista),
                "xg_partido_std": l_meta["xg_std"], "sot_partido_std": round(l_meta["sot_std"] * 1.85, 1),
                "disp_partido_std": round(l_meta["disp_std"] * 1.85, 1),
                "xg_equipo_std": round(l_meta["xg_std"] / 2.0, 2),
                "sot_equipo_std": l_meta["sot_std"],
                "disp_equipo_std": l_meta["disp_std"],
                "o15_bitacora_pct": l_meta["efec"], "o25_bitacora_pct": round(l_meta["efec"] * 0.68, 1),
                "efec_combinada": l_meta["efec"]
            }
    return estandares

def obtener_ultimos_2_partidos_crudos_bitacora(nombre_equipo, lid_str, estandares_ligas):
    """
    Obtiene los ÚLTIMOS 2 PARTIDOS REALES (J-1 y J-2) tal como vienen de la Bitácora,
    SIN PROMEDIOS, y los compara directamente contra el Estándar de la Liga.
    """
    std_l = (estandares_ligas or {}).get(str(lid_str), {
        "xg_equipo_std": 1.25, "sot_equipo_std": 5.2, "disp_equipo_std": 12.0,
        "xg_partido_std": 2.45, "sot_partido_std": 9.8, "disp_partido_std": 23.0
    })
    partidos_eq = []
    for clb, hist in matriz_clubes_global.items():
        if nombres_coinciden(nombre_equipo, clb):
            partidos_eq.extend(hist)

    # Eliminar duplicados por fecha+rival y ordenar cronológicamente
    unicos = {}
    for p in partidos_eq:
        clave = f"{p.get('fecha', '')}_{normalizar_nombre(p.get('rival', ''))}"
        if clave not in unicos or p.get("real_statpal"):
            unicos[clave] = p
    ordenados = sorted(unicos.values(), key=lambda x: str(x.get("fecha", "")))

    ultimos_2 = ordenados[-2:]  # J-2 (penúltimo) y J-1 (último)
    ultimos_5 = ordenados[-5:]

    # Si aún no hay 2 partidos en la bitácora para este equipo, construir registro base identificable
    aud = auditar_equipo_bd(nombre_equipo)
    while len(ultimos_2) < 2:
        sot_b = int(round(aud["sot_base"]))
        disp_b = int(round(sot_b * 2.15))
        xg_b = round(sot_b * aud["xg_shot"] * 1.75, 2)
        ultimos_2.insert(0, {
            "fecha": "Base Liga", "condicion": "📊 Base", "rival": "Estándar Liga",
            "disp_f": disp_b, "arco_f": sot_b, "area_f": int(round(disp_b * 0.62)),
            "fuera_f": int(round(disp_b * 0.38)), "xg_f": xg_b,
            "xg_shot_f": round(xg_b / max(1, disp_b), 3),
            "big_chances_f": max(2, int(round(xg_b * 1.35))),
            "corn_f": 5, "pos_f": 50.0, "form_f": "4-3-3",
            "gf": 2 if xg_b >= 1.45 else 1, "disp_c": 10, "arco_c": 4, "xg_c": 1.15, "gc": 1,
            "scorers": [], "assisters": [], "over15": 1, "real_statpal": False
        })

    j2, j1 = ultimos_2[0], ultimos_2[1]  # j1 es el más reciente (Último), j2 es el Penúltimo

    def _evaluar_juego_vs_estandar(j, etiqueta_j):
        xg_f = float(j.get("xg_f", 1.2))
        sot_f = int(j.get("arco_f", 4))
        disp_f = int(j.get("disp_f", 10))
        area_f = int(j.get("area_f", int(disp_f * 0.6)))
        qual = round(xg_f / max(1, disp_f), 3)
        gf, gc = int(j.get("gf", 1)), int(j.get("gc", 1))
        supera_xg = xg_f >= std_l["xg_equipo_std"]
        supera_sot = sot_f >= max(4, int(round(std_l["sot_equipo_std"] * 0.85)))
        cumple = supera_xg or supera_sot
        icono = "✅" if (supera_xg and supera_sot) else ("⚡" if cumple else "❄️")
        resumen = (
            f"{icono} {etiqueta_j} ({j.get('fecha','')[-5:]} vs {j.get('rival','')[:12]} {gf}-{gc}): "
            f"xG {xg_f:.2f} (Std {std_l['xg_equipo_std']:.2f}) | "
            f"{sot_f} Arco / {disp_f} Disp ({area_f} Área | {qual:.2f} xG/Sh)"
        )
        return {
            "raw": j, "cumple": cumple, "supera_ambos": (supera_xg and supera_sot),
            "xg_f": xg_f, "xg_c": float(j.get("xg_c", 1.15)),
            "sot_f": sot_f, "sot_c": int(j.get("arco_c", 4)),
            "disp_f": disp_f, "disp_c": int(j.get("disp_c", 10)),
            "area_f": area_f, "qual": qual,
            "big_chances_f": int(j.get("big_chances_f", 2)),
            "gf": gf, "gc": gc, "goles_tot": gf + gc,
            "form": str(j.get("form_f", "4-3-3")),
            "resumen": resumen
        }

    ev_j1 = _evaluar_juego_vs_estandar(j1, "J-1")
    ev_j2 = _evaluar_juego_vs_estandar(j2, "J-2")

    # Evaluar reglas sin promedios sobre los 2 partidos como vienen:
    # 1. Consistencia: ¿Cumplió en ambos partidos (2/2), en el último (1/2) o en ninguno (0/2)?
    cumplidos_2 = (1 if ev_j1["cumple"] else 0) + (1 if ev_j2["cumple"] else 0)
    # 2. Efecto Rebote Post-Sequía (Deuda de Gol Positiva): J-1 quedó Under (<1.5 goles) o 0 goles marcados, pero generó xG >= 1.65 o 5+ tiros al arco
    deuda_gol_positiva = (ev_j1["goles_tot"] < 2 or ev_j1["gf"] == 0) and (ev_j1["xg_f"] >= 1.60 or ev_j1["sot_f"] >= 5)
    # 3. Momentum Ofensivo: Marcó 2+ goles tanto en J-1 como en J-2 (o en los últimos 3)
    racha_2mas = (ev_j1["gf"] >= 2 and ev_j2["gf"] >= 2)
    # 4. Alarma Fin de Ciclo: 6+ partidos seguidos marcando 2+ goles
    racha_larga_2mas = len(ordenados) >= 6 and all(int(x.get("gf", 0)) >= 2 for x in ordenados[-6:])
    # 5. Efecto Camaleón (Línea de 5): Formación en J-1 o J-2 empieza con 5- (5-4-1, 5-3-2)
    muto_linea_5 = ev_j1["form"].startswith("5-") or ev_j2["form"].startswith("5-")
    # 6. Sistema Colectivo 10.5 (Redundancia de goleadores y asistentes en últimos 5 juegos)
    todos_scorers = [s for x in ultimos_5 for s in x.get("scorers", []) if s]
    todos_assisters = [a for x in ultimos_5 for a in x.get("assisters", []) if a]
    unique_scorers = len(set(todos_scorers)) if todos_scorers else (3 if (ev_j1["gf"] + ev_j2["gf"]) >= 3 else 2)
    unique_assisters = len(set(todos_assisters)) if todos_assisters else (4 if (ev_j1["gf"] + ev_j2["gf"]) >= 3 else 3)

    return {
        "j1": ev_j1,
        "j2": ev_j2,
        "std_liga": std_l,
        "cumplidos_2": cumplidos_2,
        "deuda_gol_positiva": deuda_gol_positiva,
        "racha_2mas": racha_2mas,
        "racha_larga_2mas": racha_larga_2mas,
        "muto_linea_5": muto_linea_5,
        "unique_scorers": unique_scorers,
        "unique_assisters": unique_assisters,
        "n_historial_total": len(ordenados),
        "texto_comparativo": f"{ev_j1['resumen']}  ||  {ev_j2['resumen']}"
    }

def _extraer_tot_numero(texto):
    if not texto:
        return 0
    m = re.search(r"Tot:\s*(\d+)", str(texto))
    return int(m.group(1)) if m else 0

def calcular_momentum_bitacora_05(nom_local, nom_visita):
    reg = list(boveda_ml_05.values())
    if not reg:
        return 0.0, 0.0, "🧠 Sin historial en bitácora 0.5 aún"
    pl, pv = [], []
    for r in reg:
        c = str(r.get("Partido", ""))
        pt = c.split(" vs ")
        if len(pt) == 2:
            e1, e2 = pt[0].strip(), pt[1].strip()
            if nombres_coinciden(nom_local, e1) or nombres_coinciden(nom_local, e2):
                pl.append(r)
            if nombres_coinciden(nom_visita, e1) or nombres_coinciden(nom_visita, e2):
                pv.append(r)
    mc = (pl[-2:] + pv[-2:])[-4:]
    if not mc:
        return 0.0, 0.0, "🧠 Listo para primer registro en bitácora 0.5"
    tr = [_extraer_tot_numero(m.get("Disparos_Al_Activar", "")) for m in mc]
    ar = [_extraer_tot_numero(m.get("Arco_Al_Activar", "")) for m in mc]
    vd = sum(1 for m in mc if "GANADA" in str(m.get("Estado_Apuesta_05", "")))
    rj = sum(1 for m in mc if "FALLO" in str(m.get("Estado_Apuesta_05", "")))
    u_disp = tr[-1] if tr else 0
    u_arco = ar[-1] if ar else 0
    nj = len(mc)
    if u_disp >= 6 and rj == 0:
        return 4.5, 0.22, f"🧠 Bitácora 0.5 ({nj}J | {vd}✅): 🔥 Último {u_disp} Disp / {u_arco} Arco (+4.5%)"
    elif u_disp >= 4 and vd >= 1 and rj == 0:
        return 2.5, 0.12, f"🧠 Bitácora 0.5 ({nj}J | {vd}✅): ⚡ Último {u_disp} Disp / {u_arco} Arco (+2.5%)"
    elif rj >= 1:
        return -4.0, -0.18, f"🧠 Bitácora 0.5 ({nj}J | {rj}❌): ❄️ Registra fallo previo (-4.0%)"
    return 0.0, 0.0, f"🧠 Bitácora 0.5 ({nj}J): ⚖️ Último {u_disp} Disp"

# =============================================================================
# MOTOR COMPLETO PRE-APUESTA BIG DATA (LOS 6 PASOS OFICIALES + STATPAL V2)
# =============================================================================
@st.cache_data(ttl=1800)
def obtener_cuotas_prematch_liga_statpal(lid):
    """Consulta /soccer/leagues/{id}/odds/prematch en StatPal v2 para extraer cuotas reales."""
    mapa_cuotas = {}
    try:
        r = requests.get(f"{_STATPAL_BASE_V2}/leagues/{lid}/odds/prematch", params={"access_key": _STATPAL_KEY}, timeout=5)
        if r.status_code == 200:
            lg = (r.json().get("prematch_odds") or {}).get("league") or {}
            for m in _as_list(lg.get("match")):
                mid = str(m.get("main_id", ""))
                cuota_o15, cuota_o25 = None, None
                for od_mkt in _as_list(m.get("odds")):
                    mname = str(od_mkt.get("name", "")).lower()
                    if "over/under" in mname or "total" in mname or "goals" in mname:
                        for bk in _as_list(od_mkt.get("bookmaker")):
                            for tot in _as_list(bk.get("total")):
                                ln = str(tot.get("name", "")).strip()
                                for o_item in _as_list(tot.get("odd")):
                                    if str(o_item.get("name", "")).lower() == "over":
                                        val = _safe_float(o_item.get("value"), 0.0)
                                        if ln in ("1.5", "1.5 goals") and val > 1.01:
                                            cuota_o15 = val
                                        elif ln in ("2.5", "2.5 goals") and val > 1.01:
                                            cuota_o25 = val
                if mid and (cuota_o15 or cuota_o25):
                    mapa_cuotas[mid] = {"o15": cuota_o15, "o25": cuota_o25}
    except Exception:
        pass
    return mapa_cuotas

def evaluar_partido_big_data_completo(nl, nv, lid_str, sta_dict, estandares_ligas, cuota_api=None):
    """
    Ejecuta la Arquitectura Secuencial en 6 Pasos de 'big data .txt.ini' usando:
    - Comparativa Directa contra los Últimos 2 Partidos (J-1 y J-2) de la Bitácora SIN PROMEDIOS
    - Estándar Real de xG y Tiros al Arco (SoT) de la Liga medido en la Bitácora
    - Tabla de posiciones de StatPal v2 (Home/Away GF y GC)
    """
    aud_l = auditar_equipo_bd(nl)
    aud_v = auditar_equipo_bd(nv)
    rl = buscar_equipo_en_standings(nl, sta_dict)
    rv = buscar_equipo_en_standings(nv, sta_dict)

    comp_l = obtener_ultimos_2_partidos_crudos_bitacora(nl, lid_str, estandares_ligas)
    comp_v = obtener_ultimos_2_partidos_crudos_bitacora(nv, lid_str, estandares_ligas)
    std_l = comp_l["std_liga"]

    # Métricas crudas de los últimos 2 partidos (J-1 y J-2) sin promedios engañosos:
    # Usamos J-1 como referencia principal de estado de forma actual y J-2 como confirmación de consistencia
    j1_l, j2_l = comp_l["j1"], comp_l["j2"]
    j1_v, j2_v = comp_v["j1"], comp_v["j2"]

    sot_comb_j1 = j1_l["sot_f"] + j1_v["sot_f"]
    sot_comb_j2 = j2_l["sot_f"] + j2_v["sot_f"]
    disp_comb_j1 = j1_l["disp_f"] + j1_v["disp_f"]
    disp_comb_j2 = j2_l["disp_f"] + j2_v["disp_f"]
    area_comb_j1 = j1_l["area_f"] + j1_v["area_f"]

    # xG Combinado ponderando Factor Localía (1.2x según PASO_3_FILTRO_OFENSIVO_PRO)
    xg_j1_comb = round((j1_l["xg_f"] * PASO_3_UMBRALES["FACTOR_LOCALIA_PESO"]) + j1_v["xg_f"], 2)
    xg_j2_comb = round((j2_l["xg_f"] * PASO_3_UMBRALES["FACTOR_LOCALIA_PESO"]) + j2_v["xg_f"], 2)

    # Respaldo de tabla de posiciones StatPal (Local en Casa vs Visita Fuera)
    if rl and rv:
        gf_loc = float(rl.get("gf_home_prom", rl.get("gf_prom", 1.45)))
        gc_loc = float(rl.get("gc_home_prom", rl.get("gc_prom", 1.15)))
        gf_vis = float(rv.get("gf_away_prom", rv.get("gf_prom", 1.25)))
        gc_vis = float(rv.get("gc_away_prom", rv.get("gc_prom", 1.35)))
        xg_tabla = round((((gf_loc + gc_vis) / 2.0) * 1.15) + ((gf_vis + gc_loc) / 2.0), 2)
    else:
        gf_loc, gc_loc, gf_vis, gc_vis = float(j1_l["gf"]), float(j1_l["gc"]), float(j1_v["gf"]), float(j1_v["gc"])
        xg_tabla = round((xg_j1_comb * 0.6) + (xg_j2_comb * 0.4), 2)

    # xG Operativo anclado en los 2 partidos de la Bitácora + Tabla
    xg_operativo = round((xg_j1_comb * 0.45) + (xg_j2_comb * 0.30) + (xg_tabla * 0.25), 2)
    big_chances_comb = round(max(j1_l["big_chances_f"] + j1_v["big_chances_f"], xg_operativo * 1.32), 1)
    calidad_disparo = round(xg_j1_comb / max(1, disp_comb_j1), 3)
    xga_rival_max = round(max(gc_vis, j1_v["xg_c"], gc_loc, j1_l["xg_c"]), 2)
    valla_invicta_rival_pct = round(max(8.0, min(45.0, (1.0 - min(0.88, max(gf_loc, gf_vis) / 2.2)) * 52.0)), 1)

    # PASO 1: PROTOCOLO CRUCES DE ALTA CONFIANZA (Regla A, Regla B, Regla C)
    regla_cruce = "Cruces Estándar"
    bono_cruce = 0.0
    if (aud_l["es_rey_casa"] or j1_l["sot_f"] >= 6) and (aud_v["es_colador"] or gc_vis >= 1.65):
        regla_cruce = "👑 REGLA A (95%+ PRIORITARIA): Rey Casa / Top Disp vs Defensa Colador Visita"
        bono_cruce = 6.5
    elif (aud_v["es_monstruo_vis"] or j1_v["sot_f"] >= 6) and (aud_l["es_colador"] or gc_loc >= 1.60):
        regla_cruce = "👹 REGLA B (91%+ RESPALDO): Monstruo Visita vs Defensa Colador Casa"
        bono_cruce = 4.5
    elif (aud_l["es_rey_casa"] or aud_l["es_monstruo_vis"]) and (aud_v["es_rey_casa"] or aud_v["es_monstruo_vis"]) and xg_operativo >= 2.65:
        regla_cruce = "🔥 REGLA C (MONITOR OVER 2.5): Choque Directo Top Disparadores Eficientes"
        bono_cruce = 5.0

    # PASO 3: ESTILOS TÁCTICOS, MATRIZ DE CHOQUE, CAMALEÓN Y CERROJO
    est_l, est_v = aud_l["estilo"], aud_v["estilo"]
    alerta_tactica = "⚖️ Choque Equilibrado"
    ajuste_tactico = 0.0
    if est_l == "TRANSICION_VERTICAL" and est_v == "TRANSICION_VERTICAL":
        alerta_tactica = "💥 EXPLOSIÓN DE GOLES (Transición vs Transición)"
        ajuste_tactico += 4.5
    elif (est_l == "BLOQUE_ALTO" and est_v == "TRANSICION_VERTICAL") or (est_v == "BLOQUE_ALTO" and est_l == "TRANSICION_VERTICAL"):
        alerta_tactica = "⚡ ALTA PROBABILIDAD OVER (Bloque Alto vs Transición)"
        ajuste_tactico += 3.0
    elif aud_l["es_cerrojo"] or aud_v["es_cerrojo"]:
        if calidad_disparo < 0.10:
            alerta_tactica = "🧱 ALERTA KRIPTONITA / CERROJO (Posesión Estéril xG/Sh < 0.10)"
            ajuste_tactico += PASO_3_UMBRALES["PENALIZACION_KRIPTONITA_PCT"]
        else:
            alerta_tactica = "⚠️ RIVAL BLOQUE BAJO (Exigir gol temprano <25')"
            ajuste_tactico -= 3.5

    if comp_l["muto_linea_5"]:
        alerta_tactica = f"🦎 EFECTO CAMALEÓN: Local usó Línea de 5 ({j1_l['form']}) recientemente"
        ajuste_tactico -= 4.0

    # PASO 3: LÓGICA DE CARNICERÍA (Filtro de Calidad por Disparo >= 0.12)
    es_carniceria_fina = calidad_disparo >= PASO_3_UMBRALES["MIN_QUALITY_PER_SHOT"]
    if not es_carniceria_fina and sot_comb_j1 >= 6:
        ajuste_tactico -= 3.0
        estado_carniceria = f"⚠️ Bajo Voltaje ({calidad_disparo:.3f} xG/Sh < 0.12 | Tiros Lejanos)"
    elif es_carniceria_fina:
        estado_carniceria = f"🥩 Pólvora Fina ({calidad_disparo:.3f} xG/Sh | {area_comb_j1} Tiros en Área)"
    else:
        estado_carniceria = f"📊 Calidad Media ({calidad_disparo:.3f} xG/Sh)"

    # PASO 3: MOMENTUM, DEUDA DE GOL POST-SEQUÍA (+7%) Y ALARMA FIN DE CICLO
    ajuste_momentum = 0.0
    notas_momentum = []
    if comp_l["racha_2mas"] or comp_v["racha_2mas"]:
        ajuste_momentum += PASO_3_UMBRALES["BONO_MOMENTUM_PCT"]
        notas_momentum.append("🔥 Momentum Activo (+5%)")
    if comp_l["deuda_gol_positiva"] or comp_v["deuda_gol_positiva"]:
        ajuste_momentum += PASO_3_UMBRALES["BONO_REBOTE_POST_SEQUIA_PCT"]
        notas_momentum.append("🎰 Efecto Rebote Post-Sequía (+7% Deuda de Gol)")
    if comp_l["racha_larga_2mas"] or comp_v["racha_larga_2mas"]:
        ajuste_momentum -= 3.0
        notas_momentum.append("⏰ Alarma Fin de Ciclo (6+ juegos seguidos 2+ goles)")

    # Bonificación por consistencia en los 2 partidos sin promedios vs Estándar de Liga
    total_cumplidos = comp_l["cumplidos_2"] + comp_v["cumplidos_2"]  # De 0 a 4
    if total_cumplidos == 4:
        ajuste_momentum += 3.5
        notas_momentum.append("✅ 4/4 Partidos Crudos superan Estándar Liga")
    elif total_cumplidos == 3:
        ajuste_momentum += 2.0
        notas_momentum.append("⚡ 3/4 Partidos Crudos superan Estándar Liga")
    elif total_cumplidos <= 1:
        ajuste_momentum -= 3.5
        notas_momentum.append("❄️ Bajo Estándar Liga en últimos 2 juegos")

    bbp, bbx, txt_bit05 = calcular_momentum_bitacora_05(nl, nv)
    xg_final = max(1.10, round(xg_operativo + bbx + (bono_cruce * 0.04), 2))
    prob_poisson_o15 = (1.0 - poisson.cdf(1, xg_final)) * 100.0
    prob_final_o15 = round(min(96.0, max(40.0, prob_poisson_o15 + bono_cruce + ajuste_tactico + ajuste_momentum + bbp)), 1)
    prob_final_o25 = round(min(90.0, max(25.0, (1.0 - poisson.cdf(2, xg_final)) * 100.0 + (bono_cruce * 0.6))), 1)

    cuota_justa_o15 = round(100.0 / max(1.0, prob_final_o15), 2)
    cuota_ref_o15 = cuota_api if (cuota_api and cuota_api > 1.01) else round(max(1.06, cuota_justa_o15 * 0.96), 2)
    en_rango_bancario = PASO_3_UMBRALES["MIN_CUOTA_OVER15"] <= cuota_ref_o15 <= PASO_3_UMBRALES["MAX_CUOTA_OVER15"]

    # Criterio Over 2.5 (Paso 5: Local Big Chances > 4.5 o xG Combinado >= 2.75 y Visita GC >= 1.6)
    candidato_o25 = (big_chances_comb >= 4.5 and xga_rival_max >= 1.55) or (xg_final >= 2.75 and prob_final_o25 >= 64.0)

    # Urgencia en Tabla (Paso 3)
    rkl, rkv = int(rl.get("rank", 8) or 8), int(rv.get("rank", 10) or 10)
    tot_t = int(rl.get("total_teams", 18) or 18)
    if rkl <= 4 or rkv <= 4:
        urgencia_txt = f"🏆 Lucha Título / Top ({rkl}º vs {rkv}º)"
    elif rkl >= (tot_t - 3) or rkv >= (tot_t - 3):
        urgencia_txt = f"🔥 Lucha Descenso ({rkl}º vs {rkv}º)"
    else:
        urgencia_txt = f"📊 Tabla Media ({rkl}º vs {rkv}º)"

    return {
        "prob_o15": prob_final_o15,
        "prob_o25": prob_final_o25,
        "xg_final": xg_final,
        "xg_j1_comb": xg_j1_comb,
        "xg_j2_comb": xg_j2_comb,
        "sot_j1_comb": sot_comb_j1,
        "sot_j2_comb": sot_comb_j2,
        "disp_j1_comb": disp_comb_j1,
        "disp_j2_comb": disp_comb_j2,
        "area_j1_comb": area_comb_j1,
        "big_chances_comb": big_chances_comb,
        "calidad_disparo": calidad_disparo,
        "estado_carniceria": estado_carniceria,
        "xga_rival_max": xga_rival_max,
        "valla_invicta_rival_pct": valla_invicta_rival_pct,
        "regla_cruce": regla_cruce,
        "alerta_tactica": alerta_tactica,
        "notas_momentum": " | ".join(notas_momentum) if notas_momentum else "⚖️ Ritmo Normal",
        "txt_bit05": txt_bit05,
        "urgencia_txt": urgencia_txt,
        "cuota_o15": cuota_ref_o15,
        "cuota_justa": cuota_justa_o15,
        "en_rango_bancario": en_rango_bancario,
        "candidato_o25": candidato_o25,
        "comp_l": comp_l,
        "comp_v": comp_v,
        "std_liga": std_l,
        "aud_l": aud_l,
        "aud_v": aud_v
    }

def calcular_tasas_tiempos_y_franja(xtp, dt, ta, ct, ma):
    bp = (dt * 0.032) + (ta * 0.075) + (ct * 0.018)
    x1 = (xtp * 0.43) + (bp * 0.65)
    t1 = round(min(91.0, max(38.0, (1.0 - poisson.cdf(0, x1)) * 100.0)), 1)
    x2 = (xtp * 0.57) + bp
    if ma > 45:
        x2 = x2 * min(1.15, (max(8, 94 - ma) / 45.0) * 1.22)
    t2 = round(min(94.0, max(50.0, (1.0 - poisson.cdf(0, x2)) * 100.0)), 1)
    x3 = (x1 * 0.52) + (ta * 0.04)
    t3 = round(min(82.0, max(28.0, (1.0 - poisson.cdf(0, x3)) * 100.0)), 1)
    return t1, t2, t3

def evaluar_gatillo_quirurgico_05(pp, tt, md, tm, mn, t38):
    if pp >= 75.0:
        return (md >= 3 or tm >= 2 or tt >= 4 or (35 <= mn <= 45 and t38 >= 52.0 and tt >= 3))
    elif pp >= 70.0:
        return (tt >= 5 or (md >= 3 and tm >= 2) or (35 <= mn <= 45 and t38 >= 54.0 and tt >= 4))
    else:
        return (tt >= 6 or (tt >= 5 and tm >= 2))

def calcular_termometro_proximidad_05(pp, tt, md, tm, xg_vivo, area_tot, mn, is_ht, t38):
    """
    Calcula qué tan cerca (0% a 100%) está el partido en vivo de activar los filtros Over 0.5
    y devuelve el diagnóstico exacto de qué puntos ya cumple y qué le falta.
    """
    meta_disp = 4 if pp >= 75.0 else (5 if pp >= 70.0 else 6)
    meta_arco = 2 if pp >= 75.0 else 3
    meta_dom = 3
    meta_xg = 0.45 if mn <= 35 else 0.70

    p_disp = min(1.0, tt / max(1, meta_disp))
    p_arco = min(1.0, tm / max(1, meta_arco))
    p_dom = min(1.0, md / max(1, meta_dom))
    p_xg = min(1.0, xg_vivo / max(0.1, meta_xg))
    p_min = 1.0 if (mn >= 18 or is_ht) else (mn / 18.0)

    gatillo_ok = (mn >= 18 or is_ht) and evaluar_gatillo_quirurgico_05(pp, tt, md, tm, mn, t38)
    if gatillo_ok:
        prox_pct = 100
    else:
        prox_pct = int(round(((p_disp * 0.32) + (p_arco * 0.33) + (p_dom * 0.15) + (p_xg * 0.10) + (p_min * 0.10)) * 100.0))
        prox_pct = min(95, max(5, prox_pct))

    faltantes = []
    if mn < 18 and not is_ht:
        faltantes.append(f"Esperar min 18' (faltan {18 - mn} min)")
    if tt < meta_disp:
        faltantes.append(f"+{meta_disp - tt} Disp (lleva {tt}/{meta_disp})")
    if tm < meta_arco:
        faltantes.append(f"+{meta_arco - tm} Tiro al Arco (lleva {tm}/{meta_arco})")
    if not faltantes and not gatillo_ok:
        faltantes.append("Confirmar presión en área")

    detalle_filtro = "✅ ¡FILTROS COMPLETOS AL 100%!" if gatillo_ok else f"🔍 Para activar filtro: {', '.join(faltantes)}"
    return prox_pct, gatillo_ok, detalle_filtro, meta_disp, meta_arco


# =============================================================================
# 🔬 AUDITORÍA PROFUNDA VIP (CLIMA, BAJAS, H2H, ALINEACIÓN + BITÁCORA 2J CRUDOS)
# =============================================================================
@st.cache_data(ttl=900)
def obtener_extras_partido_statpal(lid, mid, local_id, visita_id, nl, nv):
    """
    Consulta los endpoints complementarios de StatPal v2 para el Paso 3 y Paso 4:
    - /soccer/leagues/{lid}/weather-forecast
    - /soccer/leagues/{lid}/injuries-suspensions
    - /soccer/head-to-head/teams/{id1}/{id2}
    - /soccer/leagues/{lid}/predictions
    """
    res = {
        "clima_txt": "🌤️ Condiciones Normales (Óptimo para fútbol ofensivo)",
        "clima_alerta": False,
        "bajas_l": [],
        "bajas_v": [],
        "h2h_txt": "Sin cerrojo histórico detectado",
        "h2h_under_cronico": False,
        "pred_statpal": ""
    }
    # 1. Clima en StatPal
    try:
        rw = requests.get(f"{_STATPAL_BASE_V2}/leagues/{lid}/weather-forecast", params={"access_key": _STATPAL_KEY}, timeout=4)
        if rw.status_code == 200:
            wf_lg = (rw.json().get("weather_forecast") or {}).get("league") or {}
            for m in _as_list(wf_lg.get("match")):
                if str(m.get("main_id", "")) == str(mid) or (
                    nombres_coinciden(str((m.get("home") or {}).get("name", "")), nl)
                ):
                    w = m.get("weather") or {}
                    desc = str(w.get("description", w.get("condition", "Despejado")))
                    temp = str(w.get("temp_c", w.get("temperature", "19")))
                    wind = _safe_float(w.get("wind_kph", w.get("wind_speed", 12)), 12.0)
                    rain = _safe_float(w.get("rain_mm", w.get("precipitation", 0)), 0.0)
                    alerta_c = wind >= 40.0 or rain >= 8.0 or any(x in desc.lower() for x in ["storm", "heavy rain", "snow", "tormenta"])
                    res["clima_alerta"] = alerta_c
                    res["clima_txt"] = f"{'⛈️ ALERTA CLIMA' if alerta_c else '🌤️ Clima Estable'}: {desc} | {temp}°C | Viento {wind:.0f} km/h"
                    break
    except Exception:
        pass

    # 2. Lesiones y suspensiones en StatPal
    try:
        ri = requests.get(f"{_STATPAL_BASE_V2}/leagues/{lid}/injuries-suspensions", params={"access_key": _STATPAL_KEY}, timeout=4)
        if ri.status_code == 200:
            inj_lg = (ri.json().get("injuries_suspensions") or {}).get("league") or {}
            for m in _as_list(inj_lg.get("match")):
                hm = m.get("home") or {}
                aw = m.get("away") or {}
                if str(m.get("main_id", "")) == str(mid) or nombres_coinciden(str(hm.get("name", "")), nl):
                    for pl in _as_list((hm.get("missing_players") or {}).get("player")):
                        p_nom = str(pl.get("name", "")).strip()
                        p_raz = str(pl.get("reason", "Baja")).strip()
                        if p_nom:
                            res["bajas_l"].append(f"{p_nom} ({p_raz})")
                    for pl in _as_list((aw.get("missing_players") or {}).get("player")):
                        p_nom = str(pl.get("name", "")).strip()
                        p_raz = str(pl.get("reason", "Baja")).strip()
                        if p_nom:
                            res["bajas_v"].append(f"{p_nom} ({p_raz})")
                    break
    except Exception:
        pass

    # 3. Head-to-Head (H2H) directo en StatPal
    if local_id and visita_id:
        try:
            rh = requests.get(f"{_STATPAL_BASE_V2}/head-to-head/teams/{local_id}/{visita_id}", params={"access_key": _STATPAL_KEY}, timeout=4)
            if rh.status_code == 200:
                h2h_node = (rh.json().get("h2h") or {}).get("matches") or {}
                lista_h2h = _as_list(h2h_node.get("match"))[:5]
                if lista_h2h:
                    goles_h2h = []
                    marcadores = []
                    for hm_m in lista_h2h[:3]:
                        gh = _safe_int((hm_m.get("home") or {}).get("goals", (hm_m.get("home") or {}).get("score", 0)), 0)
                        ga = _safe_int((hm_m.get("away") or {}).get("goals", (hm_m.get("away") or {}).get("score", 0)), 0)
                        goles_h2h.append(gh + ga)
                        marcadores.append(f"{gh}-{ga}")
                    cerrojo = len(goles_h2h) >= 2 and all(g <= 1 for g in goles_h2h[:2])
                    res["h2h_under_cronico"] = cerrojo
                    res["h2h_txt"] = (
                        f"{'🚨 ALERTA H2H UNDER' if cerrojo else '✅ H2H Favorable'}: "
                        f"Últimos cruces ({', '.join(marcadores)})"
                    )
        except Exception:
            pass

    return res

def analizar_partido_profundo_mrfutbol(partido, sta_dict, estandares_ligas, st_vivo=None):
    nl = partido["local"]
    nv = partido["visita"]
    lid = str(partido.get("league_id", ""))
    mid = str(partido.get("id", ""))

    eval_bd = evaluar_partido_big_data_completo(nl, nv, lid, sta_dict, estandares_ligas)
    extras = obtener_extras_partido_statpal(lid, mid, partido.get("local_id", ""), partido.get("visita_id", ""), nl, nv)

    comp_l = eval_bd["comp_l"]
    comp_v = eval_bd["comp_v"]
    std_l = eval_bd["std_liga"]

    # Penalización Paso 4 si hay alerta climática severa o H2H de cerrojo mutuo
    penalizacion_paso4 = 0.0
    alertas_paso4 = []
    if extras["clima_alerta"]:
        penalizacion_paso4 -= 5.0
        alertas_paso4.append(extras["clima_txt"])
    if extras["h2h_under_cronico"]:
        penalizacion_paso4 -= 6.0
        alertas_paso4.append(extras["h2h_txt"])
    if len(extras["bajas_l"]) >= 3 or len(extras["bajas_v"]) >= 3:
        penalizacion_paso4 -= 3.0
        alertas_paso4.append(f"🏥 Bajas reportadas (L:{len(extras['bajas_l'])} / V:{len(extras['bajas_v'])})")

    prob_o15_ajustada = round(max(35.0, min(96.0, eval_bd["prob_o15"] + penalizacion_paso4)), 1)
    prob_o25_ajustada = round(max(20.0, min(90.0, eval_bd["prob_o25"] + penalizacion_paso4)), 1)
    prob_o05_ht = round(min(92.0, max(45.0, (1.0 - poisson.cdf(0, eval_bd["xg_final"] * 0.45)) * 100.0 + (4.0 if comp_l["cumplidos_2"] == 2 else 0.0))), 1)

    return {
        "eval_bd": eval_bd,
        "extras": extras,
        "comp_l": comp_l,
        "comp_v": comp_v,
        "std_l": std_l,
        "prob_o15": prob_o15_ajustada,
        "prob_o25": prob_o25_ajustada,
        "prob_o05_ht": prob_o05_ht,
        "alertas_paso4": " | ".join(alertas_paso4) if alertas_paso4 else "✅ Sin bloqueos en Paso 4 (Clima, H2H y Plantilla OK)"
    }

# =============================================================================
# 🎯 AUDITOR AUTOMÁTICO DE BITÁCORA EN VIVO OVER 0.5 (NUNCA SE BORRA)
# =============================================================================
def auditar_y_registrar_bitacora_en_vivo_05(partidos_evaluados_vivo, todos_los_eventos):
    """
    1. Registra automáticamente en boveda_ml_05 todo partido en vivo 0-0 que alcance el 100% del filtro Over 0.5.
    2. Audita en tiempo real todos los partidos pendientes en boveda_ml_05:
       - Si cae 1+ gol en vivo o finalizado -> ✅ GANADA (VERDE) con minuto del primer gol y marcador.
       - Si termina 0-0 (state == 'post') -> ❌ FALLO (0-0 Final).
    3. Guarda inmediatamente en bitacora_mrfutbol_05.json para que jamás se pierda.
    """
    hubo_cambio = False
    mapa_eventos = {str(e.get("id", "")): e for e in todos_los_eventos if e.get("id")}

    # 1. Registrar nuevas activaciones en vivo
    for item in partidos_evaluados_vivo:
        if not item.get("gatillo_ok"):
            continue
        ev = item["ev"]
        mid = str(ev.get("id", ""))
        if not mid:
            continue
        if mid not in boveda_ml_05:
            boveda_ml_05[mid] = {
                "ID": mid,
                "Fecha": ev.get("fecha_iso", obtener_reloj_mexico().strftime("%Y-%m-%d")),
                "Liga": ev.get("liga_ui", ""),
                "Partido": f"{ev['local']} vs {ev['visita']}",
                "Minuto_Activacion": f"{ev['minuto']}'" if not ev.get("is_ht") else "HT (45')",
                "Disparos_Al_Activar": f"{item['dl']}-{item['dv']} (Tot: {item['tt']})",
                "Arco_Al_Activar": f"{item['al']}-{item['av']} (Tot: {item['tm']})",
                "Area_Al_Activar": f"{item['arl']}-{item['arv']} (Tot: {item['area_tot']})",
                "xG_Vivo_Al_Activar": f"{item['xg_vivo']:.2f}",
                "Prob_Pre_O15": f"{item['prob_pre']:.1f}%",
                "Respaldo_2J_Crudos": item.get("resumen_2j_corto", "Bitácora Activa"),
                "Marcador_Actual": f"{ev['gol_l']}-{ev['gol_v']}",
                "Minuto_Primer_Gol": "-",
                "Estado_Apuesta_05": "⏳ EN JUEGO (0-0)"
            }
            hubo_cambio = True

    # 2. Auditar partidos ya registrados en boveda_ml_05 contra la cartelera y bitácora histórica
    for mid, reg in list(boveda_ml_05.items()):
        estado_act = str(reg.get("Estado_Apuesta_05", ""))
        ev = mapa_eventos.get(str(mid))
        if ev:
            gl, gv = int(ev.get("gol_l", 0)), int(ev.get("gol_v", 0))
            tot_g = gl + gv
            nuevo_marc = f"{gl}-{gv}"
            if reg.get("Marcador_Actual") != nuevo_marc:
                reg["Marcador_Actual"] = nuevo_marc
                hubo_cambio = True

            if tot_g >= 1 and "GANADA" not in estado_act:
                p_min = ev.get("primer_gol_min") or f"{ev.get('minuto', 'Gol')}'"
                reg["Minuto_Primer_Gol"] = str(p_min)
                reg["Estado_Apuesta_05"] = f"✅ GANADA (VERDE {gl}-{gv})"
                hubo_cambio = True
            elif tot_g == 0 and ev.get("state") == "post" and "FALLO" not in estado_act:
                reg["Estado_Apuesta_05"] = "❌ FALLO (0-0 Final)"
                hubo_cambio = True
        elif str(mid) in bitacora_partidos_statpal:
            p_hist = bitacora_partidos_statpal[str(mid)]
            gl, gv = int(p_hist.get("gol_l", 0)), int(p_hist.get("gol_v", 0))
            if (gl + gv) >= 1 and "GANADA" not in estado_act:
                reg["Marcador_Actual"] = f"{gl}-{gv}"
                reg["Estado_Apuesta_05"] = f"✅ GANADA (VERDE {gl}-{gv})"
                hubo_cambio = True
            elif (gl + gv) == 0 and "FALLO" not in estado_act:
                reg["Marcador_Actual"] = "0-0"
                reg["Estado_Apuesta_05"] = "❌ FALLO (0-0 Final)"
                hubo_cambio = True

    if hubo_cambio:
        guardar_bitacora_servidor(boveda_ml_05)

# =============================================================================
# 📄 GENERADORES DE REPORTE OFICIAL (PASO 6) Y BOLETÍN IMPRIMIBLE HTML/PDF
# =============================================================================
def generar_reporte_oficial_txt(fecha_str, lista_picks_o15, lista_picks_o25, metricas_globales):
    lineas = [
        "===============================================================================",
        f" 📊 REPORTE JORNADA OFICIAL BIG DATA (STATPAL V2) - FECHA: {fecha_str}",
        " CREADO POR: MIGUEL RAMÍREZ | ARQUITECTURA SECUENCIAL EN 6 PASOS",
        "===============================================================================",
        f" Partidos Escaneados: {metricas_globales.get('total_escaneados', 0)} | "
        f"Aprobados Élite Over 1.5: {len(lista_picks_o15)} | "
        f"Candidatos Over 2.5: {len(lista_picks_o25)}",
        "-------------------------------------------------------------------------------",
        " 1. TABLA PRINCIPAL: SELECCIÓN ÉLITE OVER 1.5 GOLES (FILTROS STRICTO + 2J CRUDOS)",
        "-------------------------------------------------------------------------------"
    ]
    if not lista_picks_o15:
        lineas.append(" [!] Ningún partido cumple simultáneamente todos los umbrales de élite en esta fecha.")
    else:
        for i, p in enumerate(lista_picks_o15, 1):
            lineas.extend([
                f" #{i:02d} | [{p['Hora']}] {p['Liga']} | {p['Partido']}",
                f"     • Regla Big Data : {p['Regla_Cruce']}",
                f"     • Probabilidad   : {p['Prob_O15']:.1f}% Over 1.5 | Cuota: {p['Cuota_O15']:.2f} (Justa: {p['Cuota_Justa']:.2f})",
                f"     • xG / Disparo   : xG Proy: {p['xG_Proy']:.2f} (Std Liga: {p['xG_Std_Liga']:.2f}) | Calidad: {p['Carniceria']}",
                f"     • Últimos 2J (L) : {p['Local_2J_Crudos']}",
                f"     • Últimos 2J (V) : {p['Visita_2J_Crudos']}",
                f"     • Táctica / Mom. : {p['Alerta_Tactica']} | {p['Momentum']}",
                "-------------------------------------------------------------------------------"
            ])

    lineas.extend([
        "",
        "===============================================================================",
        " 2. MONITOR SECUNDARIO: CANDIDATOS OVER 2.5 GOLES (SOLO CONSULTA / PASO 5)",
        "==============================================================================="
    ])
    if not lista_picks_o25:
        lineas.append(" [i] Sin candidatos Over 2.5 que superen el filtro de Big Chances >= 4.5 y xGA >= 1.55.")
    else:
        for i, p in enumerate(lista_picks_o25, 1):
            lineas.append(
                f" #{i:02d} | [{p['Hora']}] {p['Liga']} | {p['Partido']} -> "
                f"Prob Over 2.5: {p['Prob_O25']:.1f}% | xG: {p['xG_Proy']:.2f} | Big Chances: {p['Big_Chances']:.1f}"
            )
    lineas.append("===============================================================================")
    return "\n".join(lineas)

def generar_boletin_html_imprimible(fecha_str, lista_picks_o15, lista_picks_o25):
    filas_15 = ""
    for p in lista_picks_o15:
        filas_15 += f"""
        <tr>
            <td><b>{p['Hora']}</b><br><small>{p['Liga']}</small></td>
            <td><b>{p['Partido']}</b><br><small style="color:#0284c7;">{p['Regla_Cruce']}</small></td>
            <td style="text-align:center;"><b style="color:#15803d;font-size:15px;">{p['Prob_O15']:.1f}%</b><br><small>Cuota: {p['Cuota_O15']:.2f}</small></td>
            <td style="text-align:center;"><b>{p['xG_Proy']:.2f}</b><br><small>Std: {p['xG_Std_Liga']:.2f}</small></td>
            <td><small><b>L:</b> {p['Local_2J_Crudos']}<br><b>V:</b> {p['Visita_2J_Crudos']}</small></td>
            <td><small>{p['Carniceria']}<br>{p['Alerta_Tactica']}</small></td>
        </tr>
        """
    if not filas_15:
        filas_15 = "<tr><td colspan='6' style='text-align:center;padding:16px;'>Sin partidos en esta vista</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Boletín Oficial MRFUTBOL Big Data - {fecha_str}</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 24px; color: #0f172a; background: #ffffff; }}
h1 {{ margin-bottom: 4px; color: #0f172a; font-size: 22px; }}
.sub {{ color: #475569; font-size: 13px; margin-bottom: 16px; }}
.btn-print {{ background: #16a34a; color: white; border: none; padding: 10px 18px; border-radius: 6px; font-weight: bold; cursor: pointer; margin-bottom: 16px; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 12.5px; }}
th {{ background: #0f172a; color: #f8fafc; padding: 10px; text-align: left; }}
td {{ border-bottom: 1px solid #cbd5e1; padding: 8px 10px; vertical-align: top; }}
tr:nth-child(even) {{ background: #f8fafc; }}
@media print {{ .btn-print {{ display: none; }} }}
</style>
</head>
<body>
<button class="btn-print" onclick="window.print()">🖨️ IMPRIMIR / GUARDAR COMO PDF</button>
<h1>⚽ BOLETÍN OFICIAL BIG DATA MRFUTBOL — {fecha_str}</h1>
<div class="sub">Creado por Miguel Ramírez | Motor StatPal API v2 (50,000 llamadas/día) | Comparativa Directa 2 Partidos Sin Promedios</div>
<table>
<thead>
<tr>
<th>Hora / Liga</th>
<th>Partido / Regla</th>
<th>Over 1.5 / Cuota</th>
<th>xG vs Std Liga</th>
<th>Últimos 2 Partidos Crudos (J-1 y J-2 sin promedios)</th>
<th>Calidad Disparo & Táctica</th>
</tr>
</thead>
<tbody>
{filas_15}
</tbody>
</table>
</body>
</html>"""
    return html

# =============================================================================
# 🎨 ESTILOS VISUALES PREMIUM Y RENDERIZADO CENTRAL
# =============================================================================
st.markdown("""
<style>
    .stApp { background-color: #070b14; color: #f1f5f9; }
    .mrf-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #064e3b 100%);
        border: 1px solid #22c55e;
        border-radius: 14px;
        padding: 18px 22px;
        margin-bottom: 16px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.45);
    }
    .mrf-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 12px;
    }
    .mrf-card-elite {
        background: linear-gradient(135deg, #091926 0%, #052e16 100%);
        border: 1.5px solid #22c55e;
        border-radius: 12px;
        padding: 15px 18px;
        margin-bottom: 14px;
        box-shadow: 0 4px 18px rgba(34, 197, 94, 0.18);
    }
    .mrf-card-hot {
        background: linear-gradient(135deg, #1e1b4b 0%, #3b0764 100%);
        border: 1.5px solid #f59e0b;
        border-radius: 12px;
        padding: 15px 18px;
        margin-bottom: 14px;
    }
    .mrf-pill {
        display: inline-block;
        padding: 3px 9px;
        border-radius: 999px;
        font-size: 11.5px;
        font-weight: 700;
        margin-right: 6px;
        margin-bottom: 4px;
    }
    .therm-bar-bg {
        width: 100%;
        background-color: #1e293b;
        border-radius: 10px;
        height: 16px;
        overflow: hidden;
        margin: 6px 0;
        border: 1px solid #334155;
    }
    .status-live {
        display: inline-block;
        background: #dc2626;
        color: #ffffff;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 11.5px;
        font-weight: 800;
    }
    .status-ht {
        display: inline-block;
        background: #d97706;
        color: #ffffff;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 11.5px;
        font-weight: 800;
    }
    .status-final {
        display: inline-block;
        background: #334155;
        color: #e2e8f0;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 11.5px;
        font-weight: 700;
    }
    .status-badge {
        display: inline-block;
        background: #0284c7;
        color: #ffffff;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 11.5px;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

def renderizar_central_mrfutbol():
    ahora_mx = obtener_reloj_mexico()
    sh = ahora_mx.strftime("%Y-%m-%d")
    sa = (ahora_mx - timedelta(days=1)).strftime("%Y-%m-%d")
    sm = (ahora_mx + timedelta(days=1)).strftime("%Y-%m-%d")

    # Barra Lateral: Estado de API StatPal, Corazón de Bitácora y Respaldo Permanente
    with st.sidebar:
        st.markdown("### ⚡ MOTOR STATPAL API v2")
        uso_sp = consultar_uso_real_statpal()
        if uso_sp.get("ok"):
            st.success(f"🟢 **StatPal Conectado ({uso_sp['status']})**")
            st.caption(f"Plan: **{uso_sp['plan']}** | Límite: **50,000 llamadas/día**")
            st.metric("Llamadas Usadas Hoy", f"{uso_sp['usadas_hoy']:,}", f"Restantes: {50000 - int(uso_sp['usadas_hoy']):,}")
        else:
            st.warning("🟡 Reconectando con StatPal v2...")

        st.markdown("---")
        st.markdown("### 🧠 CORAZÓN DE LA BITÁCORA")
        st.caption("La Bitácora recopila datos reales de StatPal y **nunca se borra**. Mide el estándar de xG y tiros de cada liga contra los últimos 2 partidos sin promedios.")
        c_b1, c_b2 = st.columns(2)
        c_b1.metric("Partidos Auditados", f"{len(bitacora_partidos_statpal):,}")
        c_b2.metric("Clubes en Matriz", f"{len(matriz_clubes_global):,}")
        st.metric("Bitácora En Vivo 0.5", f"{len(boveda_ml_05):,} registros")

        if st.button("🔄 Actualizar Datos En Vivo y Bitácora", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()

        with st.expander("🛡️ Respaldo Eterno (Exportar / Restaurar Bitácora)"):
            paquete_respaldo = json.dumps({
                "boveda_ml_05": boveda_ml_05,
                "boveda_vip": boveda_vip,
                "matriz_clubes_global": matriz_clubes_global,
                "bitacora_partidos_statpal": bitacora_partidos_statpal
            }, ensure_ascii=False, indent=2)
            st.download_button(
                "💾 Descargar Bitácora Completa (.JSON)",
                data=paquete_respaldo.encode("utf-8"),
                file_name=f"corazon_bitacora_mrfutbol_{sh}.json",
                mime="application/json",
                use_container_width=True
            )
            archivo_subido = st.file_uploader("Restaurar Bitácora (.JSON)", type=["json"])
            if archivo_subido is not None:
                try:
                    datos_rest = json.loads(archivo_subido.read().decode("utf-8"))
                    if isinstance(datos_rest.get("boveda_ml_05"), dict):
                        boveda_ml_05.update(datos_rest["boveda_ml_05"])
                        guardar_bitacora_servidor(boveda_ml_05)
                    if isinstance(datos_rest.get("boveda_vip"), dict):
                        boveda_vip.update(datos_rest["boveda_vip"])
                        guardar_vip_servidor(boveda_vip)
                    if isinstance(datos_rest.get("matriz_clubes_global"), dict):
                        matriz_clubes_global.update(datos_rest["matriz_clubes_global"])
                        guardar_matriz_clubes_servidor(matriz_clubes_global)
                    if isinstance(datos_rest.get("bitacora_partidos_statpal"), dict):
                        bitacora_partidos_statpal.update(datos_rest["bitacora_partidos_statpal"])
                        guardar_bitacora_partidos_servidor(bitacora_partidos_statpal)
                    st.success("✅ ¡Bitácora fusionada y guardada con éxito!")
                except Exception as e_rest:
                    st.error(f"Error al leer archivo: {e_rest}")

    # Encabezado Principal con ancla #creado-por-miguel-ramirez
    st.markdown(f"""
    <div class="mrf-header" id="creado-por-miguel-ramirez">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
            <div>
                <h2 style="margin:0;color:#f8fafc;font-size:24px;">⚽ MRFUTBOL BIG DATA — CENTRAL DE INTELIGENCIA STATPAL v2</h2>
                <div style="color:#94a3b8;font-size:13.5px;margin-top:4px;">
                    <b>Creado por Miguel Ramírez</b> | Corazón de Bitácora Permanente • Comparativa Cruda 2 Partidos (Sin Promedios) • Terminal En Vivo Over 0.5
                </div>
            </div>
            <div style="text-align:right;">
                <span class="mrf-pill" style="background:#052e16;color:#4ade80;border:1px solid #22c55e;">🕒 Hora CDMX: {ahora_mx.strftime('%H:%M')} ({sh})</span>
                <span class="mrf-pill" style="background:#0f172a;color:#38bdf8;border:1px solid #0284c7;">📡 20 Ligas Oficiales Big Data</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Carga de Cartelera, Estadísticas en Vivo, Tablas y Sincronización del Corazón de la Bitácora
    with st.spinner("Sincronizando Cartelera, Estadísticas Ópticas y Corazón de la Bitácora desde StatPal API v2..."):
        cartelera, ligas_activas = obtener_cartelera_statpal_v2()
        lids_para_stats = tuple(sorted(set(ligas_activas if ligas_activas else [l["statpal_id"] for l in LIGAS_BIG_DATA[:10]])))
        mapa_stats_vivo = obtener_mapa_stats_en_vivo_statpal(lids_para_stats)
        sta_dict, efec_ligas_real = obtener_standings_todas_ligas_statpal()
        sincronizar_bitacora_corazon_statpal(cartelera, mapa_stats_vivo)
        estandares_ligas = calcular_estandares_reales_ligas_bitacora()

    # Selector Global de Día Operativo
    col_d1, col_d2, col_d3 = st.columns([2, 2, 2])
    with col_d1:
        modo_dia = st.radio(
            "📅 Jornada Operativa:",
            options=["Hoy", "Ayer", "Mañana", "Todas (Ayer + Hoy + Mañana)"],
            index=0,
            horizontal=True
        )
    with col_d2:
        ligas_opciones = ["🌎 TODAS LAS 20 LIGAS BIG DATA"] + [l["id"] for l in LIGAS_BIG_DATA]
        liga_filtro = st.selectbox("🏆 Filtrar por Liga:", options=ligas_opciones, index=0)
    with col_d3:
        busqueda_eq = st.text_input("🔍 Buscar Club o Partido:", placeholder="Ej. Bayern, Arsenal, PSV, Barcelona...").strip()

    fechas_permitidas = {sh} if modo_dia == "Hoy" else ({sa} if modo_dia == "Ayer" else ({sm} if modo_dia == "Mañana" else {sa, sh, sm}))

    # Aplanar todos los eventos y evaluar en vivo + pre-apuesta
    todos_eventos = []
    eventos_filtrados = []
    for nombre_liga, cont in cartelera.items():
        for ev in cont.get("eventos", []):
            todos_eventos.append(ev)
            if ev.get("fecha_iso") not in fechas_permitidas and ev.get("state") != "in":
                continue
            if liga_filtro != "🌎 TODAS LAS 20 LIGAS BIG DATA" and ev.get("liga_ui") != liga_filtro:
                continue
            if busqueda_eq and (busqueda_eq.lower() not in ev["local"].lower() and busqueda_eq.lower() not in ev["visita"].lower()):
                continue
            eventos_filtrados.append(ev)

    # Pre-evaluar partidos en vivo para alimentar automáticamente la Bitácora En Vivo 0.5
    partidos_vivo_evaluados = []
    for ev in todos_eventos:
        if ev.get("state") == "in":
            mid = str(ev.get("id", ""))
            st_m = (mapa_stats_vivo.get(mid) or {}).get("stats") or {}
            eval_pre = evaluar_partido_big_data_completo(ev["local"], ev["visita"], ev["league_id"], sta_dict, estandares_ligas)
            dl = int(st_m.get("toth_l", 0))
            dv = int(st_m.get("toth_v", 0))
            al = int(st_m.get("tmeta_l", 0))
            av = int(st_m.get("tmeta_v", 0))
            arl = int(st_m.get("area_l", 0))
            arv = int(st_m.get("area_v", 0))
            cl = int(st_m.get("esquinas_l", 0))
            cv = int(st_m.get("esquinas_v", 0))
            xgl = float(st_m.get("xg_l", 0.0))
            xgv = float(st_m.get("xg_v", 0.0))
            tt = dl + dv
            tm = al + av
            md = max(dl, dv)
            area_tot = arl + arv
            xg_vivo = round(xgl + xgv, 2)
            t1, t2, t38 = calcular_tasas_tiempos_y_franja(eval_pre["xg_final"], tt, tm, cl + cv, ev["minuto"])
            prox_pct, gat_ok, det_filtro, meta_d, meta_a = calcular_termometro_proximidad_05(
                eval_pre["prob_o15"], tt, md, tm, xg_vivo, area_tot, ev["minuto"], ev["is_ht"], t38
            )
            res_2j_corto = (
                f"L(J1:{eval_pre['comp_l']['j1']['xg_f']:.2f}xG/{eval_pre['comp_l']['j1']['sot_f']}SoT) | "
                f"V(J1:{eval_pre['comp_v']['j1']['xg_f']:.2f}xG/{eval_pre['comp_v']['j1']['sot_f']}SoT)"
            )
            partidos_vivo_evaluados.append({
                "ev": ev, "st_m": st_m, "eval_pre": eval_pre,
                "dl": dl, "dv": dv, "al": al, "av": av, "arl": arl, "arv": arv,
                "cl": cl, "cv": cv, "xgl": xgl, "xgv": xgv,
                "tt": tt, "tm": tm, "md": md, "area_tot": area_tot, "xg_vivo": xg_vivo,
                "t1": t1, "t2": t2, "t38": t38,
                "prox_pct": prox_pct, "gatillo_ok": (gat_ok and (ev["gol_l"] + ev["gol_v"] == 0)),
                "detalle_filtro": det_filtro, "meta_disp": meta_d, "meta_arco": meta_a,
                "prob_pre": eval_pre["prob_o15"],
                "resumen_2j_corto": res_2j_corto
            })

    # Auditar y registrar automáticamente en la Bitácora Permanente 0.5
    auditar_y_registrar_bitacora_en_vivo_05(partidos_vivo_evaluados, todos_eventos)

    # =========================================================================
    # PESTAÑAS PRINCIPALES DEL SISTEMA
    # =========================================================================
    picks_vip_dict = boveda_vip.setdefault("picks_vip_hoy", {}) if isinstance(boveda_vip, dict) else {}

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📅 1. CARTELERA + CORAZÓN BITÁCORA",
        f"🔴 2. PARTIDOS EN VIVO ({len(partidos_vivo_evaluados)})",
        "📈 3. PRE-APUESTAS BIG DATA (6 PASOS)",
        "⚡ 4. TERMINAL EN VIVO 0.5 + TERMÓMETRO",
        f"💎 5. AUDITORÍA PROFUNDA + SALA VIP ({len(picks_vip_dict)})"
    ])

    # -------------------------------------------------------------------------
    # PESTAÑA 1: CARTELERA + CORAZÓN DE LA BITÁCORA (ESTÁNDARES Y 2J SIN PROMEDIOS)
    # -------------------------------------------------------------------------
    with tab1:
        st.markdown("#### 🧠 Corazón de Recopilación de Datos: Estándares Reales por Liga vs Últimos 2 Partidos (Sin Promedios)")
        with st.expander("📊 Ver Estándares Reales de xG y Tiros de las 20 Ligas medidos por la Bitácora", expanded=False):
            filas_std = []
            for idx_l, l_meta in enumerate(LIGAS_BIG_DATA, 1):
                lid = l_meta["statpal_id"]
                st_l = estandares_ligas.get(lid, {})
                cat_l = "🔥 Élite Top (86-91%)" if l_meta["efec"] >= 86.0 else ("⚡ Alta Confianza (81-85%)" if l_meta["efec"] >= 81.0 else "🛡️ Estándar Pro (79-80%)")
                filas_std.append({
                    "Ranking": f"#{l_meta.get('rank', idx_l):02d}",
                    "Liga": l_meta["id"],
                    "Categoría": l_meta.get("cat", cat_l),
                    "Muestra Bitácora": f"{st_l.get('muestra_partidos', 0)} PJ",
                    "xG Estándar / Partido": st_l.get("xg_partido_std", l_meta["xg_std"]),
                    "xG Estándar / Equipo": st_l.get("xg_equipo_std", round(l_meta["xg_std"] / 2, 2)),
                    "Tiros al Arco Std / Eq": st_l.get("sot_equipo_std", l_meta["sot_std"]),
                    "Disparos Totales Std / Eq": st_l.get("disp_equipo_std", l_meta["disp_std"]),
                    "% Over 1.5 Efectividad": f"{st_l.get('efec_combinada', l_meta['efec']):.1f}%"
                })
            st.dataframe(pd.DataFrame(filas_std), use_container_width=True, hide_index=True)

        st.markdown(f"#### 📅 Cartelera Oficial StatPal v2 ({modo_dia}) — {len(eventos_filtrados)} Partidos Encontrados")
        if not eventos_filtrados:
            st.info("No hay partidos programados con el filtro actual. Prueba cambiando 'Jornada Operativa' a 'Todas (Ayer + Hoy + Mañana)'.")
        else:
            # Agrupar por liga
            por_liga_ui = {}
            for ev in eventos_filtrados:
                por_liga_ui.setdefault(ev["liga_ui"], []).append(ev)

            for nom_l, lista_ev in por_liga_ui.items():
                lid_actual = lista_ev[0]["league_id"]
                std_actual = estandares_ligas.get(str(lid_actual), {})
                st.markdown(
                    f"**{nom_l}** — <small style='color:#38bdf8;'>Estándar Liga en Bitácora: "
                    f"<b>{std_actual.get('xg_partido_std', 2.60):.2f} xG/Partido</b> ({std_actual.get('xg_equipo_std', 1.30):.2f} xG/Eq) | "
                    f"<b>{std_actual.get('sot_equipo_std', 5.2):.1f} Tiros al Arco/Eq</b> | "
                    f"Efectividad Over 1.5: <b>{std_actual.get('efec_combinada', 80.0):.1f}%</b></small>",
                    unsafe_allow_html=True
                )
                for ev in sorted(lista_ev, key=lambda x: x["hora_local"]):
                    comp_l = obtener_ultimos_2_partidos_crudos_bitacora(ev["local"], ev["league_id"], estandares_ligas)
                    comp_v = obtener_ultimos_2_partidos_crudos_bitacora(ev["visita"], ev["league_id"], estandares_ligas)
                    marc_txt = f"{ev['gol_l']} - {ev['gol_v']}" if ev["state"] in ("in", "post") else "vs"
                    st.markdown(f"""
                    <div class="mrf-card">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <div>
                                {ev['badge_html']} <b style="font-size:15.5px;color:#f8fafc;margin-left:8px;">{ev['local']} <span style="color:#22c55e;">{marc_txt}</span> {ev['visita']}</b>
                                <span style="color:#94a3b8;font-size:12px;margin-left:8px;">({ev['fecha_iso']} • {ev['reloj_txt']})</span>
                            </div>
                            <div>
                                <span class="mrf-pill" style="background:#1e293b;color:#cbd5e1;">Std Liga: {std_actual.get('xg_equipo_std',1.3):.2f} xG / {std_actual.get('sot_equipo_std',5.0):.1f} SoT</span>
                            </div>
                        </div>
                        <div style="margin-top:8px;font-size:12.5px;color:#cbd5e1;background:#070b14;padding:8px 12px;border-radius:8px;border-left:3px solid #38bdf8;">
                            <div>🏠 <b>{ev['local']} (Últimos 2 Juegos SIN Promedios):</b> {comp_l['texto_comparativo']}</div>
                            <div style="margin-top:4px;">✈️ <b>{ev['visita']} (Últimos 2 Juegos SIN Promedios):</b> {comp_v['texto_comparativo']}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # PESTAÑA 2: PARTIDOS EN VIVO (ESTADÍSTICAS REALES STATPAL)
    # -------------------------------------------------------------------------
    with tab2:
        st.markdown("#### 🔴 Monitor de Partidos en Vivo con Estadísticas Reales StatPal v2")
        if not partidos_vivo_evaluados:
            st.info("En este instante no hay partidos en juego ('in-play') dentro de las 20 ligas seleccionadas. Revisa la Pestaña 3 para Pre-Apuestas o la Pestaña 4 para la Bitácora 0.5.")
        else:
            for item in partidos_vivo_evaluados:
                ev = item["ev"]
                st.markdown(f"""
                <div class="mrf-card-elite">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            {ev['badge_html']} <b style="font-size:17px;color:#ffffff;margin-left:8px;">{ev['local']} <span style="color:#4ade80;">{ev['gol_l']} - {ev['gol_v']}</span> {ev['visita']}</b>
                            <span style="color:#cbd5e1;font-size:12.5px;margin-left:8px;">• {ev['liga_ui']}</span>
                        </div>
                        <div>
                            <span class="mrf-pill" style="background:#0284c7;color:#fff;">xG Vivo: {item['xgl']:.2f} - {item['xgv']:.2f} (Tot: {item['xg_vivo']:.2f})</span>
                            <span class="mrf-pill" style="background:#15803d;color:#fff;">Pre Over 1.5: {item['prob_pre']:.1f}%</span>
                        </div>
                    </div>
                    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:10px;text-align:center;background:#070b14;padding:10px;border-radius:8px;">
                        <div><small style="color:#94a3b8;">Disparos Totales</small><br><b style="font-size:15px;">{item['dl']} - {item['dv']} ({item['tt']})</b></div>
                        <div><small style="color:#94a3b8;">Tiros al Arco (SoT)</small><br><b style="font-size:15px;color:#4ade80;">{item['al']} - {item['av']} ({item['tm']})</b></div>
                        <div><small style="color:#94a3b8;">Tiros Dentro Área</small><br><b style="font-size:15px;color:#38bdf8;">{item['arl']} - {item['arv']} ({item['area_tot']})</b></div>
                        <div><small style="color:#94a3b8;">Córners</small><br><b style="font-size:15px;">{item['cl']} - {item['cv']}</b></div>
                        <div><small style="color:#94a3b8;">Proximidad Filtro 0.5</small><br><b style="font-size:15px;color:#facc15;">{item['prox_pct']}%</b></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # PESTAÑA 3: PRE-APUESTAS BIG DATA (LOS 6 PASOS + COMPARATIVA 2 PARTIDOS)
    # -------------------------------------------------------------------------
    with tab3:
        st.markdown("#### 📈 Motor Pre-Apuestas Big Data (Arquitectura Secuencial de 6 Pasos + Comparativa Cruda 2 Partidos)")
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            umbral_prob_o15 = st.slider("🎯 Probabilidad Mínima Over 1.5 (%)", min_value=60.0, max_value=92.0, value=74.0, step=1.0)
        with col_f2:
            solo_rango_bancario = st.checkbox("🏦 Solo Rango Bancario Cuota (1.05 - 1.45)", value=False)
        with col_f3:
            exigir_consistencia_2j = st.checkbox("🔥 Exigir que al menos 2 de los 4 juegos crudos superen el Estándar Liga", value=True)

        picks_o15 = []
        picks_o25 = []

        for ev in eventos_filtrados:
            eval_bd = evaluar_partido_big_data_completo(ev["local"], ev["visita"], ev["league_id"], sta_dict, estandares_ligas)
            comp_l = eval_bd["comp_l"]
            comp_v = eval_bd["comp_v"]
            std_l = eval_bd["std_liga"]
            tot_cumplidos = comp_l["cumplidos_2"] + comp_v["cumplidos_2"]

            if exigir_consistencia_2j and tot_cumplidos < 2:
                continue
            if solo_rango_bancario and not eval_bd["en_rango_bancario"]:
                continue

            registro_pick = {
                "ID": ev["id"],
                "Fecha": ev["fecha_iso"],
                "Hora": ev["hora_local"],
                "Liga": ev["liga_ui"],
                "Partido": f"{ev['local']} vs {ev['visita']}",
                "Local": ev["local"],
                "Visita": ev["visita"],
                "Estado": ev["state"],
                "Marcador": f"{ev['gol_l']}-{ev['gol_v']}" if ev["state"] in ("in", "post") else "PRE",
                "Prob_O15": eval_bd["prob_o15"],
                "Prob_O25": eval_bd["prob_o25"],
                "Cuota_O15": eval_bd["cuota_o15"],
                "Cuota_Justa": eval_bd["cuota_justa"],
                "xG_Proy": eval_bd["xg_final"],
                "xG_Std_Liga": std_l["xg_partido_std"],
                "SoT_J1_Comb": eval_bd["sot_j1_comb"],
                "SoT_J2_Comb": eval_bd["sot_j2_comb"],
                "Big_Chances": eval_bd["big_chances_comb"],
                "Carniceria": eval_bd["estado_carniceria"],
                "Regla_Cruce": eval_bd["regla_cruce"],
                "Alerta_Tactica": eval_bd["alerta_tactica"],
                "Momentum": eval_bd["notas_momentum"],
                "Urgencia": eval_bd["urgencia_txt"],
                "Local_2J_Crudos": comp_l["texto_comparativo"],
                "Visita_2J_Crudos": comp_v["texto_comparativo"],
                "Cumplidos_4": f"{tot_cumplidos}/4 Juegos >= Std Liga",
                "ev_raw": ev,
                "eval_raw": eval_bd
            }

            if eval_bd["prob_o15"] >= umbral_prob_o15:
                picks_o15.append(registro_pick)
            if eval_bd["candidato_o25"]:
                picks_o25.append(registro_pick)

        picks_o15.sort(key=lambda x: (x["Prob_O15"], x["xG_Proy"]), reverse=True)
        picks_o25.sort(key=lambda x: (x["Prob_O25"], x["xG_Proy"]), reverse=True)

        # Botones de Exportación Oficial Paso 6 (TXT, CSV y Boletín HTML/PDF)
        txt_rep = generar_reporte_oficial_txt(sh, picks_o15, picks_o25, {"total_escaneados": len(eventos_filtrados)})
        html_bol = generar_boletin_html_imprimible(sh, picks_o15, picks_o25)

        c_ex1, c_ex2, c_ex3 = st.columns(3)
        with c_ex1:
            st.download_button(
                "📄 Descargar reporte_jornada_oficial.txt (Paso 6)",
                data=txt_rep.encode("utf-8"),
                file_name="reporte_jornada_oficial.txt",
                mime="text/plain",
                use_container_width=True
            )
        with c_ex2:
            st.download_button(
                "🖨️ Descargar Boletín Imprimible (HTML / PDF)",
                data=html_bol.encode("utf-8"),
                file_name=f"boletin_bigdata_mrfutbol_{sh}.html",
                mime="text/html",
                use_container_width=True
            )
        with c_ex3:
            if picks_o15:
                df_exp = pd.DataFrame([{k: v for k, v in p.items() if k not in ("ev_raw", "eval_raw")} for p in picks_o15])
                st.download_button(
                    "📊 Exportar Tabla Pre-Apuestas (.CSV)",
                    data=df_exp.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"pre_apuestas_bigdata_{sh}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

        st.markdown(f"##### 🏆 Selección Élite Over 1.5 Goles ({len(picks_o15)} Partidos Aprobados)")
        if not picks_o15:
            st.warning("Ningún partido de la vista actual supera el umbral seleccionado. Puedes bajar el deslizador de probabilidad o cambiar la Jornada Operativa.")
        else:
            for idx, p in enumerate(picks_o15):
                es_regla_a = "REGLA A" in p["Regla_Cruce"]
                clase_c = "mrf-card-elite" if es_regla_a or p["Prob_O15"] >= 82.0 else "mrf-card"
                st.markdown(f"""
                <div class="{clase_c}">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
                        <div>
                            <span class="mrf-pill" style="background:#0f172a;color:#38bdf8;border:1px solid #0284c7;">{p['Hora']} • {p['Liga']}</span>
                            <b style="font-size:17px;color:#ffffff;">{p['Partido']}</b>
                            <span class="mrf-pill" style="background:#1e293b;color:#facc15;margin-left:6px;">{p['Regla_Cruce']}</span>
                        </div>
                        <div>
                            <span class="mrf-pill" style="background:#15803d;color:#ffffff;font-size:13.5px;">🔥 Over 1.5: {p['Prob_O15']:.1f}%</span>
                            <span class="mrf-pill" style="background:#0369a1;color:#ffffff;">Over 2.5: {p['Prob_O25']:.1f}%</span>
                            <span class="mrf-pill" style="background:#334155;color:#f8fafc;">Cuota: {p['Cuota_O15']:.2f} (Justa {p['Cuota_Justa']:.2f})</span>
                        </div>
                    </div>
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px;background:#070b14;padding:10px;border-radius:8px;font-size:12.5px;">
                        <div><span style="color:#94a3b8;">xG Proy vs Std Liga:</span><br><b style="color:#4ade80;">{p['xG_Proy']:.2f} xG</b> <small>(Std: {p['xG_Std_Liga']:.2f})</small></div>
                        <div><span style="color:#94a3b8;">Tiros al Arco Crudos:</span><br><b>J-1: {p['SoT_J1_Comb']} SoT | J-2: {p['SoT_J2_Comb']} SoT</b></div>
                        <div><span style="color:#94a3b8;">Calidad Disparo (Paso 3):</span><br><b>{p['Carniceria']}</b></div>
                        <div><span style="color:#94a3b8;">Consistencia Bitácora:</span><br><b style="color:#38bdf8;">{p['Cumplidos_4']}</b></div>
                    </div>
                    <div style="margin-top:8px;font-size:12px;color:#cbd5e1;padding:6px 10px;background:#090d16;border-radius:6px;">
                        <div>🏠 <b>{p['Local']} (2J Crudos):</b> {p['Local_2J_Crudos']}</div>
                        <div style="margin-top:3px;">✈️ <b>{p['Visita']} (2J Crudos):</b> {p['Visita_2J_Crudos']}</div>
                        <div style="margin-top:4px;color:#94a3b8;">🧠 <b>Táctica & Momentum:</b> {p['Alerta_Tactica']} | {p['Momentum']} | {p['Urgencia']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button(f"💎 Enviar a Sala VIP: {p['Partido']}", key=f"vip_btn_{p['ID']}_{idx}"):
                    picks_vip_dict[str(p["ID"])] = {
                        "ID": str(p["ID"]),
                        "Fecha": p["Fecha"],
                        "Hora": p["Hora"],
                        "Liga": p["Liga"],
                        "Partido": p["Partido"],
                        "Prob_O15": p["Prob_O15"],
                        "Cuota_O15": p["Cuota_O15"],
                        "xG_Proy": p["xG_Proy"],
                        "Regla": p["Regla_Cruce"],
                        "Estado": "📌 EN SEGUIMIENTO VIP"
                    }
                    guardar_vip_servidor(boveda_vip)
                    st.success(f"✅ {p['Partido']} guardado en la Sala VIP.")

        with st.expander(f"🔥 Monitor Secundario Over 2.5 Goles — Paso 5 ({len(picks_o25)} Candidatos)", expanded=False):
            if not picks_o25:
                st.caption("Sin candidatos Over 2.5 en este filtro.")
            else:
                df_25 = pd.DataFrame([{
                    "Hora": p["Hora"], "Liga": p["Liga"], "Partido": p["Partido"],
                    "Prob Over 2.5 (%)": p["Prob_O25"], "xG Proy": p["xG_Proy"],
                    "Big Chances Comb": p["Big_Chances"], "Calidad Disparo": p["Carniceria"]
                } for p in picks_o25])
                st.dataframe(df_25, use_container_width=True, hide_index=True)

    # -------------------------------------------------------------------------
    # PESTAÑA 4: TERMINAL EN VIVO OVER 0.5 + TERMÓMETRO DE PROXIMIDAD Y BITÁCORA
    # -------------------------------------------------------------------------
    with tab4:
        st.markdown("#### ⚡ Terminal Quirúrgica En Vivo Over 0.5 Goles + Termómetro de Proximidad a los Filtros")
        st.caption(
            "Muestra en tiempo real las estadísticas de cada partido en vivo y **qué tan cerca (0% a 100%)** está de activar el gatillo Over 0.5, "
            "respaldado por los últimos 2 partidos crudos de la Bitácora. Cuando llega al 100% en 0-0, se registra y audita solo en la Bitácora Permanente."
        )

        if not partidos_vivo_evaluados:
            st.info("No hay partidos en vivo en este momento. Abajo puedes consultar y descargar la Bitácora Permanente Over 0.5.")
        else:
            # Ordenar por mayor proximidad al filtro (los que están al 100% o más cerca primero)
            ordenados_vivo_05 = sorted(
                partidos_vivo_evaluados,
                key=lambda x: (1 if (x["ev"]["gol_l"] + x["ev"]["gol_v"] == 0) else 0, x["prox_pct"], x["prob_pre"]),
                reverse=True
            )
            for item in ordenados_vivo_05:
                ev = item["ev"]
                sin_goles = (ev["gol_l"] + ev["gol_v"]) == 0
                pct = item["prox_pct"]
                color_barra = "#22c55e" if pct >= 100 else ("#f59e0b" if pct >= 70 else "#38bdf8")
                card_cls = "mrf-card-elite" if (pct >= 100 and sin_goles) else ("mrf-card-hot" if (pct >= 75 and sin_goles) else "mrf-card")

                estado_gol_txt = (
                    "🚨 ¡GATILLO OVER 0.5 ACTIVADO EN 0-0! (REGISTRADO EN BITÁCORA)"
                    if (pct >= 100 and sin_goles)
                    else ("🔥 CALENTANDO FILTRO EN 0-0" if sin_goles else f"⚽ YA HAY GOL ({ev['gol_l']}-{ev['gol_v']}) — MONITOR OVER +0.5 ADICIONAL")
                )

                st.markdown(f"""
                <div class="{card_cls}">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
                        <div>
                            {ev['badge_html']} <b style="font-size:17px;color:#ffffff;margin-left:8px;">{ev['local']} <span style="color:#4ade80;">{ev['gol_l']} - {ev['gol_v']}</span> {ev['visita']}</b>
                            <span style="color:#94a3b8;font-size:12px;margin-left:8px;">({ev['liga_ui']})</span>
                        </div>
                        <div>
                            <span class="mrf-pill" style="background:{color_barra};color:#070b14;font-size:13px;">🌡️ Proximidad al Filtro: {pct}%</span>
                            <span class="mrf-pill" style="background:#1e293b;color:#f8fafc;">{estado_gol_txt}</span>
                        </div>
                    </div>
                    <div class="therm-bar-bg">
                        <div style="width:{pct}%;background:{color_barra};height:100%;transition:width 0.4s;"></div>
                    </div>
                    <div style="font-size:12.5px;color:#facc15;font-weight:600;margin-bottom:8px;">
                        {item['detalle_filtro']} &nbsp;|&nbsp;
                        <span style="color:#38bdf8;">Tasa 1T: {item['t1']:.1f}% • Tasa 2T: {item['t2']:.1f}% • Franja 38'-HT: {item['t38']:.1f}%</span>
                    </div>
                    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;background:#070b14;padding:9px;border-radius:8px;text-align:center;font-size:12.5px;">
                        <div><span style="color:#94a3b8;">Disparos (Meta ≥{item['meta_disp']})</span><br><b>{item['dl']} - {item['dv']} (Tot: {item['tt']})</b></div>
                        <div><span style="color:#94a3b8;">Al Arco (Meta ≥{item['meta_arco']})</span><br><b style="color:#4ade80;">{item['al']} - {item['av']} (Tot: {item['tm']})</b></div>
                        <div><span style="color:#94a3b8;">Dentro del Área</span><br><b style="color:#38bdf8;">{item['arl']} - {item['arv']} (Tot: {item['area_tot']})</b></div>
                        <div><span style="color:#94a3b8;">xG en Vivo</span><br><b>{item['xgl']:.2f} - {item['xgv']:.2f} ({item['xg_vivo']:.2f})</b></div>
                        <div><span style="color:#94a3b8;">Respaldo 2J Crudos</span><br><b>{item['eval_pre']['comp_l']['cumplidos_2'] + item['eval_pre']['comp_v']['cumplidos_2']}/4 >= Std Liga</b></div>
                    </div>
                    <div style="margin-top:6px;font-size:11.5px;color:#cbd5e1;">
                        🧠 <b>Soporte Bitácora 2J Sin Promedios:</b> {item['resumen_2j_corto']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### 📓 Bitácora Permanente de Alertas En Vivo Over 0.5 (Auditoría Automática)")
        regs_05 = list(boveda_ml_05.values())
        ganadas_05 = sum(1 for r in regs_05 if "GANADA" in str(r.get("Estado_Apuesta_05", "")))
        fallos_05 = sum(1 for r in regs_05 if "FALLO" in str(r.get("Estado_Apuesta_05", "")))
        en_juego_05 = sum(1 for r in regs_05 if "EN JUEGO" in str(r.get("Estado_Apuesta_05", "")))
        cerradas_05 = ganadas_05 + fallos_05
        winrate_05 = round((ganadas_05 / cerradas_05) * 100.0, 1) if cerradas_05 > 0 else 100.0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Alertas 0.5", len(regs_05))
        m2.metric("✅ Ganadas (Verde)", ganadas_05)
        m3.metric("⏳ En Juego / ❌ Fallos", f"{en_juego_05} / {fallos_05}")
        m4.metric("🎯 Efectividad Real Bitácora", f"{winrate_05:.1f}%")

        if regs_05:
            df_bit05 = pd.DataFrame(list(reversed(regs_05)))
            st.dataframe(df_bit05, use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Descargar Bitácora En Vivo Over 0.5 (.CSV)",
                data=df_bit05.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"bitacora_vivo_05_{sh}.csv",
                mime="text/csv"
            )
        else:
            st.caption("La Bitácora En Vivo 0.5 está lista y registrará automáticamente el primer partido que alcance el 100% del filtro.")

    # -------------------------------------------------------------------------
    # PESTAÑA 5: AUDITORÍA PROFUNDA 1 A 1 + SALA VIP
    # -------------------------------------------------------------------------
    with tab5:
        st.markdown("#### 🔬 Laboratorio de Auditoría Profunda 1 a 1 (Clima, Bajas, H2H y Comparativa 2 Partidos Sin Promedios)")
        if not eventos_filtrados:
            st.info("Selecciona una jornada con partidos para usar el Laboratorio de Auditoría Profunda.")
        else:
            mapa_sel = {f"[{e['hora_local']}] {e['liga_ui']} — {e['local']} vs {e['visita']}": e for e in eventos_filtrados}
            etiqueta_sel = st.selectbox("Selecciona un partido para auditar a fondo:", options=list(mapa_sel.keys()))
            if etiqueta_sel:
                ev_sel = mapa_sel[etiqueta_sel]
                aud_prof = analizar_partido_profundo_mrfutbol(ev_sel, sta_dict, estandares_ligas)
                eb = aud_prof["eval_bd"]
                ex = aud_prof["extras"]
                cl = aud_prof["comp_l"]
                cv = aud_prof["comp_v"]
                sl = aud_prof["std_l"]

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Probabilidad Over 1.5", f"{aud_prof['prob_o15']:.1f}%", f"Cuota: {eb['cuota_o15']:.2f}")
                k2.metric("Probabilidad Over 0.5 HT", f"{aud_prof['prob_o05_ht']:.1f}%", "1er Tiempo")
                k3.metric("Probabilidad Over 2.5", f"{aud_prof['prob_o25']:.1f}%", f"BigCh: {eb['big_chances_comb']:.1f}")
                k4.metric("xG Proyectado vs Liga", f"{eb['xg_final']:.2f} xG", f"Std Liga: {sl['xg_partido_std']:.2f}")

                st.markdown(f"""
                <div class="mrf-card">
                    <b>🛡️ Auditoría Paso 3 y Paso 4 (StatPal API v2):</b><br>
                    • <b>Regla de Cruce:</b> {eb['regla_cruce']}<br>
                    • <b>Calidad de Disparo (Carnicería):</b> {eb['estado_carniceria']} | <b>Táctica:</b> {eb['alerta_tactica']}<br>
                    • <b>Sistema Colectivo 10.5 (Últimos 5J):</b> Local ({cl['unique_scorers']} goleadores / {cl['unique_assisters']} asistentes) • Visita ({cv['unique_scorers']} goleadores / {cv['unique_assisters']} asistentes)<br>
                    • <b>Clima:</b> {ex['clima_txt']} | <b>H2H:</b> {ex['h2h_txt']}<br>
                    • <b>Bajas Local ({len(ex['bajas_l'])}):</b> {', '.join(ex['bajas_l'][:5]) if ex['bajas_l'] else 'Plantilla Completa'}<br>
                    • <b>Bajas Visita ({len(ex['bajas_v'])}):</b> {', '.join(ex['bajas_v'][:5]) if ex['bajas_v'] else 'Plantilla Completa'}
                </div>
                """, unsafe_allow_html=True)

                st.markdown("##### 📊 Comparativa Directa: Últimos 2 Partidos Como Vienen (SIN PROMEDIOS) vs Estándar de la Liga")
                df_comp_2j = pd.DataFrame([
                    {
                        "Equipo / Referencia": f"📏 ESTÁNDAR LIGA ({ev_sel['liga_ui']})",
                        "Partido": f"Muestra: {sl.get('muestra_partidos', 0)} PJ en Bitácora",
                        "xG": sl["xg_equipo_std"],
                        "Tiros al Arco (SoT)": sl["sot_equipo_std"],
                        "Disparos Totales": sl["disp_equipo_std"],
                        "Tiros en Área": round(sl["disp_equipo_std"] * 0.60, 1),
                        "xG / Disparo": round(sl["xg_equipo_std"] / max(1.0, sl["disp_equipo_std"]), 3),
                        "Veredicto vs Liga": "🎯 Línea Base Oficial"
                    },
                    {
                        "Equipo / Referencia": f"🏠 {ev_sel['local']} (J-1 Último)",
                        "Partido": f"{cl['j1']['raw'].get('fecha','')} vs {cl['j1']['raw'].get('rival','')} ({cl['j1']['gf']}-{cl['j1']['gc']})",
                        "xG": cl["j1"]["xg_f"],
                        "Tiros al Arco (SoT)": cl["j1"]["sot_f"],
                        "Disparos Totales": cl["j1"]["disp_f"],
                        "Tiros en Área": cl["j1"]["area_f"],
                        "xG / Disparo": cl["j1"]["qual"],
                        "Veredicto vs Liga": "✅ SUPERA ESTÁNDAR" if cl["j1"]["cumple"] else "❄️ BAJO ESTÁNDAR"
                    },
                    {
                        "Equipo / Referencia": f"🏠 {ev_sel['local']} (J-2 Penúltimo)",
                        "Partido": f"{cl['j2']['raw'].get('fecha','')} vs {cl['j2']['raw'].get('rival','')} ({cl['j2']['gf']}-{cl['j2']['gc']})",
                        "xG": cl["j2"]["xg_f"],
                        "Tiros al Arco (SoT)": cl["j2"]["sot_f"],
                        "Disparos Totales": cl["j2"]["disp_f"],
                        "Tiros en Área": cl["j2"]["area_f"],
                        "xG / Disparo": cl["j2"]["qual"],
                        "Veredicto vs Liga": "✅ SUPERA ESTÁNDAR" if cl["j2"]["cumple"] else "❄️ BAJO ESTÁNDAR"
                    },
                    {
                        "Equipo / Referencia": f"✈️ {ev_sel['visita']} (J-1 Último)",
                        "Partido": f"{cv['j1']['raw'].get('fecha','')} vs {cv['j1']['raw'].get('rival','')} ({cv['j1']['gf']}-{cv['j1']['gc']})",
                        "xG": cv["j1"]["xg_f"],
                        "Tiros al Arco (SoT)": cv["j1"]["sot_f"],
                        "Disparos Totales": cv["j1"]["disp_f"],
                        "Tiros en Área": cv["j1"]["area_f"],
                        "xG / Disparo": cv["j1"]["qual"],
                        "Veredicto vs Liga": "✅ SUPERA ESTÁNDAR" if cv["j1"]["cumple"] else "❄️ BAJO ESTÁNDAR"
                    },
                    {
                        "Equipo / Referencia": f"✈️ {ev_sel['visita']} (J-2 Penúltimo)",
                        "Partido": f"{cv['j2']['raw'].get('fecha','')} vs {cv['j2']['raw'].get('rival','')} ({cv['j2']['gf']}-{cv['j2']['gc']})",
                        "xG": cv["j2"]["xg_f"],
                        "Tiros al Arco (SoT)": cv["j2"]["sot_f"],
                        "Disparos Totales": cv["j2"]["disp_f"],
                        "Tiros en Área": cv["j2"]["area_f"],
                        "xG / Disparo": cv["j2"]["qual"],
                        "Veredicto vs Liga": "✅ SUPERA ESTÁNDAR" if cv["j2"]["cumple"] else "❄️ BAJO ESTÁNDAR"
                    }
                ])
                st.dataframe(df_comp_2j, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### 💎 Sala VIP de Seguimiento")
        if picks_vip_dict:
            st.dataframe(pd.DataFrame(list(picks_vip_dict.values())), use_container_width=True, hide_index=True)
        else:
            st.caption("Usa el botón '💎 Enviar a Sala VIP' en la Pestaña 3 para fijar tus partidos favoritos aquí.")

renderizar_central_mrfutbol()
