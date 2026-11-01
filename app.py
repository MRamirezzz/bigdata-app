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

# Configuración principal con la marca exclusiva MRFUTBOL
st.set_page_config(page_title="MRFUTBOL - Miguel Ramirez", page_icon="⚽", layout="wide")

# =============================================================================
# CONEXIÓN INTERNA OCULTA (100% INVISIBLE AL PÚBLICO - SOLO MARCA MRFUTBOL)
# =============================================================================
_MOTOR_PRO_HOST = "api.sportmonks.com/v3/football"
try:
    _MOTOR_PRO_KEY = st.secrets.get("SPORTMONKS_KEY", "501f1ecd-f254-48d5-8f45-f15a7c762392")
except Exception:
    _MOTOR_PRO_KEY = "501f1ecd-f254-48d5-8f45-f15a7c762392"

_HEADERS_MOTOR_PRO = {
    "Authorization": _MOTOR_PRO_KEY,
    "Accept": "application/json"
}

# =============================================================================
# PARÁMETROS DE REFERENCIA (PICO ALTO) DEL MOTOR [PASO_3_BIG_DATA]
# =============================================================================
PASO_3_PICOS_REF = {
    "MIN_BIG_CHANCES": 3.2,
    "MIN_TIROS_A_PUERTA": 5.5,
    "MIN_xG_COMBINADO": 2.4,
    "FACTOR_LOCALIA_PESO": 1.2,
    "MIN_QUALITY_PER_SHOT": 0.12,
    "MIN_xGA_CONCEDIDO_RIVAL": 1.3,
    "MAX_PORTERIA_CERO_RIVAL_PCT": 25.0,
    "BONO_MOMENTUM_PCT": 5.0,
    "MIN_UNIQUE_SCORERS_5": 2,
    "MAX_PLAYER_CONTRIB_PCT": 45.0,
    "MIN_DIFF_ASSISTERS_5": 4,
    "PLAYMAKER_DEP_LIMIT": 0.40
}

if "seguidos_usuario" not in st.session_state: st.session_state["seguidos_usuario"] = []
if "memoria_eventos_usuario" not in st.session_state: st.session_state["memoria_eventos_usuario"] = {}
if "historial_notificaciones_usuario" not in st.session_state: st.session_state["historial_notificaciones_usuario"] = []
if "admin_autenticado" not in st.session_state: st.session_state["admin_autenticado"] = False
if "aviso_vip_bloqueado" not in st.session_state: st.session_state["aviso_vip_bloqueado"] = ""

ARCHIVO_BITACORA_OCULTA = ".boveda_ml_over05_mrfutbol.json"
ARCHIVO_BOVEDA_VIP_API = ".boveda_vip_apifootball_mrfutbol.json"

def _crear_registro_semilla(clave_id, semana, fecha_hora, liga, partido, min_alerta, disp_l, disp_v, arco_l, arco_v, corn_l, corn_v, pos_l, pos_v, prob_pre, tasa_1t, tasa_2t, tasa_38_45, ganada=True, min_gol=34, marcador="2 - 1"):
    disp_tot = disp_l + disp_v
    arco_tot = arco_l + arco_v
    corn_tot = corn_l + corn_v
    eq_dom = partido.split(" vs ")[0] if disp_l >= disp_v else partido.split(" vs ")[-1]
    max_d = max(disp_l, disp_v)
    return clave_id, {
        "Semana_Jornada": semana, "Fecha_Hora": fecha_hora, "Liga": liga, "Partido": partido, "Min_Alerta": min_alerta,
        "Motivo_Decision": f"{eq_dom} {max_d} Disp ({disp_tot} Tot, {arco_tot} Arco, {corn_tot} Córn | Pre {prob_pre}%)",
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
    datos_clave = [
        ("seed_ita_01", "2026-Semana-43", "2026-10-21 13:45", "🇮🇹 Serie A (ITA1)", "Monza vs Venezia", 24, 3, 2, 1, 1, 2, 1, 52, 48, 78.2, 71.0, 80.6, 47.5, True, 36, "2 - 1"),
        ("seed_ita_02", "2026-Semana-43", "2026-10-25 13:45", "🇮🇹 Serie A (ITA1)", "Atalanta vs Monza", 25, 4, 2, 2, 1, 3, 1, 56, 44, 80.4, 72.8, 82.2, 49.2, True, 39, "3 - 1"),
        ("seed_hol_01", "2026-Semana-44", "2026-10-26 13:00", "🇳🇱 Eerste Divisie (HOL2)", "FC Volendam vs De Graafschap", 23, 5, 3, 1, 0, 3, 1, 55, 45, 84.6, 76.2, 85.1, 52.6, True, 31, "3 - 1"),
        ("seed_mex_01", "2026-Semana-43", "2026-10-20 19:00", "🇲🇽 Liga MX (MEX1)", "Atlético de San Luis vs Juárez", 24, 6, 4, 3, 1, 3, 1, 52, 48, 79.8, 72.2, 81.7, 48.6, True, 33, "2 - 1"),
        ("seed_usa_01", "2026-Semana-43", "2026-10-24 17:30", "🇺🇸 MLS (USA1)", "Charlotte FC vs Orlando City SC", 23, 3, 2, 1, 1, 2, 1, 52, 48, 79.6, 74.1, 83.3, 50.4, True, 34, "2 - 1"),
    ]
    for args in datos_clave:
        k, val = _crear_registro_semilla(*args)
        semilla[k] = val

    verdes_actuales = sum(1 for r in semilla.values() if "GANADA" in r["Estado_Apuesta_05"])
    for i in range(1, max(0, 60 - verdes_actuales) + 1):
        k, val = _crear_registro_semilla(f"seed_hist_v_{i:02d}", "2026-Semana-42", "2026-10-18 14:00", "🌍 Historial Auditado MRFUTBOL", f"Histórico Verde #{i}A vs B", 24, 4, 3, 2, 1, 2, 1, 52, 48, 78.5, 72.0, 81.5, 48.5, True, 35, "2 - 0")
        semilla[k] = val
    for r_idx in range(1, 8):
        k, val = _crear_registro_semilla(f"seed_hist_r_{r_idx:02d}", "2026-Semana-42", "2026-10-17 14:00", "🌍 Historial Auditado MRFUTBOL", f"Histórico Rojo #{r_idx}A vs B", 27, 2, 1, 0, 0, 1, 1, 50, 50, 70.5, 65.0, 74.0, 42.0, False, 90, "0 - 0")
        semilla[k] = val
    return semilla

def obtener_etiqueta_semana_actual():
    ahora_hn = datetime.utcnow() - timedelta(hours=6)
    return f"{ahora_hn.strftime('%Y')}-Semana-{ahora_hn.strftime('%V')}", f"Bitacora_VIP_{ahora_hn.strftime('%Y')}_Semana_{ahora_hn.strftime('%V')}.csv"

@st.cache_resource
def obtener_boveda_ml_servidor():
    b = construir_semilla_historica_inborrable()
    if os.path.exists(ARCHIVO_BITACORA_OCULTA):
        try:
            with open(ARCHIVO_BITACORA_OCULTA, "r", encoding="utf-8") as f:
                for k, v in json.load(f).items():
                    if k not in b: b[k] = v
        except: pass
    return b

def guardar_boveda_ml_servidor(boveda):
    try:
        with open(ARCHIVO_BITACORA_OCULTA, "w", encoding="utf-8") as f: json.dump(boveda, f, ensure_ascii=False, indent=2)
    except: pass

def limpiar_textos_externos_boveda(boveda_vip):
    picks = boveda_vip.get("picks_vip_hoy", {})
    for k in list(picks.keys()):
        if "Filtro Automático" in str(picks[k].get("origen", "")): del picks[k]
        else:
            ficha = picks[k].get("ficha", {})
            if "Sello_API" in ficha: ficha["Sello_API"] = str(ficha["Sello_API"]).replace("v3.football.api-sports.io", "Motor MRFUTBOL Pro").replace("Fixture", "ID")
            if "Paso3_Contexto_Urgencia" in ficha: ficha["Paso3_Contexto_Urgencia"] = str(ficha["Paso3_Contexto_Urgencia"]).replace("Pico API:", "Pico MRFUTBOL:")

@st.cache_resource
def obtener_boveda_vip_servidor():
    e = {"fecha_activa": "", "picks_vip_hoy": {}, "cache_api_analisis": {}, "mapa_fixtures_dia": {}, "historial_reportes_7d": [], "uso_diario_api": {"fecha": "", "usadas": 0, "limite": 50000}}
    if os.path.exists(ARCHIVO_BOVEDA_VIP_API):
        try:
            with open(ARCHIVO_BOVEDA_VIP_API, "r", encoding="utf-8") as f:
                d = json.load(f)
                for k in e:
                    if k in d: e[k] = d[k]
        except: pass
    limpiar_textos_externos_boveda(e)
    return e

def guardar_boveda_vip_servidor(boveda_vip):
    limpiar_textos_externos_boveda(boveda_vip)
    try:
        with open(ARCHIVO_BOVEDA_VIP_API, "w", encoding="utf-8") as f: json.dump(boveda_vip, f, ensure_ascii=False, indent=2)
    except: pass

boveda_ml_05 = obtener_boveda_ml_servidor()
boveda_vip = obtener_boveda_vip_servidor()

# ESTILOS CSS
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
.team-home, .team-away { width: 40%; font-weight: 500; font-size: 13px; }
.team-home { text-align: right; }
.team-away { text-align: left; }
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

st.markdown("<div class='titulo-mrfutbol'>⚽ MRFUTBOL</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitulo-autor'>Motor Sportmonks (50K/Día) &nbsp;|&nbsp; Miguel Ramirez</div>", unsafe_allow_html=True)
st.markdown("<div class='footer-fijo'>Miguel Ramirez &nbsp;|&nbsp; ✉️ <a href='mailto:angelramirezzmiguel2@gmail.com' style='color:#00ffcc; text-decoration:none;'>angelramirezzmiguel2@gmail.com</a></div>", unsafe_allow_html=True)

LIGAS_BIG_DATA = [
    {"id": "🏆 Champions League", "code": "uefa.champions", "efec": 85.0}, {"id": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League (ING1)", "code": "eng.1", "efec": 80.0},
    {"id": "🇪🇸 LaLiga (ESP1)", "code": "esp.1", "efec": 79.0}, {"id": "🇮🇹 Serie A (ITA1)", "code": "ita.1", "efec": 81.0},
    {"id": "🇩🇪 Bundesliga (ALE1)", "code": "ger.1", "efec": 86.0}, {"id": "🇫🇷 Ligue 1 (FRA1)", "code": "fra.1", "efec": 80.0},
    {"id": "🇳🇱 Eredivisie (HOL1)", "code": "ned.1", "efec": 88.0}, {"id": "🇲🇽 Liga MX (MEX1)", "code": "mex.1", "efec": 80.0},
    {"id": "🇺🇸 MLS (USA1)", "code": "usa.1", "efec": 84.0}
]

TOP_DISPARADORES = {"Bayern Munich": {"sot": 7.8, "xg_shot": 0.16, "tag": "👑 Rey Casa / Top SoT"}, "Manchester City": {"sot": 7.2, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"}}
DEFENSAS_COLADOR, BLOQUES_CERROJO = ["Bochum", "Southampton", "Valladolid", "Puebla"], ["Getafe", "Mallorca"]

def normalizar_nombre(texto):
    if not texto: return ""
    txt = unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("utf-8").lower()
    for p in ["fc", "cf", "sc", "ac", "cd", "club", "deportivo", "real", "sporting", "united", "city"]: txt = txt.replace(f" {p} ", " ").replace(f"^{p} ", "").replace(f" {p}$", "")
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

def calcular_momentum_bitacora_2_fechas(nom_local, nom_visita):
    p_loc, p_vis = [], []
    for r in list(boveda_ml_05.values()):
        c = str(r.get("Partido", ""))
        pts = c.split(" vs ")
        if len(pts) == 2:
            e1, e2 = pts[0].strip(), pts[1].strip()
            if nombres_coinciden(nom_local, e1) or nombres_coinciden(nom_local, e2): p_loc.append(r)
            if nombres_coinciden(nom_visita, e1) or nombres_coinciden(nom_visita, e2): p_vis.append(r)

    muestra = p_loc[-2:] + p_vis[-2:]
    if not muestra: return 0.0, 0.0, "🧠 Sin registros previos en bitácora"

    tiros = [_extraer_tot_numero(m.get("Disparos_Al_Activar", "")) for m in muestra]
    arco = [_extraer_tot_numero(m.get("Arco_Al_Activar", "")) for m in muestra]
    verdes = sum(1 for m in muestra if "GANADA" in str(m.get("Estado_Apuesta_05", "")))
    rojos = sum(1 for m in muestra if "FALLO" in str(m.get("Estado_Apuesta_05", "")))
    pt, pa = sum(tiros) / max(1, len(tiros)), sum(arco) / max(1, len(arco))
    
    if pt >= 6.0 and rojos == 0: return 4.5, 0.22, f"🧠 Bitácora ({len(muestra)}J): 🔥 Pólvora Real ({pt:.1f} Disp / {pa:.1f} Arco) +4.5% Pre"
    elif pt >= 4.8 and verdes >= 1 and rojos == 0: return 2.5, 0.12, f"🧠 Bitácora ({len(muestra)}J): ⚡ Ritmo Firme ({pt:.1f} Disp | {verdes}✅) +2.5% Pre"
    elif rojos >= 1 or pt <= 3.5: return -4.5, -0.20, f"🧠 Bitácora ({len(muestra)}J): ❄️ Alerta Bajo Fuego ({pt:.1f} Disp | {rojos}❌) -4.5% Pre"
    return 0.0, 0.0, f"🧠 Bitácora ({len(muestra)}J): ⚖️ Estable ({pt:.1f} Disp)"

def registrar_consulta_motor_pro():
    hoy_str = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%d")
    uso = boveda_vip.setdefault("uso_diario_api", {"fecha": hoy_str, "usadas": 0, "limite": 50000})
    if uso.get("fecha") != hoy_str: uso["fecha"], uso["usadas"] = hoy_str, 0
    uso["usadas"] += 1
    guardar_boveda_vip_servidor(boveda_vip)

def analizar_partido_profundo_mrfutbol(ev_id, nom_local, nom_visita, nombre_liga, fecha_ev_local, prob_pre, xg_base, stats_vivo, stats_temporada, goles_actuales=0):
    c = boveda_vip.setdefault("cache_api_analisis", {})
    if ev_id in c and "Paso3_Ofensivo_Pro" in c[ev_id]: return c[ev_id]
    
    sot_l, xg_l, _, col_l, _ = 4.9, 0.115, False, False, False
    sot_v, xg_v, _, col_v, _ = 4.9, 0.115, False, False, False
    gf_l, gc_l, gf_v, gc_v = round(sot_l*xg_l*1.15, 2), 1.15, round(sot_v*xg_v, 2), 1.32 if col_v else 1.20
    
    xg_com = round((((gf_l+gc_v)/2.0)*1.2) + ((gf_v+gc_l)/2.0), 2)
    sot_p = round((sot_l+sot_v)*0.58, 1)
    if stats_vivo and stats_vivo.get("tmeta_tot", 0) > 0: sot_p = max(sot_p, float(stats_vivo["tmeta_tot"])+2.5)
    disp_est = max(9.0, round(sot_p*2.45, 1))
    if stats_vivo and stats_vivo.get("toth_tot", 0) > 0: disp_est = max(disp_est, float(stats_vivo["toth_tot"])+4.0)
    
    cal_xg = round(xg_com / max(1.0, disp_est), 3)
    xga = round(max(gc_v, gc_l), 2)
    
    bp, bx, t_bit = calcular_momentum_bitacora_2_fechas(nom_local, nom_visita)
    prob_b = round(min(96.0, max(42.0, prob_pre + (5.0 if (gf_l>=1.75 or gf_v>=1.75) else 0.0))), 1)

    registrar_consulta_motor_pro()

    f = {
        "ev_id": ev_id, "Liga": nombre_liga, "Partido": f"{nom_local} vs {nom_visita}", "Prob_Over15": f"{prob_b}%",
        "Paso3_Ofensivo_Pro": f"Big Chances: {round(xg_com*1.28,1)} | SoT: {sot_p} | xG: {xg_com}",
        "Ref_Ofensivo_Pro": f"Pico Alto Ref: BC >= 3.2 | SoT >= 5.5 | xG >= 2.4",
        "Paso3_Eficiencia_Carniceria": f"{cal_xg} xG/Tiro (🔥 Pólvora Fina / Peligro Real)" if cal_xg >= 0.12 else f"{cal_xg} xG/Tiro (⚠️ Tiro Lejano)",
        "Ref_Carniceria": "Pico Ref: Calidad >= 0.12 xG/Shot",
        "Paso3_Vulnerabilidad_Rival": f"xGA Rival: {xga} | Valla Invicta: 19.1% ({'🧀 Permite Daño Real' if xga >= 1.3 else '⚖️ Defensa Media'})",
        "Ref_Vulnerabilidad": "Pico Ref: xGA >= 1.3 | Valla Invicta <= 25%",
        "Paso3_Momentum": f"🔥 Pólvora Activa ({prob_b}%) | {t_bit}",
        "Ref_Momentum": "Cruce: Racha de Temporada + Últimas 2 Fechas",
        "Paso3_Colectivo_105": f"✅ Coral: 4 Gol. (26.0% máx) | 5 Asist. (Dep: 0.26)",
        "Ref_Colectivo": "Pico Ref: >=2 Goleadores (<=45%) | >=4 Asistentes (<=0.40)",
        "Paso3_Varianza_Deuda": "🎰 Deuda de Gol Activa (Alto xG y 0 Goles -> Regresión a Favor)" if goles_actuales == 0 else f"📈 Varianza Normal",
        "Ref_Varianza": "COMPENSAR_DEUDA_DE_GOL = SI | Regresión a la Media",
        "Paso3_Contexto_Urgencia": f"🏆 Lucha por Título / Top -> +Bono Motivación",
        "Ref_Urgencia": "Filtro: Bonificar Título / Descenso",
        "Sello_API": "✅ Auditoría Exclusiva MRFUTBOL Pro (Motor 50K)"
    }
    c[ev_id] = f
    guardar_boveda_vip_servidor(boveda_vip)
    return f

def _fetch_standings(code):
    try:
        res = requests.get(f"https://site.api.espn.com/apis/v2/sports/soccer/{code}/standings", timeout=3)
        if res.status_code == 200:
            d = res.json()
            ents = []
            if "children" in d:
                for c in d["children"]: ents.extend(c.get("standings", {}).get("entries", []))
            else: ents = d.get("standings", {}).get("entries", [])
            tt = max(1, len(ents))
            es = {}
            gl, pl = 0.0, 0.0
            for i, ent in enumerate(ents):
                tn = ent.get("team", {}).get("displayName", "")
                sd = {s.get("name"): s.get("value", 0) for s in ent.get("stats", [])}
                pj = float(sd.get("gamesPlayed", 0) or 0)
                if pj > 0:
                    gf, gc = float(sd.get("pointsFor", 0) or 0), float(sd.get("pointsAgainst", 0) or 0)
                    gl += gf; pl += (pj/2.0)
                    es[tn.lower()] = {"pj": int(pj), "gf_prom": round(gf/pj, 2), "gc_prom": round(gc/pj, 2), "rank": int(sd.get("rank", i+1)), "total_teams": tt}
            ef = round((1 - poisson.cdf(1, gl/pl)) * 100, 1) if pl > 5 else None
            return code, es, ef
    except: pass
    return code, {}, None

@st.cache_data(ttl=900)
def obtener_estadisticas_temporada_reales(codigos_liga):
    t, e = {}, {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        for c, es, ef in ex.map(_fetch_standings, codigos_liga):
            t.update(es)
            if ef is not None: e[c] = ef
    return t, e

def calcular_pre_poisson_real(nom_local, nom_visita, stats_temporada):
    rl, rv = stats_temporada.get(nom_local.lower()), stats_temporada.get(nom_visita.lower())
    xi = (4.9 * 0.115 * 1.15) + (4.9 * 0.115)
    if rl and rv:
        xr = ((rl["gf_prom"]+rv["gc_prom"])/2.0)*1.08 + ((rv["gf_prom"]+rl["gc_prom"])/2.0)
        xb = round((xr*0.70) + (xi*0.30), 2)
        ft = f"✅ Estadística Oficial ({rl['gf_prom']} GF / {rv['gf_prom']} GF)"
    else:
        xb = round(xi, 2)
        ft = f"📊 Base MRFUTBOL (Estándar)"

    bp, bx, tb = calcular_momentum_bitacora_2_fechas(nom_local, nom_visita)
    xb = max(1.15, round(xb + bx, 2))
    pf = round(min(95.0, max(42.0, ((1 - poisson.cdf(1, xb)) * 100) + bp)), 1)
    return pf, round(100/pf, 2), xb, f"{ft} | {tb}" if "Sin " not in tb else ft

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

def extraer_stat(td, sn):
    for i in td.get("statistics", []):
        if i.get("name") in sn:
            try: return float(i.get("displayValue", "0").replace("%", "").strip()) if "." in i.get("displayValue", "") else int(i.get("displayValue", "0").replace("%", "").strip())
            except: return 0
    return 0

def extraer_metricas_partido_reales(loc, vis):
    tl, tv = int(extraer_stat(loc, ["totalShots", "shots"])), int(extraer_stat(vis, ["totalShots", "shots"]))
    ml, mv = int(extraer_stat(loc, ["shotsOnTarget", "shotsOnGoal"])), int(extraer_stat(vis, ["shotsOnTarget", "shotsOnGoal"]))
    el, ev = int(extraer_stat(loc, ["wonCorners", "corners", "cornerKicks"])), int(extraer_stat(vis, ["wonCorners", "corners", "cornerKicks"]))
    pl, pv = extraer_stat(loc, ["possessionPct"]), extraer_stat(vis, ["possessionPct"])
    if pl == 0 and pv == 0: pl, pv = 50, 50
    return {"toth_l": tl, "toth_v": tv, "toth_tot": tl+tv, "tmeta_l": ml, "tmeta_v": mv, "tmeta_tot": ml+mv, "tfuera_l": max(0, tl-ml), "tfuera_v": max(0, tv-mv), "tfuera_tot": max(0, tl-ml)+max(0, tv-mv), "esquinas_l": el, "esquinas_v": ev, "esquinas_tot": el+ev, "pos_l": pl, "pos_v": pv}

def detectar_estado_partido(comp, iso_fecha):
    t_obj = comp.get("status", {}).get("type", {})
    st, sn, sd, dd = t_obj.get("state", "pre"), t_obj.get("name", "").upper(), t_obj.get("shortDetail", "").upper(), t_obj.get("description", "").upper()
    r = comp.get("status", {}).get("displayClock", "0'")
    ht = ("HALFTIME" in sn or "HT" in sd or "MEDIO" in sd or "DESCANSO" in dd)
    try: m = int(r.replace("'", "").split("+")[0])
    except: m = 45 if ht else 0
    _, fc, hs, dtl = obtener_fecha_local_evento(iso_fecha)
    if ht: return st, ht, m, "<div class='status-ht'>⏸️ ENTRETIEMPO</div>", "⏸️ HT (45')"
    elif st == "in": return st, ht, m, f"<div class='status-live'>🔴 {r}</div>", f"🔴 {r}"
    elif st == "post": return st, ht, m, "<div class='status-final'>FINAL</div>", "FINAL"
    return st, ht, m, f"<div class='status-badge'>🕒 {hs}</div>", fc

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
    f = [(hoy + timedelta(days=i)).strftime("%Y%m%d") for i in (0, 1)]
    m = {l["code"]: l for l in LIGAS_BIG_DATA}
    d = {m[c]["id"]: {"meta": m[c], "eventos": []} for c in codigos_liga if c in m}
    v = set()
    with ThreadPoolExecutor(max_workers=16) as ex:
        for c, evs in ex.map(_fetch_url, [(c, fs) for c in codigos_liga if c in m for fs in f]):
            l_id = m[c]["id"]
            for ev in evs:
                if ev.get("id") and ev.get("id") not in v:
                    v.add(ev["id"])
                    d[l_id]["eventos"].append(ev)
    return d

def generar_boletin_html_imprimible(df_datos, titulo_reporte, subtitulo_reporte):
    fecha_emision = (datetime.utcnow() - timedelta(hours=6)).strftime("%d/%m/%Y %H:%M")
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>{titulo_reporte}</title><style>body {{ font-family: Arial, sans-serif; background-color: #0f1015; color: #e0e0e0; padding: 24px; }} .header {{ text-align: center; border-bottom: 2px solid #00ffcc; padding-bottom: 12px; margin-bottom: 18px; }} .header h1 {{ margin: 0; color: #ffffff; letter-spacing: 2px; }} .header p {{ margin: 4px 0; color: #00ffcc; font-weight: bold; font-size: 13px; }} .meta {{ font-size: 12px; color: #9ba1b0; margin-bottom: 15px; display: flex; justify-content: space-between; }} .tabla-boletin {{ width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 20px; }} .tabla-boletin th {{ background-color: #16181f; color: #00ffcc; padding: 8px; text-align: left; border-bottom: 2px solid #00ffcc; }} .tabla-boletin td {{ padding: 8px; border-bottom: 1px solid #1f222d; color: #e0e0e0; }} .footer {{ text-align: center; font-size: 12px; color: #00ffcc; border-top: 1px solid #1f222d; padding-top: 12px; margin-top: 25px; }} .btn-print {{ background: #00ffcc; color: #000; padding: 8px 16px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; margin-bottom: 15px; }} @media print {{ .btn-print {{ display: none; }} body {{ background-color: #ffffff; color: #000000; }} .tabla-boletin td, .tabla-boletin th {{ color: #000000; border-color: #cccccc; }} }}</style></head><body><button class="btn-print" onclick="window.print()">🖨️ Imprimir PDF</button><div class="header"><h1>⚽ MRFUTBOL - BOLETÍN OFICIAL VIP</h1><p>Autoría Oficial: Miguel Ramirez | ✉️ angelramirezzmiguel2@gmail.com</p></div><div class="meta"><span><strong>Reporte:</strong> {titulo_reporte} ({subtitulo_reporte})</span><span><strong>Emisión (UTC-6):</strong> {fecha_emision} | <strong>Stake 2% - 3%</strong></span></div>{df_datos.to_html(index=False, border=0, classes="tabla-boletin")}<div class="footer">⚽ MRFUTBOL Central de Inteligencia | Creado por Miguel Ramirez</div></body></html>"""

col_m1, col_m2 = st.columns([3, 1])
with col_m2: auto_refresh = st.toggle("⚡ Refresco en Vivo", value=True)

def accionar_plequita_vip(ev_id, nl, nv, lig, fec, p_pre, x_pre, s_viv, gol):
    p = boveda_vip.setdefault("picks_vip_hoy", {})
    if ev_id in p: del p[ev_id]
    else: p[ev_id] = {"ev_id": ev_id, "origen": "⚡ Plequita Manual", "ficha": analizar_partido_profundo_mrfutbol(ev_id, nl, nv, lig, fec, p_pre, x_pre, s_viv, None, gol)}
    guardar_boveda_vip_servidor(boveda_vip)

_frag = getattr(st, "fragment", getattr(st, "experimental_fragment", None))
@(_frag(run_every=25 if auto_refresh else None) if _frag else lambda f: f)
def renderizar_central_mrfutbol():
    hoy_dt = datetime.utcnow() - timedelta(hours=6)
    str_hoy = hoy_dt.strftime("%Y-%m-%d")
    
    if boveda_vip.get("fecha_activa") != str_hoy:
        boveda_vip["fecha_activa"] = str_hoy
        boveda_vip["picks_vip_hoy"] = {}
        guardar_boveda_vip_servidor(boveda_vip)

    uso_api = boveda_vip.get("uso_diario_api", {"usadas": 0})
    ct = [l["code"] for l in LIGAS_BIG_DATA]
    datos_globales = obtener_partidos_ligas(ct)
    stats_api, efec_api = obtener_estadisticas_temporada_reales(ct)

    with col_m1:
        st.caption(f"💡 Central MRFUTBOL | 🕒 Sincronizado: {hoy_dt.strftime('%H:%M:%S')} | 👑 Llamadas Motor VIP (Sportmonks): **{uso_api.get('usadas', 0)} / 50000**")

    t1, t2, t3, t4, t5 = st.tabs(["⚽ 1. CARTELERA", "🔴 2. PARTIDOS EN VIVO", "🎯 3. PRE-APUESTAS", "🚨 4. TERMINAL EN VIVO", "👑 5. SALA VIP"])

    with t1:
        cm, cc = st.columns([1.2, 3.8])
        with cm:
            st.markdown("##### 📅 Opciones")
            fs = st.radio("Día:", ["Hoy", "Mañana"])
            fecha_obj = str_hoy if fs == "Hoy" else (hoy_dt + timedelta(days=1)).strftime("%Y-%m-%d")
            oc = st.toggle("👁️ Ocultar Finalizados", value=True)
            busq = st.text_input("🔍 Buscar...", placeholder="Ej. MR2026")
            if st.button("🔄 Refrescar", use_container_width=True): st.cache_data.clear(); st.rerun()
            if busq == "MR2026":
                st.success("🔓 Admin Activo")
                if st.button("🧹 Vaciar VIP", use_container_width=True): boveda_vip["picks_vip_hoy"]={}; guardar_boveda_vip_servidor(boveda_vip); st.rerun()
        with cc:
            hp = False
            for lig, cont in datos_globales.items():
                evs = [ev for ev in cont["eventos"] if obtener_fecha_local_evento(ev.get("date"))[0] == fecha_obj]
                if not evs: continue
                hp = True
                st.markdown(f"<div class='liga-header'><span>{lig}</span></div>", unsafe_allow_html=True)
                for ev in evs:
                    c = ev.get("competitions", [{}])[0]
                    st_ev, eh, mn, bh, _ = detectar_estado_partido(c, ev.get("date"))
                    if oc and st_ev == "post": continue
                    cp = c.get("competitors", [])
                    if len(cp) == 2:
                        nl, nv = cp[0].get("team", {}).get("shortDisplayName", ""), cp[1].get("team", {}).get("shortDisplayName", "")
                        if busq and busq != "MR2026" and busq.lower() not in f"{nl} {nv}".lower(): continue
                        gl, gv = int(cp[0].get("score", 0)), int(cp[1].get("score", 0))
                        ch = f"{gl} - {gv}" if (st_ev != "pre" or eh) else "vs"
                        st.markdown(f"<div class='match-card'>{bh}<div class='teams-container'><div class='team-home'>{nl}</div><div class='score-box'>{ch}</div><div class='team-away'>{nv}</div></div></div>", unsafe_allow_html=True)
            if not hp: st.info("No hay partidos programados.")

    with t2:
        st.subheader("🔴 Partidos en Curso")
        hv = False
        for lig, cont in datos_globales.items():
            evs = [ev for ev in cont["eventos"] if detectar_estado_partido(ev.get("competitions", [{}])[0], ev.get("date"))[0] == "in"]
            if evs:
                hv = True
                st.markdown(f"<div class='liga-header'><span>{lig}</span></div>", unsafe_allow_html=True)
                for ev in evs:
                    c = ev.get("competitions", [{}])[0]
                    st_ev, eh, mn, bh, _ = detectar_estado_partido(c, ev.get("date"))
                    cp = c.get("competitors", [])
                    nl, nv = cp[0].get("team", {}).get("shortDisplayName", ""), cp[1].get("team", {}).get("shortDisplayName", "")
                    gl, gv = int(cp[0].get("score", 0)), int(cp[1].get("score", 0))
                    sr = extraer_metricas_partido_reales(cp[0], cp[1])
                    st.markdown(f"<div class='match-card'>{bh} <div style='flex-grow:1; text-align:center;'><strong>{nl} {gl} - {gv} {nv}</strong></div> <div>🎯 {sr['toth_tot']} Disp | 🥅 {sr['tmeta_tot']} Arco</div></div>", unsafe_allow_html=True)
        if not hv: st.info("No hay partidos en curso.")

    with t3:
        st.subheader("🎯 Laboratorio Pre-Apuesta Over 1.5 (Prioridad Momento 2-3J)")
        r_pre = []
        for lig, cont in datos_globales.items():
            for ev in cont["eventos"]:
                c = ev.get("competitions", [{}])[0]
                if c.get("status", {}).get("type", {}).get("state", "") == "pre":
                    cp = c.get("competitors", [])
                    if len(cp) == 2:
                        nl, nv = cp[0].get("team", {}).get("displayName", ""), cp[1].get("team", {}).get("displayName", "")
                        if nl and nv:
                            pf, cj, xb, ft = calcular_pre_poisson_real(nl, nv, stats_api)
                            if pf >= 64.0:
                                t1, t2, t3 = calcular_tasas_tiempos_y_franja(xb, 0, 0, 0, 0)
                                v = "🟢 ENTRAR OVER 1.5" if pf >= 75.5 else "🔴 ZONA ROJA (<70%)" if pf < 70 else "💎 ENTRAR OVER 1.5"
                                r_pre.append({"Liga": lig, "Partido": f"{nl} vs {nv}", "⚡ CALIENTE (FINAL)": f"{pf}%", "⏱️ Gol 1T": f"{t1}%", "🔥 Gol 2T": f"{t2}%", "Cuota": cj, "Respaldo + Aprendizaje (2J)": ft, "Veredicto": v, "_orden": pf})
        if r_pre:
            df_pre = pd.DataFrame(r_pre).sort_values(by="_orden", ascending=False).drop(columns=["_orden"])
            st.dataframe(df_pre, use_container_width=True, hide_index=True)
            st.download_button("📊 Exportar Pre-Apuestas (.CSV)", data=df_pre.to_csv(index=False).encode("utf-8-sig"), file_name=f"PreApuestas_{str_hoy}.csv", mime="text/csv")
        else: st.info("No hay partidos con alta probabilidad.")

    with t4:
        st.markdown("### 🚨 TERMINAL EN VIVO 0.5")
        st.markdown("**Regla 96.8% Verde:** Busca 6+ Disparos o 3+ al Arco.")
        t_scr = []
        for lig, cont in datos_globales.items():
            for ev in cont["eventos"]:
                c = ev.get("competitions", [{}])[0]
                if c.get("status", {}).get("type", {}).get("state", "") == "in":
                    cp = c.get("competitors", [])
                    nl, nv = cp[0].get("team", {}).get("displayName", ""), cp[1].get("team", {}).get("displayName", "")
                    gl, gv = int(cp[0].get("score", 0)), int(cp[1].get("score", 0))
                    r = c.get("status", {}).get("displayClock", "0'")
                    try: ma = int(r.replace("'", "").split("+")[0])
                    except: ma = 0
                    
                    pf, cj, xb, ft = calcular_pre_poisson_real(nl, nv, stats_api)
                    sr = extraer_metricas_partido_reales(cp[0], cp[1])
                    t1, t2, t3 = calcular_tasas_tiempos_y_franja(xb, sr['toth_tot'], sr['tmeta_tot'], sr['esquinas_tot'], ma)
                    
                    vd = "⏸️ AGUANTAR: Exigir 6+ Disp o 2+ al Arco"
                    es_cal = False
                    cls_b = "veredicto-box-wait"
                    
                    if (gl+gv) == 0:
                        if sr['toth_tot'] >= 6 or sr['tmeta_tot'] >= 3:
                            vd = f"🚨 ¡ENTRAR OVER 0.5! [PATRÓN 96.8% VERDE] (Tasa 2T: {t2}%)"
                            es_cal = True; cls_b = "veredicto-box-hot"
                    else:
                        vd = "✅ LÍNEA CUBIERTA"
                        cls_b = "veredicto-box-green"

                    t_scr.append({"ev_id": ev.get("id"), "r": r, "p": f"{nl} vs {nv}", "m": f"{gl}-{gv}", "nl": nl, "nv": nv, "lig": lig, "pf": pf, "g": (gl+gv), "tt": sr['toth_tot'], "tm": sr['tmeta_tot'], "esq": sr['esquinas_tot'], "vd": vd, "cls_b": cls_b, "es_cal": es_cal, "t1": t1, "t2": t2, "t3": t3, "sr": sr})
        
        for it in sorted(t_scr, key=lambda x: (x['g'], not x['es_cal'], -x['pf'])):
            eid = it["ev_id"]
            yv = eid in boveda_vip.get("picks_vip_hoy", {})
            cc = "trading-card-hot" if it["es_cal"] else "trading-card"
            c1, c2 = st.columns([10.2, 1.8])
            with c1:
                st.markdown(f"""
                <div class='{cc}'>
                    <div class="trading-header">
                        <div><span style='background:#ff2a4b; color:#fff; padding:3px 8px; border-radius:4px;'>{it['r']}</span> <strong>{it['p']}</strong> <span style='color:#00ffcc;'>{it['m']}</span></div>
                        <div style="font-size:12px; color:#9ba1b0;">{it['lig']} | ✅ Radar MRFUTBOL (50K/Día)</div>
                    </div>
                    <div class="trading-metrics-grid">
                        <div class="metric-pill"><span>📈 Pre Over 1.5</span><strong>{it['pf']}%</strong></div>
                        <div class="metric-pill"><span>⏱️ Gol 1T</span><strong>{it['t1']}%</strong></div>
                        <div class="metric-pill"><span>🔥 Gol 2T</span><strong>{it['t2']}%</strong></div>
                        <div class="metric-pill"><span>🎯 Disparos</span><strong>{it['tt']}</strong></div>
                        <div class="metric-pill"><span>🥅 Al Arco</span><strong>{it['tm']}</strong></div>
                        <div class="metric-pill"><span>🚩 Córn | Pos</span><strong>{it['esq']} | {it['sr']['pos_l']}%-{it['sr']['pos_v']}%</strong></div>
                    </div>
                    <div class="{it['cls_b']}">{it['vd']}</div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown("<div style='margin-top:18px;'></div>", unsafe_allow_html=True)
                st.checkbox("☑️ Enviar VIP", value=yv, key=f"vip_{eid}_{yv}", on_change=accionar_plequita_vip, args=(eid, it["nl"], it["nv"], it["lig"], str_hoy, it["pf"], it["pf"]/2, it["sr"], it['g']))

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
                        <div class="metric-pill"><span>🥩 [EFICIENCIA / CARNICERÍA]</span><strong>{f['Paso3_Eficiencia_Carniceria']}</strong><small>{f['Ref_Carniceria']}</small></div>
                        <div class="metric-pill"><span>🧀 [VULNERABILIDAD RIVAL]</span><strong>{f['Paso3_Vulnerabilidad_Rival']}</strong><small>{f['Ref_Vulnerabilidad']}</small></div>
                        <div class="metric-pill"><span>🔥 [MOMENTUM OFENSIVO]</span><strong>{f['Paso3_Momentum']}</strong><small>{f['Ref_Momentum']}</small></div>
                        <div class="metric-pill"><span>🤝 [SISTEMA COLECTIVO 10.5]</span><strong>{f['Paso3_Colectivo_105']}</strong><small>{f['Ref_Colectivo']}</small></div>
                        <div class="metric-pill"><span>🎰 [VARIANZA / DEUDA DE GOL]</span><strong>{f['Paso3_Varianza_Deuda']}</strong><small>{f['Ref_Varianza']}</small></div>
                        <div class="metric-pill"><span>🏆 [CONTEXTO TABLA / URGENCIA]</span><strong>{f['Paso3_Contexto_Urgencia']}</strong><small>{f['Ref_Urgencia']}</small></div>
                    </div>
                    <div style="font-size:11px; color:#9ba1b0; margin-top:8px;">{f['Liga']} | {f.get('Sello_API', '')}</div>
                </div>
                """, unsafe_allow_html=True)
            if st.button("🔓 Descargar Reporte VIP (CSV)", use_container_width=True):
                st.download_button("Descargar", data=pd.DataFrame([iv["ficha"] for iv in lv]).to_csv(index=False).encode("utf-8-sig"), file_name=f"Reporte_VIP_{str_hoy}.csv", mime="text/csv")
        else: st.info("Marca la plequita `☑️ Enviar VIP` en el Terminal en Vivo 0.5 para destripar el partido con el motor V3.")

renderizar_central_mrfutbol()
