# lista.py
from flask import Flask, Response, redirect, request, stream_template
import scraper
import time
import os
import requests
import threading
from urllib.parse import urljoin, urlparse

app = Flask(__name__)

# Almacenamiento en memoria - IGUAL QUE EL ORIGINAL
ULTIMA_ACTUALIZACION = 0
STREAMS = {}  # { "foxsports": "https://...fubohd.com/...m3u8?token=..." }

CACHE_SECONDS = 15 * 60  # 15 minutos - IGUAL QUE EL ORIGINAL

def leer_canales():
    """Lee los canales desde canales.txt - IGUAL QUE EL ORIGINAL"""
    try:
        with open("canales.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except Exception as e:
        print(f"[❌] Error leyendo canales.txt: {e}")
        return ["foxsports", "tudn"]  # fallback

def actualizar_streams():
    """Actualizar streams - SIMPLIFICADO pero manteniendo lógica original"""
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
            # Timeout más corto para evitar cuelgues
            url_real = scraper.obtener_stream_url(canal)
            if url_real:
                nuevos_streams[canal] = url_real
                print(f"[✅] Stream obtenido para {canal}")
            else:
                # Mantener caché si existe - IGUAL QUE EL ORIGINAL
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
    print(f"[⏰] Próxima actualización en 15 minutos")

@app.route("/stream/<canal>")
def proxy_stream(canal):
    """Retransmite el stream en tiempo real actuando como proxy"""
    actualizar_streams()
    url_real = STREAMS.get(canal)
    if not url_real:
        return "Stream no disponible", 404
    
    print(f"[🎬] Iniciando retransmisión de {canal}")
    
    def generate_stream():
        """Genera el stream en tiempo real"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Referer': 'https://la14hd.com/',
            'Origin': 'https://la14hd.com',
            'Accept': '*/*',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive'
        })
        
        try:
            print(f"[📡] Conectando a stream: {url_real[:50]}...")
            
            # Si es un archivo .m3u8, necesitamos manejarlo diferente
            if url_real.endswith('.m3u8'):
                # Descargar el playlist m3u8
                response = session.get(url_real, stream=True, timeout=10)
                if response.status_code == 200:
                    m3u8_content = response.text
                    print(f"[📋] Playlist m3u8 obtenido ({len(m3u8_content)} caracteres)")
                    
                    # Modificar las URLs relativas en el m3u8 para que pasen por nuestro proxy
                    base_url = '/'.join(url_real.split('/')[:-1]) + '/'
                    modified_m3u8 = proxy_m3u8_content(m3u8_content, base_url, canal)
                    
                    yield modified_m3u8.encode('utf-8')
                else:
                    print(f"[❌] Error descargando m3u8: {response.status_code}")
                    yield b"#EXTM3U\n#EXT-X-ENDLIST\n"
            else:
                # Stream directo
                response = session.get(url_real, stream=True, timeout=10)
                if response.status_code == 200:
                    print(f"[✅] Stream conectado, retransmitiendo...")
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                else:
                    print(f"[❌] Error conectando al stream: {response.status_code}")
                    
        except Exception as e:
            print(f"[💥] Error en generate_stream: {e}")
            yield b"#EXTM3U\n#EXT-X-ENDLIST\n"
    
    # Determinar el content-type apropiado
    if url_real.endswith('.m3u8'):
        content_type = 'application/vnd.apple.mpegurl'
    else:
        content_type = 'video/mp2t'
    
    return Response(
        generate_stream(),
        mimetype=content_type,
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Range'
        }
    )

def proxy_m3u8_content(m3u8_content, base_url, canal):
    """Modifica el contenido m3u8 para que los segmentos pasen por nuestro proxy"""
    lines = m3u8_content.split('\n')
    modified_lines = []
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            # Es una URL de segmento
            if line.startswith('http'):
                segment_url = line
            else:
                # URL relativa - construir URL completa
                segment_url = urljoin(base_url, line)
            
            # AQUÍ ESTÁ EL FIX: Encodear correctamente la URL
            from urllib.parse import quote
            encoded_url = quote(segment_url, safe='')
            proxy_url = f"/segment/{canal}/{encoded_url}"
            modified_lines.append(proxy_url)
        else:
            modified_lines.append(line)
    
    return '\n'.join(modified_lines)

@app.route("/segment/<canal>/<path:segment_url>")
def proxy_segment(canal, segment_url):
    """Proxy para segmentos de video individuales"""
    # Decodificar la URL del segmento
    from urllib.parse import unquote
    real_segment_url = unquote(segment_url)
    
    print(f"[🎞️] Sirviendo segmento: {real_segment_url[:50]}...")
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Referer': 'https://la14hd.com/',
        'Origin': 'https://la14hd.com',
        'Accept': '*/*',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache'
    })
    
    try:
        response = session.get(url_real, stream=True, timeout=30, allow_redirects=True)
        
        def generate_segment():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        return Response(
            generate_segment(),
            status=response.status_code,
            mimetype='video/mp2t',
            headers={
                'Content-Length': response.headers.get('Content-Length'),
                'Content-Range': response.headers.get('Content-Range'),
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'no-cache',
                'Access-Control-Allow-Origin': '*'
            }
        )
        
    except Exception as e:
        print(f"[💥] Error sirviendo segmento: {e}")
        return "Segment not available", 404

@app.route("/test-direct/<canal>")
def test_direct(canal):
    actualizar_streams()
    url_real = STREAMS.get(canal)
    return redirect(url_real) if url_real else "No disponible"

@app.route("/direct/<canal>")
def direct_url(canal):
    """Devuelve la URL directa (comportamiento anterior)"""
    actualizar_streams()
    url_real = STREAMS.get(canal)
    if url_real:
        return Response(url_real, mimetype="text/plain")
    else:
        return "Stream no disponible", 404

@app.route("/playlist.m3u")
def playlist():
    """Genera una lista IPTV con URLs limpias - IGUAL QUE EL ORIGINAL"""
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
    """Página de prueba con instrucciones para VLC"""
    actualizar_streams()
    html = """
    <h1>🎬 la14hd IPTV Proxy Server</h1>
    <h2>📺 Streams disponibles (RETRANSMISIÓN):</h2>
    <ul>
    """
    for canal in STREAMS:
        html += f'''
        <li>
            <strong>{canal.upper()}</strong><br>
            <a href="/stream/{canal}" target="_blank">🎬 Stream Proxy (Recomendado)</a> | 
            <a href="/direct/{canal}" target="_blank">📋 URL Directa</a>
        </li>
        '''
    html += """
    </ul>
    <h2>📁 Descargas:</h2>
    <p><a href='/playlist.m3u'>📄 Descargar playlist.m3u (Proxy)</a></p>
    
    <h2>📺 Cómo usar:</h2>
    
    <h3>🎬 Opción 1: Stream Proxy (RECOMENDADO)</h3>
    <p><strong>✅ Ventajas:</strong> Sin tokens, sin restricciones, funciona desde cualquier lugar</p>
    <ol>
        <li>Copia la URL del "Stream Proxy"</li>
        <li>Abre VLC → Media → Open Network Stream</li>
        <li>Pega la URL completa</li>
        <li>¡Disfruta! El stream pasa por nuestro servidor</li>
    </ol>
    
    <h3>📋 Opción 2: URL Directa</h3>
    <p><strong>⚠️ Limitaciones:</strong> Tokens temporales, puede no funcionar</p>
    
    <h2>🔗 URLs Proxy para VLC:</h2>
    """
    base_url = request.url_root.rstrip("/")
    for canal in STREAMS:
        html += f'<p><strong>{canal.upper()}:</strong> <code>{base_url}/stream/{canal}</code></p>'
    
    html += """
    <h2>💡 ¿Cómo funciona el Proxy?</h2>
    <p>🔄 Tu dispositivo → Nuestro servidor → Stream original → De vuelta a ti</p>
    <p>✅ El servidor maneja todos los tokens y restricciones por ti</p>
    """
    
    html += "</div>"
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
