# lista.py
from flask import Flask, Response, redirect, request
import scraper
import time
import os

app = Flask(__name__)

# Almacenamiento en memoria
ULTIMA_ACTUALIZACION = 0
STREAMS = {}
CACHE_SECONDS = 15 * 60  # 15 minutos
updating = False  # Para evitar múltiples actualizaciones simultáneas

def actualizar_streams():
    global ULTIMA_ACTUALIZACION, STREAMS, updating
    ahora = time.time()
    
    if ahora - ULTIMA_ACTUALIZACION < CACHE_SECONDS and STREAMS:
        return  # Usa caché

    if updating:
        return  # Evita múltiples actualizaciones simultáneas

    updating = True
    print("[🔄] Iniciando actualización de streams...")
    
    nuevos_streams = {}
    canales = leer_canales()

    for canal in canales:
        print(f"[📡] Procesando canal: {canal}")
        url_real = scraper.obtener_stream_url(canal)
        if url_real:
            nuevos_streams[canal] = url_real
            print(f"[✅] {canal.upper()}: {url_real}")
        else:
            if canal in STREAMS:
                print(f"[🔁] Usando caché para {canal}")
                nuevos_streams[canal] = STREAMS[canal]
            else:
                print(f"[❌] Sin stream para {canal}")

    STREAMS.update(nuevos_streams)
    ULTIMA_ACTUALIZACION = time.time()
    updating = False
    print(f"[⏰] Actualización completada. Próxima en 15 minutos")
