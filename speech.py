import io
import re

from messages import AppError
from translator import LANGUAGES

MAX_LENGTH = 1500
DEFAULT_LANG = "de"
_CODES = {lang["code"] for lang in LANGUAGES}
AUTO = "auto"
_ARABIC = re.compile("[\u0600-\u06FF]")


class SpeechError(AppError):
    pass


class SpeechUnavailable(AppError):
    pass


def info():
    return {
        "languages": [{"code": l["code"], "label": l["label"]} for l in LANGUAGES],
        "max_length": MAX_LENGTH,
    }


def synthesize(text, lang=DEFAULT_LANG, slow=False):
    text = (text or "").strip()
    if not text:
        raise SpeechError("enter_text")
    if len(text) > MAX_LENGTH:
        raise SpeechError("text_too_long", max=MAX_LENGTH)
    if lang == AUTO:
        lang = "ar" if _ARABIC.search(text) else DEFAULT_LANG
    if lang not in _CODES:
        raise SpeechError("bad_target")

    try:
        from gtts import gTTS
    except ImportError:
        raise SpeechUnavailable("tts_needs_gtts") from None

    buffer = io.BytesIO()
    try:
        gTTS(text=text, lang=lang, slow=bool(slow)).write_to_fp(buffer)
    except (AssertionError, ValueError):
        raise SpeechError("tts_nothing_to_say") from None
    except Exception:
        raise SpeechUnavailable("tts_unavailable") from None

    audio = buffer.getvalue()
    if not audio:
        raise SpeechUnavailable("tts_unavailable")
    return audio


def text_to_speech(text, lang=DEFAULT_LANG, slow=False, output_file="output.mp3"):
    audio = synthesize(text, lang, slow)
    with open(output_file, "wb") as file:
        file.write(audio)
    return f"Saved speech to {output_file}"


if __name__ == "__main__":
    user_text = input("Enter the text: ")
    if user_text.strip():
        try:
            print(text_to_speech(user_text, lang=DEFAULT_LANG, output_file="Sound_1.mp3"))
        except (SpeechError, SpeechUnavailable) as error:
            print(error)
