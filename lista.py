from flask import Flask, Response, request
import scraper
import time
import os

app = Flask(__name__)

# Almacenamiento en memoria (suficiente para Render)
ULTIMA_ACTUALIZACION = 0
CANALES = []

CACHE_MINUTES = 15
CACHE_SECONDS = CACHE_MINUTES * 60

def actualizar_canales():
    """Actualiza la lista de canales y sus streams"""
    global ULTIMA_ACTUALIZACION, CANALES
    ahora = time.time()
    if ahora - ULTIMA_ACTUALIZACION < CACHE_SECONDS:
        return

    print("[🔄] Actualizando lista de canales...")
    canales_activos = scraper.obtener_canales_activos()
    canales_con_stream = []

    for canal in canales_activos:
        stream_url = scraper.obtener_stream_url(canal["href"])
        if stream_url:
            canales_con_stream.append({
                "nombre": canal["nombre"],
                "stream_url": stream_url
            })
            print(f"[✅] {canal['nombre']}: {stream_url}")

    CANALES = canales_con_stream
    ULTIMA_ACTUALIZACION = ahora
    print(f"[⏰] Próxima actualización en {CACHE_MINUTES} minutos")

@app.route("/playlist.m3u")
def playlist():
    actualizar_canales()

    m3u = "#EXTM3U x-tvg-url=\"https://la14hd.com\"\n"
    for canal in CANALES:
        m3u += f'#EXTINF:-1 tvg-name="{canal["nombre"]}" group-title="la14hd", {canal["nombre"]}\n'
        m3u += f"{canal['stream_url']}\n"

    return Response(m3u, mimetype="application/x-mpegurl")

@app.route("/")
def index():
    actualizar_canales()
    html = "<h1>la14hd IPTV Playlist</h1><ul>"
    for canal in CANALES:
        html += f'<li><a href="{canal["stream_url"]}" target="_blank">{canal["nombre"]}</a></li>'
    html += "</ul><p><a href='/playlist.m3u'>Descargar playlist.m3u</a></p>"
    return html

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
