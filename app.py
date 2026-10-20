import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from scipy.stats import poisson

# Configuración de la página
st.set_page_config(page_title="Portal Fútbol & Big Data - Miguel Ramirez", page_icon="⚽", layout="wide")

# Estilos CSS para imitar las tarjetas oscuras de tu captura con escudos y marcadores centrados
st.markdown("""
<style>
.liga-header {
    background-color: #1a1c23;
    color: #ffffff;
    padding: 12px 18px;
    border-radius: 10px 10px 0 0;
    font-weight: 700;
    font-size: 17px;
    border-bottom: 2px solid #2d303e;
    margin-top: 20px;
    display: flex;
    align-items: center;
}
.match-row {
    background-color: #121318;
    padding: 12px 16px;
    border-bottom: 1px solid #222530;
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: #e0e0e0;
    font-family: sans-serif;
}
.match-row:hover {
    background-color: #181a20;
}
.status-badge {
    background-color: #262936;
    color: #9ba1b0;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: bold;
    min-width: 65px;
    text-align: center;
}
.status-live {
    background-color: #ff2a4b;
    color: #ffffff;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: bold;
    min-width: 65px;
    text-align: center;
}
.teams-container {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-grow: 1;
    gap: 15px;
}
.team-home {
    text-align: right;
    width: 38%;
    font-weight: 600;
    font-size: 15px;
}
.team-away {
    text-align: left;
    width: 38%;
    font-weight: 600;
    font-size: 15px;
}
.score-box {
    background-color: #1f222d;
    padding: 5px 14px;
    border-radius: 8px;
    font-weight: 800;
    font-size: 16px;
    color: #ffffff;
    min-width: 70px;
    text-align: center;
}
.team-logo {
    width: 26px;
    height: 26px;
    object-fit: contain;
    vertical-align: middle;
}
</style>
""", unsafe_allow_html=True)

# Cabecera principal con tu firma
st.title("⚽ PORTAL DE FÚTBOL EUROPEO & CENTRAL BIG DATA")
st.markdown("<h2 style='text-align: center; color: #00ffcc;'>🔥 CREADO POR MIGUEL RAMIREZ 🔥</h2>", unsafe_allow_html=True)

# Botón de Notificaciones Nativas del Navegador (Push Web)
components.html("""
<div style="display: flex; justify-content: flex-end; align-items: center; font-family: sans-serif; margin-bottom: 5px;">
    <button id="btn-notif" onclick="activarNotificaciones()" style="background-color: #00ffcc; color: #0b0c10; border: none; padding: 8px 16px; border-radius: 20px; font-weight: bold; cursor: pointer; box-shadow: 0 2px 8px rgba(0,255,204,0.3);">
        🔔 Activar Notificaciones de Goles y Alertas 0-0
    </button>
</div>
<script>
function activarNotificaciones() {
    if (!("Notification" in window)) {
        alert("Tu navegador no soporta notificaciones web.");
    } else if (Notification.permission === "granted") {
        new Notification("⚽ Central Big Data - Miguel Ramirez", {
            body: "¡Las alertas en vivo ya están activas en tu dispositivo!",
        });
        document.getElementById("btn-notif").innerText = "✅ Notificaciones Activas";
    } else if (Notification.permission !== "denied") {
        Notification.requestPermission().then(function (permission) {
            if (permission === "granted") {
                new Notification("⚽ Central Big Data - Miguel Ramirez", {
                    body: "¡Notificaciones activadas! Recibirás avisos de fijos y 0-0.",
                });
                document.getElementById("btn-notif").innerText = "✅ Notificaciones Activas";
            }
        });
    }
}
</script>
""", height=45)

def disparar_notificacion_push(titulo, mensaje):
    components.html(f"""
    <script>
    if ("Notification" in window && Notification.permission === "granted") {{
        new Notification("{titulo}", {{ body: "{mensaje}" }});
    }}
    </script>
    """, height=0)

# =============================================================================
# LIGAS: CHAMPIONS LEAGUE + LAS 5 GRANDES LIGAS DE EUROPA Y BASE DE DATOS (.INI)
# =============================================================================
LIGAS_PRINCIPALES = [
    {"id": "🏆 Champions League", "espn": "uefa.champions", "efec": "85%"},
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
    "PSV Eindhoven": {"sot": 7.5, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top SoT"},
    "Celtic": {"sot": 8.0, "xg_shot": 0.16, "tag": "👑 Rey Casa / Top SoT"},
    "Sporting CP": {"sot": 7.1, "xg_shot": 0.15, "tag": "👑 Rey Casa / Top SoT"},
    "Bodo/Glimt": {"sot": 7.0, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"},
    "Galatasaray": {"sot": 7.0, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"},
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
    "Borussia Dortmund": {"sot": 6.4, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"},
    "Bayer Leverkusen": {"sot": 6.6, "xg_shot": 0.14, "tag": "👑 Rey Casa / Top SoT"}
}

DEFENSAS_COLADOR = [
    "Bochum", "Augsburg", "Southampton", "Ipswich", "Leicester", 
    "Hellas Verona", "Venezia", "Angers", "Saint-Etienne", "Espanyol", 
    "Real Valladolid", "Holstein Kiel", "Heidenheim", "Montpellier", "Le Havre",
    "Wolverhampton", "Las Palmas", "Parma", "Como", "Slovan Bratislava", "Young Boys", "Salzburg"
]

BLOQUES_CERROJO = ["Getafe", "Mallorca", "Empoli", "Everton"]

def auditar_equipo_bd(nombre_equipo):
    sot_base = 4.9
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

@st.cache_data(ttl=120)
def obtener_jornada_automatica():
    hoy = datetime.now()
    # Escanea automáticamente desde hoy hasta +4 días para traer toda la jornada activa sin preguntar días
    rango_fechas = f"{hoy.strftime('%Y%m%d')}-{(hoy + timedelta(days=4)).strftime('%Y%m%d')}"
    datos_por_liga = {}

    for liga in LIGAS_PRINCIPALES:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga['espn']}/scoreboard?dates={rango_fechas}"
        try:
            res = requests.get(url, timeout=4)
            if res.status_code == 200:
                eventos = res.json().get("events", [])
                if eventos:
                    datos_por_liga[liga["id"]] = {
                        "meta": liga,
                        "eventos": eventos
                    }
        except Exception:
            pass
    return datos_por_liga

# =============================================================================
# ESTRUCTURA DE LAS 3 SECCIONES
# =============================================================================
sec_futbol, sec_apuestas, sec_live = st.tabs([
    "⚽ 1. RESULTADOS Y JORNADA (PORTADA)", 
    "🎯 2. APUESTAS OVER 1.5 (MOTOR BIG DATA)", 
    "🚨 3. SCRAPING EN VIVO (CAZADOR DE 0-0)"
])

datos_jornada = obtener_jornada_automatica()

# -----------------------------------------------------------------------------
# SECCIÓN 1: PORTADA DE FÚTBOL AUTOMÁTICA CON ESCUDOS (ESTILO CAPTURA)
# -----------------------------------------------------------------------------
with sec_futbol:
    filtro_vista = st.radio(
        "Filtro rápido:", 
        ["📅 Todos los Partidos de la Jornada", "🔴 Solo En Vivo"], 
        horizontal=True,
        label_visibility="collapsed"
    )

    hay_partidos_mostrados = False

    for nombre_liga, contenido in datos_jornada.items():
        eventos = contenido["eventos"]
        filas_html = ""

        for ev in eventos:
            comp = ev.get("competitions", [{}])[0]
            st_state = comp.get("status", {}).get("type", {}).get("state", "pre")
            detalle_corto = comp.get("status", {}).get("type", {}).get("shortDetail", "")
            reloj = comp.get("status", {}).get("displayClock", "")

            if filtro_vista == "🔴 Solo En Vivo" and st_state != "in":
                continue

            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                hay_partidos_mostrados = True
                loc = competitors[0]
                vis = competitors[1]

                nom_l = loc.get("team", {}).get("shortDisplayName", loc.get("team", {}).get("displayName", "Local"))
                nom_v = vis.get("team", {}).get("shortDisplayName", vis.get("team", {}).get("displayName", "Visita"))
                logo_l = loc.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
                logo_v = vis.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
                gol_l = loc.get("score", "0")
                gol_v = vis.get("score", "0")

                if st_state == "in":
                    badge_html = f"<div class='status-live'>🔴 {reloj}</div>"
                    centro_html = f"{gol_l} - {gol_v}"
                elif st_state == "post":
                    badge_html = "<div class='status-badge'>TC</div>"
                    centro_html = f"{gol_l} - {gol_v}"
                else:
                    try:
                        dt = datetime.fromisoformat(ev.get("date", "").replace("Z", "+00:00"))
                        badge_html = f"<div class='status-badge'>{dt.strftime('%d/%m')}</div>"
                        centro_html = dt.strftime("%H:%M")
                    except:
                        badge_html = f"<div class='status-badge'>{detalle_corto}</div>"
                        centro_html = "vs"

                filas_html += f"""
                <div class="match-row">
                    {badge_html}
                    <div class="teams-container">
                        <div class="team-home">{nom_l}</div>
                        <img src="{logo_l}" class="team-logo">
                        <div class="score-box">{centro_html}</div>
                        <img src="{logo_v}" class="team-logo">
                        <div class="team-away">{nom_v}</div>
                    </div>
                </div>
                """

        if filas_html:
            st.markdown(f"<div class='liga-header'>{nombre_liga}</div>{filas_html}", unsafe_allow_html=True)

    if not hay_partidos_mostrados:
        st.info("No hay partidos en curso en este preciso segundo. Cambia el botón a 'Todos los Partidos de la Jornada'.")

# -----------------------------------------------------------------------------
# SECCIÓN 2: BUSCADOR AUTOMÁTICO DE APUESTAS OVER 1.5 (CON BIG DATA .INI)
# -----------------------------------------------------------------------------
with sec_apuestas:
    st.subheader("🎯 Auditoría Automática Over 1.5 (Champions + 5 Grandes Ligas)")
    st.markdown("Cruza automáticamente toda la jornada activa con tu base de datos (**xG/Shot >= 0.12**, **Reyes de Casa vs Coladores** y **Anti-Cerrojo**).")

    reporte_pre = []
    for nombre_liga, contenido in datos_jornada.items():
        efec_liga = contenido["meta"]["efec"]
        for evento in contenido["eventos"]:
            comp = evento.get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                nom_local = competitors[0].get("team", {}).get("displayName", "Local")
                nom_visita = competitors[1].get("team", {}).get("displayName", "Visita")
                fecha_iso = evento.get("date", "")
                try:
                    dt = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00"))
                    fecha_str = dt.strftime("%d/%m %H:%M")
                except:
                    fecha_str = "Jornada Activa"

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
                    "Fecha / Hora": fecha_str,
                    "Torneo": f"{nombre_liga} ({efec_liga})",
                    "Partido": f"{nom_local} vs {nom_visita}",
                    "🎯 SoT Esp.": sot_combinado,
                    "💎 xG/Shot": calidad_disparo,
                    "⚽ xG Total": round(xg_base, 2),
                    "🔥 Prob. Over 1.5": f"{prob_final}%",
                    "Cuota Mín.": cuota_justa,
                    "Contexto Big Data": regla_aplicada,
                    "Veredicto Oficial": veredicto
                })

    if reporte_pre:
        st.dataframe(pd.DataFrame(reporte_pre), use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# SECCIÓN 3: SCRAPING EN VIVO Y MONITOREO AUTOMÁTICO DE LOS 0 A 0
# -----------------------------------------------------------------------------
with sec_live:
    st.subheader("🚨 Cazador de 0-0 en Vivo (Champions + 5 Grandes Ligas)")
    st.markdown("Vigila automáticamente los partidos en juego. Si detecta un **0-0** en el minuto 20+ con tiros al arco y asedio, lanza la **alerta visual y notificación Push** para entrarle al **Over 0.5 HT / 1.5 Live**.")

    auto_monitor = st.checkbox("🔄 Mantener Radar 0-0 Auto-Actualizando cada 60 segundos", value=True)

    partidos_monitoreados = []
    alertas_cero_cero = []

    for nombre_liga, contenido in datos_jornada.items():
        for evento in contenido["eventos"]:
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

                estado_alerta = "⚪ Sin alerta"
                if status_type == "in":
                    if goles_tot == 0:
                        if min_num >= 20 and (sot_live >= 3 or tiros_live >= 6 or sot_h_l >= 6.5 or col_v):
                            estado_alerta = "🚨 ¡ALERTA 0-0 MADURO! -> METER OVER 0.5 / 1.5"
                            msg_alerta = f"{nom_l} vs {nom_v} ({reloj}) | 0-0 con {sot_live} tiros al arco y {tiros_live} disparos. ¡METER OVER 0.5 / 1.5!"
                            alertas_cero_cero.append(msg_alerta)
                            disparar_notificacion_push("🚨 ALERTA CAZADOR 0-0", msg_alerta)
                        else:
                            estado_alerta = f"👀 Vigilando 0-0 ({reloj})"
                    elif goles_tot == 1 and 20 <= min_num <= 75:
                        if sot_live >= 4 or tiros_live >= 8:
                            estado_alerta = "🔥 1-0 CON ASEDIO -> OVER 1.5 / 2.5 LIVE"
                        else:
                            estado_alerta = "🟢 1 Gol - Ritmo normal"
                    elif goles_tot >= 2:
                        estado_alerta = "✅ OVER 1.5 COBRADO"
                elif status_type == "pre":
                    estado_alerta = "⏳ Por jugar (En cola para vigilar 0-0)"
                else:
                    estado_alerta = "🏁 Finalizado"

                partidos_monitoreados.append({
                    "Estado": f"🔴 {reloj}" if status_type == "in" else detalle,
                    "Torneo": nombre_liga,
                    "Encuentro": f"{nom_l} vs {nom_v}",
                    "Marcador": f"{goles_l} - {goles_v}",
                    "🎯 Tiros al Arco (Live)": sot_live,
                    "💥 Disparos Totales": tiros_live,
                    "Perfil Big Data": f"{tag_l} vs {tag_v}",
                    "🔔 RADAR CAZADOR 0-0": estado_alerta
                })

    if alertas_cero_cero:
        for al in alertas_cero_cero:
            st.error(f"🔥 **CAZA 0-0 DETECTADA**: {al}")
    else:
        st.success("📡 Vigilante 0-0 activo y escaneando la jornada automáticamente.")

    if partidos_monitoreados:
        st.dataframe(pd.DataFrame(partidos_monitoreados), use_container_width=True, hide_index=True)

    if auto_monitor:
        time.sleep(60)
        st.rerun()
