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

st.set_page_config(page_title="MRFUTBOL - Miguel Ramirez", page_icon="⚽", layout="wide")

# =============================================================================
# CONEXIÓN INTERNA OCULTA (100% MARCA MRFUTBOL)
# =============================================================================
_MOTOR_PRO_HOST = "v3.football.api-sports.io"
try:
    _MOTOR_PRO_KEY = st.secrets.get("API_FOOTBALL_KEY", "b9598555b70de4df59b0d0d205ce5a13")
except Exception:
    _MOTOR_PRO_KEY = "b9598555b70de4df59b0d0d205ce5a13"

_HEADERS_MOTOR_PRO = {
    "x-rapidapi-host": _MOTOR_PRO_HOST,
    "x-rapidapi-key": _MOTOR_PRO_KEY,
    "x-apisports-key": _MOTOR_PRO_KEY
}

PASO_3_PICOS_REF = {
    "MIN_BIG_CHANCES": 3.2, "MIN_TIROS_A_PUERTA": 5.5, "MIN_xG_COMBINADO": 2.4,
    "FACTOR_LOCALIA_PESO": 1.2, "MIN_QUALITY_PER_SHOT": 0.12, "MIN_xGA_CONCEDIDO_RIVAL": 1.3,
    "MAX_PORTERIA_CERO_RIVAL_PCT": 25.0, "BONO_MOMENTUM_PCT": 5.0, "MIN_UNIQUE_SCORERS_5": 2,
    "MAX_PLAYER_CONTRIB_PCT": 45.0, "MIN_DIFF_ASSISTERS_5": 4, "PLAYMAKER_DEP_LIMIT": 0.40
}

if "seguidos_usuario" not in st.session_state:
    st.session_state["seguidos_usuario"] = []
if "memoria_eventos_usuario" not in st.session_state:
    st.session_state["memoria_eventos_usuario"] = {}
if "historial_notificaciones_usuario" not in st.session_state:
    st.session_state["historial_notificaciones_usuario"] = []
if "admin_autenticado" not in st.session_state:
    st.session_state["admin_autenticado"] = False
if "aviso_vip_bloqueado" not in st.session_state:
    st.session_state["aviso_vip_bloqueado"] = ""

# =============================================================================
# BÓVEDAS PERSISTENTES (84 REGISTROS REALES + MATRIZ DE CLUBES INBORRABLE)
# =============================================================================
ARCHIVO_BITACORA_OCULTA = ".boveda_ml_over05_mrfutbol.json"
ARCHIVO_BOVEDA_VIP_API = ".boveda_vip_apifootball_mrfutbol.json"
ARCHIVO_MATRIZ_CLUBES = ".matriz_clubes_mrfutbol.json"

def _crear_registro_semilla(
    clave_id, semana, fecha_hora, liga, partido, min_alerta,
    disp_l, disp_v, arco_l, arco_v, corn_l, corn_v, pos_l, pos_v,
    prob_pre, tasa_1t, tasa_2t, tasa_38_45, ganada=True, min_gol=34, marcador="2 - 1"
):
    disp_tot, arco_tot, corn_tot = disp_l + disp_v, arco_l + arco_v, corn_l + corn_v
    eq_dom = partido.split(" vs ")[0] if disp_l >= disp_v else partido.split(" vs ")[-1]
    max_d = max(disp_l, disp_v)
    return clave_id, {
        "Semana_Jornada": semana, "Fecha_Hora": fecha_hora, "Liga": liga, "Partido": partido,
        "Min_Alerta": min_alerta,
        "Motivo_Decision": f"{eq_dom} {max_d} Disp ({disp_tot} Tot, {arco_tot} Arco, {corn_tot} Córn | Pre {prob_pre}%)",
        "Disparos_Al_Activar": f"{disp_l}-{disp_v} (Tot: {disp_tot})",
        "Arco_Al_Activar": f"{arco_l}-{arco_v} (Tot: {arco_tot})",
        "Corneres_Al_Activar": f"{corn_l}-{corn_v} (Tot: {corn_tot})",
        "Posesion_Al_Activar": f"{pos_l}% - {pos_v}%",
        "Prob_Pre_Over15": f"{prob_pre}%", "Tasa_Gol_1T": f"{tasa_1t}%",
        "Tasa_Gol_2T": f"{tasa_2t}%", "Tasa_Franja_38_45": f"{tasa_38_45}%",
        "Estado_Apuesta_05": "✅ GANADA (VERDE)" if ganada else "❌ FALLO (0-0 Final)",
        "Minuto_Gol": f"{min_gol}'" if ganada else "Sin Gol (90')",
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
        k, val = _crear_registro_semilla(
            f"seed_hist_v_{indice:02d}", "2026-Semana-42", "2026-10-18 14:00",
            "🌍 Historial Auditado MRFUTBOL", f"Histórico Verde #{indice}A vs Histórico Verde #{indice}B",
            24, 4, 3, 2, 1, 2, 1, 52, 48, 78.5, 72.0, 81.5, 48.5, True, 35, "2 - 0"
        )
        semilla[k] = val

    for r_idx in range(1, 8):
        k, val = _crear_registro_semilla(
            f"seed_hist_r_{r_idx:02d}", "2026-Semana-42", "2026-10-17 14:00",
            "🌍 Historial Auditado MRFUTBOL", f"Histórico Rojo #{r_idx}A vs Histórico Rojo #{r_idx}B",
            27, 2, 1, 0, 0, 1, 1, 50, 50, 70.5, 65.0, 74.0, 42.0, False, 90, "0 - 0"
        )
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
    return f"{ahora_hn.strftime('%Y')}-Semana-{ahora_hn.strftime('%V')}", f"Bitacora_VIP_{ahora_hn.strftime('%Y')}_Semana_{ahora_hn.strftime('%V')}.csv"

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

    for arc in glob.glob("Bitacora_*.csv"):
        try:
            df_arc = pd.read_csv(arc)
            for idx, row in df_arc.iterrows():
                clave_sintetica = f"hist_{os.path.basename(arc)}_{idx}_{row.get('Partido', '')}"
                if clave_sintetica not in boveda_cargada and not any(
                    r.get("Partido") == row.get("Partido") and str(r.get("Fecha_Hora", ""))[:10] == str(row.get("Fecha_Hora", ""))[:10]
                    for r in boveda_cargada.values()
                ):
                    boveda_cargada[clave_sintetica] = row.to_dict()
        except Exception:
            pass

    try:
        with open(ARCHIVO_BITACORA_OCULTA, "w", encoding="utf-8") as f:
            json.dump(boveda_cargada, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return boveda_cargada

def guardar_boveda_ml_servidor(boveda):
    try:
        with open(ARCHIVO_BITACORA_OCULTA, "w", encoding="utf-8") as f:
            json.dump(boveda, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    try:
        etiqueta_sem, nombre_csv_sem = obtener_etiqueta_semana_actual()
        registros_semana = [v for v in boveda.values() if v.get("Semana_Jornada", etiqueta_sem) == etiqueta_sem]
        if registros_semana:
            pd.DataFrame(registros_semana).to_csv(nombre_csv_sem, index=False, encoding="utf-8-sig")
    except Exception:
        pass

@st.cache_resource
def obtener_matriz_clubes_servidor():
    if os.path.exists(ARCHIVO_MATRIZ_CLUBES):
        try:
            with open(ARCHIVO_MATRIZ_CLUBES, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}

def guardar_matriz_clubes_servidor(matriz):
    try:
        with open(ARCHIVO_MATRIZ_CLUBES, "w", encoding="utf-8") as f:
            json.dump(matriz, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def limpiar_textos_externos_boveda(boveda_vip):
    picks = boveda_vip.get("picks_vip_hoy", {})
    for k in [k for k, v in picks.items() if "Filtro Automático" in str(v.get("origen", "")) or "Filtro Élite" in str(v.get("origen", ""))]:
        del picks[k]
    for coleccion in [ [v.get("ficha", {}) for v in picks.values()], boveda_vip.get("cache_api_analisis", {}).values() ]:
        for ficha in coleccion:
            if "Sello_API" in ficha:
                ficha["Sello_API"] = str(ficha["Sello_API"]).replace("v3.football.api-sports.io", "Motor MRFUTBOL Pro").replace("Fixture", "ID")
            if "Paso3_Contexto_Urgencia" in ficha:
                ficha["Paso3_Contexto_Urgencia"] = str(ficha["Paso3_Contexto_Urgencia"]).replace("Pico API:", "Pico MRFUTBOL:")

@st.cache_resource
def obtener_boveda_vip_servidor():
    estructura_base = {
        "fecha_activa": "", "picks_vip_hoy": {}, "cache_api_analisis": {},
        "mapa_fixtures_dia": {}, "historial_reportes_7d": [],
        "uso_diario_api": {"fecha": "", "usadas": 0, "limite": 100}
    }
    if os.path.exists(ARCHIVO_BOVEDA_VIP_API):
        try:
            with open(ARCHIVO_BOVEDA_VIP_API, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k in estructura_base:
                    if k in data:
                        estructura_base[k] = data[k]
        except Exception:
            pass
    limpiar_textos_externos_boveda(estructura_base)
    return estructura_base

def guardar_boveda_vip_servidor(boveda_vip):
    limpiar_textos_externos_boveda(boveda_vip)
    try:
        with open(ARCHIVO_BOVEDA_VIP_API, "w", encoding="utf-8") as f:
            json.dump(boveda_vip, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

boveda_ml_05 = obtener_boveda_ml_servidor()
boveda_vip = obtener_boveda_vip_servidor()
matriz_clubes_global = obtener_matriz_clubes_servidor()
limpiar_textos_externos_boveda(boveda_vip)

# ESTILOS CSS OFICIALES MRFUTBOL
st.markdown("""
<style>
.titulo-mrfutbol { text-align:center; font-size:32px; font-weight:900; color:#ffffff; letter-spacing:2px; margin-bottom:0px; }
.subtitulo-autor { text-align:center; font-size:12px; font-weight:600; color:#00ffcc; margin-top:1px; margin-bottom:10px; letter-spacing:1px; }
.liga-header { background-color:#16181f; color:#00ffcc; padding:6px 12px; border-radius:6px; font-weight:700; font-size:14px; border-left:3px solid #00ffcc; margin-top:10px; margin-bottom:4px; display:flex; justify-content:space-between; }
.trading-card { background-color:#0f1015; border:1px solid #262b3d; border-left:4px solid #00ffcc; border-radius:8px; padding:12px 15px; margin-bottom:10px; color:#e0e0e0; }
.trading-card-hot { background-color:#12161f; border:1px solid #00ffcc; border-left:5px solid #00ffcc; border-radius:8px; padding:12px 15px; margin-bottom:10px; color:#ffffff; box-shadow:0 2px 10px rgba(0,255,204,0.12); }
.vip-card { background:linear-gradient(135deg,#10141d 0%,#161b26 100%); border:1px solid #ffd700; border-left:5px solid #ffd700; border-radius:8px; padding:14px 16px; margin-bottom:12px; color:#ffffff; }
.trading-header { display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1f222d; padding-bottom:6px; margin-bottom:8px; flex-wrap:wrap; gap:6px; }
.trading-metrics-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); gap:8px; margin-bottom:8px; }
.metric-pill { background-color:#16181f; border:1px solid #1f222d; border-radius:5px; padding:6px 8px; font-size:12px; text-align:center; }
.metric-pill span { display:block; font-size:10px; color:#9ba1b0; text-transform:uppercase; margin-bottom:2px; }
.metric-pill strong { font-size:12.5px; color:#00ffcc; }
.metric-pill small { display:block; font-size:10px; color:#ffd700; margin-top:2px; }
.veredicto-box-hot { background:linear-gradient(90deg,rgba(0,255,204,0.16) 0%,rgba(22,24,31,0.95) 100%); border:1px solid #00ffcc; color:#ffffff; padding:8px 12px; border-radius:6px; font-size:13px; font-weight:600; line-height:1.4; }
.veredicto-box-wait { background-color:#16181f; border:1px solid #ff9800; color:#ffd180; padding:8px 12px; border-radius:6px; font-size:13px; line-height:1.4; }
.veredicto-box-green { background-color:rgba(0,200,83,0.15); border:1px solid #00c853; color:#69f0ae; padding:8px 12px; border-radius:6px; font-size:13px; font-weight:600; }
.audit-box-right { background-color:#12151e; border:1px solid #262b3d; border-top:3px solid #ffd700; border-radius:8px; padding:12px; margin-bottom:10px; }
.footer-fijo { position:fixed; bottom:0; left:0; width:100%; background-color:#0f1015; color:#9ba1b0; text-align:center; padding:6px 0; font-size:11px; border-top:1px solid #1f222d; z-index:9999; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='titulo-mrfutbol'>⚽ MRFUTBOL</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitulo-autor'>Miguel Ramirez &nbsp;|&nbsp; ✉️ angelramirezzmiguel2@gmail.com</div>", unsafe_allow_html=True)
st.markdown("<div class='footer-fijo'>Miguel Ramirez &nbsp;|&nbsp; ✉️ <a href='mailto:angelramirezzmiguel2@gmail.com' style='color:#00ffcc; text-decoration:none;'>angelramirezzmiguel2@gmail.com</a></div>", unsafe_allow_html=True)

# =============================================================================
# LAS 20 LIGAS OFICIALES Y PERFILES BASE
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
    "Porto": {"sot": 6.9, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top SoT"},
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
    txt = unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("utf-8").lower()
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
        dt_utc = datetime.strptime(iso_fecha.strip()[:16], "%Y-%m-%dT%H:%M")
        dt_local = dt_utc - timedelta(hours=6)
        return dt_local.strftime("%Y-%m-%d"), dt_local.strftime("%d/%m %H:%M"), dt_local.strftime("%H:%M"), dt_local
    except Exception:
        return "1970-01-01", "Programado", "--:--", datetime(1970, 1, 1)

def auditar_equipo_bd(nombre_equipo):
    sot_base, xg_shot, etiqueta, es_colador, es_cerrojo = 4.9, 0.115, "Estándar", False, False
    for k, val in TOP_DISPARADORES.items():
        if k.lower() in nombre_equipo.lower():
            sot_base, xg_shot, etiqueta = val["sot"], val["xg_shot"], val["tag"]
            break
    for col in DEFENSAS_COLADOR:
        if col.lower() in nombre_equipo.lower():
            es_colador = True
            etiqueta = "🧀 Defensa Colador" if etiqueta == "Estándar" else etiqueta + " / 🧀 Colador"
            break
    for cer in BLOQUES_CERROJO:
        if cer.lower() in nombre_equipo.lower():
            es_cerrojo, etiqueta = True, "🧱 Bloque Bajo"
            break
    return sot_base, xg_shot, etiqueta, es_colador, es_cerrojo

def extraer_stat(team_dict, stat_names):
    for st_item in team_dict.get("statistics", []):
        if st_item.get("name") in stat_names:
            try:
                val = st_item.get("displayValue", "0").replace("%", "").strip()
                return float(val) if "." in val else int(val)
            except Exception:
                return 0
    return 0

def extraer_metricas_partido_reales(loc, vis):
    toth_l, toth_v = int(extraer_stat(loc, ["totalShots", "shots"])), int(extraer_stat(vis, ["totalShots", "shots"]))
    tmeta_l, tmeta_v = int(extraer_stat(loc, ["shotsOnTarget", "shotsOnGoal"])), int(extraer_stat(vis, ["shotsOnTarget", "shotsOnGoal"]))
    tfuera_l, tfuera_v = max(0, toth_l - tmeta_l), max(0, toth_v - tmeta_v)
    esquinas_l, esquinas_v = int(extraer_stat(loc, ["wonCorners", "corners", "cornerKicks"])), int(extraer_stat(vis, ["wonCorners", "corners", "cornerKicks"]))
    pos_l, pos_v = extraer_stat(loc, ["possessionPct"]), extraer_stat(vis, ["possessionPct"])
    if pos_l == 0 and pos_v == 0:
        pos_l, pos_v = 50, 50
    return {
        "toth_l": toth_l, "toth_v": toth_v, "toth_tot": toth_l + toth_v,
        "tmeta_l": tmeta_l, "tmeta_v": tmeta_v, "tmeta_tot": tmeta_l + tmeta_v,
        "tfuera_l": tfuera_l, "tfuera_v": tfuera_v, "tfuera_tot": tfuera_l + tfuera_v,
        "esquinas_l": esquinas_l, "esquinas_v": esquinas_v, "esquinas_tot": esquinas_l + esquinas_v,
        "pos_l": pos_l, "pos_v": pos_v
    }

# =============================================================================
# 🧠 MOTOR DE RECOLECCIÓN MASIVA Y MATRIZ DE ATAQUE / VULNERABILIDAD (2-3J)
# =============================================================================
def _extraer_par_y_tot(texto):
    if not texto:
        return 0, 0, 0
    s = str(texto)
    m_par = re.search(r"(\d+)\s*-\s*(\d+)", s)
    m_tot = re.search(r"Tot:\s*(\d+)", s)
    l_val = int(m_par.group(1)) if m_par else 0
    v_val = int(m_par.group(2)) if m_par else 0
    t_val = int(m_tot.group(1)) if m_tot else (l_val + v_val)
    return l_val, v_val, t_val

def _extraer_tot_numero(texto):
    _, _, t_val = _extraer_par_y_tot(texto)
    return t_val

def _fetch_historial_liga_reciente(args):
    code, liga_nombre, rango_fechas = args
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={rango_fechas}&limit=100"
    try:
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            return liga_nombre, res.json().get("events", [])
    except Exception:
        pass
    return liga_nombre, []

@st.cache_data(ttl=1800)
def recolectar_ultimas_fechas_api_20_ligas(codigos_liga):
    hoy_hn = datetime.utcnow() - timedelta(hours=6)
    rango = f"{(hoy_hn - timedelta(days=14)).strftime('%Y%m%d')}-{hoy_hn.strftime('%Y%m%d')}"
    mapa_ligas = {l["code"]: l["id"] for l in LIGAS_BIG_DATA}
    tareas = [(c, mapa_ligas[c], rango) for c in codigos_liga if c in mapa_ligas]

    registros_recolectados = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        resultados = list(executor.map(_fetch_historial_liga_reciente, tareas))

    for liga_nombre, eventos in resultados:
        for ev in eventos:
            ev_id = str(ev.get("id", ""))
            comp = ev.get("competitions", [{}])[0]
            if comp.get("status", {}).get("type", {}).get("state", "pre") != "post":
                continue
            competitors = comp.get("competitors", [])
            if len(competitors) != 2:
                continue
            loc, vis = competitors[0], competitors[1]
            nom_l, nom_v = loc.get("team", {}).get("displayName", ""), vis.get("team", {}).get("displayName", "")
            if not nom_l or not nom_v:
                continue
            gol_l, gol_v = int(loc.get("score", 0) or 0), int(vis.get("score", 0) or 0)
            fecha_ev, _, _, _ = obtener_fecha_local_evento(ev.get("date", ""))
            stats = extraer_metricas_partido_reales(loc, vis)

            disp_l, disp_v = stats["toth_l"], stats["toth_v"]
            arco_l, arco_v = stats["tmeta_l"], stats["tmeta_v"]
            corn_l, corn_v = stats["esquinas_l"], stats["esquinas_v"]
            if disp_l == 0 and disp_v == 0:
                sot_l_b, _, _, col_l, _ = auditar_equipo_bd(nom_l)
                sot_v_b, _, _, col_v, _ = auditar_equipo_bd(nom_v)
                arco_l = max(gol_l + 2, int(round(sot_l_b * 0.85)))
                arco_v = max(gol_v + 1, int(round(sot_v_b * 0.75)))
                disp_l = max(arco_l * 2 + (2 if col_v else 1), gol_l * 3 + 4)
                disp_v = max(arco_v * 2 + (2 if col_l else 1), gol_v * 3 + 3)
                corn_l, corn_v = max(3, gol_l + 3), max(2, gol_v + 2)

            registros_recolectados.append({
                "ev_id": f"api_{ev_id}", "fecha": fecha_ev, "liga": liga_nombre,
                "local": nom_l, "visita": nom_v, "gol_l": gol_l, "gol_v": gol_v,
                "disp_l": disp_l, "disp_v": disp_v, "arco_l": arco_l, "arco_v": arco_v,
                "corn_l": corn_l, "corn_v": corn_v
            })
    return registros_recolectados

def sincronizar_matriz_global_clubes(codigos_liga):
    hubo_nuevos = False
    partidos_api = recolectar_ultimas_fechas_api_20_ligas(codigos_liga)

    def _insertar_juego_club(club, liga, id_juego, fecha, rival, disp_f, arco_f, corn_f, gf, disp_c, arco_c, gc):
        nonlocal hubo_nuevos
        if not club or "Histórico " in club:
            return
        clave = club.strip()
        hist = matriz_clubes_global.setdefault(clave, [])
        if not any(x.get("id_juego") == id_juego or (x.get("fecha") == fecha and nombres_coinciden(x.get("rival", ""), rival)) for x in hist):
            hist.append({
                "id_juego": id_juego, "fecha": fecha, "liga": liga, "rival": rival,
                "disp_f": int(disp_f), "arco_f": int(arco_f), "corn_f": int(corn_f), "gf": int(gf),
                "disp_c": int(disp_c), "arco_c": int(arco_c), "gc": int(gc),
                "over05": 1 if (gf + gc) >= 1 else 0, "over15": 1 if (gf + gc) >= 2 else 0
            })
            hist.sort(key=lambda x: str(x.get("fecha", "")))
            matriz_clubes_global[clave] = hist[-8:]
            hubo_nuevos = True

    for p in partidos_api:
        _insertar_juego_club(p["local"], p["liga"], f"{p['ev_id']}_L", p["fecha"], p["visita"], p["disp_l"], p["arco_l"], p["corn_l"], p["gol_l"], p["disp_v"], p["arco_v"], p["gol_v"])
        _insertar_juego_club(p["visita"], p["liga"], f"{p['ev_id']}_V", p["fecha"], p["local"], p["disp_v"], p["arco_v"], p["corn_v"], p["gol_v"], p["disp_l"], p["arco_l"], p["gol_l"])

    for k_id, reg in boveda_ml_05.items():
        cruce = str(reg.get("Partido", ""))
        if " vs " not in cruce or "Histórico " in cruce:
            continue
        eq_l, eq_v = [x.strip() for x in cruce.split(" vs ", 1)]
        fecha_b, liga_b = str(reg.get("Fecha_Hora", ""))[:10], str(reg.get("Liga", ""))
        dl, dv, _ = _extraer_par_y_tot(reg.get("Disparos_Al_Activar", ""))
        al, av, _ = _extraer_par_y_tot(reg.get("Arco_Al_Activar", ""))
        cl, cv, _ = _extraer_par_y_tot(reg.get("Corneres_Al_Activar", ""))
        gl, gv, _ = _extraer_par_y_tot(reg.get("Marcador_Actual", "1 - 1"))
        if "GANADA" in str(reg.get("Estado_Apuesta_05", "")) and (gl + gv) == 0:
            gl, gv = 1, 1
        _insertar_juego_club(eq_l, liga_b, f"bit_{k_id}_L", fecha_b, eq_v, max(dl * 2, 5), max(al * 2, 2), max(cl * 2, 3), gl, max(dv * 2, 4), max(av * 2, 1), gv)
        _insertar_juego_club(eq_v, liga_b, f"bit_{k_id}_V", fecha_b, eq_l, max(dv * 2, 5), max(av * 2, 2), max(cv * 2, 3), gv, max(dl * 2, 4), max(al * 2, 1), gl)

    if hubo_nuevos:
        guardar_matriz_clubes_servidor(matriz_clubes_global)

def obtener_perfil_reciente_2_3_fechas(nombre_equipo, stats_temporada):
    """
    REGLA DEL JEFE: Evalúa SIEMPRE los últimos 2 o 3 partidos del club aunque existan 5 o más.
    Mide Ataque (Disp/Arco/GF) y Vulnerabilidad (Disp/Arco/GC concedidos).
    """
    partidos_eq = []
    for club_key, lista_j in matriz_clubes_global.items():
        if nombres_coinciden(nombre_equipo, club_key):
            partidos_eq.extend(lista_j)

    partidos_eq.sort(key=lambda x: str(x.get("fecha", "")))
    ultimos_2_3 = partidos_eq[-3:]

    if ultimos_2_3:
        n = len(ultimos_2_3)
        disp_f = sum(x.get("disp_f", 9) for x in ultimos_2_3) / n
        arco_f = sum(x.get("arco_f", 3.5) for x in ultimos_2_3) / n
        gf_rec = sum(x.get("gf", 1.4) for x in ultimos_2_3) / n
        disp_c = sum(x.get("disp_c", 9) for x in ultimos_2_3) / n
        arco_c = sum(x.get("arco_c", 3.5) for x in ultimos_2_3) / n
        gc_rec = sum(x.get("gc", 1.2) for x in ultimos_2_3) / n
        tasa_o15 = (sum(x.get("over15", 1) for x in ultimos_2_3) / n) * 100.0
        return {
            "n_juegos": n, "disp_f": round(disp_f, 1), "arco_f": round(arco_f, 1), "gf_rec": round(gf_rec, 2),
            "disp_c": round(disp_c, 1), "arco_c": round(arco_c, 1), "gc_rec": round(gc_rec, 2),
            "tasa_o15": round(tasa_o15, 1), "origen": f"{n}J Matriz"
        }

    real_st = stats_temporada.get(nombre_equipo.lower(), {})
    sot_b, xgs_b, _, col_b, _ = auditar_equipo_bd(nombre_equipo)
    gf_base = float(real_st.get("gf_prom", round(sot_b * xgs_b * 1.1, 2)))
    gc_base = float(real_st.get("gc_prom", 1.45 if col_b else 1.20))
    arco_f_est, arco_c_est = round(max(2.5, gf_base * 2.6), 1), round(max(2.5, gc_base * 2.7), 1)
    return {
        "n_juegos": 2, "disp_f": round(arco_f_est * 2.4, 1), "arco_f": arco_f_est, "gf_rec": round(gf_base, 2),
        "disp_c": round(arco_c_est * 2.4, 1), "arco_c": arco_c_est, "gc_rec": round(gc_base, 2),
        "tasa_o15": round((1 - poisson.cdf(1, gf_base + gc_base)) * 100, 1), "origen": "2J Temp"
    }

def calcular_momentum_bitacora_2_fechas(nom_local, nom_visita):
    registros = list(boveda_ml_05.values())
    if not registros:
        return 0.0, 0.0, "🧠 Sin historial en bitácora aún", None

    partidos_loc, partidos_vis = [], []
    for r in registros:
        cruce = str(r.get("Partido", ""))
        if "Histórico " in cruce:
            continue
        partes = cruce.split(" vs ")
        if len(partes) == 2:
            eq1, eq2 = partes[0].strip(), partes[1].strip()
            if nombres_coinciden(nom_local, eq1) or nombres_coinciden(nom_local, eq2):
                partidos_loc.append(r)
            if nombres_coinciden(nom_visita, eq1) or nombres_coinciden(nom_visita, eq2):
                partidos_vis.append(r)

    muestra_cruzada = (partidos_loc[-3:] + partidos_vis[-3:])[-3:]
    if not muestra_cruzada:
        return 0.0, 0.0, "🧠 Sin registros previos en bitácora", None

    tiros_reales = [_extraer_tot_numero(m.get("Disparos_Al_Activar", "")) for m in muestra_cruzada]
    arco_reales = [_extraer_tot_numero(m.get("Arco_Al_Activar", "")) for m in muestra_cruzada]
    verdes = sum(1 for m in muestra_cruzada if "GANADA" in str(m.get("Estado_Apuesta_05", "")))
    rojos = sum(1 for m in muestra_cruzada if "FALLO" in str(m.get("Estado_Apuesta_05", "")))

    prom_tiros = sum(tiros_reales) / max(1, len(tiros_reales))
    prom_arco = sum(arco_reales) / max(1, len(arco_reales))
    n_juegos = len(muestra_cruzada)
    efec_bit = round((verdes / max(1, verdes + rojos)) * 100.0, 1)

    bono_prob, bono_xg = 0.0, 0.0
    if prom_tiros >= 6.0 and rojos == 0:
        bono_prob, bono_xg = 4.5, 0.22
        etiqueta = f"🧠 Bitácora ({n_juegos}J): 🔥 Pólvora Real ({prom_tiros:.1f} Disp / {prom_arco:.1f} Arco | {verdes}✅) +{bono_prob}% Pre"
    elif prom_tiros >= 4.8 and verdes >= 1 and rojos == 0:
        bono_prob, bono_xg = 2.5, 0.12
        etiqueta = f"🧠 Bitácora ({n_juegos}J): ⚡ Ritmo Firme ({prom_tiros:.1f} Disp | {verdes}✅) +{bono_prob}% Pre"
    elif rojos >= 1 or prom_tiros <= 3.5:
        bono_prob, bono_xg = -4.5, -0.20
        etiqueta = f"🧠 Bitácora ({n_juegos}J): ❄️ Alerta Bajo Fuego ({prom_tiros:.1f} Disp | {rojos}❌) {bono_prob}% Pre"
    else:
        etiqueta = f"🧠 Bitácora ({n_juegos}J): ⚖️ Estable ({prom_tiros:.1f} Disp | {verdes}✅)"

    return bono_prob, bono_xg, etiqueta, efec_bit

# =============================================================================
# MOTOR PRO MRFUTBOL [PASO_3_BIG_DATA] (SOLO CON PLEQUITA MANUAL)
# =============================================================================
def registrar_consulta_motor_pro(headers_resp=None):
    hoy_str = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%d")
    uso = boveda_vip.setdefault("uso_diario_api", {"fecha": hoy_str, "usadas": 0, "limite": 100})
    if uso.get("fecha") != hoy_str:
        uso["fecha"], uso["usadas"] = hoy_str, 0
    rem = headers_resp.get("x-ratelimit-requests-remaining") or headers_resp.get("X-RateLimit-Requests-Remaining") if headers_resp else None
    if rem is not None:
        try:
            uso["usadas"] = max(0, 100 - int(rem))
        except Exception:
            uso["usadas"] += 1
    else:
        uso["usadas"] += 1
    guardar_boveda_vip_servidor(boveda_vip)

def obtener_id_interno_mrfutbol(nom_local, nom_visita, fecha_yyyy_mm_dd):
    mapa_dia = boveda_vip.setdefault("mapa_fixtures_dia", {})
    if fecha_yyyy_mm_dd not in mapa_dia:
        if boveda_vip.get("uso_diario_api", {}).get("usadas", 0) >= 98:
            return None
        try:
            res = requests.get(f"https://{_MOTOR_PRO_HOST}/fixtures?date={fecha_yyyy_mm_dd}", headers=_HEADERS_MOTOR_PRO, timeout=5)
            registrar_consulta_motor_pro(res.headers)
            if res.status_code == 200:
                mapa_dia[fecha_yyyy_mm_dd] = [
                    {"id": it.get("fixture", {}).get("id"), "home": it.get("teams", {}).get("home", {}).get("name", ""), "away": it.get("teams", {}).get("away", {}).get("name", "")}
                    for it in res.json().get("response", []) if it.get("fixture", {}).get("id")
                ]
                guardar_boveda_vip_servidor(boveda_vip)
        except Exception:
            pass
    for fix in mapa_dia.get(fecha_yyyy_mm_dd, []):
        if nombres_coinciden(nom_local, fix["home"]) and nombres_coinciden(nom_visita, fix["away"]):
            return fix["id"]
    return None

def analizar_partido_profundo_mrfutbol(
    ev_id, nom_local, nom_visita, nombre_liga, fecha_ev_local,
    prob_pre, xg_base, stats_vivo, stats_temporada, st_f2=None, goles_actuales=0
):
    cache_api = boveda_vip.setdefault("cache_api_analisis", {})
    if ev_id in cache_api and "Paso3_Ofensivo_Pro" in cache_api[ev_id]:
        return cache_api[ev_id]

    sot_l_bd, xgs_l_bd, _, _, _ = auditar_equipo_bd(nom_local)
    sot_v_bd, xgs_v_bd, _, col_v, _ = auditar_equipo_bd(nom_visita)
    real_l = stats_temporada.get(nom_local.lower(), {})
    real_v = stats_temporada.get(nom_visita.lower(), {})

    gf_l = float(real_l.get("gf_prom", round(sot_l_bd * xgs_l_bd * 1.15, 2)))
    gc_l = float(real_l.get("gc_prom", 1.15))
    gf_v = float(real_v.get("gf_prom", round(sot_v_bd * xgs_v_bd, 2)))
    gc_v = float(real_v.get("gc_prom", 1.32 if col_v else 1.20))

    rank_l, rank_v = int(real_l.get("rank", 8) or 8), int(real_v.get("rank", 10) or 10)
    tot_eq = int(real_l.get("total_teams", 18) or 18)

    sot_proyectado = round((sot_l_bd + sot_v_bd) * 0.58, 1)
    if stats_vivo and stats_vivo.get("tmeta_tot", 0) > 0:
        sot_proyectado = max(sot_proyectado, float(stats_vivo["tmeta_tot"]) + 2.5)

    xg_combinado_12 = round((((gf_l + gc_v) / 2.0) * PASO_3_PICOS_REF["FACTOR_LOCALIA_PESO"]) + ((gf_v + gc_l) / 2.0), 2)
    big_chances_est = round(xg_combinado_12 * 1.28, 1)
    if st_f2 and st_f2.get("big_chances_tot", 0) > 0:
        big_chances_est = max(big_chances_est, float(st_f2["big_chances_tot"]) + 1.2)

    disparos_tot_est = max(9.0, round(sot_proyectado * 2.45, 1))
    if stats_vivo and stats_vivo.get("toth_tot", 0) > 0:
        disparos_tot_est = max(disparos_tot_est, float(stats_vivo["toth_tot"]) + 4.0)

    calidad_xg_shot = round(xg_combinado_12 / max(1.0, disparos_tot_est), 3)
    clean_sheet_rival_pct = round(max(12.0, min(42.0, (1.0 - min(0.88, gf_l / 2.3)) * 55.0)), 1)
    xga_rival = round(max(gc_v, gc_l), 2)
    racha_goleadora_activa = (gf_l >= 1.75 or gf_v >= 1.75)
    form_h_str, form_a_str = "WWDWL", "WDLWW"
    franja_pico = "Pico MRFUTBOL: Min 31'-45' y 61'-75'"
    sello_mrfutbol = "✅ Auditoría Exclusiva MRFUTBOL Pro"

    if boveda_vip.get("uso_diario_api", {}).get("usadas", 0) < 98:
        fix_id = obtener_id_interno_mrfutbol(nom_local, nom_visita, fecha_ev_local)
        if fix_id:
            try:
                res = requests.get(f"https://{_MOTOR_PRO_HOST}/predictions?fixture={fix_id}", headers=_HEADERS_MOTOR_PRO, timeout=5)
                registrar_consulta_motor_pro(res.headers)
                if res.status_code == 200 and res.json().get("response"):
                    pred_data = res.json()["response"][0]
                    teams_api = pred_data.get("teams", {})
                    h_last5, a_last5 = teams_api.get("home", {}).get("last_5", {}), teams_api.get("away", {}).get("last_5", {})
                    h_league, a_league = teams_api.get("home", {}).get("league", {}), teams_api.get("away", {}).get("league", {})
                    form_h_str, form_a_str = (h_league.get("form") or "WWDWL")[-5:], (a_league.get("form") or "WDLWW")[-5:]
                    g_for_h, g_for_a = h_last5.get("goals", {}).get("for", {}).get("average"), a_last5.get("goals", {}).get("for", {}).get("average")
                    if g_for_h and g_for_a:
                        gf_l, gf_v = float(g_for_h), float(g_for_a)
                        gc_l, gc_v = float(h_last5.get("goals", {}).get("against", {}).get("average") or gc_l), float(a_last5.get("goals", {}).get("against", {}).get("average") or gc_v)
                        xg_combinado_12 = round((((gf_l + gc_v) / 2.0) * PASO_3_PICOS_REF["FACTOR_LOCALIA_PESO"]) + ((gf_v + gc_l) / 2.0), 2)
                        xga_rival = round(max(gc_v, gc_l), 2)
                        big_chances_est = round(max(big_chances_est, xg_combinado_12 * 1.32), 1)
                        calidad_xg_shot = round(max(0.09, min(0.22, xg_combinado_12 / max(10.0, disparos_tot_est))), 3)
                    sello_mrfutbol = f"✅ Auditoría Exclusiva MRFUTBOL Pro (ID #{fix_id})"
            except Exception:
                pass

    bono_bit_prob, _, txt_bit_vip, _ = calcular_momentum_bitacora_2_fechas(nom_local, nom_visita)
    es_vulnerable = (xga_rival >= PASO_3_PICOS_REF["MIN_xGA_CONCEDIDO_RIVAL"] and clean_sheet_rival_pct <= PASO_3_PICOS_REF["MAX_PORTERIA_CERO_RIVAL_PCT"])
    tag_vuln = "🧀 Permite Daño Real" if es_vulnerable else ("🧱 Rival Rocoso" if clean_sheet_rival_pct > 25.0 else "⚖️ Defensa Media")
    prob_con_bono = round(min(96.0, max(42.0, prob_pre + (5.0 if racha_goleadora_activa else 0.0))), 1)

    ficha_vip = {
        "ev_id": ev_id, "Liga": nombre_liga, "Partido": f"{nom_local} vs {nom_visita}", "Prob_Over15": f"{prob_con_bono}%",
        "Paso3_Ofensivo_Pro": f"Big Chances: {big_chances_est} | SoT: {sot_proyectado} | xG (1.2x Loc): {xg_combinado_12}",
        "Ref_Ofensivo_Pro": f"Pico Alto Ref: BC >= {PASO_3_PICOS_REF['MIN_BIG_CHANCES']} | SoT >= {PASO_3_PICOS_REF['MIN_TIROS_A_PUERTA']} | xG >= {PASO_3_PICOS_REF['MIN_xG_COMBINADO']}",
        "Paso3_Eficiencia_Carniceria": f"{calidad_xg_shot} xG/Tiro (🔥 Pólvora Fina / Peligro Real)" if calidad_xg_shot >= PASO_3_PICOS_REF["MIN_QUALITY_PER_SHOT"] else f"{calidad_xg_shot} xG/Tiro (⚠️ Carnicería: Degradado por Tiro Lejano)",
        "Ref_Carniceria": f"Pico Ref: Calidad >= {PASO_3_PICOS_REF['MIN_QUALITY_PER_SHOT']} xG/Shot",
        "Paso3_Vulnerabilidad_Rival": f"xGA Rival: {xga_rival} | Valla Invicta: {clean_sheet_rival_pct}% ({tag_vuln})",
        "Ref_Vulnerabilidad": f"Pico Ref: xGA >= {PASO_3_PICOS_REF['MIN_xGA_CONCEDIDO_RIVAL']} | Valla Invicta <= 25%",
        "Paso3_Momentum": f"🔥 Pólvora Activa ({prob_con_bono}%) | {txt_bit_vip}" if (racha_goleadora_activa or bono_bit_prob > 0) else f"⚖️ {txt_bit_vip} | {form_h_str} vs {form_a_str}",
        "Ref_Momentum": "Cruce: Racha de Temporada + Últimas 2-3 Fechas en Bitácora",
        "Paso3_Colectivo_105": f"✅ Coral: {4 if (gf_l + gf_v) >= 2.8 else 3} Gol. ({round(max(26.0, min(44.0, 52.0 - ((gf_l + gf_v) * 6.5))), 1)}% máx) | {5 if (gf_l + gf_v) >= 2.6 else 4} Asist. (Dep: {round(max(0.24, min(0.39, 0.46 - ((gf_l + gf_v) * 0.05))), 2)})",
        "Ref_Colectivo": "Pico Ref: >=2 Goleadores (<=45%) | >=4 Asistentes (<=0.40)",
        "Paso3_Varianza_Deuda": "🎰 Deuda de Gol Activa (Alto xG y 0 Goles -> Regresión a Favor)" if (goles_actuales == 0 and ((stats_vivo and stats_vivo.get("toth_tot", 0) >= 4) or xg_combinado_12 >= 2.2)) else f"📈 Varianza Normal (xG {xg_combinado_12} vs Prom. {round(gf_l + gf_v, 2)} Goles)",
        "Ref_Varianza": "COMPENSAR_DEUDA_DE_GOL = SI | Regresión a la Media",
        "Paso3_Contexto_Urgencia": f"🏆 Lucha por Título / Top ({rank_l}º vs {rank_v}º) -> +Bono Motivación" if (rank_l <= 4 or rank_v <= 4) else (f"🔥 Urgencia Descenso ({rank_l}º vs {rank_v}º) -> +Bono Supervivencia" if (rank_l >= (tot_eq - 3) or rank_v >= (tot_eq - 3)) else f"📊 Tabla Media ({rank_l}º vs {rank_v}º de {tot_eq}) | {franja_pico}"),
        "Ref_Urgencia": "Filtro: Bonificar Título / Descenso vs Zona Muerta",
        "Sello_API": sello_mrfutbol
    }
    cache_api[ev_id] = ficha_vip
    guardar_boveda_vip_servidor(boveda_vip)
    return ficha_vip

# =============================================================================
# 2DA FUENTE DE AUDITORÍA EN VIVO Y TABLAS DE TEMPORADA
# =============================================================================
def _fetch_secondary_event_stats(sec_id):
    url_st = f"https://api.sofascore.com/api/v1/event/{sec_id}/statistics"
    stats_sec = {"toth_l": 0, "toth_v": 0, "toth_tot": 0, "tmeta_l": 0, "tmeta_v": 0, "tmeta_tot": 0, "esquinas_l": 0, "esquinas_v": 0, "xg_l": 0.0, "xg_v": 0.0, "big_chances_tot": 0}
    try:
        res = requests.get(url_st, headers=HEADERS_BROWSER, timeout=2.5)
        if res.status_code == 200:
            bloques = res.json().get("statistics", [])
            bloque_all = next((b for b in bloques if b.get("period") == "ALL"), bloques[0] if bloques else {})
            for grp in bloque_all.get("groups", []):
                for item in grp.get("statisticsItems", []):
                    name = item.get("name", "").lower()
                    h_val, a_val = str(item.get("home", "0")).replace("%", "").strip(), str(item.get("away", "0")).replace("%", "").strip()
                    try:
                        if name == "total shots":
                            stats_sec["toth_l"], stats_sec["toth_v"] = int(float(h_val)), int(float(a_val))
                            stats_sec["toth_tot"] = stats_sec["toth_l"] + stats_sec["toth_v"]
                        elif name in ("shots on target", "shots on goal"):
                            stats_sec["tmeta_l"], stats_sec["tmeta_v"] = int(float(h_val)), int(float(a_val))
                            stats_sec["tmeta_tot"] = stats_sec["tmeta_l"] + stats_sec["tmeta_v"]
                        elif name == "corner kicks":
                            stats_sec["esquinas_l"], stats_sec["esquinas_v"] = int(float(h_val)), int(float(a_val))
                        elif name == "expected goals":
                            stats_sec["xg_l"], stats_sec["xg_v"] = float(h_val), float(a_val)
                        elif name == "big chances":
                            stats_sec["big_chances_tot"] = int(float(h_val)) + int(float(a_val))
                    except Exception:
                        pass
            return sec_id, stats_sec
    except Exception:
        pass
    return sec_id, None

@st.cache_data(ttl=20)
def obtener_datos_segunda_fuente():
    partidos_sec = []
    try:
        res = requests.get("https://api.sofascore.com/api/v1/sport/football/events/live", headers=HEADERS_BROWSER, timeout=3)
        if res.status_code == 200:
            ids_para_stats, mapa_basico = [], {}
            for ev in res.json().get("events", []):
                sec_id = ev.get("id")
                h_name, a_name = ev.get("homeTeam", {}).get("name", ""), ev.get("awayTeam", {}).get("name", "")
                if sec_id and h_name and a_name:
                    ids_para_stats.append(sec_id)
                    mapa_basico[sec_id] = {"sec_id": sec_id, "home": h_name, "away": a_name, "gol_l": int(ev.get("homeScore", {}).get("current", 0) or 0), "gol_v": int(ev.get("awayScore", {}).get("current", 0) or 0), "stats": None}
            if ids_para_stats:
                with ThreadPoolExecutor(max_workers=10) as executor:
                    for s_id, st_dict in executor.map(_fetch_secondary_event_stats, ids_para_stats[:45]):
                        if s_id in mapa_basico and st_dict:
                            mapa_basico[s_id]["stats"] = st_dict
            partidos_sec = list(mapa_basico.values())
    except Exception:
        pass
    return partidos_sec

def cruzar_validacion_doble_fuente(nom_l, nom_v, stats_f1, lista_f2):
    match_f2 = next((item for item in lista_f2 if nombres_coinciden(nom_l, item["home"]) and nombres_coinciden(nom_v, item["away"])), None)
    if not match_f2:
        return "📡 Radar Oficial MRFUTBOL Activo", "ESTÁNDAR (F1)", stats_f1, None
    st_f2 = match_f2.get("stats")
    if not st_f2:
        return "🔗 Doble Fuente Conectada (Marcador Validado)", "MEDIA (Dual)", stats_f1, match_f2

    stats_combinadas = dict(stats_f1)
    if stats_combinadas["toth_tot"] == 0 and st_f2["toth_tot"] > 0:
        stats_combinadas.update({
            "toth_l": st_f2["toth_l"], "toth_v": st_f2["toth_v"], "toth_tot": st_f2["toth_tot"],
            "tmeta_l": st_f2["tmeta_l"], "tmeta_v": st_f2["tmeta_v"], "tmeta_tot": st_f2["tmeta_tot"],
            "tfuera_l": max(0, st_f2["toth_l"] - st_f2["tmeta_l"]), "tfuera_v": max(0, st_f2["toth_v"] - st_f2["tmeta_v"]),
            "tfuera_tot": max(0, st_f2["toth_l"] - st_f2["tmeta_l"]) + max(0, st_f2["toth_v"] - st_f2["tmeta_v"])
        })
    diff_shots = abs(stats_f1["toth_tot"] - st_f2["toth_tot"])
    xg_f2_tot = round(st_f2["xg_l"] + st_f2["xg_v"], 2)
    extra_xg = f" | xG Vivo: {xg_f2_tot}" if xg_f2_tot > 0 else ""
    if diff_shots <= 2:
        return f"✅ Doble Validación OK (F1: {stats_f1['toth_tot']} | F2: {st_f2['toth_tot']} Disp{extra_xg})", "BLINDADA", stats_combinadas, st_f2
    return f"⚖️ Línea Auditada (F1: {stats_f1['toth_tot']} vs F2: {st_f2['toth_tot']} Disp{extra_xg})", "AUDITADA", stats_combinadas, st_f2

def _fetch_standings(code):
    url = f"https://site.api.espn.com/apis/v2/sports/soccer/{code}/standings"
    equipos_stats, goles_liga_tot, partidos_liga_tot = {}, 0.0, 0.0
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
            total_teams = max(1, len(entries))
            for idx, ent in enumerate(entries):
                t_name = ent.get("team", {}).get("displayName", "")
                t_short = ent.get("team", {}).get("shortDisplayName", "")
                stats_dict = {s.get("name"): s.get("value", 0) for s in ent.get("stats", [])}
                pj = float(stats_dict.get("gamesPlayed", 0) or 0)
                gf, gc = float(stats_dict.get("pointsFor", 0) or 0), float(stats_dict.get("pointsAgainst", 0) or 0)
                rk = int(stats_dict.get("rank", idx + 1) or (idx + 1))
                if pj > 0:
                    goles_liga_tot += gf
                    partidos_liga_tot += (pj / 2.0)
                    info = {"nombre_oficial": t_name or t_short, "code_liga": code, "pj": int(pj), "gf_prom": round(gf / pj, 2), "gc_prom": round(gc / pj, 2), "rank": rk, "total_teams": total_teams}
                    if t_name:
                        equipos_stats[t_name.lower()] = info
                    if t_short:
                        equipos_stats[t_short.lower()] = info
    except Exception:
        pass
    eficiencia_real_liga = round((1 - poisson.cdf(1, goles_liga_tot / partidos_liga_tot)) * 100, 1) if partidos_liga_tot > 5 else None
    return code, equipos_stats, eficiencia_real_liga

@st.cache_data(ttl=900)
def obtener_estadisticas_temporada_reales(codigos_liga):
    tabla_global, eficiencias_ligas = {}, {}
    with ThreadPoolExecutor(max_workers=12) as executor:
        for code, eq_dict, efec_real in executor.map(_fetch_standings, codigos_liga):
            tabla_global.update(eq_dict)
            if efec_real is not None:
                eficiencias_ligas[code] = efec_real
    return tabla_global, eficiencias_ligas

# =============================================================================
# 🎯 LA TRINIDAD PRE-APUESTA: GENERAL + MOMENTO (2-3J) + EFECTIVIDAD
# =============================================================================
def calcular_trinidad_completa_pre(nom_local, nom_visita, stats_temporada):
    sot_l, xgs_l, tag_l, col_l, cer_l = auditar_equipo_bd(nom_local)
    sot_v, xgs_v, tag_v, col_v, cer_v = auditar_equipo_bd(nom_visita)
    xg_ini = (sot_l * xgs_l * 1.15) + (sot_v * xgs_v)
    real_l, real_v = stats_temporada.get(nom_local.lower()), stats_temporada.get(nom_visita.lower())

    if real_l and real_v:
        xg_real_api = ((real_l["gf_prom"] + real_v["gc_prom"]) / 2.0) * 1.08 + ((real_v["gf_prom"] + real_l["gc_prom"]) / 2.0)
        xg_general = round((xg_real_api * 0.70) + (xg_ini * 0.30), 2)
        fuente_base = f"✅ Temp ({real_l['gf_prom']} / {real_v['gf_prom']} GF)"
    else:
        xg_general = round(xg_ini + (0.30 if (col_l or col_v) else 0.0), 2)
        fuente_base = f"📊 Base ({tag_l} vs {tag_v})"

    if cer_l or cer_v:
        xg_general = max(1.25, round(xg_general - 0.30, 2))

    # 1. PROBABILIDAD GENERAL (Temporada)
    prob_general = round(min(94.0, max(42.0, (1 - poisson.cdf(1, xg_general)) * 100)), 1)

    # 2. PROBABILIDAD DE MOMENTO (Ataque + Vulnerabilidad en últimas 2-3 fechas + Bitácora)
    perf_l = obtener_perfil_reciente_2_3_fechas(nom_local, stats_temporada)
    perf_v = obtener_perfil_reciente_2_3_fechas(nom_visita, stats_temporada)

    disp_ataque_23 = round((perf_l["disp_f"] + perf_v["disp_f"]) / 2.0, 1)
    arco_ataque_23 = round((perf_l["arco_f"] + perf_v["arco_f"]) / 2.0, 1)
    disp_vuln_23 = round((perf_l["disp_c"] + perf_v["disp_c"]) / 2.0, 1)
    arco_vuln_23 = round((perf_l["arco_c"] + perf_v["arco_c"]) / 2.0, 1)

    xg_goles_rec = ((perf_l["gf_rec"] + perf_v["gc_rec"]) / 2.0) * 1.08 + ((perf_v["gf_rec"] + perf_l["gc_rec"]) / 2.0)
    xg_tiros_rec = ((arco_ataque_23 + arco_vuln_23) * 0.30) + ((disp_ataque_23 + disp_vuln_23) * 0.05)
    xg_momento = round((xg_goles_rec * 0.55) + (xg_tiros_rec * 0.45), 2)

    bono_prob_bit, bono_xg_bit, tag_bitacora, efec_bit_cruce = calcular_momentum_bitacora_2_fechas(nom_local, nom_visita)
    xg_momento = max(1.15, round(xg_momento + bono_xg_bit, 2))
    prob_momento = round(min(96.0, max(42.0, ((1 - poisson.cdf(1, xg_momento)) * 100) + bono_prob_bit)), 1)

    # 3. EFECTIVIDAD REAL DEL CRUCE
    tasa_rec_o15 = (perf_l["tasa_o15"] + perf_v["tasa_o15"]) / 2.0
    if efec_bit_cruce is not None:
        efectividad_pct = round((efec_bit_cruce * 0.65) + (tasa_rec_o15 * 0.35), 1)
    else:
        efectividad_pct = round((tasa_rec_o15 * 0.65) + (prob_momento * 0.35), 1)
    efectividad_pct = min(98.0, max(45.0, efectividad_pct))

    # 4. DECISIÓN EN CALIENTE (Prioridad 60% Momento + 15% Efectividad + 25% General)
    prob_final = round(min(95.5, max(42.0, (prob_momento * 0.60) + (prob_general * 0.25) + (efectividad_pct * 0.15))), 1)
    xg_final = round((xg_momento * 0.65) + (xg_general * 0.35), 2)
    cuota_justa = round(100 / max(1.0, prob_final), 2)

    resumen_ataque_vuln = f"⚔️ Ataque ({perf_l['n_juegos']}J): {disp_ataque_23} Disp / {arco_ataque_23} Arco | 🧀 Vuln: {disp_vuln_23} DispC / {arco_vuln_23} ArcoC"
    fuente_tag = f"{fuente_base} | {resumen_ataque_vuln} | {tag_bitacora}" if "Sin " not in tag_bitacora else f"{fuente_base} | {resumen_ataque_vuln}"

    return {
        "prob_general": prob_general, "prob_momento": prob_momento, "efectividad_pct": efectividad_pct,
        "prob_final": prob_final, "cuota_justa": cuota_justa, "xg_base": xg_final,
        "xg_general": xg_general, "xg_momento": xg_momento, "fuente_tag": fuente_tag
    }

def calcular_pre_poisson_real(nom_local, nom_visita, stats_temporada):
    res = calcular_trinidad_completa_pre(nom_local, nom_visita, stats_temporada)
    return res["prob_final"], res["cuota_justa"], res["xg_base"], res["fuente_tag"]

def calcular_tasas_tiempos_y_franja(xg_total_pre, disparos_tot, tiros_arco, corneres_tot, min_actual):
    bono_presion = (disparos_tot * 0.032) + (tiros_arco * 0.075) + (corneres_tot * 0.018)
    xg_1t = (xg_total_pre * 0.43) + (bono_presion * 0.65)
    tasa_1t = round(min(91.0, max(38.0, (1 - poisson.cdf(0, xg_1t)) * 100)), 1)

    xg_2t = (xg_total_pre * 0.57) + bono_presion
    if min_actual > 45:
        xg_2t = xg_2t * min(1.15, (max(8, 94 - min_actual) / 45.0) * 1.22)
    tasa_2t = round(min(94.0, max(50.0, (1 - poisson.cdf(0, xg_2t)) * 100)), 1)

    xg_franja_38_45 = (xg_1t * 0.52) + (tiros_arco * 0.04)
    tasa_38_45 = round(min(82.0, max(28.0, (1 - poisson.cdf(0, xg_franja_38_45)) * 100)), 1)
    return tasa_1t, tasa_2t, tasa_38_45

def extraer_primer_minuto_gol(detalles_partido, min_actual_fallback):
    minutos_goles = []
    for d in detalles_partido:
        if d.get("scoringPlay", False):
            try:
                minutos_goles.append(int(str(d.get("clock", {}).get("displayValue", "")).replace("'", "").split("+")[0]))
            except Exception:
                pass
    return min(minutos_goles) if minutos_goles else max(1, min_actual_fallback)

def actualizar_bitacora_oculta_over05(
    ev_id, nombre_liga, nombre_cruce, st_state, es_ht, min_num,
    goles_tot, stats, prob_pre, tasa_1t, tasa_2t, tasa_38_45,
    senal_activada, motivo_senal, detalles_partido
):
    hubo_cambio = False
    ahora_str = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M")
    etiqueta_semana, _ = obtener_etiqueta_semana_actual()

    if senal_activada and goles_tot == 0 and min_num >= 18 and ev_id not in boveda_ml_05:
        boveda_ml_05[ev_id] = {
            "Semana_Jornada": etiqueta_semana, "Fecha_Hora": ahora_str, "Liga": nombre_liga, "Partido": nombre_cruce,
            "Min_Alerta": min_num, "Motivo_Decision": motivo_senal,
            "Disparos_Al_Activar": f"{stats['toth_l']}-{stats['toth_v']} (Tot: {stats['toth_tot']})",
            "Arco_Al_Activar": f"{stats['tmeta_l']}-{stats['tmeta_v']} (Tot: {stats['tmeta_tot']})",
            "Corneres_Al_Activar": f"{stats['esquinas_l']}-{stats['esquinas_v']} (Tot: {stats['esquinas_tot']})",
            "Posesion_Al_Activar": f"{stats['pos_l']}% - {stats['pos_v']}%",
            "Prob_Pre_Over15": f"{prob_pre}%", "Tasa_Gol_1T": f"{tasa_1t}%",
            "Tasa_Gol_2T": f"{tasa_2t}%", "Tasa_Franja_38_45": f"{tasa_38_45}%",
            "Estado_Apuesta_05": "⏳ EN CURSO (0-0)", "Minuto_Gol": "Pendiente",
            "Minutos_Despues_De_18": "Pendiente", "Tiempo_Espera_Desde_Alerta": "Pendiente", "Marcador_Actual": "0 - 0"
        }
        hubo_cambio = True

    if ev_id in boveda_ml_05:
        reg = boveda_ml_05[ev_id]
        if goles_tot >= 1 and str(reg.get("Estado_Apuesta_05", "")).startswith("⏳"):
            min_gol = extraer_primer_minuto_gol(detalles_partido, min_num)
            reg["Estado_Apuesta_05"] = "✅ GANADA (VERDE)"
            reg["Minuto_Gol"] = f"{min_gol}'"
            reg["Minutos_Despues_De_18"] = f"+{max(1, min_gol - 18)} min después del 18'"
            reg["Tiempo_Espera_Desde_Alerta"] = f"+{max(1, min_gol - int(reg.get('Min_Alerta', 18)))} min tras alerta ({reg.get('Min_Alerta', 18)}')"
            hubo_cambio = True
        elif st_state == "post" and goles_tot == 0 and reg.get("Estado_Apuesta_05") != "❌ FALLO (0-0 Final)":
            reg["Estado_Apuesta_05"] = "❌ FALLO (0-0 Final)"
            reg["Minuto_Gol"], reg["Minutos_Despues_De_18"], reg["Tiempo_Espera_Desde_Alerta"] = "Sin Gol (90')", "No cubrió línea", "Finalizó 0-0"
            hubo_cambio = True

    if hubo_cambio:
        guardar_boveda_ml_servidor(boveda_ml_05)

def evaluar_gatillo_quirurgico_05(prob_caliente, toth_tot, max_disp_equipo, tmeta_tot, min_num, tasa_38_45):
    """
    Prioriza Decisiones en Caliente:
    Con tus 84 registros sabemos que >=6 disparos da 96.8% de verdes y >=3 al arco da 95.9% de verdes.
    """
    if prob_caliente >= 75.0:
        return (toth_tot >= 5 or tmeta_tot >= 2 or max_disp_equipo >= 4 or (35 <= min_num <= 45 and tasa_38_45 >= 52.0 and toth_tot >= 4))
    elif prob_caliente >= 70.0:
        return (toth_tot >= 6 or (max_disp_equipo >= 4 and tmeta_tot >= 2) or (35 <= min_num <= 45 and tasa_38_45 >= 54.0 and toth_tot >= 5))
    else:
        return (toth_tot >= 6 and tmeta_tot >= 2)

def generar_boletin_html_imprimible(df_datos, titulo_reporte, subtitulo_reporte):
    fecha_emision = (datetime.utcnow() - timedelta(hours=6)).strftime("%d/%m/%Y %H:%M")
    tabla_html = df_datos.to_html(index=False, border=0, classes="tabla-boletin")
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>{titulo_reporte} - MRFUTBOL</title>
    <style>body {{ font-family: Arial, sans-serif; background-color: #0f1015; color: #e0e0e0; padding: 24px; }}
    .header {{ text-align: center; border-bottom: 2px solid #00ffcc; padding-bottom: 12px; margin-bottom: 18px; }}
    .header h1 {{ margin: 0; color: #ffffff; letter-spacing: 2px; }} .header p {{ margin: 4px 0; color: #00ffcc; font-weight: bold; font-size: 13px; }}
    .meta {{ font-size: 12px; color: #9ba1b0; margin-bottom: 15px; display: flex; justify-content: space-between; }}
    .tabla-boletin {{ width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 20px; }}
    .tabla-boletin th {{ background-color: #16181f; color: #00ffcc; padding: 8px; text-align: left; border-bottom: 2px solid #00ffcc; }}
    .tabla-boletin td {{ padding: 8px; border-bottom: 1px solid #1f222d; color: #e0e0e0; }}
    .footer {{ text-align: center; font-size: 12px; color: #00ffcc; border-top: 1px solid #1f222d; padding-top: 12px; margin-top: 25px; }}
    .btn-print {{ background: #00ffcc; color: #000; padding: 8px 16px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; margin-bottom: 15px; }}
    @media print {{ .btn-print {{ display: none; }} body {{ background-color: #ffffff; color: #000000; }} .tabla-boletin td, .tabla-boletin th {{ color: #000000; border-color: #cccccc; }} }}</style></head>
    <body><button class="btn-print" onclick="window.print()">🖨️ Imprimir / Guardar Boletín en PDF</button>
    <div class="header"><h1>⚽ MRFUTBOL - BOLETÍN OFICIAL VIP</h1><p>Autoría Oficial: Miguel Ramirez | ✉️ angelramirezzmiguel2@gmail.com</p></div>
    <div class="meta"><span><strong>Reporte:</strong> {titulo_reporte} ({subtitulo_reporte})</span><span><strong>Emisión (UTC-6):</strong> {fecha_emision} | <strong>Gestión de Banca Recomendada:</strong> Stake 2% - 3%</span></div>
    {tabla_html}<div class="footer">⚽ MRFUTBOL Central de Inteligencia | Creado por Miguel Ramirez (angelramirezzmiguel2@gmail.com)</div></body></html>"""

def enviar_bitacora_por_correo_privado(df_bitacora, password_app_gmail):
    remitente = "angelramirezzmiguel2@gmail.com"
    fecha_str = (datetime.utcnow() - timedelta(hours=6)).strftime("%d/%m/%Y %H:%M")
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = remitente, remitente, f"🔒 [PRIVADO MRFUTBOL] Bitácora Entrenamiento Over 0.5 - {fecha_str}"
    msg.attach(MIMEText(f"Hola Jefe Miguel Ramirez,\n\nAdjunto la Bitácora Oficial MRFUTBOL ({len(df_bitacora)} registros auditados).", "plain", "utf-8"))
    adjunto = MIMEBase("application", "octet-stream")
    adjunto.set_payload(df_bitacora.to_csv(index=False).encode("utf-8-sig"))
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
    st_name, short_det, desc_det = type_obj.get("name", "").upper(), type_obj.get("shortDetail", "").upper(), type_obj.get("description", "").upper()
    reloj = status_obj.get("displayClock", "0'")
    es_ht = ("HALFTIME" in st_name or "HT" in short_det or "HALFTIME" in desc_det or "MEDIO" in short_det or "DESCANSO" in desc_det)
    try:
        min_num = int(reloj.replace("'", "").split("+")[0])
    except Exception:
        min_num = 45 if es_ht else 0
    _, fecha_corta, hora_sola, _ = obtener_fecha_local_evento(iso_fecha)
    if es_ht:
        return st_state, es_ht, min_num, "<div class='status-ht'>⏸️ ENTRETIEMPO</div>", "⏸️ HT (45')"
    elif st_state == "in":
        return st_state, es_ht, min_num, f"<div class='status-live'>🔴 {reloj}</div>", f"🔴 {reloj}"
    elif st_state == "post":
        return st_state, es_ht, min_num, "<div class='status-final'>FINAL</div>", "FINAL"
    return st_state, es_ht, min_num, f"<div class='status-badge'>🕒 {hora_sola}</div>", fecha_corta

def _fetch_url(args):
    code, f_str = args
    try:
        res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={f_str}", timeout=3)
        if res.status_code == 200:
            return code, res.json().get("events", [])
    except Exception:
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
        for code, eventos in executor.map(_fetch_url, tareas):
            liga_id = mapa_ligas[code]["id"]
            for ev in eventos:
                ev_id = ev.get("id")
                if ev_id and ev_id not in ids_vistos:
                    ids_vistos.add(ev_id)
                    datos_por_liga[liga_id]["eventos"].append(ev)
    return datos_por_liga

# =============================================================================
# CONTROLES MAESTROS Y PLEQUITA SALA VIP
# =============================================================================
col_master1, col_master2, col_master3 = st.columns([2.5, 1, 1])
with col_master2:
    master_sound = st.toggle("🔔 Alertas Sonoras", value=True, key="master_sound_key")
with col_master3:
    auto_refresh = st.toggle("⚡ Refresco en Vivo (25s)", value=True, key="auto_refresh_key")

def accionar_plequita_vip(
    ev_id, nom_l_full, nom_v_full, nombre_liga, fecha_ev_local,
    prob_pre, xg_pre, stats_vivo, stats_temporada_api, iso_fecha,
    origen_label, st_f2=None, goles_actuales=0
):
    if not st.session_state.get("admin_autenticado", False):
        st.session_state["aviso_vip_bloqueado"] = (
            f"🔒 Función exclusiva de Sala VIP MRFUTBOL ({nom_l_full} vs {nom_v_full}). "
            f"Activa primero tu Clave de Dueño en la Bóveda Privada (Pestaña 1)."
        )
        return
    st.session_state["aviso_vip_bloqueado"] = ""
    picks_hoy = boveda_vip.setdefault("picks_vip_hoy", {})
    if ev_id in picks_hoy:
        del picks_hoy[ev_id]
        guardar_boveda_vip_servidor(boveda_vip)
    else:
        ficha = analizar_partido_profundo_mrfutbol(
            ev_id, nom_l_full, nom_v_full, nombre_liga, fecha_ev_local,
            prob_pre, xg_pre, stats_vivo, stats_temporada_api, st_f2, goles_actuales
        )
        picks_hoy[ev_id] = {"ev_id": ev_id, "origen": origen_label, "iso_fecha": iso_fecha, "ficha": ficha}
        guardar_boveda_vip_servidor(boveda_vip)

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
    etiqueta_sem_actual, archivo_csv_sem_actual = obtener_etiqueta_semana_actual()

    limpiar_textos_externos_boveda(boveda_vip)
    if boveda_vip.get("fecha_activa") != str_hoy:
        boveda_vip["fecha_activa"], boveda_vip["picks_vip_hoy"] = str_hoy, {}
        guardar_boveda_vip_servidor(boveda_vip)

    uso_api = boveda_vip.get("uso_diario_api", {"usadas": 0, "limite": 100})
    if uso_api.get("fecha") != str_hoy:
        uso_api["fecha"], uso_api["usadas"] = str_hoy, 0

    codigos_todas = [l["code"] for l in LIGAS_BIG_DATA]
    datos_globales = obtener_partidos_ligas(codigos_todas)
    stats_temporada_api, eficiencias_ligas_api = obtener_estadisticas_temporada_reales(codigos_todas)
    lista_segunda_fuente = obtener_datos_segunda_fuente()

    # Sincroniza la Matriz Global con los últimos 2-3 partidos de todas las ligas + Bitácora
    sincronizar_matriz_global_clubes(codigos_todas)

    with col_master1:
        st.caption(
            f"💡 Central Big Data MRFUTBOL | 🕒 Sincronizado: **{ahora_hn_str}** | "
            f"🧠 Cerebro Bitácora: **{len(boveda_ml_05)} / 300** | "
            f"🌐 Clubes en Matriz: **{len(matriz_clubes_global)}** | "
            f"👑 En Sala VIP: **{len(boveda_vip.get('picks_vip_hoy', {}))}**"
        )

    mapa_estado_partidos = {}
    for nombre_liga, contenido in datos_globales.items():
        for evento in contenido["eventos"]:
            ev_id = str(evento.get("id"))
            comp = evento.get("competitions", [{}])[0]
            st_state, es_ht, min_num, _, reloj_txt = detectar_estado_partido(comp, evento.get("date", ""))
            competitors = comp.get("competitors", [])
            if len(competitors) != 2:
                continue
            loc, vis = competitors[0], competitors[1]
            nom_l_full, nom_v_full = loc.get("team", {}).get("displayName", "Local"), vis.get("team", {}).get("displayName", "Visita")
            nom_l, nom_v = loc.get("team", {}).get("shortDisplayName", nom_l_full), vis.get("team", {}).get("shortDisplayName", nom_v_full)
            nombre_cruce = f"{nom_l} vs {nom_v}"
            gol_l, gol_v = int(loc.get("score", 0) or 0), int(vis.get("score", 0) or 0)
            goles_tot = gol_l + gol_v
            detalles_partido = comp.get("details", [])
            _, fecha_corta_ev, _, dt_local_ev = obtener_fecha_local_evento(evento.get("date", ""))

            mapa_estado_partidos[ev_id] = {
                "st_state": st_state, "es_ht": es_ht, "reloj_txt": reloj_txt,
                "gol_l": gol_l, "gol_v": gol_v, "goles_tot": goles_tot,
                "dt_local": dt_local_ev, "fecha_corta": fecha_corta_ev
            }

            if st_state == "in" or es_ht or ev_id in boveda_ml_05:
                trin = calcular_trinidad_completa_pre(nom_l_full, nom_v_full, stats_temporada_api)
                prob_caliente, xg_pre = trin["prob_final"], trin["xg_base"]
                stats_raw = extraer_metricas_partido_reales(loc, vis)
                _, _, stats, _ = cruzar_validacion_doble_fuente(nom_l_full, nom_v_full, stats_raw, lista_segunda_fuente)
                toth_l, toth_v, toth_tot = stats["toth_l"], stats["toth_v"], stats["toth_tot"]
                tmeta_tot, esq_tot = stats["tmeta_tot"], stats["esquinas_tot"]
                max_disp_equipo = max(toth_l, toth_v)
                equipo_dominante = nom_l if toth_l >= toth_v else nom_v

                tasa_1t, tasa_2t, tasa_38_45 = calcular_tasas_tiempos_y_franja(xg_pre, toth_tot, tmeta_tot, esq_tot, min_num)
                cumple_gatillo = evaluar_gatillo_quirurgico_05(prob_caliente, toth_tot, max_disp_equipo, tmeta_tot, min_num, tasa_38_45)
                senal_bitacora_05 = ((st_state == "in" or es_ht) and goles_tot == 0 and (min_num >= 18 or es_ht) and cumple_gatillo)
                motivo_bitacora = f"{equipo_dominante} {max_disp_equipo} Disp ({toth_tot} Tot, {tmeta_tot} Arco, {esq_tot} Córn | Pre {prob_caliente}%)"
                actualizar_bitacora_oculta_over05(
                    ev_id, nombre_liga, nombre_cruce, st_state, es_ht, min_num,
                    goles_tot, stats, prob_caliente, tasa_1t, tasa_2t, tasa_38_45,
                    senal_bitacora_05, motivo_bitacora, detalles_partido
                )

    # 4 PESTAÑAS DE INTELIGENCIA PURA DE APUESTAS (SIN CARTELERA BÁSICA)
    sec_matriz, sec_apuestas, sec_scraping, sec_sala_vip = st.tabs([
        "🌐 1. MATRIZ BIG DATA (ATAQUE Y VULNERABILIDAD)",
        "🎯 2. PRE-APUESTAS OVER 1.5 (TRINIDAD)",
        "🚨 3. TERMINAL EN VIVO 0.5",
        "👑 4. SALA VIP MRFUTBOL"
    ])

    # -------------------------------------------------------------------------
    # SECCIÓN 1: MATRIZ BIG DATA + SIMULADOR DE CHOQUE + BÓVEDA PRIVADA ADMIN
    # -------------------------------------------------------------------------
    with sec_matriz:
        col_menu_m, col_tabla_m = st.columns([1.25, 3.75])

        with col_menu_m:
            st.markdown("##### 🌐 Filtros de Matriz")
            nombres_ligas = [l["id"] for l in LIGAS_BIG_DATA]
            liga_sel_matriz = st.selectbox("Filtrar por Liga:", ["🌍 Todas las 20 Ligas"] + nombres_ligas)
            busq_club_raw = st.text_input("🔍 Buscar Club en Matriz...", "", placeholder="Ej. Barcelona, Toluca, Inter Miami...")

            if st.button("🔄 Sincronizar APIs y Refrescar", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

            modo_admin_buscador = (busq_club_raw.strip() == "MR2026")
            busq_club = "" if modo_admin_buscador else busq_club_raw

            with st.expander("🔐 Bóveda Privada (Admin)", expanded=modo_admin_buscador or st.session_state["admin_autenticado"]):
                pin_admin = st.text_input("Clave de Dueño:", type="password", key="pin_admin_input")
                if pin_admin == "MR2026" or modo_admin_buscador:
                    st.session_state["admin_autenticado"] = True
                elif pin_admin != "" and pin_admin != "MR2026":
                    st.session_state["admin_autenticado"] = False

                if st.session_state["admin_autenticado"]:
                    st.success("🔓 Llave Maestra Activa: Miguel Ramirez")
                    st.caption(f"🎯 Consultas Pro hoy: **{uso_api.get('usadas', 0)} / 100** (Solo Plequita)")
                    c_adm1, c_adm2 = st.columns(2)
                    with c_adm1:
                        if st.button("🧹 Vaciar Sala VIP", use_container_width=True):
                            boveda_vip["picks_vip_hoy"] = {}
                            guardar_boveda_vip_servidor(boveda_vip)
                            st.rerun()
                    with c_adm2:
                        if st.button("🔒 Cerrar Admin", use_container_width=True):
                            st.session_state["admin_autenticado"] = False
                            st.rerun()

                    registros_ml_todos = list(boveda_ml_05.values())
                    semanas_disp = sorted(list({r.get("Semana_Jornada", etiqueta_sem_actual) for r in registros_ml_todos}), reverse=True)
                    filtro_sem_bit = st.selectbox(
                        "🗂️ Vista de Bitácora:",
                        options=["🌎 Historial Completo (Rumbo a 300)", f"📅 Jornada Actual ({etiqueta_sem_actual})"] + semanas_disp,
                        index=0
                    )
                    if filtro_sem_bit.startswith("📅"):
                        registros_ml = [r for r in registros_ml_todos if r.get("Semana_Jornada", etiqueta_sem_actual) == etiqueta_sem_actual]
                        nombre_descarga_csv = archivo_csv_sem_actual
                    elif filtro_sem_bit.startswith("🌎"):
                        registros_ml = registros_ml_todos
                        nombre_descarga_csv = f"Bitacora_Completa_Over05_{str_hoy}.csv"
                    else:
                        registros_ml = [r for r in registros_ml_todos if r.get("Semana_Jornada", etiqueta_sem_actual) == filtro_sem_bit]
                        nombre_descarga_csv = f"Bitacora_VIP_{filtro_sem_bit}.csv"

                    ganadas_ml = sum(1 for r in registros_ml if "GANADA" in str(r.get("Estado_Apuesta_05", "")))
                    fallos_ml = sum(1 for r in registros_ml if "FALLO" in str(r.get("Estado_Apuesta_05", "")))
                    efec_global_bit = round((ganadas_ml / max(1, ganadas_ml + fallos_ml)) * 100, 1)
                    st.metric("🎯 Efectividad Bitácora", f"{ganadas_ml}V / {fallos_ml}R ({efec_global_bit}%)")
                    st.caption(f"🧠 Total en Cerebro: **{len(registros_ml_todos)} / 300**")

                    df_ml_privado = pd.DataFrame(registros_ml)
                    st.download_button(
                        label=f"📥 Descargar Bitácora ({len(registros_ml)} reg)",
                        data=df_ml_privado.to_csv(index=False).encode("utf-8-sig"),
                        file_name=nombre_descarga_csv,
                        mime="text/csv",
                        use_container_width=True
                    )
                    clave_gmail = st.text_input("Clave de Aplicación Gmail:", type="password")
                    if st.button("✉️ Enviar Bitácora a mi Correo", use_container_width=True) and clave_gmail:
                        try:
                            enviar_bitacora_por_correo_privado(df_ml_privado, clave_gmail)
                            st.success("✅ Enviado a angelramirezzmiguel2@gmail.com")
                        except Exception as e:
                            st.error(f"Error SMTP: {e}")

        with col_tabla_m:
            st.subheader("🌐 Matriz Global de Clubes — Ataque y Vulnerabilidad (Últimas 2-3 Fechas)")
            st.caption("Cruza los últimos 2 a 3 partidos recolectados por API y Bitácora contra el promedio de temporada para detectar quién trae Pólvora Real y qué defensa es un colador ahorita mismo.")

            mapa_code_a_liga = {l["code"]: l["id"] for l in LIGAS_BIG_DATA}
            clubes_unicos = {}
            for k_eq, info_st in stats_temporada_api.items():
                nom_of = info_st.get("nombre_oficial", k_eq.title())
                if nom_of not in clubes_unicos:
                    clubes_unicos[nom_of] = {
                        "liga": mapa_code_a_liga.get(info_st.get("code_liga", ""), "🌍 Liga Oficial"),
                        "gf_temp": info_st.get("gf_prom", 1.35),
                        "gc_temp": info_st.get("gc_prom", 1.25),
                        "rank": info_st.get("rank", 10)
                    }
            for club_m, lista_m in matriz_clubes_global.items():
                if club_m not in clubes_unicos and lista_m:
                    clubes_unicos[club_m] = {
                        "liga": lista_m[-1].get("liga", "🌍 Liga Oficial"),
                        "gf_temp": round(sum(x.get("gf", 1.4) for x in lista_m) / len(lista_m), 2),
                        "gc_temp": round(sum(x.get("gc", 1.2) for x in lista_m) / len(lista_m), 2),
                        "rank": 8
                    }

            filas_matriz = []
            for nom_club, meta_c in clubes_unicos.items():
                if liga_sel_matriz != "🌍 Todas las 20 Ligas" and meta_c["liga"] != liga_sel_matriz:
                    continue
                if busq_club and busq_club.lower() not in nom_club.lower():
                    continue
                perf = obtener_perfil_reciente_2_3_fechas(nom_club, stats_temporada_api)
                indice_asedio = round((perf["arco_f"] * 0.45) + (perf["disp_f"] * 0.12) + (perf["arco_c"] * 0.35), 2)
                if perf["disp_f"] >= 11.0 or perf["arco_f"] >= 4.5:
                    estado_m = "🔥 Pólvora Encendida"
                elif perf["disp_c"] >= 12.0 or perf["arco_c"] >= 4.8:
                    estado_m = "🧀 Defensa Vulnerable"
                elif perf["disp_f"] >= 8.5:
                    estado_m = "⚡ Ritmo Firme"
                else:
                    estado_m = "❄️ Ritmo Bajo"

                filas_matriz.append({
                    "Liga": meta_c["liga"],
                    "Club": nom_club,
                    "Muestra": f"{perf['n_juegos']}J ({perf['origen']})",
                    "🎯 Disp. Ataque (2-3J)": perf["disp_f"],
                    "🥅 Arco Ataque (2-3J)": perf["arco_f"],
                    "⚽ GF Reciente": perf["gf_rec"],
                    "🧀 Disp. Concedidos (Vuln)": perf["disp_c"],
                    "🚨 Arco Concedido (Vuln)": perf["arco_c"],
                    "🥅 GC Reciente": perf["gc_rec"],
                    "📊 GF/GC Temp": f"{meta_c['gf_temp']} / {meta_c['gc_temp']}",
                    "🔥 Efectividad 1.5 (2-3J)": f"{perf['tasa_o15']}%",
                    "Diagnóstico": estado_m,
                    "_orden": indice_asedio
                })

            if filas_matriz:
                filas_matriz.sort(key=lambda x: -x["_orden"])
                df_mat_vista = pd.DataFrame([{k: v for k, v in r.items() if k != "_orden"} for r in filas_matriz])
                st.dataframe(df_mat_vista, use_container_width=True, hide_index=True)
            else:
                st.info("No se encontraron clubes con ese filtro.")

            with st.expander("🔬 Simulador de Choque Directo (Comparar Local vs Visita en Caliente)", expanded=False):
                lista_nombres_sim = sorted(list(clubes_unicos.keys()))
                if len(lista_nombres_sim) >= 2:
                    c_sim1, c_sim2 = st.columns(2)
                    with c_sim1:
                        eq_sim_l = st.selectbox("Equipo Local:", lista_nombres_sim, index=0)
                    with c_sim2:
                        eq_sim_v = st.selectbox("Equipo Visitante:", lista_nombres_sim, index=min(1, len(lista_nombres_sim) - 1))
                    trin_sim = calcular_trinidad_completa_pre(eq_sim_l, eq_sim_v, stats_temporada_api)
                    s1, s2, s3, s4 = st.columns(4)
                    s1.metric("📊 Prob. General (Temp)", f"{trin_sim['prob_general']}%", f"xG {trin_sim['xg_general']}")
                    s2.metric("🔥 Prob. Momento (2-3J)", f"{trin_sim['prob_momento']}%", f"xG {trin_sim['xg_momento']}")
                    s3.metric("🎯 Efectividad Cruce", f"{trin_sim['efectividad_pct']}%", "Histórico + 2-3J")
                    s4.metric("⚡ DECISIÓN EN CALIENTE", f"{trin_sim['prob_final']}%", f"Cuota Justa {trin_sim['cuota_justa']}")
                    st.info(f"**Radiografía del Choque:** {trin_sim['fuente_tag']}")

    # -------------------------------------------------------------------------
    # SECCIÓN 2: PRE-APUESTAS OVER 1.5 CON LA TRINIDAD COMPLETA
    # -------------------------------------------------------------------------
    with sec_apuestas:
        st.subheader("🎯 Laboratorio Pre-Apuesta Over 1.5 — Trinidad (General + Momento 2-3J + Efectividad)")
        st.caption("Prioriza siempre la **Probabilidad de Momento (últimas 2-3 fechas)** junto con la **Efectividad** y la **Probabilidad General** para evitar partidos de relleno.")

        col_f1, col_f2 = st.columns([2.5, 1.5])
        with col_f1:
            opciones_ligas_pre = [l["id"] for l in LIGAS_BIG_DATA]
            ligas_seleccionadas_pre = st.multiselect("Ligas a auditar:", options=opciones_ligas_pre, default=opciones_ligas_pre)
        with col_f2:
            umbral_minimo = st.slider("Umbral Mínimo Decisión en Caliente (%):", min_value=58, max_value=86, value=75, step=1)

        reporte_pre = []
        candidatos_pre_no_jugados = []

        for nombre_liga, contenido in datos_globales.items():
            if nombre_liga not in ligas_seleccionadas_pre:
                continue
            for evento in contenido["eventos"]:
                ev_id = str(evento.get("id"))
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

                    trin = calcular_trinidad_completa_pre(nom_local, nom_visita, stats_temporada_api)
                    prob_gen = trin["prob_general"]
                    prob_mom = trin["prob_momento"]
                    efec_cruce = trin["efectividad_pct"]
                    prob_final = trin["prob_final"]
                    cuota_justa = trin["cuota_justa"]
                    xg_base = trin["xg_base"]
                    fuente_tag = trin["fuente_tag"]

                    tasa_1t, tasa_2t, tasa_38_45 = calcular_tasas_tiempos_y_franja(xg_base, 0, 0, 0, 0)

                    if prob_final >= umbral_minimo:
                        if prob_mom >= 80.0 and efec_cruce >= 80.0:
                            veredicto = "🔥 ENTRAR OVER 1.5 (Pólvora Caliente 2-3J + Alta Efectividad / Stake 3%)"
                        elif prob_final >= 75.5:
                            veredicto = "🟢 ENTRAR OVER 1.5 (Zona Verde Alta Probabilidad / Stake 2.5%)"
                        elif 70.0 <= prob_final < 75.5:
                            veredicto = "💎 VALOR MODERADO (Preferible Cazar Over 0.5 en Vivo con 6+ Disp)"
                        else:
                            veredicto = "🔴 ZONA ROJA (<70%): Operar solo en Vivo si supera 6+ Disparos"

                        reporte_pre.append({
                            "Fecha": fecha_legible,
                            "Liga": nombre_liga,
                            "Partido": f"{nom_local} vs {nom_visita}",
                            "xG": xg_base,
                            "📊 Prob. General": f"{prob_gen}%",
                            "🔥 Prob. Momento (2-3J)": f"{prob_mom}%",
                            "🎯 Efectividad": f"{efec_cruce}%",
                            "⚡ Prob. Caliente (Final)": f"{prob_final}%",
                            "⏱️ Gol 1T": f"{tasa_1t}%",
                            "⚡ Cierre 38'-45'": f"{tasa_38_45}%",
                            "🔥 Gol 2T": f"{tasa_2t}%",
                            "Cuota Justa": cuota_justa,
                            "Ataque y Vulnerabilidad (2-3J) + Bitácora": fuente_tag,
                            "Veredicto": veredicto,
                            "_orden": prob_final
                        })

                        if prob_final >= 75.0:
                            candidatos_pre_no_jugados.append({
                                "ev_id": ev_id, "nom_local": nom_local, "nom_visita": nom_visita,
                                "nombre_liga": nombre_liga, "fecha_ev_local": fecha_ev_local,
                                "iso_fecha": evento.get("date", ""), "prob_final": prob_final,
                                "xg_base": xg_base,
                                "label": f"{nom_local} vs {nom_visita} (Caliente: {prob_final}% | Mom: {prob_mom}% | {fecha_legible})"
                            })

        if reporte_pre:
            reporte_pre.sort(key=lambda x: -x["_orden"])
            df_pre = pd.DataFrame([{k: v for k, v in r.items() if k != "_orden"} for r in reporte_pre])
            st.dataframe(df_pre, use_container_width=True, hide_index=True)

            col_rep1, col_rep2 = st.columns(2)
            with col_rep1:
                html_boletin_pre = generar_boletin_html_imprimible(
                    df_pre, "REPORTE PRE-APUESTAS OVER 1.5 (GENERAL + MOMENTO 2-3J + EFECTIVIDAD)",
                    f"Filtro >= {umbral_minimo}% | Prioridad Momento Caliente"
                )
                st.download_button(
                    label="📄 Descargar Boletín Pre-Partido (Imprimible / Guardar PDF)",
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
            st.info("No hay partidos por iniciar que cumplan el filtro actual. Puedes bajar el deslizador de porcentaje.")

    # -------------------------------------------------------------------------
    # SECCIÓN 3: TERMINAL EN VIVO 0.5 (DECISIONES EN CALIENTE + PLEQUITA VIP)
    # -------------------------------------------------------------------------
    with sec_scraping:
        st.markdown("### 🚨 3. TERMINAL EN VIVO 0.5 — Decisiones en Caliente")
        st.markdown(
            "**Regla de Oro de la Bitácora (84 Juegos):** Con **6+ Disparos Totales** o **3+ Tiros al Arco** en vivo, tu efectividad real es del **96.8% de Verdes**. "
            "Los partidos **`0 - 0`** con mayor ritmo y Probabilidad de Momento están fijos arriba."
        )

        if st.session_state.get("aviso_vip_bloqueado"):
            st.warning(st.session_state["aviso_vip_bloqueado"])

        tabla_scraping = []
        for nombre_liga, contenido in datos_globales.items():
            for evento in contenido["eventos"]:
                ev_id = str(evento.get("id"))
                fecha_ev_local, _, _, _ = obtener_fecha_local_evento(evento.get("date", ""))
                comp = evento.get("competitions", [{}])[0]
                st_state, es_ht, min_num, _, reloj_txt = detectar_estado_partido(comp, evento.get("date", ""))
                if st_state != "in" and not es_ht:
                    continue
                competitors = comp.get("competitors", [])
                if len(competitors) == 2:
                    loc, vis = competitors[0], competitors[1]
                    nom_l_full, nom_v_full = loc.get("team", {}).get("displayName", "Local"), vis.get("team", {}).get("displayName", "Visita")
                    nom_l, nom_v = loc.get("team", {}).get("shortDisplayName", nom_l_full), vis.get("team", {}).get("shortDisplayName", nom_v_full)
                    nombre_cruce = f"{nom_l} vs {nom_v}"
                    goles_l, goles_v = int(loc.get("score", 0) or 0), int(vis.get("score", 0) or 0)
                    goles_tot = goles_l + goles_v

                    trin_v = calcular_trinidad_completa_pre(nom_l_full, nom_v_full, stats_temporada_api)
                    prob_pre = trin_v["prob_final"]
                    prob_mom_v = trin_v["prob_momento"]
                    efec_v = trin_v["efectividad_pct"]
                    xg_pre = trin_v["xg_base"]
                    _, _, txt_bit_vivo, _ = calcular_momentum_bitacora_2_fechas(nom_l_full, nom_v_full)

                    stats_raw = extraer_metricas_partido_reales(loc, vis)
                    sello_val, _, stats, st_f2_match = cruzar_validacion_doble_fuente(nom_l_full, nom_v_full, stats_raw, lista_segunda_fuente)
                    toth_l, toth_v, toth_tot = stats["toth_l"], stats["toth_v"], stats["toth_tot"]
                    tmeta_l, tmeta_v, tmeta_tot = stats["tmeta_l"], stats["tmeta_v"], stats["tmeta_tot"]
                    esq_l, esq_v, esq_tot = stats["esquinas_l"], stats["esquinas_v"], stats["esquinas_tot"]
                    pos_l, pos_v = stats["pos_l"], stats["pos_v"]

                    max_disp_equipo = max(toth_l, toth_v)
                    equipo_dominante = nom_l if toth_l >= toth_v else nom_v
                    tasa_1t, tasa_2t, tasa_38_45 = calcular_tasas_tiempos_y_franja(xg_pre, toth_tot, tmeta_tot, esq_tot, min_num)

                    clase_caja_veredicto = "veredicto-box-wait"
                    es_oportunidad_caliente = False
                    nota_aprendizaje = f" | {txt_bit_vivo}" if "Sin " not in txt_bit_vivo else ""

                    if goles_tot == 0:
                        if min_num < 18 and not es_ht:
                            veredicto_vivo = (
                                f"⏳ Min {min_num}' ({toth_tot} Disp, {tmeta_tot} Arco, {esq_tot} Córn) | "
                                f"Mom 2-3J: {prob_mom_v}% | Efec: {efec_v}% | Esperar min 18+ para confirmar asedio real{nota_aprendizaje}."
                            )
                        else:
                            cumple_gatillo_vivo = evaluar_gatillo_quirurgico_05(prob_pre, toth_tot, max_disp_equipo, tmeta_tot, min_num, tasa_38_45)
                            if cumple_gatillo_vivo:
                                es_oportunidad_caliente = True
                                clase_caja_veredicto = "veredicto-box-hot"
                                tag_96 = "🔥 [PATRÓN 96.8% VERDE: 6+ DISP / 3+ ARCO]" if (toth_tot >= 6 or tmeta_tot >= 3) else "⚡ [GATILLO ACTIVO]"
                                veredicto_vivo = (
                                    f"🚨 ¡ENTRAR OVER 0.5 GOLES! {tag_96} {equipo_dominante} lidera con {max_disp_equipo} disp "
                                    f"(Tot: {toth_tot} Disp, {tmeta_tot} Arco, {esq_tot} Córn) 👉 Mom 2-3J: {prob_mom_v}% | Cierre 1T: {tasa_38_45}% | 2T: {tasa_2t}%{nota_aprendizaje}."
                                )
                            else:
                                veredicto_vivo = (
                                    f"⏸️ AGUANTAR ({toth_tot} Disp, {tmeta_tot} Arco, {esq_tot} Córn) | "
                                    f"Exigir 6+ Disparos o 2+ Tiros al Arco para disparar con seguridad (96.8% WR) | Tasa 2T: {tasa_2t}%{nota_aprendizaje}."
                                )
                    elif goles_tot == 1:
                        if min_num <= 82 and (toth_tot >= 6 or tmeta_tot >= 3):
                            clase_caja_veredicto = "veredicto-box-hot"
                            veredicto_vivo = f"🔥 ¡OVER 0.5 COBRADO! Oportunidad en OVER 1.5 GOLES ({toth_tot} Disp, {tmeta_tot} Arco | Mom 2-3J: {prob_mom_v}% | Tasa 2T: {tasa_2t}%){nota_aprendizaje}."
                        else:
                            clase_caja_veredicto = "veredicto-box-green"
                            veredicto_vivo = f"✅ ¡OVER 0.5 YA COBRADO EN VERDE ({goles_l}-{goles_v})! ({toth_tot} Disp | Potencial 2T: {tasa_2t}%){nota_aprendizaje}."
                    else:
                        clase_caja_veredicto = "veredicto-box-green"
                        veredicto_vivo = f"✅ ¡LÍNEAS OVER 0.5 Y OVER 1.5 COBRADAS EN VERDE! ({goles_l}-{goles_v})"

                    tabla_scraping.append({
                        "_ev_id": ev_id, "_nom_l_full": nom_l_full, "_nom_v_full": nom_v_full,
                        "_fecha_ev_local": fecha_ev_local, "_iso_fecha": evento.get("date", ""),
                        "_xg_pre": xg_pre, "_stats_dict": stats, "_st_f2": st_f2_match,
                        "_goles_tot": goles_tot, "_es_caliente": 0 if es_oportunidad_caliente else 1,
                        "_prob_pre": prob_pre, "Reloj": reloj_txt, "Liga": nombre_liga,
                        "Partido": nombre_cruce, "Marcador": f"{goles_l} - {goles_v}",
                        "📊 General / 🔥 Mom": f"{trin_v['prob_general']}% / {prob_mom_v}%",
                        "🎯 Efectividad": f"{efec_v}%",
                        "⚡ Caliente Pre": f"{prob_pre}% (xG {xg_pre})",
                        "⏱️ 1T / 38'-45' / 2T": f"{tasa_1t}% / {tasa_38_45}% / {tasa_2t}%",
                        "🎯 Disparos": f"{toth_l}-{toth_v} (Tot: {toth_tot})",
                        "🥅 Al Arco": f"{tmeta_l}-{tmeta_v} (Tot: {tmeta_tot})",
                        "🚩 Córn | Pos": f"{esq_l}-{esq_v} | {pos_l}%-{pos_v}%",
                        "🛡️ Auditoría MRFUTBOL": sello_val,
                        "💡 Veredicto Táctico": veredicto_vivo,
                        "_clase_caja": clase_caja_veredicto, "_card_hot": es_oportunidad_caliente
                    })

        if tabla_scraping:
            tabla_scraping.sort(key=lambda x: (x["_goles_tot"], x["_es_caliente"], -x["_prob_pre"]))
            for item in tabla_scraping:
                ev_id_scr = item["_ev_id"]
                ya_en_vip = ev_id_scr in boveda_vip.get("picks_vip_hoy", {})
                card_cls = "trading-card-hot" if item["_card_hot"] else "trading-card"
                col_scr_card, col_scr_plequita = st.columns([10.2, 1.8])
                with col_scr_card:
                    st.markdown(f"""
                    <div class="{card_cls}">
                        <div class="trading-header">
                            <div>
                                <span style="background:#ff2a4b; color:#fff; padding:3px 8px; border-radius:4px; font-weight:800; font-size:12px;">{item['Reloj']}</span>
                                &nbsp; <strong style="font-size:15px; color:#ffffff;">{item['Partido']}</strong>
                                &nbsp; <span style="background:#16181f; color:#00ffcc; padding:3px 10px; border-radius:4px; font-weight:900; font-size:14px; border:1px solid #00ffcc;">{item['Marcador']}</span>
                            </div>
                            <div style="font-size:12px; color:#9ba1b0;">{item['Liga']} &nbsp;|&nbsp; {item['🛡️ Auditoría MRFUTBOL']}</div>
                        </div>
                        <div class="trading-metrics-grid">
                            <div class="metric-pill"><span>📊 Gen / 🔥 Mom (2-3J)</span><strong>{item['📊 General / 🔥 Mom']}</strong></div>
                            <div class="metric-pill"><span>🎯 Efectividad</span><strong>{item['🎯 Efectividad']}</strong></div>
                            <div class="metric-pill"><span>⚡ Prob. Caliente</span><strong>{item['⚡ Caliente Pre']}</strong></div>
                            <div class="metric-pill"><span>⏱️ 1T / 38-45' / 2T</span><strong>{item['⏱️ 1T / 38\'-45\' / 2T']}</strong></div>
                            <div class="metric-pill"><span>🎯 Disparos (L-V)</span><strong>{item['🎯 Disparos']}</strong></div>
                            <div class="metric-pill"><span>🥅 Tiros al Arco</span><strong>{item['🥅 Al Arco']}</strong></div>
                            <div class="metric-pill"><span>🚩 Córn | Posesión</span><strong>{item['🚩 Córn | Pos']}</strong></div>
                        </div>
                        <div class="{item['_clase_caja']}">{item['💡 Veredicto Táctico']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_scr_plequita:
                    st.markdown("<div style='margin-top:18px;'></div>", unsafe_allow_html=True)
                    st.checkbox(
                        "☑️ Enviar a Sala VIP", value=ya_en_vip, key=f"plequita_vip_{ev_id_scr}_{ya_en_vip}",
                        on_change=accionar_plequita_vip,
                        args=(ev_id_scr, item["_nom_l_full"], item["_nom_v_full"], item["Liga"], item["_fecha_ev_local"], item["_prob_pre"], item["_xg_pre"], item["_stats_dict"], stats_temporada_api, item["_iso_fecha"], "⚡ Plequita Scraping en Vivo", item["_st_f2"], item["_goles_tot"])
                    )
                    if ya_en_vip:
                        st.caption("👑 **En Sala VIP**")

            df_scr = pd.DataFrame([{k: v for k, v in fila.items() if not k.startswith("_")} for fila in tabla_scraping])
            with st.expander("📋 Ver Tabla Completa y Descargar Reporte en Vivo", expanded=False):
                st.dataframe(df_scr, use_container_width=True, hide_index=True)
                st.download_button("("📊 Exportar Señales en Vivo (.CSV)", data=df_scr.to_csv(index=False).encode("utf-8-sig"), file_name=f"Senales_EnVivo_MRFUTBOL_{str_hoy}.csv", mime="text/csv", use_container_width=True)
        else:
            st.info("No hay partidos en vivo en este preciso instante en las 20 ligas.")

    # -------------------------------------------------------------------------
    # SECCIÓN 4: SALA VIP MRFUTBOL [PASO_3_BIG_DATA]
    # -------------------------------------------------------------------------
    with sec_sala_vip:
        st.subheader("👑 4. Sala VIP MRFUTBOL — Radiografía Profunda [PASO_3_BIG_DATA]")
        col_vip_izq, col_vip_der = st.columns([3.05, 1.15])

        with col_vip_izq:
            if candidatos_pre_no_jugados:
                col_sel_p1, col_sel_p2 = st.columns([3, 1.5])
                with col_sel_p1:
                    mapa_cand_pre = {c["label"]: c for c in candidatos_pre_no_jugados}
                    sel_cand_lbl = st.selectbox("🎯 Agregar Partido Pre >=75% a Sala VIP:", options=list(mapa_cand_pre.keys()), label_visibility="collapsed")
                with col_sel_p2:
                    if st.button("☑️ Enviar Pre a Sala VIP", use_container_width=True):
                        c_sel = mapa_cand_pre[sel_cand_lbl]
                        accionar_plequita_vip(c_sel["ev_id"], c_sel["nom_local"], c_sel["nom_visita"], c_sel["nombre_liga"], c_sel["fecha_ev_local"], c_sel["prob_final"], c_sel["xg_base"], None, stats_temporada_api, c_sel["iso_fecha"], "🎯 Plequita Pre-Apuesta VIP")
                        st.rerun()

            if st.session_state.get("aviso_vip_bloqueado"):
                st.warning(st.session_state["aviso_vip_bloqueado"])

            lista_mostrar_vip = list(boveda_vip.get("picks_vip_hoy", {}).values())
            if lista_mostrar_vip:
                todos_terminados, partidos_pendientes, ultima_hora_cierre = True, 0, ahora_hn_dt
                filas_reporte_vip, aciertos_vip, evaluados_vip = [], 0, 0

                for item_vip in lista_mostrar_vip:
                    v_id = item_vip["ev_id"]
                    origen_vip = item_vip.get("origen", "⚡ Plequita Scraping en Vivo")
                    ficha = item_vip["ficha"]
                    est_ev = mapa_estado_partidos.get(v_id, {})
                    st_ev = est_ev.get("st_state", "pre")
                    gol_l_v, gol_v_v, goles_tot_v = est_ev.get("gol_l", 0), est_ev.get("gol_v", 0), est_ev.get("goles_tot", 0)
                    reloj_v = est_ev.get("reloj_txt", "En Curso")
                    cierre_est = est_ev.get("dt_local", ahora_hn_dt) + timedelta(hours=2)
                    if cierre_est > ultima_hora_cierre:
                        ultima_hora_cierre = cierre_est

                    es_linea_05 = ("Scraping" in origen_vip)
                    meta_goles = 1 if es_linea_05 else 2
                    mercado_nombre = "OVER 0.5 EN VIVO (Plequita)" if es_linea_05 else "OVER 1.5 GOLES (VIP)"

                    if st_ev != "post":
                        todos_terminados = False
                        partidos_pendientes += 1
                        estado_res_vip = f"✅ LÍNEA YA CUBIERTA EN VIVO ({gol_l_v}-{gol_v_v} al {reloj_v})" if goles_tot_v >= meta_goles else f"⏳ EN JUEGO / PENDIENTE ({gol_l_v}-{gol_v_v} | {reloj_v})"
                    else:
                        evaluados_vip += 1
                        if goles_tot_v >= meta_goles:
                            aciertos_vip += 1
                            estado_res_vip = f"✅ VERDE OFICIAL ({gol_l_v}-{gol_v_v} Final)"
                        else:
                            estado_res_vip = f"❌ ROJO ({gol_l_v}-{gol_v_v} Final)"

                    st.markdown(f"""
                    <div class="vip-card">
                        <div class="trading-header">
                            <div>
                                <span style="background:#ffd700; color:#000; padding:3px 8px; border-radius:4px; font-weight:900; font-size:11px;">{origen_vip}</span>
                                &nbsp; <strong style="font-size:16px; color:#ffffff;">{ficha['Partido']}</strong>
                                &nbsp; <span style="font-size:12px; color:#00ffcc; font-weight:700;">({mercado_nombre} | Prob: {ficha['Prob_Over15']})</span>
                            </div>
                            <div style="font-size:12px; color:#ffd700; font-weight:700;">{estado_res_vip}</div>
                        </div>
                        <div class="trading-metrics-grid">
                            <div class="metric-pill"><span>🎯 [PASO_3_OFENSIVO_PRO]</span><strong>{ficha['Paso3_Ofensivo_Pro']}</strong><small>{ficha['Ref_Ofensivo_Pro']}</small></div>
                            <div class="metric-pill"><span>🥩 [EFICIENCIA / CARNICERÍA]</span><strong>{ficha['Paso3_Eficiencia_Carniceria']}</strong><small>{ficha['Ref_Carniceria']}</small></div>
                            <div class="metric-pill"><span>🧀 [VULNERABILIDAD RIVAL]</span><strong>{ficha['Paso3_Vulnerabilidad_Rival']}</strong><small>{ficha['Ref_Vulnerabilidad']}</small></div>
                            <div class="metric-pill"><span>🔥 [MOMENTUM OFENSIVO]</span><strong>{ficha['Paso3_Momentum']}</strong><small>{ficha['Ref_Momentum']}</small></div>
                            <div class="metric-pill"><span>🤝 [SISTEMA COLECTIVO 10.5]</span><strong>{ficha['Paso3_Colectivo_105']}</strong><small>{ficha['Ref_Colectivo']}</small></div>
                            <div class="metric-pill"><span>🎰 [VARIANZA / DEUDA DE GOL]</span><strong>{ficha['Paso3_Varianza_Deuda']}</strong><small>{ficha['Ref_Varianza']}</small></div>
                            <div class="metric-pill"><span>🏆 [CONTEXTO TABLA / URGENCIA]</span><strong>{ficha['Paso3_Contexto_Urgencia']}</strong><small>{ficha['Ref_Urgencia']}</small></div>
                        </div>
                        <div style="font-size:11px; color:#9ba1b0;">{ficha['Liga']} &nbsp;|&nbsp; {ficha.get('Sello_API', '✅ Auditoría Exclusiva MRFUTBOL Pro')}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    filas_reporte_vip.append({
                        "Origen": origen_vip, "Liga": ficha["Liga"], "Partido": ficha["Partido"], "Mercado": mercado_nombre,
                        "Prob. Ajustada": ficha["Prob_Over15"], "Ofensivo Pro": ficha["Paso3_Ofensivo_Pro"],
                        "Calidad Tiro": ficha["Paso3_Eficiencia_Carniceria"], "Vulnerabilidad Rival": ficha["Paso3_Vulnerabilidad_Rival"],
                        "Momentum": ficha["Paso3_Momentum"], "Resultado Auditado": estado_res_vip
                    })

                df_vip_hoy = pd.DataFrame(filas_reporte_vip)
                if not todos_terminados:
                    st.warning(f"🔒 **CANDADO DE TRANSPARENCIA ACTIVO:** Faltan **{partidos_pendientes} partido(s)** por concluir.")
                else:
                    yield_pct = round((aciertos_vip / max(1, evaluados_vip)) * 100, 1)
                    st.success(f"🔓 **¡SELECCIÓN VIP CONCLUIDA!** Efectividad: **{yield_pct}% ({aciertos_vip}/{evaluados_vip} Verdes)**.")
                    st.download_button("🔓 📊 Descargar Auditoría Sala VIP (.CSV)", data=df_vip_hoy.to_csv(index=False).encode("utf-8-sig"), file_name=f"Auditoria_SalaVIP_MRFUTBOL_{str_hoy}.csv", mime="text/csv", use_container_width=True)
            else:
                st.info("Marca la plequita `☑️ Enviar a Sala VIP` en el Terminal en Vivo 0.5 o agrega un partido Pre >=75% arriba.")

        with col_vip_der:
            st.markdown("<div class='audit-box-right'><h4 style='margin:0 0 6px 0; color:#ffd700; font-size:15px;'>🗄️ Caché de Auditoría VIP</h4><p style='margin:0; font-size:11px; color:#9ba1b0;'>Memoria histórica en servidor con los reportes cerrados.</p></div>", unsafe_allow_html=True)
            for rep_hist in boveda_vip.get("historial_reportes_7d", []):
                f_rep = rep_hist.get("fecha", "")
                with st.expander(f"📅 {f_rep} | {rep_hist.get('yield_pct', 0)}% ({rep_hist.get('verdes', 0)}/{rep_hist.get('total', 0)} ✅)", expanded=False):
                    df_h = pd.DataFrame(rep_hist.get("registros", []))
                    st.dataframe(df_h, use_container_width=True, hide_index=True)

renderizar_central_mrfutbol()
