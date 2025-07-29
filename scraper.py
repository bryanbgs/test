# scraper.py
from playwright.sync_api import sync_playwright
import time

# Dominios conocidos de streams
STREAM_KEYWORDS = ["fubohd.com", "m3u8", "hls"]

def obtener_stream_url(canal):
    """
    Va directamente a la URL del canal y captura el .m3u8
    """
    url = f"https://la14hd.com/vivo/canales.php?stream={canal}"
    captured_urls = []

    def on_request(req):
        req_url = req.url.lower()
        if any(kw in req_url for kw in ["fubohd.com", "m3u8"]) and ".m3u8" in req_url:
            print(f"[✔️] Capturado: {req.url}")
            captured_urls.append(req.url)

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1920,1080"
                ]
            )

            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                referer="https://la14hd.com/",
                locale="es-ES",
                timezone_id="America/Bogota",
            )

            # Anti-detección
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es'] });
                Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            """)

            page = context.new_page()
            page.on("request", on_request)

            print(f"[🌐] Cargando: {url}")
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=20000)

            # Hacer clic en cualquier parte del reproductor para "reproducir"
            try:
                print("[🖱️] Haciendo clic para reproducir...")
                # Busca un iframe o el contenedor del video
                iframe = page.frame_locator("iframe").first
                if iframe.is_visible():
                    iframe.locator("body").click(timeout=5000)
                else:
                    # Si no hay iframe, haz clic en el body
                    page.locator("body").click(timeout=5000)
                print("[✅] Clic realizado")
            except Exception as e:
                print(f"[⚠️] Error al hacer clic: {e}")

            # Esperar a que se cargue el stream
            print("[⏳] Esperando 10 segundos a que se genere el stream...")
            page.wait_for_timeout(10000)

            # Espera adicional si el stream es lento
            print("[🔍] Buscando streams adicionales...")
            page.wait_for_timeout(5000)

            browser.close()

            return captured_urls[0] if captured_urls else None

        except Exception as e:
            print(f"[❌] Error obteniendo stream para {canal}: {e}")
            if browser:
                browser.close()
            return None
