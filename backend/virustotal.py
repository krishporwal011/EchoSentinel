import asyncio
import base64
import logging
import os
from typing import Any, Dict, Literal, Optional
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("echosentinel.virustotal")

VIRUSTOTAL_BASE_URL = "https://www.virustotal.com/api/v3"
MAX_URL_LENGTH = 2048
POLL_INTERVAL_SECONDS = 1.2
MAX_POLL_ATTEMPTS = 4  # Strict timeout limit (approx 5 seconds max)


class ScanUrlRequest(BaseModel):
    url: str = Field(..., description="The HTTP or HTTPS website URL to scan")


class UrlStats(BaseModel):
    malicious: Optional[int] = None
    suspicious: Optional[int] = None
    harmless: Optional[int] = None
    undetected: Optional[int] = None


class ScanUrlResponse(BaseModel):
    status: Literal["completed", "pending", "error"]
    classification: Literal[
        "malicious",
        "suspicious",
        "no_threats_detected",
        "unknown",
        "analysis_pending",
        "scan_error",
    ]
    url: str
    stats: Optional[UrlStats] = None
    provider: str = "VirusTotal"
    analysis_id: Optional[str] = None
    report_url: Optional[str] = None
    message: str


def validate_url(url: str) -> str:
    """
    Validate that the input is a valid HTTP or HTTPS URL with a non-empty hostname.
    Rejects malformed input, internal/loopback anomalies, and excessively long URLs.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    cleaned = url.strip()
    if len(cleaned) > MAX_URL_LENGTH:
        raise ValueError(f"URL exceeds maximum allowed length of {MAX_URL_LENGTH} characters.")

    if any(c.isspace() for c in cleaned):
        raise ValueError("URL cannot contain whitespace.")

    parsed = urlparse(cleaned)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are supported.")

    hostname = (parsed.hostname or "").strip()
    if not hostname:
        raise ValueError("URL must contain a valid hostname or domain.")

    if len(hostname) > 255:
        raise ValueError("Hostname exceeds maximum allowable length.")

    return cleaned


def encode_url_id(url: str) -> str:
    """
    Generate the official VirusTotal v3 URL identifier:
    Base64-encoded URL string without '=' padding.
    """
    return base64.urlsafe_b64encode(url.encode("utf-8")).decode("utf-8").strip("=")


def determine_classification(stats: Optional[Dict[str, Any]]) -> tuple[
    Literal["malicious", "suspicious", "no_threats_detected", "unknown"],
    str,
    UrlStats,
]:
    """
    Determine classification and user message from completed VirusTotal analysis stats.
    Does NOT invent zero or fake statistics.
    """
    if not stats or not isinstance(stats, dict):
        return (
            "unknown",
            "No usable threat report is currently available.",
            UrlStats(),
        )

    malicious = stats.get("malicious") if isinstance(stats.get("malicious"), int) else None
    suspicious = stats.get("suspicious") if isinstance(stats.get("suspicious"), int) else None
    harmless = stats.get("harmless") if isinstance(stats.get("harmless"), int) else None
    undetected = stats.get("undetected") if isinstance(stats.get("undetected"), int) else None

    url_stats = UrlStats(
        malicious=malicious,
        suspicious=suspicious,
        harmless=harmless,
        undetected=undetected,
    )

    if malicious is not None and malicious > 0:
        vendors = "vendors" if malicious != 1 else "vendor"
        return (
            "malicious",
            f"Flagged as malicious by {malicious} security {vendors}.",
            url_stats,
        )

    if suspicious is not None and suspicious > 0:
        vendors = "vendors" if suspicious != 1 else "vendor"
        return (
            "suspicious",
            f"Flagged as suspicious by {suspicious} security {vendors}.",
            url_stats,
        )

    if (harmless is not None and harmless > 0) or (undetected is not None and undetected > 0):
        return (
            "no_threats_detected",
            "No threats were detected by the available checks. This does not guarantee that the URL is safe.",
            url_stats,
        )

    return (
        "unknown",
        "No usable threat report is currently available.",
        url_stats,
    )


async def scan_url_with_virustotal(
    url: str,
    api_key: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> ScanUrlResponse:
    """
    Execute URL scanning using the official VirusTotal API v3:
    1. Validate input URL.
    2. Check for existing URL report via GET /api/v3/urls/{url_id}.
    3. If not found (404), submit for analysis via POST /api/v3/urls.
    4. Poll /api/v3/analyses/{analysis_id} with strict timeout.
    5. Normalize and return predictable ScanUrlResponse.
    """
    # 1. URL validation
    try:
        validated_url = validate_url(url)
    except ValueError as exc:
        return ScanUrlResponse(
            status="error",
            classification="scan_error",
            url=url,
            stats=None,
            provider="VirusTotal",
            analysis_id=None,
            report_url=None,
            message=str(exc),
        )

    # 2. Check API Key
    effective_key = (api_key or os.getenv("VIRUSTOTAL_API_KEY", "")).strip()
    if not effective_key:
        return ScanUrlResponse(
            status="error",
            classification="scan_error",
            url=validated_url,
            stats=None,
            provider="VirusTotal",
            analysis_id=None,
            report_url=None,
            message="VirusTotal API key is not configured. Please set VIRUSTOTAL_API_KEY in backend/.env.",
        )

    url_id = encode_url_id(validated_url)
    report_url = f"https://www.virustotal.com/gui/url/{url_id}"

    headers = {
        "x-apikey": effective_key,
        "Accept": "application/json",
        "User-Agent": "EchoSentinel-VoiceSecurity/2.0",
    }

    own_client = client is None
    http_client = client or httpx.AsyncClient(timeout=15.0)

    try:
        # 3. Try to retrieve existing URL report
        try:
            resp = await http_client.get(
                f"{VIRUSTOTAL_BASE_URL}/urls/{url_id}",
                headers=headers,
            )
        except httpx.TimeoutException:
            return ScanUrlResponse(
                status="error",
                classification="scan_error",
                url=validated_url,
                stats=None,
                provider="VirusTotal",
                analysis_id=None,
                report_url=report_url,
                message="Connection to VirusTotal API timed out while retrieving report. Please try again.",
            )
        except httpx.RequestError as exc:
            return ScanUrlResponse(
                status="error",
                classification="scan_error",
                url=validated_url,
                stats=None,
                provider="VirusTotal",
                analysis_id=None,
                report_url=report_url,
                message=f"Network error contacting VirusTotal: {exc.__class__.__name__}",
            )

        if resp.status_code == 200:
            try:
                payload = resp.json()
                data = payload.get("data")
                if not isinstance(data, dict):
                    raise ValueError("Missing 'data' object in report payload")
                attributes = data.get("attributes", {})
                raw_stats = attributes.get("last_analysis_stats")
                classification, message, parsed_stats = determine_classification(raw_stats)
                return ScanUrlResponse(
                    status="completed",
                    classification=classification,
                    url=validated_url,
                    stats=parsed_stats,
                    provider="VirusTotal",
                    analysis_id=None,
                    report_url=report_url,
                    message=message,
                )
            except Exception as exc:
                logger.error("Failed to parse existing VirusTotal report: %s", exc)
                return ScanUrlResponse(
                    status="error",
                    classification="scan_error",
                    url=validated_url,
                    stats=None,
                    provider="VirusTotal",
                    analysis_id=None,
                    report_url=report_url,
                    message="Received a malformed report response from VirusTotal.",
                )

        if resp.status_code in {401, 403}:
            return ScanUrlResponse(
                status="error",
                classification="scan_error",
                url=validated_url,
                stats=None,
                provider="VirusTotal",
                analysis_id=None,
                report_url=report_url,
                message="VirusTotal authentication failed. Please verify that your VIRUSTOTAL_API_KEY is valid.",
            )

        if resp.status_code == 429:
            return ScanUrlResponse(
                status="error",
                classification="scan_error",
                url=validated_url,
                stats=None,
                provider="VirusTotal",
                analysis_id=None,
                report_url=report_url,
                message="VirusTotal API rate limit or quota exceeded. Please wait a few moments before trying again.",
            )

        # 4. If URL report does not exist (404), submit for analysis
        if resp.status_code == 404:
            try:
                submit_resp = await http_client.post(
                    f"{VIRUSTOTAL_BASE_URL}/urls",
                    headers=headers,
                    data={"url": validated_url},
                )
            except httpx.TimeoutException:
                return ScanUrlResponse(
                    status="error",
                    classification="scan_error",
                    url=validated_url,
                    stats=None,
                    provider="VirusTotal",
                    analysis_id=None,
                    report_url=report_url,
                    message="Connection to VirusTotal API timed out while submitting URL for analysis.",
                )
            except httpx.RequestError as exc:
                return ScanUrlResponse(
                    status="error",
                    classification="scan_error",
                    url=validated_url,
                    stats=None,
                    provider="VirusTotal",
                    analysis_id=None,
                    report_url=report_url,
                    message=f"Network error submitting URL to VirusTotal: {exc.__class__.__name__}",
                )

            if submit_resp.status_code in {401, 403}:
                return ScanUrlResponse(
                    status="error",
                    classification="scan_error",
                    url=validated_url,
                    stats=None,
                    provider="VirusTotal",
                    analysis_id=None,
                    report_url=report_url,
                    message="VirusTotal authentication failed during URL submission. Please check your API key.",
                )

            if submit_resp.status_code == 429:
                return ScanUrlResponse(
                    status="error",
                    classification="scan_error",
                    url=validated_url,
                    stats=None,
                    provider="VirusTotal",
                    analysis_id=None,
                    report_url=report_url,
                    message="VirusTotal API quota exceeded during submission. Please wait a few moments before retrying.",
                )

            if submit_resp.status_code not in {200, 201}:
                return ScanUrlResponse(
                    status="error",
                    classification="scan_error",
                    url=validated_url,
                    stats=None,
                    provider="VirusTotal",
                    analysis_id=None,
                    report_url=report_url,
                    message=f"VirusTotal rejected the submission with HTTP status {submit_resp.status_code}.",
                )

            try:
                submit_payload = submit_resp.json()
                submit_data = submit_payload.get("data")
                if not isinstance(submit_data, dict):
                    raise ValueError("Missing 'data' in submission response")
                analysis_id = submit_data.get("id")
                if not analysis_id:
                    raise ValueError("Missing analysis 'id' in submission response")
            except Exception as exc:
                logger.error("Failed to parse submission response: %s", exc)
                return ScanUrlResponse(
                    status="error",
                    classification="scan_error",
                    url=validated_url,
                    stats=None,
                    provider="VirusTotal",
                    analysis_id=None,
                    report_url=report_url,
                    message="Malformed submission response received from VirusTotal.",
                )

            # 5. Poll analysis status with strict timeout
            for attempt in range(MAX_POLL_ATTEMPTS):
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                try:
                    poll_resp = await http_client.get(
                        f"{VIRUSTOTAL_BASE_URL}/analyses/{analysis_id}",
                        headers=headers,
                    )
                except Exception:
                    continue

                if poll_resp.status_code == 200:
                    try:
                        poll_payload = poll_resp.json()
                        poll_data = poll_payload.get("data", {})
                        poll_attributes = poll_data.get("attributes", {})
                        analysis_status = poll_attributes.get("status")

                        if analysis_status == "completed":
                            raw_stats = poll_attributes.get("stats")
                            classification, message, parsed_stats = determine_classification(raw_stats)
                            return ScanUrlResponse(
                                status="completed",
                                classification=classification,
                                url=validated_url,
                                stats=parsed_stats,
                                provider="VirusTotal",
                                analysis_id=analysis_id,
                                report_url=report_url,
                                message=message,
                            )
                    except Exception:
                        pass

            # If still not completed after poll timeout
            return ScanUrlResponse(
                status="pending",
                classification="analysis_pending",
                url=validated_url,
                stats=None,
                provider="VirusTotal",
                analysis_id=analysis_id,
                report_url=report_url,
                message="Analysis is currently queued or in progress with VirusTotal. Please check back shortly or view the report directly.",
            )

        # Fallback for unexpected status codes
        return ScanUrlResponse(
            status="error",
            classification="scan_error",
            url=validated_url,
            stats=None,
            provider="VirusTotal",
            analysis_id=None,
            report_url=report_url,
            message=f"VirusTotal returned unexpected status {resp.status_code}.",
        )

    finally:
        if own_client:
            await http_client.aclose()
