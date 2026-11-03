from job_hunter.models import Job
from bs4 import BeautifulSoup
from html import unescape


def clean_html(value: str | None) -> str:
    return BeautifulSoup(unescape(value or ""), "html.parser").get_text(" ", strip=True)

def normalize(provider: str, slug: str, company: str, payload: dict) -> Job:
    if provider == "greenhouse":
        return Job(provider=provider, board=slug, external_id=str(payload["id"]), company=company,
            title=payload["title"], location=(payload.get("location") or {}).get("name", "Unknown"),
            description=clean_html(payload.get("content")), url=payload["absolute_url"],
            apply_url=payload["absolute_url"], updated_at=payload.get("updated_at"),
            remote=None)
    if provider == "ashby":
        return Job(provider=provider, board=slug,
            external_id=str(payload.get("id") or payload.get("jobUrl") or payload["title"]),
            company=company, title=payload["title"], location=payload.get("location") or "Unknown",
            description=clean_html(payload.get("descriptionHtml") or payload.get("descriptionPlain")),
            url=payload["jobUrl"], apply_url=payload.get("applyUrl") or payload["jobUrl"],
            remote=payload.get("isRemote"), salary_text=str(payload.get("compensation") or "") or None)
    if provider == "lever":
        cats = payload.get("categories") or {}
        return Job(provider=provider, board=slug, external_id=str(payload["id"]), company=company,
            title=payload["text"], location=cats.get("location") or "Unknown",
            description=clean_html(payload.get("descriptionPlain") or payload.get("description") or payload.get("additionalPlain")),
            url=payload["hostedUrl"], apply_url=payload.get("applyUrl") or payload["hostedUrl"])
    raise ValueError(f"Unknown provider: {provider}")
