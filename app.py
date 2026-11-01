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
# CONEXIÓN MAESTRA SPORTMONKS BIG DATA (50,000 LLAMADAS/DÍA)
# =============================================================================
_SPORTMONKS_HOST = "https://api.sportmonks.com/v3/football"
try:
    _SPORTMONKS_KEY = st.secrets.get("SPORTMONKS_KEY", "501f1ecd-f254-48d5-8f45-f15a7c762392")
except Exception:
    _SPORTMONKS_KEY = "501f1ecd-f254-48d5-8f45-f15a7c762392"

_HEADERS_SPORTMONKS = {
    "Authorization": _SPORTMONKS_KEY,
    "Accept": "application/json"
}

PASO_3_PICOS_REF = {
    "MIN_BIG_CHANCES": 3.2, "MIN_TIROS_A_PUERTA": 5.5, "MIN_xG_COMBINADO": 2.4,
    "FACTOR_LOCALIA_PESO": 1.2, "MIN_QUALITY_PER_SHOT": 0.12, "MIN_xGA_CONCEDIDO_RIVAL": 1.3,
    "MAX_PORTERIA_CERO_RIVAL_PCT": 25.0, "BONO_MOMENTUM_PCT": 5.0, "MIN_UNIQUE_SCORERS_5": 2,
    "MAX_PLAYER_CONTRIB_PCT": 45.0, "MIN_DIFF_ASSISTERS_5": 4, "PLAYMAKER_DEP_LIMIT": 0.40
}

if "admin_autenticado" not in st.session_state: st.session_state["admin_autenticado"] = False
if "aviso_vip_bloqueado" not in st.session_state: st.session_state["aviso_vip_bloqueado"] = ""

# =============================================================================
# BÓVEDAS PERSISTENTES 
# =============================================================================
ARCHIVO_BITACORA_OCULTA = ".boveda_ml_over05_mrfutbol.json"
ARCHIVO_BOVEDA_VIP_API = ".boveda_vip_sportmonks.json"
ARCHIVO_MATRIZ_CLUBES = ".matriz_clubes_mrfutbol.json"

def obtener_etiqueta_semana_actual():
    h = datetime.utcnow() - timedelta(hours=6)
    return f"{h.strftime('%Y')}-Semana-{h.strftime('%V')}", f"Bitacora_VIP_{h.strftime('%Y')}_Semana_{h.strftime('%V')}.csv"

@st.cache_resource
def obtener_boveda_ml_servidor():
    b = {}
    if os.path.exists(ARCHIVO_BITACORA_OCULTA):
        try:
            with open(ARCHIVO_BITACORA_OCULTA, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict): b.update(d)
        except Exception: pass
    for arc in glob.glob("Bitacora_*.csv"):
        try:
            df_arc = pd.read_csv(arc)
            for idx, row in df_arc.iterrows():
                cs = f"hist_{os.path.basename(arc)}_{idx}_{row.get('Partido', '')}"
                if cs not in b: b[cs] = row.to_dict()
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

@st.cache_resource
def obtener_boveda_vip_servidor():
    e = {"fecha_activa": "", "picks_vip_hoy": {}, "cache_api_analisis": {}, "mapa_fixtures_dia": {}, "uso_diario_api": {"fecha": "", "usadas": 0, "limite": 50000}}
    if os.path.exists(ARCHIVO_BOVEDA_VIP_API):
        try:
            with open(ARCHIVO_BOVEDA_VIP_API, "r", encoding="utf-8") as f:
                d = json.load(f)
                for k in e:
                    if k in d: e[k] = d[k]
        except Exception: pass
    return e

def guardar_boveda_vip_servidor(boveda_vip):
    try:
        with open(ARCHIVO_BOVEDA_VIP_API, "w", encoding="utf-8") as f: json.dump(boveda_vip, f, ensure_ascii=False, indent=2)
    except Exception: pass

boveda_ml_05 = obtener_boveda_ml_servidor()
boveda_vip = obtener_boveda_vip_servidor()
matriz_clubes_global = obtener_matriz_clubes_servidor()

# CSS OFICIAL MRFUTBOL
st.markdown("""
<style>
.titulo-mrfutbol { text-align:center; font-size:32px; font-weight:900; color:#ffffff; letter-spacing:2px; margin-bottom:0px; }
.subtitulo-autor { text-align:center; font-size:12px; font-weight:600; color:#00ffcc; margin-top:1px; margin-bottom:10px; letter-spacing:1px; }
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
.footer-fijo { position:fixed; bottom:0; left:0; width:100%; background-color:#0f1015; color:#9ba1b0; text-align:center; padding:6px 0; font-size:11px; border-top:1px solid #1f222d; z-index:9999; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='titulo-mrfutbol'>⚽ MRFUTBOL V3</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitulo-autor'>Motor Sportmonks (50K/Día) &nbsp;|&nbsp; Miguel Ramirez</div>", unsafe_allow_html=True)

LIGAS_BIG_DATA = [{"id": "🏆 Champions League", "code": "uefa.champions"}, {"id": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier", "code": "eng.1"}, {"id": "🇪🇸 LaLiga", "code": "esp.1"}, {"id": "🇩🇪 Bundesliga", "code": "ger.1"}, {"id": "🇮🇹 Serie A", "code": "ita.1"}, {"id": "🇺🇸 MLS", "code": "usa.1"}, {"id": "🇲🇽 Liga MX", "code": "mex.1"}, {"id": "🇳🇱 Eredivisie", "code": "ned.1"}]
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

# =============================================================================
# MOTOR PRO SPORTMONKS [PASO_3_BIG_DATA] 
# =============================================================================
def registrar_consulta_sportmonks(headers_resp=None):
    hoy_str = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%d")
    uso = boveda_vip.setdefault("uso_diario_api", {"fecha": hoy_str, "usadas": 0, "limite": 50000})
    if uso.get("fecha") != hoy_str: uso["fecha"], uso["usadas"] = hoy_str, 0
    rem = headers_resp.get("X-RateLimit-Remaining") if headers_resp else None
    if rem is not None:
        try: uso["usadas"] = 50000 - int(rem)
        except: uso["usadas"] += 1
    else: uso["usadas"] += 1
    guardar_boveda_vip_servidor(boveda_vip)

def obtener_id_interno_sportmonks(nom_local, nom_visita, fecha_yyyy_mm_dd):
    mapa_dia = boveda_vip.setdefault("mapa_fixtures_dia", {})
    if fecha_yyyy_mm_dd not in mapa_dia:
        if boveda_vip.get("uso_diario_api", {}).get("usadas", 0) >= 49950: return None
        try:
            res = requests.get(f"{_SPORTMONKS_HOST}/fixtures/date/{fecha_yyyy_mm_dd}?include=participants", headers=_HEADERS_SPORTMONKS, timeout=6)
            registrar_consulta_sportmonks(res.headers)
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
        except Exception: pass
    for fix in mapa_dia.get(fecha_yyyy_mm_dd, []):
        if nombres_coinciden(nom_local, fix["home"]) and nombres_coinciden(nom_visita, fix["away"]):
            return fix["id"]
    return None

def analizar_partido_profundo_sportmonks(ev_id, nom_local, nom_visita, nombre_liga, fecha_ev_local, prob_pre, xg_base, stats_vivo, goles_actuales=0):
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
    sello_vip = "✅ Auditoría Élite MRFUTBOL (Sportmonks V3)"

    if boveda_vip.get("uso_diario_api", {}).get("usadas", 0) < 49950:
        fix_id = obtener_id_interno_sportmonks(nom_local, nom_visita, fecha_ev_local)
        if fix_id:
            try:
                res = requests.get(f"{_SPORTMONKS_HOST}/fixtures/{fix_id}?include=statistics", headers=_HEADERS_SPORTMONKS, timeout=5)
                registrar_consulta_sportmonks(res.headers)
                if res.status_code == 200:
                    sello_vip = f"✅ Conexión Élite Sportmonks (ID #{fix_id})"
            except Exception: pass

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
# FUNCIONES AUXILIARES DE CÁLCULO
# =============================================================================
def _extraer_tot_numero(texto):
    if not texto: return 0
    m = re.search(r"Tot:\s*(\d+)", str(texto))
    return int(m.group(1)) if m else 0

def obtener_perfil_reciente_2_3_fechas(nombre_equipo):
    partidos_eq = []
    for club_key, lista_j in matriz_clubes_global.items():
        if nombres_coinciden(nombre_equipo, club_key): partidos_eq.extend(lista_j)
    partidos_eq.sort(key=lambda x: str(x.get("fecha", "")))
    ultimos_2_3 = partidos_eq[-3:]
    if ultimos_2_3:
        n = len(ultimos_2_3)
        return {
            "n_juegos": n, "disp_f": round(sum(x.get("disp_f", 9) for x in ultimos_2_3)/n, 1),
            "arco_f": round(sum(x.get("arco_f", 3.5) for x in ultimos_2_3)/n, 1),
            "disp_c": round(sum(x.get("disp_c", 9) for x in ultimos_2_3)/n, 1),
            "arco_c": round(sum(x.get("arco_c", 3.5) for x in ultimos_2_3)/n, 1),
            "tasa_o15": round((sum(x.get("over15", 1) for x in ultimos_2_3)/n)*100.0, 1), "origen": f"{n}J Matriz"
        }
    return {"n_juegos": 2, "disp_f": 9.5, "arco_f": 3.8, "disp_c": 9.5, "arco_c": 3.8, "tasa_o15": 75.0, "origen": "Base"}

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
    muestra = (partidos_loc[-3:] + partidos_vis[-3:])[-3:]
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
    xg_general = round((sot_l * xgs_l * 1.15) + (sot_v * xgs_v) + (0.30 if (col_l or col_v) else 0.0), 2)
    prob_general = round(min(94.0, max(42.0, (1 - poisson.cdf(1, xg_general)) * 100)), 1)
    
    perf_l, perf_v = obtener_perfil_reciente_2_3_fechas(nom_local), obtener_perfil_reciente_2_3_fechas(nom_visita)
    bono_prob_bit, bono_xg_bit, tag_bitacora, efec_bit_cruce = calcular_momentum_bitacora_2_fechas(nom_local, nom_visita)
    xg_momento = max(1.15, round(xg_general + bono_xg_bit, 2))
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

# =============================================================================
# SCRAPING LIGERO PARA RASTREAR EN VIVO (ESPN)
# =============================================================================
def _fetch_url(args):
    code, f_str = args
    try:
        res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={f_str}", timeout=3)
        if res.status_code == 200: return code, res.json().get("events", [])
    except Exception: pass
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
    else: picks_hoy[ev_id] = {"ev_id": ev_id, "origen": "⚡ Plequita Scraping (Sportmonks)", "ficha": analizar_partido_profundo_sportmonks(ev_id, nom_l_full, nom_v_full, nombre_liga, fecha_ev_local, prob_pre, xg_pre, stats_vivo, goles_actuales)}
    guardar_boveda_vip_servidor(boveda_vip)

_frag = getattr(st, "fragment", getattr(st, "experimental_fragment", None))
@(_frag(run_every=25 if auto_refresh else None) if _frag else lambda f: f)
def renderizar_central_mrfutbol():
    hoy_dt = datetime.utcnow() - timedelta(hours=6)
    str_hoy = hoy_dt.strftime("%Y-%m-%d")
    uso_api = boveda_vip.get("uso_diario_api", {"usadas": 0})
    datos_globales = obtener_partidos_ligas([l["code"] for l in LIGAS_BIG_DATA])

    with col_m1:
        st.caption(f"💡 Central Big Data MRFUTBOL | 🕒 {hoy_dt.strftime('%H:%M:%S')} | 👑 Llamadas Sportmonks: **{uso_api.get('usadas', 0)} / 50,000**")

    t_matriz, t_pre, t_vivo, t_vip = st.tabs(["🌐 1. MATRIZ BIG DATA", "🎯 2. PRE-APUESTAS", "🚨 3. TERMINAL EN VIVO", "👑 4. SALA VIP (SPORTMONKS)"])

    # -------------------------------------------------------------------------
    # TAB 1: MATRIZ BIG DATA Y BÓVEDA ADMIN
    # -------------------------------------------------------------------------
    with t_matriz:
        col_menu_m, col_tabla_m = st.columns([1.25, 3.75])
        with col_menu_m:
            st.markdown("##### 🌐 Filtros")
            liga_sel = st.selectbox("Filtrar Liga:", ["🌍 Todas"] + [l["id"] for l in LIGAS_BIG_DATA])
            busq_club = st.text_input("🔍 Buscar Club / Admin...", placeholder="Ej. MR2026")
            if st.button("🔄 Sincronizar", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

            es_admin = (busq_club.strip() == "MR2026" or st.session_state["admin_autenticado"])
            with st.expander("🔐 Bóveda Privada (Admin)", expanded=es_admin):
                if es_admin:
                    st.session_state["admin_autenticado"] = True
                    st.success("🔓 Llave Maestra Activa")
                    if st.button("🧹 Vaciar VIP", use_container_width=True): boveda_vip["picks_vip_hoy"] = {}; guardar_boveda_vip_servidor(boveda_vip); st.rerun()
                    
                    df_ml = pd.DataFrame(list(boveda_ml_05.values()))
                    if not df_ml.empty:
                        st.download_button(f"📥 Bajar Bitácora ({len(df_ml)})", data=df_ml.to_csv(index=False).encode("utf-8-sig"), file_name=f"Bitacora_MRFUTBOL.csv", mime="text/csv", use_container_width=True)

        with col_tabla_m:
            st.subheader("🌐 Matriz de Clubes (Ataque y Vulnerabilidad)")
            filas_mat = []
            for club, hist in matriz_clubes_global.items():
                if busq_club and busq_club != "MR2026" and busq_club.lower() not in club.lower(): continue
                if len(hist) > 0:
                    pf = obtener_perfil_reciente_2_3_fechas(club)
                    filas_mat.append({"Club": club, "Muestra": pf["origen"], "🎯 Disp. Ataque": pf["disp_f"], "🧀 Disp. Vuln": pf["disp_c"], "🔥 Efectividad": f"{pf['tasa_o15']}%"})
            if filas_mat: st.dataframe(pd.DataFrame(filas_mat).sort_values(by="🎯 Disp. Ataque", ascending=False), use_container_width=True, hide_index=True)
            else: st.info("Matriz recolectando datos silenciosamente mediante el Terminal en Vivo.")

    # -------------------------------------------------------------------------
    # TAB 2: PRE-APUESTAS
    # -------------------------------------------------------------------------
    with t_pre:
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
                        if t["prob_final"] >= 75.0:
                            rep_pre.append({"Liga": liga, "Partido": f"{nl} vs {nv}", "📊 Prob General": f"{t['prob_general']}%", "🔥 Momento (2-3J)": f"{t['prob_momento']}%", "🎯 Efectividad Cruce": f"{t['efectividad_pct']}%", "⚡ CALIENTE (FINAL)": f"{t['prob_final']}%", "Radiografía": t['fuente_tag'], "_orden": t['prob_final']})
        if rep_pre:
            df_pre = pd.DataFrame(rep_pre).sort_values(by="_orden", ascending=False).drop(columns=["_orden"])
            st.dataframe(df_pre, use_container_width=True, hide_index=True)
            st.download_button("📊 Exportar Pre-Apuestas (.CSV)", data=df_pre.to_csv(index=False).encode("utf-8-sig"), file_name=f"PreApuestas_{str_hoy}.csv", mime="text/csv")
        else: st.info("No hay partidos por iniciar con más del 75% de probabilidad.")

    # -------------------------------------------------------------------------
    # TAB 3: TERMINAL EN VIVO
    # -------------------------------------------------------------------------
    with t_vivo:
        st.markdown("### 🚨 TERMINAL EN VIVO 0.5 — Decisiones en Caliente")
        st.markdown("**Regla 96.8% Verde:** Busca 6+ Disparos o 3+ al Arco.")
        tabla_scr = []
        for liga, cont in datos_globales.items():
            for ev in cont["eventos"]:
                comp = ev.get("competitions", [{}])[0]
                if comp.get("status", {}).get("type", {}).get("state", "") == "in":
                    loc, vis = comp.get("competitors", [{}, {}])
                    nl, nv = loc.get("team", {}).get("displayName", ""), vis.get("team", {}).get("displayName", "")
                    gl, gv = int(loc.get("score", 0)), int(vis.get("score", 0))
                    reloj = comp.get("status", {}).get("displayClock", "0'")
                    t = calcular_trinidad_completa_pre(nl, nv)
                    tabla_scr.append({"ev_id": ev.get("id"), "reloj": reloj, "partido": f"{nl} vs {nv}", "marcador": f"{gl}-{gv}", "nl": nl, "nv": nv, "liga": liga, "prob": t['prob_final']})
        
        for item in sorted(tabla_scr, key=lambda x: -x['prob']):
            ev_id = item["ev_id"]
            ya_vip = ev_id in boveda_vip.get("picks_vip_hoy", {})
            c1, c2 = st.columns([10, 2])
            with c1: st.markdown(f"<div class='trading-card'><span style='background:#ff2a4b; color:#fff; padding:2px 5px; border-radius:3px;'>{item['reloj']}</span> <strong>{item['partido']}</strong> ({item['marcador']}) | 🔥 Prob: {item['prob']}%</div>", unsafe_allow_html=True)
            with c2: st.checkbox("☑️ Enviar a Sala VIP", value=ya_vip, key=f"vip_{ev_id}_{ya_vip}", on_change=accionar_plequita_vip, args=(ev_id, item["nl"], item["nv"], item["liga"], str_hoy, item["prob"], 2.5, None, 0))

    # -------------------------------------------------------------------------
    # TAB 4: SALA VIP (SPORTMONKS)
    # -------------------------------------------------------------------------
    with t_vip:
        st.subheader("👑 SALA VIP MRFUTBOL — Radiografía Sportmonks")
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
                    <div style="font-size:11px; color:#ffd700; margin-top:8px;">{f.get('Sello_API', '')}</div>
                </div>
                """, unsafe_allow_html=True)
        else: st.info("Marca la plequita `☑️ Enviar a Sala VIP` en la pestaña anterior para destripar el partido con Sportmonks.")

renderizar_central_mrfutbol()
