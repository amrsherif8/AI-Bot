import re
import shutil
import tempfile
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from messages import AppError

MAX_DURATION = 60 * 60
MAX_BYTES = 150 * 1024 * 1024
MAX_CACHED = 5
CACHE_DIR = Path(tempfile.gettempdir()) / "funke_youtube_audio"

_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
          "youtu.be", "www.youtu.be"}
_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_TYPES = {".m4a": "audio/mp4", ".mp4": "audio/mp4", ".webm": "audio/webm",
          ".opus": "audio/ogg", ".ogg": "audio/ogg", ".mp3": "audio/mpeg"}

_cache = {}
_lock = threading.Lock()
_download_lock = threading.Lock()

shutil.rmtree(CACHE_DIR, ignore_errors=True)


class YoutubeError(AppError):
    status = 400


class YoutubeNotFound(YoutubeError):
    status = 404


class YoutubeUnavailable(YoutubeError):
    status = 503


def video_id(url):
    url = (url or "").strip()
    if not url:
        raise YoutubeError("yt_empty")
    if "://" not in url:
        url = "https://" + url
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except ValueError:
        raise YoutubeError("yt_bad_url") from None
    if parsed.scheme not in ("http", "https") or host not in _HOSTS:
        raise YoutubeError("yt_bad_url")

    parts = [p for p in parsed.path.split("/") if p]
    candidate = ""
    if host.endswith("youtu.be"):
        candidate = parts[0] if parts else ""
    elif parts and parts[0] == "watch":
        candidate = (parse_qs(parsed.query).get("v") or [""])[0]
    elif len(parts) > 1 and parts[0] in ("shorts", "embed", "live", "v"):
        candidate = parts[1]

    if not _ID.match(candidate):
        raise YoutubeError("yt_bad_url")
    return candidate


def _public(entry):
    return {
        "id": entry["id"],
        "title": entry["title"],
        "duration": entry["duration"],
        "audio": f"/youtube/audio/{entry['id']}",
    }


def _cached(vid):
    with _lock:
        entry = _cache.get(vid)
    if entry is not None and Path(entry["path"]).is_file():
        return entry
    return None


def _remember(entry):
    with _lock:
        _cache.pop(entry["id"], None)
        _cache[entry["id"]] = entry
        old = []
        while len(_cache) > MAX_CACHED:
            old.append(_cache.pop(next(iter(_cache))))
    for item in old:
        try:
            Path(item["path"]).unlink()
        except OSError:
            pass


def _download(yt_dlp, vid):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    link = f"https://www.youtube.com/watch?v={vid}"
    options = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 2,
        "max_filesize": MAX_BYTES,
        "outtmpl": str(CACHE_DIR / "%(id)s.%(ext)s"),
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(link, download=False)
            if info.get("is_live") or info.get("duration") is None:
                raise YoutubeError("yt_live")
            duration = int(info["duration"])
            if duration > MAX_DURATION:
                raise YoutubeError("yt_too_long", max=MAX_DURATION // 60)
            ydl.download([link])
    except YoutubeError:
        raise
    except Exception as error:
        print("YouTube error:", error)
        raise YoutubeUnavailable("yt_failed") from None

    files = [p for p in CACHE_DIR.glob(f"{vid}.*") if p.suffix.lower() in _TYPES]
    if not files:
        print("YouTube error: no audio file was written to", CACHE_DIR)
        raise YoutubeUnavailable("yt_failed")
    return {
        "id": vid,
        "title": str(info.get("title") or vid),
        "duration": duration,
        "path": str(files[0]),
    }


def prepare(url):
    vid = video_id(url)
    entry = _cached(vid)
    if entry is not None:
        return _public(entry)

    try:
        import yt_dlp
    except ImportError:
        raise YoutubeUnavailable("yt_needs_ytdlp") from None

    with _download_lock:
        entry = _cached(vid)
        if entry is None:
            entry = _download(yt_dlp, vid)
            _remember(entry)
    return _public(entry)


def audio_file(vid):
    entry = _cached(vid) if _ID.match(vid or "") else None
    if entry is None:
        raise YoutubeNotFound("yt_not_found")
    path = Path(entry["path"])
    return path, _TYPES.get(path.suffix.lower(), "application/octet-stream")


if __name__ == "__main__":
    import sys

    link = sys.argv[1] if len(sys.argv) > 1 else input("YouTube link: ")
    try:
        result = prepare(link)
        print(result["title"], f"({result['duration']} s)")
        print(audio_file(result["id"])[0])
    except YoutubeError as error:
        print(error)
