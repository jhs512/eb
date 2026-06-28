#!/usr/bin/env python3
"""ingest.py — 유튜브/음성·영상을 텍스트(전사)로 바꾸는 선택(optional) 도구.

eb 코어(eb.py)는 stdlib only를 유지한다. 이 도구는 미디어 흡수를 위해 서드파티가
필요하므로 **선택 의존**이다(sync.py 와 같은 위치). eb-learn 스킬이 호출한다:

  python ingest.py "<유튜브 URL>"      # 자막 우선(youtube-transcript-api)
  python ingest.py path/to/audio.mp3   # whisper 로컬 전사(자막 없는 음성/영상)

전사 텍스트를 stdout 으로 출력한다 → eb-learn 이 받아 증류 후 eb.py 로 그래프에 반영.

전략(자막 우선 + whisper 선택):
  - 유튜브 URL → 기존 자막을 가져온다(가볍고 ML 불필요).
  - 음성/영상 파일 → whisper 로 전사(무겁고 선택 설치).
필요한 라이브러리가 없으면 설치 안내를 stderr 로 내고 종료코드 1.

설치(선택):
  pip install -r requirements-ingest.txt   # youtube-transcript-api
  pip install openai-whisper               # 음성 파일 전사 시(+ ffmpeg 필요)
"""
from __future__ import annotations

import argparse
import re
import sys

# 순수 함수(오프라인 테스트 가능) -------------------------------------------- #
_YT_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")
_VIDEO_ID = re.compile(r"(?:v=|/embed/|youtu\.be/|/v/|/shorts/)([A-Za-z0-9_-]{11})")
_SOUND_CUE = re.compile(r"[\[(](?:music|applause|laughter|음악|박수|웃음)[\])]",
                        re.IGNORECASE)
_TIMESTAMP = re.compile(r"\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}")


def is_youtube_url(s: str) -> bool:
    s = (s or "").strip().lower()
    return s.startswith(("http://", "https://")) and any(h in s for h in _YT_HOSTS)


def extract_video_id(url: str):
    """유튜브 URL에서 11자 영상 id를 뽑는다. 못 찾으면 None."""
    m = _VIDEO_ID.search(url or "")
    return m.group(1) if m else None


def clean_transcript(text: str) -> str:
    """전사 텍스트 정리: 음향 큐([Music] 등)·VTT 타임스탬프 제거, 공백 정규화."""
    text = _TIMESTAMP.sub(" ", text or "")
    text = _SOUND_CUE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def segments_to_text(segments) -> str:
    """[{"text": ...}, ...] 형태의 자막 세그먼트를 하나의 정리된 텍스트로."""
    parts = []
    for seg in segments or []:
        t = seg.get("text") if isinstance(seg, dict) else getattr(seg, "text", "")
        if t:
            parts.append(t)
    return clean_transcript(" ".join(parts))


# 어댑터(서드파티, lazy import) --------------------------------------------- #
def fetch_youtube_transcript(video_id: str, languages=None) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise RuntimeError(
            "youtube-transcript-api 가 필요합니다: pip install -r requirements-ingest.txt")
    segments = YouTubeTranscriptApi.get_transcript(
        video_id, languages=languages or ["ko", "en"])
    return segments_to_text(segments)


def transcribe_audio(path: str, model: str = "base") -> str:
    try:
        import whisper
    except ImportError:
        raise RuntimeError(
            "openai-whisper 가 필요합니다: pip install openai-whisper (+ ffmpeg)")
    result = whisper.load_model(model).transcribe(path)
    return clean_transcript(result.get("text", ""))


def ingest(source: str, languages=None, model: str = "base") -> str:
    """소스(유튜브 URL 또는 음성/영상 파일) → 전사 텍스트."""
    if is_youtube_url(source):
        vid = extract_video_id(source)
        if not vid:
            raise RuntimeError(f"유튜브 영상 id를 찾을 수 없습니다: {source}")
        return fetch_youtube_transcript(vid, languages)
    return transcribe_audio(source, model)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog="ingest",
                                description="유튜브/음성·영상 → 전사 텍스트(선택 도구)")
    p.add_argument("source", help="유튜브 URL 또는 음성/영상 파일 경로")
    p.add_argument("--lang", action="append", help="자막 우선 언어(반복 가능, 예: --lang ko --lang en)")
    p.add_argument("--model", default="base", help="whisper 모델(기본 base)")
    args = p.parse_args(argv)
    try:
        print(ingest(args.source, languages=args.lang, model=args.model))
    except RuntimeError as ex:
        print(f"✗ {ex}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
