"""AI-powered company report analyzer using Claude + SEC EDGAR."""

from __future__ import annotations

import io
import logging
from typing import Literal

import anthropic
import httpx

from ..config import settings

log = logging.getLogger(__name__)

EDGAR_BASE = "https://data.sec.gov"
HEADERS = {"User-Agent": "MarketAlerts contact@marketalerts.app"}

Language = Literal["he", "en"]

_SYSTEM = """You are a senior financial analyst. Analyze the company filing provided and return a structured JSON response.
Always respond with valid JSON only — no markdown, no extra text."""

_REPORT_PROMPT = """Analyze this SEC filing excerpt and return JSON with these exact fields:
{{
  "ticker": "...",
  "company": "...",
  "report_type": "10-K | 10-Q | 8-K | ...",
  "period": "Q1 2025 / FY2024 / ...",
  "summary": "2-3 sentence executive summary",
  "revenue": {{"value": number_or_null, "currency": "USD", "change_pct": number_or_null}},
  "net_income": {{"value": number_or_null, "currency": "USD", "change_pct": number_or_null}},
  "eps": {{"value": number_or_null, "vs_estimate": number_or_null}},
  "key_highlights": ["bullet 1", "bullet 2", "bullet 3"],
  "risks": ["risk 1", "risk 2"],
  "outlook": "management guidance summary or null",
  "sentiment": "bullish | neutral | bearish",
  "alert_worthy": true_or_false
}}

Filing text:
{text}"""

_TRANSLATE_PROMPT = """Translate the following financial news from English to Hebrew.
Keep ticker symbols (AAPL, NVDA etc.) as-is. Keep numbers as-is. Be concise and professional.

Text: {text}

Return ONLY the Hebrew translation, nothing else."""


def _client() -> anthropic.Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


async def translate_to_hebrew(text: str) -> str:
    """Translate English financial text to Hebrew."""
    if not text or not text.strip():
        return text
    try:
        client = _client()
        msg = await _run_sync(client, _TRANSLATE_PROMPT.format(text=text[:2000]))
        return msg.strip()
    except Exception:
        log.exception("translation failed")
        return text


async def analyze_text(text: str, ticker: str = "") -> dict:
    """Analyze raw report text and return structured insights."""
    client = _client()
    prompt = _REPORT_PROMPT.format(text=text[:8000])
    raw = await _run_sync(client, prompt)
    import json
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "Could not parse AI response", "raw": raw[:500]}


async def _run_sync(client: anthropic.Anthropic, prompt: str) -> str:
    import asyncio
    def _call():
        msg = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    return await asyncio.to_thread(_call)


# ── SEC EDGAR ──────────────────────────────────────────────────────────────

async def _edgar_get(path: str) -> dict | list:
    async with httpx.AsyncClient(headers=HEADERS, timeout=20) as client:
        r = await client.get(f"{EDGAR_BASE}{path}")
        r.raise_for_status()
        return r.json()


async def get_company_cik(ticker: str) -> str | None:
    """Resolve ticker → CIK using EDGAR company tickers JSON."""
    data = await _edgar_get("/files/company_tickers.json")
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    return None


async def get_latest_filings(ticker: str, form_types: list[str] | None = None) -> list[dict]:
    """Return list of recent filings for a ticker."""
    cik = await get_company_cik(ticker)
    if not cik:
        return []
    form_types = form_types or ["10-K", "10-Q", "8-K"]
    data = await _edgar_get(f"/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=&dateb=&owner=include&count=20&search_text=&output=atom")
    # Use submissions endpoint instead — more reliable JSON
    subs = await _edgar_get(f"/submissions/CIK{cik}.json")
    recent = subs.get("filings", {}).get("recent", {})
    results = []
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    descriptions = recent.get("primaryDocument", [])
    for i, form in enumerate(forms):
        if form in form_types:
            acc = accessions[i].replace("-", "")
            results.append({
                "form": form,
                "date": dates[i],
                "accession": accessions[i],
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{descriptions[i]}",
                "ticker": ticker.upper(),
                "cik": cik,
            })
        if len(results) >= 5:
            break
    return results


async def fetch_and_analyze(ticker: str, form_type: str = "10-Q") -> dict:
    """Fetch latest filing of form_type for ticker and return AI analysis."""
    filings = await get_latest_filings(ticker, [form_type])
    if not filings:
        return {"error": f"No {form_type} found for {ticker}"}

    filing = filings[0]
    url = filing["url"]
    log.info("fetching filing ticker=%s form=%s url=%s", ticker, form_type, url)

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")

        if "pdf" in content_type:
            text = _extract_pdf_text(r.content)
        else:
            # HTML/HTM — strip tags
            import re
            text = re.sub(r"<[^>]+>", " ", r.text)
            text = re.sub(r"\s+", " ", text).strip()

    analysis = await analyze_text(text[:8000], ticker)
    analysis["filing"] = filing
    return analysis


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return " ".join(page.extract_text() or "" for page in reader.pages[:20])
    except Exception:
        return ""
