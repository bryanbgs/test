# lista.py
from flask import Flask, Response, redirect, request, abort
import scraper
import time
import os
import requests
from urllib.parse import urlparse
from functools import wraps

app = Flask(__name__)

# Almacenamiento en memoria
ULTIMA_ACTUALIZACION = 0
STREAMS = {}  # { "foxsports": "https://...fubohd.com/...m3u8?token=..." }

CACHE_SECONDS = 15 * 60  # 15 minutos

# Configuración de timeout para requests
REQUEST_TIMEOUT = 10  # segundos

def leer_canales():
    """Lee los canales desde canales.txt"""
    try:
        with open("canales.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except Exception as e:
        print(f"[❌] Error leyendo canales.txt: {e}")
        return ["foxsports", "tudn"]  # fallback

def actualizar_streams():
    """Actualizar streams"""
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
            url_real = scraper.obtener_stream_url(canal)
            if url_real:
                nuevos_streams[canal] = url_real
                print(f"[✅] Stream obtenido para {canal}")
            else:
                # Mantener caché si existe
                if canal in STREAMS:
                    print(f"[🔁] Usando caché para {canal}")
                    nuevos_streams[canal] = STREAMS[canal]
                else:
                    print(f"[❌] Sin stream ni caché para {canal}")
        except Exception as e:
            print(f"[💥] Error procesando {canal}: {e}")
            # Mantener caché si existe
            if canal in STREAMS:
                print(f"[🔁] Usando caché para {canal} (por error)")
                nuevos_streams[canal] = STREAMS[canal]

    STREAMS.update(nuevos_streams)
    ULTIMA_ACTUALIZACION = ahora
    print(f"[✅] Actualización completada. {len(nuevos_streams)} canales actualizados.")
    print(f"[⏰] Próxima actualización en {CACHE_SECONDS//60} minutos")

def add_response_headers(headers={}):
    """Decorador para agregar headers a las respuestas"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            resp = f(*args, **kwargs)
            if isinstance(resp, Response):
                for hdr, val in headers.items():
                    resp.headers[hdr] = val
            return resp
        return decorated_function
    return decorator

@app.route("/stream/<canal>")
@add_response_headers({
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
})
def proxy_stream(canal):
    """Proxy inverso que mantiene la IP del cliente"""
    actualizar_streams()
    url_real = STREAMS.get(canal)
    
    if not url_real:
        return "Stream no disponible", 404
    
    # Extraer el dominio base para los headers
    parsed_url = urlparse(url_real)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    # Configurar headers para mantener la IP original
    headers = {
        "Referer": domain + "/",
        "Origin": domain,
        "User-Agent": request.headers.get("User-Agent", ""),
        "X-Forwarded-For": request.remote_addr,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }
    
    # Hacer streaming del contenido
    try:
        req = requests.get(
            url_real,
            headers=headers,
            stream=True,
            timeout=REQUEST_TIMEOUT
        )
        
        if req.status_code != 200:
            print(f"[⚠️] Respuesta no exitosa: {req.status_code}")
            return "Error al obtener el stream", 502
            
        return Response(
            req.iter_content(chunk_size=1024*16),  # 16KB chunks
            content_type=req.headers.get('Content-Type', 'application/octet-stream'),
            status=req.status_code
        )
    except requests.exceptions.Timeout:
        print(f"[⏰] Timeout al obtener stream para {canal}")
        return "Timeout al conectar con el servidor", 504
    except Exception as e:
        print(f"[💥] Error en proxy para {canal}: {str(e)}")
        return "Error al obtener el stream", 502

@app.route("/playlist.m3u")
def playlist():
    """Genera una lista IPTV con URLs limpias"""
    actualizar_streams()
    base_url = request.url_root.rstrip("/")
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

@app.route("/debug")
def debug():
    """Endpoint de debug simple"""
    return {
        "streams_disponibles": list(STREAMS.keys()),
        "total_streams": len(STREAMS),
        "ultima_actualizacion": time.ctime(ULTIMA_ACTUALIZACION) if ULTIMA_ACTUALIZACION else "Nunca",
        "cache_expira_en": max(0, int((CACHE_SECONDS - (time.time() - ULTIMA_ACTUALIZACION))/60)) if ULTIMA_ACTUALIZACION else 0
    }

@app.route("/test/<canal>")
def test_canal(canal):
    """Probar un canal específico sin cache"""
    print(f"[🧪] Prueba directa de {canal}")
    url = scraper.obtener_stream_url(canal)
    if url:
        return {"status": "success", "canal": canal, "url": url[:50] + "..."}
    else:
        return {"status": "failed", "canal": canal, "url": None}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
