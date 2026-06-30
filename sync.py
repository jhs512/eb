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
  python sync.py --data data            # 동기화(CSV -> 시트 overwrite)
  python sync.py --data data --dry-run  # 계획만(쓰기 없음)
  python sync.py --data data --check    # 시트가 CSV와 일치하는지 검사(드리프트 보고, 역기록 없음)

일관성: CSV가 단일 원천이라 동기화는 CSV -> 시트 단방향이다. 시트를 손편집하면
--check 로 드리프트를 감지할 수 있다(역동기화는 하지 않음 — CSV를 고쳐 다시 sync 한다).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

# (파일, 탭이름 override 환경변수, 기본 탭이름, 페이지 분할 여부)
TABS = [("nodes.csv", "NODE_TAB", "_data", True),
        ("edges.csv", "EDGE_TAB", "_edges", True),
        ("meta.csv", "META_TAB", "_meta", False)]

# 한 탭에 데이터(헤더 제외) 최대 행 수. 넘으면 `_data`/`_data2`/… 로 끊어 미러한다.
# Gemini Live 가 시트를 한 번에 다 못 읽고 앞부분만 읽는 경우가 있어, 탭을 짧게 끊고
# CSV `no` 칼럼으로 "no N → 탭 ceil(N/60)" 을 바로 찾게 하려는 것.
ROWS_PER_PAGE = 60


def _pages(tab: str, rows: list, paginate: bool) -> list:
    """rows(헤더+데이터)를 탭 페이지로 나눈다 → [(탭이름, [헤더]+데이터청크), ...].

    paginate=False 이거나 데이터가 ROWS_PER_PAGE 이하면 단일 탭. 2번째부터는
    `<tab>2`, `<tab>3` … (첫 페이지는 접미사 없이 `<tab>`)."""
    if not rows:
        return []
    header, data = rows[0], rows[1:]
    if not paginate or len(data) <= ROWS_PER_PAGE:
        return [(tab, rows)]
    out = []
    for i in range(0, len(data), ROWS_PER_PAGE):
        k = i // ROWS_PER_PAGE
        name = tab if k == 0 else f"{tab}{k + 1}"
        out.append((name, [header] + data[i:i + ROWS_PER_PAGE]))
    return out


def _read_rows(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.reader(f)]


def _norm_rows(rows: list) -> list:
    """후행 빈 셀/빈 행을 제거해 비교를 정규화한다(시트는 빈 칸 패딩이 다름)."""
    out = []
    for r in rows:
        cells = [("" if c is None else str(c)) for c in r]
        while cells and cells[-1].strip() == "":
            cells.pop()
        out.append(cells)
    while out and not out[-1]:
        out.pop()
    return out


def diff_rows(csv_rows: list, sheet_rows: list) -> dict:
    """CSV(원천)와 시트 행을 행 단위로 비교해 드리프트를 보고한다(역기록 없음).

    반환: {only_in_csv:[(i,row)], only_in_sheet:[(i,row)], changed:[(i,csv,sheet)], in_sync:bool}
    """
    c = _norm_rows(csv_rows)
    s = _norm_rows(sheet_rows)
    out = {"only_in_csv": [], "only_in_sheet": [], "changed": []}
    for i in range(max(len(c), len(s))):
        cr = c[i] if i < len(c) else None
        sr = s[i] if i < len(s) else None
        if cr is not None and sr is None:
            out["only_in_csv"].append((i, cr))
        elif cr is None and sr is not None:
            out["only_in_sheet"].append((i, sr))
        elif cr != sr:
            out["changed"].append((i, cr, sr))
    out["in_sync"] = not (out["only_in_csv"] or out["only_in_sheet"] or out["changed"])
    return out


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


def _tab_pattern(tab: str):
    """`<tab>`, `<tab>2`, `<tab>3` … 페이지 탭을 매칭하는 정규식."""
    return re.compile(rf"^{re.escape(tab)}\d*$")


def sync(data_dir: str, dry_run: bool = False) -> int:
    base = Path(data_dir)
    plan = []          # (탭이름, fname, rows) — 페이지 단위
    page_tabs = []     # (기본탭, paginate, [이 기본탭의 desired 페이지 이름들])
    for fname, env, default, paginate in TABS:
        rows = _read_rows(base / fname)
        tab = os.environ.get(env) or default   # 빈 문자열 override도 default로
        pages = _pages(tab, rows, paginate)
        page_tabs.append((tab, paginate, [n for n, _ in pages]))
        for name, chunk in pages:
            plan.append((name, fname, chunk))
        if not rows:
            print(f"{fname} -> '{tab}' 탭: (파일 없음/빈 파일)")
        elif len(pages) == 1:
            print(f"{fname} -> '{tab}' 탭: {len(rows)} 행 (헤더 포함)")
        else:
            print(f"{fname} -> {len(pages)}개 탭으로 분할({ROWS_PER_PAGE}행/탭): "
                  + ", ".join(f"'{n}'({len(c) - 1}행)" for n, c in pages))

    if dry_run:
        print("[dry-run] 쓰기 없음.")
        return 0

    sid = os.environ.get("SPREADSHEET_ID")
    if not sid:
        sys.exit("SPREADSHEET_ID 환경변수가 필요합니다.")

    gc = _client()
    sh = gc.open_by_key(sid)
    existing = {ws.title: ws for ws in sh.worksheets()}
    for tab, fname, rows in plan:
        if not rows:
            continue
        ws = existing.get(tab)
        if ws is not None:
            ws.clear()
        else:
            ws = sh.add_worksheet(title=tab, rows=max(len(rows) + 10, 20),
                                  cols=max(len(rows[0]) + 2, 10))
            existing[tab] = ws
        ws.update(rows, value_input_option="RAW")
        print(f"✓ '{tab}' 갱신: {len(rows)} 행")

    # 데이터가 줄어 더는 필요 없어진 옛 페이지 탭(`_data2` 등)을 정리한다.
    desired = {name for name, _, _ in plan}
    for tab, paginate, names in page_tabs:
        if not paginate:
            continue
        pat = _tab_pattern(tab)
        for title, ws in list(existing.items()):
            if pat.match(title) and title not in desired:
                sh.del_worksheet(ws)
                del existing[title]
                print(f"🗑 스테일 페이지 탭 삭제: '{title}'")
    print("동기화 완료.")
    return 0


def check(data_dir: str) -> int:
    """시트(뷰)가 CSV(원천)와 일치하는지 검사. 손편집/드리프트를 보고만 한다(역기록 없음).

    드리프트가 있으면 1을 반환한다. CSV가 원천이므로 해결책은 'CSV 수정 후 재sync'다.
    """
    base = Path(data_dir)
    sid = os.environ.get("SPREADSHEET_ID")
    if not sid:
        sys.exit("SPREADSHEET_ID 환경변수가 필요합니다.")
    gc = _client()
    sh = gc.open_by_key(sid)
    by_title = {ws.title: ws for ws in sh.worksheets()}
    drift = False
    for fname, env, default, paginate in TABS:
        rows = _read_rows(base / fname)
        if not rows:
            continue
        tab = os.environ.get(env) or default   # 빈 문자열 override도 default로
        pages = _pages(tab, rows, paginate)
        # 페이지 탭들을 이어붙여(헤더는 첫 페이지 것만) 원천 CSV와 비교한다.
        sheet_rows = []
        missing = False
        for k, (name, _chunk) in enumerate(pages):
            ws = by_title.get(name)
            if ws is None:
                print(f"✗ '{name}' 탭 없음 (CSV에는 {len(rows)} 행)")
                drift = True
                missing = True
                break
            vals = ws.get_all_values()
            sheet_rows += vals if k == 0 else vals[1:]   # 둘째 페이지부터 헤더 제거
        if missing:
            continue
        d = diff_rows(rows, sheet_rows)
        if d["in_sync"]:
            print(f"✓ '{tab}' 일치 ({len(rows)} 행)")
            continue
        drift = True
        print(f"✗ '{tab}' 드리프트: CSV에만 {len(d['only_in_csv'])}, "
              f"시트에만 {len(d['only_in_sheet'])}, 변경 {len(d['changed'])}")
        for i, cr, sr in d["changed"][:10]:
            print(f"    행 {i}: CSV={cr} | 시트={sr}")
    if drift:
        print("드리프트 감지: 시트가 원천(CSV)과 다릅니다. CSV를 고쳐 다시 sync 하세요.")
        return 1
    print("시트가 CSV와 일치합니다.")
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
    p.add_argument("--check", action="store_true",
                   help="시트가 CSV와 일치하는지 검사만(역기록 없음). 드리프트면 종료코드 1")
    args = p.parse_args(argv)
    if args.check:
        return check(args.data)
    return sync(args.data, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
