import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from scipy.stats import poisson

# Configuración de la página estilo Portal Deportivo
st.set_page_config(page_title="Portal Fútbol & Big Data - Miguel Ramirez", page_icon="⚽", layout="wide")

# Cabecera principal con tu firma
st.title("⚽ PORTAL DE FÚTBOL EUROPEO & CENTRAL BIG DATA")
st.markdown("<h2 style='text-align: center; color: #00ffcc;'>🔥 CREADO POR MIGUEL RAMIREZ 🔥</h2>", unsafe_allow_html=True)
st.markdown("---")

# =============================================================================
# LIGAS PRINCIPALES (LAS 5 GRANDES DE EUROPA) Y BASE DE DATOS (.INI)
# =============================================================================
CINCO_GRANDES_LIGAS = [
    {"id": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "espn": "eng.1", "efec": "80%"},
    {"id": "🇪🇸 LaLiga", "espn": "esp.1", "efec": "79%"},
    {"id": "🇮🇹 Serie A", "espn": "ita.1", "efec": "81%"},
    {"id": "🇩🇪 Bundesliga", "espn": "ger.1", "efec": "86%"},
    {"id": "🇫🇷 Ligue 1", "espn": "fra.1", "efec": "80%"},
]

TOP_DISPARADORES = {
    "Bayern Munich": {"sot": 7.8, "xg_shot": 0.16, "tag": "👑 Rey Casa / Top SoT"},
    "Barcelona": {"sot": 7.4, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top SoT"},
    "Manchester City": {"sot": 7.2, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"},
    "Paris Saint-Germain": {"sot": 7.1, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top SoT"},
    "Atalanta": {"sot": 6.5, "xg_shot": 0.13, "tag": "👑 Rey Casa / Top SoT"},
    "Inter": {"sot": 6.3, "xg_shot": 0.14, "tag": "👑 Rey Casa"},
    "Tottenham": {"sot": 6.2, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "AS Monaco": {"sot": 6.1, "xg_shot": 0.13, "tag": "👑 Rey Casa"},
    "AC Milan": {"sot": 6.0, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Villarreal": {"sot": 5.9, "xg_shot": 0.14, "tag": "👹 Monstruo Visita"},
    "Aston Villa": {"sot": 5.8, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "TSG Hoffenheim": {"sot": 5.7, "xg_shot": 0.13, "tag": "👹 Monstruo Visita"},
    "Real Madrid": {"sot": 6.8, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top SoT"},
    "Liverpool": {"sot": 6.9, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"},
    "Bayer Leverkusen": {"sot": 6.6, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"}
}

DEFENSAS_COLADOR = [
    "Bochum", "Augsburg", "Southampton", "Ipswich", "Leicester", 
    "Hellas Verona", "Venezia", "Angers", "Saint-Etienne", "Espanyol", 
    "Real Valladolid", "Holstein Kiel", "Heidenheim", "Montpellier", "Le Havre",
    "Wolverhampton", "Las Palmas", "Parma", "Como"
]

BLOQUES_CERROJO = ["Getafe", "Mallorca", "Empoli", "Everton"]

def auditar_equipo_bd(nombre_equipo):
    sot_base = 4.8
    xg_shot = 0.11
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
            etiqueta = "🧱 Bloque Bajo (Cerrojo)"
            break

    return sot_base, xg_shot, etiqueta, es_colador, es_cerrojo

def extraer_stat_live(team_dict, stat_names):
    for st_item in team_dict.get("statistics", []):
        if st_item.get("name") in stat_names:
            try:
                return float(st_item.get("displayValue", 0))
            except:
                return 0.0
    return 0.0

# =============================================================================
# ESTRUCTURA DE LAS 3 SECCIONES COMO PEDISTE
# =============================================================================
sec_futbol, sec_apuestas, sec_live = st.tabs([
    "⚽ 1. RESULTADOS DE FÚTBOL (PORTADA)", 
    "🎯 2. SECCIÓN APUESTAS OVER 1.5 (BIG DATA)", 
    "🚨 3. SCRAPING EN VIVO (CAZADOR DE 0-0)"
])

# -----------------------------------------------------------------------------
# SECCIÓN 1: PÁGINA NORMAL DE FÚTBOL (RESULTADOS Y MARCADORES DE LAS 5 LIGAS)
# -----------------------------------------------------------------------------
with sec_futbol:
    st.subheader("🏆 Cartelera y Marcadores Oficiales - Las 5 Grandes Ligas de Europa")
    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        dia_consulta = st.selectbox("📅 Ver Jornada:", ["Hoy", "Mañana", "Ayer"])
    
    offset = 0 if dia_consulta == "Hoy" else (1 if dia_consulta == "Mañana" else -1)
    fecha_cartelera = (datetime.now() + timedelta(days=offset)).strftime("%Y%m%d")

    for liga in CINCO_GRANDES_LIGAS:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga['espn']}/scoreboard?dates={fecha_cartelera}"
        try:
            res = requests.get(url, timeout=4)
            if res.status_code == 200:
                eventos = res.json().get("events", [])
                if eventos:
                    st.markdown(f"#### {liga['id']}")
                    filas_liga = []
                    for ev in eventos:
                        comp = ev.get("competitions", [{}])[0]
                        estado = comp.get("status", {}).get("type", {}).get("shortDetail", "Programado")
                        competitors = comp.get("competitors", [])
                        if len(competitors) == 2:
                            loc = competitors[0]
                            vis = competitors[1]
                            nom_l = loc.get("team", {}).get("displayName", "Local")
                            nom_v = vis.get("team", {}).get("displayName", "Visita")
                            gol_l = loc.get("score", "0")
                            gol_v = vis.get("score", "0")
                            st_state = comp.get("status", {}).get("type", {}).get("state", "pre")
                            
                            marcador_str = f"{gol_l} - {gol_v}" if st_state != "pre" else "vs"
                            filas_liga.append({
                                "Hora / Estado": estado,
                                "Local": nom_l,
                                "Marcador": marcador_str,
                                "Visitante": nom_v
                            })
                    st.dataframe(pd.DataFrame(filas_liga), use_container_width=True, hide_index=True)
        except Exception:
            pass

# -----------------------------------------------------------------------------
# SECCIÓN 2: BUSCADOR DE APUESTAS 1.5 (CON CONTEXTO xG/SHOT Y CRUCES .INI)
# -----------------------------------------------------------------------------
with sec_apuestas:
    st.subheader("🎯 Auditoría Pre-Partido Over 1.5 (Motor xG/Shot + Cruces de Oro)")
    st.markdown("Filtra las **5 Grandes Ligas** buscando cruces de **Top Disparadores (SoT >= 5.5)** contra **Defensas Colador**, descartando **Cerrojos**.")

    if st.button("🚀 BUSCAR FIJOS OVER 1.5 (PRÓXIMOS 3 DÍAS)"):
        hoy = datetime.now()
        fechas_buscar = [(hoy + timedelta(days=i)).strftime("%Y%m%d") for i in range(3)]
        reporte_pre = []

        with st.spinner("Auditando efectividad xG/Shot y defensas en Europa..."):
            for fecha in fechas_buscar:
                for liga in CINCO_GRANDES_LIGAS:
                    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga['espn']}/scoreboard?dates={fecha}"
                    try:
                        res = requests.get(url, timeout=4)
                        if res.status_code == 200:
                            for evento in res.json().get("events", []):
                                comp = evento.get("competitions", [{}])[0]
                                competitors = comp.get("competitors", [])
                                if len(competitors) == 2:
                                    nom_local = competitors[0].get("team", {}).get("displayName", "Local")
                                    nom_visita = competitors[1].get("team", {}).get("displayName", "Visita")
                                    fecha_iso = evento.get("date", "")
                                    try:
                                        dt = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00"))
                                        fecha_str = dt.strftime("%Y-%m-%d %H:%M")
                                    except:
                                        fecha_str = fecha

                                    sot_l, xgs_l, tag_l, col_l, cer_l = auditar_equipo_bd(nom_local)
                                    sot_v, xgs_v, tag_v, col_v, cer_v = auditar_equipo_bd(nom_visita)

                                    sot_combinado = round((sot_l + sot_v) / 1.6, 1)
                                    calidad_disparo = round(max(xgs_l, xgs_v), 2)
                                    xg_base = round((sot_l * xgs_l * 1.2) + (sot_v * xgs_v), 2)
                                    
                                    regla_aplicada = "Análisis Estándar"
                                    bono_prob = 0.0

                                    if (sot_l >= 6.0 and col_v):
                                        xg_base += 0.65
                                        bono_prob += 7.0
                                        regla_aplicada = "🔥 REGLA A: Rey Casa vs Colador (Prioritaria)"
                                    elif (sot_v >= 5.7 and col_l):
                                        xg_base += 0.50
                                        bono_prob += 5.0
                                        regla_aplicada = "⚡ REGLA B: Monstruo Visita vs Colador"
                                    elif (sot_l >= 6.2 and sot_v >= 6.0):
                                        xg_base += 0.70
                                        bono_prob += 6.0
                                        regla_aplicada = "💥 REGLA C: Choque de Trenes (Over 1.5 / 2.5)"

                                    if cer_l or cer_v:
                                        xg_base = max(1.35, xg_base - 0.55)
                                        bono_prob -= 10.0
                                        regla_aplicada = "🧱 ALERTA KRIPTONITA: Rival Cerrojo (-10%)"

                                    prob_poisson = (1 - poisson.cdf(1, xg_base)) * 100
                                    prob_final = round(min(98.5, max(45.0, prob_poisson + bono_prob)), 1)
                                    cuota_justa = round(100 / prob_final, 2)

                                    if cer_l or cer_v:
                                        veredicto = "🛑 ABORTAR / RIESGO 0-0"
                                    elif prob_final >= 84.0 and calidad_disparo >= 0.13:
                                        veredicto = "🟢 METER FICHA FUERTE (Cruce Oro)"
                                    elif prob_final >= 78.0:
                                        veredicto = "🟢 METER FICHA (Over 1.5)"
                                    else:
                                        veredicto = "🟡 ESPERAR EN VIVO (Sección 3)"

                                    reporte_pre.append({
                                        "Fecha": fecha_str,
                                        "Liga": liga["id"],
                                        "Partido": f"{nom_local} vs {nom_visita}",
                                        "🎯 SoT Esp.": sot_combinado,
                                        "💎 xG/Shot": calidad_disparo,
                                        "⚽ xG Total": round(xg_base, 2),
                                        "🔥 Prob. Over 1.5": f"{prob_final}%",
                                        "Cuota Justa": cuota_justa,
                                        "Contexto Big Data": regla_aplicada,
                                        "Veredicto": veredicto
                                    })
                    except Exception:
                        pass

        if reporte_pre:
            st.dataframe(pd.DataFrame(reporte_pre), use_container_width=True, hide_index=True)
        else:
            st.warning("No se encontraron partidos programados en este rango.")

# -----------------------------------------------------------------------------
# SECCIÓN 3: SCRAPING EN VIVO DE LAS 5 GRANDES LIGAS (MONITOREO DE 0 A 0)
# -----------------------------------------------------------------------------
with sec_live:
    st.subheader("🚨 Radar de Scraping en Vivo - Vigilante Permanente de los 0-0")
    st.markdown("Monitorea exclusivamente las **5 Grandes Ligas de Europa**. Si un partido está **0-0** pasando el minuto 20 con alto volumen de disparos al arco y peligro real, dispara la alerta para meter **Over 0.5 / 1.5 Live**.")

    auto_monitor = st.checkbox("🔄 Activar Vigilancia Automática Continua (Refresca cada 60 seg)", value=False)
    btn_escanear_live = st.button("⚡ ESCANEAR PARTIDOS 0-0 Y TIROS AL ARCO AHORA")

    if btn_escanear_live or auto_monitor:
        hoy_str = datetime.now().strftime("%Y%m%d")
        partidos_monitoreados = []
        alertas_cero_cero = []

        for liga in CINCO_GRANDES_LIGAS:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga['espn']}/scoreboard?dates={hoy_str}"
            try:
                res = requests.get(url, timeout=4)
                if res.status_code == 200:
                    for evento in res.json().get("events", []):
                        comp = evento.get("competitions", [{}])[0]
                        status_type = comp.get("status", {}).get("type", {}).get("state", "pre")
                        reloj = comp.get("status", {}).get("displayClock", "0'")
                        detalle = comp.get("status", {}).get("type", {}).get("shortDetail", "Programado")

                        competitors = comp.get("competitors", [])
                        if len(competitors) == 2:
                            local = competitors[0]
                            visita = competitors[1]
                            nom_l = local.get("team", {}).get("displayName", "Local")
                            nom_v = visita.get("team", {}).get("displayName", "Visita")
                            goles_l = int(local.get("score", 0) or 0)
                            goles_v = int(visita.get("score", 0) or 0)
                            goles_tot = goles_l + goles_v

                            tiros_l = extraer_stat_live(local, ["totalShots", "shots"])
                            tiros_v = extraer_stat_live(visita, ["totalShots", "shots"])
                            sot_l = extraer_stat_live(local, ["shotsOnTarget", "shotsOnGoal"])
                            sot_v = extraer_stat_live(visita, ["shotsOnTarget", "shotsOnGoal"])

                            sot_live = int(sot_l + sot_v)
                            tiros_live = int(tiros_l + tiros_v)

                            sot_h_l, xgs_l, tag_l, col_l, cer_l = auditar_equipo_bd(nom_l)
                            sot_h_v, xgs_v, tag_v, col_v, cer_v = auditar_equipo_bd(nom_v)

                            min_num = 0
                            try:
                                min_num = int(reloj.replace("'", "").split("+")[0])
                            except:
                                min_num = 0

                            # LÓGICA ESPECIAL CAZADOR DE 0-0
                            estado_alerta = "⚪ Sin alerta activa"
                            if status_type == "in":
                                if goles_tot == 0:
                                    if min_num >= 20 and (sot_live >= 3 or tiros_live >= 6 or sot_h_l >= 6.5 or col_v):
                                        estado_alerta = "🚨 ¡ALERTA 0-0 MADURO! -> METER OVER 0.5 HT / 1.5 LIVE"
                                        alertas_cero_cero.append(
                                            f"🔥 **CAZA 0-0 DETECTADA ({reloj})**: {nom_l} vs {nom_v} ({liga['id']}) | "
                                            f"🎯 Tiros al Arco: {sot_live} | 💥 Disparos: {tiros_live} | "
                                            f"👉 **ACCIÓN: METER FICHA AL OVER 0.5 / 1.5 YA**"
                                        )
                                    else:
                                        estado_alerta = f"👀 Vigilando 0-0 (Min {reloj} - Calentando motores)"
                                elif goles_tot == 1 and 20 <= min_num <= 75:
                                    if sot_live >= 4 or tiros_live >= 8:
                                        estado_alerta = "🟢 1-0 CON ASEDIO -> BUSCAR OVER 1.5 / 2.5 LIVE"
                                    else:
                                        estado_alerta = "🟡 1 Gol - Ritmo normal"
                                elif goles_tot >= 2:
                                    estado_alerta = "✅ OVER 1.5 CUMPLIDO"
                            elif status_type == "pre":
                                estado_alerta = "⏳ Esperando pitazo inicial para vigilar el 0-0"
                            else:
                                estado_alerta = "🏁 Partido Finalizado"

                            partidos_monitoreados.append({
                                "Reloj": f"{reloj} ({detalle})" if status_type == "in" else detalle,
                                "Liga": liga["id"],
                                "Encuentro": f"{nom_l} vs {nom_v}",
                                "Marcador": f"{goles_l} - {goles_v}",
                                "🎯 Tiros al Arco (SoT)": sot_live,
                                "💥 Disparos Totales": tiros_live,
                                "Perfil Big Data": f"{tag_l} vs {tag_v}",
                                "🔔 RADAR CAZADOR 0-0": estado_alerta
                            })
            except Exception:
                pass

        # Mostrar banners gigantes si hay un 0-0 listo para reventar
        if alertas_cero_cero:
            for al in alertas_cero_cero:
                st.error(al)
        else:
            st.info("📡 Escáner activo: Ningún partido en 0-0 rompe todavía el umbral de asedio (Min 20+ con alta presión de tiros).")

        if partidos_monitoreados:
            st.dataframe(pd.DataFrame(partidos_monitoreados), use_container_width=True, hide_index=True)

        if auto_monitor:
            time.sleep(60)
            st.rerun()
