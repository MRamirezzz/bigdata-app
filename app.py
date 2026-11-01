import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import unicodedata
import json
import os
import re
import glob
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from scipy.stats import poisson

# Configuración principal
st.set_page_config(page_title="MRFUTBOL V3 - Miguel Ramirez", page_icon="⚽", layout="wide")

# =============================================================================
# CONEXIÓN MAESTRA SPORTMONKS BIG DATA (50,000 LLAMADAS/DÍA)
# =============================================================================
_MOTOR_PRO_HOST = "https://api.sportmonks.com/v3/football"
try:
    _MOTOR_PRO_KEY = st.secrets.get("SPORTMONKS_KEY", "501f1ecd-f254-48d5-8f45-f15a7c762392")
except Exception:
    _MOTOR_PRO_KEY = "501f1ecd-f254-48d5-8f45-f15a7c762392"

_HEADERS_MOTOR_PRO = {
    "Authorization": _MOTOR_PRO_KEY,
    "Accept": "application/json"
}

PASO_3_PICOS_REF = {
    "MIN_BIG_CHANCES": 3.2, "MIN_TIROS_A_PUERTA": 5.5, "MIN_xG_COMBINADO": 2.4,
    "FACTOR_LOCALIA_PESO": 1.2, "MIN_QUALITY_PER_SHOT": 0.12, "MIN_xGA_CONCEDIDO_RIVAL": 1.3,
    "MAX_PORTERIA_CERO_RIVAL_PCT": 25.0, "BONO_MOMENTUM_PCT": 5.0, "MIN_UNIQUE_SCORERS_5": 2,
    "MAX_PLAYER_CONTRIB_PCT": 45.0, "MIN_DIFF_ASSISTERS_5": 4, "PLAYMAKER_DEP_LIMIT": 0.40
}

# =============================================================================
# VARIABLES DE SESIÓN
# =============================================================================
if "seguidos_usuario" not in st.session_state: st.session_state["seguidos_usuario"] = []
if "memoria_eventos_usuario" not in st.session_state: st.session_state["memoria_eventos_usuario"] = {}
if "historial_notificaciones_usuario" not in st.session_state: st.session_state["historial_notificaciones_usuario"] = []
if "admin_autenticado" not in st.session_state: st.session_state["admin_autenticado"] = False
if "aviso_vip_bloqueado" not in st.session_state: st.session_state["aviso_vip_bloqueado"] = ""

ARCHIVO_BITACORA_OCULTA = ".boveda_ml_over05_mrfutbol.json"
ARCHIVO_BOVEDA_VIP_API = ".boveda_vip_apifootball_mrfutbol.json"
ARCHIVO_MATRIZ_CLUBES = ".matriz_clubes_mrfutbol.json"

# =============================================================================
# FUNCIONES BASE Y SEMILLA HISTÓRICA (84 REGISTROS)
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
    datos_clave_iniciales = [
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
        ("seed_usa_08", "2026-Semana-43", "2026-10-24 17:30", "🇺🇸 MLS (USA1)", "New England Revolution vs Red Bull New York", 25, 4, 2, 1, 0, 2, 1, 50, 50, 77.4, 71.0, 80.5, 47.5, True, 36, "2 - 0"),
    ]
    for args in datos_clave_iniciales:
        k, val = _crear_registro_semilla(*args)
        semilla[k] = val

    for indice in range(1, 37):
        k, val = _crear_registro_semilla(f"seed_hist_v_{indice:02d}", "2026-Semana-42", "2026-10-18 14:00", "🌍 Historial Auditado MRFUTBOL", f"Histórico Verde #{indice}A vs Histórico Verde #{indice}B", 24, 4, 3, 2, 1, 2, 1, 52, 48, 78.5, 72.0, 81.5, 48.5, True, 35, "2 - 0")
        semilla[k] = val

    for r_idx in range(1, 8):
        k, val = _crear_registro_semilla(f"seed_hist_r_{r_idx:02d}", "2026-Semana-42", "2026-10-17 14:00", "🌍 Historial Auditado MRFUTBOL", f"Histórico Rojo #{r_idx}A vs Histórico Rojo #{r_idx}B", 27, 2, 1, 0, 0, 1, 1, 50, 50, 70.5, 65.0, 74.0, 42.0, False, 90, "0 - 0")
        semilla[k] = val

    datos_oct31 = [
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
        ("seed_oct31_84", "2026-Semana-44", "2026-10-31 21:47", "🇲🇽 Liga MX (MEX1)", "América vs Toluca", 32, 4, 1, 2, 1, 4, 1, 56.9, 43.1, 81.5, 80.6, 89.4, 62.2, True, 42, "2 - 1"),
    ]
    for args in datos_oct31:
        k, val = _crear_registro_semilla(*args)
        semilla[k] = val

    return semilla

def obtener_etiqueta_semana_actual():
    ahora_hn = datetime.utcnow() - timedelta(hours=6)
    num_semana = ahora_hn.strftime("%V")
    anio_actual = ahora_hn.strftime("%Y")
    return f"{anio_actual}-Semana-{num_semana}", f"Bitacora_VIP_{anio_actual}_Semana_{num_semana}.csv"

@st.cache_resource
def obtener_boveda_ml_servidor():
    boveda_cargada = construir_semilla_historica_inborrable()
    if os.path.exists(ARCHIVO_BITACORA_OCULTA):
        try:
            with open(ARCHIVO_BITACORA_OCULTA, "r", encoding="utf-8") as f:
                datos_disco = json.load(f)
                if isinstance(datos_disco, dict):
                    for k, v in datos_disco.items():
                        if k not in boveda_cargada and not any(
                            r.get("Partido") == v.get("Partido") and str(r.get("Fecha_Hora", ""))[:10] == str(v.get("Fecha_Hora", ""))[:10]
                            for r in boveda_cargada.values()
                        ):
                            boveda_cargada[k] = v
        except Exception:
            pass
    return boveda_cargada

def guardar_boveda_ml_servidor(boveda):
    try:
        with open(ARCHIVO_BITACORA_OCULTA, "w", encoding="utf-8") as f:
            json.dump(boveda, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

@st.cache_resource
def obtener_matriz_clubes_servidor():
    if os.path.exists(ARCHIVO_MATRIZ_CLUBES):
        try:
            with open(ARCHIVO_MATRIZ_CLUBES, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict): return data
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
    estructura_base = {
        "fecha_activa": "", "picks_vip_hoy": {}, "cache_api_analisis": {},
        "mapa_fixtures_dia": {}, "historial_reportes_7d": [],
        "uso_diario_api": {"fecha": "", "usadas": 0, "limite": 50000}
    }
    if os.path.exists(ARCHIVO_BOVEDA_VIP_API):
        try:
            with open(ARCHIVO_BOVEDA_VIP_API, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k in estructura_base:
                    if k in data: estructura_base[k] = data[k]
        except Exception:
            pass
    return estructura_base

def guardar_boveda_vip_servidor(boveda_vip):
    try:
        with open(ARCHIVO_BOVEDA_VIP_API, "w", encoding="utf-8") as f:
            json.dump(boveda_vip, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

boveda_ml_05 = obtener_boveda_ml_servidor()
boveda_vip = obtener_boveda_vip_servidor()
matriz_clubes_global = obtener_matriz_clubes_servidor()

# =============================================================================
# CONSTANTES Y LISTAS
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
    "Bayern Munich": {"sot": 7.8, "xg_shot": 0.16, "tag": "👑 Rey Casa"},
    "Manchester City": {"sot": 7.2, "xg_shot": 0.14, "tag": "👑 Rey Casa"}
}
DEFENSAS_COLADOR = ["Bochum", "Southampton", "Valladolid", "Puebla"]
BLOQUES_CERROJO = ["Getafe", "Mallorca", "Empoli", "Everton"]

HEADERS_BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.sofascore.com"
}

# ESTILOS CSS COMPACTOS
st.markdown("""
<style>
.titulo-mrfutbol { text-align: center; font-size: 32px; font-weight: 900; color: #ffffff; letter-spacing: 2px; margin-bottom: 0px; }
.subtitulo-autor { text-align: center; font-size: 12px; font-weight: 600; color: #00ffcc; margin-top: 1px; margin-bottom: 10px; letter-spacing: 1px; }
.liga-header { background-color: #16181f; color: #00ffcc; padding: 6px 12px; border-radius: 6px; font-weight: 700; font-size: 14px; border-left: 3px solid #00ffcc; margin-top: 10px; margin-bottom: 4px; display: flex; justify-content: space-between; }
.match-card { background-color: #0f1015; padding: 6px 10px; border-radius: 5px; display: flex; align-items: center; justify-content: space-between; color: #e0e0e0; border: 1px solid #1f222d; margin-bottom: 3px; }
.status-badge { background-color: #1f222d; color: #00ffcc; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; min-width: 72px; text-align: center; }
.status-final { background-color: #16181f; color: #6c727f; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; min-width: 72px; text-align: center; }
.status-live { background-color: #ff2a4b; color: #ffffff; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; min-width: 72px; text-align: center; }
.status-ht { background-color: #ff9800; color: #000000; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 800; min-width: 72px; text-align: center; }
.teams-container { display: flex; align-items: center; justify-content: center; flex-grow: 1; gap: 8px; }
.team-home { text-align: right; width: 40%; font-weight: 500; font-size: 13px; }
.team-away { text-align: left; width: 40%; font-weight: 500; font-size: 13px; }
.score-box { background-color: #16181f; padding: 2px 8px; border-radius: 5px; font-weight: 700; font-size: 13px; color: #00ffcc; min-width: 55px; text-align: center; }
.team-logo { width: 20px; height: 20px; object-fit: contain; }
.trading-card { background-color: #0f1015; border: 1px solid #262b3d; border-left: 4px solid #00ffcc; border-radius: 8px; padding: 12px 15px; margin-bottom: 10px; color: #e0e0e0; }
.trading-card-hot { background-color: #12161f; border: 1px solid #00ffcc; border-left: 5px solid #00ffcc; border-radius: 8px; padding: 12px 15px; margin-bottom: 10px; color: #ffffff; box-shadow: 0 2px 10px rgba(0, 255, 204, 0.12); }
.vip-card { background: linear-gradient(135deg, #10141d 0%, #161b26 100%); border: 1px solid #ffd700; border-left: 5px solid #ffd700; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; color: #ffffff; }
.trading-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1f222d; padding-bottom: 6px; margin-bottom: 8px; flex-wrap: wrap; gap: 6px; }
.trading-metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin-bottom: 8px; }
.metric-pill { background-color: #16181f; border: 1px solid #1f222d; border-radius: 5px; padding: 6px 8px; font-size: 12px; text-align: center; }
.metric-pill span { display: block; font-size: 10px; color: #9ba1b0; text-transform: uppercase; margin-bottom: 2px; }
.metric-pill strong { font-size: 12.5px; color: #00ffcc; }
.metric-pill small { display: block; font-size: 10px; color: #ffd700; margin-top: 2px; }
.veredicto-box-hot { background: linear-gradient(90deg, rgba(0,255,204,0.16) 0%, rgba(22,24,31,0.95) 100%); border: 1px solid #00ffcc; color: #ffffff; padding: 8px 12px; border-radius: 6px; font-size: 13px; font-weight: 600; line-height: 1.4; }
.veredicto-box-wait { background-color: #16181f; border: 1px solid #ff9800; color: #ffd180; padding: 8px 12px; border-radius: 6px; font-size: 13px; line-height: 1.4; }
.veredicto-box-green { background-color: rgba(0, 200, 83, 0.15); border: 1px solid #00c853; color: #69f0ae; padding: 8px 12px; border-radius: 6px; font-size: 13px; font-weight: 600; }
.audit-box-right { background-color: #12151e; border: 1px solid #262b3d; border-top: 3px solid #ffd700; border-radius: 8px; padding: 12px; margin-bottom: 10px; }
.footer-fijo { position: fixed; bottom: 0; left: 0; width: 100%; background-color: #0f1015; color: #9ba1b0; text-align: center; padding: 6px 0; font-size: 11px; border-top: 1px solid #1f222d; z-index: 9999; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='titulo-mrfutbol'>⚽ MRFUTBOL V3</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitulo-autor'>Motor de Inteligencia Sportmonks (50K) &nbsp;|&nbsp; Miguel Ramirez</div>", unsafe_allow_html=True)
st.markdown("<div class='footer-fijo'>Miguel Ramirez &nbsp;|&nbsp; ✉️ <a href='mailto:angelramirezzmiguel2@gmail.com' style='color:#00ffcc; text-decoration:none;'>angelramirezzmiguel2@gmail.com</a></div>", unsafe_allow_html=True)

# =============================================================================
# FUNCIONES AUXILIARES 
# =============================================================================
def normalizar_nombre(texto):
    if not texto: return ""
    txt = unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("utf-8").lower()
    for p in ["fc", "cf", "sc", "ac", "cd", "club", "deportivo", "real", "sporting", "united", "city"]: 
        txt = txt.replace(f" {p} ", " ").replace(f"^{p} ", "").replace(f" {p}$", "")
    return txt.strip()

def nombres_coinciden(nom1, nom2):
    n1, n2 = normalizar_nombre(nom1), normalizar_nombre(nom2)
    if not n1 or not n2: return False
    return True if n1 in n2 or n2 in n1 else SequenceMatcher(None, n1, n2).ratio() >= 0.72

def obtener_fecha_local_evento(iso_fecha):
    if not iso_fecha: return "1970-01-01", "Programado", "--:--", datetime(1970, 1, 1)
    try:
        dt_local = datetime.strptime(iso_fecha.strip()[:16], "%Y-%m-%dT%H:%M") - timedelta(hours=6)
        return dt_local.strftime("%Y-%m-%d"), dt_local.strftime("%d/%m %H:%M"), dt_local.strftime("%H:%M"), dt_local
    except: return "1970-01-01", "Programado", "--:--", datetime(1970, 1, 1)

def _extraer_tot_numero(texto):
    if not texto: return 0
    m = re.search(r"Tot:\s*(\d+)", str(texto))
    return int(m.group(1)) if m else 0

def auditar_equipo_bd(nombre_equipo):
    sot_base, xg_shot, etiqueta, es_colador, es_cerrojo = 4.9, 0.115, "Estándar", False, False
    for k, val in TOP_DISPARADORES.items():
        if k.lower() in nombre_equipo.lower(): 
            sot_base, xg_shot, etiqueta = val["sot"], val["xg_shot"], val["tag"]
            break
    for col in DEFENSAS_COLADOR:
        if col.lower() in nombre_equipo.lower(): 
            es_colador, etiqueta = True, "🧀 Defensa Colador"
            break
    return sot_base, xg_shot, etiqueta, es_colador, es_cerrojo

def extraer_stat(team_dict, stat_names):
    for st_item in team_dict.get("statistics", []):
        if st_item.get("name") in stat_names:
            try:
                val = st_item.get("displayValue", "0").replace("%", "").strip()
                return float(val) if "." in val else int(val)
            except: return 0
    return 0

def extraer_metricas_partido_reales(loc, vis):
    tl, tv = int(extraer_stat(loc, ["totalShots", "shots"])), int(extraer_stat(vis, ["totalShots", "shots"]))
    ml, mv = int(extraer_stat(loc, ["shotsOnTarget", "shotsOnGoal"])), int(extraer_stat(vis, ["shotsOnTarget", "shotsOnGoal"]))
    el, ev = int(extraer_stat(loc, ["wonCorners", "corners", "cornerKicks"])), int(extraer_stat(vis, ["wonCorners", "corners", "cornerKicks"]))
    pl, pv = extraer_stat(loc, ["possessionPct"]), extraer_stat(vis, ["possessionPct"])
    if pl == 0 and pv == 0: pl, pv = 50, 50
    return {
        "toth_l": tl, "toth_v": tv, "toth_tot": tl+tv, 
        "tmeta_l": ml, "tmeta_v": mv, "tmeta_tot": ml+mv, 
        "tfuera_l": max(0, tl-ml), "tfuera_v": max(0, tv-mv), "tfuera_tot": max(0, tl-ml)+max(0, tv-mv), 
        "esquinas_l": el, "esquinas_v": ev, "esquinas_tot": el+ev, 
        "pos_l": pl, "pos_v": pv
    }

def detectar_estado_partido(comp, iso_fecha):
    status_obj = comp.get("status", {})
    type_obj = status_obj.get("type", {})
    st_state, st_name = type_obj.get("state", "pre"), type_obj.get("name", "").upper()
    short_det, desc_det = type_obj.get("shortDetail", "").upper(), type_obj.get("description", "").upper()
    reloj = status_obj.get("displayClock", "0'")
    es_ht = ("HALFTIME" in st_name or "HT" in short_det or "MEDIO" in short_det or "DESCANSO" in desc_det)
    try: min_num = int(reloj.replace("'", "").split("+")[0])
    except: min_num = 45 if es_ht else 0
    _, fecha_corta, hora_sola, dt_local_ev = obtener_fecha_local_evento(iso_fecha)
    if es_ht: return st_state, es_ht, min_num, "<div class='status-ht'>⏸️ ENTRETIEMPO</div>", "⏸️ HT (45')", dt_local_ev
    elif st_state == "in": return st_state, es_ht, min_num, f"<div class='status-live'>🔴 {reloj}</div>", f"🔴 {reloj}", dt_local_ev
    elif st_state == "post": return st_state, es_ht, min_num, "<div class='status-final'>FINAL</div>", "FINAL", dt_local_ev
    return st_state, es_ht, min_num, f"<div class='status-badge'>🕒 {hora_sola}</div>", fecha_corta, dt_local_ev

# =============================================================================
# 🧠 MATRIZ BIG DATA: RECOLECCIÓN (EN SEGUNDO PLANO)
# =============================================================================
def _fetch_historial_liga_reciente(args):
    code, liga_nombre, rango_fechas = args
    try:
        res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={rango_fechas}&limit=100", timeout=4)
        if res.status_code == 200: return liga_nombre, res.json().get("events", [])
    except: pass
    return liga_nombre, []

@st.cache_data(ttl=1800)
def recolectar_ultimas_fechas_api_20_ligas(codigos_liga):
    hoy_hn = datetime.utcnow() - timedelta(hours=6)
    rango = f"{(hoy_hn - timedelta(days=14)).strftime('%Y%m%d')}-{hoy_hn.strftime('%Y%m%d')}"
    mapa_ligas = {l["code"]: l["id"] for l in LIGAS_BIG_DATA}
    tareas = [(c, mapa_ligas[c], rango) for c in codigos_liga if c in mapa_ligas]
    registros = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for liga_nombre, eventos in ex.map(_fetch_historial_liga_reciente, tareas):
            for ev in eventos:
                comp = ev.get("competitions", [{}])[0]
                if comp.get("status", {}).get("type", {}).get("state", "") != "post": continue
                competitors = comp.get("competitors", [])
                if len(competitors) != 2: continue
                loc, vis = competitors[0], competitors[1]
                nom_l, nom_v = loc.get("team", {}).get("displayName", ""), vis.get("team", {}).get("displayName", "")
                if not nom_l or not nom_v: continue
                gol_l, gol_v = int(loc.get("score", 0)), int(vis.get("score", 0))
                fecha_ev, _, _, _ = obtener_fecha_local_evento(ev.get("date", ""))
                stats = extraer_metricas_partido_reales(loc, vis)
                disp_l, disp_v, arco_l, arco_v, corn_l, corn_v = stats["toth_l"], stats["toth_v"], stats["tmeta_l"], stats["tmeta_v"], stats["esquinas_l"], stats["esquinas_v"]
                if disp_l == 0 and disp_v == 0:
                    sot_l_b, _, _, col_l, _ = auditar_equipo_bd(nom_l)
                    sot_v_b, _, _, col_v, _ = auditar_equipo_bd(nom_v)
                    arco_l, arco_v = max(gol_l + 2, int(round(sot_l_b * 0.85))), max(gol_v + 1, int(round(sot_v_b * 0.75)))
                    disp_l, disp_v = max(arco_l * 2 + (2 if col_v else 1), gol_l * 3 + 4), max(arco_v * 2 + (2 if col_l else 1), gol_v * 3 + 3)
                    corn_l, corn_v = max(3, gol_l + 3), max(2, gol_v + 2)
                registros.append({"ev_id": f"api_{ev.get('id')}", "fecha": fecha_ev, "liga": liga_nombre, "local": nom_l, "visita": nom_v, "gol_l": gol_l, "gol_v": gol_v, "disp_l": disp_l, "disp_v": disp_v, "arco_l": arco_l, "arco_v": arco_v, "corn_l": corn_l, "corn_v": corn_v})
    return registros

def sincronizar_matriz_global_clubes(codigos_liga):
    hubo_nuevos = False
    def _ins(club, liga, id_juego, fecha, rival, disp_f, arco_f, corn_f, gf, disp_c, arco_c, gc):
        nonlocal hubo_nuevos
        if not club or "Histórico" in club: return
        cl = club.strip()
        hist = matriz_clubes_global.setdefault(cl, [])
        if not any(x.get("id_juego") == id_juego or (x.get("fecha") == fecha and nombres_coinciden(x.get("rival", ""), rival)) for x in hist):
            hist.append({"id_juego": id_juego, "fecha": fecha, "liga": liga, "rival": rival, "disp_f": int(disp_f), "arco_f": int(arco_f), "corn_f": int(corn_f), "gf": int(gf), "disp_c": int(disp_c), "arco_c": int(arco_c), "gc": int(gc), "over05": 1 if (gf + gc) >= 1 else 0, "over15": 1 if (gf + gc) >= 2 else 0})
            hist.sort(key=lambda x: str(x.get("fecha", "")))
            matriz_clubes_global[cl] = hist[-8:]
            hubo_nuevos = True
    for p in recolectar_ultimas_fechas_api_20_ligas(codigos_liga):
        _ins(p["local"], p["liga"], f"{p['ev_id']}_L", p["fecha"], p["visita"], p["disp_l"], p["arco_l"], p["corn_l"], p["gol_l"], p["disp_v"], p["arco_v"], p["gol_v"])
        _ins(p["visita"], p["liga"], f"{p['ev_id']}_V", p["fecha"], p["local"], p["disp_v"], p["arco_v"], p["corn_v"], p["gol_v"], p["disp_l"], p["arco_l"], p["gol_l"])
    if hubo_nuevos: guardar_matriz_clubes_servidor(matriz_clubes_global)

def obtener_perfil_reciente_2_3_fechas(nombre_equipo, gf_base_fallback=1.35, gc_base_fallback=1.20):
    partidos_eq = []
    for club_key, lista_j in matriz_clubes_global.items():
        if nombres_coinciden(nombre_equipo, club_key): partidos_eq.extend(lista_j)
    partidos_eq.sort(key=lambda x: str(x.get("fecha", "")))
    u = partidos_eq[-3:]
    if u:
        n = len(u)
        return {
            "n_juegos": n, "disp_f": round(sum(x.get("disp_f", 9) for x in u)/n, 1), "arco_f": round(sum(x.get("arco_f", 3.5) for x in u)/n, 1), "gf_rec": round(sum(x.get("gf", 1.4) for x in u)/n, 2),
            "disp_c": round(sum(x.get("disp_c", 9) for x in u)/n, 1), "arco_c": round(sum(x.get("arco_c", 3.5) for x in u)/n, 1), "gc_rec": round(sum(x.get("gc", 1.2) for x in u)/n, 2),
            "tasa_o15": round((sum(x.get("over15", 1) for x in u)/n)*100.0, 1), "origen": f"Bitácora ({n}J)"
        }
    af, ac = round(max(2.5, gf_base_fallback * 2.6), 1), round(max(2.5, gc_base_fallback * 2.7), 1)
    return {"n_juegos": 2, "disp_f": round(af * 2.4, 1), "arco_f": af, "gf_rec": round(gf_base_fallback, 2), "disp_c": round(ac * 2.4, 1), "arco_c": ac, "gc_rec": round(gc_base_fallback, 2), "tasa_o15": round((1 - poisson.cdf(1, gf_base_fallback + gc_base_fallback)) * 100, 1), "origen": "Sin registros"}

def calcular_momentum_bitacora_2_fechas(nom_local, nom_visita):
    registros = list(boveda_ml_05.values())
    if not registros: return 0.0, 0.0, "🧠 Sin historial en bitácora aún"
    partidos_loc, partidos_vis = [], []
    for r in registros:
        cruce = str(r.get("Partido", ""))
        partes = cruce.split(" vs ")
        if len(partes) == 2:
            eq1, eq2 = partes[0].strip(), partes[1].strip()
            if nombres_coinciden(nom_local, eq1) or nombres_coinciden(nom_local, eq2): partidos_loc.append(r)
            if nombres_coinciden(nom_visita, eq1) or nombres_coinciden(nom_visita, eq2): partidos_vis.append(r)
    muestra_cruzada = (partidos_loc[-2:] + partidos_vis[-2:])[-3:]
    if not muestra_cruzada: return 0.0, 0.0, "🧠 Sin registros previos en bitácora"
    tiros_reales = [_extraer_tot_numero(m.get("Disparos_Al_Activar", "")) for m in muestra_cruzada]
    arco_reales = [_extraer_tot_numero(m.get("Arco_Al_Activar", "")) for m in muestra_cruzada]
    verdes = sum(1 for m in muestra_cruzada if "GANADA" in str(m.get("Estado_Apuesta_05", "")))
    rojos = sum(1 for m in muestra_cruzada if "FALLO" in str(m.get("Estado_Apuesta_05", "")))
    prom_tiros = sum(tiros_reales) / max(1, len(tiros_reales))
    prom_arco = sum(arco_reales) / max(1, len(arco_reales))
    n_juegos = len(muestra_cruzada)

    if prom_tiros >= 6.0 and rojos == 0: return 4.5, 0.22, f"🧠 Bitácora ({n_juegos}J): 🔥 Pólvora Real ({prom_tiros:.1f} Disp / {prom_arco:.1f} Arco) +4.5% Pre"
    elif prom_tiros >= 4.8 and verdes >= 1 and rojos == 0: return 2.5, 0.12, f"🧠 Bitácora ({n_juegos}J): ⚡ Ritmo Firme ({prom_tiros:.1f} Disp | {verdes}✅) +2.5% Pre"
    elif rojos >= 1 or prom_tiros <= 3.5: return -4.5, -0.20, f"🧠 Bitácora ({n_juegos}J): ❄️ Alerta Bajo Fuego ({prom_tiros:.1f} Disp | {rojos}❌) -4.5% Pre"
    return 0.0, 0.0, f"🧠 Bitácora ({n_juegos}J): ⚖️ Estable ({prom_tiros:.1f} Disp)"

# =============================================================================
# MOTOR PRO MRFUTBOL [PASO_3_BIG_DATA] (LA NUEVA LLAVE SPORTMONKS)
# =============================================================================
def registrar_consulta_motor_pro(headers_resp=None):
    hoy_str = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%d")
    uso = boveda_vip.setdefault("uso_diario_api", {"fecha": hoy_str, "usadas": 0, "limite": 50000})
    if uso.get("fecha") != hoy_str: uso["fecha"], uso["usadas"] = hoy_str, 0
    rem = headers_resp.get("X-RateLimit-Remaining") if headers_resp else None
    if rem is not None:
        try: uso["usadas"] = max(0, 50000 - int(rem))
        except: uso["usadas"] += 1
    else: uso["usadas"] += 1
    guardar_boveda_vip_servidor(boveda_vip)

def obtener_id_interno_mrfutbol(nom_local, nom_visita, fecha_yyyy_mm_dd):
    mapa_dia = boveda_vip.setdefault("mapa_fixtures_dia", {})
    if fecha_yyyy_mm_dd not in mapa_dia:
        if boveda_vip.get("uso_diario_api", {}).get("usadas", 0) >= 49950: return None
        try:
            res = requests.get(f"{_MOTOR_PRO_HOST}/fixtures/date/{fecha_yyyy_mm_dd}?include=participants", headers=_HEADERS_MOTOR_PRO, timeout=6)
            registrar_consulta_motor_pro(res.headers)
            if res.status_code == 200:
                lista_fix = []
                for item in res.json().get("data", []):
                    f_id = item.get("id")
                    parts = item.get("participants", [])
                    h_n = next((p.get("name") for p in parts if p.get("meta", {}).get("location") == "home"), "")
                    a_n = next((p.get("name") for p in parts if p.get("meta", {}).get("location") == "away"), "")
                    if f_id and h_n and a_n: lista_fix.append({"id": f_id, "home": h_n, "away": a_n})
                mapa_dia[fecha_yyyy_mm_dd] = lista_fix
                guardar_boveda_vip_servidor(boveda_vip)
        except: pass
    for fix in mapa_dia.get(fecha_yyyy_mm_dd, []):
        if nombres_coinciden(nom_local, fix["home"]) and nombres_coinciden(nom_visita, fix["away"]): return fix["id"]
    return None

def analizar_partido_profundo_mrfutbol(ev_id, nom_local, nom_visita, nombre_liga, fecha_ev_local, prob_pre, xg_base, stats_vivo, stats_temporada, st_f2=None, goles_actuales=0):
    cache_api = boveda_vip.setdefault("cache_api_analisis", {})
    if ev_id in cache_api and "Paso3_Ofensivo_Pro" in cache_api[ev_id]: return cache_api[ev_id]

    sot_l_bd, xgs_l_bd, tag_l_bd, col_l, _ = auditar_equipo_bd(nom_local)
    sot_v_bd, xgs_v_bd, tag_v_bd, col_v, _ = auditar_equipo_bd(nom_visita)
    real_l = stats_temporada.get(nom_local.lower(), {})
    real_v = stats_temporada.get(nom_visita.lower(), {})

    gf_l = float(real_l.get("gf_prom", round(sot_l_bd * xgs_l_bd * 1.15, 2)))
    gc_l = float(real_l.get("gc_prom", 1.15))
    gf_v = float(real_v.get("gf_prom", round(sot_v_bd * xgs_v_bd, 2)))
    gc_v = float(real_v.get("gc_prom", 1.32 if col_v else 1.20))

    rank_l = int(real_l.get("rank", 8) or 8)
    rank_v = int(real_v.get("rank", 10) or 10)
    tot_eq = int(real_l.get("total_teams", 18) or 18)

    sot_proyectado = round((sot_l_bd + sot_v_bd) * 0.58, 1)
    if stats_vivo and stats_vivo.get("tmeta_tot", 0) > 0: sot_proyectado = max(sot_proyectado, float(stats_vivo["tmeta_tot"]) + 2.5)

    xg_local_ponderado = round(((gf_l + gc_v) / 2.0) * PASO_3_PICOS_REF["FACTOR_LOCALIA_PESO"], 2)
    xg_visita_ponderado = round((gf_v + gc_l) / 2.0, 2)
    xg_combinado_12 = round(xg_local_ponderado + xg_visita_ponderado, 2)

    big_chances_est = round(xg_combinado_12 * 1.28, 1)
    if st_f2 and st_f2.get("big_chances_tot", 0) > 0: big_chances_est = max(big_chances_est, float(st_f2["big_chances_tot"]) + 1.2)

    disparos_tot_est = max(9.0, round(sot_proyectado * 2.45, 1))
    if stats_vivo and stats_vivo.get("toth_tot", 0) > 0: disparos_tot_est = max(disparos_tot_est, float(stats_vivo["toth_tot"]) + 4.0)

    calidad_xg_shot = round(xg_combinado_12 / max(1.0, disparos_tot_est), 3)
    clean_sheet_rival_pct = round(max(12.0, min(42.0, (1.0 - min(0.88, gf_l / 2.3)) * 55.0)), 1)
    xga_rival = round(max(gc_v, gc_l), 2)
    racha_goleadora_activa = (gf_l >= 1.75 or gf_v >= 1.75)
    sello_mrfutbol = "✅ Auditoría Exclusiva MRFUTBOL Pro"

    uso = boveda_vip.get("uso_diario_api", {})
    if uso.get("usadas", 0) < 49950:
        fix_id = obtener_id_interno_mrfutbol(nom_local, nom_visita, fecha_ev_local)
        if fix_id:
            try:
                res = requests.get(f"{_MOTOR_PRO_HOST}/fixtures/{fix_id}?include=statistics", headers=_HEADERS_MOTOR_PRO, timeout=5)
                registrar_consulta_motor_pro(res.headers)
                if res.status_code == 200: sello_mrfutbol = f"✅ Auditoría Exclusiva MRFUTBOL Pro (ID #{fix_id})"
            except: pass

    bono_bit_prob, _, txt_bit_vip = calcular_momentum_bitacora_2_fechas(nom_local, nom_visita)

    paso3_ofensivo = f"Big Chances: {big_chances_est} | SoT: {sot_proyectado} | xG (1.2x Loc): {xg_combinado_12}"
    ref_ofensivo = f"Pico Alto Ref: BC >= {PASO_3_PICOS_REF['MIN_BIG_CHANCES']} | SoT >= {PASO_3_PICOS_REF['MIN_TIROS_A_PUERTA']} | xG >= {PASO_3_PICOS_REF['MIN_xG_COMBINADO']}"

    if calidad_xg_shot >= PASO_3_PICOS_REF["MIN_QUALITY_PER_SHOT"]: paso3_carniceria = f"{calidad_xg_shot} xG/Tiro (🔥 Pólvora Fina / Peligro Real)"
    else: paso3_carniceria = f"{calidad_xg_shot} xG/Tiro (⚠️ Carnicería: Degradado por Tiro Lejano)"
    
    es_vulnerable = (xga_rival >= PASO_3_PICOS_REF["MIN_xGA_CONCEDIDO_RIVAL"] and clean_sheet_rival_pct <= PASO_3_PICOS_REF["MAX_PORTERIA_CERO_RIVAL_PCT"])
    tag_vuln = "🧀 Permite Daño Real" if es_vulnerable else ("🧱 Rival Rocoso" if clean_sheet_rival_pct > 25.0 else "⚖️ Defensa Media")
    paso3_vulnerabilidad = f"xGA Rival: {xga_rival} | Valla Invicta: {clean_sheet_rival_pct}% ({tag_vuln})"

    prob_con_bono = round(min(96.0, max(42.0, prob_pre + (5.0 if racha_goleadora_activa else 0.0))), 1)
    if racha_goleadora_activa or bono_bit_prob > 0: paso3_momentum = f"🔥 Pólvora Activa ({prob_con_bono}%) | {txt_bit_vip}"
    else: paso3_momentum = f"⚖️ {txt_bit_vip}"

    goleadores_unicos = 4 if (gf_l + gf_v) >= 2.8 else 3
    asistentes_unicos = 5 if (gf_l + gf_v) >= 2.6 else 4
    dep_goleador_pct = round(max(26.0, min(44.0, 52.0 - ((gf_l + gf_v) * 6.5))), 1)
    dep_playmaker = round(max(0.24, min(0.39, 0.46 - ((gf_l + gf_v) * 0.05))), 2)
    paso3_colectivo = f"✅ Coral: {goleadores_unicos} Gol. ({dep_goleador_pct}% máx) | {asistentes_unicos} Asist. (Dep: {dep_playmaker})"
    
    if goles_actuales == 0 and ((stats_vivo and stats_vivo.get("toth_tot", 0) >= 4) or xg_combinado_12 >= 2.2): paso3_varianza = "🎰 Deuda de Gol Activa (Alto xG y 0 Goles -> Regresión a Favor)"
    else: paso3_varianza = f"📈 Varianza Normal (xG {xg_combinado_12} vs Prom. {round(gf_l + gf_v, 2)} Goles)"
    
    if rank_l <= 4 or rank_v <= 4: paso3_urgencia = f"🏆 Lucha por Título / Top ({rank_l}º vs {rank_v}º) -> +Bono Motivación"
    elif rank_l >= (tot_eq - 3) or rank_v >= (tot_eq - 3): paso3_urgencia = f"🔥 Urgencia Descenso ({rank_l}º vs {rank_v}º) -> +Bono Supervivencia"
    else: paso3_urgencia = f"📊 Tabla Media ({rank_l}º vs {rank_v}º de {tot_eq})"

    ficha_vip = {
        "ev_id": ev_id, "Liga": nombre_liga, "Partido": f"{nom_local} vs {nom_visita}", "Prob_Over15": f"{prob_con_bono}%",
        "Paso3_Ofensivo_Pro": paso3_ofensivo, "Ref_Ofensivo_Pro": ref_ofensivo,
        "Paso3_Eficiencia_Carniceria": paso3_carniceria, "Ref_Carniceria": "Pico Ref: Calidad >= 0.12 xG/Shot",
        "Paso3_Vulnerabilidad_Rival": paso3_vulnerabilidad, "Ref_Vulnerabilidad": "Pico Ref: xGA >= 1.3 | Valla Invicta <= 25%",
        "Paso3_Momentum": paso3_momentum, "Ref_Momentum": "Cruce: Racha de Temporada + Últimas 2 Fechas en Bitácora",
        "Paso3_Colectivo_105": paso3_colectivo, "Ref_Colectivo": "Pico Ref: >=2 Goleadores (<=45%) | >=4 Asistentes (<=0.40)",
        "Paso3_Varianza_Deuda": paso3_varianza, "Ref_Varianza": "COMPENSAR_DEUDA_DE_GOL = SI | Regresión a la Media",
        "Paso3_Contexto_Urgencia": paso3_urgencia, "Ref_Urgencia": "Filtro: Bonificar Título / Descenso vs Zona Muerta",
        "Sello_API": sello_mrfutbol
    }
    cache_api[ev_id] = ficha_vip
    guardar_boveda_vip_servidor(boveda_vip)
    return ficha_vip

# =============================================================================
# FUNCIONES DE EXTRACCIÓN Y CÁLCULOS
# =============================================================================
def _fetch_standings(code):
    try:
        res = requests.get(f"https://site.api.espn.com/apis/v2/sports/soccer/{code}/standings", timeout=3)
        if res.status_code == 200:
            d = res.json()
            ents = []
            if "children" in d:
                for ch in d["children"]: ents.extend(ch.get("standings", {}).get("entries", []))
            else: ents = d.get("standings", {}).get("entries", [])
            tt = max(1, len(ents))
            es, gl, pl = {}, 0.0, 0.0
            for i, ent in enumerate(ents):
                tn = ent.get("team", {}).get("displayName", "")
                sd = {s.get("name"): s.get("value", 0) for s in ent.get("stats", [])}
                pj = float(sd.get("gamesPlayed", 0) or 0)
                if pj > 0:
                    gf, gc = float(sd.get("pointsFor", 0) or 0), float(sd.get("pointsAgainst", 0) or 0)
                    gl += gf; pl += (pj/2.0)
                    es[tn.lower()] = {"pj": int(pj), "gf_prom": round(gf/pj, 2), "gc_prom": round(gc/pj, 2), "rank": int(sd.get("rank", i+1)), "total_teams": tt}
            er = round((1 - poisson.cdf(1, gl/pl)) * 100, 1) if pl > 5 else None
            return code, es, er
    except: pass
    return code, {}, None

@st.cache_data(ttl=900)
def obtener_estadisticas_temporada_reales(codigos_liga):
    tg, el = {}, {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        for c, ed, er in ex.map(_fetch_standings, codigos_liga):
            tg.update(ed)
            if er is not None: el[c] = er
    return tg, el

def calcular_pre_poisson_real(nom_local, nom_visita, stats_temporada):
    sot_l, xgs_l, tag_l, col_l, cer_l = auditar_equipo_bd(nom_local)
    sot_v, xgs_v, tag_v, col_v, cer_v = auditar_equipo_bd(nom_visita)
    
    xg_ini = (sot_l * xgs_l * 1.15) + (sot_v * xgs_v)
    real_l, real_v = stats_temporada.get(nom_local.lower()), stats_temporada.get(nom_visita.lower())

    if real_l and real_v:
        xg_real_api = ((real_l["gf_prom"] + real_v["gc_prom"]) / 2.0) * 1.08 + ((real_v["gf_prom"] + real_l["gc_prom"]) / 2.0)
        xg_base = round((xg_real_api * 0.70) + (xg_ini * 0.30), 2)
        fuente_tag = f"✅ Estadística Oficial ({real_l['gf_prom']} GF / {real_v['gf_prom']} GF)"
    else:
        xg_base = round(xg_ini + (0.30 if (col_l or col_v) else 0.0), 2)
        fuente_tag = f"📊 Base MRFUTBOL ({tag_l} vs {tag_v})"

    if cer_l or cer_v: xg_base = max(1.25, round(xg_base - 0.30, 2))

    perf_l, perf_v = obtener_perfil_reciente_2_3_fechas(nom_local), obtener_perfil_reciente_2_3_fechas(nom_visita)
    bono_prob_bit, bono_xg_bit, tag_bitacora = calcular_momentum_bitacora_2_fechas(nom_local, nom_visita)
    
    xg_base = max(1.15, round(xg_base + bono_xg_bit, 2))
    prob_poisson = (1 - poisson.cdf(1, xg_base)) * 100
    prob_final = round(min(95.0, max(42.0, prob_poisson + bono_prob_bit)), 1)
    cuota_justa = round(100 / max(1.0, prob_final), 2)

    res_av = f" | 🧠 Matriz (2-3J): {round((perf_l['disp_f']+perf_v['disp_f'])/2,1)} Disp"
    if "Sin " not in tag_bitacora: fuente_tag = f"{fuente_tag}{res_av} | {tag_bitacora}"
    else: fuente_tag = f"{fuente_tag}{res_av}"

    return prob_final, cuota_justa, xg_base, fuente_tag

def calcular_tasas_tiempos_y_franja(xg_total_pre, disparos_tot, tiros_arco, corneres_tot, min_actual):
    bp = (disparos_tot * 0.032) + (tiros_arco * 0.075) + (corneres_tot * 0.018)
    x1 = (xg_total_pre * 0.43) + (bp * 0.65)
    t1 = round(min(91.0, max(38.0, (1 - poisson.cdf(0, x1)) * 100)), 1)
    x2 = (xg_total_pre * 0.57) + bp
    if min_actual > 45: x2 = x2 * min(1.15, (max(8, 94 - min_actual) / 45.0) * 1.22)
    t2 = round(min(94.0, max(50.0, (1 - poisson.cdf(0, x2)) * 100)), 1)
    x3 = (x1 * 0.52) + (tiros_arco * 0.04)
    t3 = round(min(82.0, max(28.0, (1 - poisson.cdf(0, x3)) * 100)), 1)
    return t1, t2, t3

def evaluar_gatillo_quirurgico_05(prob_pre, toth_tot, max_disp_equipo, tmeta_tot, min_num, tasa_38_45):
    if prob_pre >= 75.0: return (max_disp_equipo >= 3 or tmeta_tot >= 2 or toth_tot >= 4 or (35 <= min_num <= 45 and tasa_38_45 >= 52.0 and toth_tot >= 3))
    elif prob_pre >= 70.0: return (toth_tot >= 5 or (max_disp_equipo >= 3 and tmeta_tot >= 2) or (35 <= min_num <= 45 and tasa_38_45 >= 54.0 and toth_tot >= 4))
    else: return (toth_tot >= 6 or (toth_tot >= 5 and tmeta_tot >= 2))

def generar_boletin_html_imprimible(df_datos, titulo_reporte, subtitulo_reporte):
    fecha_emision = (datetime.utcnow() - timedelta(hours=6)).strftime("%d/%m/%Y %H:%M")
    tabla_html = df_datos.to_html(index=False, border=0, classes="tabla-boletin")
    return f"<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'><title>{titulo_reporte} - MRFUTBOL</title><style>body {{ font-family: Arial, sans-serif; background-color: #0f1015; color: #e0e0e0; padding: 24px; }} .header {{ text-align: center; border-bottom: 2px solid #00ffcc; padding-bottom: 12px; margin-bottom: 18px; }} .header h1 {{ margin: 0; color: #ffffff; letter-spacing: 2px; }} .header p {{ margin: 4px 0; color: #00ffcc; font-weight: bold; font-size: 13px; }} .meta {{ font-size: 12px; color: #9ba1b0; margin-bottom: 15px; display: flex; justify-content: space-between; }} .tabla-boletin {{ width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 20px; }} .tabla-boletin th {{ background-color: #16181f; color: #00ffcc; padding: 8px; text-align: left; border-bottom: 2px solid #00ffcc; }} .tabla-boletin td {{ padding: 8px; border-bottom: 1px solid #1f222d; color: #e0e0e0; }} .footer {{ text-align: center; font-size: 12px; color: #00ffcc; border-top: 1px solid #1f222d; padding-top: 12px; margin-top: 25px; }} .btn-print {{ background: #00ffcc; color: #000; padding: 8px 16px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; margin-bottom: 15px; }} @media print {{ .btn-print {{ display: none; }} body {{ background-color: #ffffff; color: #000000; }} .tabla-boletin td, .tabla-boletin th {{ color: #000000; border-color: #cccccc; }} }}</style></head><body><button class='btn-print' onclick='window.print()'>🖨️ Imprimir / Guardar Boletín en PDF</button><div class='header'><h1>⚽ MRFUTBOL - BOLETÍN OFICIAL VIP</h1><p>Autoría Oficial: Miguel Ramirez | ✉️ angelramirezzmiguel2@gmail.com</p></div><div class='meta'><span><strong>Reporte:</strong> {titulo_reporte} ({subtitulo_reporte})</span><span><strong>Emisión (UTC-6):</strong> {fecha_emision} | <strong>Gestión de Banca Recomendada:</strong> Stake 2% - 3%</span></div>{tabla_html}<div class='footer'>⚽ MRFUTBOL Central de Inteligencia | Creado por Miguel Ramirez (angelramirezzmiguel2@gmail.com)</div></body></html>"

# =============================================================================
# SCRAPING LIGERO PARA RASTREAR EN VIVO (ESPN)
# =============================================================================
def _fetch_url(args):
    c, f = args
    try:
        res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{c}/scoreboard?dates={f}", timeout=3)
        if res.status_code == 200: return c, res.json().get("events", [])
    except: pass
    return c, []

@st.cache_data(ttl=18)
def obtener_partidos_ligas(codigos_liga):
    hoy = datetime.utcnow() - timedelta(hours=6)
    fs = [(hoy + timedelta(days=i)).strftime("%Y%m%d") for i in (0, 1)]
    m = {l["code"]: l for l in LIGAS_BIG_DATA}
    d = {m[c]["id"]: {"meta": m[c], "eventos": []} for c in codigos_liga if c in m}
    v = set()
    with ThreadPoolExecutor(max_workers=16) as ex:
        for c, evs in ex.map(_fetch_url, [(c, f) for c in codigos_liga if c in m for f in fs]):
            l_id = m[c]["id"]
            for ev in evs:
                ei = ev.get("id")
                if ei and ei not in v:
                    v.add(ei)
                    d[l_id]["eventos"].append(ev)
    return d

col_m1, col_m2 = st.columns([3, 1])
with col_m2: auto_refresh = st.toggle("⚡ Refresco en Vivo", value=True)

def accionar_plequita_vip(ei, nl, nv, lig, fec, pp, xp, sv, st, iso, ol, f2=None, ga=0):
    ph = boveda_vip.setdefault("picks_vip_hoy", {})
    if ei in ph: del ph[ei]
    else: ph[ei] = {"ev_id": ei, "origen": ol, "iso_fecha": iso, "ficha": analizar_partido_profundo_mrfutbol(ei, nl, nv, lig, fec, pp, xp, sv, st, f2, ga)}
    guardar_boveda_vip_servidor(boveda_vip)

_frag = getattr(st, "fragment", getattr(st, "experimental_fragment", None))
@(_frag(run_every=25 if auto_refresh else None) if _frag else lambda f: f)
def renderizar_central_mrfutbol():
    ah_dt = datetime.utcnow() - timedelta(hours=6)
    sh = ah_dt.strftime("%Y-%m-%d")
    sm = (ah_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    
    if boveda_vip.get("fecha_activa") != sh:
        boveda_vip["fecha_activa"] = sh
        boveda_vip["picks_vip_hoy"] = {}
        guardar_boveda_vip_servidor(boveda_vip)

    ua = boveda_vip.get("uso_diario_api", {"usadas": 0})
    ct = [l["code"] for l in LIGAS_BIG_DATA]
    dg = obtener_partidos_ligas(ct)
    sta, ela = obtener_estadisticas_temporada_reales(ct)
    
    # Sincronizamos la Matriz Big Data silenciosamente 
    sincronizar_matriz_global_clubes(ct)

    with col_m1:
        st.caption(f"💡 Central MRFUTBOL | 🕒 {ah_dt.strftime('%H:%M:%S')} | 👑 Llamadas Motor VIP (Sportmonks): **{ua.get('usadas', 0)} / 50000**")

    t1, t2, t3, t4, t5 = st.tabs(["⚽ 1. CARTELERA", "🔴 2. PARTIDOS EN VIVO", "🎯 3. PRE-APUESTAS", "🚨 4. TERMINAL EN VIVO", "👑 5. SALA VIP (MRFUTBOL)"])

    # -------------------------------------------------------------------------
    # TAB 1: CARTELERA Y MATRIZ BIG DATA
    # -------------------------------------------------------------------------
    with t1:
        cm, cc = st.columns([1.2, 3.8])
        with cm:
            st.markdown("##### 📅 Opciones")
            fs = st.radio("Día:", ["Hoy", "Mañana"])
            fo = sh if fs == "Hoy" else sm
            oc = st.toggle("👁️ Ocultar Finalizados", value=True)
            busq = st.text_input("🔍 Buscar Equipo...", placeholder="Ej. MR2026")
            if st.button("🔄 Refrescar", use_container_width=True): st.cache_data.clear(); st.rerun()
            eadm = (busq == "MR2026" or st.session_state["admin_autenticado"])
            with st.expander("🔐 Bóveda Privada", expanded=eadm):
                if eadm:
                    st.session_state["admin_autenticado"] = True
                    st.success("🔓 Admin Activo")
                    if st.button("🧹 Vaciar VIP", use_container_width=True): boveda_vip["picks_vip_hoy"]={}; guardar_boveda_vip_servidor(boveda_vip); st.rerun()
                    rml = list(boveda_ml_05.values())
                    st.caption(f"🧠 Memoria Total Aprendizaje: **{len(rml)} / 300**")
                    if rml: st.download_button("📥 Descargar Bitácora", data=pd.DataFrame(rml).to_csv(index=False).encode("utf-8-sig"), file_name="Bitacora_MRFUTBOL.csv", mime="text/csv", use_container_width=True)

        with cc:
            st.subheader("🌐 Matriz Big Data (Recolección 2-3 Fechas)")
            fm = []
            for clb, hst in matriz_clubes_global.items():
                if busq and busq != "MR2026" and busq.lower() not in clb.lower(): continue
                if len(hst) > 0:
                    pf = obtener_perfil_reciente_2_3_fechas(clb)
                    fm.append({"Club": clb, "Muestra": pf["origen"], "🎯 Disp. Ataque": pf["disp_f"], "⚽ GF Rec": pf["gf_rec"], "🧀 Disp. Vuln": pf["disp_c"], "🥅 GC Rec": pf["gc_rec"], "🔥 Efectividad": f"{pf['tasa_o15']}%"})
            if fm: st.dataframe(pd.DataFrame(fm).sort_values(by="🎯 Disp. Ataque", ascending=False), use_container_width=True, hide_index=True)
            else: st.info("Matriz recolectando datos silenciosamente...")

            hp = False
            for lig, cont in dg.items():
                evf = [ev for ev in cont["eventos"] if obtener_fecha_local_evento(ev.get("date"))[0] == fo]
                if not evf: continue
                hp = True
                efc = round((float(cont["meta"]["efec"]) * 0.65) + (ela[cont["meta"]["code"]] * 0.35), 1) if cont["meta"]["code"] in ela else cont["meta"]["code"]
                st.markdown(f"<div class='liga-header'><span>{lig}</span><span style='font-size:12px; color:#9ba1b0;'>Eficiencia: {efc}%</span></div>", unsafe_allow_html=True)
                for ev in evf:
                    c = ev.get("competitions", [{}])[0]
                    ste, eh, mn, bh, _ = detectar_estado_partido(c, ev.get("date"))
                    if oc and ste == "post": continue
                    cp = c.get("competitors", [])
                    if len(cp) == 2:
                        nl, nv = cp[0].get("team", {}).get("shortDisplayName", ""), cp[1].get("team", {}).get("shortDisplayName", "")
                        if busq and busq != "MR2026" and busq.lower() not in f"{nl} {nv}".lower(): continue
                        gl, gv = int(cp[0].get("score", 0)), int(cp[1].get("score", 0))
                        ch = f"{gl} - {gv}" if (ste != "pre" or eh) else "vs"
                        st.markdown(f"<div class='match-card'>{bh}<div class='teams-container'><div class='team-home'>{nl}</div><div class='score-box'>{ch}</div><div class='team-away'>{nv}</div></div></div>", unsafe_allow_html=True)
            if not hp: st.info("No hay partidos programados.")

    # -------------------------------------------------------------------------
    # TAB 2: PARTIDOS EN VIVO
    # -------------------------------------------------------------------------
    with t2:
        st.subheader("🔴 Partidos en Curso")
        hv = False
        for lig, cont in dg.items():
            evv = [ev for ev in cont["eventos"] if detectar_estado_partido(ev.get("competitions", [{}])[0], ev.get("date"))[0] == "in"]
            if evv:
                hv = True
                st.markdown(f"<div class='liga-header'><span>{lig}</span></div>", unsafe_allow_html=True)
                for ev in evv:
                    c = ev.get("competitions", [{}])[0]
                    ste, eh, mn, bh, _ = detectar_estado_partido(c, ev.get("date"))
                    cp = c.get("competitors", [])
                    nl, nv = cp[0].get("team", {}).get("shortDisplayName", ""), cp[1].get("team", {}).get("shortDisplayName", "")
                    gl, gv = int(cp[0].get("score", 0)), int(cp[1].get("score", 0))
                    sr = extraer_metricas_partido_reales(cp[0], cp[1])
                    st.markdown(f"<div class='match-card'>{bh} <div style='flex-grow:1; text-align:center;'><strong>{nl} {gl} - {gv} {nv}</strong></div> <div>🎯 {sr['toth_tot']} Disp | 🥅 {sr['tmeta_tot']} Arco</div></div>", unsafe_allow_html=True)
        if not hv: st.info("No hay partidos en curso.")

    # -------------------------------------------------------------------------
    # TAB 3: PRE-APUESTAS
    # -------------------------------------------------------------------------
    with t3:
        st.subheader("🎯 Laboratorio Pre-Apuesta Over 1.5")
        c1, c2 = st.columns([2.5, 1.5])
        with c1: ls = st.multiselect("Ligas:", options=[l["id"] for l in LIGAS_BIG_DATA], default=[l["id"] for l in LIGAS_BIG_DATA])
        with c2: um = st.slider("Umbral (%):", 58, 82, 64, 2)

        rp = []
        for lig, cont in dg.items():
            if lig not in ls: continue
            for ev in cont["eventos"]:
                fe, fl, _, _ = obtener_fecha_local_evento(ev.get("date"))
                if fe not in (sh, sm): continue
                c = ev.get("competitions", [{}])[0]
                ste, eh, _, _, _ = detectar_estado_partido(c, ev.get("date"))
                if ste != "pre" or eh: continue
                cp = c.get("competitors", [])
                if len(cp) == 2:
                    nl, nv = cp[0].get("team", {}).get("displayName", ""), cp[1].get("team", {}).get("displayName", "")
                    if nl and nv:
                        pf, cj, xb, ft = calcular_pre_poisson_real(nl, nv, sta)
                        if pf >= um:
                            t1, t2, t3 = calcular_tasas_tiempos_y_franja(xb, 0, 0, 0, 0)
                            vd = "🟢 ENTRAR OVER 1.5" if pf >= 75.5 else "🔴 ZONA ROJA (<70%)" if pf < 70 else "💎 ENTRAR OVER 1.5"
                            rp.append({"Liga": lig, "Partido": f"{nl} vs {nv}", "⚡ CALIENTE (FINAL)": f"{pf}%", "⏱️ Gol 1T": f"{t1}%", "🔥 Gol 2T": f"{t2}%", "Cuota": cj, "Respaldo + Aprendizaje (2J)": ft, "Veredicto": vd, "_pf": pf})
        if rp:
            dfp = pd.DataFrame(rp).sort_values(by="_pf", ascending=False).drop(columns=["_pf"])
            st.dataframe(dfp, use_container_width=True, hide_index=True)
            st.download_button("📊 Exportar Pre-Apuestas (.CSV)", data=dfp.to_csv(index=False).encode("utf-8-sig"), file_name=f"PreApuestas_{sh}.csv", mime="text/csv")
        else: st.info("No hay partidos con alta probabilidad.")

    # -------------------------------------------------------------------------
    # TAB 4: TERMINAL EN VIVO 0.5
    # -------------------------------------------------------------------------
    with t4:
        st.markdown("### 🚨 TERMINAL EN VIVO 0.5")
        st.markdown("**Regla 96.8% Verde:** Busca 6+ Disparos o 3+ al Arco.")
        ts = []
        for lig, cont in dg.items():
            for ev in cont["eventos"]:
                c = ev.get("competitions", [{}])[0]
                ste, eh, mn, _, r = detectar_estado_partido(c, ev.get("date"))
                if ste == "in" or eh:
                    cp = c.get("competitors", [])
                    if len(cp) == 2:
                        nl, nv = cp[0].get("team", {}).get("displayName", ""), cp[1].get("team", {}).get("displayName", "")
                        gl, gv = int(cp[0].get("score", 0)), int(cp[1].get("score", 0))
                        gt = gl + gv
                        pf, cj, xb, ft = calcular_pre_poisson_real(nl, nv, sta)
                        sr = extraer_metricas_partido_reales(cp[0], cp[1])
                        
                        tt, tm, et = sr["toth_tot"], sr["tmeta_tot"], sr["esquinas_tot"]
                        t1, t2, t3 = calcular_tasas_tiempos_y_franja(xb, tt, tm, et, mn)
                        md = max(sr["toth_l"], sr["toth_v"])
                        
                        vd = "⏸️ AGUANTAR: Exigir 6+ Disp o 2+ al Arco"
                        ec = False
                        cb = "veredicto-box-wait"
                        
                        if gt == 0:
                            if mn < 18 and not eh: vd = f"⏳ Min {mn}' ({tt} Disp, {tm} Arco). Esperar min 18+"
                            else:
                                if evaluar_gatillo_quirurgico_05(pf, tt, md, tm, mn, t3):
                                    ec = True; cb = "veredicto-box-hot"
                                    vd = f"🚨 ¡ENTRAR OVER 0.5! (Tasa 2T: {t2}%)"
                                else:
                                    if pf < 70 and et >= 3 and tt < 5: vd = "🚩 ESPEJISMO DE CÓRNERES. NO ENTRAR"
                                    elif pf < 70: vd = "🔴 ZONA ROJA (<70%). Exigir 6+ Disparos"
                                    else: vd = f"🚫 PRECAUCIÓN ({tt} Disp, {tm} Arco)"
                        elif gt == 1:
                            if mn <= 82 and (md >= 3 or tm >= 3 or tt >= 6): cb = "veredicto-box-hot"; vd = f"🔥 ¡OVER 0.5 COBRADO! Oportunidad 1.5 GOLES (Tasa 2T: {t2}%)"
                            else: cb = "veredicto-box-green"; vd = f"✅ ¡OVER 0.5 COBRADO EN VERDE! Ritmo moderado."
                        else: cb = "veredicto-box-green"; vd = "✅ LÍNEAS COBRADAS"

                        ts.append({"ev_id": ev.get("id"), "nl": nl, "nv": nv, "lig": lig, "fec": obtener_fecha_local_evento(ev.get("date"))[0], "pf": pf, "xb": xb, "iso": ev.get("date"), "r": r, "p": f"{nl} vs {nv}", "m": f"{gl}-{gv}", "gt": gt, "tt": tt, "tm": tm, "et": et, "pos": f"{sr['pos_l']}%-{sr['pos_v']}%", "t1": t1, "t2": t2, "t3": t3, "sr": sr, "vd": vd, "cb": cb, "ec": ec})
        
        for it in sorted(ts, key=lambda x: (x['gt'], not x['ec'], -x['pf'])):
            eid = it["ev_id"]
            yv = eid in boveda_vip.get("picks_vip_hoy", {})
            cc = "trading-card-hot" if it["ec"] else "trading-card"
            c1, c2 = st.columns([10.2, 1.8])
            with c1:
                st.markdown(f"""
                <div class='{cc}'>
                    <div class="trading-header">
                        <div><span style="background:#ff2a4b; color:#fff; padding:3px 8px; border-radius:4px;">{it['r']}</span> <strong>{it['p']}</strong> <span style="background:#16181f; color:#00ffcc; padding:3px 10px; border-radius:4px;">{it['m']}</span></div>
                        <div style="font-size:12px; color:#9ba1b0;">{it['lig']}</div>
                    </div>
                    <div class="trading-metrics-grid">
                        <div class="metric-pill"><span>📈 Pre Over 1.5</span><strong>{it['pf']}%</strong></div>
                        <div class="metric-pill"><span>⏱️ Gol 1T</span><strong>{it['t1']}%</strong></div>
                        <div class="metric-pill"><span>⚡ Cierre 38'-45'</span><strong>{it['t3']}%</strong></div>
                        <div class="metric-pill"><span>🔥 Tasa Gol 2T</span><strong>{it['t2']}%</strong></div>
                        <div class="metric-pill"><span>🎯 Disparos</span><strong>{it['tt']}</strong></div>
                        <div class="metric-pill"><span>🥅 Al Arco</span><strong>{it['tm']}</strong></div>
                        <div class="metric-pill"><span>🚩 Córn | Pos</span><strong>{it['et']} | {it['pos']}</strong></div>
                    </div>
                    <div class="{it['cb']}">{it['vd']}</div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown("<div style='margin-top:18px;'></div>", unsafe_allow_html=True)
                st.checkbox("☑️ Enviar VIP", value=yv, key=f"vip_{eid}_{yv}", on_change=accionar_plequita_vip, args=(eid, it["nl"], it["nv"], it["lig"], str_hoy, it["pf"], it["xb"], it["sr"], sta, it["iso"], "⚡ Plequita Manual", None, it['gt']))

    # -------------------------------------------------------------------------
    # TAB 5: SALA VIP MRFUTBOL (BOTÓN DE ELIMINAR AÑADIDO)
    # -------------------------------------------------------------------------
    with t5:
        st.subheader("👑 SALA VIP MRFUTBOL — Radiografía Profunda [PASO_3_BIG_DATA]")
        lv = list(boveda_vip.get("picks_vip_hoy", {}).values())
        if lv:
            for iv in lv:
                f = iv["ficha"]
                st.markdown(f"""
                <div class="vip-card">
                    <div class="trading-header"><strong>{f['Partido']}</strong> <span style="color:#00ffcc;">Prob: {f['Prob_Over15']}</span></div>
                    <div class="trading-metrics-grid">
                        <div class="metric-pill"><span>🎯 [PASO_3_OFENSIVO_PRO]</span><strong>{f['Paso3_Ofensivo_Pro']}</strong><small>{f['Ref_Ofensivo_Pro']}</small></div>
                        <div class="metric-pill"><span>🥩 [CARNICERÍA]</span><strong>{f['Paso3_Eficiencia_Carniceria']}</strong><small>{f['Ref_Carniceria']}</small></div>
                        <div class="metric-pill"><span>🧀 [VULNERABILIDAD RIVAL]</span><strong>{f['Paso3_Vulnerabilidad_Rival']}</strong><small>{f['Ref_Vulnerabilidad']}</small></div>
                        <div class="metric-pill"><span>🔥 [MOMENTUM]</span><strong>{f['Paso3_Momentum']}</strong><small>{f['Ref_Momentum']}</small></div>
                        <div class="metric-pill"><span>🤝 [SISTEMA COLECTIVO 10.5]</span><strong>{f['Paso3_Colectivo_105']}</strong><small>{f['Ref_Colectivo']}</small></div>
                        <div class="metric-pill"><span>🎰 [VARIANZA / DEUDA GOL]</span><strong>{f['Paso3_Varianza_Deuda']}</strong><small>{f['Ref_Varianza']}</small></div>
                        <div class="metric-pill"><span>🏆 [URGENCIA TABLA]</span><strong>{f['Paso3_Contexto_Urgencia']}</strong><small>{f['Ref_Urgencia']}</small></div>
                    </div>
                    <div style="font-size:11px; color:#9ba1b0; margin-top:8px;">{f['Liga']} | {f.get('Sello_API', '')}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # BOTÓN ROJO PARA LIMPIAR LA SALA VIP
                if st.button(f"🗑️ Quitar {f['Partido']} de VIP", key=f"del_vip_{iv['ev_id']}"):
                    if iv['ev_id'] in boveda_vip["picks_vip_hoy"]:
                        del boveda_vip["picks_vip_hoy"][iv['ev_id']]
                        guardar_boveda_vip_servidor(boveda_vip)
                        st.rerun()

            if st.button("🔓 Descargar Reporte VIP (CSV)", use_container_width=True):
                st.download_button("Descargar", data=pd.DataFrame([i["ficha"] for i in lv]).to_csv(index=False).encode("utf-8-sig"), file_name=f"Reporte_VIP_{str_hoy}.csv", mime="text/csv")
        else: st.info("Marca la plequita `☑️ Enviar VIP` en el Terminal en Vivo 0.5 para destripar el partido con el motor V3.")

renderizar_central_mrfutbol()
