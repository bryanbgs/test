# scraper.py
from playwright.sync_api import sync_playwright
import time


def obtener_stream_url_para_cliente(canal, client_ip, timeout=30):
    """
    Genera stream URL como si el cliente se conectara desde su propia IP
    """
    print(f"[🔑] Generando token para {canal} desde IP cliente: {client_ip}")
    url = f"https://la14hd.com/vivo/canales.php?stream={canal}"
    captured_urls = []
    start_time = time.time()

    def on_request(req):
        req_url = req.url.lower()
        if ".m3u8" in req_url and ("fubohd.com" in req_url or "hls" in req_url):
            print(f"[🔍 CAPTURADO para {client_ip}] {req.url}")
            captured_urls.append(req.url)

    def check_timeout():
        return time.time() - start_time > timeout

    try:
        print(f"[🌐] Navegador para {canal} (IP cliente: {client_ip})...")
        if check_timeout():
            return None

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu",
                    "--disable-dev-shm-usage"
                ]
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                locale="es-ES",
                timezone_id="America/Bogota",
                extra_http_headers={
                    "Referer": "https://la14hd.com/",
                    "Origin": "https://la14hd.com",
                    "X-Forwarded-For": client_ip,
                    "X-Real-IP": client_ip,
                    "CF-Connecting-IP": client_ip
                }
            )
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es'] });
            """)
            page = context.new_page()
            page.on("request", on_request)

            print(f"[🚀] Cargando para IP {client_ip}: {url}")
            if check_timeout():
                browser.close()
                return None

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                print(f"[✅] Página cargada para {client_ip}")
            except Exception as e:
                print(f"[❌] Error cargando para {client_ip}: {e}")
                browser.close()
                return None

            print(f"[⏳] Procesando contenido para {client_ip}...")
            page.wait_for_timeout(3000)

            iframe_found = False
            try:
                page.wait_for_selector("iframe", timeout=15000)
                print(f"[🧩] Iframe detectado para {client_ip}")
                frame = page.frame_locator("iframe").first
                frame.locator("body").click(force=True, timeout=5000)
                print(f"[✅] Clic en iframe para {client_ip}")
                iframe_found = True
            except Exception as e:
                print(f"[⚠️] Sin iframe para {client_ip}: {e}")

            if not iframe_found:
                try:
                    page.click("body", force=True, timeout=5000)
                    print(f"[🖱️] Clic en body para {client_ip}")
                except Exception as e:
                    print(f"[⚠️] No se pudo hacer clic en body: {e}")

            print(f"[⏳] Esperando stream para {client_ip}...")
            wait_time = 12
            for i in range(wait_time):
                if captured_urls:
                    print(f"[🎯] Stream generado para {client_ip} en {i+1}s")
                    break
                if check_timeout():
                    break
                page.wait_for_timeout(1000)

            browser.close()

            if captured_urls:
                print(f"[✅] Token generado exitosamente para {client_ip}")
                return captured_urls[0]
            else:
                print(f"[❌] No se generó token para {client_ip}")
                return None

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[💥] Error para {client_ip}: {str(e)[:100]} (duración: {elapsed:.2f}s)")
        return None


def obtener_stream_url(canal, timeout=30):
    """
    Obtiene la URL del stream (versión sin IP específica, para caché)
    """
    return obtener_stream_url_para_cliente(canal, "127.0.0.1", timeout=timeout)
