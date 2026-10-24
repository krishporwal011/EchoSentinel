import asyncio
import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from virustotal import (
    determine_classification,
    encode_url_id,
    scan_url_with_virustotal,
    validate_url,
)

client = TestClient(app)


# 1. Valid URL Test
def test_valid_url():
    assert validate_url("https://example.com") == "https://example.com"
    assert validate_url("http://sub.domain.co.uk/path?q=1") == "http://sub.domain.co.uk/path?q=1"
    assert validate_url("   https://test.org/   ") == "https://test.org/"


# 2. Invalid URL Test
def test_invalid_url():
    with pytest.raises(ValueError, match="non-empty"):
        validate_url("")
    with pytest.raises(ValueError, match="whitespace"):
        validate_url("https://example .com")
    with pytest.raises(ValueError, match="hostname"):
        validate_url("https://")
    with pytest.raises(ValueError, match="maximum allowed length"):
        validate_url("https://example.com/" + ("a" * 2050))


# 3. Unsupported URL Scheme Test
def test_unsupported_url_scheme():
    with pytest.raises(ValueError, match="Only HTTP and HTTPS"):
        validate_url("ftp://example.com/file")
    with pytest.raises(ValueError, match="Only HTTP and HTTPS"):
        validate_url("file:///etc/passwd")
    with pytest.raises(ValueError, match="Only HTTP and HTTPS"):
        validate_url("javascript:alert(1)")


# 4. Missing API Key Test
def test_missing_api_key():
    async def _test():
        with patch.dict(os.environ, {"VIRUSTOTAL_API_KEY": ""}, clear=False):
            res = await scan_url_with_virustotal("https://example.com", api_key="")
            assert res.status == "error"
            assert res.classification == "scan_error"
            assert "VirusTotal API key is not configured" in res.message

    asyncio.run(_test())


# 5. Existing Report Test
def test_existing_report():
    async def _test():
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "data": {
                        "attributes": {
                            "last_analysis_stats": {
                                "harmless": 72,
                                "malicious": 0,
                                "suspicious": 0,
                                "undetected": 18,
                            }
                        }
                    }
                },
            )
        )
        async with httpx.AsyncClient(transport=mock_transport) as http_client:
            res = await scan_url_with_virustotal(
                "https://example.com",
                api_key="dummy-test-key",
                client=http_client,
            )
            assert res.status == "completed"
            assert res.classification == "no_threats_detected"
            assert res.stats.harmless == 72
            assert res.stats.malicious == 0
            assert "No threats were detected" in res.message

    asyncio.run(_test())


# 6 & 7. URL Not Found & Submission Test
def test_url_not_found_and_submission():
    async def _test():
        def handler(request: httpx.Request):
            if request.method == "GET" and "/urls/" in str(request.url):
                return httpx.Response(404, json={"error": {"code": "NotFoundError"}})
            if request.method == "POST" and "/urls" in str(request.url):
                return httpx.Response(200, json={"data": {"id": "u-analysis-12345", "type": "analysis"}})
            if request.method == "GET" and "/analyses/u-analysis-12345" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "attributes": {
                                "status": "completed",
                                "stats": {"harmless": 50, "malicious": 0, "suspicious": 0, "undetected": 10},
                            }
                        }
                    },
                )
            return httpx.Response(500)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            res = await scan_url_with_virustotal(
                "https://newsite.com",
                api_key="dummy-test-key",
                client=http_client,
            )
            assert res.status == "completed"
            assert res.classification == "no_threats_detected"
            assert res.analysis_id == "u-analysis-12345"

    asyncio.run(_test())


# 8. Completed Analysis Test
def test_completed_analysis():
    stats = {"harmless": 60, "malicious": 0, "suspicious": 0, "undetected": 5}
    classification, msg, parsed = determine_classification(stats)
    assert classification == "no_threats_detected"
    assert parsed.harmless == 60


# 9. Pending Analysis Test
def test_pending_analysis():
    async def _test():
        def handler(request: httpx.Request):
            if request.method == "GET" and "/urls/" in str(request.url):
                return httpx.Response(404, json={"error": {"code": "NotFoundError"}})
            if request.method == "POST" and "/urls" in str(request.url):
                return httpx.Response(200, json={"data": {"id": "u-analysis-pending", "type": "analysis"}})
            if request.method == "GET" and "/analyses/" in str(request.url):
                return httpx.Response(
                    200,
                    json={"data": {"attributes": {"status": "queued"}}},
                )
            return httpx.Response(500)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            with patch("virustotal.POLL_INTERVAL_SECONDS", 0.01), patch("virustotal.MAX_POLL_ATTEMPTS", 2):
                res = await scan_url_with_virustotal(
                    "https://pendingsite.com",
                    api_key="dummy-test-key",
                    client=http_client,
                )
                assert res.status == "pending"
                assert res.classification == "analysis_pending"
                assert "queued or in progress" in res.message

    asyncio.run(_test())


# 10. Malicious Result Test
def test_malicious_result():
    classification, msg, stats = determine_classification({"malicious": 14, "harmless": 20})
    assert classification == "malicious"
    assert stats.malicious == 14
    assert "Flagged as malicious by 14 security vendors" in msg


# 11. Suspicious Result Test
def test_suspicious_result():
    classification, msg, stats = determine_classification({"malicious": 0, "suspicious": 4, "harmless": 20})
    assert classification == "suspicious"
    assert stats.suspicious == 4
    assert "Flagged as suspicious by 4 security vendors" in msg


# 12. Zero-Detection Result Test
def test_zero_detection_result():
    classification, msg, stats = determine_classification({"malicious": 0, "suspicious": 0, "harmless": 75, "undetected": 15})
    assert classification == "no_threats_detected"
    assert msg == "No threats were detected by the available checks. This does not guarantee that the URL is safe."


# 13. Missing Statistics Test
def test_missing_statistics():
    classification, msg, stats = determine_classification({})
    assert classification == "unknown"
    assert msg == "No usable threat report is currently available."
    assert stats.malicious is None
    assert stats.harmless is None


# 14. Authentication Failure Test (401/403)
def test_authentication_failure():
    async def _test():
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(401, json={"error": {"code": "WrongCredentialsError"}})
        )
        async with httpx.AsyncClient(transport=mock_transport) as http_client:
            res = await scan_url_with_virustotal(
                "https://example.com",
                api_key="invalid-key",
                client=http_client,
            )
            assert res.status == "error"
            assert res.classification == "scan_error"
            assert "authentication failed" in res.message.lower()

    asyncio.run(_test())


# 15. Rate Limiting Test (429)
def test_rate_limiting():
    async def _test():
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(429, json={"error": {"code": "QuotaExceededError"}})
        )
        async with httpx.AsyncClient(transport=mock_transport) as http_client:
            res = await scan_url_with_virustotal(
                "https://example.com",
                api_key="dummy-key",
                client=http_client,
            )
            assert res.status == "error"
            assert res.classification == "scan_error"
            assert "quota exceeded" in res.message.lower() or "rate limit" in res.message.lower()

    asyncio.run(_test())


# 16. Timeout Test
def test_timeout_handling():
    async def _test():
        def timeout_handler(request: httpx.Request):
            raise httpx.ReadTimeout("Timed out connecting to VirusTotal")

        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as http_client:
            res = await scan_url_with_virustotal(
                "https://example.com",
                api_key="dummy-key",
                client=http_client,
            )
            assert res.status == "error"
            assert res.classification == "scan_error"
            assert "timed out" in res.message.lower()

    asyncio.run(_test())


# 17. Malformed API Response Test
def test_malformed_api_response():
    async def _test():
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, text="NOT_VALID_JSON{{{")
        )
        async with httpx.AsyncClient(transport=mock_transport) as http_client:
            res = await scan_url_with_virustotal(
                "https://example.com",
                api_key="dummy-key",
                client=http_client,
            )
            assert res.status == "error"
            assert res.classification == "scan_error"
            assert "malformed" in res.message.lower()

    asyncio.run(_test())


# 18. FastAPI Endpoint End-to-End Test
def test_fastapi_scan_url_endpoint():
    with patch("main.scan_url_with_virustotal", new_callable=AsyncMock) as mock_scan:
        from virustotal import ScanUrlResponse, UrlStats

        mock_scan.return_value = ScanUrlResponse(
            status="completed",
            classification="no_threats_detected",
            url="https://google.com",
            stats=UrlStats(malicious=0, suspicious=0, harmless=80, undetected=10),
            provider="VirusTotal",
            analysis_id=None,
            report_url="https://www.virustotal.com/gui/url/aHR0cHM6Ly9nb29nbGUuY29t",
            message="No threats were detected by the available checks. This does not guarantee that the URL is safe.",
        )

        resp = client.post("/api/scan-url", json={"url": "https://google.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["classification"] == "no_threats_detected"
        assert data["stats"]["harmless"] == 80
        assert data["provider"] == "VirusTotal"
