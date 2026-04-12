"""
Smart content analyser.

Given raw decoded data from the scanner, this module:
  1. Classifies the content type (URL, product barcode, wifi, contact, …)
  2. Performs an internet lookup / safety check
  3. Returns a structured AnalysisReport
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Content-type classification patterns
# ---------------------------------------------------------------------------

_WIFI_RE = re.compile(r"^WIFI:", re.IGNORECASE)
_VCARD_RE = re.compile(r"^BEGIN:VCARD", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^mailto:", re.IGNORECASE)
_PHONE_RE = re.compile(r"^tel:", re.IGNORECASE)
_GEO_RE = re.compile(r"^geo:", re.IGNORECASE)
_CRYPTO_RE = re.compile(
    r"^(bitcoin|ethereum|litecoin|monero|ripple|stellar):", re.IGNORECASE
)
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
# EAN-8, EAN-13, UPC-A patterns
_EAN_RE = re.compile(r"^\d{8}$|^\d{12}$|^\d{13}$")


def classify(raw: str) -> str:
    """Return a simple content-type string."""
    if _URL_RE.match(raw):
        return "url"
    if _WIFI_RE.match(raw):
        return "wifi"
    if _VCARD_RE.match(raw):
        return "contact"
    if _EMAIL_RE.match(raw):
        return "email"
    if _PHONE_RE.match(raw):
        return "phone"
    if _GEO_RE.match(raw):
        return "geo"
    if _CRYPTO_RE.match(raw):
        return "crypto"
    if _EAN_RE.match(raw):
        return "product"
    return "text"


# ---------------------------------------------------------------------------
# Structured result
# ---------------------------------------------------------------------------

@dataclass
class AnalysisReport:
    content_type: str
    raw_data: str
    is_safe: Optional[bool] = None
    risk_level: str = "unknown"      # safe | suspicious | dangerous | unknown
    summary: str = ""
    links: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Async HTTP helper
# ---------------------------------------------------------------------------

_SESSION: Optional[aiohttp.ClientSession] = None


async def _get_session() -> aiohttp.ClientSession:
    global _SESSION
    if _SESSION is None or _SESSION.closed:
        _SESSION = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers={"User-Agent": "TelegramCodeBot/1.0"},
        )
    return _SESSION


async def close_session() -> None:
    global _SESSION
    if _SESSION and not _SESSION.closed:
        await _SESSION.close()


# ---------------------------------------------------------------------------
# URL safety check (VirusTotal)
# ---------------------------------------------------------------------------

async def _check_url_virustotal(url: str) -> tuple[bool, str]:
    """
    Returns (is_safe, summary).
    Falls back gracefully when the API key is absent.
    """
    if not settings.VIRUSTOTAL_API_KEY:
        return True, "No safety check configured."

    import base64
    session = await _get_session()
    url_id = base64.urlsafe_b64encode(url.encode()).rstrip(b"=").decode()
    api_url = f"https://www.virustotal.com/api/v3/urls/{url_id}"
    try:
        async with session.get(
            api_url,
            headers={"x-apikey": settings.VIRUSTOTAL_API_KEY},
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                stats = (
                    data.get("data", {})
                    .get("attributes", {})
                    .get("last_analysis_stats", {})
                )
                malicious = stats.get("malicious", 0)
                suspicious = stats.get("suspicious", 0)
                if malicious > 0:
                    return False, f"Detected as malicious by {malicious} scanner(s)."
                if suspicious > 0:
                    return True, f"Flagged as suspicious by {suspicious} scanner(s). Proceed with caution."
                return True, "No threats detected."
            return True, f"VT check returned HTTP {resp.status}."
    except Exception as exc:
        logger.debug("VirusTotal check failed: %s", exc)
        return True, "Safety check unavailable."


# ---------------------------------------------------------------------------
# Product lookup (Open Food Facts + Google fallback)
# ---------------------------------------------------------------------------

async def _lookup_product(barcode: str) -> dict:
    session = await _get_session()
    off_url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    try:
        async with session.get(off_url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("status") == 1:
                    product = data["product"]
                    return {
                        "found": True,
                        "source": "Open Food Facts",
                        "name": product.get("product_name", "Unknown"),
                        "brand": product.get("brands", ""),
                        "categories": product.get("categories", ""),
                        "image_url": product.get("image_url", ""),
                        "nutriscore": product.get("nutriscore_grade", ""),
                    }
    except Exception as exc:
        logger.debug("OFF lookup failed: %s", exc)

    # Fallback: Google search
    search_result = await _google_search(f"product barcode {barcode}")
    return {"found": bool(search_result), "source": "Google", "results": search_result}


# ---------------------------------------------------------------------------
# Google / SerpAPI search
# ---------------------------------------------------------------------------

async def _google_search(query: str, num: int = 5) -> list[dict]:
    """Return a list of {title, link, snippet} dicts."""
    session = await _get_session()

    # Try SerpAPI first
    if settings.SERP_API_KEY:
        try:
            async with session.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": settings.SERP_API_KEY,
                    "num": num,
                    "engine": "google",
                },
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    organic = data.get("organic_results", [])
                    return [
                        {
                            "title": r.get("title", ""),
                            "link": r.get("link", ""),
                            "snippet": r.get("snippet", ""),
                        }
                        for r in organic[:num]
                    ]
        except Exception as exc:
            logger.debug("SerpAPI search failed: %s", exc)

    # Try Google Custom Search API
    if settings.GOOGLE_API_KEY and settings.GOOGLE_CSE_ID:
        try:
            async with session.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": settings.GOOGLE_API_KEY,
                    "cx": settings.GOOGLE_CSE_ID,
                    "q": query,
                    "num": num,
                },
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("items", [])
                    return [
                        {
                            "title": i.get("title", ""),
                            "link": i.get("link", ""),
                            "snippet": i.get("snippet", ""),
                        }
                        for i in items[:num]
                    ]
        except Exception as exc:
            logger.debug("Google CSE search failed: %s", exc)

    return []


# ---------------------------------------------------------------------------
# WiFi credential parser
# ---------------------------------------------------------------------------

def _parse_wifi(raw: str) -> dict:
    params: dict[str, str] = {}
    # WIFI:T:WPA;S:NetworkName;P:Password;;
    for part in raw[5:].split(";"):
        if ":" in part:
            key, _, value = part.partition(":")
            params[key.strip().upper()] = value.strip()
    return {
        "ssid": params.get("S", ""),
        "password": params.get("P", ""),
        "security": params.get("T", "WPA"),
        "hidden": params.get("H", "false").lower() == "true",
    }


# ---------------------------------------------------------------------------
# URL preview
# ---------------------------------------------------------------------------

async def _url_preview(url: str) -> dict:
    session = await _get_session()
    try:
        async with session.get(url, allow_redirects=True, max_redirects=5) as resp:
            final_url = str(resp.url)
            content_type = resp.headers.get("Content-Type", "")
            status = resp.status
            title = ""
            if "text/html" in content_type:
                html = await resp.text(errors="replace")
                # naive title extraction
                match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
                if match:
                    title = match.group(1).strip()[:200]
            return {
                "final_url": final_url,
                "status_code": status,
                "content_type": content_type,
                "page_title": title,
            }
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

async def analyse(raw_data: str, code_type: str = "") -> AnalysisReport:
    """
    Classify and enrich a decoded code value.

    This is the single entry point used by bot handlers and the API.
    """
    content_type = classify(raw_data)
    report = AnalysisReport(content_type=content_type, raw_data=raw_data)

    try:
        if content_type == "url":
            parsed = urlparse(raw_data)
            report.extra["domain"] = parsed.netloc

            # Safety check + preview in parallel
            safety_task = asyncio.create_task(_check_url_virustotal(raw_data))
            preview_task = asyncio.create_task(_url_preview(raw_data))
            (is_safe, safety_msg), preview = await asyncio.gather(safety_task, preview_task)

            report.is_safe = is_safe
            report.risk_level = "safe" if is_safe else "dangerous"
            report.extra["safety"] = safety_msg
            report.extra["preview"] = preview
            report.summary = (
                f"🔗 *URL detected*\n"
                f"Domain: `{parsed.netloc}`\n"
                f"Safety: {safety_msg}\n"
                f"Page title: {preview.get('page_title', 'N/A')}"
            )
            report.links = [raw_data]

        elif content_type == "product":
            product_info = await _lookup_product(raw_data)
            report.is_safe = True
            report.risk_level = "safe"
            report.extra["product"] = product_info
            if product_info.get("found"):
                report.summary = (
                    f"📦 *Product found*\n"
                    f"Name: {product_info.get('name', 'N/A')}\n"
                    f"Brand: {product_info.get('brand', 'N/A')}\n"
                    f"Categories: {product_info.get('categories', 'N/A')}\n"
                    f"NutriScore: {product_info.get('nutriscore', 'N/A').upper()}"
                )
            else:
                results = product_info.get("results", [])
                report.summary = f"🔍 Searched for barcode `{raw_data}`."
                report.links = [r["link"] for r in results if r.get("link")]

        elif content_type == "wifi":
            wifi = _parse_wifi(raw_data)
            report.is_safe = True
            report.risk_level = "safe"
            report.extra["wifi"] = wifi
            hidden_label = "Yes" if wifi.get("hidden") else "No"
            report.summary = (
                f"📶 *WiFi credentials*\n"
                f"SSID: `{wifi.get('ssid', 'N/A')}`\n"
                f"Security: {wifi.get('security', 'WPA')}\n"
                f"Password: `{wifi.get('password', 'N/A')}`\n"
                f"Hidden: {hidden_label}"
            )

        elif content_type == "contact":
            report.is_safe = True
            report.risk_level = "safe"
            # Simple vCard name extraction
            name_match = re.search(r"FN:(.*)", raw_data)
            email_match = re.search(r"EMAIL[^:]*:(.*)", raw_data)
            tel_match = re.search(r"TEL[^:]*:(.*)", raw_data)
            report.extra["vcard"] = {
                "name": name_match.group(1).strip() if name_match else "",
                "email": email_match.group(1).strip() if email_match else "",
                "phone": tel_match.group(1).strip() if tel_match else "",
            }
            report.summary = (
                f"👤 *Contact card*\n"
                f"Name: {report.extra['vcard']['name'] or 'N/A'}\n"
                f"Email: {report.extra['vcard']['email'] or 'N/A'}\n"
                f"Phone: {report.extra['vcard']['phone'] or 'N/A'}"
            )

        elif content_type == "crypto":
            report.is_safe = True
            report.risk_level = "safe"
            coin, _, address = raw_data.partition(":")
            report.extra["crypto"] = {"coin": coin, "address": address.split("?")[0]}
            report.summary = (
                f"₿ *Crypto address*\n"
                f"Coin: {coin.title()}\n"
                f"Address: `{report.extra['crypto']['address']}`"
            )

        else:
            # Plain text / unknown — do a Google search
            results = await _google_search(raw_data[:200], num=3)
            report.is_safe = True
            report.risk_level = "safe"
            report.extra["search_results"] = results
            report.links = [r["link"] for r in results if r.get("link")]
            snippets = "\n".join(
                f"• [{r['title']}]({r['link']})" for r in results[:3]
            )
            report.summary = (
                f"📄 *Text content*\n"
                f"Content: `{raw_data[:100]}`\n\n"
                f"*Search results:*\n{snippets or 'No results found.'}"
            )

    except Exception as exc:
        logger.exception("Analysis error for %r: %s", raw_data[:50], exc)
        report.error = str(exc)
        report.summary = f"Analysis failed: {exc}"

    return report
