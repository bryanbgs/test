# lista.py - Versión Final Funcional
from flask import Flask, Response, redirect, request
import scraper
import time
import os
import requests
from urllib.parse import urlparse, urljoin, unquote
from functools import wraps

app = Flask(__name__)

# Almacenamiento en memoria
ULTIMA_ACTUALIZACION = 0
STREAMS = {}  # { "foxsports": {"url": "https://...m3u8", "base_url": "https://.../"} }

CACHE_SECONDS = 15 * 60  # 15 minutos
REQUEST_TIMEOUT = 20  # segundos

def leer_canales():
    """Lee los canales desde canales.txt"""
    try:
        with open("canales.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except Exception as e:
        print(f"[❌] Error leyendo canales.txt: {e}")
        return ["foxsports", "tudn"]  # fallback

def actualizar_streams():
    """Actualizar streams con estructura mejorada"""
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
                parsed_url = urlparse(url_real)
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                
                # Extraer el path base (sin el nombre del archivo m3u8)
                path_parts = parsed_url.path.split('/')
                if path_parts[-1].endswith('.m3u8'):
                    base_path = '/'.join(path_parts[:-1])
                else:
                    base_path = parsed_url.path
                
                nuevos_streams[canal] = {
                    "url": url_real,
                    "base_url": base_url,
                    "base_path": base_path,
                    "full_path": parsed_url.path,
                    "channel_id": path_parts[-1].replace('.m3u8', '')
                }
                print(f"[✅] Stream obtenido para {canal}")
            else:
                if canal in STREAMS:
                    print(f"[🔁] Usando caché para {canal}")
                    nuevos_streams[canal] = STREAMS[canal]
                else:
                    print(f"[❌] Sin stream ni caché para {canal}")
        except Exception as e:
            print(f"[💥] Error procesando {canal}: {e}")
            if canal in STREAMS:
                print(f"[🔁] Usando caché para {canal} (por error)")
                nuevos_streams[canal] = STREAMS[canal]

    STREAMS.update(nuevos_streams)
    ULTIMA_ACTUALIZACION = ahora
    print(f"[✅] Actualización completada. {len(nuevos_streams)} canales actualizados.")

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

def get_proxy_headers(url_real, request):
    """Genera headers para las solicitudes proxy"""
    parsed_url = urlparse(url_real)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    return {
        "Referer": domain + "/",
        "Origin": domain,
        "User-Agent": request.headers.get("User-Agent", ""),
        "X-Forwarded-For": request.remote_addr,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }

@app.route("/stream/<path:subpath>")
@add_response_headers({
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
})
def proxy_stream(subpath):
    """Maneja tanto el canal principal como los segmentos TS"""
    actualizar_streams()
    
    # Decodificar la URL (por si hay caracteres especiales)
    subpath = unquote(subpath)
    
    # Manejar solicitudes de segmentos TS
    if '.ts' in subpath or '.m4s' in subpath:
        return handle_ts_segment(subpath)
    
    # Si es solo el nombre del canal (ej. foxsports)
    canal = subpath.split('/')[0]
    if canal not in STREAMS:
        return "Canal no encontrado", 404
    
    stream_info = STREAMS[canal]
    return proxy_m3u8(stream_info["url"], stream_info)

def handle_ts_segment(subpath):
    """Maneja específicamente las solicitudes de segmentos TS"""
    # Extraer el canal de la ruta (puede ser foxsports/mono/segmento.ts)
    parts = subpath.split('/')
    possible_channels = [p for p in parts if p in STREAMS]
    
    if not possible_channels:
        return "Canal no encontrado en la ruta del segmento", 404
    
    canal = possible_channels[0]
    stream_info = STREAMS[canal]
    
    # Reconstruir la ruta original del segmento
    ts_relative_path = subpath[len(canal)+1:]
    
    # Manejar el caso especial donde hay múltiples ?token=
    if '?token=' in ts_relative_path:
        ts_relative_path = ts_relative_path.split('?token=')[0] + '?token=' + ts_relative_path.split('?token=')[1].split('?token=')[0]
    
    # Construir la URL completa del segmento
    ts_url = f"{stream_info['base_url']}{stream_info['base_path']}/{ts_relative_path}"
    
    print(f"[🔍] Proxying segmento: {ts_url}")
    return proxy_segment(ts_url)

def proxy_m3u8(url_real, stream_info):
    """Proxy para archivos M3U8 que reescribe las URLs de los segmentos"""
    try:
        req = requests.get(
            url_real,
            headers=get_proxy_headers(url_real, request),
            timeout=REQUEST_TIMEOUT
        )
        
        if req.status_code != 200:
            print(f"[⚠️] Respuesta no exitosa: {req.status_code}")
            return "Error al obtener el stream", 502
            
        content_type = req.headers.get('Content-Type', 'application/vnd.apple.mpegurl')
        
        if 'mpegurl' in content_type.lower():
            content = req.text
            lines = content.split('\n')
            new_lines = []
            
            for line in lines:
                if line.strip() and not line.startswith('#') and ('.ts' in line or '.m4s' in line):
                    # Manejar URLs con parámetros
                    segment_path = line.split('?')[0]
                    params = line.split('?')[1] if '?' in line else ''
                    
                    # Extraer solo el nombre del segmento
                    segment_name = segment_path.split('/')[-1]
                    
                    # Construir nueva ruta manteniendo la estructura de subdirectorios
                    new_path = f"/stream/{stream_info['channel_id']}/{segment_name}"
                    if params:
                        new_path += f"?{params.split('&')[0]}"  # Tomar solo el primer parámetro token
                    
                    new_lines.append(new_path)
                else:
                    new_lines.append(line)
            
            return Response('\n'.join(new_lines), content_type=content_type)
        else:
            return Response(req.content, content_type=content_type)
            
    except requests.exceptions.Timeout:
        print(f"[⏰] Timeout al obtener M3U8")
        return "Timeout al conectar con el servidor", 504
    except Exception as e:
        print(f"[💥] Error en proxy M3U8: {str(e)}")
        return "Error al obtener el stream", 502

def proxy_segment(url_real):
    """Proxy para segmentos TS"""
    try:
        # Limpiar URL de parámetros duplicados
        if '?token=' in url_real:
            base_url = url_real.split('?token=')[0]
            token = url_real.split('?token=')[1].split('&')[0]
            url_real = f"{base_url}?token={token}"
        
        req = requests.get(
            url_real,
            headers=get_proxy_headers(url_real, request),
            stream=True,
            timeout=REQUEST_TIMEOUT
        )
        
        if req.status_code != 200:
            print(f"[⚠️] Respuesta no exitosa para segmento: {req.status_code}")
            return "Error al obtener el segmento", 502
            
        return Response(
            req.iter_content(chunk_size=1024*16),
            content_type=req.headers.get('Content-Type', 'video/MP2T'),
            direct_passthrough=True
        )
    except requests.exceptions.Timeout:
        print(f"[⏰] Timeout al obtener segmento TS")
        return "Timeout al conectar con el servidor", 504
    except Exception as e:
        print(f"[💥] Error en proxy segmento: {str(e)}")
        return "Error al obtener el segmento", 502

@app.route("/playlist.m3u")
def playlist():
    """Genera una lista IPTV con URLs limpias"""
    actualizar_streams()
    base_url = request.url_root.rstrip("/")
    m3u = "#EXTM3U x-tvg-url=\"https://la14hd.com\"\n"
    for canal, info in STREAMS.items():
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
