# ============ JARVIS v1 — ГОТОВ ДЛЯ GITHUB ============
import tkinter as tk
from tkinter import scrolledtext
import subprocess
import threading
import queue
import sys
import time
import os
import json
import re
import random
import string
import urllib.request
import urllib.parse
import zipfile
import socket
import webbrowser
from datetime import datetime, timedelta

import sounddevice as sd
from vosk import Model, KaldiRecognizer

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.05
    PYAW_AVAILABLE = True
except ImportError:
    PYAW_AVAILABLE = False

try:
    import pyperclip
    PYCLIP_AVAILABLE = True
except ImportError:
    PYCLIP_AVAILABLE = False

try:
    import pygetwindow as gw
    PYWIN_AVAILABLE = True
except ImportError:
    PYWIN_AVAILABLE = False

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

WMI_AVAILABLE = False
_wmi_module = None

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# ============ НАСТРОЙКИ ============
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def find_steam():
    """Ищет steam.exe в стандартных местах + через реестр."""
    candidates = [
        r"C:\Program Files (x86)\Steam\steam.exe",
        r"C:\Program Files\Steam\steam.exe",
        r"D:\Steam\steam.exe",
        r"E:\Steam\steam.exe",
        r"D:\Program Files (x86)\Steam\steam.exe",
        r"D:\Program Files\Steam\steam.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p

    # Поиск через реестр Windows
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
        winreg.CloseKey(key)
        steam_exe = os.path.join(steam_path, "steam.exe")
        if os.path.exists(steam_exe):
            return steam_exe
    except Exception:
        pass

    return None


STEAM_PATH = find_steam()

CSGO_APP_ID = "4465480"
WEATHER_CITY = "Moscow"
WAKE_WORDS = ["jarvis", "джарвис", "javis", "джервис", "jarvi", "жавис"]
NOTES_FILE = os.path.join(SCRIPT_DIR, "notes.txt")

TTS_RATE = 180
TTS_VOICE_KEYWORD = "irina"
_stop_speaking_flag = threading.Event()
_current_tts_engine = None

RECORDING = {
    "active": False, "thread": None,
    "stop_flag": threading.Event(),
    "output_path": None, "fps": 10.0,
}

MODEL_DIR_NAME = "vosk-model-small-ru-0.22"
VOSK_MODEL_PATH = os.path.join(SCRIPT_DIR, MODEL_DIR_NAME)
MODEL_URLS = [
    "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
    "https://github.com/kercre123/vosk-models/raw/main/vosk-model-small-ru-0.22.zip",
]
MODEL_ZIP = os.path.join(SCRIPT_DIR, "vosk-model-small-ru-0.22.zip")

SAMPLE_RATE = 16000
BLOCKSIZE = 1000
QUEUE_TIMEOUT = 0.02
RMS_THRESHOLD = 80
MIC_KEYWORDS = ["microphone", "микрофон", "mic", "usb"]

BG_COLOR = "#0C0C0C"
FG_COLOR = "#CCCCCC"
GREEN = "#0F0"
YELLOW = "#FFD700"
RED = "#FF3B3B"
CYAN = "#22D3EE"
GRAY = "#777"
MAGENTA = "#FF6BE6"

log_queue = queue.Queue()
is_listening = False
stop_flag = threading.Event()

_vosk_model = None
_vosk_model_lock = threading.Lock()

_last_open_time = {}
OPEN_COOLDOWN = 5
_last_action_time = 0


# ======================= ОТКРЫТИЕ ССЫЛОК =======================
def open_url(url):
    try:
        webbrowser.open_new_tab(url)
        return True
    except Exception:
        pass
    try:
        webbrowser.open(url, new=2)
        return True
    except Exception:
        pass
    try:
        os.startfile(url)
        return True
    except Exception:
        pass
    return False


def can_open(action_name):
    now = time.time()
    last = _last_open_time.get(action_name, 0)
    if now - last < OPEN_COOLDOWN:
        return False
    _last_open_time[action_name] = now
    return True


# ======================= СИСТЕМА =======================
def system_get_temperature():
    global _wmi_module, WMI_AVAILABLE
    if _wmi_module is None:
        try:
            import wmi as _wmi
            _wmi_module = _wmi
            WMI_AVAILABLE = True
        except Exception:
            _wmi_module = False
            WMI_AVAILABLE = False
            return "н/д"
    if not _wmi_module:
        return "н/д"
    try:
        w = _wmi_module.WMI(namespace="root\\wmi")
        temps = w.MSAcpi_ThermalZoneTemperature()
        for t in temps:
            celsius = (t.CurrentTemperature / 10.0) - 273.15
            return f"{celsius:.0f}°C"
    except Exception:
        pass
    return "н/д"


def system_report_voice(log_func=None):
    if not PSUTIL_AVAILABLE:
        speak("Хозяин, psutil не установлен.", log_func)
        return
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        parts = [f"Загрузка процессора {cpu} процентов"]
        temp = system_get_temperature()
        if temp != "н/д":
            parts.append(f"температура {temp}")
        parts.append(f"ОЗУ использовано {ram.percent} процентов")
        parts.append(f"на диске C свободно {disk.free / 1024**3:.0f} гигабайт")
        try:
            battery = psutil.sensors_battery()
            if battery:
                status = "заряжается" if battery.power_plugged else "от батареи"
                parts.append(f"батарея {battery.percent} процентов, {status}")
        except Exception:
            pass
        uptime = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
        hours = int(uptime.total_seconds() // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)
        parts.append(f"компьютер работает {hours} часов {minutes} минут")
        text = "Хозяин, доклад о системе. " + ". ".join(parts) + ". Всё в норме."
        speak(text, log_func)
    except Exception as e:
        if log_func:
            log_func(f"Ошибка системы: {e}", "error")


# ======================= БАЗА ЗНАНИЙ =======================
KNOWLEDGE_BASE = {
    "фотосинтез": "Фотосинтез — процесс, при котором растения используют солнечный свет, воду и углекислый газ для производства кислорода и глюкозы.",
    "гравитация": "Гравитация — сила притяжения между объектами с массой. Открыта Ньютоном.",
    "атом": "Атом — мельчайшая частица вещества.",
    "космос": "Космос — пространство за пределами атмосферы Земли.",
    "вселенная": "Вселенная — всё, что существует. Возраст 13.8 млрд лет.",
    "солнце": "Солнце — звезда в центре Солнечной системы.",
    "луна": "Луна — спутник Земли.",
    "марс": "Марс — четвёртая планета. Красная планета.",
    "чёрная дыра": "Чёрная дыра — область с огромной гравитацией.",
    "гагарин": "Юрий Гагарин — первый человек в космосе. 1961 год.",
    "пушкин": "Александр Пушкин — великий русский поэт. 1799-1837.",
    "толстой": "Лев Толстой — русский писатель. Война и мир.",
    "ленин": "Владимир Ленин — основатель СССР.",
    "сталин": "Иосиф Сталин — руководитель СССР 1924-1953.",
    "наполеон": "Наполеон Бонапарт — французский император.",
    "россия": "Россия — самая большая страна. Столица Москва.",
    "москва": "Москва — столица России. Основана 1147.",
    "компьютер": "Компьютер — машина для обработки информации.",
    "интернет": "Интернет — глобальная сеть.",
    "python": "Python — популярный язык программирования.",
    "искусственный интеллект": "ИИ — системы, способные учиться.",
    "нейросеть": "Нейросеть — модель, вдохновлённая мозгом.",
    "кошка": "Кошка — домашнее животное.",
    "собака": "Собака — друг человека.",
    "мозг": "Мозг — центральный орган нервной системы.",
    "сердце": "Сердце — мышечный орган, качает кровь.",
    "человек": "Человек — Homo sapiens.",
    "любовь": "Любовь — глубокое чувство привязанности.",
    "счастье": "Счастье — состояние радости.",
    "дружба": "Дружба — близкие отношения.",
    "время": "Время — форма существования материи.",
    "музыка": "Музыка — искусство звуков.",
    "кино": "Кино — искусство движущихся изображений.",
    "кс": "Контр-Страйк — командный шутер.",
    "кс го": "Counter-Strike: Global Offensive — старая версия CS 2012 года.",
    "донк": "Donk — профессиональный игрок CS, Team Spirit.",
    "симпл": "s1mple — легендарный игрок CS, NAVI.",
}

KNOWLEDGE_SYNONYMS = {
    "ии": "искусственный интеллект",
    "чёрная": "чёрная дыра",
    "питон": "python",
    "cs": "кс",
    "csgo": "кс го",
    "ксго": "кс го",
}

ABOUT_ME = (
    "Я Jarvis. Мой создатель — мальчик, которому пятнадцать лет. "
    "Я работаю офлайн, без интернета. Могу с тобой общаться, отвечать на вопросы, "
    "рассказывать о разных темах, помогать с играми, открывать приложения, "
    "управлять мышкой, вводить команды в консоль CS, делать скриншоты и записывать экран. "
    "Также я умею докладывать о состоянии системы."
)

DIALOGS = {
    "привет": "Привет, хозяин. Рад тебя слышать.",
    "доброе утро": "Доброе утро, хозяин.",
    "добрый день": "Добрый день, хозяин.",
    "добрый вечер": "Добрый вечер, хозяин.",
    "как дела": "Всё отлично, хозяин. Готов служить.",
    "как ты": "Работаю в штатном режиме.",
    "кто ты": "Я Jarvis, твой голосовой помощник.",
    "спасибо": "Всегда пожалуйста, хозяин.",
    "благодарю": "Рад стараться, хозяин.",
    "молодец": "Спасибо, хозяин. Стараюсь.",
    "ты лучший": "Спасибо, хозяин. Ты тоже лучший.",
    "я тебя люблю": "И я тебя, хозяин.",
    "помоги": "Конечно, что нужно?",
    "мне скучно": "Могу рассказать что-нибудь.",
    "пока": "До встречи, хозяин.",
    "до свидания": "До свидания, хозяин.",
    "спокойной ночи": "Спокойной ночи, хозяин.",
    "ты тут": "Да, я здесь.",
    "хватит": "Останавливаюсь.",
    "замолчи": "Молчу.",
}

STORIES = [
    "Хозяин, расскажу о чёрных дырах. Чёрная дыра — область пространства, где гравитация настолько сильна, что даже свет не может её покинуть. В 2019 году учёные впервые сфотографировали тень чёрной дыры в галактике M87.",
    "Хозяин, расскажу про Марс. Красная планета — четвёртая от Солнца. На Марсе — самая высокая гора в Солнечной системе, Олимп, 21 километр.",
    "Хозяин, расскажу о человеческом мозге. В нём 86 миллиардов нейронов. Мозг потребляет 20 процентов энергии тела, хотя весит всего полтора килограмма.",
    "Хозяин, расскажу о Древнем Египте. Египтяне построили пирамиды — гробницы фараонов. Пирамида Хеопса высотой 146 метров.",
    "Хозяин, расскажу о Второй мировой войне. Она началась в 1939 году и длилась шесть лет. Погибло около 70 миллионов человек.",
]


# ======================= ФУНКЦИОНАЛ =======================
def give_functional(log_func=None):
    log_func("=" * 70, "noise")
    log_func("ФУНКЦИОНАЛ JARVIS", "trigger")
    log_func("=" * 70, "noise")
    log_func("", "noise")
    log_func("ИГРЫ:", "info")
    log_func("   Джарвис задрот        - запуск CS:GO", "noise")
    log_func("   Джарвис роблокс       - запуск Roblox", "noise")
    log_func("   Джарвис лолик         - запуск Discord", "noise")
    log_func("   Джарвис телеграм      - запуск Telegram", "noise")
    log_func("", "noise")
    log_func("КОНСОЛЬ CS:GO:", "info")
    log_func("   Джарвис тренировка    - карта aim_botz", "noise")
    log_func("   Джарвис мираж         - карта de_mirage", "noise")
    log_func("   Джарвис даст 2        - карта de_dust2", "noise")
    log_func("   Джарвис добавь ботов  - добавить ботов", "noise")
    log_func("   Джарвис настрой прицел - настройка прицела", "noise")
    log_func("   Джарвис включи fps    - FPS-счётчик", "noise")
    log_func("", "noise")
    log_func("МЫШЬ:", "info")
    log_func("   Джарвис мышка вверх/вниз/влево/вправо", "noise")
    log_func("   Джарвис клик / правый клик", "noise")
    log_func("", "noise")
    log_func("СИСТЕМА:", "info")
    log_func("   Джарвис система       - доклад о системе", "noise")
    log_func("   Джарвис скриншот      - сохранить скриншот", "noise")
    log_func("   Джарвис запись        - запись экрана", "noise")
    log_func("   Джарвис громче / тише / выключи звук", "noise")
    log_func("", "noise")
    log_func("ИНФОРМАЦИЯ:", "info")
    log_func("   Джарвис информация    - голосом расскажет", "noise")
    log_func("   Джарвис расскажи о себе", "noise")
    log_func("   Джарвис какие темы ты знаешь", "noise")
    log_func("   Джарвис что такое X", "noise")
    log_func("   Джарвис время / день / погода", "noise")
    log_func("", "noise")
    log_func("ПОИСК:", "info")
    log_func("   Джарвис найти X       - поиск в Google", "noise")
    log_func("", "noise")
    log_func("РАЗВЛЕЧЕНИЯ:", "info")
    log_func("   Джарвис шутка / факт / цитата / монетка", "noise")
    log_func("   Джарвис случайное число / пароль 16", "noise")
    log_func("", "noise")
    log_func("МАТЕМАТИКА:", "info")
    log_func("   Джарвис два плюс два", "noise")
    log_func("", "noise")
    log_func("ПРОЧЕЕ:", "info")
    log_func("   Джарвис калькулятор / блокнот / проводник", "noise")
    log_func("   Джарвис заблокируй / перезагрузи / выключи", "noise")
    log_func("=" * 70, "noise")


def give_info(log_func=None):
    text = (
        "Хозяин, вот всё что я умею. "
        "Если хочешь список команд текстом - скажи джарвис функционал. "
        "Я умею: открывать приложения и сайты, управлять консолью CS, "
        "управлять мышкой, докладывать о системе, отвечать на вопросы, "
        "рассказывать истории, считать математику, развлекать шутками, "
        "искать в интернете, делать скриншоты, записывать экран, "
        "показывать время, дату и погоду. Вот и всё, хозяин."
    )
    speak(text, log_func)


# ======================= TTS =======================
def _speak_sync(text):
    global _current_tts_engine, TTS_RATE, TTS_VOICE_KEYWORD
    if not TTS_AVAILABLE:
        return False
    _stop_speaking_flag.clear()
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", TTS_RATE)
        engine.setProperty("volume", 1.0)
        chosen = None
        try:
            voices = engine.getProperty("voices")
            if TTS_VOICE_KEYWORD:
                for v in voices:
                    v_name = v.name.lower()
                    v_id = v.id.lower()
                    if TTS_VOICE_KEYWORD.lower() in v_name or TTS_VOICE_KEYWORD.lower() in v_id:
                        chosen = v.id
                        break
            if not chosen:
                for v in voices:
                    v_name = v.name.lower()
                    if "irina" in v_name or "ирина" in v_name:
                        chosen = v.id
                        break
            if chosen:
                engine.setProperty("voice", chosen)
        except Exception:
            pass
        _current_tts_engine = engine
        engine.say(text)
        engine.runAndWait()
        if _stop_speaking_flag.is_set():
            try:
                engine.stop()
            except Exception:
                pass
        _current_tts_engine = None
        try:
            engine.stop()
        except Exception:
            pass
        del engine
        return True
    except Exception as e:
        print(f"[TTS] Ошибка: {e}")
        _current_tts_engine = None
        return False


def stop_speaking(log_func=None):
    _stop_speaking_flag.set()
    if _current_tts_engine:
        try:
            _current_tts_engine.stop()
        except Exception:
            pass
    if log_func:
        log_func("Стоп!", "error")


def speak(text, log_func=None):
    if log_func:
        log_func(f'Jarvis: "{text}"', "speak")
    if not TTS_AVAILABLE:
        return
    threading.Thread(target=_speak_sync, args=(text,), daemon=True).start()


def list_installed_voices():
    if not TTS_AVAILABLE:
        return []
    try:
        engine = pyttsx3.init()
        return [{"id": v.id, "name": v.name} for v in engine.getProperty("voices")]
    except Exception:
        return []


# ======================= МИКРОФОН =======================
def pick_best_microphone(log_func):
    try:
        devices = sd.query_devices()
    except Exception as e:
        log_func(f"Ошибка списка устройств: {e}", "error")
        return None
    input_devices = []
    for idx, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0:
            input_devices.append((idx, dev["name"]))
    if not input_devices:
        return None
    for idx, name in input_devices:
        for kw in MIC_KEYWORDS:
            if kw in name.lower():
                return idx
    return input_devices[0][0]


# ======================= МЫШЬ =======================
def move_mouse(direction, log_func=None, pixels=200, duration=0.4):
    if not PYAW_AVAILABLE:
        return
    screen_w, screen_h = pyautogui.size()
    x, y = pyautogui.position()
    dx, dy = 0, 0
    d = direction.lower()

    if "вверх" in d: dy = -pixels
    elif "вниз" in d: dy = pixels
    elif "влево" in d: dx = -pixels
    elif "вправо" in d: dx = pixels
    else:
        speak("Куда двигать мышку?", log_func)
        return

    new_x = max(0, min(screen_w - 1, x + dx))
    new_y = max(0, min(screen_h - 1, y + dy))

    try:
        pyautogui.moveTo(new_x, new_y, duration=duration)
        log_func(f"Мышь -> {direction} ({new_x}, {new_y})", "trigger")
    except Exception as e:
        log_func(f"Ошибка мыши: {e}", "error")


def mouse_click(click_type="left", log_func=None):
    if not PYAW_AVAILABLE:
        return
    try:
        if click_type == "left":
            pyautogui.click()
            log_func("Левый клик", "trigger")
        elif click_type == "right":
            pyautogui.rightClick()
            log_func("Правый клик", "trigger")
    except Exception as e:
        log_func(f"Ошибка клика: {e}", "error")


def scroll_mouse(direction="down", amount=5, log_func=None):
    if not PYAW_AVAILABLE:
        return
    try:
        if "вниз" in direction.lower():
            pyautogui.scroll(-amount)
            log_func("Прокрутка вниз", "trigger")
        else:
            pyautogui.scroll(amount)
            log_func("Прокрутка вверх", "trigger")
    except Exception as e:
        log_func(f"Ошибка прокрутки: {e}", "error")


# ======================= CS:GO =======================
def find_cs_window():
    if not PYWIN_AVAILABLE:
        return None
    try:
        for w in gw.getAllWindows():
            title = w.title.lower()
            if any(x in title for x in ["counter-strike", "cs2", "csgo", "counter strike"]):
                return w
    except Exception:
        pass
    return None


def cs_console_command(command, log_func=None):
    if not PYAW_AVAILABLE or not PYWIN_AVAILABLE:
        speak("pyautogui или pygetwindow не установлены", log_func)
        return False

    cs_window = find_cs_window()
    if not cs_window:
        speak("CS не запущена, хозяин.", log_func)
        log_func("Окно CS не найдено", "error")
        return False

    try:
        if cs_window.isMinimized:
            cs_window.restore()
        cs_window.activate()
        time.sleep(1.0)
        pyautogui.press("`")
        time.sleep(0.6)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("delete")
        time.sleep(0.2)
        if PYCLIP_AVAILABLE:
            pyperclip.copy(command)
            time.sleep(0.2)
            pyautogui.hotkey("ctrl", "v")
        else:
            pyautogui.typewrite(command, interval=0.02)
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(0.4)
        pyautogui.press("`")
        log_func(f"CS консоль: {command}", "trigger")
        return True
    except Exception as e:
        log_func(f"Ошибка ввода в CS: {e}", "error")
        return False


def cs_map_command(map_name, log_func=None, voice_name=None):
    if cs_console_command(f"map {map_name}", log_func):
        name = voice_name if voice_name else map_name
        speak(f"Открываю {name}", log_func)
        return True
    return False


def cs_add_bots(log_func=None):
    if cs_console_command("bot_add_t; bot_add_ct; bot_add_t; bot_add_ct", log_func):
        speak("Добавила ботов", log_func)


def cs_kick_bots(log_func=None):
    if cs_console_command("bot_kick", log_func):
        speak("Убрала ботов", log_func)


def cs_setup_crosshair(log_func=None):
    cmd = "cl_crosshairstyle 4; cl_crosshairsize 2; cl_crosshairgap -1; cl_crosshairthickness 0; cl_crosshaircolor 1"
    if cs_console_command(cmd, log_func):
        speak("Настроила прицел", log_func)


def cs_show_fps(log_func=None):
    if cs_console_command("cl_showfps 1", log_func):
        speak("FPS-счётчик включён", log_func)


# ======================= ЗАГРУЗКА МОДЕЛИ =======================
def load_vosk_model(log_func=None):
    global _vosk_model
    if _vosk_model is not None:
        return _vosk_model
    with _vosk_model_lock:
        if _vosk_model is not None:
            return _vosk_model
        if not os.path.exists(VOSK_MODEL_PATH):
            if log_func:
                log_func("Модель не найдена, скачиваю...", "info")
            if not download_model(log_func):
                return None
        if log_func:
            log_func("Загружаю модель Vosk в память...", "info")
        try:
            _vosk_model = Model(VOSK_MODEL_PATH)
            if log_func:
                log_func("Модель загружена и готова к работе!", "trigger")
            return _vosk_model
        except Exception as e:
            if log_func:
                log_func(f"Ошибка загрузки модели: {e}", "error")
            return None


def download_model(log_func):
    if os.path.exists(VOSK_MODEL_PATH):
        return True
    if os.path.exists(MODEL_ZIP):
        log_func("Найден архив", "info")
    else:
        log_func("Скачиваю модель Vosk...", "info")
        socket.setdefaulttimeout(30)
        success = False
        for i, url in enumerate(MODEL_URLS, 1):
            try:
                urllib.request.urlretrieve(url, MODEL_ZIP)
                success = True
                break
            except Exception as e:
                log_func(f"   Не вышло: {e}", "error")
        if not success:
            return False
    try:
        with zipfile.ZipFile(MODEL_ZIP, "r") as z:
            z.extractall(SCRIPT_DIR)
    except Exception as e:
        log_func(f"Ошибка распаковки: {e}", "error")
        return False
    try:
        os.remove(MODEL_ZIP)
    except Exception:
        pass
    return os.path.exists(VOSK_MODEL_PATH)


# ======================= ПОГОДА =======================
def get_weather_text(city):
    if not REQUESTS_AVAILABLE:
        return None
    try:
        url = f"https://wttr.in/{city}?format=j1&lang=ru"
        r = requests.get(url, timeout=6)
        data = r.json()
        c = data["current_condition"][0]
        temp = c["temp_C"]
        feels = c["FeelsLikeC"]
        desc_list = c.get("lang_ru", [])
        desc = desc_list[0].get("value", "") if desc_list else c["weatherDesc"][0]["value"]
        return f"Хозяин, сейчас в городе {city} {temp} градусов, ощущается как {feels}. {desc}."
    except Exception:
        return None


def open_weather(log_func=None):
    if not can_open("weather"):
        return
    open_url(f"https://yandex.ru/pogoda/{WEATHER_CITY}")
    text = get_weather_text(WEATHER_CITY)
    if text:
        speak(text, log_func)


# ======================= ACTIONS =======================
ACTIONS = [
    ("cs_crosshair",    ["настрой прицел", "поставь прицел", "настроить прицел"]),
    ("cs_map_aim_botz", ["тренировка", "тренировку", "тренировке", "тренировки", "тренировк",
                          "тренеровка", "тренеровку", "разминка", "разминку",
                          "aim botz", "аим бот", "aimbotz", "aim bot"]),
    ("cs_map_aim_map",  ["аим мап", "aim map", "аим мапа"]),
    ("cs_map_dust2",    ["запусти даст 2", "запусти даст2", "dust 2", "даст 2", "дастик"]),
    ("cs_map_mirage",   ["запусти мираж", "mirage", "мираж"]),
    ("cs_map_inferno",  ["запусти инферно", "inferno", "инферно"]),
    ("cs_map_nuke",     ["запусти нук", "nuke", "нук"]),
    ("cs_map_overpass", ["запусти оверпасс", "overpass", "оверпасс"]),
    ("cs_add_bots",     ["добавь ботов", "добавить ботов", "подкинь ботов"]),
    ("cs_kick_bots",    ["убери ботов", "убрать ботов", "удали ботов"]),
    ("cs_fps_on",       ["включи fps", "включи фпс", "покажи fps"]),
    ("mouse_move",      ["мышка", "мышь", "мишка", "курсор"]),
    ("mouse_right",     ["правый клик", "правый щелчок"]),
    ("mouse_click",     ["клик", "кликни", "щёлкни", "щелкни"]),
    ("mouse_scroll_down", ["прокрути вниз", "прокрутка вниз", "скролл вниз"]),
    ("mouse_scroll_up",   ["прокрути вверх", "прокрутка вверх", "скролл вверх"]),
    ("functional",      ["функционал", "функции", "все функции", "список функций"]),
    ("info",            ["информация", "инфо", "что ты умеешь", "команды", "список команд"]),
    ("system",          ["система", "состояние системы", "доклад системы"]),
    ("story",           ["расскажи о чём-нибудь", "расскажи что-нибудь", "расскажи историю", "удиви меня"]),
    ("about_me",        ["расскажи о себе", "расскажи про себя", "что ты такое"]),
    ("topics",          ["какие темы", "список тем", "все темы"]),
    ("question",        ["что такое", "кто такой", "кто такая", "расскажи о", "расскажи про", "объясни", "что значит"]),
    ("voice_irina",     ["голос ирина", "женский голос"]),
    ("voice_pavel",     ["голос павел", "мужской голос"]),
    ("voice_list",      ["список голосов", "какие голоса"]),
    ("faster",          ["говори быстрее"]),
    ("slower",          ["говори медленнее"]),
    ("stop_all",        ["стоп", "остановись", "замолчи", "хватит"]),
    ("record_start",    ["запись", "запись экрана", "начни запись"]),
    ("record_stop",     ["стоп запись", "останови запись"]),
    ("lock_pc",         ["заблокируй компьютер", "блокировка"]),
    ("reboot_pc",       ["перезагрузи компьютер", "ребут"]),
    ("shutdown",        ["выключи компьютер", "выключи пк"]),
    ("task_manager",    ["диспетчер задач"]),
    ("settings_win",    ["настройки windows"]),
    ("note_add",        ["запиши заметку", "добавь заметку", "запомни"]),
    ("note_show",       ["покажи заметки"]),
    ("note_clear",      ["очисти заметки"]),
    ("media_pause",     ["пауза"]),
    ("media_play",      ["продолжи"]),
    ("media_next",      ["следующий трек"]),
    ("media_prev",      ["предыдущий трек"]),
    ("volume_up",       ["громче", "прибавь звук"]),
    ("volume_down",     ["тише", "убавь звук"]),
    ("mute",            ["выключи звук"]),
    ("minimize_all",    ["сверни всё", "покажи рабочий стол"]),
    ("screenshot",      ["скриншот", "снимок экрана"]),
    ("calc",            ["калькулятор"]),
    ("notepad",         ["блокнот"]),
    ("explorer",        ["проводник", "мой компьютер"]),
    ("find",            ["найти", "найди", "поискать", "поищи", "искать"]),
    ("youtube",         ["ютуб", "ютюб", "ютьюб", "youtube"]),
    ("vk_open",         ["вк", "вконтакте", "мессенджер"]),
    ("discord",         ["лолик", "лоли", "дискорд", "discord"]),
    ("telegram",        ["телеграм", "telegram", "тг"]),
    ("roblox",          ["роблокс", "роблок", "roblox"]),
    ("csgo",            ["задрот", "кс го", "ксго", "csgo"]),
    ("music",           ["музыка", "включи музыку"]),
    ("movie",           ["кино", "фильм", "кинопоиск"]),
    ("joke",            ["шутка", "анекдот", "пошути"]),
    ("fact",            ["факт", "расскажи факт"]),
    ("quote",           ["цитата", "мотивация"]),
    ("coin",            ["монетка", "подбрось"]),
    ("random",          ["случайное число", "рандом"]),
    ("password",        ["пароль", "сгенерируй пароль"]),
    ("weather",         ["погода", "градус", "температур"]),
    ("time",            ["время", "который час"]),
    ("date",            ["дата", "число", "какой сегодня день"]),
    ("math",            ["плюс", "минус", "умножить", "разделить", "посчитай"]),
]

_trigger_lock = threading.Lock()


def has_wake_word(text):
    return any(w in text for w in WAKE_WORDS)


def detect_action(text):
    tl = text.lower().strip()
    cs_priority = ["тренир", "тренер", "размин", "аим", "aim", "даст", "мираж",
                   "инферн", "нук", "оверпас", "задрот"]

    for name, keywords in ACTIONS:
        for kw in keywords:
            if kw not in tl:
                continue
            if kw == "вк":
                if any(cp in tl for cp in cs_priority):
                    continue
                pattern = r'(?:^|\s)' + re.escape(kw) + r'(?:\s|$)'
                if not re.search(pattern, tl):
                    continue
            return name
    return None


def find_in_knowledge(question):
    q = question.lower()
    for key, answer in KNOWLEDGE_BASE.items():
        if key in q:
            return answer
    for syn, real_key in KNOWLEDGE_SYNONYMS.items():
        if syn in q and real_key in KNOWLEDGE_BASE:
            return KNOWLEDGE_BASE[real_key]
    words = re.findall(r'\w+', q)
    for word in words:
        if len(word) < 4:
            continue
        for key, answer in KNOWLEDGE_BASE.items():
            if word in key or key in word:
                return answer
    return None


def answer_question(question, log_func=None):
    q = question.lower()
    for w in WAKE_WORDS:
        q = q.replace(w, " ").strip()
    for prefix in ["что такое", "кто такой", "кто такая", "расскажи о",
                   "расскажи про", "объясни", "что значит"]:
        q = q.replace(prefix, " ").strip()
    q = " ".join(q.split())
    if not q:
        return
    answer = find_in_knowledge(q)
    if answer:
        speak(answer, log_func)


def handle_topics(log_func):
    topics = sorted(KNOWLEDGE_BASE.keys())
    count = len(topics)
    log_func(f"Тем: {count}", "trigger")
    for i, topic in enumerate(topics, 1):
        log_func(f"  {i}. {topic}", "info")
    speak(f"Хозяин, я знаю {count} тем. Список показала в логе.", log_func)


# ======================= ЗАПИСЬ ЭКРАНА =======================
def _recording_worker(output_path, fps, stop_event, log_func):
    try:
        screen_w, screen_h = pyautogui.size()
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out = cv2.VideoWriter(output_path, fourcc, fps, (screen_w, screen_h))
        start = time.time()
        frame_count = 0
        while not stop_event.is_set():
            img = pyautogui.screenshot()
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            out.write(frame)
            frame_count += 1
            elapsed = time.time() - start
            expected = frame_count / fps
            if expected > elapsed:
                time.sleep(expected - elapsed)
        out.release()
        speak("Запись сохранена на рабочий стол, хозяин", log_func)
    except Exception as e:
        log_func(f"Ошибка записи: {e}", "error")


def start_recording(log_func):
    if not CV2_AVAILABLE or not PYAW_AVAILABLE:
        speak("Не могу записать экран", log_func)
        return
    if RECORDING["active"]:
        speak("Запись уже идёт", log_func)
        return
    try:
        user = os.environ.get("USERPROFILE", "")
        desktop = os.path.join(user, "Desktop")
        if not os.path.isdir(desktop):
            desktop = os.path.join(user, "Рабочий стол")
        filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
        output_path = os.path.join(desktop, filename)
        stop_event = threading.Event()
        RECORDING["active"] = True
        RECORDING["stop_flag"] = stop_event
        RECORDING["output_path"] = output_path
        t = threading.Thread(target=_recording_worker,
                             args=(output_path, RECORDING["fps"], stop_event, log_func),
                             daemon=True)
        RECORDING["thread"] = t
        t.start()
        speak("Начала запись экрана.", log_func)
    except Exception as e:
        log_func(f"Ошибка: {e}", "error")


def stop_recording(log_func):
    if not RECORDING["active"]:
        speak("Запись и так не идёт", log_func)
        return
    RECORDING["stop_flag"].set()
    RECORDING["active"] = False


# ======================= ПРОЧИЕ =======================
def find_and_launch(names, log_func=None, label="программу"):
    user = os.environ.get("USERPROFILE", "")
    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    public = os.environ.get("PUBLIC", r"C:\Users\Public")
    dirs = [
        os.path.join(user, "Desktop"), os.path.join(user, "Рабочий стол"),
        os.path.join(public, "Desktop"), os.path.join(public, "Рабочий стол"),
        r"C:\Program Files", r"C:\Program Files (x86)", appdata, localappdata,
    ]
    exts = [".lnk", ".exe", ".url", ".bat"]
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for name in names:
            for ext in exts:
                c = os.path.join(d, name + ext)
                if os.path.exists(c):
                    try:
                        os.startfile(c)
                        log_func(f"Запустила {label}", "launch")
                        return True
                    except Exception:
                        pass
    return False


def launch_csgo(log_func=None):
    if not STEAM_PATH:
        log_func("Steam не найден!", "error")
        speak("Steam не найден, хозяин", log_func)
        return
    try:
        subprocess.Popen([STEAM_PATH, "-applaunch", CSGO_APP_ID])
        log_func(f"CS:GO (App ID {CSGO_APP_ID}) запускается!", "launch")
    except Exception as e:
        log_func(f"Ошибка: {e}", "error")


def open_calculator(log_func):
    subprocess.Popen("calc.exe")
    speak("Открываю калькулятор", log_func)


def open_notepad(log_func):
    subprocess.Popen("notepad.exe")


def open_explorer(log_func):
    subprocess.Popen("explorer.exe")


def make_screenshot(log_func):
    if not PYAW_AVAILABLE:
        return
    user = os.environ.get("USERPROFILE", "")
    desktop = os.path.join(user, "Desktop")
    if not os.path.isdir(desktop):
        desktop = os.path.join(user, "Рабочий стол")
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = os.path.join(desktop, filename)
    pyautogui.screenshot().save(path)
    speak("Скриншот сохранён", log_func)


def volume_up(log_func):
    if PYAW_AVAILABLE:
        for _ in range(5):
            pyautogui.press("volumeup")


def volume_down(log_func):
    if PYAW_AVAILABLE:
        for _ in range(5):
            pyautogui.press("volumedown")


def mute_volume(log_func):
    if PYAW_AVAILABLE:
        pyautogui.press("volumemute")


def minimize_all(log_func):
    if PYAW_AVAILABLE:
        pyautogui.hotkey("win", "d")


def media_pause(log_func):
    if PYAW_AVAILABLE:
        pyautogui.press("playpause")


def media_play(log_func):
    if PYAW_AVAILABLE:
        pyautogui.press("playpause")


def media_next(log_func):
    if PYAW_AVAILABLE:
        pyautogui.press("nexttrack")


def media_prev(log_func):
    if PYAW_AVAILABLE:
        pyautogui.press("prevtrack")


def tell_joke(log_func):
    jokes = [
        "Программист - это машина по превращению кофе в код.",
        "Работает? Не трогай!",
        "Нет, это не баг. Это фича.",
    ]
    speak(random.choice(jokes), log_func)


def tell_fact(log_func):
    facts = [
        "Мёд не портится. Находили горшки возрастом 3000 лет.",
        "Осьминоги имеют три сердца.",
        "Бананы - это ягоды.",
    ]
    speak(random.choice(facts), log_func)


def tell_quote(log_func):
    quotes = [
        "Не важно, как медленно ты идёшь, главное - не останавливаться.",
        "Всё, что нас не убивает, делает нас сильнее.",
    ]
    speak(random.choice(quotes), log_func)


def flip_coin(log_func):
    speak(f"Выпал {random.choice(['орёл', 'решка'])}", log_func)


def random_number(text, log_func):
    numbers = re.findall(r'\d+', text)
    if len(numbers) >= 2:
        a, b = int(numbers[0]), int(numbers[1])
        if a > b:
            a, b = b, a
        speak(f"Случайное число: {random.randint(a, b)}", log_func)
    else:
        speak(f"Случайное число: {random.randint(1, 100)}", log_func)


def generate_password(length_str, log_func):
    try:
        length = max(4, min(128, int(length_str)))
    except Exception:
        length = 16
    alphabet = string.ascii_letters + string.digits
    pwd = "".join(random.choice(alphabet) for _ in range(length))
    log_func(f"Пароль: {pwd}", "trigger")
    speak(f"Пароль из {length} символов в логе", log_func)


def do_search(query, log_func=None):
    if not query:
        speak("Что найти, хозяин?", log_func)
        return
    if not can_open("find"):
        return
    search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    open_url(search_url)
    speak(f"Ищу {query} в интернете", log_func)


def lock_pc(log_func):
    os.system("rundll32.exe user32.dll,LockWorkStation")


def open_task_manager(log_func):
    subprocess.Popen("taskmgr.exe")


def open_settings(log_func):
    subprocess.Popen("ms-settings:", shell=True)


def reboot_pc(log_func):
    speak("Перезагружаю через 30 секунд", log_func)
    os.system("shutdown /r /t 30")


def shutdown_pc(log_func):
    speak("Выключаю через 30 секунд", log_func)
    os.system("shutdown /s /t 30")


def note_add(text, log_func):
    if not text:
        speak("Что записать?", log_func)
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {text}\n")
    speak("Записала", log_func)


def note_show(log_func):
    if not os.path.exists(NOTES_FILE):
        speak("Заметок нет", log_func)
        return
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
    lines = content.split("\n")
    for line in lines:
        log_func(f"  {line}", "info")
    speak(f"У вас {len(lines)} заметок", log_func)


def note_clear(log_func):
    if os.path.exists(NOTES_FILE):
        os.remove(NOTES_FILE)
    speak("Очистила заметки", log_func)


def launch_roblox(log_func=None):
    if find_and_launch(["Roblox", "Roblox Player", "RobloxPlayerBeta", "Роблокс"],
                       log_func, label="Roblox"):
        speak("Открываю роблокс", log_func)
        return
    try:
        open_url("roblox://")
    except Exception:
        pass


def launch_telegram(log_func=None):
    if find_and_launch(["Telegram", "Telegram Desktop", "телеграм"],
                       log_func, label="Telegram"):
        speak("Открываю телеграм", log_func)
        return
    speak("Не нашла телеграм", log_func)


def launch_discord(log_func=None):
    if find_and_launch(["Discord", "дискорд"], log_func, label="Discord"):
        speak("Открываю лолик", log_func)
        return
    speak("Не нашла лолик", log_func)


def do_math(text, log_func):
    t = text.lower()
    for w in WAKE_WORDS:
        t = t.replace(w, " ")
    tokens = []
    nums = {"ноль": 0, "один": 1, "два": 2, "три": 3, "четыре": 4, "пять": 5,
            "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10}
    for word in t.split():
        if word.isdigit():
            tokens.append(("num", int(word)))
        elif word in nums:
            tokens.append(("num", nums[word]))
        elif word in ("плюс", "+"):
            tokens.append(("op", "+"))
        elif word in ("минус", "-"):
            tokens.append(("op", "-"))
        elif word in ("умножить", "*"):
            tokens.append(("op", "*"))
        elif word in ("разделить", "/"):
            tokens.append(("op", "/"))
    if len(tokens) < 3:
        speak("Не поняла пример", log_func)
        return
    try:
        result = tokens[0][1]
        i = 1
        while i + 1 < len(tokens):
            op, b = tokens[i][1], tokens[i + 1][1]
            if op == "+": result += b
            elif op == "-": result -= b
            elif op == "*": result *= b
            elif op == "/":
                if b == 0:
                    speak("На ноль делить нельзя", log_func)
                    return
                result /= b
            i += 2
        if result == int(result): result = int(result)
        speak(f"Хозяин, {result}", log_func)
    except Exception:
        pass


# ======================= ОБРАБОТКА КОМАНД =======================
def execute_action(action, log_func, partial=False, text=""):
    global _last_action_time, TTS_RATE, TTS_VOICE_KEYWORD

    if action == "cs_map_aim_botz":
        cs_map_command("aim_botz", log_func, voice_name="тренировку"); return True
    if action == "cs_map_aim_map":
        cs_map_command("aim_map", log_func, voice_name="аим мап"); return True
    if action == "cs_map_dust2":
        cs_map_command("de_dust2", log_func, voice_name="даст 2"); return True
    if action == "cs_map_mirage":
        cs_map_command("de_mirage", log_func, voice_name="мираж"); return True
    if action == "cs_map_inferno":
        cs_map_command("de_inferno", log_func, voice_name="инферно"); return True
    if action == "cs_map_nuke":
        cs_map_command("de_nuke", log_func, voice_name="нук"); return True
    if action == "cs_map_overpass":
        cs_map_command("de_overpass", log_func, voice_name="оверпасс"); return True
    if action == "cs_add_bots":
        cs_add_bots(log_func); return True
    if action == "cs_kick_bots":
        cs_kick_bots(log_func); return True
    if action == "cs_crosshair":
        cs_setup_crosshair(log_func); return True
    if action == "cs_fps_on":
        cs_show_fps(log_func); return True

    if action == "mouse_move":
        tl = text.lower()
        direction = ""
        if "вверх" in tl or "верх" in tl: direction = "вверх"
        elif "вниз" in tl or "низ" in tl: direction = "вниз"
        elif "влево" in tl or "лево" in tl: direction = "влево"
        elif "вправо" in tl or "право" in tl: direction = "вправо"
        if direction:
            move_mouse(direction, log_func)
            speak(f"Двигаю мышку {direction}", log_func)
        else:
            speak("Куда двигать мышку, хозяин?", log_func)
        return True

    if action == "mouse_click":
        mouse_click("left", log_func); speak("Клик", log_func); return True
    if action == "mouse_right":
        mouse_click("right", log_func); speak("Правый клик", log_func); return True
    if action == "mouse_scroll_down":
        scroll_mouse("down", 5, log_func); speak("Прокручиваю вниз", log_func); return True
    if action == "mouse_scroll_up":
        scroll_mouse("up", 5, log_func); speak("Прокручиваю вверх", log_func); return True

    if action == "functional": give_functional(log_func); return True
    if action == "info": give_info(log_func); return True
    if action == "stop_all":
        stop_speaking(log_func); _last_action_time = 0; return True
    if action == "faster":
        TTS_RATE = min(TTS_RATE + 40, 300); speak("Говорю быстрее", log_func); return True
    if action == "slower":
        TTS_RATE = max(TTS_RATE - 40, 100); speak("Говорю медленнее", log_func); return True
    if action == "voice_irina":
        TTS_VOICE_KEYWORD = "irina"; speak("Говорю женским голосом", log_func); return True
    if action == "voice_pavel":
        TTS_VOICE_KEYWORD = "pavel"; speak("Говорю мужским голосом", log_func); return True
    if action == "voice_list":
        voices = list_installed_voices()
        log_func("Голоса:", "trigger")
        for v in voices:
            log_func(f"  - {v['name']}", "info")
        speak("Показала список в логе", log_func); return True
    if action == "about_me":
        speak(ABOUT_ME, log_func); return True
    if action == "story":
        speak(random.choice(STORIES), log_func); return True
    if action == "topics":
        handle_topics(log_func); return True
    if action == "question":
        answer_question(text, log_func); return True

    if action == "youtube":
        if can_open("youtube"):
            open_url("https://www.youtube.com"); speak("Открываю ютуб", log_func)
        return True
    if action == "vk_open":
        if can_open("vk"):
            open_url("https://vk.com/im"); speak("Открываю ВК", log_func)
        return True
    if action == "music":
        if can_open("music"):
            open_url("https://music.youtube.com"); speak("Открываю музыку", log_func)
        return True
    if action == "movie":
        if can_open("movie"):
            open_url("https://www.kinopoisk.ru"); speak("Открываю кинопоиск", log_func)
        return True
    if action == "roblox":
        if can_open("roblox"): launch_roblox(log_func)
        return True
    if action == "telegram":
        if can_open("telegram"): launch_telegram(log_func)
        return True
    if action == "discord":
        if can_open("discord"): launch_discord(log_func)
        return True
    if action == "csgo":
        if can_open("csgo"): launch_csgo(log_func)
        return True

    if action == "find":
        q = text.lower()
        for w in WAKE_WORDS:
            q = q.replace(w, " ")
        for prefix in ["найти", "найди", "поискать", "поищи", "искать"]:
            if prefix in q:
                idx = q.index(prefix) + len(prefix)
                q = q[idx:].strip()
                break
        do_search(q, log_func); return True

    if action == "system": system_report_voice(log_func); return True
    if action == "record_start": start_recording(log_func); return True
    if action == "record_stop": stop_recording(log_func); return True
    if action == "lock_pc": lock_pc(log_func); return True
    if action == "reboot_pc": reboot_pc(log_func); return True
    if action == "shutdown": shutdown_pc(log_func); return True
    if action == "task_manager": open_task_manager(log_func); return True
    if action == "settings_win": open_settings(log_func); return True
    if action == "note_add":
        t = text.lower()
        note_text = ""
        for prefix in ["запиши заметку", "добавь заметку", "запомни"]:
            if prefix in t:
                idx = t.index(prefix) + len(prefix)
                note_text = text[idx:].strip()
                break
        note_add(note_text, log_func); return True
    if action == "note_show": note_show(log_func); return True
    if action == "note_clear": note_clear(log_func); return True
    if action == "media_pause": media_pause(log_func); return True
    if action == "media_play": media_play(log_func); return True
    if action == "media_next": media_next(log_func); return True
    if action == "media_prev": media_prev(log_func); return True
    if action == "volume_up": volume_up(log_func); return True
    if action == "volume_down": volume_down(log_func); return True
    if action == "mute": mute_volume(log_func); return True
    if action == "minimize_all": minimize_all(log_func); return True
    if action == "screenshot": make_screenshot(log_func); return True
    if action == "calc": open_calculator(log_func); return True
    if action == "notepad": open_notepad(log_func); return True
    if action == "explorer": open_explorer(log_func); return True
    if action == "joke": tell_joke(log_func); return True
    if action == "fact": tell_fact(log_func); return True
    if action == "quote": tell_quote(log_func); return True
    if action == "coin": flip_coin(log_func); return True
    if action == "random": random_number(text, log_func); return True
    if action == "password":
        m = re.search(r'\d+', text)
        generate_password(m.group(0) if m else "16", log_func); return True
    if action == "weather": open_weather(log_func); return True
    if action == "time":
        now = datetime.now()
        speak(f"Хозяин, сейчас {now.hour} часов {now.minute} минут", log_func); return True
    if action == "date":
        months = ["января", "февраля", "марта", "апреля", "мая", "июня",
                  "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        now = datetime.now()
        speak(f"Хозяин, сегодня {days[now.weekday()]}, {now.day} {months[now.month-1]} {now.year} года", log_func)
        return True
    if action == "math": do_math(text, log_func); return True

    return False


def handle_text(text, log_func, partial=False):
    global _last_action_time

    if not partial:
        if not has_wake_word(text):
            tl = text.lower().strip()
            for key, response in DIALOGS.items():
                if key in tl:
                    with _trigger_lock:
                        now = time.time()
                        if now - _last_action_time < 2:
                            return
                        _last_action_time = now
                    speak(response, log_func)
                    return

    if has_wake_word(text):
        action = detect_action(text)
        if action:
            if partial and action in (
                "vk_open", "youtube", "discord", "telegram", "roblox",
                "csgo", "music", "movie", "find", "info", "question",
                "story", "about_me", "topics", "system", "functional",
                "mouse_move", "mouse_click", "mouse_right",
                "mouse_scroll_down", "mouse_scroll_up",
                "cs_map_aim_botz", "cs_map_aim_map", "cs_map_dust2",
                "cs_map_mirage", "cs_map_inferno", "cs_map_nuke",
                "cs_map_overpass", "cs_add_bots", "cs_kick_bots",
                "cs_crosshair", "cs_fps_on"
            ):
                return
            execute_action(action, log_func, partial=partial, text=text)
        else:
            if partial:
                return
            q = text.lower()
            for w in WAKE_WORDS:
                q = q.replace(w, " ").strip()
            q = " ".join(q.split())
            if len(q) > 3:
                with _trigger_lock:
                    now = time.time()
                    if now - _last_action_time < 3:
                        return
                    _last_action_time = now
                answer_question(q, log_func)


# ======================= РАСПОЗНАВАНИЕ =======================
def listen_worker(log_func):
    model = load_vosk_model(log_func)
    if model is None:
        log_func("Модель не загружена", "error")
        return

    device_index = pick_best_microphone(log_func)
    if device_index is None:
        return

    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(True)
    audio_queue = queue.Queue()

    def cb(indata, frames, time_info, status):
        audio_queue.put(bytes(indata))

    log_func("Слушаю...", "info")

    import audioop
    last_partial = ""
    last_handled = ""

    try:
        with sd.RawInputStream(
                samplerate=SAMPLE_RATE, blocksize=BLOCKSIZE,
                device=device_index, dtype='int16', channels=1, callback=cb):
            while not stop_flag.is_set():
                try:
                    data = audio_queue.get(timeout=QUEUE_TIMEOUT)
                except queue.Empty:
                    continue
                rms = audioop.rms(data, 2)
                if rms < RMS_THRESHOLD:
                    rec.AcceptWaveform(data)
                    continue
                if rec.AcceptWaveform(data):
                    r = json.loads(rec.Result())
                    t = r.get("text", "").lower().strip()
                    if t:
                        log_func(f'Услышал: "{t}"', "recognized")
                        handle_text(t, log_func, partial=False)
                        last_partial = ""
                        last_handled = ""
                else:
                    p = json.loads(rec.PartialResult()).get("partial", "").lower().strip()
                    if p and p != last_partial:
                        last_partial = p
                        if p != last_handled:
                            last_handled = p
                            handle_text(p, log_func, partial=True)
    except Exception as e:
        log_func(f"Ошибка аудио: {e}", "error")


# ======================= GUI =======================
class CmdWindow:
    def __init__(self, root):
        self.root = root
        root.title("Jarvis")
        root.geometry("950x700")
        root.configure(bg=BG_COLOR)

        top = tk.Frame(root, bg=BG_COLOR)
        top.pack(fill="x", padx=8, pady=(8, 0))

        self.btn_start = tk.Button(top, text="СТАРТ", font=("Consolas", 10, "bold"),
                                    bg="#1a1a1a", fg=GREEN, activebackground="#333",
                                    relief="flat", padx=14, pady=4, cursor="hand2",
                                    command=self.start_listening)
        self.btn_start.pack(side="left", padx=(0, 6))

        self.btn_stop = tk.Button(top, text="СТОП", font=("Consolas", 10, "bold"),
                                   bg="#1a1a1a", fg=RED, activebackground="#333",
                                   relief="flat", padx=14, pady=4, cursor="hand2",
                                   state="disabled", command=self.stop_listening)
        self.btn_stop.pack(side="left", padx=(0, 6))

        self.btn_clear = tk.Button(top, text="ОЧИСТИТЬ", font=("Consolas", 10, "bold"),
                                    bg="#1a1a1a", fg=YELLOW, activebackground="#333",
                                    relief="flat", padx=14, pady=4, cursor="hand2",
                                    command=self.clear_log)
        self.btn_clear.pack(side="left", padx=(0, 6))

        self.btn_system = tk.Button(top, text="СИСТЕМА", font=("Consolas", 10, "bold"),
                                     bg="#1a1a1a", fg=CYAN, activebackground="#333",
                                     relief="flat", padx=14, pady=4, cursor="hand2",
                                     command=self.test_system)
        self.btn_system.pack(side="left", padx=(0, 6))

        self.btn_info = tk.Button(top, text="ИНФОРМАЦИЯ", font=("Consolas", 10, "bold"),
                                   bg="#1a1a1a", fg=MAGENTA, activebackground="#333",
                                   relief="flat", padx=14, pady=4, cursor="hand2",
                                   command=self.test_info)
        self.btn_info.pack(side="left", padx=(0, 6))

        self.btn_functional = tk.Button(top, text="ФУНКЦИОНАЛ", font=("Consolas", 10, "bold"),
                                         bg="#1a1a1a", fg=YELLOW, activebackground="#333",
                                         relief="flat", padx=14, pady=4, cursor="hand2",
                                         command=self.test_functional)
        self.btn_functional.pack(side="left")

        self.status_label = tk.Label(top, text="ЗАГРУЗКА...", font=("Consolas", 10, "bold"),
                                      bg=BG_COLOR, fg=YELLOW)
        self.status_label.pack(side="right", padx=8)

        self.log_widget = scrolledtext.ScrolledText(
            root, wrap="word", font=("Consolas", 11),
            bg=BG_COLOR, fg=FG_COLOR, insertbackground=GREEN,
            relief="flat", borderwidth=0, state="disabled")
        self.log_widget.pack(fill="both", expand=True, padx=8, pady=8)

        self.log_widget.tag_config("time", foreground=GRAY)
        self.log_widget.tag_config("info", foreground=CYAN)
        self.log_widget.tag_config("heard", foreground=YELLOW)
        self.log_widget.tag_config("recognized", foreground="#FFFFFF")
        self.log_widget.tag_config("trigger", foreground=GREEN, font=("Consolas", 11, "bold"))
        self.log_widget.tag_config("error", foreground=RED)
        self.log_widget.tag_config("launch", foreground=GREEN, font=("Consolas", 12, "bold"))
        self.log_widget.tag_config("noise", foreground=GRAY)
        self.log_widget.tag_config("speak", foreground=MAGENTA, font=("Consolas", 11, "bold"))

        bottom = tk.Label(
            root,
            text=f'Тем: {len(KNOWLEDGE_BASE)} | "Джарвис функционал" - список команд',
            font=("Consolas", 9), bg="#1a1a1a", fg=GRAY, anchor="w", padx=10, pady=4)
        bottom.pack(fill="x", side="bottom")

        self.root.after(20, self.process_log_queue)

        self.log("Jarvis запущен", "info")
        self.log("Голос: женский (Ирина)", "info")
        self.log(f"Steam: {STEAM_PATH or 'НЕ НАЙДЕН!'}", "info" if STEAM_PATH else "error")
        self.log(f"CS:GO App ID: {CSGO_APP_ID}", "info")
        self.log("-" * 70, "noise")

        threading.Thread(target=self.load_model_bg, daemon=True).start()

    def load_model_bg(self):
        model = load_vosk_model(self.log)
        if model:
            self.log("Модель готова. Нажми СТАРТ.", "trigger")
            self.status_label.config(text="ГОТОВ", fg=GREEN)
            speak("Система готова, хозяин", self.log)
        else:
            self.log("Модель не загружена.", "error")
            self.status_label.config(text="ОШИБКА", fg=RED)

    def test_system(self):
        system_report_voice(self.log)

    def test_info(self):
        give_info(self.log)

    def test_functional(self):
        give_functional(self.log)

    def log(self, text, tag=None):
        log_queue.put((text, tag))

    def process_log_queue(self):
        try:
            while True:
                text, tag = log_queue.get_nowait()
                self._append(text, tag)
        except queue.Empty:
            pass
        self.root.after(20, self.process_log_queue)

    def _append(self, text, tag=None):
        self.log_widget.config(state="normal")
        ts = time.strftime("%H:%M:%S")
        self.log_widget.insert("end", f"[{ts}] ", "time")
        if tag:
            self.log_widget.insert("end", text + "\n", tag)
        else:
            self.log_widget.insert("end", text + "\n")
        self.log_widget.see("end")
        self.log_widget.config(state="disabled")

    def clear_log(self):
        self.log_widget.config(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.config(state="disabled")
        self.log("Журнал очищен.", "noise")

    def start_listening(self):
        global is_listening
        if is_listening:
            return
        if _vosk_model is None:
            self.log("Модель ещё не загружена. Подожди.", "error")
            return
        is_listening = True
        stop_flag.clear()
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.status_label.config(text="СЛУШАЮ...", fg=GREEN)
        self.log("-" * 70, "noise")
        self.log("Запуск прослушки...", "info")
        threading.Thread(target=listen_worker, args=(self.log,), daemon=True).start()

    def stop_listening(self):
        global is_listening
        if not is_listening:
            return
        stop_flag.set()
        is_listening = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.status_label.config(text="ГОТОВ", fg=GREEN)
        self.log("Прослушка остановлена.", "error")


if __name__ == "__main__":
    root = tk.Tk()
    app = CmdWindow(root)
    root.mainloop()
