from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import os
import threading
from winotify import Notification
from PIL import Image, ImageDraw, ImageFont
import pystray

THRESHOLD = 35
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_log.txt")
MAX_LOG_BYTES = 5 * 1024 * 1024

last_level = None
heartbeat_count = 0
tray_icon = None

def log(message):
    line = f"[{datetime.now():%d.%m.%Y %H:%M:%S}] {message}"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def maybe_rotate():
    try:
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > MAX_LOG_BYTES:
            os.replace(LOG_PATH, LOG_PATH.replace(".txt", "_old.txt"))
    except Exception:
        pass

def show_toast(level):
    try:
        Notification(
            app_id="Battery Alert Server",
            title="Батарея планшета разряжена",
            msg=f"Уровень заряда: {level}%",
            duration="short",
        ).show()
    except Exception:
        log(f"Тост не показался, но уровень: {level}")

# --- Иконка в трее ---

def build_icon_image(level):
    """Рисует значок: корпус батарейки + доля заряда + процент."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Цвет по уровню
    if level > 50:
        fill = (76, 175, 80, 255)      # зелёный
    elif level > 20:
        fill = (255, 193, 7, 255)      # жёлтый
    else:
        fill = (244, 67, 54, 255)      # красный
    # Корпус батарейки
    d.rounded_rectangle([8, 20, 50, 48], radius=6, outline=(120, 120, 120, 255), width=3)
    d.rectangle([50, 27, 56, 41], fill=(120, 120, 120, 255))  # контакт
    # Заряд внутри
    if level > 0:
        w = int(38 * min(level, 100) / 100)
        d.rounded_rectangle([11, 23, 11 + max(w, 4), 45], radius=4, fill=fill)
    # Процент
    try:
        font = ImageFont.truetype("arialbd.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
    text = str(level)
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((32 - tw / 2, 50 - th / 2 + 8), text, font=font, fill=(255, 255, 255, 255),
           stroke_width=2, stroke_fill=(0, 0, 0, 255))
    return img

def update_tray(level):
    global tray_icon
    try:
        if tray_icon is not None:
            tray_icon.icon = build_icon_image(level)
            tray_icon.title = f"Планшет: {level}%"
            tray_icon.update_menu()
    except Exception:
        pass

def on_exit(icon, item):
    icon.stop()
    os._exit(0)

def run_tray():
    global tray_icon
    menu = pystray.Menu(
        pystray.MenuItem(lambda item: f"Планшет: {last_level}%" if last_level else "Планшет: нет данных",
                         None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Выход", on_exit),
    )
    tray_icon = pystray.Icon("battery", build_icon_image(0), "Планшет: ожидание", menu)
    tray_icon.run()

# --- HTTP-сервер ---

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        global last_level, heartbeat_count
        length = int(self.headers.get('Content-Length', 0) or 0)
        body = self.rfile.read(length).decode('utf-8', errors='replace') if length else ''
        try:
            level = int(body.split('"level":')[1].strip().strip(' }'))
        except Exception:
            level = -1
        if self.path == '/battery' and level > 0:
            prev = last_level
            last_level = level
            heartbeat_count += 1
            if level != prev:
                maybe_rotate()
                log(f"Уровень изменился: {prev} -> {level}")
                update_tray(level)  # перекрашиваем иконку
            elif heartbeat_count % 10 == 0:
                update_tray(level)  # подстраховка: обновить даже без изменения
            if heartbeat_count % 10 == 0:
                maybe_rotate()
                log(f"Жив, опрос идёт, уровень: {level}")
            if level <= THRESHOLD and (prev is None or prev > THRESHOLD):
                maybe_rotate()
                log(f"Порог пройден ВНИЗ: {prev} -> {level}")
                show_toast(level)
            elif level > THRESHOLD and (prev is None or prev <= THRESHOLD):
                maybe_rotate()
                log(f"Заряд восстановился ВВЕРХ: {prev} -> {level}")
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')

    def log_message(self, *args):
        pass

# Сеть — в отдельном потоке, трей — в главном (так требует pystray)
log("Сервер запущен (с иконкой в трее), слушает 0.0.0.0:8080")
threading.Thread(target=lambda: ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever(),
                 daemon=True).start()
run_tray()
