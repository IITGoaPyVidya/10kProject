"""YouTube transcript retrieval via the video's existing captions (manual or auto-generated)."""
import re
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import (
    IpBlocked, NoTranscriptFound, RequestBlocked, TranscriptsDisabled, VideoUnavailable,
    YouTubeTranscriptApi, YouTubeTranscriptApiException,
)

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
_MARK_EVERY_S = 60  # insert a [TIME mm:ss] marker roughly every minute for citations
_DISPLAY_EVERY_S = 30  # one timestamp per ~30s block in the displayed transcript


def extract_video_id(url: str) -> str:
    """Return the 11-char video id from a YouTube URL; raises ValueError otherwise."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or host not in _HOSTS:
        raise ValueError("Enter a valid YouTube link.")
    if host == "youtu.be":
        vid = parsed.path.lstrip("/").split("/")[0]
    elif parsed.path == "/watch":
        vid = parse_qs(parsed.query).get("v", [""])[0]
    else:
        m = re.match(r"^/(?:shorts|embed|live|v)/([^/?]+)", parsed.path)
        vid = m.group(1) if m else ""
    if not _ID_RE.match(vid):
        raise ValueError("Could not find a video id in that YouTube link.")
    return vid


def _stamp(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def fetch_transcript(video_id: str, languages: tuple[str, ...] = ("en", "en-US", "en-GB", "en-IN")) -> dict:
    """Fetch captions and return {text, display, segments, duration_s}.

    `text` (periodic [TIME] markers) feeds the analyzers; `display` has one timestamp per ~30s block.
    """
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=list(languages))
    except TranscriptsDisabled:
        raise ValueError("This video has captions disabled, so no transcript is available.")
    except NoTranscriptFound:
        raise ValueError("No English transcript found for this video.")
    except VideoUnavailable:
        raise ValueError("Video is unavailable (private, removed, or region-locked).")
    except (IpBlocked, RequestBlocked):
        raise ValueError("YouTube blocked the transcript request from this server's IP. Try again later.")
    except YouTubeTranscriptApiException as exc:
        raise ValueError(f"Could not retrieve transcript: {type(exc).__name__}")

    lines: list[str] = []
    blocks: list[tuple[float, list[str]]] = []
    next_mark = 0.0
    last_end = 0.0
    count = 0
    for snip in fetched:
        count += 1
        clean = snip.text.replace("\n", " ").strip()
        if not blocks or snip.start >= blocks[-1][0] + _DISPLAY_EVERY_S:
            blocks.append((snip.start, []))
        blocks[-1][1].append(clean)
        if snip.start >= next_mark:
            lines.append(f"\n[TIME {_stamp(snip.start)}]")
            next_mark = snip.start + _MARK_EVERY_S
        lines.append(clean)
        last_end = snip.start + snip.duration
    text = " ".join(lines).replace(" \n", "\n").strip()
    display = "\n\n".join(f"[{_stamp(start)}] {' '.join(parts)}" for start, parts in blocks)
    return {"text": text, "display": display, "segments": count, "duration_s": int(last_end)}
