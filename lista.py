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
def get_user_stream(canal):
    """Cada cliente genera su propio token desde su IP"""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    print(f"[🔑] Cliente {client_ip} solicitando {canal}")
    
    # Ejecutar scraping desde la IP del cliente (a través de nuestro servidor)
    try:
        print(f"[🌐] Generando token para IP: {client_ip}")
        url_con_token = scraper.obtener_stream_url_para_cliente(canal, client_ip)
        
        if url_con_token:
            print(f"[✅] Token generado para {client_ip}")
            return Response(url_con_token, mimetype="text/plain")
        else:
            return "No se pudo generar stream para tu IP", 404
            
    except Exception as e:
        print(f"[💥] Error generando token para {client_ip}: {e}")
        return "Error generando stream", 500

@app.route("/direct-proxy/<canal>")
def direct_proxy_stream(canal):
    """Genera token en tiempo real sin cache"""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    print(f"[⚡] Generación directa para {client_ip} - {canal}")
    
    # No usar cache, generar fresh token
    url_fresh = scraper.obtener_stream_url(canal)
    
    if url_fresh:
        return Response(url_fresh, mimetype="text/plain")
    else:
        return "Stream no disponible", 404

def proxy_m3u8_content(m3u8_content, base_url, canal):
    """Modifica el contenido m3u8 para que los segmentos pasen por nuestro proxy"""
    lines = m3u8_content.split('\n')
    modified_lines = []
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            # Es una URL de segmento
            if line.startswith('http'):
                # URL absoluta - crear proxy
                segment_url = line
            else:
                # URL relativa - construir URL completa
                segment_url = urljoin(base_url, line)
            
            # Crear URL de proxy para este segmento
            proxy_url = f"/segment/{canal}/" + requests.utils.quote(segment_url, safe='')
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
        'Range': request.headers.get('Range', '')
    })
    
    try:
        response = session.get(real_segment_url, stream=True, timeout=15)
        
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
    """Genera playlist que cada cliente usará con su propia IP"""
    base_url = request.url_root.rstrip("/")
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    m3u = f"#EXTM3U x-tvg-url=\"https://la14hd.com\" \n"
    m3u += f"# Generado para IP: {client_ip}\n"
    
    canales = leer_canales()
    for canal in canales:
        nombre = canal.replace("-", " ").upper()
        m3u += f'#EXTINF:-1 tvg-name="{nombre}" group-title="la14hd", {nombre}\n'
        m3u += f"{base_url}/stream/{canal}\n"
    
    return Response(m3u, mimetype="application/x-mpegurl")

@app.route("/")
def index():
    """Página de prueba con instrucciones para VLC"""
    actualizar_streams()
    html = """
    <h1>🎯 la14hd Smart Proxy</h1>
    <h2>✨ Genera tokens individuales por IP</h2>
    
    <div style="background: #f0f8ff; padding: 15px; border-radius: 8px; margin: 10px 0;">
        <h3>🔑 ¿Cómo funciona?</h3>
        <p><strong>Tu IP:</strong> """ + request.headers.get('X-Forwarded-For', request.remote_addr) + """</p>
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
            <a href="/stream/{canal}" target="_blank" style="color: #2196F3;">🎬 Obtener URL con tu IP</a> |
            <a href="/direct-proxy/{canal}" target="_blank" style="color: #FF9800;">⚡ Generación directa</a>
        </li>
        '''
    
    html += """
    </ul>
    
    <h2>📄 Playlist:</h2>
    <p><a href='/playlist.m3u' style="color: #4CAF50;">📥 Descargar playlist.m3u (personalizado para tu IP)</a></p>
    
    <h2>📺 Instrucciones VLC:</h2>
    <ol>
        <li>Copia la URL "🎬 Obtener URL con tu IP"</li>
        <li>Pégala en VLC → Media → Open Network Stream</li>
        <li>¡El token se genera automáticamente con tu IP!</li>
    </ol>
    
    <h2>🔗 URLs para tu IP:</h2>
    """
    
    base_url = request.url_root.rstrip("/")
    for canal in canales:
        html += f'<p><strong>{canal.upper()}:</strong> <code>{base_url}/stream/{canal}</code></p>'
    
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
