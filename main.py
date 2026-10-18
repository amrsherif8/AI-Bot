from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import math_solver
import translator
from botAI import start_robot, stop_robot
from sound import find_sound, list_sounds, play_word

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"    # اللوجو والأيقونات (index.html بيطلبهم من /assets/...)


class MathRequest(BaseModel):
    expression: str
    operation: str
    variable: Optional[str] = None
    point: Optional[str] = None
    lower: Optional[str] = None
    upper: Optional[str] = None
    lang: str = "de"        # لغة رسايل الأخطاء: "de" أو "en"


class TranslateRequest(BaseModel):
    text: str
    target: str
    source: str = "auto"
    lang: str = "de"


class TranslateCommandRequest(BaseModel):
    command: str            # مثلاً: "translate to German: good morning"
    source: str = "auto"
    lang: str = "de"


# الواجهة (index.html) لازم تكون جنب main.py
@app.get("/")
def home():
    return FileResponse(BASE_DIR / "index.html")


# اللوجو: ملفات مجلد assets بس، ومفيش خروج منه
@app.get("/assets/{name}")
def asset(name: str):
    path = ASSETS_DIR / name
    if path.parent != ASSETS_DIR or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)


# ---------- الأصوات والروبوت ----------
@app.get("/sounds")
def sounds():
    return list_sounds()


@app.get("/play/{word}")
def play_api(word: str):
    if find_sound(word) is None:
        raise HTTPException(status_code=404, detail="Word not found")
    play_word(word)
    return {"status": "played", "word": word}

@app.get("/hi")
def hi():
    if start_robot():
        return {"status": "robot started"}
    return {"status": "robot is already running"}


@app.get("/bye")
def bye():
    stop_robot()
    return {"status": "robot stopping"}


# ---------- الرياضيات ----------
@app.get("/math/operations")
def math_operations():
    return math_solver.operations_list()


@app.post("/math/solve")
def math_solve(req: MathRequest):
    try:
        return math_solver.solve(
            req.expression, req.operation,
            req.variable, req.point, req.lower, req.upper,
        )
    except math_solver.MathError as error:
        raise HTTPException(status_code=400, detail=error.text(req.lang))


@app.get("/math/history")
def math_history():
    return math_solver.get_history()


@app.delete("/math/history")
def math_history_clear():
    math_solver.clear_history()
    return {"status": "cleared"}


# ---------- الترجمة ----------
@app.get("/translate/languages")
def translate_languages():
    return translator.info()


@app.post("/translate")
def translate_api(req: TranslateRequest):
    try:
        return translator.translate(req.text, req.target, req.source)
    except translator.TranslateError as error:
        raise HTTPException(status_code=400, detail=error.text(req.lang))
    except translator.TranslatorUnavailable as error:
        raise HTTPException(status_code=503, detail=error.text(req.lang))


# نفس أمر الصوت بالظبط، بس مكتوب: "translate to German: good morning"
@app.post("/translate/command")
def translate_command_api(req: TranslateCommandRequest):
    try:
        return translator.translate_command(req.command, req.source)
    except translator.TranslateError as error:
        raise HTTPException(status_code=400, detail=error.text(req.lang))
    except translator.TranslatorUnavailable as error:
        raise HTTPException(status_code=503, detail=error.text(req.lang))
