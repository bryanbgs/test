# lista.py
from flask import Flask, Response, redirect, request
import scraper
import time
import os
import threading
from datetime import datetime

app = Flask(__name__)

# Almacenamiento en memoria
ULTIMA_ACTUALIZACION = 0
STREAMS = {}  # { "foxsports": "https://...fubohd.com/...m3u8?token=..." }
ACTUALIZANDO = False  # Flag para evitar múltiples actualizaciones simultáneas
ERRORES_CANAL = {}  # Contador de errores por canal
MAX_ERRORES_POR_CANAL = 3  # Máximo de errores antes de pausar un canal

CACHE_SECONDS = 20 * 60  # 20 minutos (más tiempo para reducir carga)
TIMEOUT_ACTUALIZACION = 45  # Timeout más corto para Render

def leer_canales():
    """Lee los canales desde canales.txt"""
    try:
        with open("canales.txt", "r", encoding="utf-8") as f:
            canales = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            print(f"[📋] Canales cargados: {canales}")
            return canales
    except Exception as e:
        print(f"[❌] Error leyendo canales.txt: {e}")
        return ["foxsports"]  # fallback con un solo canal

def actualizar_canal_individual(canal):
    """Actualiza un solo canal con timeout y manejo de errores"""
    try:
        print(f"[📡] Procesando canal: {canal}")
        
        # Verificar si el canal ha fallado demasiadas veces
        if ERRORES_CANAL.get(canal, 0) >= MAX_ERRORES_POR_CANAL:
            print(f"[⏸️] Canal {canal} pausado por exceso de errores")
            return None
            
        # Usar timeout para evitar que se cuelgue
        start_time = time.time()
        url_real = scraper.obtener_stream_url(canal, timeout=TIMEOUT_ACTUALIZACION)
        elapsed = time.time() - start_time
        
        if url_real:
            print(f"[✅] Canal {canal} actualizado en {elapsed:.1f}s")
            # Resetear contador de errores si fue exitoso
            ERRORES_CANAL[canal] = 0
            return url_real
        else:
            print(f"[⚠️] No se obtuvo URL para {canal}")
            ERRORES_CANAL[canal] = ERRORES_CANAL.get(canal, 0) + 1
            return None
            
    except Exception as e:
        print(f"[💥] Error procesando {canal}: {e}")
        ERRORES_CANAL[canal] = ERRORES_CANAL.get(canal, 0) + 1
        return None

def actualizar_streams():
    """Actualiza streams con control mejorado"""
    global ULTIMA_ACTUALIZACION, STREAMS, ACTUALIZANDO
    
    ahora = time.time()
    
    # Verificar si ya está actualizando o si no ha pasado suficiente tiempo
    if ACTUALIZANDO:
        print("[⏳] Actualización ya en progreso, saltando...")
        return
        
    if ahora - ULTIMA_ACTUALIZACION < CACHE_SECONDS:
        print(f"[💾] Usando cache (válido por {int((CACHE_SECONDS - (ahora - ULTIMA_ACTUALIZACION))/60)} min más)")
        return

    ACTUALIZANDO = True
    
    try:
        print(f"[🔄] Iniciando actualización de streams... [{datetime.now().strftime('%H:%M:%S')}]")
        canales = leer_canales()
        
        # Limitar a máximo 3 canales para Render
        if len(canales) > 3:
            print(f"[⚠️] Demasiados canales ({len(canales)}), limitando a 3 para Render")
            canales = canales[:3]
        
        nuevos_streams = {}
        canales_exitosos = 0
        
        for i, canal in enumerate(canales, 1):
            print(f"[{i}/{len(canales)}] Procesando: {canal}")
            
            url_real = actualizar_canal_individual(canal)
            
            if url_real:
                nuevos_streams[canal] = url_real
                canales_exitosos += 1
            else:
                # Mantener caché anterior si existe y no ha expirado demasiado
                if canal in STREAMS:
                    print(f"[🔁] Manteniendo caché para {canal}")
                    nuevos_streams[canal] = STREAMS[canal]
                else:
                    print(f"[❌] Sin stream disponible para {canal}")
            
            # Pausa más larga entre canales para Render
            if i < len(canales):
                time.sleep(5)  # Aumentado de 2 a 5 segundos

        # Actualizar streams solo si se obtuvo al menos uno exitoso
        if canales_exitosos > 0 or len(nuevos_streams) > 0:
            STREAMS.update(nuevos_streams)
            ULTIMA_ACTUALIZACION = ahora
            print(f"[✅] Actualización completada: {canales_exitosos} nuevos, {len(STREAMS)} total")
        else:
            print(f"[⚠️] No se actualizó nada, manteniendo cache anterior")
            
            print(f"[⏰] Próxima actualización en 20 minutos")
        
    except Exception as e:
        print(f"[💥] Error general en actualización: {e}")
    finally:
        ACTUALIZANDO = False

def actualizar_streams_async():
    """Actualiza streams en un hilo separado para no bloquear las requests"""
    thread = threading.Thread(target=actualizar_streams)
    thread.daemon = True
    thread.start()

@app.route("/stream/<canal>")
def proxy_stream(canal):
    """Redirige a la URL real del stream (oculta el token)"""
    # Actualizar en background si es necesario
    if time.time() - ULTIMA_ACTUALIZACION > CACHE_SECONDS and not ACTUALIZANDO:
        actualizar_streams_async()
    
    url_real = STREAMS.get(canal)
    if url_real:
        print(f"[🎯] Redirigiendo {canal} a stream")
        return redirect(url_real)
    else:
        print(f"[❌] Stream no disponible para {canal}")
        return f"Stream '{canal}' no disponible. Canales disponibles: {list(STREAMS.keys())}", 404

@app.route("/playlist.m3u")
def playlist():
    """Genera una lista IPTV con URLs limpias"""
    # Actualizar en background si es necesario
    if time.time() - ULTIMA_ACTUALIZACION > CACHE_SECONDS and not ACTUALIZANDO:
        actualizar_streams_async()
        
    base_url = request.url_root.rstrip("/")
    m3u = "#EXTM3U x-tvg-url=\"https://la14hd.com\"\n"
    
    for canal, url in STREAMS.items():
        nombre = canal.replace("-", " ").upper()
        m3u += f'#EXTINF:-1 tvg-name="{nombre}" group-title="la14hd", {nombre}\n'
        m3u += f"{base_url}/stream/{canal}\n"
        
    print(f"[📄] Generando playlist con {len(STREAMS)} canales")
    return Response(m3u, mimetype="application/x-mpegurl")

@app.route("/")
def index():
    """Página de prueba mejorada"""
    # Inicializar si es la primera vez
    if not STREAMS and not ACTUALIZANDO:
        actualizar_streams_async()
    
    html = f"""
    <h1>la14hd IPTV Playlist</h1>
    <p><strong>Estado:</strong> {'🔄 Actualizando...' if ACTUALIZANDO else '✅ Activo'}</p>
    <p><strong>Última actualización:</strong> {datetime.fromtimestamp(ULTIMA_ACTUALIZACION).strftime('%H:%M:%S') if ULTIMA_ACTUALIZACION else 'Nunca'}</p>
    <p><strong>Canales disponibles:</strong> {len(STREAMS)}</p>
    <ul>
    """
    
    for canal in STREAMS:
        errores = ERRORES_CANAL.get(canal, 0)
        estado = "⏸️ Pausado" if errores >= MAX_ERRORES_POR_CANAL else f"✅ Activo ({errores} errores)"
        html += f'<li><a href="/stream/{canal}" target="_blank">{canal.upper()}</a> - {estado}</li>'
    
    html += f"""
    </ul>
    <p><a href='/playlist.m3u'>📁 Descargar playlist.m3u</a></p>
    <p><a href='/'>🔄 Refrescar página</a></p>
    """
    return html

@app.route("/force-update")
def force_update():
    """Fuerza una actualización manual"""
    global ULTIMA_ACTUALIZACION
    if ACTUALIZANDO:
        return {"status": "Ya se está actualizando", "actualizando": True}
    
    # Resetear el tiempo para forzar actualización
    ULTIMA_ACTUALIZACION = 0
    actualizar_streams_async()
    return {"status": "Actualización iniciada", "actualizando": True}

@app.route("/debug")
def debug():
    """Página de debug para ver el estado interno"""
    return {
        "streams": list(STREAMS.keys()),
        "ultima_actualizacion": ULTIMA_ACTUALIZACION,
        "actualizando": ACTUALIZANDO,
        "errores_canal": ERRORES_CANAL,
        "cache_valido": time.time() - ULTIMA_ACTUALIZACION < CACHE_SECONDS
    }

@app.route("/health")
def health():
    """Endpoint de salud para Render"""
    return {"status": "ok", "streams": len(STREAMS), "actualizando": ACTUALIZANDO}

if __name__ == "__main__":
    print("[🚀] Iniciando aplicación...")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
