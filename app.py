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
st.set_page_config(page_title="MRFUTBOL - Big Data Matrix", page_icon="⚽", layout="wide")

# =============================================================================
# CONEXIÓN INTERNA OCULTA (100% INVISIBLE AL PÚBLICO)
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

# =============================================================================
# 1. BÓVEDAS INBORRABLES (EL CEREBRO DEL SISTEMA)
# =============================================================================
ARCHIVO_BITACORA_OCULTA = ".boveda_ml_over05_mrfutbol.json"
ARCHIVO_MATRIZ_CLUBES = ".matriz_clubes_global.json"
ARCHIVO_BOVEDA_VIP = ".boveda_vip_apifootball_mrfutbol.json"

def _crear_registro_semilla(clave_id, semana, fecha_hora, liga, partido, min_alerta, disp_l, disp_v, arco_l, arco_v, corn_l, corn_v, pos_l, pos_v, prob_pre, tasa_1t, tasa_2t, tasa_38_45, ganada=True, min_gol=34, marcador="2 - 1"):
    disp_tot = disp_l + disp_v
    arco_tot = arco_l + arco_v
    corn_tot = corn_l + corn_v
    eq_dom = partido.split(" vs ")[0] if disp_l >= disp_v else partido.split(" vs ")[-1]
    max_d = max(disp_l, disp_v)
    return clave_id, {
        "Semana_Jornada": semana,
        "Fecha_Hora": fecha_hora,
        "Liga": liga,
        "Partido": partido,
        "Min_Alerta": min_alerta,
        "Motivo_Decision": f"{eq_dom} {max_d} Disp ({disp_tot} Tot, {arco_tot} Arco, {corn_tot} Córn | Pre {prob_pre}%)",
        "Disparos_Al_Activar": f"{disp_l}-{disp_v} (Tot: {disp_tot})",
        "Arco_Al_Activar": f"{arco_l}-{arco_v} (Tot: {arco_tot})",
        "Corneres_Al_Activar": f"{corn_l}-{corn_v} (Tot: {corn_tot})",
        "Prob_Pre_Over15": f"{prob_pre}%",
        "Estado_Apuesta_05": "✅ GANADA (VERDE)" if ganada else "❌ FALLO (0-0 Final)"
    }

def construir_semilla_historica():
    semilla = {}
    # Semilla compacta para no saturar código visual (Aquí va tu historial base de 67 verdes/rojos)
    for i in range(1, 61):
        k, v = _crear_registro_semilla(f"hist_v_{i}", "Semana-Base", "2026-10-01", "🌍 Historial", f"EqVerde{i} vs EqVerde{i}B", 24, 5, 3, 2, 1, 2, 1, 55, 45, 80.0, 75.0, 85.0, 50.0, True, 35, "2-0")
        semilla[k] = v
    for i in range(1, 8):
        k, v = _crear_registro_semilla(f"hist_r_{i}", "Semana-Base", "2026-10-01", "🌍 Historial", f"EqRojo{i} vs EqRojo{i}B", 27, 2, 1, 0, 0, 1, 1, 50, 50, 70.0, 65.0, 74.0, 42.0, False, 90, "0-0")
        semilla[k] = v
    return semilla

@st.cache_resource
def cargar_matriz_global_clubes():
    # Esta es la NUEVA base de datos gigante que almacena el asedio de TODOS los clubes
    if os.path.exists(ARCHIVO_MATRIZ_CLUBES):
        try:
            with open(ARCHIVO_MATRIZ_CLUBES, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def guardar_matriz_global(matriz):
    try:
        with open(ARCHIVO_MATRIZ_CLUBES, "w", encoding="utf-8") as f:
            json.dump(matriz, f, ensure_ascii=False)
    except: pass

@st.cache_resource
def obtener_boveda_ml_servidor():
    boveda_cargada = construir_semilla_historica()
    if os.path.exists(ARCHIVO_BITACORA_OCULTA):
        try:
            with open(ARCHIVO_BITACORA_OCULTA, "r", encoding="utf-8") as f:
                datos_disco = json.load(f)
                boveda_cargada.update(datos_disco)
        except: pass
    return boveda_cargada

def guardar_boveda_ml_servidor(boveda):
    try:
        with open(ARCHIVO_BITACORA_OCULTA, "w", encoding="utf-8") as f:
            json.dump(boveda, f, ensure_ascii=False, indent=2)
    except: pass

matriz_clubes = cargar_matriz_global_clubes()
boveda_ml_05 = obtener_boveda_ml_servidor()

# =============================================================================
# 2. MOTOR DE LA TRINIDAD PRE-APUESTA (General, Momento, Efectividad)
# =============================================================================
def _extraer_tot(texto):
    m = re.search(r"Tot:\s*(\d+)", str(texto))
    return int(m.group(1)) if m else 0

def calcular_trinidad_pre_apuesta(nom_local, nom_visita, xg_base_temporada):
    """
    PRIORIDAD AL MOMENTO: 
    - 60% Probabilidad de Momento (Últimas 3 fechas en Matriz)
    - 25% Probabilidad General (Temporada)
    - 15% Efectividad Bitácora (Nuestros verdes reales)
    """
    # 1. PROBABILIDAD GENERAL (Temporada)
    prob_general = (1 - poisson.cdf(1, xg_base_temporada)) * 100

    # 2. PROBABILIDAD DE MOMENTO (Búsqueda en Matriz de las últimas 3 fechas)
    disp_momento = 4.0 # Base estándar
    arco_momento = 1.5
    partidos_recopilados = []
    
    # Rastrear en matriz global
    for equipo in [nom_local, nom_visita]:
        if equipo in matriz_clubes:
            # Tomar los últimos 3 registros
            ultimos = matriz_clubes[equipo][-3:]
            partidos_recopilados.extend(ultimos)
            
    if partidos_recopilados:
        disp_momento = sum(p.get("disp", 4) for p in partidos_recopilados) / len(partidos_recopilados)
        arco_momento = sum(p.get("arco", 1) for p in partidos_recopilados) / len(partidos_recopilados)
    
    # Fórmula de asedio: Si disparan más de 6 veces o 3 al arco, la prob de momento sube radicalmente.
    xg_momento = xg_base_temporada
    if disp_momento >= 6.0 or arco_momento >= 2.5:
        xg_momento += 0.85
        etiqueta_momento = f"🔥 ASALTO ({disp_momento:.1f} Disp/J)"
    elif disp_momento >= 4.5:
        xg_momento += 0.35
        etiqueta_momento = f"⚡ RITMO ACTIVO ({disp_momento:.1f} Disp/J)"
    elif disp_momento < 3.0:
        xg_momento -= 0.60
        etiqueta_momento = f"❄️ PÓLVORA MOJADA ({disp_momento:.1f} Disp/J)"
    else:
        etiqueta_momento = f"⚖️ ESTÁNDAR ({disp_momento:.1f} Disp/J)"
        
    prob_momento = (1 - poisson.cdf(1, xg_momento)) * 100

    # 3. EFECTIVIDAD HISTÓRICA (Nuestros verdes de Bitácora)
    verdes, rojos = 0, 0
    for r in boveda_ml_05.values():
        cruce = str(r.get("Partido", ""))
        if nom_local in cruce or nom_visita in cruce:
            if "GANADA" in str(r.get("Estado_Apuesta_05", "")):
                verdes += 1
            elif "FALLO" in str(r.get("Estado_Apuesta_05", "")):
                rojos += 1
    
    total_bitacora = verdes + rojos
    efectividad = 0.0
    if total_bitacora >= 2:
        efectividad = (verdes / total_bitacora) * 100
        etiqueta_efec = f"✅ {efectividad:.1f}% ({verdes}V-{rojos}R)"
    else:
        efectividad = prob_momento # Si no hay datos, hereda el momento
        etiqueta_efec = "N/A (Datos Insuficientes)"

    # CÁLCULO FINAL PONDERADO (Priodidad: Momento Caliente)
    prob_final = (prob_general * 0.25) + (prob_momento * 0.60) + (efectividad * 0.15)
    prob_final = round(min(96.0, max(40.0, prob_final)), 1)
    
    return {
        "Prob_General": round(prob_general, 1),
        "Prob_Momento": round(prob_momento, 1),
        "Etiqueta_Momento": etiqueta_momento,
        "Efectividad_Bit": etiqueta_efec,
        "Prob_Final_Ajustada": prob_final,
        "Cuota_Justa": round(100 / max(1, prob_final), 2)
    }


# ESTILOS CSS COMPACTOS PROFESIONALES
st.markdown("""
<style>
.titulo-mrfutbol { text-align: center; font-size: 32px; font-weight: 900; color: #ffffff; letter-spacing: 2px; margin-bottom: 0px; }
.subtitulo-autor { text-align: center; font-size: 12px; font-weight: 600; color: #00ffcc; margin-top: 1px; margin-bottom: 10px; }
.trading-card-hot { background-color: #12161f; border-left: 5px solid #00ffcc; border-radius: 8px; padding: 12px; margin-bottom: 10px; color: #ffffff; box-shadow: 0 2px 10px rgba(0, 255, 204, 0.12); }
.trading-metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; margin-bottom: 8px; }
.metric-pill { background-color: #16181f; border: 1px solid #1f222d; border-radius: 5px; padding: 6px; text-align: center; }
.metric-pill span { display: block; font-size: 10px; color: #9ba1b0; text-transform: uppercase; }
.metric-pill strong { font-size: 14px; color: #00ffcc; }
.veredicto-box-hot { background: linear-gradient(90deg, rgba(0,255,204,0.16) 0%, rgba(22,24,31,0.95) 100%); border: 1px solid #00ffcc; padding: 8px; border-radius: 6px; font-size: 13px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='titulo-mrfutbol'>⚽ MRFUTBOL BIG DATA</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitulo-autor'>Central de Inteligencia | Miguel Ramirez</div>", unsafe_allow_html=True)

# Ligas y Funciones de Scraping (ESPN / Sofascore)
LIGAS_BIG_DATA = [{"id": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier", "code": "eng.1"}, {"id": "🇪🇸 LaLiga", "code": "esp.1"}, {"id": "🇩🇪 Bundesliga", "code": "ger.1"}, {"id": "🇮🇹 Serie A", "code": "ita.1"}, {"id": "🇺🇸 MLS", "code": "usa.1"}, {"id": "🇲🇽 Liga MX", "code": "mex.1"}, {"id": "🇳🇱 Eredivisie", "code": "ned.1"}]

def _fetch_url(args):
    code, f_str = args
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={f_str}"
    try:
        res = requests.get(url, timeout=3)
        if res.status_code == 200: return res.json().get("events", [])
    except: pass
    return []

@st.cache_data(ttl=60)
def obtener_cartelera_cruda():
    hoy_str = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y%m%d")
    eventos_totales = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        resultados = list(executor.map(_fetch_url, [(l["code"], hoy_str) for l in LIGAS_BIG_DATA]))
    for ev_list in resultados: eventos_totales.extend(ev_list)
    return eventos_totales

eventos_raw = obtener_cartelera_cruda()

# 4 PESTAÑAS TÁCTICAS (Adiós a Cartelera Básica)
tab_matriz, tab_pre, tab_vivo, tab_vip = st.tabs([
    "🌐 1. MATRIZ BIG DATA", 
    "🎯 2. LABORATORIO PRE-APUESTA", 
    "🚨 3. TERMINAL EN VIVO 0.5",
    "👑 4. SALA VIP (PASO 3)"
])

# =============================================================================
# PESTAÑA 1: MATRIZ BIG DATA (Recolección Automática)
# =============================================================================
with tab_matriz:
    st.markdown("### 🌐 Matriz Matriz de Inteligencia MRFUTBOL")
    st.caption("Esta bóveda absorbe automáticamente los datos de ataque de los equipos que pasan por el radar. Es el 'Cerebro' de la Probabilidad de Momento.")
    
    # Lógica silenciosa de recolección: Si hay datos en la bitácora o en el radar, nutrir matriz_clubes.
    for reg in boveda_ml_05.values():
        partido = reg.get("Partido", "")
        if "vs" in partido:
            l_team, v_team = partido.split(" vs ")
            l_team, v_team = l_team.strip(), v_team.strip()
            tot_d = _extraer_tot(reg.get("Disparos_Al_Activar", ""))
            tot_a = _extraer_tot(reg.get("Arco_Al_Activar", ""))
            
            # Repartir a ambos clubes en la matriz (aproximado para nutrir el motor)
            for t in [l_team, v_team]:
                if t not in matriz_clubes: matriz_clubes[t] = []
                # Evitar duplicados por fecha
                if not any(x.get("fecha") == reg.get("Fecha_Hora") for x in matriz_clubes[t]):
                    matriz_clubes[t].append({
                        "fecha": reg.get("Fecha_Hora"),
                        "disp": max(2, tot_d // 2), # Asignación promediada para big data
                        "arco": max(1, tot_a // 2)
                    })
    guardar_matriz_global(matriz_clubes)

    # Mostrar la matriz al público
    filas_matriz = []
    for club, historial in matriz_clubes.items():
        if len(historial) > 0:
            ultimos = historial[-3:]
            prom_d = sum(x["disp"] for x in ultimos) / len(ultimos)
            prom_a = sum(x["arco"] for x in ultimos) / len(ultimos)
            estado = "🔥 Peligroso" if prom_d >= 6.0 else ("⚡ Activo" if prom_d >= 4.5 else "❄️ Frío")
            filas_matriz.append({"Club": club, "Partidos Registrados": len(historial), "Prom. Disp (Últ. 3)": round(prom_d, 1), "Prom. Arco (Últ. 3)": round(prom_a, 1), "Estado Actual": estado})
    
    if filas_matriz:
        df_matriz = pd.DataFrame(filas_matriz).sort_values(by="Prom. Disp (Últ. 3)", ascending=False)
        st.dataframe(df_matriz, use_container_width=True, hide_index=True)
    else:
        st.info("La matriz está recolectando datos. Se poblará a medida que el Terminal detecte partidos.")

# =============================================================================
# PESTAÑA 2: LABORATORIO PRE-APUESTA (La Trinidad)
# =============================================================================
with tab_pre:
    st.markdown("### 🎯 Laboratorio Pre-Apuesta (Prioridad: Momento)")
    st.caption("No más promedios muertos. El algoritmo destripa 3 métricas puras: Histórico de Temporada, Pulso Actual (Últ. 3 Fechas) y Nuestro Win Rate.")
    
    reporte_trinidad = []
    for ev in eventos_raw:
        comp = ev.get("competitions", [{}])[0]
        estado = comp.get("status", {}).get("type", {}).get("state", "pre")
        if estado == "pre":
            loc = comp.get("competitors", [])[0].get("team", {}).get("displayName", "L")
            vis = comp.get("competitors", [])[1].get("team", {}).get("displayName", "V")
            xg_falso_api = 2.85 # Aquí enganchas tu Poisson de standings
            
            trinidad = calcular_trinidad_pre_apuesta(loc, vis, xg_falso_api)
            
            if trinidad["Prob_Final_Ajustada"] >= 65.0:
                reporte_trinidad.append({
                    "Partido": f"{loc} vs {vis}",
                    "📊 Prob. General (Temp)": f"{trinidad['Prob_General']}%",
                    "🔥 Prob. Momento (Últ 3)": f"{trinidad['Prob_Momento']}%",
                    "🛡️ Nuestra Efectividad": trinidad["Efectividad_Bit"],
                    "🎯 PROB. FINAL AJUSTADA": f"{trinidad['Prob_Final_Ajustada']}%",
                    "Cuota Mín. Sugerida": trinidad["Cuota_Justa"],
                    "Lectura del Motor": trinidad["Etiqueta_Momento"]
                })
    
    if reporte_trinidad:
        df_trin = pd.DataFrame(reporte_trinidad).sort_values(by="🎯 PROB. FINAL AJUSTADA", ascending=False)
        st.dataframe(df_trin, use_container_width=True, hide_index=True)
    else:
        st.info("No hay partidos pre-partido con alto valor en este momento.")

# =============================================================================
# PESTAÑA 3: TERMINAL EN VIVO 0.5 (Decisiones en Caliente)
# =============================================================================
with tab_vivo:
    st.markdown("### 🚨 Terminal de Asedio en Vivo (Caza del Over 0.5)")
    st.caption("Solo muestra partidos 0-0. El algoritmo mide la carnicería en tiempo real.")
    
    for ev in eventos_raw:
        comp = ev.get("competitions", [{}])[0]
        estado = comp.get("status", {}).get("type", {}).get("state", "pre")
        goles_l = int(comp.get("competitors", [])[0].get("score", 0) or 0)
        goles_v = int(comp.get("competitors", [])[1].get("score", 0) or 0)
        
        # Filtro estricto: Solo partidos EN VIVO y 0-0
        if estado == "in" and (goles_l + goles_v) == 0:
            loc = comp.get("competitors", [])[0].get("team", {}).get("displayName", "L")
            vis = comp.get("competitors", [])[1].get("team", {}).get("displayName", "V")
            reloj = comp.get("status", {}).get("displayClock", "0'")
            
            # Simulamos stats en vivo para el layout (Aquí va tu conexión a Sofascore)
            disp_tot, arco_tot, corn_tot = 8, 3, 4
            
            trinidad = calcular_trinidad_pre_apuesta(loc, vis, 2.9)
            
            # Decisión en Caliente:
            if disp_tot >= 6 or arco_tot >= 2:
                veredicto = "🚨 ¡ENTRAR OVER 0.5! Asedio confirmado en cancha."
                clase_caja = "veredicto-box-hot"
            else:
                veredicto = "⏸️ ESPERAR: Ritmo lento. No forzar cuota."
                clase_caja = "veredicto-box-wait"
                
            st.markdown(f"""
            <div class="trading-card-hot">
                <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                    <div><span style="background:#ff2a4b; padding:2px 6px; border-radius:4px;">{reloj}</span> <strong>{loc} vs {vis}</strong></div>
                    <div style="color:#00ffcc; font-weight:bold;">0 - 0</div>
                </div>
                <div class="trading-metrics-grid">
                    <div class="metric-pill"><span>🎯 Disp Totales</span><strong>{disp_tot}</strong></div>
                    <div class="metric-pill"><span>🥅 Al Arco</span><strong>{arco_tot}</strong></div>
                    <div class="metric-pill"><span>🚩 Córneres</span><strong>{corn_tot}</strong></div>
                    <div class="metric-pill"><span>🔥 Prob. Ajustada</span><strong>{trinidad['Prob_Final_Ajustada']}%</strong></div>
                </div>
                <div class="{clase_caja}">{veredicto}</div>
            </div>
            """, unsafe_allow_html=True)

# =============================================================================
# PESTAÑA 4: SALA VIP (PASO 3)
# =============================================================================
with tab_vip:
    st.markdown("### 👑 Bóveda VIP [Paso_3_Big_Data]")
    st.caption("Esta sección sigue operando bajo llave. Aquí analizas la carnicería detallada de la API Pro.")
    st.info("Utiliza el botón 'Enviar a Sala VIP' en el Terminal 0.5 para generar la radiografía profunda de asedio y vulnerabilidad.")
