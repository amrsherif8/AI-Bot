# import pandas as pd
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel

import auth
import documents
import math_solver
import speech
import translator
import youtube_audio
try:
    # الروبوت الصوتي بيحتاج ميكروفون وسماعات، فبيشتغل محلياً بس
    from botAI import set_input_language, start_robot, stop_robot
    ROBOT_AVAILABLE = True
except Exception:
    ROBOT_AVAILABLE = False

    def set_input_language(code):
        return code

    def start_robot():
        return False

    def stop_robot():
        pass

from sound import find_sound, list_sounds, play_word

app = FastAPI(
    dependencies=[Depends(auth.require_login)],     # كل الصفحات والـ API محتاجة تسجيل دخول
    docs_url=None, redoc_url=None, openapi_url=None,
)
app.add_middleware(
    SessionMiddleware, secret_key=auth.SECRET_KEY, max_age=60 * 60 * 24 * 7,
    same_site="lax", https_only=auth.ON_RENDER,
)


@app.exception_handler(auth.LoginRedirect)
async def _to_login(request: Request, exc: auth.LoginRedirect):
    return RedirectResponse("/login", status_code=303)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if request.session.get("user") in auth.USERS:
        return RedirectResponse("/", status_code=303)
    return auth.login_page()


@app.post("/login")
def login(request: Request, username: str = Form(""), password: str = Form("")):
    ip = auth.client_ip(request)
    wait = auth.locked_for(ip)
    if wait:
        return HTMLResponse(auth.login_page(f"Too many attempts. Try again in {wait}s."), status_code=429)
    username = username.strip()
    if not auth.check_login(username, password):
        auth.register_fail(ip)
        auth.log("-", "LOGIN FAILED", f"name={username[:40]} ip={ip}")
        return HTMLResponse(auth.login_page("Wrong username or password."), status_code=401)
    auth.clear_fails(ip)
    request.session.clear()
    request.session["user"] = username
    auth.log(username, "LOGIN", f"ip={ip}")
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    user = request.session.get("user")
    request.session.clear()
    if user:
        auth.log(user, "LOGOUT")
    return RedirectResponse("/login", status_code=303)


@app.get("/me")
def me(request: Request):
    return {"user": request.state.user, "admin": auth.is_admin(request.state.user)}


@app.get("/admin", response_class=HTMLResponse, dependencies=[Depends(auth.require_admin)])
def admin_page(user: str = ""):
    import html as _h
    rows = "".join(
        f"<tr><td>{_h.escape(e['time'])}</td><td>{_h.escape(e['user'])}</td>"
        f"<td>{_h.escape(e['action'])}</td><td>{_h.escape(e['detail'])}</td></tr>"
        for e in auth.activity(user or None)
    )
    names = " · ".join(f'<a href="/admin?user={_h.escape(u)}">{_h.escape(u)}</a>' for u in auth.USERS)
    return (
        "<!doctype html><meta charset=utf-8><title>Activity</title>"
        "<style>body{font-family:system-ui;margin:20px}td,th{padding:4px 10px;border-bottom:1px solid #ccc;text-align:left;font-size:14px}</style>"
        f"<h2>Activity</h2><p><a href='/admin'>all</a> · {names} · <a href='/'>app</a></p>"
        f"<table><tr><th>Time</th><th>User</th><th>Action</th><th>Detail</th></tr>{rows}</table>"
    )

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"


class MathRequest(BaseModel):
    expression: str
    operation: str
    variable: Optional[str] = None
    point: Optional[str] = None
    lower: Optional[str] = None
    upper: Optional[str] = None
    lang: str = "de"

class TranslateRequest(BaseModel):
    text: str
    target: str
    source: str = "auto"
    lang: str = "de"


class TranslateCommandRequest(BaseModel):
    command: str
    source: str = "auto"
    lang: str = "de"


class SpeechRequest(BaseModel):
    text: str
    target: str = "de"
    slow: bool = False
    lang: str = "de"


class YoutubeRequest(BaseModel):
    url: str
    lang: str = "de"


class AskRequest(BaseModel):
    doc_id: int
    question: str
    lang: str = "de"
    answer_lang: str = "auto"



@app.get("/")
def home():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/assets/{name}")
def asset(name: str):
    path = ASSETS_DIR / name
    if path.parent != ASSETS_DIR or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)



@app.get("/sounds")
def sounds():
    return list_sounds()


@app.get("/play/{word}")
def play_api(word: str):
    if find_sound(word) is None:
        raise HTTPException(status_code=404, detail="Word not found")
    if not play_word(word):
        raise HTTPException(status_code=503, detail="Audio file not found (Sound_1.mp3 / Sound.mp3)")
    return {"status": "played", "word": word}

@app.get("/hi")
def hi(listen: str = "auto"):
    set_input_language(listen)
    if start_robot():
        return {"status": "robot started"}
    return {"status": "robot is already running"}


@app.get("/robot/listen")
def robot_listen(code: str = "auto"):
    return {"status": "ok", "listen": set_input_language(code)}


@app.get("/bye")
def bye():
    stop_robot()
    return {"status": "robot stopping"}


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


@app.get("/math/plot")
def math_plot(expression: str, var: str = "x", lang: str = "de"):
    try:
        return {"status": "success", "image": math_solver.plot_expression(expression, var)}
    except math_solver.MathError as error:
        raise HTTPException(status_code=400, detail=error.text(lang))


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


@app.post("/translate/command")
def translate_command_api(req: TranslateCommandRequest):
    try:
        return translator.translate_command(req.command, req.source)
    except translator.TranslateError as error:
        raise HTTPException(status_code=400, detail=error.text(req.lang))
    except translator.TranslatorUnavailable as error:
        raise HTTPException(status_code=503, detail=error.text(req.lang))


@app.get("/speech/info")
def speech_info():
    return speech.info()


@app.post("/speech")
def speech_api(req: SpeechRequest):
    try:
        audio = speech.synthesize(req.text, req.target, req.slow)
    except speech.SpeechError as error:
        raise HTTPException(status_code=400, detail=error.text(req.lang))
    except speech.SpeechUnavailable as error:
        raise HTTPException(status_code=503, detail=error.text(req.lang))
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/youtube")
def youtube_api(req: YoutubeRequest):
    try:
        return youtube_audio.prepare(req.url)
    except youtube_audio.YoutubeError as error:
        raise _doc_error(error, req.lang)


@app.get("/youtube/audio/{video_id}")
def youtube_audio_file(video_id: str, lang: str = "de"):
    try:
        path, media_type = youtube_audio.audio_file(video_id)
    except youtube_audio.YoutubeError as error:
        raise _doc_error(error, lang)
    return FileResponse(path, media_type=media_type)


def _doc_error(error, lang):
    return HTTPException(status_code=getattr(error, "status", 400), detail=error.text(lang))


@app.get("/files/info")
def files_info():
    return documents.info()


@app.get("/files")
def files_list():
    return documents.list_documents()


@app.post("/files/upload")
async def files_upload(request: Request, name: str = "file", lang: str = "de"):
    try:
        declared = request.headers.get("content-length")
        if declared and declared.isdigit():
            documents.check_size(int(declared))
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            documents.check_size(len(data))
        return await run_in_threadpool(documents.add_document, name, bytes(data))
    except documents.DocumentError as error:
        raise _doc_error(error, lang)


@app.post("/files/ask")
def files_ask(req: AskRequest):
    try:
        return documents.ask(req.doc_id, req.question, req.answer_lang)
    except documents.DocumentError as error:
        raise _doc_error(error, req.lang)


@app.get("/files/{doc_id}")
def files_get(doc_id: int, lang: str = "de"):
    try:
        return documents.get_document(doc_id)
    except documents.DocumentError as error:
        raise _doc_error(error, lang)


@app.delete("/files/{doc_id}")
def files_delete(doc_id: int, lang: str = "de"):
    try:
        documents.delete_document(doc_id)
        return {"status": "deleted"}
    except documents.DocumentError as error:
        raise _doc_error(error, lang)


@app.delete("/files/{doc_id}/chat")
def files_clear_chat(doc_id: int, lang: str = "de"):
    try:
        documents.clear_chat(doc_id)
        return {"status": "cleared"}
    except documents.DocumentError as error:
        raise _doc_error(error, lang)


@app.post("/translate/document")
async def translate_document_api(request: Request, name: str = "file", target: str = "ar",
                                 source: str = "auto", lang: str = "de"):
    try:
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            documents.check_size(len(data))

        def work():
            text = documents.read_text(name, bytes(data))
            return translator.translate_document(text, target, source)

        return await run_in_threadpool(work)
    except documents.DocumentError as error:
        raise _doc_error(error, lang)
    except translator.TranslateError as error:
        raise HTTPException(status_code=400, detail=error.text(lang))
    except translator.TranslatorUnavailable as error:
        raise HTTPException(status_code=503, detail=error.text(lang))

