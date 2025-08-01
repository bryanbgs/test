# lista.py
from flask import Flask, Response, request, render_template_string, render_template
import scraper
import time
import os

app = Flask(__name__)

ULTIMA_ACTUALIZACION = 0
STREAMS = {}
CACHE_SECONDS = 15 * 60  # 15 minutos


def leer_canales():
    try:
        with open("canales.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except Exception as e:
        print(f"[❌] Error leyendo canales.txt: {e}")
        return ["foxsports", "tudn"]


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
        try:
            url_real = scraper.obtener_stream_url(canal, timeout=30)
            if url_real:
                nuevos_streams[canal] = url_real
                print(f"[✅] Stream obtenido para {canal}")
            elif canal in STREAMS:
                print(f"[🔁] Usando caché para {canal}")
                nuevos_streams[canal] = STREAMS[canal]
            else:
                print(f"[❌] Sin stream ni caché para {canal}")
        except Exception as e:
            print(f"[💥] Error procesando {canal}: {e}")
            if canal in STREAMS:
                nuevos_streams[canal] = STREAMS[canal]

    STREAMS.update(nuevos_streams)
    ULTIMA_ACTUALIZACION = ahora
    print(f"[✅] Actualización completada. {len(nuevos_streams)} canales actualizados.")


@app.route("/stream/<canal>")
def get_user_stream(canal):
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    client_ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.remote_addr

    print(f"[🔑] Cliente {client_ip} solicitando {canal}")

    try:
        url_con_token = scraper.obtener_stream_url_para_cliente(canal, client_ip, timeout=30)
        if url_con_token:
            print(f"[✅] Token generado para {client_ip}")
            return Response(
                url_con_token.strip(),
                mimetype="application/vnd.apple.mpegurl",
                headers={"Content-Disposition": "inline; filename=stream.m3u8"}
            )
        else:
            return "No se pudo generar stream para tu IP", 404
    except Exception as e:
        print(f"[💥] Error generando token para {client_ip}: {e}")
        return "Error generando stream", 500


@app.route("/direct/<canal>")
def direct_url(canal):
    actualizar_streams()
    url_real = STREAMS.get(canal)
    if url_real:
        return Response(url_real, mimetype="text/plain")
    else:
        return "Stream no disponible", 404


@app.route("/playlist.m3u")
def playlist():
    base_url = request.url_root.rstrip("/")
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    client_ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.remote_addr

    m3u = f"#EXTM3U x-tvg-url=\"https://la14hd.com\"\n"
    m3u += f"# Generado para IP: {client_ip}\n"
    canales = leer_canales()

    for canal in canales:
        nombre = canal.replace("-", " ").upper()
        m3u += f'#EXTINF:-1 tvg-name="{nombre}" group-title="la14hd", {nombre}\n'
        m3u += f"{base_url}/stream/{canal}\n"

    return Response(m3u, mimetype="application/x-mpegurl")


@app.route("/")
def index():
    actualizar_streams()
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    client_ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.remote_addr

    html = f"""
    <h1>🎯 la14hd Smart Proxy</h1>
    <h2>✨ Genera tokens individuales por IP</h2>
    <div style="background: #f0f8ff; padding: 15px; border-radius: 8px; margin: 10px 0;">
        <h3>🔑 ¿Cómo funciona?</h3>
        <p><strong>Tu IP:</strong> {client_ip}</p>
        <p>✅ Cada cliente genera su propio token desde su IP</p>
        <p>✅ Sin restricciones ni conflictos de tokens</p>
        <p>✅ Funciona como si accedieras directo desde tu ubicación</p>
    </div>
    <h2>📺 Canales disponibles:</h2>
    <ul>
    """
    canales = leer_canales()
    for canal in canales:
        html += f'''
        <li style="margin: 10px 0;">
            <strong>{canal.upper()}</strong><br>
            <a href="/stream/{canal}" target="_blank" style="color: #2196F3;">🎬 Obtener URL con tu IP</a>
        </li>
        '''
    html += f"""
    </ul>
    <h2>📄 Playlist:</h2>
    <p><a href='/playlist.m3u' style="color: #4CAF50;">📥 Descargar playlist.m3u (para tu IP: {client_ip})</a></p>
    <h2>📺 Instrucciones VLC:</h2>
    <ol>
        <li>Pega esta URL en VLC: <code>{request.url_root}stream/foxsports</code></li>
        <li>¡El token se genera automáticamente con tu IP!</li>
    </ol>
    """
    return html


@app.route("/debug")
def debug():
    return {
        "streams_disponibles": list(STREAMS.keys()),
        "total_streams": len(STREAMS),
        "ultima_actualizacion": time.ctime(ULTIMA_ACTUALIZACION) if ULTIMA_ACTUALIZACION else "Nunca",
        "cache_expira_en": max(0, int((CACHE_SECONDS - (time.time() - ULTIMA_ACTUALIZACION)) / 60)) if ULTIMA_ACTUALIZACION else 0
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

@app.route("/play/<canal>")
def play_stream(canal):
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    client_ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.remote_addr
    print(f"[▶️] Reproducción solicitada por {client_ip} para {canal}")

    try:
        # Generar la URL del stream con token para esta IP
        url_con_token = scraper.obtener_stream_url_para_cliente(canal, client_ip, timeout=30)
        if not url_con_token:
            return """
            <h1>❌ Stream no disponible</h1>
            <p>No se pudo obtener el stream para tu IP.</p>
            <a href='/'>« Volver al inicio</a>
            """, 404

        # Leer la plantilla HTML desde archivo o como string
        template_path = os.path.join("templates", "player.html")
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                template = f.read()
        else:
            return "❌ Plantilla player.html no encontrada", 500

        # Renderizar con datos
        rendered = render_template_string(
            template,
            canal=canal,
            nombre=canal.replace("-", " ").upper(),
            stream_url=f"/stream/{canal}"  # La ruta interna que devuelve el .m3u8
        )
        return rendered

    except Exception as e:
        print(f"[💥] Error en reproducción: {e}")
        return f"<h1>❌ Error interno: {str(e)}</h1><a href='/'>« Inicio</a>", 500
