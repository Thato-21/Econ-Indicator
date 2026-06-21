from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable

from .domain import Evidence, Horizon


USER_AGENT = "MacroCompass/0.1 local research dashboard"
CACHE_TTL = timedelta(minutes=30)


def _tls_context() -> ssl.SSLContext:
    """Use verified TLS, including MSYS's shared CA bundle when UCRT Python lacks one."""
    paths = ssl.get_default_verify_paths()
    if paths.cafile:
        return ssl.create_default_context()
    for candidate in (Path("C:/msys64/usr/ssl/cert.pem"), Path("C:/msys64/usr/ssl/certs/ca-bundle.crt")):
        if candidate.is_file():
            return ssl.create_default_context(cafile=str(candidate))
    return ssl.create_default_context()


def _request(url: str, *, body: bytes | None = None, timeout: int = 25) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, text/csv, application/xml"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout, context=_tls_context()) as response:
        return response.read()


def _json(url: str, *, body: dict | None = None) -> dict:
    payload = json.dumps(body).encode() if body is not None else None
    return json.loads(_request(url, body=payload))


def _clamp(value: float, low: float = -100, high: float = 100) -> float:
    return max(low, min(high, value))


def _horizon_evidence(
    factor: str,
    scores: dict[Horizon, float],
    confidence: float,
    observed_at: datetime,
    source: str,
    summary: str,
    metadata: dict | None = None,
) -> list[Evidence]:
    return [
        Evidence(
            factor=factor,
            horizon=horizon,
            score=round(score, 2),
            confidence=confidence,
            significance=0.8,
            observed_at=observed_at,
            source=source,
            summary=summary,
            metadata=metadata or {},
        )
        for horizon, score in scores.items()
    ]


def collect_real_yields() -> list[Evidence]:
    year = datetime.now(UTC).year
    urls = [
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"pages/xml?data=daily_treasury_real_yield_curve&field_tdr_date_value={value}"
        for value in (year - 1, year)
    ]
    rows: list[tuple[datetime, float]] = []
    for url in urls:
        root = ET.fromstring(_request(url))
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            props = entry.find(".//{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}properties")
            if props is None:
                continue
            values = {node.tag.split("}")[-1]: node.text for node in props}
            date_text = values.get("NEW_DATE") or values.get("Date")
            yield_text = values.get("TC_10YEAR") or values.get("BC_10YEAR")
            if date_text and yield_text:
                observed = datetime.fromisoformat(date_text.replace("Z", "+00:00"))
                if observed.tzinfo is None:
                    observed = observed.replace(tzinfo=UTC)
                rows.append((observed, float(yield_text)))
    rows.sort(key=lambda item: item[0])
    if len(rows) < 6:
        raise ValueError("Treasury returned insufficient real-yield history")
    latest_date, latest = rows[-1]

    def delta(index: int) -> float:
        return latest - rows[max(0, len(rows) - index)][1]

    scores = {
        Horizon.STRUCTURAL: _clamp(-delta(252) * 70),
        Horizon.INTERMEDIATE: _clamp(-delta(45) * 100),
        Horizon.TACTICAL: _clamp(-delta(10) * 140),
    }
    trend = "falling" if scores[Horizon.INTERMEDIATE] > 0 else "rising"
    return _horizon_evidence(
        "real_yields", scores, 0.95, latest_date, "US Treasury",
        f"10Y real yield {latest:.2f}%, {trend} over the intermediate window",
        {"url": urls[-1], "latest_value": latest, "unit": "percent", "windows": "1y/45d/10d"},
    )


def collect_nominal_yields() -> list[Evidence]:
    year = datetime.now(UTC).year
    urls = [
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value={value}"
        for value in (year - 1, year)
    ]
    rows: list[tuple[datetime, float]] = []
    for url in urls:
        root = ET.fromstring(_request(url))
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            props = entry.find(".//{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}properties")
            if props is None:
                continue
            values = {node.tag.split("}")[-1]: node.text for node in props}
            date_text = values.get("NEW_DATE") or values.get("Date")
            yield_text = values.get("BC_10YEAR")
            if date_text and yield_text:
                observed = datetime.fromisoformat(date_text.replace("Z", "+00:00"))
                if observed.tzinfo is None:
                    observed = observed.replace(tzinfo=UTC)
                rows.append((observed, float(yield_text)))
    rows.sort(key=lambda item: item[0])
    if len(rows) < 6:
        raise ValueError("Treasury returned insufficient nominal-yield history")
    latest_date, latest = rows[-1]

    def score(window: int, multiplier: float) -> float:
        old = rows[max(0, len(rows) - window)][1]
        return _clamp(-(latest - old) * multiplier)

    scores = {
        Horizon.STRUCTURAL: score(252, 50),
        Horizon.INTERMEDIATE: score(45, 70),
        Horizon.TACTICAL: score(10, 95),
    }
    trend = "falling" if scores[Horizon.INTERMEDIATE] > 0 else "rising"
    return _horizon_evidence(
        "nominal_yields", scores, 0.92, latest_date, "US Treasury",
        f"10Y Treasury yield {latest:.2f}%, {trend} over the intermediate window",
        {"url": urls[-1], "latest_value": latest, "unit": "percent", "windows": "1y/45d/10d"},
    )


def collect_fed_policy() -> list[Evidence]:
    url = "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/360.json"
    data = _json(url).get("refRates", [])
    rows = sorted(
        ((datetime.fromisoformat(item["effectiveDate"]).replace(tzinfo=UTC), float(item["percentRate"])) for item in data),
        key=lambda item: item[0],
    )
    if not rows:
        raise ValueError("New York Fed returned no EFFR observations")
    latest_date, latest = rows[-1]
    long_rate = rows[max(0, len(rows) - 252)][1]
    medium_rate = rows[max(0, len(rows) - 45)][1]
    recent = rows[max(0, len(rows) - 10)][1]
    long_score = _clamp(-(latest - long_rate) * 75)
    medium_score = _clamp(-(latest - medium_rate) * 95)
    tactical_score = _clamp(-(latest - recent) * 120)
    scores = {
        Horizon.STRUCTURAL: long_score,
        Horizon.INTERMEDIATE: medium_score,
        Horizon.TACTICAL: tactical_score,
    }
    stance = "easing" if medium_score > 5 else "tightening" if medium_score < -5 else "steady"
    return _horizon_evidence(
        "fed_policy", scores, 0.9, latest_date, "Federal Reserve Bank of New York",
        f"Effective fed funds rate {latest:.2f}%; recent policy rate is {stance}",
        {"url": url, "latest_value": latest, "unit": "percent"},
    )


def collect_usd() -> list[Evidence]:
    url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?range=1y&interval=1d"
    result = _json(url)["chart"]["result"][0]
    closes = [value for value in result["indicators"]["quote"][0]["close"] if value is not None]
    timestamps = result["timestamp"]
    if len(closes) < 7:
        raise ValueError("DXY provider returned insufficient history")
    latest = closes[-1]

    def pct(days: int) -> float:
        previous = closes[max(0, len(closes) - days - 1)]
        return (latest / previous - 1) * 100

    scores = {
        Horizon.STRUCTURAL: _clamp(-pct(250) * 10),
        Horizon.INTERMEDIATE: _clamp(-pct(45) * 17),
        Horizon.TACTICAL: _clamp(-pct(10) * 24),
    }
    date = datetime.fromtimestamp(timestamps[-1], UTC)
    trend = "weakening" if scores[Horizon.INTERMEDIATE] > 0 else "strengthening"
    return _horizon_evidence(
        "usd", scores, 0.9, date, "Yahoo Finance market feed",
        f"DXY {latest:.2f}; dollar is {trend} over the intermediate window",
        {"url": url, "latest_value": latest, "symbol": "DX-Y.NYB"},
    )


def _market_chart(symbol: str, range_: str = "1y") -> tuple[list[float], list[float], list[int], str]:
    encoded = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range={range_}&interval=1d"
    result = _json(url)["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    closes = [value for value in quote["close"] if value is not None]
    volumes = [float(value or 0) for value in quote.get("volume", [])]
    return closes, volumes, result["timestamp"], url


def collect_risk_sentiment() -> list[Evidence]:
    closes, _, timestamps, url = _market_chart("^VIX")
    if len(closes) < 31:
        raise ValueError("VIX provider returned insufficient history")
    latest = closes[-1]

    def pct(days: int) -> float:
        return (latest / closes[max(0, len(closes) - days - 1)] - 1) * 100

    level_component = (latest - 20) * 2
    scores = {
        Horizon.STRUCTURAL: _clamp(level_component * 0.25 + pct(120) * 0.2),
        Horizon.INTERMEDIATE: _clamp(level_component * 0.6 + pct(45) * 0.5),
        Horizon.TACTICAL: _clamp(level_component + pct(10) * 0.85),
    }
    observed = datetime.fromtimestamp(timestamps[-1], UTC)
    mood = "risk-off" if scores[Horizon.TACTICAL] > 8 else "risk-on" if scores[Horizon.TACTICAL] < -8 else "mixed"
    return _horizon_evidence(
        "risk_sentiment", scores, 0.82, observed, "Yahoo Finance market feed",
        f"VIX {latest:.2f}; current market mood is {mood}",
        {"url": url, "latest_value": latest, "symbol": "^VIX"},
    )


def collect_flows_proxy() -> list[Evidence]:
    closes, volumes, timestamps, url = _market_chart("GLD")
    if len(closes) < 31:
        raise ValueError("GLD provider returned insufficient history")
    latest = closes[-1]
    recent_volume = sum(volumes[-5:]) / max(1, len(volumes[-5:]))
    baseline_volume = sum(volumes[-30:]) / max(1, len(volumes[-30:]))
    volume_ratio = recent_volume / baseline_volume if baseline_volume else 1

    def momentum(days: int, multiplier: float) -> float:
        old = closes[max(0, len(closes) - days - 1)]
        change = (latest / old - 1) * 100
        return _clamp(change * multiplier * min(1.5, max(0.7, volume_ratio)))

    scores = {
        Horizon.STRUCTURAL: momentum(250, 4),
        Horizon.INTERMEDIATE: momentum(45, 7),
        Horizon.TACTICAL: momentum(10, 10),
    }
    observed = datetime.fromtimestamp(timestamps[-1], UTC)
    direction = "accumulation" if scores[Horizon.INTERMEDIATE] > 8 else "distribution" if scores[Horizon.INTERMEDIATE] < -8 else "balanced"
    return _horizon_evidence(
        "flows", scores, 0.68, observed, "GLD market proxy via Yahoo Finance",
        f"GLD price-volume momentum indicates {direction}; volume ratio {volume_ratio:.2f}x",
        {"url": url, "latest_value": latest, "symbol": "GLD", "proxy": True, "volume_ratio": volume_ratio},
    )


def collect_bls() -> list[Evidence]:
    now = datetime.now(UTC)
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    data = _json(
        url,
        body={
            "seriesid": ["CUSR0000SA0", "LNS14000000", "CES0000000001"],
            "startyear": str(now.year - 2),
            "endyear": str(now.year),
        },
    )
    series = {item["seriesID"]: item["data"] for item in data["Results"]["series"]}

    def monthly(series_id: str) -> list[tuple[datetime, float]]:
        rows = []
        for item in series[series_id]:
            if item["period"].startswith("M") and item["period"] != "M13" and item["value"] not in ("-", ""):
                rows.append((datetime(int(item["year"]), int(item["period"][1:]), 1, tzinfo=UTC), float(item["value"])))
        return sorted(rows)

    cpi, unemployment, payrolls = monthly("CUSR0000SA0"), monthly("LNS14000000"), monthly("CES0000000001")
    if min(len(cpi), len(unemployment), len(payrolls)) < 13:
        raise ValueError("BLS returned insufficient macro history")
    yoy = (cpi[-1][1] / cpi[-13][1] - 1) * 100
    prior_yoy = (cpi[-2][1] / cpi[-14][1] - 1) * 100
    medium_yoy = (cpi[-4][1] / cpi[-16][1] - 1) * 100
    year_ago_yoy = (cpi[-13][1] / cpi[-25][1] - 1) * 100
    latest_mom_annualized = (cpi[-1][1] / cpi[-2][1] - 1) * 1200
    inflation_momentum = yoy - medium_yoy
    inflation_scores = {
        Horizon.STRUCTURAL: _clamp(-(yoy - year_ago_yoy) * 25 + (yoy - 2) * 4),
        Horizon.INTERMEDIATE: _clamp(-inflation_momentum * 45),
        Horizon.TACTICAL: _clamp(-(latest_mom_annualized - yoy) * 12),
    }
    inflation = _horizon_evidence(
        "inflation", inflation_scores, 0.88, cpi[-1][0], "US Bureau of Labor Statistics",
        f"CPI inflation {yoy:.2f}% YoY; monthly trend {'cooling' if inflation_momentum < 0 else 'firming'}",
        {"url": url, "series": "CUSR0000SA0", "latest_value": yoy, "unit": "percent_yoy"},
    )

    payroll_12m = (payrolls[-1][1] - payrolls[-13][1]) / 12
    payroll_3m = (payrolls[-1][1] - payrolls[-4][1]) / 3
    payroll_latest = payrolls[-1][1] - payrolls[-2][1]
    unemployment_12m = unemployment[-1][1] - unemployment[-13][1]
    unemployment_3m = unemployment[-1][1] - unemployment[-4][1]
    unemployment_latest = unemployment[-1][1] - unemployment[-2][1]
    # Softer employment raises easing/recession support for gold; cap extreme release noise.
    growth_scores = {
        Horizon.STRUCTURAL: _clamp((150 - payroll_12m) / 3 + unemployment_12m * 30),
        Horizon.INTERMEDIATE: _clamp((150 - payroll_3m) / 3 + unemployment_3m * 35),
        Horizon.TACTICAL: _clamp((150 - payroll_latest) / 2.5 + unemployment_latest * 45),
    }
    growth = _horizon_evidence(
        "growth", growth_scores, 0.86, max(unemployment[-1][0], payrolls[-1][0]),
        "US Bureau of Labor Statistics",
        f"Payroll trend {payroll_3m:.0f}k/month; unemployment {unemployment[-1][1]:.1f}%",
        {"url": url, "series": ["CES0000000001", "LNS14000000"]},
    )
    return inflation + growth


def collect_news() -> list[Evidence]:
    query = '(war OR conflict OR sanctions OR military OR ceasefire OR "central bank gold" OR "gold reserves")'
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(
        {"query": query, "mode": "artlist", "maxrecords": 100, "format": "json", "timespan": "3months"}
    )
    source = "GDELT global news index"
    try:
        articles = _json(url).get("articles", [])
        records = []
        for item in articles:
            stamp = item.get("seendate", "")
            try:
                observed = datetime.strptime(stamp[:15], "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
            except ValueError:
                observed = datetime.now(UTC)
            records.append(((item.get("title") or "").lower(), observed))
    except Exception:
        rss_url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": 'war OR sanctions OR ceasefire OR "central bank" gold when:1y', "hl": "en-US", "gl": "US", "ceid": "US:en"}
        )
        rss = ET.fromstring(_request(rss_url))
        items = rss.findall("./channel/item")
        records = []
        for item in items:
            try:
                observed = parsedate_to_datetime(item.findtext("pubDate") or "").astimezone(UTC)
            except (TypeError, ValueError):
                observed = datetime.now(UTC)
            records.append(((item.findtext("title") or "").lower(), observed))
        articles = [{"title": title} for title, _ in records]
        url = rss_url
        source = "Google News RSS (GDELT fallback)"
    headlines = [title for title, _ in records]
    escalation = ("war", "attack", "strike", "invasion", "sanction", "military", "escalat", "missile", "closure", "closed")
    deescalation = ("ceasefire", "peace deal", "truce", "de-escalat", "talks resume")
    now = datetime.now(UTC)

    def geo_for(days: int) -> tuple[float, int, int]:
        selected = [title for title, observed in records if now - observed <= timedelta(days=days)]
        up_count = sum(any(word in title for word in escalation) for title in selected)
        down_count = sum(any(word in title for word in deescalation) for title in selected)
        return _clamp((up_count - down_count * 1.4) * 5), up_count, down_count

    long_geo, long_up, long_down = geo_for(365)
    medium_geo, medium_up, medium_down = geo_for(90)
    tactical_geo, tactical_up, tactical_down = geo_for(14)
    gold_articles = [title for title in headlines if "central bank" in title and ("gold" in title or "reserve" in title)]
    buying = sum(any(word in title for word in ("buy", "purchas", "add", "accumulat", "record")) for title in gold_articles)
    selling = sum(any(word in title for word in ("sell", "reduce", "cut", "decline")) for title in gold_articles)
    demand_score = _clamp((buying - selling) * 18)
    observed = datetime.now(UTC)
    geo = _horizon_evidence(
        "geopolitics",
        {Horizon.STRUCTURAL: long_geo * 0.65, Horizon.INTERMEDIATE: medium_geo * 0.85, Horizon.TACTICAL: tactical_geo},
        min(0.8, 0.35 + len(articles) / 200), observed, source,
        f"{tactical_up} escalation and {tactical_down} de-escalation headlines in the last 14 days",
        {"url": url, "article_count": len(articles), "method": "transparent keyword classifier", "windows": "365d/90d/14d"},
    )
    demand = _horizon_evidence(
        "central_bank_demand",
        {Horizon.STRUCTURAL: demand_score, Horizon.INTERMEDIATE: demand_score * 0.75, Horizon.TACTICAL: demand_score * 0.35},
        min(0.7, 0.3 + len(gold_articles) / 20), observed, source,
        f"{len(gold_articles)} recent central-bank gold/reserve headlines; {buying} buying vs {selling} selling signals",
        {"url": url, "matched_articles": len(gold_articles), "method": "transparent keyword classifier"},
    )
    return geo + demand


COLLECTORS: tuple[Callable[[], list[Evidence]], ...] = (
    collect_real_yields,
    collect_nominal_yields,
    collect_fed_policy,
    collect_usd,
    collect_risk_sentiment,
    collect_flows_proxy,
    collect_bls,
    collect_news,
)


class LiveEvidenceService:
    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path

    def collect(self, force: bool = False) -> tuple[list[Evidence], dict]:
        cached = self._read_cache()
        if cached and not force and datetime.now(UTC) - cached[1] < CACHE_TTL:
            return cached[0], self._status(cached[0], [], "live-cache", cached[1])

        evidence: list[Evidence] = []
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=len(COLLECTORS)) as pool:
            futures = {pool.submit(collector): collector.__name__ for collector in COLLECTORS}
            for future in as_completed(futures):
                try:
                    evidence.extend(future.result())
                except Exception as exc:
                    errors.append(f"{futures[future]}: {exc}")

        # Retain the last good value only for factors whose provider failed this cycle.
        if cached:
            fresh_factors = {item.factor for item in evidence}
            evidence.extend(item for item in cached[0] if item.factor not in fresh_factors)
        if evidence:
            self._write_cache(evidence)
        mode = "live" if not errors else "live-partial"
        return evidence, self._status(evidence, errors, mode, datetime.now(UTC))

    def _status(self, evidence: list[Evidence], errors: list[str], mode: str, fetched_at: datetime) -> dict:
        active = sorted({item.factor for item in evidence})
        return {
            "mode": mode,
            "message": "Latest available public releases and market/news feeds",
            "fetched_at": fetched_at,
            "newest_observation": max((item.observed_at for item in evidence), default=None),
            "active_factors": active,
            "errors": errors,
        }

    def _read_cache(self) -> tuple[list[Evidence], datetime] | None:
        if not self.cache_path.exists():
            return None
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
            evidence = [
                Evidence(
                    **{
                        **item,
                        "horizon": Horizon(item["horizon"]),
                        "observed_at": datetime.fromisoformat(item["observed_at"]),
                    }
                )
                for item in raw["evidence"]
            ]
            return evidence, datetime.fromisoformat(raw["fetched_at"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def _write_cache(self, evidence: list[Evidence]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"fetched_at": datetime.now(UTC), "evidence": [asdict(item) for item in evidence]}
        self.cache_path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
