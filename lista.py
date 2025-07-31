# lista.py
from flask import Flask, Response, redirect, request, render_template_string
import time
import os

app = Flask(__name__)

def leer_canales():
    """Lee los canales desde canales.txt"""
    try:
        with open("canales.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except Exception as e:
        print(f"[❌] Error leyendo canales.txt: {e}")
        return ["foxsports"]

@app.route("/")
def index():
    """Página principal con scraper JavaScript"""
    canales = leer_canales()
    
    html_template = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎯 la14hd Smart Client Scraper</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        .canal { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 8px; }
        .status { font-weight: bold; }
        .success { color: #4CAF50; }
        .error { color: #f44336; }
        .loading { color: #2196F3; }
        button { background: #2196F3; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        .url-box { background: #e8f5e8; padding: 10px; border-radius: 4px; margin: 10px 0; font-family: monospace; word-break: break-all; }
        .instructions { background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; }
    </style>
</head>
<body>
    <h1>🎯 la14hd Smart Client Scraper</h1>
    
    <div class="instructions">
        <h3>💡 ¿Cómo funciona?</h3>
        <p><strong>✅ Tu navegador</strong> hace el scraping directamente desde <strong>tu IP</strong></p>
        <p><strong>✅ Sin problemas de tokens</strong> - se genera específicamente para ti</p>
        <p><strong>✅ Funciona en cualquier lugar</strong> del mundo</p>
    </div>

    <div id="canales">
        {% for canal in canales %}
        <div class="canal">
            <h3>📺 {{ canal.upper() }}</h3>
            <button onclick="obtenerStream('{{ canal }}')" id="btn-{{ canal }}">🔍 Obtener Stream</button>
            <div id="status-{{ canal }}" class="status"></div>
            <div id="url-{{ canal }}" class="url-box" style="display: none;"></div>
            <div id="vlc-{{ canal }}" style="display: none; margin-top: 10px;">
                <button onclick="copiarURL('{{ canal }}')">📋 Copiar para VLC</button>
                <button onclick="abrirVLC('{{ canal }}')">▶️ Abrir en VLC</button>
            </div>
        </div>
        {% endfor %}
    </div>

    <div class="instructions">
        <h3>📺 Instrucciones para VLC:</h3>
        <ol>
            <li>Haz clic en "🔍 Obtener Stream" del canal que quieras</li>
            <li>Cuando aparezca la URL, copia con "📋 Copiar para VLC"</li>
            <li>En VLC: Media → Open Network Stream → Pegar URL → Play</li>
        </ol>
    </div>

    <script>
        async function obtenerStream(canal) {
            const btnId = `btn-${canal}`;
            const statusId = `status-${canal}`;
            const urlId = `url-${canal}`;
            const vlcId = `vlc-${canal}`;
            
            const btn = document.getElementById(btnId);
            const status = document.getElementById(statusId);
            const urlDiv = document.getElementById(urlId);
            const vlcDiv = document.getElementById(vlcId);
            
            // Reset UI
            btn.disabled = true;
            status.className = 'status loading';
            status.textContent = '🔄 Iniciando scraping desde tu navegador...';
            urlDiv.style.display = 'none';
            vlcDiv.style.display = 'none';
            
            try {
                // Crear iframe oculto para hacer el scraping
                const iframe = document.createElement('iframe');
                iframe.style.display = 'none';
                iframe.src = `https://la14hd.com/vivo/canales.php?stream=${canal}`;
                document.body.appendChild(iframe);
                
                status.textContent = '🌐 Cargando página del canal...';
                
                // Esperar a que cargue el iframe
                await new Promise(resolve => {
                    iframe.onload = resolve;
                    setTimeout(resolve, 10000); // timeout de 10s
                });
                
                status.textContent = '🎬 Interceptando streams...';
                
                // Función para interceptar requests
                let capturedUrl = null;
                let attempts = 0;
                const maxAttempts = 60; // 60 segundos máximo
                
                const checkForStream = () => {
                    attempts++;
                    
                    // Simular interacción en el iframe
                    try {
                        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                        if (iframeDoc) {
                            // Intentar hacer clic en elementos del iframe
                            const clickableElements = iframeDoc.querySelectorAll('video, iframe, div, button');
                            if (clickableElements.length > 0) {
                                clickableElements[0].click();
                            }
                        }
                    } catch (e) {
                        // Ignorar errores de CORS
                    }
                    
                    if (attempts < maxAttempts && !capturedUrl) {
                        setTimeout(checkForStream, 1000);
                        status.textContent = `🔍 Buscando stream... (${attempts}/${maxAttempts})`;
                    } else if (!capturedUrl) {
                        // Timeout - usar método alternativo
                        usarMetodoAlternativo(canal);
                    }
                };
                
                // Iniciar búsqueda
                checkForStream();
                
                // Método alternativo: Solicitar al servidor que haga scraping
                async function usarMetodoAlternativo(canal) {
                    try {
                        status.textContent = '🔄 Usando método alternativo...';
                        const response = await fetch(`/scrape/${canal}`);
                        const data = await response.json();
                        
                        if (data.success && data.url) {
                            mostrarURL(data.url, canal);
                        } else {
                            mostrarError('No se pudo obtener el stream');
                        }
                    } catch (error) {
                        mostrarError('Error en método alternativo: ' + error.message);
                    }
                }
                
            } catch (error) {
                mostrarError('Error: ' + error.message);
            }
        }
        
        function mostrarURL(url, canal) {
            const statusId = `status-${canal}`;
            const urlId = `url-${canal}`;
            const vlcId = `vlc-${canal}`;
            const btnId = `btn-${canal}`;
            
            const status = document.getElementById(statusId);
            const urlDiv = document.getElementById(urlId);
            const vlcDiv = document.getElementById(vlcId);
            const btn = document.getElementById(btnId);
            
            status.className = 'status success';
            status.textContent = '✅ Stream obtenido exitosamente!';
            
            urlDiv.textContent = url;
            urlDiv.style.display = 'block';
            vlcDiv.style.display = 'block';
            btn.disabled = false;
            
            // Guardar URL para funciones de copia
            window[`streamUrl_${canal}`] = url;
        }
        
        function mostrarError(mensaje) {
            // Implementar para todos los canales activos
            document.querySelectorAll('.status.loading').forEach(status => {
                status.className = 'status error';
                status.textContent = '❌ ' + mensaje;
            });
            
            document.querySelectorAll('button:disabled').forEach(btn => {
                btn.disabled = false;
            });
        }
        
        function copiarURL(canal) {
            const url = window[`streamUrl_${canal}`];
            if (url) {
                navigator.clipboard.writeText(url).then(() => {
                    alert('✅ URL copiada para VLC!');
                }).catch(() => {
                    // Fallback
                    const textArea = document.createElement('textarea');
                    textArea.value = url;
                    document.body.appendChild(textArea);
                    textArea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textArea);
                    alert('✅ URL copiada para VLC!');
                });
            }
        }
        
        function abrirVLC(canal) {
            const url = window[`streamUrl_${canal}`];
            if (url) {
                // Intentar abrir con protocolo VLC
                window.location.href = `vlc://${url}`;
            }
        }
    </script>
</body>
</html>
    """
    
    return render_template_string(html_template, canales=canales)

@app.route("/scrape/<canal>")
def scrape_fallback(canal):
    """Fallback: hacer scraping desde el servidor si el cliente no puede"""
    import scraper
    
    print(f"[🔄] Fallback scraping para {canal}")
    
    try:
        url = scraper.obtener_stream_url(canal, timeout=30)
        if url:
            return {"success": True, "url": url, "method": "server_fallback"}
        else:
            return {"success": False, "error": "No se pudo obtener stream"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route("/stream/<canal>")
def direct_stream(canal):
    """Endpoint directo para obtener stream (para compatibilidad)"""
    import scraper
    
    print(f"[📡] Stream directo solicitado para {canal}")
    url = scraper.obtener_stream_url(canal)
    
    if url:
        return Response(url, mimetype="text/plain")
    else:
        return "Stream no disponible", 404

@app.route("/playlist.m3u")
def playlist():
    """Genera playlist básico"""
    base_url = request.url_root.rstrip("/")
    canales = leer_canales()
    
    m3u = "#EXTM3U\n"
    for canal in canales:
        nombre = canal.replace("-", " ").upper()
        m3u += f'#EXTINF:-1 tvg-name="{nombre}" group-title="la14hd", {nombre}\n'
        m3u += f"{base_url}/stream/{canal}\n"
    
    return Response(m3u, mimetype="application/x-mpegurl")

@app.route("/health")
def health():
    """Health check"""
    return {"status": "ok", "canales": len(leer_canales())}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
