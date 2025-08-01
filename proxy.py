# proxy.py
import requests
import m3u8
import re
from urllib.parse import urljoin, urlparse
from flask import Response, request
import scraper

# Cache simple para evitar recrear el m3u8 cada vez
ACTIVE_STREAMS = {}

def reescribir_m3u8(m3u8_content, base_url, proxy_prefix):
    """
    Reescribe el contenido del .m3u8 para que todos los segmentos pasen por el proxy.
    """
    playlist = m3u8.loads(m3u8_content)

    for segment in playlist.segments:
        original_uri = segment.uri
        if not original_uri:
            continue

        # Construir URL absoluta del segmento
        segment_url = urljoin(base_url, original_uri)

        # Extraer solo el nombre del archivo (ej: 17192234.ts)
        filename = urlparse(segment_url).path.split("/")[-1]

        # Reemplazar por URL del proxy
        proxied_url = f"{proxy_prefix}/{filename}"
        segment.uri = proxied_url

    # También proxy para sub-playlists (si hay variantes)
    if playlist.playlists:
        for pl in playlist.playlists:
            original_uri = pl.uri
            if original_uri:
                sub_url = urljoin(base_url, original_uri)
                filename = urlparse(sub_url).path.split("/")[-1]
                pl.uri = f"{proxy_prefix}_sub/{filename}"

    return playlist.dumps()

def crear_proxy_inverso(canal):
    """
    Crea un generador que sirve el .m3u8 y los .ts a través del proxy.
    """
    # 1. Obtener el stream original desde la IP del servidor
    stream_url = scraper.obtener_stream_url_para_cliente(canal, "0.0.0.0", timeout=30)
    if not stream_url:
        return None

    # Dominio base del stream original
    parsed = urlparse(stream_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    playlist_path = parsed.path.rsplit("/", 1)[0]  # directorio del m3u8

    # Prefijo del proxy en tu app
    proxy_prefix = f"/proxy/{canal}"

    # 2. Descargar el .m3u8 original
    try:
        resp = requests.get(stream_url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://la14hd.com/"
        })
        resp.raise_for_status()
    except Exception as e:
        print(f"[❌] No se pudo descargar .m3u8: {e}")
        return None

    # 3. Reescribir el .m3u8 para que todo pase por el proxy
    contenido_reescrito = reescribir_m3u8(resp.text, base_url, proxy_prefix)

    # Guardar en caché temporal
    ACTIVE_STREAMS[canal] = {
        "base_url": base_url,
        "playlist_path": playlist_path,
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://la14hd.com/"
        }
    }

    return Response(
        contenido_reescrito,
        mimetype="application/vnd.apple.mpegurl",
        headers={"Content-Disposition": "inline; filename=stream.m3u8"}
    )

def manejar_segmento(canal, filename):
    """
    Sirve un segmento .ts a través del proxy.
    """
    if canal not in ACTIVE_STREAMS:
        return "Stream no activo", 404

    config = ACTIVE_STREAMS[canal]
    base_url = config["base_url"]
    playlist_path = config["playlist_path"]
    headers = config["headers"]

    # Reconstruir URL original del segmento
    segment_url = urljoin(f"{base_url}/{playlist_path}/", filename)

    try:
        resp = requests.get(segment_url, headers=headers, stream=True, timeout=10)
        if resp.status_code != 200:
            return "Segmento no disponible", 404

        return Response(
            resp.iter_content(chunk_size=1024),
            content_type=resp.headers.get("Content-Type", "video/MP2T"),
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        print(f"[❌] Error proxying {filename}: {e}")
        return "Error", 500