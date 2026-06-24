from datetime import date, datetime

import httpx

from app.core.config import settings
from app.services.cache import TTLCache
from app.services.openfda_models import RECALL_SEVERITY, ComplianceFlag, Shortage

_enforcement_cache: TTLCache[list[ComplianceFlag]] = TTLCache(settings.openfda_cache_ttl_seconds)
_shortage_cache: TTLCache[list[Shortage]] = TTLCache(settings.openfda_cache_ttl_seconds)
_label_cache: TTLCache[dict | None] = TTLCache(settings.openfda_cache_ttl_seconds)


def _quote(value: str) -> str:
    return value.replace('"', '\\"')


async def fetch_enforcement(firm_name: str) -> list[ComplianceFlag]:
    """Active/recent recalls for a manufacturer. openFDA /drug/enforcement, cached."""
    cache_key = f"enforcement:{firm_name.lower()}"
    cached = _enforcement_cache.get(cache_key)
    if cached is not None:
        return cached

    flags: list[ComplianceFlag] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{settings.openfda_base_url}/drug/enforcement.json",
            params={"search": f'recalling_firm:"{_quote(firm_name)}"', "limit": 20, "sort": "report_date:desc"},
        )
        if response.status_code == 404:
            _enforcement_cache.set(cache_key, flags)
            return flags
        response.raise_for_status()
        for result in response.json().get("results", []):
            classification = result.get("classification", "")
            flags.append(
                ComplianceFlag(
                    id=result.get("recall_number", result.get("event_id", "")),
                    flag_type="recall",
                    severity=RECALL_SEVERITY.get(classification, "low"),
                    status="active" if result.get("status") == "Ongoing" else "closed",
                    issued_date=result.get("recall_initiation_date"),
                    closed_date=result.get("termination_date"),
                    description=(result.get("reason_for_recall") or result.get("product_description") or "")[:500],
                    source_url=None,
                    affected_products=[result.get("product_description", "")],
                )
            )

    _enforcement_cache.set(cache_key, flags)
    return flags


async def fetch_shortages(generic_name: str) -> list[Shortage]:
    """Active/recent shortages for a drug. openFDA /drug/shortages, cached."""
    cache_key = f"shortages:{generic_name.lower()}"
    cached = _shortage_cache.get(cache_key)
    if cached is not None:
        return cached

    shortages: list[Shortage] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{settings.openfda_base_url}/drug/shortages.json",
            params={"search": f'generic_name:"{_quote(generic_name)}"', "limit": 20},
        )
        if response.status_code == 404:
            _shortage_cache.set(cache_key, shortages)
            return shortages
        response.raise_for_status()
        for result in response.json().get("results", []):
            status_text = (result.get("status") or "").lower()
            shortages.append(
                Shortage(
                    id=result.get("package_ndc", result.get("generic_name", "")),
                    drug_name=result.get("presentation", result.get("generic_name", "")),
                    generic_name=result.get("generic_name", generic_name),
                    status="resolved" if "resolved" in status_text else "active",
                    reason=result.get("related_info"),
                    start_date=result.get("initial_posting_date"),
                    resolved_date=result.get("discontinued_date") if "resolved" in status_text else None,
                    affected_firms=[result.get("company_name", "")] if result.get("company_name") else [],
                    last_checked=date.today(),
                )
            )

    _shortage_cache.set(cache_key, shortages)
    return shortages


async def fetch_label(generic_name: str) -> dict | None:
    """Active/inactive ingredients for a drug. openFDA /drug/label, cached."""
    cache_key = f"label:{generic_name.lower()}"
    if _label_cache.has(cache_key):
        return _label_cache.get(cache_key)

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{settings.openfda_base_url}/drug/label.json",
            params={"search": f'openfda.generic_name:"{_quote(generic_name)}"', "limit": 1},
        )
        if response.status_code == 404:
            _label_cache.set(cache_key, None)
            return None
        response.raise_for_status()
        results = response.json().get("results", [])
        label = results[0] if results else None

    _label_cache.set(cache_key, label)
    return label


def cache_age_seconds(cache_key: str) -> float | None:
    """Used to surface 'compliance data last checked' freshness to the agent/UI."""
    for cache in (_enforcement_cache, _shortage_cache, _label_cache):
        age = cache.age_seconds(cache_key)
        if age is not None:
            return age
    return None
