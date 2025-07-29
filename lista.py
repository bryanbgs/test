# lista.py
from flask import Flask, Response
import scraper
import time
import os

app = Flask(__name__)

# Configuración
CACHE_MINUTES = 15
CACHE_SECONDS = CACHE_MINUTES * 60

# Almacenamiento en memoria
ULTIMA_ACTUALIZACION = 0
CANALES_STREAMS = []

def leer_canales():
    """Lee los canales desde canales.txt"""
    canales = []
    with open("canales.txt", "r", encoding="utf-8") as f:
        for linea in f:
            canal = linea.strip()
            if canal and not canal.startswith("#"):
                canales.append(canal)
    return canales

def actualizar_streams():
    """Actualiza los streams de todos los canales"""
    global ULTIMA_ACTUALIZACION, CANALES_STREAMS
    ahora = time.time()
    if ahora - ULTIMA_ACTUALIZACION < CACHE_SECONDS:
        return

    print("[🔄] Actualizando streams...")
    canales = leer_canales()
    nuevos_streams = []

    for canal in canales:
        print(f"[📡] Procesando canal: {canal}")
        url_stream = scraper.obtener_stream_url(canal)
        if url_stream:
            nombre = canal.replace("-", " ").upper()
            nuevos_streams.append({
                "nombre": nombre,
                "stream_url": url_stream
            })
            print(f"[✅] {nombre}: {url_stream}")
        else:
            print(f"[❌] No se encontró stream para {canal}")

    CANALES_STREAMS = nuevos_streams
    ULTIMA_ACTUALIZACION = ahora
    print(f"[⏰] Próxima actualización en {CACHE_MINUTES} minutos")

@app.route("/playlist.m3u")
def playlist():
    actualizar_streams()
    m3u = "#EXTM3U x-tvg-url=\"https://la14hd.com\"\n"
    for canal in CANALES_STREAMS:
        m3u += f'#EXTINF:-1 tvg-name="{canal["nombre"]}" group-title="la14hd", {canal["nombre"]}\n'
        m3u += f"{canal['stream_url']}\n"
    return Response(m3u, mimetype="application/x-mpegurl")

@app.route("/")
def index():
    actualizar_streams()
    html = "<h1>la14hd IPTV Playlist</h1><ul>"
    for canal in CANALES_STREAMS:
        html += f'<li><a href="{canal["stream_url"]}" target="_blank">{canal["nombre"]}</a></li>'
    html += "</ul><p><a href='/playlist.m3u'>Descargar playlist.m3u</a></p>"
    return html

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
