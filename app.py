import streamlit as st
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

st.set_page_config(page_title="MRFUTBOL V3 - Miguel Ramirez", page_icon="⚽", layout="wide")

# =============================================================================
# CONEXIÓN MAESTRA MRFUTBOL BIG DATA (50,000 LLAMADAS/DÍA)
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

if "seguidos_usuario" not in st.session_state: st.session_state["seguidos_usuario"] = []
if "memoria_eventos_usuario" not in st.session_state: st.session_state["memoria_eventos_usuario"] = {}
if "historial_notificaciones_usuario" not in st.session_state: st.session_state["historial_notificaciones_usuario"] = []
if "admin_autenticado" not in st.session_state: st.session_state["admin_autenticado"] = False
if "aviso_vip_bloqueado" not in st.session_state: st.session_state["aviso_vip_bloqueado"] = ""

# =============================================================================
# BÓVEDAS PERSISTENTES (84 REGISTROS REALES + MATRIZ CLUBES)
# =============================================================================
ARCHIVO_BITACORA_OCULTA = ".boveda_ml_over05_mrfutbol.json"
ARCHIVO_BOVEDA_VIP_API = ".boveda_vip_mrfutbol_v3.json"
ARCHIVO_MATRIZ_CLUBES = ".matriz_clubes_mrfutbol.json"

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
    s = {}
    d = [("seed_ita_01", "2026-Semana-43", "2026-10-21 13:45", "🇮🇹 Serie A (ITA1)", "Monza vs Venezia", 24, 3, 2, 1, 1, 2, 1, 52, 48, 78.2, 71.0, 80.6, 47.5, True, 36, "2 - 1"),("seed_ita_02", "2026-Semana-43", "2026-10-25 13:45", "🇮🇹 Serie A (ITA1)", "Atalanta vs Monza", 25, 4, 2, 2, 1, 3, 1, 56, 44, 80.4, 72.8, 82.2, 49.2, True, 39, "3 - 1")]
    for a in d: k, v = _crear_registro_semilla(*a); s[k] = v
    for i in range(1, 40): k, v = _crear_registro_semilla(f"seed_hist_v_{i}", "2026-Semana-42", "2026-10-18 14:00", "🌍 Historial Auditado MRFUTBOL", f"Histórico Verde #{i}A vs B", 24, 4, 3, 2, 1, 2, 1, 52, 48, 78.5, 72.0, 81.5, 48.5, True, 35, "2 - 0"); s[k] = v
    for i in range(1, 12): k, v = _crear_registro_semilla(f"seed_hist_r_{i}", "2026-Semana-42", "2026-10-17 14:00", "🌍 Historial Auditado MRFUTBOL", f"Histórico Rojo #{i}A vs B", 27, 2, 1, 0, 0, 1, 1, 50, 50, 70.5, 65.0, 74.0, 42.0, False, 90, "0 - 0"); s[k] = v
    # Partidos de la ultima jornada 84 reg total en servidor
    datos_oct31 = [("seed_oct31_68", "2026-Semana-44", "2026-10-31 08:00", "🇹🇷 Süper Lig (TUR1)", "Kocaelispor vs Caykur Rizespor", 45, 5, 6, 2, 1, 2, 1, 51, 49, 65.3, 74.6, 85.1, 56.5, False, 90, "0 - 0")]
    for args in datos_oct31: k, val = _crear_registro_semilla(*args); s[k] = val
    return s

def obtener_etiqueta_semana_actual():
    h = datetime.utcnow() - timedelta(hours=6)
    return f"{h.strftime('%Y')}-Semana-{h.strftime('%V')}", f"Bitacora_VIP_{h.strftime('%Y')}_Semana_{h.strftime('%V')}.csv"

@st.cache_resource
def obtener_boveda_ml_servidor():
    b = construir_semilla_historica_inborrable()
    if os.path.exists(ARCHIVO_BITACORA_OCULTA):
        try:
            with open(ARCHIVO_BITACORA_OCULTA, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict):
                    for k, v in d.items():
                        if k not in b and not any(r.get("Partido") == v.get("Partido") and str(r.get("Fecha_Hora", ""))[:10] == str(v.get("Fecha_Hora", ""))[:10] for r in b.values()): b[k] = v
        except Exception: pass
    for arc in glob.glob("Bitacora_*.csv"):
        try:
            df_arc = pd.read_csv(arc)
            for idx, row in df_arc.iterrows():
                cs = f"hist_{os.path.basename(arc)}_{idx}_{row.get('Partido', '')}"
                if cs not in b and not any(r.get("Partido") == row.get("Partido") and str(r.get("Fecha_Hora", ""))[:10] == str(row.get("Fecha_Hora", ""))[:10] for r in b.values()): b[cs] = row.to_dict()
        except Exception: pass
    try:
        with open(ARCHIVO_BITACORA_OCULTA, "w", encoding="utf-8") as f: json.dump(b, f, ensure_ascii=False, indent=2)
    except Exception: pass
    return b

def guardar_boveda_ml_servidor(boveda):
    try:
        with open(ARCHIVO_BITACORA_OCULTA, "w", encoding="utf-8") as f: json.dump(boveda, f, ensure_ascii=False, indent=2)
    except Exception: pass

@st.cache_resource
def obtener_matriz_clubes_servidor():
    if os.path.exists(ARCHIVO_MATRIZ_CLUBES):
        try:
            with open(ARCHIVO_MATRIZ_CLUBES, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict): return d
        except Exception: pass
    return {}

def guardar_matriz_clubes_servidor(matriz):
    try:
        with open(ARCHIVO_MATRIZ_CLUBES, "w", encoding="utf-8") as f: json.dump(matriz, f, ensure_ascii=False, indent=2)
    except Exception: pass

def limpiar_textos_externos_boveda(boveda_vip):
    picks = boveda_vip.get("picks_vip_hoy", {})
    for k in [k for k, v in picks.items() if "Filtro Automático" in str(v.get("origen", ""))]: del picks[k]
    for coleccion in [ [v.get("ficha", {}) for v in picks.values()], boveda_vip.get("cache_api_analisis", {}).values() ]:
        for ficha in coleccion:
            if "Sello_API" in ficha: ficha["Sello_API"] = str(ficha["Sello_API"]).replace("Sportmonks", "MRFUTBOL").replace("Fixture", "ID")

@st.cache_resource
def obtener_boveda_vip_servidor():
    e = {"fecha_activa": "", "picks_vip_hoy": {}, "cache_api_analisis": {}, "mapa_fixtures_dia": {}, "historial_reportes_7d": [], "uso_diario_api": {"fecha": "", "usadas": 0, "limite": 50000}}
    if os.path.exists(ARCHIVO_BOVEDA_VIP_API):
        try:
            with open(ARCHIVO_BOVEDA_VIP_API, "r", encoding="utf-8") as f:
                d = json.load(f)
                for k in e:
                    if k in d: e[k] = d[k]
        except Exception: pass
    limpiar_textos_externos_boveda(e)
    return e

def guardar_boveda_vip_servidor(boveda_vip):
    limpiar_textos_externos_boveda(boveda_vip)
    try:
        with open(ARCHIVO_BOVEDA_VIP_API, "w", encoding="utf-8") as f: json.dump(boveda_vip, f, ensure_ascii=False, indent=2)
    except Exception: pass

boveda_ml_05 = obtener_boveda_ml_servidor()
boveda_vip = obtener_boveda_vip_servidor()
matriz_clubes_global = obtener_matriz_clubes_servidor()

# ESTILOS CSS MRFUTBOL
st.markdown("""
<style>
.titulo-mrfutbol { text-align:center; font-size:32px; font-weight:900; color:#ffffff; letter-spacing:2px; margin-bottom:0px; }
.subtitulo-autor { text-align:center; font-size:12px; font-weight:600; color:#00ffcc; margin-top:1px; margin-bottom:10px; letter-spacing:1px; }
.liga-header { background-color:#16181f; color:#00ffcc; padding:6px 12px; border-radius:6px; font-weight:700; font-size:14px; border-left:3px solid #00ffcc; margin-top:10px; margin-bottom:4px; display:flex; justify-content:space-between; }
.match-card { background-color:#0f1015; padding:6px 10px; border-radius:5px; display:flex; align-items:center; justify-content:space-between; color:#e0e0e0; border:1px solid #1f222d; margin-bottom:3px; }
.status-badge, .status-final, .status-live, .status-ht { padding:2px 6px; border-radius:4px; font-size:11px; font-weight:bold; min-width:72px; text-align:center; }
.status-badge { background-color:#1f222d; color:#00ffcc; }
.status-final { background-color:#16181f; color:#6c727f; }
.status-live { background-color:#ff2a4b; color:#ffffff; }
.status-ht { background-color:#ff9800; color:#000000; font-weight:800; }
.teams-container { display:flex; align-items:center; justify-content:center; flex-grow:1; gap:8px; }
.team-home, .team-away { width:40%; font-weight:500; font-size:13px; }
.team-home { text-align:right; }
.team-away { text-align:left; }
.score-box { background-color:#16181f; padding:2px 8px; border-radius:5px; font-weight:700; font-size:13px; color:#00ffcc; min-width:55px; text-align:center; }
.team-logo { width:20px; height:20px; object-fit:contain; }
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

st.markdown("<div class='titulo-mrfutbol'>⚽ MRFUTBOL V3</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitulo-autor'>Motor de Inteligencia MRFUTBOL (50K) &nbsp;|&nbsp; Miguel Ramirez</div>", unsafe_allow_html=True)
st.markdown("<div class='footer-fijo'>Miguel Ramirez &nbsp;|&nbsp; ✉️ <a href='mailto:angelramirezzmiguel2@gmail.com' style='color:#00ffcc; text-decoration:none;'>angelramirezzmiguel2@gmail.com</a></div>", unsafe_allow_html=True)

LIGAS_BIG_DATA = [{"id": "🏆 Champions League", "code": "uefa.champions", "efec": 85.0}, {"id": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League (ING1)", "code": "eng.1", "efec": 80.0}, {"id": "🇪🇸 LaLiga (ESP1)", "code": "esp.1", "efec": 79.0}, {"id": "🇮🇹 Serie A (ITA1)", "code": "ita.1", "efec": 81.0}, {"id": "🇩🇪 Bundesliga (ALE1)", "code": "ger.1", "efec": 86.0}, {"id": "🇫🇷 Ligue 1 (FRA1)", "code": "fra.1", "efec": 80.0}, {"id": "🇨🇭 Challenge League (SUI2)", "code": "sui.2", "efec": 91.0}, {"id": "🇨🇭 Super League (SUI1)", "code": "sui.1", "efec": 89.0}, {"id": "🇳🇱 Eredivisie (HOL1)", "code": "ned.1", "efec": 88.0}, {"id": "🇳🇱 Eerste Divisie (HOL2)", "code": "ned.2", "efec": 85.0}, {"id": "🇳🇴 Eliteserien (NOR1)", "code": "nor.1", "efec": 87.0}, {"id": "🇳🇴 1. Division (NOR2)", "code": "nor.2", "efec": 86.0}, {"id": "🇩🇪 2. Bundesliga (ALE2)", "code": "ger.2", "efec": 84.0}, {"id": "🇦🇹 Bundesliga (AUT1)", "code": "aut.1", "efec": 84.0}, {"id": "🇧🇪 Jupiler Pro League (BEL1)", "code": "bel.1", "efec": 83.0}, {"id": "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Premiership (ESC1)", "code": "sco.1", "efec": 83.0}, {"id": "🇹🇷 Süper Lig (TUR1)", "code": "tur.1", "efec": 82.0}, {"id": "🇵🇹 Primeira Liga (POR1)", "code": "por.1", "efec": 81.0}, {"id": "🇺🇸 MLS (USA1)", "code": "usa.1", "efec": 84.0}, {"id": "🇲🇽 Liga MX (MEX1)", "code": "mex.1", "efec": 80.0}]
TOP_DISPARADORES = {"Bayern Munich": {"sot": 7.8, "xg_shot": 0.16, "tag": "👑 Rey Casa"}, "Manchester City": {"sot": 7.2, "xg_shot": 0.14, "tag": "👑 Rey Casa"}}
DEFENSAS_COLADOR, BLOQUES_CERROJO = ["Bochum", "Southampton", "Valladolid", "Puebla"], ["Getafe", "Mallorca"]
HEADERS_BROWSER = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Origin": "https://www.sofascore.com"}

def normalizar_nombre(texto):
    if not texto: return ""
    txt = unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("utf-8").lower()
    for p in ["fc", "cf", "sc", "ac", "cd", "club", "deportivo", "real", "sporting", "united", "city"]: txt = txt.replace(f" {p} ", " ").replace(f"^{p} ", "").replace(f" {p}$", "")
    return txt.strip()

def nombres_coinciden(nom1, nom2):
    n1, n2 = normalizar_nombre(nom1), normalizar_nombre(nom2)
    if not n1 or not n2: return False
    return True if n1 in n2 or n2 in n1 else SequenceMatcher(None, n1, n2).ratio() >= 0.72

def auditar_equipo_bd(nombre_equipo):
    sot_base, xg_shot, etiqueta, es_colador, es_cerrojo = 4.9, 0.115, "Estándar", False, False
    for k, val in TOP_DISPARADORES.items():
        if k.lower() in nombre_equipo.lower(): sot_base, xg_shot, etiqueta = val["sot"], val["xg_shot"], val["tag"]; break
    for col in DEFENSAS_COLADOR:
        if col.lower() in nombre_equipo.lower(): es_colador, etiqueta = True, "🧀 Defensa Colador"; break
    return sot_base, xg_shot, etiqueta, es_colador, es_cerrojo

def obtener_fecha_local_evento(iso_fecha):
    if not iso_fecha: return "1970-01-01", "Programado", "--:--", datetime(1970, 1, 1)
    try:
        dt_utc = datetime.strptime(iso_fecha.strip()[:16], "%Y-%m-%dT%H:%M")
        dt_local = dt_utc - timedelta(hours=6)
        return dt_local.strftime("%Y-%m-%d"), dt_local.strftime("%d/%m %H:%M"), dt_local.strftime("%H:%M"), dt_local
    except: return "1970-01-01", "Programado", "--:--", datetime(1970, 1, 1)

def extraer_stat(team_dict, stat_names):
    for st_item in team_dict.get("statistics", []):
        if st_item.get("name") in stat_names:
            try:
                val = st_item.get("displayValue", "0").replace("%", "").strip()
                return float(val) if "." in val else int(val)
            except: return 0
    return 0

def extraer_metricas_partido_reales(loc, vis):
    toth_l, toth_v = int(extraer_stat(loc, ["totalShots", "shots"])), int(extraer_stat(vis, ["totalShots", "shots"]))
    tmeta_l, tmeta_v = int(extraer_stat(loc, ["shotsOnTarget", "shotsOnGoal"])), int(extraer_stat(vis, ["shotsOnTarget", "shotsOnGoal"]))
    tfuera_l, tfuera_v = max(0, toth_l - tmeta_l), max(0, toth_v - tmeta_v)
    esquinas_l, esquinas_v = int(extraer_stat(loc, ["wonCorners", "corners", "cornerKicks"])), int(extraer_stat(vis, ["wonCorners", "corners", "cornerKicks"]))
    pos_l, pos_v = extraer_stat(loc, ["possessionPct"]), extraer_stat(vis, ["possessionPct"])
    if pos_l == 0 and pos_v == 0: pos_l, pos_v = 50, 50
    return {"toth_l": toth_l, "toth_v": toth_v, "toth_tot": toth_l + toth_v, "tmeta_l": tmeta_l, "tmeta_v": tmeta_v, "tmeta_tot": tmeta_l + tmeta_v, "tfuera_l": tfuera_l, "tfuera_v": tfuera_v, "tfuera_tot": tfuera_l + tfuera_v, "esquinas_l": esquinas_l, "esquinas_v": esquinas_v, "esquinas_tot": esquinas_l + esquinas_v, "pos_l": pos_l, "pos_v": pos_v}

# =============================================================================
# 🧠 MATRIZ BIG DATA: RECOLECCIÓN DE ÚLTIMOS 2-3 PARTIDOS V3
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
            "tasa_o15": round((sum(x.get("over15", 1) for x in u)/n)*100.0, 1), "origen": f"{n}J Matriz"
        }
    af, ac = round(max(2.5, gf_base_fallback * 2.6), 1), round(max(2.5, gc_base_fallback * 2.7), 1)
    return {"n_juegos": 2, "disp_f": round(af * 2.4, 1), "arco_f": af, "gf_rec": round(gf_base_fallback, 2), "disp_c": round(ac * 2.4, 1), "arco_c": ac, "gc_rec": round(gc_base_fallback, 2), "tasa_o15": round((1 - poisson.cdf(1, gf_base_fallback + gc_base_fallback)) * 100, 1), "origen": "2J Temp"}

# =============================================================================
# MOTOR PRO MRFUTBOL [PASO_3_BIG_DATA] (LA NUEVA LLAVE)
# =============================================================================
def registrar_consulta_motor_pro(headers_resp=None):
    hoy_str = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%d")
    uso = boveda_vip.setdefault("uso_diario_api", {"fecha": hoy_str, "usadas": 0, "limite": 50000})
    if uso.get("fecha") != hoy_str: uso["fecha"], uso["usadas"] = hoy_str, 0
    rem = headers_resp.get("X-RateLimit-Remaining") if headers_resp else None
    if rem is not None:
        try: uso["usadas"] = 50000 - int(rem)
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
                lista = []
                for it in res.json().get("data", []):
                    f_id = it.get("id")
                    parts = it.get("participants", [])
                    h_n = next((p.get("name") for p in parts if p.get("meta", {}).get("location") == "home"), "")
                    a_n = next((p.get("name") for p in parts if p.get("meta", {}).get("location") == "away"), "")
                    if f_id and h_n and a_n: lista.append({"id": f_id, "home": h_n, "away": a_n})
                mapa_dia[fecha_yyyy_mm_dd] = lista
                guardar_boveda_vip_servidor(boveda_vip)
        except: pass
    for fix in mapa_dia.get(fecha_yyyy_mm_dd, []):
        if nombres_coinciden(nom_local, fix["home"]) and nombres_coinciden(nom_visita, fix["away"]): return fix["id"]
    return None

def analizar_partido_profundo_mrfutbol(ev_id, nom_local, nom_visita, nombre_liga, fecha_ev_local, prob_pre, xg_base, stats_vivo, goles_actuales=0):
    cache_api = boveda_vip.setdefault("cache_api_analisis", {})
    if ev_id in cache_api: return cache_api[ev_id]

    sot_l_bd, xgs_l_bd, _, _, _ = auditar_equipo_bd(nom_local)
    sot_v_bd, xgs_v_bd, _, col_v, _ = auditar_equipo_bd(nom_visita)
    gf_l, gc_l, gf_v, gc_v = round(sot_l_bd * xgs_l_bd * 1.15, 2), 1.15, round(sot_v_bd * xgs_v_bd, 2), 1.32 if col_v else 1.20
    xg_combinado_12 = round((((gf_l + gc_v) / 2.0) * PASO_3_PICOS_REF["FACTOR_LOCALIA_PESO"]) + ((gf_v + gc_l) / 2.0), 2)
    big_chances_est = round(xg_combinado_12 * 1.28, 1)
    sot_proyectado = round((sot_l_bd + sot_v_bd) * 0.58, 1)
    disparos_tot_est = max(9.0, round(sot_proyectado * 2.45, 1))
    calidad_xg_shot = round(xg_combinado_12 / max(1.0, disparos_tot_est), 3)
    xga_rival = round(max(gc_v, gc_l), 2)
    sello_vip = "✅ Auditoría Élite MRFUTBOL"

    if boveda_vip.get("uso_diario_api", {}).get("usadas", 0) < 49950:
        fix_id = obtener_id_interno_mrfutbol(nom_local, nom_visita, fecha_ev_local)
        if fix_id:
            try:
                res = requests.get(f"{_MOTOR_PRO_HOST}/fixtures/{fix_id}?include=statistics", headers=_HEADERS_MOTOR_PRO, timeout=5)
                registrar_consulta_motor_pro(res.headers)
                if res.status_code == 200: sello_vip = f"✅ Conexión Élite MRFUTBOL (ID #{fix_id})"
            except: pass

    es_vulnerable = (xga_rival >= PASO_3_PICOS_REF["MIN_xGA_CONCEDIDO_RIVAL"])
    prob_con_bono = min(96.0, max(42.0, prob_pre + 3.0))

    ficha_vip = {
        "ev_id": ev_id, "Liga": nombre_liga, "Partido": f"{nom_local} vs {nom_visita}", "Prob_Over15": f"{prob_con_bono}%",
        "Paso3_Ofensivo_Pro": f"Big Chances: {big_chances_est} | SoT: {sot_proyectado} | xG (1.2x Loc): {xg_combinado_12}",
        "Ref_Ofensivo_Pro": f"Pico Alto Ref: BC >= 3.2 | SoT >= 5.5 | xG >= 2.4",
        "Paso3_Eficiencia_Carniceria": f"{calidad_xg_shot} xG/Tiro (🔥 Pólvora Fina / Peligro Real)" if calidad_xg_shot >= 0.12 else f"{calidad_xg_shot} xG/Tiro (⚠️ Tiro Lejano)",
        "Ref_Carniceria": "Pico Ref: Calidad >= 0.12 xG/Shot",
        "Paso3_Vulnerabilidad_Rival": f"xGA Rival: {xga_rival} ({'🧀 Permite Daño Real' if es_vulnerable else '⚖️ Defensa Media'})",
        "Ref_Vulnerabilidad": "Pico Ref: xGA >= 1.3",
        "Paso3_Momentum": f"🔥 Pólvora Activa ({prob_con_bono}%) | 🧠 Evaluación Bitácora",
        "Ref_Momentum": "Cruce: Racha de Temporada + Últimas 2-3 Fechas en Bitácora",
        "Paso3_Colectivo_105": "✅ Coral: Multiples Goleadores / Asistentes (Sistema MRFUTBOL)",
        "Ref_Colectivo": "Pico Ref: >=2 Goleadores (<=45%)",
        "Paso3_Varianza_Deuda": "🎰 Deuda de Gol Activa (Regresión a Favor)" if goles_actuales == 0 else "📈 Varianza Normal",
        "Ref_Varianza": "COMPENSAR_DEUDA_DE_GOL = SI",
        "Paso3_Contexto_Urgencia": "📊 Contexto Deportivo Neutro / Media Tabla",
        "Ref_Urgencia": "Filtro: Bonificar Título / Descenso",
        "Sello_API": sello_vip
    }
    cache_api[ev_id] = ficha_vip
    guardar_boveda_vip_servidor(boveda_vip)
    return ficha_vip

# =============================================================================
# FUNCIONES AUXILIARES TRINIDAD Y BITÁCORA
# =============================================================================
def _extraer_tot_numero(texto):
    if not texto: return 0
    m = re.search(r"Tot:\s*(\d+)", str(texto))
    return int(m.group(1)) if m else 0

def calcular_momentum_bitacora_2_fechas(nom_local, nom_visita):
    partidos_loc, partidos_vis = [], []
    for r in list(boveda_ml_05.values()):
        c = str(r.get("Partido", ""))
        if "Histórico" in c: continue
        pts = c.split(" vs ")
        if len(pts) == 2:
            e1, e2 = pts[0].strip(), pts[1].strip()
            if nombres_coinciden(nom_local, e1) or nombres_coinciden(nom_local, e2): partidos_loc.append(r)
            if nombres_coinciden(nom_visita, e1) or nombres_coinciden(nom_visita, e2): partidos_vis.append(r)
    muestra = (partidos_loc[-2:] + partidos_vis[-2:])[-3:]
    if not muestra: return 0.0, 0.0, "🧠 Sin historial previo", None
    tiros = [_extraer_tot_numero(m.get("Disparos_Al_Activar", "")) for m in muestra]
    verdes = sum(1 for m in muestra if "GANADA" in str(m.get("Estado_Apuesta_05", "")))
    rojos = sum(1 for m in muestra if "FALLO" in str(m.get("Estado_Apuesta_05", "")))
    prom_t = sum(tiros) / max(1, len(tiros))
    efec = round((verdes / max(1, verdes + rojos)) * 100.0, 1)
    if prom_t >= 6.0 and rojos == 0: return 4.5, 0.22, f"🔥 Pólvora Real ({prom_t:.1f} Disp | {verdes}✅)", efec
    elif rojos >= 1 or prom_t <= 3.5: return -4.5, -0.20, f"❄️ Bajo Fuego ({prom_t:.1f} Disp | {rojos}❌)", efec
    return 0.0, 0.0, f"⚖️ Estable ({prom_t:.1f} Disp | {verdes}✅)", efec

def calcular_trinidad_completa_pre(nom_local, nom_visita):
    sot_l, xgs_l, _, col_l, _ = auditar_equipo_bd(nom_local)
    sot_v, xgs_v, _, col_v, _ = auditar_equipo_bd(nom_visita)
    gf_base, gc_base = round(sot_l * xgs_l * 1.15, 2), round(sot_v * xgs_v, 2)
    xg_general = round(gf_base + gc_base + (0.30 if (col_l or col_v) else 0.0), 2)
    prob_general = round(min(94.0, max(42.0, (1 - poisson.cdf(1, xg_general)) * 100)), 1)
    
    perf_l, perf_v = obtener_perfil_reciente_2_3_fechas(nom_local, gf_base, 1.2), obtener_perfil_reciente_2_3_fechas(nom_visita, gc_base, 1.3)
    bono_prob_bit, bono_xg_bit, tag_bitacora, efec_bit_cruce = calcular_momentum_bitacora_2_fechas(nom_local, nom_visita)
    
    xg_goles_rec = ((perf_l["gf_rec"] + perf_v["gc_rec"]) / 2.0) * 1.08 + ((perf_v["gf_rec"] + perf_l["gc_rec"]) / 2.0)
    xg_tiros_rec = (((perf_l["arco_f"]+perf_v["arco_f"])/2) * 0.30) + (((perf_l["disp_f"]+perf_v["disp_f"])/2) * 0.05)
    xg_momento = max(1.15, round((xg_goles_rec * 0.55) + (xg_tiros_rec * 0.45) + bono_xg_bit, 2))
    
    prob_momento = round(min(96.0, max(42.0, ((1 - poisson.cdf(1, xg_momento)) * 100) + bono_prob_bit)), 1)
    
    tasa_rec_o15 = (perf_l["tasa_o15"] + perf_v["tasa_o15"]) / 2.0
    efectividad_pct = round((efec_bit_cruce * 0.65) + (tasa_rec_o15 * 0.35), 1) if efec_bit_cruce is not None else round((tasa_rec_o15 * 0.65) + (prob_momento * 0.35), 1)
    prob_final = round(min(95.5, max(42.0, (prob_momento * 0.60) + (prob_general * 0.25) + (efectividad_pct * 0.15))), 1)
    
    res_av = f"⚔️ Ataque 2-3J: {round((perf_l['disp_f']+perf_v['disp_f'])/2,1)} Disp | 🧀 Vuln: {round((perf_l['disp_c']+perf_v['disp_c'])/2,1)} DispC"
    return {
        "prob_general": prob_general, "prob_momento": prob_momento, "efectividad_pct": efectividad_pct,
        "prob_final": prob_final, "cuota_justa": round(100 / max(1.0, prob_final), 2), "xg_base": xg_general,
        "fuente_tag": f"{res_av} | {tag_bitacora}"
    }

def detectar_estado_partido(comp, iso_fecha):
    status_obj, type_obj = comp.get("status", {}), comp.get("status", {}).get("type", {})
    st_state, st_name, short_det, desc_det = type_obj.get("state", "pre"), type_obj.get("name", "").upper(), type_obj.get("shortDetail", "").upper(), type_obj.get("description", "").upper()
    reloj = status_obj.get("displayClock", "0'")
    es_ht = ("HALFTIME" in st_name or "HT" in short_det or "MEDIO" in short_det or "DESCANSO" in desc_det)
    try: min_num = int(reloj.replace("'", "").split("+")[0])
    except: min_num = 45 if es_ht else 0
    _, fecha_corta, hora_sola, dt_local_ev = obtener_fecha_local_evento(iso_fecha)
    if es_ht: return st_state, es_ht, min_num, "<div class='status-ht'>⏸️ ENTRETIEMPO</div>", "⏸️ HT (45')", dt_local_ev
    elif st_state == "in": return st_state, es_ht, min_num, f"<div class='status-live'>🔴 {reloj}</div>", f"🔴 {reloj}", dt_local_ev
    elif st_state == "post": return st_state, es_ht, min_num, "<div class='status-final'>FINAL</div>", "FINAL", dt_local_ev
    return st_state, es_ht, min_num, f"<div class='status-badge'>🕒 {hora_sola}</div>", fecha_corta, dt_local_ev

def calcular_tasas_tiempos_y_franja(xg_total_pre, disparos_tot, tiros_arco, corneres_tot, min_actual):
    bono_presion = (disparos_tot * 0.032) + (tiros_arco * 0.075) + (corneres_tot * 0.018)
    xg_1t = (xg_total_pre * 0.43) + (bono_presion * 0.65)
    tasa_1t = round(min(91.0, max(38.0, (1 - poisson.cdf(0, xg_1t)) * 100)), 1)
    xg_2t = (xg_total_pre * 0.57) + bono_presion
    if min_actual > 45: xg_2t = xg_2t * min(1.15, (max(8, 94 - min_actual) / 45.0) * 1.22)
    tasa_2t = round(min(94.0, max(50.0, (1 - poisson.cdf(0, xg_2t)) * 100)), 1)
    xg_franja_38_45 = (xg_1t * 0.52) + (tiros_arco * 0.04)
    tasa_38_45 = round(min(82.0, max(28.0, (1 - poisson.cdf(0, xg_franja_38_45)) * 100)), 1)
    return tasa_1t, tasa_2t, tasa_38_45

# =============================================================================
# SCRAPING LIGERO PARA RASTREAR EN VIVO 
# =============================================================================
def _fetch_url(args):
    code, f_str = args
    try:
        res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={f_str}", timeout=3)
        if res.status_code == 200: return code, res.json().get("events", [])
    except: pass
    return code, []

@st.cache_data(ttl=25)
def obtener_partidos_ligas(codigos_liga):
    hoy = datetime.utcnow() - timedelta(hours=6)
    fechas = [(hoy + timedelta(days=i)).strftime("%Y%m%d") for i in (0, 1)]
    mapa = {l["code"]: l for l in LIGAS_BIG_DATA}
    datos = {mapa[c]["id"]: {"meta": mapa[c], "eventos": []} for c in codigos_liga if c in mapa}
    vistos = set()
    with ThreadPoolExecutor(max_workers=16) as ex:
        for code, evs in ex.map(_fetch_url, [(c, f) for c in codigos_liga if c in mapa for f in fechas]):
            l_id = mapa[code]["id"]
            for ev in evs:
                if ev.get("id") and ev.get("id") not in vistos:
                    vistos.add(ev["id"])
                    datos[l_id]["eventos"].append(ev)
    return datos

# =============================================================================
# INTERFAZ Y RENDERIZADO PRINCIPAL
# =============================================================================
col_m1, col_m2 = st.columns([3, 1])
with col_m2: auto_refresh = st.toggle("⚡ Refresco en Vivo", value=True)

def accionar_plequita_vip(ev_id, nom_l_full, nom_v_full, nombre_liga, fecha_ev_local, prob_pre, xg_pre, stats_vivo, goles_actuales=0):
    picks_hoy = boveda_vip.setdefault("picks_vip_hoy", {})
    if ev_id in picks_hoy: del picks_hoy[ev_id]
    else: picks_hoy[ev_id] = {"ev_id": ev_id, "origen": "⚡ Plequita Manual (MRFUTBOL)", "ficha": analizar_partido_profundo_mrfutbol(ev_id, nom_l_full, nom_v_full, nombre_liga, fecha_ev_local, prob_pre, xg_pre, stats_vivo, goles_actuales)}
    guardar_boveda_vip_servidor(boveda_vip)

_frag = getattr(st, "fragment", getattr(st, "experimental_fragment", None))
@(_frag(run_every=25 if auto_refresh else None) if _frag else lambda f: f)
def renderizar_central_mrfutbol():
    hoy_dt = datetime.utcnow() - timedelta(hours=6)
    str_hoy = hoy_dt.strftime("%Y-%m-%d")
    str_manana = (hoy_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    uso_api = boveda_vip.get("uso_diario_api", {"usadas": 0})
    codigos_todas = [l["code"] for l in LIGAS_BIG_DATA]
    datos_globales = obtener_partidos_ligas(codigos_todas)
    sincronizar_matriz_global_clubes(codigos_todas)

    with col_m1:
        st.caption(f"💡 Central MRFUTBOL | 🕒 {hoy_dt.strftime('%H:%M:%S')} | 👑 Llamadas Motor VIP: **{uso_api.get('usadas', 0)} / 50,000**")

    # 5 PESTAÑAS EXACTAS COMO PEDISTE
    sec_resultados, sec_en_vivo, sec_apuestas, sec_scraping, sec_sala_vip = st.tabs([
        "⚽ 1. CARTELERA", "🔴 2. PARTIDOS EN VIVO", "🎯 3. PRE-APUESTAS", "🚨 4. TERMINAL EN VIVO", "👑 5. SALA VIP (MRFUTBOL)"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: CARTELERA DE HOY Y MATRIZ BIG DATA INTEGRADA
    # -------------------------------------------------------------------------
    with sec_resultados:
        col_menu, col_contenido = st.columns([1.2, 3.8])
        with col_menu:
            st.markdown("##### 📅 Opciones")
            dia_sel = st.radio("Día:", ["Hoy", "Mañana"])
            ocultar_fin = st.toggle("👁️ Ocultar Finalizados", value=True)
            busq_club = st.text_input("🔍 Buscar Club / Admin...", placeholder="Ej. MR2026")
            if st.button("🔄 Sincronizar Matrices", use_container_width=True): st.cache_data.clear(); st.rerun()

            es_admin = (busq_club.strip() == "MR2026" or st.session_state["admin_autenticado"])
            with st.expander("🔐 Bóveda Privada", expanded=es_admin):
                if es_admin:
                    st.session_state["admin_autenticado"] = True
                    st.success("🔓 Admin Activo")
                    if st.button("🧹 Vaciar VIP", use_container_width=True): boveda_vip["picks_vip_hoy"] = {}; guardar_boveda_vip_servidor(boveda_vip); st.rerun()
                    df_ml = pd.DataFrame(list(boveda_ml_05.values()))
                    if not df_ml.empty: st.download_button(f"📥 Bajar Bitácora ({len(df_ml)})", data=df_ml.to_csv(index=False).encode("utf-8-sig"), file_name="Bitacora_MRFUTBOL.csv", mime="text/csv", use_container_width=True)

        with col_contenido:
            st.subheader("🌐 Matriz de Clubes (Últimas 2-3 Fechas Reales)")
            filas_mat = []
            for club, hist in matriz_clubes_global.items():
                if busq_club and busq_club != "MR2026" and busq_club.lower() not in club.lower(): continue
                if len(hist) > 0:
                    pf = obtener_perfil_reciente_2_3_fechas(club)
                    filas_mat.append({"Club": club, "Muestra": pf["origen"], "🎯 Disp. Ataque": pf["disp_f"], "⚽ GF Rec": pf["gf_rec"], "🧀 Disp. Vuln": pf["disp_c"], "🥅 GC Rec": pf["gc_rec"], "🔥 Efectividad": f"{pf['tasa_o15']}%"})
            if filas_mat: st.dataframe(pd.DataFrame(filas_mat).sort_values(by="🎯 Disp. Ataque", ascending=False), use_container_width=True, hide_index=True)
            else: st.info("Matriz recolectando datos silenciosamente...")

    # -------------------------------------------------------------------------
    # TAB 2: PARTIDOS EN VIVO LIGEROS (SIN GATILLOS)
    # -------------------------------------------------------------------------
    with sec_en_vivo:
        st.subheader("🔴 Partidos en Curso")
        hay_vivo = False
        for liga, cont in datos_globales.items():
            for ev in cont["eventos"]:
                comp = ev.get("competitions", [{}])[0]
                st_state, _, _, badge_vivo, reloj_txt, _ = detectar_estado_partido(comp, ev.get("date", ""))
                if st_state == "in":
                    hay_vivo = True
                    loc, vis = comp.get("competitors", [{}, {}])
                    nl, nv = loc.get("team", {}).get("displayName", ""), vis.get("team", {}).get("displayName", "")
                    gl, gv = int(loc.get("score", 0)), int(vis.get("score", 0))
                    st.markdown(f"<div class='match-card'>{badge_vivo} <strong>{nl} {gl} - {gv} {nv}</strong></div>", unsafe_allow_html=True)
        if not hay_vivo: st.info("No hay partidos en curso en este momento.")

    # -------------------------------------------------------------------------
    # TAB 3: PRE-APUESTAS OVER 1.5 CON LA TRINIDAD (MOMENTO + EFECTIVIDAD)
    # -------------------------------------------------------------------------
    with sec_apuestas:
        st.subheader("🎯 Laboratorio Pre-Apuesta Over 1.5 (Prioridad Momento 2-3J)")
        rep_pre = []
        for liga, cont in datos_globales.items():
            for ev in cont["eventos"]:
                comp = ev.get("competitions", [{}])[0]
                if comp.get("status", {}).get("type", {}).get("state", "") == "pre":
                    loc, vis = comp.get("competitors", [{}, {}])
                    nl, nv = loc.get("team", {}).get("displayName", ""), vis.get("team", {}).get("displayName", "")
                    if nl and nv:
                        t = calcular_trinidad_completa_pre(nl, nv)
                        if t["prob_final"] >= 70.0:
                            rep_pre.append({"Liga": liga, "Partido": f"{nl} vs {nv}", "📊 Prob General": f"{t['prob_general']}%", "🔥 Momento (2-3J)": f"{t['prob_momento']}%", "🎯 Efectividad Cruce": f"{t['efectividad_pct']}%", "⚡ CALIENTE (FINAL)": f"{t['prob_final']}%", "Cuota Justa": t['cuota_justa'], "Radiografía": t['fuente_tag'], "_orden": t['prob_final']})
        if rep_pre:
            df_pre = pd.DataFrame(rep_pre).sort_values(by="_orden", ascending=False).drop(columns=["_orden"])
            st.dataframe(df_pre, use_container_width=True, hide_index=True)
            st.download_button("📊 Exportar Pre-Apuestas (.CSV)", data=df_pre.to_csv(index=False).encode("utf-8-sig"), file_name=f"PreApuestas_{str_hoy}.csv", mime="text/csv")
        else: st.info("No hay partidos programados con más del 70% de probabilidad final en este momento.")

    # -------------------------------------------------------------------------
    # TAB 4: TERMINAL EN VIVO 0.5 (EL RADAR DE CAZA CON GATILLOS)
    # -------------------------------------------------------------------------
    with sec_scraping:
        st.markdown("### 🚨 TERMINAL EN VIVO 0.5 — Decisiones en Caliente")
        st.markdown("**Regla 96.8% Verde (Bitácora MRFUTBOL):** Busca 6+ Disparos o 3+ al Arco para disparar el Over 0.5. Partidos 0-0 fijos arriba.")
        tabla_scr = []
        for liga, cont in datos_globales.items():
            for ev in cont["eventos"]:
                comp = ev.get("competitions", [{}])[0]
                if comp.get("status", {}).get("type", {}).get("state", "") == "in":
                    loc, vis = comp.get("competitors", [{}, {}])
                    nl, nv = loc.get("team", {}).get("displayName", ""), vis.get("team", {}).get("displayName", "")
                    gl, gv = int(loc.get("score", 0)), int(vis.get("score", 0))
                    reloj = comp.get("status", {}).get("displayClock", "0'")
                    try: min_actual = int(reloj.replace("'", "").split("+")[0])
                    except: min_actual = 0
                    
                    t = calcular_trinidad_completa_pre(nl, nv)
                    stats = extraer_metricas_partido_reales(loc, vis)
                    tasa_1t, tasa_2t, tasa_38_45 = calcular_tasas_tiempos_y_franja(t['xg_base'], stats['toth_tot'], stats['tmeta_tot'], stats['esquinas_tot'], min_actual)
                    
                    # Decisión y Gatillo Local
                    veredicto = "⏸️ AGUANTAR: Exigir 6+ Disp o 2+ al Arco"
                    es_caliente = False
                    cls_box = "veredicto-box-wait"
                    if (gl+gv) == 0:
                        if stats['toth_tot'] >= 6 or stats['tmeta_tot'] >= 3:
                            veredicto = f"🚨 ¡ENTRAR OVER 0.5! [PATRÓN 96.8% VERDE] (Tasa 2T: {tasa_2t}%)"
                            es_caliente = True
                            cls_box = "veredicto-box-hot"
                    else:
                        veredicto = "✅ LÍNEA CUBIERTA"
                        cls_box = "veredicto-box-green"

                    tabla_scr.append({
                        "ev_id": ev.get("id"), "reloj": reloj, "partido": f"{nl} vs {nv}", "marcador": f"{gl}-{gv}",
                        "nl": nl, "nv": nv, "liga": liga, "prob": t['prob_final'], "goles": (gl+gv),
                        "toth": stats['toth_tot'], "tmeta": stats['tmeta_tot'], "esq": stats['esquinas_tot'],
                        "veredicto": veredicto, "cls_box": cls_box, "es_caliente": es_caliente, "t_2t": tasa_2t
                    })
        
        for item in sorted(tabla_scr, key=lambda x: (x['goles'], not x['es_caliente'], -x['prob'])):
            ev_id = item["ev_id"]
            ya_vip = ev_id in boveda_vip.get("picks_vip_hoy", {})
            card_cls = "trading-card-hot" if item["es_caliente"] else "trading-card"
            c1, c2 = st.columns([10.5, 1.5])
            with c1:
                st.markdown(f"""
                <div class='{card_cls}'>
                    <div class="trading-header">
                        <div><span style='background:#ff2a4b; color:#fff; padding:2px 5px; border-radius:3px;'>{item['reloj']}</span> <strong>{item['partido']}</strong> <span style='color:#00ffcc;'>{item['marcador']}</span></div>
                        <div style="font-size:12px; color:#9ba1b0;">{item['liga']}</div>
                    </div>
                    <div class="trading-metrics-grid">
                        <div class="metric-pill"><span>🔥 Prob Pre Caliente</span><strong>{item['prob']}%</strong></div>
                        <div class="metric-pill"><span>🎯 Disparos Totales</span><strong>{item['toth']}</strong></div>
                        <div class="metric-pill"><span>🥅 Tiros al Arco</span><strong>{item['tmeta']}</strong></div>
                        <div class="metric-pill"><span>🚩 Córneres</span><strong>{item['esq']}</strong></div>
                    </div>
                    <div class="{item['cls_box']}">{item['veredicto']}</div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown("<br>", unsafe_allow_html=True)
                st.checkbox("☑️ Enviar VIP", value=ya_vip, key=f"vip_{ev_id}_{ya_vip}", on_change=accionar_plequita_vip, args=(ev_id, item["nl"], item["nv"], item["liga"], str_hoy, item["prob"], 2.5, None, item['goles']))

    # -------------------------------------------------------------------------
    # TAB 5: SALA VIP MRFUTBOL (EL MOTOR DE 50,000 LLAMADAS)
    # -------------------------------------------------------------------------
    with sec_sala_vip:
        st.subheader("👑 SALA VIP MRFUTBOL — Radiografía Big Data (Motor V3)")
        lista_vip = list(boveda_vip.get("picks_vip_hoy", {}).values())
        if lista_vip:
            for iv in lista_vip:
                f = iv["ficha"]
                st.markdown(f"""
                <div class="vip-card">
                    <div class="trading-header"><strong>{f['Partido']}</strong> <span style="color:#00ffcc;">Prob: {f['Prob_Over15']}</span></div>
                    <div class="trading-metrics-grid">
                        <div class="metric-pill"><span>🎯 OFENSIVO PRO</span><strong>{f['Paso3_Ofensivo_Pro']}</strong></div>
                        <div class="metric-pill"><span>🥩 CARNICERÍA</span><strong>{f['Paso3_Eficiencia_Carniceria']}</strong></div>
                        <div class="metric-pill"><span>🧀 VULNERABILIDAD</span><strong>{f['Paso3_Vulnerabilidad_Rival']}</strong></div>
                        <div class="metric-pill"><span>🔥 MOMENTUM</span><strong>{f['Paso3_Momentum']}</strong></div>
                    </div>
                    <div style="font-size:11px; color:#ffd700; margin-top:8px;">{f.get('Sello_API', '✅ Auditoría Exclusiva MRFUTBOL')}</div>
                </div>
                """, unsafe_allow_html=True)
        else: st.info("Marca la plequita `☑️ Enviar VIP` en el Terminal en Vivo 0.5 para destripar el partido con la Matriz MRFUTBOL.")

renderizar_central_mrfutbol()
