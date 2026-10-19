import re
from html import unescape
import httpx
from bs4 import BeautifulSoup
from job_hunter.models import Job

SLUG = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")

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

async def collect(client: httpx.AsyncClient, provider: str, slug: str, company: str) -> list[Job]:
    if not SLUG.fullmatch(slug):
        raise ValueError("Invalid board slug")
    urls = {
        "greenhouse": (f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", {"content": "true"}),
        "ashby": (f"https://api.ashbyhq.com/posting-api/job-board/{slug}", {"includeCompensation": "true"}),
        "lever": (f"https://api.lever.co/v0/postings/{slug}", {"mode": "json"}),
    }
    if provider not in urls:
        raise ValueError(f"Unsupported provider: {provider}")
    endpoint, params = urls[provider]
    response = await client.get(endpoint, params=params)
    response.raise_for_status()
    data = response.json()
    rows = data if provider == "lever" else data["jobs"]
    results = []
    for row in rows:
        if provider == "ashby" and row.get("isListed") is False:
            continue
        try:
            results.append(normalize(provider, slug, company, row))
        except (KeyError, ValueError):
            continue
    return results
