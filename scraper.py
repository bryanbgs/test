# scraper.py
from playwright.sync_api import sync_playwright
import time

def obtener_stream_url(canal):
    url = f"https://la14hd.com/vivo/canales.php?stream={canal}"
    captured_urls = []

    def on_request(req):
        req_url = req.url.lower()
        if ".m3u8" in req_url and "fubohd.com" in req_url:
            print(f"[🔍 CAPTURADO] {req.url}")  # Log clave
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
                referer="https://la14hd.com/",
                locale="es-ES",
                timezone_id="America/Bogota",
            )

            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es'] });
            """)

            page = context.new_page()
            page.on("request", on_request)

            print(f"[🚀] Cargando: {url}")
            page.goto(url, timeout=30000)

            # Hacer clic en "Ver canal"
            try:
                print("[🖱️] Buscando botón 'Ver canal'...")
                btn = page.locator("text=Ver canal").first
                if btn.is_visible(timeout=5000):
                    btn.click()
                    print("[✅] Clic en 'Ver canal' realizado")
                else:
                    print("[⚠️] Botón 'Ver canal' no visible")
            except Exception as e:
                print(f"[❌] Error clic: {e}")

            # Hacer clic en el body (por si el reproductor requiere interacción)
            try:
                page.locator("body").click(timeout=5000)
                print("[🖱️] Clic en body realizado")
            except:
                pass

            # Esperar carga
            print("[⏳] Esperando 12 segundos a que se genere el stream...")
            page.wait_for_timeout(12000)

            browser.close()

            if captured_urls:
                print(f"[🎉] Stream encontrado para {canal}: {captured_urls[0]}")
                return captured_urls[0]
            else:
                print(f"[❌] No se encontró stream para {canal}")
                return None

        except Exception as e:
            print(f"[💥] Error grave en {canal}: {e}")
            if browser:
                browser.close()
            return None
