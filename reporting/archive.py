"""Build a filming-safe daily archive without account labels or balance amounts."""
import json
import os
import uuid
from pathlib import Path

from .paths import PRIVATE

ARCHIVE = PRIVATE / "archive"


def _source(sources, key):
    item = sources[key]
    return {
        "label": item["label"],
        "date": item["date"],
        "url": item["url"],
    }


def public_entry(report):
    """Keep analysis and official sources; remove every account-derived amount."""
    c = report["consultation"]
    sources = c["sources"]
    stocks = []
    for card in c["cards"]:
        research = card.get("research")
        if not research:
            continue
        financials = []
        for row in research["financials"]["rows"]:
            financials.append({
                key: row.get(key)
                for key in (
                    "id", "label", "value", "previous", "unit", "period",
                    "comparison", "yoy", "missing_reason"
                )
                if row.get(key) is not None
            } | {"source": _source(sources, row["source"])})
        stocks.append({
            "code": card["code"],
            "name": card["name"],
            "sector": research["sector"],
            "role": research["role"],
            "title": research["title"],
            "thesis": research["thesis"],
            "brief": research["brief"],
            "facts": research["facts"],
            "base": research["base"],
            "up": research["up"],
            "down": research["down"],
            "watch": research["watch"],
            "decision": research["decision"],
            "financial_analysis": research["financials"].get("analysis", "미확인"),
            "financials": financials,
            "sources": [_source(sources, key) for key in research["sources"]],
        })
    news = [{
        "code": item["code"],
        "date": item["date"],
        "title": item["title"],
        "summary": item["summary"],
        "impact": item["impact"],
        "source": _source(sources, item["source"]),
    } for item in c["news"] if item.get("recent")]
    events = [{
        "date": item.get("date"),
        "title": item["title"],
        "watch": item["watch"],
        "status": item["status"],
        "source": _source(sources, item["source"]),
    } for item in c["events"]]
    return {
        "date": c["as_of"],
        "headline": c["headline"],
        "summary": c["summary"],
        "stocks": stocks,
        "news": news,
        "events": events,
        "disclaimer": "개인 확인용 분석이며 매매 추천·목표주가·수익 보장이 아닙니다.",
    }


def save_archive(report, directory=ARCHIVE):
    entry = public_entry(report)
    if not entry["date"]:
        raise ValueError("조사일이 없는 리포트는 일자별 보관함에 저장하지 않습니다.")
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / f'{entry["date"]}.json'
    temporary = directory / f'.{path.name}.{uuid.uuid4().hex}'
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(entry, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def load_archive(directory=ARCHIVE):
    directory = Path(directory)
    if not directory.exists():
        return []
    entries = []
    for path in directory.glob("????-??-??.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            if item.get("date") and isinstance(item.get("stocks"), list):
                entries.append(item)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return sorted(entries, key=lambda item: item["date"], reverse=True)
