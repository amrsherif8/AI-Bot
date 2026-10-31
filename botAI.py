import asyncio
import os
import re
import tempfile
import threading

import edge_tts
import pygame
import sounddevice as sd
from faster_whisper import WhisperModel

import math_solver
import translator
from llm import LLMUnavailable, chat
from sound import trigger_sound

SAMPLE_RATE = 16000
SECONDS = 5
MAX_CONVERSATION = 20

print("Loading speech recognition model...")


speech_model = WhisperModel("base", device="cpu", compute_type="int8")

LANGUAGE_NAMES = {"ar": "Arabic", "en": "English", "de": "German"}
input_lang = None
heard_lang = None


def _system_prompt(lang):
    if lang in LANGUAGE_NAMES:
        return (
            "You are a helpful robot assistant. Respond concisely and naturally. "
            f"Always reply in {LANGUAGE_NAMES[lang]}, whatever language the user speaks."
        )
    return (
        "You are a helpful robot assistant. "
        "Respond concisely and naturally in the language spoken to you."
    )


conversation = [{"role": "system", "content": _system_prompt(input_lang)}]

robot_thread = None
stop_event = threading.Event()
_start_lock = threading.Lock()

VOICES = {
    "en": "en-US-SteffanNeural",
    "de": "de-DE-KillianNeural",
    "ar": "ar-EG-SalmaNeural",
}



def _pick_voice(text, lang):
    if lang in VOICES:
        return VOICES[lang]
    if any("؀" <= c <= "ۿ" for c in text):
        return VOICES["ar"]
    return VOICES["en"]


def speak(text, lang=None):
    print("Robot:", text)
    if not text or not text.strip():
        return

    voice = _pick_voice(text, lang)

    async def _generate(path):
        await edge_tts.Communicate(text, voice).save(path)


    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        asyncio.run(_generate(path))
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if stop_event.is_set():
                pygame.mixer.music.stop()
                break
            pygame.time.Clock().tick(10)
        pygame.mixer.music.unload()
    except Exception as error:
        print("TTS Error:", error)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass



def listen(duration=SECONDS):
    print("Listening...")
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )

    for _ in range(int(duration * 10)):
        if stop_event.is_set():
            sd.stop()
            return ""
        sd.sleep(100)
    sd.wait()

    global heard_lang
    segments, info = speech_model.transcribe(
        audio.flatten(),
        vad_filter=True,
        beam_size=5,
        language=input_lang,
        condition_on_previous_text=False,
    )
    heard_lang = info.language
    return " ".join(segment.text for segment in segments).strip()


def _voice_lang():
    if input_lang:
        return input_lang
    return heard_lang if heard_lang in VOICES else None


def ask_robot(text):
    conversation.append({"role": "user", "content": text})
    del conversation[1:-(MAX_CONVERSATION - 2)]      # بعد رد الموديل بيبقى المجموع MAX_CONVERSATION
    try:
        answer = chat(conversation)
    except LLMUnavailable as error:
        print("Gemini error:", error)
        conversation.pop()      # السؤال ماتجاوبش: نشيله عشان ماييجيش سؤالين ورا بعض في المحادثة
        return "I can't reach my brain right now."
    conversation.append({"role": "assistant", "content": answer})
    return answer


SOLVE_COMMAND = re.compile(r"^\W*(?:solve|احسب|حل)\s+(.+)$", re.IGNORECASE | re.DOTALL)


def handle_math(user_text):
    match = SOLVE_COMMAND.match(user_text)
    if not match:
        return False
    try:
        result = math_solver.solve(match.group(1).strip(), "solve")
    except math_solver.MathError as error:
        speak(error.text("en"), lang="en")
    else:
        if result["kind"] == "no_solution":
            speak("There is no solution.", lang="en")
        else:
            speak(f"The result is {result['result']}", lang="en")
    return True


def handle_clear(user_text):
    text = user_text.lower()
    if "clear history" in text or "امسح السجل" in user_text:
        math_solver.clear_history()
        del conversation[1:]
        speak("History cleared successfully.", lang="en")
        return True
    return False


def handle_translation(user_text):
    parsed = translator.parse_command(user_text)
    if parsed is None:
        return False
    target, text = parsed

    if not text:
        speak("What should I translate?", lang="en")
        text = listen()
        if not text:
            return True
        print("You:", text)

    try:
        result = translator.translate(text, target, source="auto")
    except translator.TranslateError as error:
        speak(error.text("en"), lang="en")
    except translator.TranslatorUnavailable:
        speak("I can't reach my translator right now.", lang="en")
    else:
        speak(result["translation"], lang=target)
    return True


def handle_voice_commands(user_text):
    return handle_translation(user_text) or handle_math(user_text) or handle_clear(user_text)


def robot_loop():
    speak("Hello! How can I help you?", lang="en")

    while not stop_event.is_set():
        try:
            user_text = listen()
            if not user_text:
                continue

            print("You:", user_text)

            if handle_voice_commands(user_text):
                continue

            if trigger_sound(user_text):
                continue

            if "stop robot" in user_text.lower() or "توقف" in user_text:
                speak("Okay, shutting down now.", lang="en")
                break

            speak(ask_robot(user_text), lang=_voice_lang())

        except Exception as error:
            print("Loop error:", error)
            sd.sleep(1000)

    print("Robot stopped.")


def start_robot():
    global robot_thread
    with _start_lock:
        if robot_thread and robot_thread.is_alive():
            if not stop_event.is_set():
                return False
            robot_thread.join(timeout=15)
            if robot_thread.is_alive():
                return False

        stop_event.clear()
        del conversation[1:]
        robot_thread = threading.Thread(target=robot_loop, daemon=True)
        robot_thread.start()
        return True


def set_input_language(code):
    global input_lang
    input_lang = code if code in LANGUAGE_NAMES else None
    conversation[0]["content"] = _system_prompt(input_lang)
    return input_lang or "auto"


def stop_robot():
    stop_event.set()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        set_input_language(sys.argv[1])
    start_robot()
    try:
        while robot_thread.is_alive():
            robot_thread.join(0.5)
    except KeyboardInterrupt:
        stop_robot()
        robot_thread.join(timeout=15)
