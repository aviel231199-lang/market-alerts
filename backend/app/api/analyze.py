from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ..ai.analyzer import fetch_and_analyze, get_latest_filings, translate_to_hebrew
from ..models import User
from ..security import current_user

router = APIRouter(prefix="/analyze", tags=["AI Analysis"])


class TranslateIn(BaseModel):
    text: str
    texts: list[str] | None = None  # batch


@router.get("/filings/{ticker}")
async def list_filings(
    ticker: str,
    form_type: str = Query("10-Q", description="10-K | 10-Q | 8-K"),
    _: User = Depends(current_user),
) -> list[dict]:
    """List recent SEC filings for a ticker."""
    filings = await get_latest_filings(ticker.upper(), [form_type])
    if not filings:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No {form_type} filings found for {ticker.upper()}")
    return filings


@router.get("/report/{ticker}")
async def analyze_report(
    ticker: str,
    form_type: str = Query("10-Q", description="10-K | 10-Q | 8-K"),
    _: User = Depends(current_user),
) -> dict:
    """Fetch the latest SEC filing for a ticker and return AI-powered analysis."""
    result = await fetch_and_analyze(ticker.upper(), form_type)
    if "error" in result:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, result["error"])
    return result


@router.post("/translate")
async def translate(
    data: TranslateIn,
    _: User = Depends(current_user),
) -> dict:
    """Translate financial text to Hebrew. Accepts single text or batch of texts."""
    if data.texts:
        # batch — translate all concurrently
        import asyncio
        translations = await asyncio.gather(*[translate_to_hebrew(t) for t in data.texts[:20]])
        return {"translations": list(translations)}
    translated = await translate_to_hebrew(data.text)
    return {"translation": translated}
