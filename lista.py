# lista.py
from flask import Flask, Response, redirect, request
import scraper
import time
import os

app = Flask(__name__)

# Almacenamiento en memoria
ULTIMA_ACTUALIZACION = 0
STREAMS = {}  # { "foxsports": "https://...fubohd.com/...m3u8?token=..." }

CACHE_SECONDS = 15 * 60  # 15 minutos

def leer_canales():
    """Lee los canales desde canales.txt"""
    try:
        with open("canales.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except Exception as e:
        print(f"[❌] Error leyendo canales.txt: {e}")
        return ["foxsports", "tudn"]  # fallback

def actualizar_streams():
    global ULTIMA_ACTUALIZACION, STREAMS
    ahora = time.time()
    if ahora - ULTIMA_ACTUALIZACION < CACHE_SECONDS:
        return

    print("[🔄] Iniciando actualización de streams...")
    nuevos_streams = {}
    canales = leer_canales()

    for canal in canales:
        print(f"[📡] Procesando canal: {canal}")
        url_real = scraper.obtener_stream_url(canal)
        if url_real:
            nuevos_streams[canal] = url_real
        else:
            # Mantener caché si existe
            if canal in STREAMS:
                print(f"[🔁] Usando caché para {canal}")
                nuevos_streams[canal] = STREAMS[canal]
            else:
                print(f"[❌] Sin stream ni caché para {canal}")

    STREAMS.update(nuevos_streams)
    ULTIMA_ACTUALIZACION = ahora
    print(f"[✅] Actualización completada. {len(nuevos_streams)} canales actualizados.")
    print(f"[⏰] Próxima actualización en 15 minutos")

@app.route("/stream/<canal>")
def proxy_stream(canal):
    """Redirige a la URL real del stream (oculta el token)"""
    actualizar_streams()
    url_real = STREAMS.get(canal)
    if url_real:
        return redirect(url_real)
    else:
        return "Stream no disponible", 404

@app.route("/playlist.m3u")
def playlist():
    """Genera una lista IPTV con URLs limpias"""
    actualizar_streams()
    base_url = request.url_root.rstrip("/")  # https://tu-app.onrender.com
    m3u = "#EXTM3U x-tvg-url=\"https://la14hd.com\"\n"
    for canal, url in STREAMS.items():
        nombre = canal.replace("-", " ").upper()
        m3u += f'#EXTINF:-1 tvg-name="{nombre}" group-title="la14hd", {nombre}\n'
        m3u += f"{base_url}/stream/{canal}\n"
    return Response(m3u, mimetype="application/x-mpegurl")

@app.route("/")
def index():
    """Página de prueba"""
    actualizar_streams()
    html = "<h1>la14hd IPTV Playlist</h1><ul>"
    for canal in STREAMS:
        html += f'<li><a href="/stream/{canal}" target="_blank">{canal.upper()}</a></li>'
    html += "</ul><p><a href='/playlist.m3u'>Descargar playlist.m3u</a></p>"
    return html

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
