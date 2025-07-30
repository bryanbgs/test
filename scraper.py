# scraper.py
from playwright.sync_api import sync_playwright
import time
import signal
import sys

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Timeout alcanzado")

def obtener_stream_url(canal, timeout=60):
    """
    Obtiene la URL del stream con timeout y mejor manejo de errores
    """
    url = f"https://la14hd.com/vivo/canales.php?stream={canal}"
    captured_urls = []
    browser = None
    
    def on_request(req):
        req_url = req.url.lower()
        if ".m3u8" in req_url and ("fubohd.com" in req_url or "hls" in req_url):
            print(f"[🔍 CAPTURADO] {req.url}")
            captured_urls.append(req.url)

    # Configurar timeout con señal (solo funciona en Unix)
    if hasattr(signal, 'SIGALRM'):
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)

    try:
        print(f"[🌐] Iniciando navegador para {canal} (timeout: {timeout}s)...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-extensions",
                    "--disable-plugins",
                    "--disable-images",  # Deshabilitar imágenes para mayor velocidad
                    "--disable-javascript-harmony-shipping",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-features=TranslateUI,BlinkGenPropertyTrees"
                ]
            )

            context = browser.new_context(
                viewport={"width": 1280, "height": 720},  # Viewport más pequeño
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                locale="es-ES",
                timezone_id="America/Bogota",
                extra_http_headers={
                    "Referer": "https://la14hd.com/",
                    "Origin": "https://la14hd.com"
                }
            )

            # Anti-detección más completa
            context.add_init_script("""
                // Anti-detección básica
                Object.defineProperty(navigator, 'webdriver', { 
                    get: () => false 
                });
                
                // Simular Chrome real
                window.chrome = { 
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // Plugins fake
                Object.defineProperty(navigator, 'plugins', { 
                    get: () => [
                        {name: 'Chrome PDF Plugin'},
                        {name: 'Chrome PDF Viewer'},
                        {name: 'Native Client'}
                    ]
                });
                
                // Idiomas
                Object.defineProperty(navigator, 'languages', { 
                    get: () => ['es-ES', 'es', 'en-US', 'en'] 
                });
                
                // Permisos
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

            page = context.new_page()
            
            # Configurar timeouts más agresivos
            page.set_default_navigation_timeout(20000)  # 20 segundos máximo para navegación
            page.set_default_timeout(15000)  # 15 segundos máximo para acciones
            
            page.on("request", on_request)

            print(f"[🚀] Cargando: {url}")
            start_time = time.time()
            
            # Cargar página con timeout
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            print(f"[✅] Página cargada en {time.time() - start_time:.1f}s")

            # Esperar contenido inicial más corto
            print("[⏳] Esperando contenido inicial...")
            page.wait_for_timeout(3000)  # Reducido de 5000 a 3000

            # Manejo mejorado de iframes
            iframe_found = False
            try:
                # Verificar si hay iframes
                iframes = page.locator("iframe").count()
                print(f"[🧩] Se encontraron {iframes} iframe(s)")
                
                if iframes > 0:
                    # Intentar con el primer iframe que tenga contenido relevante
                    for i in range(min(iframes, 3)):  # Máximo 3 iframes
                        try:
                            frame = page.frame_locator("iframe").nth(i)
                            # Verificar si el iframe está listo
                            frame.locator("body").wait_for(state="visible", timeout=5000)
                            frame.locator("body").click(force=True, timeout=3000)
                            print(f"[✅] Clic realizado en iframe {i}")
                            iframe_found = True
                            break
                        except Exception as e:
                            print(f"[⚠️] Iframe {i} no disponible: {e}")
                            continue
                            
            except Exception as e:
                print(f"[⚠️] Error general con iframes: {e}")

            # Fallback si no se encontraron iframes o no funcionaron
            if not iframe_found:
                try:
                    print("[🖱️] Intentando clic en body principal...")
                    page.click("body", force=True, timeout=3000)
                    print("[✅] Clic en página principal exitoso")
                except Exception as e:
                    print(f"[⚠️] No se pudo hacer clic en body: {e}")

            # Esperar por el stream con timeout más corto
            max_wait = min(15, timeout - 10)  # Máximo 15 segundos o timeout-10
            print(f"[⏳] Esperando {max_wait}s para capturar stream...")
            
            wait_start = time.time()
            while time.time() - wait_start < max_wait:
                if captured_urls:
                    print(f"[🎯] Stream capturado en {time.time() - wait_start:.1f}s")
                    break
                page.wait_for_timeout(1000)  # Verificar cada segundo
            
            # Limpiar recursos
            browser.close()
            
            if captured_urls:
                print(f"[✅] Stream obtenido para {canal}: {captured_urls[0][:50]}...")
                return captured_urls[0]
            else:
                print(f"[❌] No se capturó ningún stream para {canal}")
                return None

    except TimeoutException:
        print(f"[⏰] Timeout alcanzado para {canal} ({timeout}s)")
        if browser:
            try:
                browser.close()
            except:
                pass
        return None
        
    except Exception as e:
        print(f"[💥] Error en {canal}: {str(e)[:100]}")
        if browser:
            try:
                browser.close()
            except:
                pass
        return None
        
    finally:
        # Limpiar timeout
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)

def test_canal(canal):
    """Función de prueba para un canal específico"""
    print(f"[🧪] Probando canal: {canal}")
    url = obtener_stream_url(canal, timeout=30)
    if url:
        print(f"[✅] Éxito: {url}")
    else:
        print(f"[❌] Falló: {canal}")
    return url

if __name__ == "__main__":
    # Prueba directa del scraper
    if len(sys.argv) > 1:
        canal = sys.argv[1]
        test_canal(canal)
    else:
        print("Uso: python scraper.py <nombre_canal>")
        print("Ejemplo: python scraper.py foxsports")
