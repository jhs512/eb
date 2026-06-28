#!/usr/bin/env python3
"""Excel Brain (eb) — 3개 CSV를 Google 스프레드시트로 동기화 (선택 기능).

CSV가 진실의 원천이고, 시트는 생성되는 뷰다. 각 CSV를 같은 이름의 탭으로 올린다:
  data/nodes.csv -> _data 탭
  data/edges.csv -> _edges 탭
  data/meta.csv  -> _meta 탭

인증(둘 중 하나):
  - GOOGLE_APPLICATION_CREDENTIALS = 서비스 계정 JSON 키 파일 경로
  - GOOGLE_SA_KEY                  = 서비스 계정 JSON 키 내용(문자열, CI용)
대상:
  - SPREADSHEET_ID = 대상 스프레드시트 ID (필수)
탭 이름 override(선택): NODE_TAB / EDGE_TAB / META_TAB

방식: 단순 overwrite — 각 탭을 비우고 CSV 전체를 쓴다. CSV가 원천이라 증분이 불필요.

사용:
  pip install -r requirements.txt
  export GOOGLE_APPLICATION_CREDENTIALS=~/.config/eb/sa-key.json
  export SPREADSHEET_ID=...
  python sync.py --data data            # 동기화
  python sync.py --data data --dry-run  # 계획만(쓰기 없음)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

TABS = [("nodes.csv", "NODE_TAB", "_data"),
        ("edges.csv", "EDGE_TAB", "_edges"),
        ("meta.csv", "META_TAB", "_meta")]


def _read_rows(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.reader(f)]


def _client():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        sys.exit("gspread/google-auth가 필요합니다: pip install -r requirements.txt")

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    raw = os.environ.get("GOOGLE_SA_KEY")
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if raw:
        info = json.loads(raw)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
    elif path:
        creds = Credentials.from_service_account_file(os.path.expanduser(path), scopes=scopes)
    else:
        sys.exit("인증 정보가 없습니다: GOOGLE_SA_KEY 또는 GOOGLE_APPLICATION_CREDENTIALS 설정")
    return gspread.authorize(creds)


def sync(data_dir: str, dry_run: bool = False) -> int:
    base = Path(data_dir)
    plan = []
    for fname, env, default in TABS:
        rows = _read_rows(base / fname)
        tab = os.environ.get(env, default)
        plan.append((tab, fname, rows))
        print(f"{fname} -> '{tab}' 탭: {len(rows)} 행" + (" (헤더 포함)" if rows else " (파일 없음/빈 파일)"))

    if dry_run:
        print("[dry-run] 쓰기 없음.")
        return 0

    sid = os.environ.get("SPREADSHEET_ID")
    if not sid:
        sys.exit("SPREADSHEET_ID 환경변수가 필요합니다.")

    gc = _client()
    sh = gc.open_by_key(sid)
    for tab, fname, rows in plan:
        if not rows:
            continue
        try:
            ws = sh.worksheet(tab)
            ws.clear()
        except Exception:
            ws = sh.add_worksheet(title=tab, rows=max(len(rows) + 10, 20),
                                  cols=max(len(rows[0]) + 2, 10))
        ws.update(rows, value_input_option="RAW")
        print(f"✓ '{tab}' 갱신: {len(rows)} 행")
    print("동기화 완료.")
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog="sync", description="eb CSV -> Google Sheet 동기화")
    p.add_argument("--data", default="data", help="CSV 디렉토리 (기본: data)")
    p.add_argument("--dry-run", action="store_true", help="계획만 출력")
    args = p.parse_args(argv)
    return sync(args.data, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
