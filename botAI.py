import os
import subprocess
import threading

import requests
import sounddevice as sd
from faster_whisper import WhisperModel

import translator
from sound import trigger_sound

MODEL_NAME = "llama3.2:3b"
SAMPLE_RATE = 16000
SECONDS = 6

# أمر الترجمة بالصوت: الـ regex والتحليل في translator.py (parse_command)،
# عشان الصوت والـ API يشتغلوا بنفس الصيغ.


print("Loading speech recognition model...")
speech_model = WhisperModel("base", device="cpu", compute_type="int8")

conversation = [
    {
        "role": "system",
        "content": (
            "You are an English-speaking robot assistant. "
            "You MUST respond entirely in English. "
            "Use simple, natural, conversational English. "
            "Keep responses concise and suitable for speaking aloud."
        ),
    }
]

robot_thread = None
stop_event = threading.Event()


def listen():
    print("Listening...")
    audio = sd.rec(
        int(SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()

    segments, _ = speech_model.transcribe(
        audio.flatten(),
        language="en",
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=False,
    )
    return " ".join(segment.text for segment in segments).strip()


def ask_robot(text):
    conversation.append({"role": "user", "content": text})

    response = requests.post(
        "http://localhost:11434/api/chat",
        json={"model": MODEL_NAME, "messages": conversation, "stream": False},
        timeout=180,
    )
    response.raise_for_status()

    answer = response.json()["message"]["content"]
    conversation.append({"role": "assistant", "content": answer})
    return answer


def speak(text):
    print("Robot:", text)
    env = dict(os.environ, SPEAK_TEXT=text)
    subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            "Add-Type -AssemblyName System.Speech; "
            "(New-Object System.Speech.Synthesis.SpeechSynthesizer)"
            ".Speak($env:SPEAK_TEXT)",
        ],
        env=env,
        check=False,
    )


def handle_translation(user_text):
    """لو الجملة أمر ترجمة بينفذه ويرجع True. لو لأ يرجع False والحلقة تكمل عادي."""
    parsed = translator.parse_command(user_text)
    if parsed is None:
        return False
    target, text = parsed

    # Whisper متظبط على الإنجليزي (language="en")، يعني الكلام اللي بيتسمع إنجليزي دايماً
    if target == "en":
        speak("Everything I hear is already English. Try German or Arabic.")
        return True

    if not text:
        speak("What should I translate?")
        text = listen()
        if not text:
            return True
        print("You:", text)

    try:
        result = translator.translate(text, target, source="en")
    except translator.TranslateError:
        speak("Sorry, I can't translate that.")
    except translator.TranslatorUnavailable:
        speak("I can't reach my translator. Is Ollama running?")
    else:
        speak(result["translation"])
    return True


def robot_loop():
    speak("Hello! How can I help you?")

    while not stop_event.is_set():
        try:
            user_text = listen()

            if not user_text:
                continue

            print("You:", user_text)

            # الترجمة الأول، عشان "hi" جوه كلمة زي "this" ماتشغّلش الصوت بالغلط
            if handle_translation(user_text):
                continue

            if trigger_sound(user_text):
                continue

            if "stop robot" in user_text.lower():
                speak("Okay, shutting down now.")
                break

            speak(ask_robot(user_text))

        except requests.RequestException as error:
            print("Ollama connection error:", error)
            speak("I can't reach my brain. Is Ollama running?")
            break

    print("Robot stopped.")


def start_robot():
    """if the robot is not already running, start it in a new thread and return True. Otherwise, return False."""
    global robot_thread
    if robot_thread and robot_thread.is_alive():
        return False

    stop_event.clear()
    del conversation[1:] 
    robot_thread = threading.Thread(target=robot_loop, daemon=True)
    robot_thread.start()
    return True


def stop_robot():
    stop_event.set()
