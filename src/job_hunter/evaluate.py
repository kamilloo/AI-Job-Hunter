import re

from job_hunter.models import Job, Match, Eligibility, EligibilityFactors
from job_hunter.classify_remote import classify_remote
from job_hunter.classify_location import classify_location
ROLE = re.compile(
    r"(backend|back.end|software engineer|php|platform|"
    r"reliability|sre|integration|product engineer|"
    r"data engineer|ai engineer|solutions engineer|"
    r"developer team lead)",
    re.I,
)
REMOTE = re.compile(r"\b(remote|distributed|work from anywhere)\b", re.I)
POLAND = re.compile(r"\b(poland|polska|polish|emea|europe|european union|\beu\b|\beea\b|worldwide|anywhere)\b", re.I)
EXCLUDE_LOC = re.compile(r"\b(united states only|us only|usa only|canada only|uk only|united kingdom only|north america only)\b", re.I)
HYBRID = re.compile(r"\b(hybrid|on.site|onsite|in.office|office attendance|days? (?:per|a) week in (?:the )?office)\b", re.I)
MANAGEMENT_REQUIRED = re.compile(
    r"\b("
    r"people management|"
    r"people-manager|"
    r"direct reports|"
    r"performance reviews|"
    r"performance management|"
    r"line management"
    r")\b",
    re.I,
)
def evaluate(job: Job, profile: dict) -> Match:
    text = f"{job.title} {job.description}".lower()
    loc = job.location.lower()
    reasons, concerns, evidence = [], [], []
    rejected = False
    if not ROLE.search(job.title):
        concerns.append("Title outside target engineering roles")
        rejected = True
    if any(x.lower() in job.company.lower() for x in profile.get("skipped_companies", [])):
        concerns.append("Previously skipped company; requires material change")
        rejected = True
    if any(x in job.title.lower() for x in ["wordpress", "woocommerce", "frontend", "front-end"]):
        concerns.append("Excluded specialty or frontend-first role")
        rejected = True
    if EXCLUDE_LOC.search(f"{loc} {job.description}") or HYBRID.search(loc):
        concerns.append("Explicit location restriction or hybrid posting")
        rejected = True
    elif HYBRID.search(job.description):
        concerns.append("Office / hybrid language in description; manual verification needed")
    location_supported = bool(POLAND.search(loc) or POLAND.search(job.description))
    location_eligibility = classify_location(job.location, job.description)
    if location_eligibility == Eligibility.rejected:
        rejected = True
        concerns.append("Location restriction excludes candidates based in Poland")
    elif location_eligibility == Eligibility.review:
        concerns.append("Location eligibility requires verification")
    remote_claim = bool(job.remote is True or REMOTE.search(loc) or REMOTE.search(job.description))
    remote_eligibility = classify_remote(
        remote=job.remote,
        remote_claim=remote_claim,
        description=job.description,
    )

    if remote_eligibility == Eligibility.rejected:
        rejected = True
        concerns.append("Mandatory office attendance or nonremote requirement")

    elif remote_eligibility == Eligibility.review:
        concerns.append("Remote eligibility requires verification")

    if not location_supported:
        concerns.append("Poland eligibility not established")
    if not remote_claim:
        concerns.append("Full remote requirement not established")
    if not job.verified_live:
        concerns.append("Live official application endpoint not yet verified")
    tech_hits = [s for s in profile.get("core_skills", []) if re.search(r"(?<!\w)" + re.escape(s.lower()) + r"(?!\w)", text)]
    if tech_hits:
        reasons.append("Relevant stack: " + ", ".join(tech_hits[:8]))
        evidence.extend(tech_hits[:8])
    else:
        concerns.append("No explicit core stack overlap in description")
    if re.search(r"\b(senior|staff|lead)\b", job.title, re.I):
        reasons.append("Seniority aligns with experience")
    for flag in profile.get("culture_flags", []):
        if flag.lower() in text:
            concerns.append("Culture caution: " + flag)

    management_review = bool(
        re.search(r"\b(team lead|engineering manager)\b", job.title, re.I)
        and MANAGEMENT_REQUIRED.search(job.description)
    )

    if management_review:
        concerns.append(
            "Formal people-management responsibilities require verification"
        )

    transition = bool(re.search(r"\b(ai|llm|agent|platform|reliability|sre|data)\b", text))
    ai_score = min(100, 35 + (35 if transition else 0) + (15 if tech_hits else 0))
    score = min(100, 20 + 6 * min(len(tech_hits), 8) + (15 if "senior" in job.title.lower() else 0) + (10 if location_supported and remote_claim else 0))

    if rejected or remote_eligibility == Eligibility.rejected:
        eligibility = Eligibility.rejected

    elif (
            remote_eligibility == Eligibility.review
            or location_eligibility == Eligibility.review
            or management_review
            or not location_supported
            or not job.verified_live
    ):
        eligibility = Eligibility.review

    else:
        eligibility = Eligibility.eligible

    return Match(key=job.key, eligibility=eligibility, score=score, ai_transition_score=ai_score,
                 reasons=reasons, concerns=concerns, evidence=evidence)

def aggregate_eligibility(factors: EligibilityFactors) -> Eligibility:
    values = [
        factors.location,
        factors.remote,
        factors.technical,
        factors.compensation,
        factors.ats,
    ]

    if Eligibility.rejected in values:
        return Eligibility.rejected

    if Eligibility.review in values:
        return Eligibility.review

    return Eligibility.eligible

