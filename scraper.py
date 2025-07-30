# scraper.py
from playwright.sync_api import sync_playwright
import time

def obtener_stream_url(canal):
    url = f"https://la14hd.com/vivo/canales.php?stream={canal}"
    captured_urls = []

    def on_request(req):
        req_url = req.url.lower()
        # Filtrar por .m3u8 y dominios relevantes
        if ".m3u8" in req_url and ("fubohd.com" in req_url or "hls" in req_url):
            print(f"[🔍 CAPTURADO] {req.url}")
            captured_urls.append(req.url)

    with sync_playwright() as p:
        browser = None
        try:
            print(f"[🌐] Iniciando navegador para {canal}...")
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled"
                ]
            )

            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                locale="es-ES",
                timezone_id="America/Bogota",
                extra_http_headers={
                    "Referer": "https://la14hd.com/",
                    "Origin": "https://la14hd.com"
                }
            )

            # Anti-detección de automatización
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es'] });
            """)

            page = context.new_page()
            page.on("request", on_request)

            print(f"[🚀] Cargando: {url}")
            start_time = time.time()
            page.goto(url, timeout=30000)

            # Espera inicial breve para que cargue el contenido
            print("[⏳] Esperando 6 segundos a que se genere el stream...")
            page.wait_for_timeout(6000)  # Reducido: suficiente si no hay iframe

            # Opcional: hacer clic en body por si acaso (aunque no sea necesario)
            try:
                page.click("body", force=True, timeout=3000)
                print("[🖱️] Clic en página (seguridad)")
            except:
                pass  # No es crítico

            # Esperar un poco más para capturar el .m3u8 si llega tarde
            remaining = 8000 - (time.time() - start_time) * 1000
            if remaining > 0:
                page.wait_for_timeout(int(remaining))

            browser.close()

            # Devolver la primera URL .m3u8 capturada
            return captured_urls[0] if captured_urls else None

        except Exception as e:
            print(f"[💥] Error en {canal}: {e}")
            if browser:
                try:
                    browser.close()
                except:
                    pass
            return None
