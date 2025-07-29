# scraper.py
from playwright.sync_api import sync_playwright
import re

# Dominios conocidos de streams
STREAM_KEYWORDS = ["fubohd.com", "dood.stream", "playerhd.site", "gamingtvlive.com", "m3u8"]

def es_canal_activo(elemento):
    """Verifica si el canal tiene estado 'Activo'"""
    hermanos = elemento.query_selector_all("xpath=preceding-sibling::*")
    for hermano in reversed(hermanos):
        texto = hermano.inner_text().strip()
        if texto == "Activo":
            return True
        if texto and texto != "Inactivo":
            break
    return False

def obtener_canales_activos():
    """Extrae los canales activos de la14hd.com"""
    canales = []
    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            page = browser.new_page()
            page.goto("https://la14hd.com", timeout=30000)
            page.wait_for_load_state("networkidle")

            # Buscar todos los enlaces con texto "Link"
            links = page.locator("text=Link").all()
            for link in links:
                if not link.is_visible():
                    continue
                parent = link.element_handle().owner_frame().frame_element()
                if not es_canal_activo(parent):
                    continue

                # Obtener el nombre del canal (el hermano anterior más cercano que sea texto)
                nombre = ""
                hermanos = link.query_selector_all("xpath=preceding-sibling::*")
                for hermano in reversed(hermanos):
                    txt = hermano.inner_text().strip()
                    if txt and txt not in ["Activo", "Inactivo", "Link"]:
                        nombre = txt
                        break

                href = link.get_attribute("href")
                if href and href.startswith("/en-vivo/"):
                    stream_key = re.search(r"/en-vivo/(.+?)/", href)
                    if stream_key:
                        stream_key = stream_key.group(1)
                        canales.append({
                            "nombre": nombre or stream_key.replace("-", " ").title(),
                            "stream_key": stream_key,
                            "href": href
                        })
            browser.close()
        except Exception as e:
            print(f"[❌] Error en scraping: {e}")
            if browser:
                browser.close()
    return canales

def obtener_stream_url(stream_key):
    """Dado un stream_key, captura la URL .m3u8 real"""
    url_canal = f"https://la14hd.com{stream_key}"
    captured_urls = []

    def on_request(req):
        req_url = req.url.lower()
        if any(kw in req_url for kw in ["fubohd.com", "m3u8"]) and ".m3u8" in req_url:
            captured_urls.append(req.url)

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
            """)
            page = context.new_page()
            page.on("request", on_request)
            page.goto(url_canal, timeout=30000)

            # Hacer clic en "Ver canal"
            try:
                page.locator("text=Ver canal").first.click(timeout=5000)
            except:
                pass

            page.wait_for_timeout(10000)  # Esperar carga del stream
            browser.close()

            return captured_urls[0] if captured_urls else None
        except Exception as e:
            print(f"[❌] Error obteniendo stream: {e}")
            if browser:
                browser.close()
            return None
