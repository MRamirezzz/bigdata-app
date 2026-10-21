import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from scipy.stats import poisson

try:
    from fpdf import FPDF
    PDF_DISPONIBLE = True
except ImportError:
    PDF_DISPONIBLE = False

# Configuración principal con la marca MRFUTBOL
st.set_page_config(page_title="MRFUTBOL - Miguel Ramirez", page_icon="⚽", layout="wide")

# =============================================================================
# PERSISTENCIA PERMANENTE POR USUARIO (SOBREVIVE AL AUTO-REFRESCO Y RECARGAS)
# =============================================================================
qp = st.query_params

if "user_phone" not in st.session_state:
    st.session_state["user_phone"] = qp.get("phone", "")
if "user_apikey" not in st.session_state:
    st.session_state["user_apikey"] = qp.get("apikey", "")
if "master_sound" not in st.session_state:
    st.session_state["master_sound"] = (qp.get("sound", "1") == "1")
if "auto_refresh" not in st.session_state:
    st.session_state["auto_refresh"] = (qp.get("refresh", "1") == "1")
if "scraping_modo_todos" not in st.session_state:
    st.session_state["scraping_modo_todos"] = (qp.get("scrapall", "0") == "1")

if "seguidos_portada" not in st.session_state:
    seg_str = qp.get("seg", "")
    st.session_state["seguidos_portada"] = [x for x in seg_str.split(",") if x]
if "seguidos_scraping" not in st.session_state:
    scr_str = qp.get("scr", "")
    st.session_state["seguidos_scraping"] = [x for x in scr_str.split(",") if x]

if "memoria_eventos" not in st.session_state:
    st.session_state["memoria_eventos"] = {}
if "alertas_enviadas_wa" not in st.session_state:
    st.session_state["alertas_enviadas_wa"] = set()
if "historial_notificaciones" not in st.session_state:
    st.session_state["historial_notificaciones"] = []

def guardar_estado_permanente():
    st.query_params["phone"] = st.session_state["user_phone"]
    st.query_params["apikey"] = st.session_state["user_apikey"]
    st.query_params["sound"] = "1" if st.session_state["master_sound"] else "0"
    st.query_params["refresh"] = "1" if st.session_state["auto_refresh"] else "0"
    st.query_params["scrapall"] = "1" if st.session_state["scraping_modo_todos"] else "0"
    st.query_params["seg"] = ",".join(st.session_state["seguidos_portada"])
    st.query_params["scr"] = ",".join(st.session_state["seguidos_scraping"])

# ESTILOS CSS COMPACTOS
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
    color: #9ba1b0;
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
</style>
""", unsafe_allow_html=True)

# ENCABEZADO OFICIAL MRFUTBOL
st.markdown("<div class='titulo-mrfutbol'>⚽ MRFUTBOL</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitulo-autor'>Miguel Ramirez &nbsp;|&nbsp; ✉️ angelramirezzmiguel2@gmail.com</div>", unsafe_allow_html=True)

# =============================================================================
# MOTOR DE ENVÍO INDIVIDUAL A WHATSAPP Y ALERTA SONORA
# =============================================================================
def enviar_whatsapp_usuario(texto_mensaje):
    telefono = st.session_state["user_phone"].strip().replace(" ", "").replace("-", "")
    apikey = st.session_state["user_apikey"].strip()
    if not telefono or not apikey:
        return False
    try:
        msg_encoded = urllib.parse.quote(f"⚽ *MRFUTBOL VIP*\n{texto_mensaje}")
        url = f"https://api.callmebot.com/whatsapp.php?phone={telefono}&text={msg_encoded}&apikey={apikey}"
        requests.get(url, timeout=4)
        return True
    except:
        return False

def disparar_alerta_evento(id_unico_alerta, titulo, mensaje, icono="🔔"):
    # Respeta el apagado permanente del usuario
    if not st.session_state["master_sound"]:
        return

    if id_unico_alerta in st.session_state["alertas_enviadas_wa"]:
        return
    st.session_state["alertas_enviadas_wa"].add(id_unico_alerta)

    hora_actual = (datetime.utcnow() - timedelta(hours=6)).strftime("%H:%M:%S")
    registro = f"[{hora_actual}] {icono} **{titulo}**: {mensaje}"
    st.toast(f"**{titulo}**\n\n{mensaje}", icon=icono)
    st.session_state["historial_notificaciones"].insert(0, registro)

    # Enviar al WhatsApp registrado por este usuario
    enviar_whatsapp_usuario(f"{icono} *{titulo}*\n{mensaje}")

    # Sonido en navegador (para PC / Laptop)
    components.html("""
    <script>
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.35);
    } catch(e) {}
    </script>
    """, height=0)

# =============================================================================
# PANEL SUPERIOR: REGISTRO MULTIUSUARIO WHATSAPP + APAGADO PERMANENTE
# =============================================================================
col_top1, col_top2, col_top3 = st.columns([2.2, 1.4, 1.4])
with col_top1:
    estado_wa = "🟢 WhatsApp Conectado" if (st.session_state["user_phone"] and st.session_state["user_apikey"]) else "⚪ WhatsApp Sin Vincular (Abre el panel abajo)"
    st.caption(f"💡 Estado de tu línea personal: **{estado_wa}**")
with col_top2:
    nuevo_sound = st.toggle(
        "🔔 Notificaciones Activas (Permanente)",
        value=st.session_state["master_sound"],
        key="toggle_master_ui"
    )
    if nuevo_sound != st.session_state["master_sound"]:
        st.session_state["master_sound"] = nuevo_sound
        guardar_estado_permanente()
        st.rerun()
with col_top3:
    nuevo_ref = st.toggle(
        "🔄 Auto-Refresco (2m)",
        value=st.session_state["auto_refresh"],
        key="toggle_ref_ui"
    )
    if nuevo_ref != st.session_state["auto_refresh"]:
        st.session_state["auto_refresh"] = nuevo_ref
        guardar_estado_permanente()
        st.rerun()

with st.expander("📲 Registro de Usuario para Alertas en tu WhatsApp Personal (Multiusuario)", expanded=False):
    st.markdown("""
    **¿Cómo recibir las alertas de tus partidos en tu propio WhatsApp en 30 segundos?**
    1. Haz clic aquí desde tu celular o WhatsApp Web: 👉 [**Activar Bot de WhatsApp MRFUTBOL**](https://api.callmebot.com/whatsapp.php?source=web) o envía el mensaje **`I allow callmebot to send me messages`** al número **`+34 698 28 89 73`** en WhatsApp.
    2. El bot te responderá al instante con tu código **API Key** personal.
    3. Ingresa tu número (con código de país, ej. `+50499887766`) y tu código abajo. ¡Tus datos quedan guardados en tu enlace personal!
    """)
    c_wa1, c_wa2, c_wa3 = st.columns([2, 1.5, 1.5])
    with c_wa1:
        inp_phone = st.text_input("📱 Tu Número de WhatsApp (con + y código de país):", value=st.session_state["user_phone"], placeholder="Ej: +50499999999")
    with c_wa2:
        inp_key = st.text_input("🔑 Tu Clave del Bot (API Key):", value=st.session_state["user_apikey"], placeholder="Ej: 1234567")
    with c_wa3:
        st.write("")
        st.write("")
        if st.button("💾 Guardar y Probar mi WhatsApp", use_container_width=True):
            st.session_state["user_phone"] = inp_phone.strip()
            st.session_state["user_apikey"] = inp_key.strip()
            guardar_estado_permanente()
            ok = enviar_whatsapp_usuario("✅ ¡Tu número ha quedado vinculado a MRFUTBOL! Recibirás aquí las alertas de los partidos que actives.")
            if ok:
                st.success("✅ ¡Guardado! Revisa tu WhatsApp, te acabamos de enviar un mensaje de prueba.")
            else:
                st.warning("⚠️ Datos guardados, pero verifica que hayas ingresado el número con signo '+' y tu API Key correcta.")

# =============================================================================
# FUNCIÓN GENERADORA DE REPORTE PDF PROFESIONAL
# =============================================================================
def generar_pdf_preapuestas(df_reporte):
    if not PDF_DISPONIBLE:
        return None
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    
    # Encabezado Oscuro MRFUTBOL
    pdf.set_fill_color(22, 24, 31)
    pdf.rect(0, 0, 297, 26, "F")
    pdf.set_text_color(0, 255, 204)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "MRFUTBOL - REPORTE OFICIAL DE PRE-APUESTAS (OVER 1.5)", new_x="LMARGIN", new_y="NEXT", align="C")
    
    hora_rep = (datetime.utcnow() - timedelta(hours=6)).strftime("%d/%m/%Y %H:%M")
    pdf.set_text_color(230, 230, 230)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, f"Autor: Miguel Ramirez | angelramirezzmiguel2@gmail.com | Generado: {hora_rep}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    # Cabecera de la tabla
    pdf.set_fill_color(31, 34, 45)
    pdf.set_text_color(0, 255, 204)
    pdf.set_font("Helvetica", "B", 9)
    anchos = [26, 48, 72, 22, 26, 22, 61]
    columnas = ["Fecha", "Liga", "Partido", "xG Esp.", "Prob. Over 1.5", "Cuota", "Veredicto"]
    
    for ancho, col_nom in zip(anchos, columnas):
        pdf.cell(ancho, 8, col_nom, border=1, align="C", fill=True)
    pdf.ln()

    # Filas de partidos
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("Helvetica", "", 9)
    fill_row = False
    for _, row in df_reporte.iterrows():
        pdf.set_fill_color(240, 244, 248) if fill_row else pdf.set_fill_color(255, 255, 255)
        
        # Limpiar emojis para que el PDF estándar no falle con caracteres especiales
        liga_clean = str(row["Liga"]).encode("latin-1", "ignore").decode("latin-1").strip()
        partido_clean = str(row["Partido"]).encode("latin-1", "ignore").decode("latin-1").strip()
        ver_raw = str(row["Veredicto"])
        if "Cuota de Valor" in ver_raw:
            ver_clean = "ENTRAR OVER 1.5 (Cuota de Valor)"
        elif "Fijo Alta" in ver_raw:
            ver_clean = "ENTRAR OVER 1.5 (Fijo Alta Prob.)"
        else:
            ver_clean = "VALOR MODERADO (Para En Vivo)"

        valores = [
            str(row["Fecha"]),
            liga_clean[:26],
            partido_clean[:38],
            str(row["xG Esperado"]),
            str(row["Prob. Pre Over 1.5"]),
            str(row["Cuota Estimada"]),
            ver_clean
        ]
        for ancho, val in zip(anchos, valores):
            pdf.cell(ancho, 7, val, border=1, align="C", fill=True)
        pdf.ln()
        fill_row = not fill_row

    return bytes(pdf.output())

# =============================================================================
# LAS 19 LIGAS OFICIALES DEL ARCHIVO BIG DATA (.INI) + CHAMPIONS LEAGUE
# =============================================================================
LIGAS_BIG_DATA = [
    {"id": "🏆 Champions League", "code": "uefa.champions", "efec": "85%"},
    {"id": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League (ING1)", "code": "eng.1", "efec": "80%"},
    {"id": "🇪🇸 LaLiga (ESP1)", "code": "esp.1", "efec": "79%"},
    {"id": "🇮🇹 Serie A (ITA1)", "code": "ita.1", "efec": "81%"},
    {"id": "🇩🇪 Bundesliga (ALE1)", "code": "ger.1", "efec": "86%"},
    {"id": "🇫🇷 Ligue 1 (FRA1)", "code": "fra.1", "efec": "80%"},
    {"id": "🇨🇭 Challenge League (SUI2)", "code": "sui.2", "efec": "91%"},
    {"id": "🇨🇭 Super League (SUI1)", "code": "sui.1", "efec": "89%"},
    {"id": "🇳🇱 Eredivisie (HOL1)", "code": "ned.1", "efec": "88%"},
    {"id": "🇳🇱 Eerste Divisie (HOL2)", "code": "ned.2", "efec": "85%"},
    {"id": "🇳🇴 Eliteserien (NOR1)", "code": "nor.1", "efec": "87%"},
    {"id": "🇳🇴 1. Division (NOR2)", "code": "nor.2", "efec": "86%"},
    {"id": "🇩🇪 2. Bundesliga (ALE2)", "code": "ger.2", "efec": "84%"},
    {"id": "🇦🇹 Bundesliga (AUT1)", "code": "aut.1", "efec": "84%"},
    {"id": "🇧🇪 Jupiler Pro League (BEL1)", "code": "bel.1", "efec": "83%"},
    {"id": "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Premiership (ESC1)", "code": "sco.1", "efec": "83%"},
    {"id": "🇹🇷 Süper Lig (TUR1)", "code": "tur.1", "efec": "82%"},
    {"id": "🇵🇹 Primeira Liga (POR1)", "code": "por.1", "efec": "81%"},
    {"id": "🇺🇸 MLS (USA1)", "code": "usa.1", "efec": "84%"},
    {"id": "🇲🇽 Liga MX (MEX1)", "code": "mex.1", "efec": "80%"},
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

def _fetch_standings(code):
    url = f"https://site.api.espn.com/apis/v2/sports/soccer/{code}/standings"
    equipos_stats = {}
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
                    info = {"pj": int(pj), "gf_prom": round(gf / pj, 2), "gc_prom": round(gc / pj, 2)}
                    if t_name:
                        equipos_stats[t_name.lower()] = info
                    if t_short:
                        equipos_stats[t_short.lower()] = info
    except:
        pass
    return code, equipos_stats

@st.cache_data(ttl=900)
def obtener_estadisticas_temporada_reales(codigos_liga):
    tabla_global = {}
    with ThreadPoolExecutor(max_workers=12) as executor:
        resultados = list(executor.map(_fetch_standings, codigos_liga))
    for code, eq_dict in resultados:
        tabla_global.update(eq_dict)
    return tabla_global

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
        fuente_tag = f"📊 Prom. Real ({real_l['gf_prom']} GF / {real_v['gf_prom']} GF)"
    else:
        bono_col = 0.30 if (col_l or col_v) else 0.0
        xg_base = round(xg_ini + bono_col, 2)
        fuente_tag = f"{tag_l} vs {tag_v}"

    if cer_l or cer_v:
        xg_base = max(1.25, round(xg_base - 0.30, 2))

    prob_poisson = (1 - poisson.cdf(1, xg_base)) * 100
    prob_final = round(min(95.0, max(42.0, prob_poisson)), 1)
    cuota_justa = round(100 / prob_final, 2)
    return prob_final, cuota_justa, xg_base, fuente_tag

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
    
    return {
        "toth_l": toth_l, "toth_v": toth_v, "toth_tot": toth_l + toth_v,
        "tmeta_l": tmeta_l, "tmeta_v": tmeta_v, "tmeta_tot": tmeta_l + tmeta_v,
        "tfuera_l": tfuera_l, "tfuera_v": tfuera_v, "tfuera_tot": tfuera_l + tfuera_v,
        "esquinas_l": esquinas_l, "esquinas_v": esquinas_v, "esquinas_tot": esquinas_l + esquinas_v,
        "pos_l": pos_l, "pos_v": pos_v
    }

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

    if es_ht:
        badge_html = "<div class='status-ht'>⏸️ ENTRETIEMPO</div>"
        reloj_txt = "⏸️ HT (45')"
    elif st_state == "in":
        badge_html = f"<div class='status-live'>🔴 {reloj}</div>"
        reloj_txt = f"🔴 {reloj}"
    elif st_state == "post":
        badge_html = "<div class='status-badge'>FINAL</div>"
        reloj_txt = "FINAL"
    else:
        try:
            dt = datetime.fromisoformat(iso_fecha.replace("Z", "+00:00")) - timedelta(hours=6)
            fecha_legible = dt.strftime("%d/%m %H:%M")
        except:
            fecha_legible = "Programado"
        badge_html = f"<div class='status-badge'>{fecha_legible}</div>"
        reloj_txt = fecha_legible

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

@st.cache_data(ttl=20)
def obtener_partidos_ligas(codigos_liga):
    hoy_hn = datetime.utcnow() - timedelta(hours=6)
    fechas = [(hoy_hn + timedelta(days=i)).strftime("%Y%m%d") for i in (-1, 0, 1)]
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

codigos_todas = [l["code"] for l in LIGAS_BIG_DATA]
datos_globales = obtener_partidos_ligas(codigos_todas)
stats_temporada_api = obtener_estadisticas_temporada_reales(codigos_todas)

sec_resultados, sec_en_vivo, sec_apuestas, sec_scraping = st.tabs([
    "⚽ 1. RESULTADOS", 
    "🔴 2. PARTIDOS EN VIVO", 
    "🎯 3. PRE-APUESTAS (PDF)", 
    "🚨 4. SCRAPING Y ALERTAS"
])

# -----------------------------------------------------------------------------
# SECCIÓN 1: RESULTADOS GENERALES Y NOTIFICACIÓN INDIVIDUAL POR PARTIDO
# -----------------------------------------------------------------------------
with sec_resultados:
    col_menu, col_contenido = st.columns([1.2, 3.8])

    with col_menu:
        st.markdown("##### 📌 Ligas Disponibles")
        nombres_ligas = [l["id"] for l in LIGAS_BIG_DATA]
        liga_seleccionada_panel = st.selectbox("Filtrar Liga:", ["🌍 Todas las Ligas"] + nombres_ligas, label_visibility="collapsed")
        texto_busqueda = st.text_input("🔍 Buscar Equipo...", "", placeholder="Ej. Real Madrid, Guadalajara...")
        if st.button("🔄 Actualizar Datos Ahora", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with col_contenido:
        for nombre_liga, contenido in datos_globales.items():
            if liga_seleccionada_panel != "🌍 Todas las Ligas" and liga_seleccionada_panel != nombre_liga:
                continue

            eventos_filtrados = []
            for ev in contenido["eventos"]:
                comp = ev.get("competitions", [{}])[0]
                competitors = comp.get("competitors", [])
                if len(competitors) == 2:
                    nom_l = competitors[0].get("team", {}).get("displayName", "")
                    nom_v = competitors[1].get("team", {}).get("displayName", "")
                    if not texto_busqueda or (texto_busqueda.lower() in nom_l.lower() or texto_busqueda.lower() in nom_v.lower()):
                        eventos_filtrados.append(ev)

            if not eventos_filtrados:
                continue

            st.markdown(f"<div class='liga-header'>{nombre_liga}</div>", unsafe_allow_html=True)

            for ev in eventos_filtrados:
                ev_id = str(ev.get("id"))
                comp = ev.get("competitions", [{}])[0]
                competitors = comp.get("competitors", [])
                if len(competitors) != 2:
                    continue

                loc, vis = competitors[0], competitors[1]
                nom_l = loc.get("team", {}).get("shortDisplayName", loc.get("team", {}).get("displayName", "Local"))
                nom_v = vis.get("team", {}).get("shortDisplayName", vis.get("team", {}).get("displayName", "Visita"))
                logo_l = loc.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
                logo_v = vis.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
                gol_l = int(loc.get("score", 0) or 0)
                gol_v = int(vis.get("score", 0) or 0)
                nombre_cruce = f"{nom_l} vs {nom_v}"

                st_state, es_ht, min_num, badge_html, _ = detectar_estado_partido(comp, ev.get("date", ""))
                centro_html = f"{gol_l} - {gol_v}" if (st_state != "pre" or es_ht) else "vs"

                detalles_partido = comp.get("details", [])
                rojas_actuales = sum(1 for d in detalles_partido if d.get("redCard", False))
                stats = extraer_metricas_partido_reales(loc, vis)

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
                    ya_seguido = ev_id in st.session_state["seguidos_portada"]
                    activar_si = st.checkbox("🔔 Seguir", value=ya_seguido, key=f"portada_bell_{ev_id}")

                    if activar_si and not ya_seguido:
                        st.session_state["seguidos_portada"].append(ev_id)
                        st.session_state["memoria_eventos"][ev_id] = {
                            "state": st_state,
                            "ht_notificado": es_ht,
                            "goles_l": gol_l,
                            "goles_v": gol_v,
                            "rojas": rojas_actuales
                        }
                        guardar_estado_permanente()
                        disparar_alerta_evento(f"seg_on_{ev_id}", f"Seguimiento Activo: {nombre_cruce}", "Te avisaremos goles, descanso, rojas y final.", "✅")
                    elif not activar_si and ya_seguido:
                        st.session_state["seguidos_portada"].remove(ev_id)
                        guardar_estado_permanente()

                    if activar_si:
                        if ev_id not in st.session_state["memoria_eventos"]:
                            st.session_state["memoria_eventos"][ev_id] = {
                                "state": st_state,
                                "ht_notificado": es_ht,
                                "goles_l": gol_l,
                                "goles_v": gol_v,
                                "rojas": rojas_actuales
                            }
                        mem = st.session_state["memoria_eventos"][ev_id]
                        if mem["state"] == "pre" and st_state == "in":
                            disparar_alerta_evento(f"ini_{ev_id}", "⏳ ¡ARRANCÓ EL PARTIDO!", f"{nombre_cruce} (0-0)", "🟢")
                        if es_ht and not mem["ht_notificado"]:
                            disparar_alerta_evento(f"ht_{ev_id}", "⏸️ ENTRETIEMPO (HT)", f"{nombre_cruce} | Marcador: {gol_l}-{gol_v}", "⏱️")
                            mem["ht_notificado"] = True
                        if (gol_l + gol_v) > (mem["goles_l"] + mem["goles_v"]):
                            disparar_alerta_evento(f"gol_{ev_id}_{gol_l}_{gol_v}", f"⚽ ¡GOL EN {nombre_cruce}!", f"Nuevo marcador: {gol_l}-{gol_v}", "⚽")
                        elif (gol_l + gol_v) < (mem["goles_l"] + mem["goles_v"]):
                            disparar_alerta_evento(f"var_{ev_id}_{gol_l}_{gol_v}", "❌ ¡GOL ANULADO (VAR)!", f"{nombre_cruce} vuelve a {gol_l}-{gol_v}", "🚫")
                        if rojas_actuales > mem["rojas"]:
                            disparar_alerta_evento(f"roja_{ev_id}_{rojas_actuales}", "🟥 ¡TARJETA ROJA!", f"Expulsión en {nombre_cruce}", "🟥")
                        if mem["state"] != "post" and st_state == "post":
                            disparar_alerta_evento(f"fin_{ev_id}", "🏁 FINAL DEL PARTIDO", f"{nombre_cruce} terminó {gol_l}-{gol_v}", "🏁")

                        st.session_state["memoria_eventos"][ev_id].update({
                            "state": st_state,
                            "goles_l": gol_l,
                            "goles_v": gol_v,
                            "rojas": rojas_actuales
                        })

    if st.session_state["historial_notificaciones"]:
        with st.expander("📲 Bandeja de Alertas Enviadas en esta Sesión", expanded=False):
            for notif in st.session_state["historial_notificaciones"][:10]:
                st.info(notif)

# -----------------------------------------------------------------------------
# SECCIÓN 2: PARTIDOS EN VIVO
# -----------------------------------------------------------------------------
with sec_en_vivo:
    st.subheader("🔴 Partidos en Vivo y Entretiempo")
    st.caption("Estadísticas 100% reales y directas de cancha (Disparos Totales, Tiros al Arco, Disparos Fuera, Córneres y Posesión).")
    
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
        st.markdown(f"<div class='liga-header'>{nombre_liga}</div>", unsafe_allow_html=True)

        for ev in eventos_en_vivo:
            ev_id = str(ev.get("id"))
            comp = ev.get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])
            if len(competitors) != 2:
                continue

            loc, vis = competitors[0], competitors[1]
            nom_l = loc.get("team", {}).get("shortDisplayName", loc.get("team", {}).get("displayName", "Local"))
            nom_v = vis.get("team", {}).get("shortDisplayName", vis.get("team", {}).get("displayName", "Visita"))
            logo_l = loc.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
            logo_v = vis.get("team", {}).get("logo", "https://a.espncdn.com/i/teamlogos/soccer/500/default-team-logo-500.png")
            gol_l = int(loc.get("score", 0) or 0)
            gol_v = int(vis.get("score", 0) or 0)
            nombre_cruce = f"{nom_l} vs {nom_v}"

            _, _, _, badge_vivo, _ = detectar_estado_partido(comp, ev.get("date", ""))
            stats = extraer_metricas_partido_reales(loc, vis)

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

            with st.expander(f"📊 Estadísticas en Cancha ({nombre_cruce})", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("🎯 Disparos Totales", f"{stats['toth_l']} - {stats['toth_v']}", f"Total: {stats['toth_tot']}")
                with c2:
                    st.metric("🥅 Tiros al Arco", f"{stats['tmeta_l']} - {stats['tmeta_v']}", f"Total: {stats['tmeta_tot']}")
                with c3:
                    st.metric("💥 Disparos Fuera", f"{stats['tfuera_l']} - {stats['tfuera_v']}", f"Total: {stats['tfuera_tot']}")
                with c4:
                    st.metric("🚩 Córneres | Posesión", f"{stats['esquinas_l']} - {stats['esquinas_v']}", f"Pos: {stats['pos_l']}% - {stats['pos_v']}%")

                detalles_partido = comp.get("details", [])
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

# -----------------------------------------------------------------------------
# SECCIÓN 3: PRE-APUESTAS OVER 1.5 + DESCARGA DE REPORTE EN PDF
# -----------------------------------------------------------------------------
with sec_apuestas:
    st.subheader("🎯 Laboratorio Pre-Apuesta Over 1.5 + Exportación a PDF")
    st.caption("Cruza los goles reales anotados y recibidos por cada equipo con tu base de datos y descarga el boletín en PDF.")

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
            comp = evento.get("competitions", [{}])[0]
            st_state, es_ht, _, _, fecha_str = detectar_estado_partido(comp, evento.get("date", ""))
            if st_state != "pre" or es_ht:
                continue

            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                nom_local = competitors[0].get("team", {}).get("displayName", "Local")
                nom_visita = competitors[1].get("team", {}).get("displayName", "Visita")

                prob_final, cuota_justa, xg_base, fuente_tag = calcular_pre_poisson_real(
                    nom_local, nom_visita, stats_temporada_api
                )
                if prob_final >= umbral_minimo:
                    if 64.0 <= prob_final <= 75.5:
                        veredicto = "💎 ENTRAR OVER 1.5 (Cuota de Valor / Paga Bien)"
                    elif prob_final > 75.5:
                        veredicto = "🟢 ENTRAR OVER 1.5 (Fijo Alta Probabilidad)"
                    else:
                        veredicto = "🟡 VALOR MODERADO (Ideal para En Vivo)"

                    reporte_pre.append({
                        "Fecha": fecha_str,
                        "Liga": nombre_liga,
                        "Partido": f"{nom_local} vs {nom_v if 'nom_v' in locals() else nom_visita}",
                        "xG Esperado": xg_base,
                        "Prob. Pre Over 1.5": f"{prob_final}%",
                        "Cuota Estimada": cuota_justa,
                        "Base de Cálculo": fuente_tag,
                        "Veredicto": veredicto
                    })
                    reporte_pre[-1]["Partido"] = f"{nom_local} vs {nom_visita}"

    if reporte_pre:
        df_pre = pd.DataFrame(reporte_pre)
        
        # BOTÓN DE DESCARGA DIRECTA EN PDF
        col_btn_pdf, col_info_pdf = st.columns([1.5, 2.5])
        with col_btn_pdf:
            if PDF_DISPONIBLE:
                pdf_bytes = generar_pdf_preapuestas(df_pre)
                fecha_arch = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y%m%d_%H%M")
                st.download_button(
                    label="📄 DESCARGAR REPORTE PRE-APUESTA EN PDF",
                    data=pdf_bytes,
                    file_name=f"MRFUTBOL_PreApuestas_{fecha_arch}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.warning("⚠️ Agrega `fpdf2` en tu archivo requirements.txt de GitHub para habilitar el botón PDF.")
        with col_info_pdf:
            st.caption(f"✅ Se encontraron **{len(df_pre)} partidos** listos para incluir en tu boletín PDF.")

        st.dataframe(df_pre, use_container_width=True, hide_index=True)
    else:
        st.info("No hay partidos programados que cumplan el filtro actual. Puedes bajar el deslizador de porcentaje.")

# -----------------------------------------------------------------------------
# SECCIÓN 4: SCRAPING Y ALERTAS INDIVIDUALES POR PARTIDO EN VIVO
# -----------------------------------------------------------------------------
with sec_scraping:
    st.subheader("🚨 Motor de Scraping y Alertas Individuales en Vivo")
    
    c_sc1, c_sc2 = st.columns([2.8, 1.2])
    with c_sc1:
        st.markdown(
            "Marca la casilla **`🔔 Alerta VIP`** en los partidos en vivo de los que quieras recibir aviso de entrada "
            "a **Over 0.5** o **Over 1.5** en tu WhatsApp."
        )
    with c_sc2:
        modo_todos = st.toggle(
            "📢 Alertar en TODOS los partidos",
            value=st.session_state["scraping_modo_todos"],
            key="toggle_scrap_all"
        )
        if modo_todos != st.session_state["scraping_modo_todos"]:
            st.session_state["scraping_modo_todos"] = modo_todos
            guardar_estado_permanente()
            st.rerun()

    partidos_scraping_activos = False
    for nombre_liga, contenido in datos_globales.items():
        for evento in contenido["eventos"]:
            comp = evento.get("competitions", [{}])[0]
            st_state, es_ht, min_num, _, reloj_txt = detectar_estado_partido(comp, evento.get("date", ""))
            if st_state != "in" and not es_ht:
                continue

            competitors = comp.get("competitors", [])
            if len(competitors) == 2:
                partidos_scraping_activos = True
                ev_id = str(evento.get("id"))
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
                stats = extraer_metricas_partido_reales(loc, vis)
                toth_tot = stats["toth_tot"]
                tmeta_tot = stats["tmeta_tot"]

                # Control de suscripción individual en Scraping (o si también lo marcó en Portada)
                seguido_indiv = (ev_id in st.session_state["seguidos_scraping"]) or (ev_id in st.session_state["seguidos_portada"])
                col_s_info, col_s_chk = st.columns([9.5, 2.5])

                with col_s_chk:
                    chk_scrap = st.checkbox(
                        "🔔 Alerta VIP",
                        value=seguido_indiv,
                        key=f"scr_bell_{ev_id}"
                    )
                    if chk_scrap and ev_id not in st.session_state["seguidos_scraping"]:
                        st.session_state["seguidos_scraping"].append(ev_id)
                        guardar_estado_permanente()
                    elif not chk_scrap and ev_id in st.session_state["seguidos_scraping"]:
                        st.session_state["seguidos_scraping"].remove(ev_id)
                        guardar_estado_permanente()

                debe_notificar = st.session_state["scraping_modo_todos"] or chk_scrap

                veredicto_vivo = f"⏳ Calentando ({prob_pre}% Pre | Esperando Min 15+)"
                if min_num >= 15 or es_ht:
                    if goles_tot == 0:
                        if tmeta_tot >= 2 or toth_tot >= 6 or (prob_pre >= 68 and toth_tot >= 4):
                            veredicto_vivo = (
                                f"🚨 ¡ENTRAR AL OVER 0.5 GOLES! "
                                f"(Pre: {prob_pre}% + En vivo: {toth_tot} Disp y {tmeta_tot} al Arco)"
                            )
                            if debe_notificar:
                                disparar_alerta_evento(
                                    f"ov05_{ev_id}",
                                    f"🚨 ENTRAR OVER 0.5: {nombre_cruce}",
                                    f"Reloj: {reloj_txt} (0-0) | Pre: {prob_pre}% | Disparos: {toth_tot} ({tmeta_tot} al arco)",
                                    "🚨"
                                )
                        else:
                            veredicto_vivo = f"⚪ Monitoreando 0-0 (Pre: {prob_pre}% | {toth_tot} Disp, {tmeta_tot} Arco)"
                    elif goles_tot == 1:
                        if min_num <= 82 and (tmeta_tot >= 3 or toth_tot >= 7 or (prob_pre >= 68 and toth_tot >= 5)):
                            veredicto_vivo = (
                                f"🔥 ¡ENTRAR AL OVER 1.5 GOLES! "
                                f"(Pre: {prob_pre}% + En vivo: {toth_tot} Disp y {tmeta_tot} al Arco)"
                            )
                            if debe_notificar:
                                disparar_alerta_evento(
                                    f"ov15_{ev_id}",
                                    f"🔥 ENTRAR OVER 1.5: {nombre_cruce}",
                                    f"Reloj: {reloj_txt} ({goles_l}-{goles_v}) | Pre: {prob_pre}% | Disparos: {toth_tot} ({tmeta_tot} al arco)",
                                    "🔥"
                                )
                        else:
                            veredicto_vivo = f"🟢 1 Gol en cancha (Pre: {prob_pre}% | {toth_tot} Disp, {tmeta_tot} Arco)"
                    else:
                        veredicto_vivo = f"✅ ¡LÍNEA OVER 1.5 COBRADA EN VERDE! ({goles_l}-{goles_v})"

                with col_s_info:
                    st.markdown(
                        f"**{reloj_txt}** | {nombre_liga} | **{nombre_cruce}** (`{goles_l} - {goles_v}`) "
                        f"— 📈 Pre: `{prob_pre}%` | 🎯 Disp: `{stats['toth_l']}-{stats['toth_v']} ({toth_tot})` | "
                        f"🥅 Arco: `{stats['tmeta_l']}-{stats['tmeta_v']} ({tmeta_tot})`  \n"
                        f"👉 **{veredicto_vivo}**"
                    )
                st.divider()

    if not partidos_scraping_activos:
        st.info("No hay partidos en vivo en este momento para evaluar en el motor de scraping.")

# TEMPORIZADOR NO BLOQUEANTE AL FINAL DEL ARCHIVO (CONSERVANDO LOS PARÁMETROS DEL USUARIO)
if st.session_state["auto_refresh"]:
    components.html("""
    <script>
    setTimeout(function() {
        window.parent.location.reload();
    }, 120000);
    </script>
    """, height=0)
