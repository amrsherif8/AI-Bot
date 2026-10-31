import re
import threading
from pathlib import Path

try:
    import pygame
except ImportError:  # على السيرفر مفيش سماعات
    pygame = None

BASE_DIR = Path(__file__).resolve().parent
AUDIO_NAMES = ("Sound_1.mp3", "Sound.mp3")


WORDS = {
    "Hamza": (0, 4),
    "Ahmed": (4, 8),
    "hi": (12, 15),
}

stop_timer = None
_lock = threading.Lock()


def _audio_path():
    for folder in (BASE_DIR, Path.cwd()):
        for name in AUDIO_NAMES:
            path = folder / name
            if path.is_file():
                return path
    return None


def _key(word):
    word = (word or "").strip().lower()
    for name in WORDS:
        if name.lower() == word:
            return name
    return None


def find_sound(word):
    key = _key(word)
    return WORDS[key] if key else None


def list_sounds():
    return [
        {"word": name, "start": start, "end": end, "duration": end - start}
        for name, (start, end) in WORDS.items()
    ]


def play_word(word):
    global stop_timer
    key = _key(word)
    if key is None or pygame is None:
        return False
    path = _audio_path()
    if path is None:
        print(f"Cannot play '{key}': none of {AUDIO_NAMES} was found next to sound.py or in the working directory.")
        return False
    start, end = WORDS[key]
    with _lock:
        if stop_timer:
            stop_timer.cancel()
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play(start=start)
        except pygame.error as error:
            print("Audio error:", error)
            return False
        stop_timer = threading.Timer(end - start, _stop)
        stop_timer.daemon = True
        stop_timer.start()
    return True


def _stop():
    if pygame is None:
        return
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except pygame.error:
        pass


def trigger_sound(text):
    text = (text or "").lower()
    for word in WORDS:
        if re.search(rf"\b{re.escape(word.lower())}\b", text) and play_word(word):
            return True
    return False


if __name__ == "__main__":
    import sys
    import time

    word = " ".join(sys.argv[1:]) or input(f"Word ({', '.join(WORDS)}): ")
    key = _key(word)
    if key is not None and play_word(key):
        start, end = WORDS[key]
        time.sleep(end - start + 0.5)
    else:
        print("Word not found, or the audio file is missing.")
