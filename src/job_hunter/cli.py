import argparse
import asyncio
import json
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
import httpx
import yaml
from job_hunter.collectors.ats import collect_with_diagnostics
from job_hunter.collectors.calculate_discovery_status import calculate_discovery_status
from job_hunter.collectors.verify_detail import verify_detail
from job_hunter.observability import emit_log, make_log_event
from job_hunter.discovery_log_level import discovery_log_level
from job_hunter.evaluate import evaluate
from job_hunter.agents.requirements_agent import assess_requirements, gemini_config
from job_hunter.agent import assess_requirements_agent
from job_hunter.technical_eligibility import grounded_technical_eligibility
from job_hunter.combine_eligibility import combine_eligibility
from job_hunter.models import Job, Eligibility
from job_hunter.describe_source_error import describe_source_error
from job_hunter.safe_identifier import safe_identifier

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]

def db_init(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS jobs (key TEXT PRIMARY KEY, company TEXT, title TEXT, url TEXT, last_seen TEXT, status TEXT DEFAULT "new")')
    conn.commit()

def save_job(conn, job):
    conn.execute('INSERT INTO jobs(key,company,title,url,last_seen) VALUES(?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET last_seen=excluded.last_seen',
                 (job.key, job.company, job.title, str(job.url), datetime.now(timezone.utc).isoformat()))

def report(
    items,
    errors,
    path,
    *,
    ai_errors=None,
    normalization_warnings=None,
    verification_errors=None,
    discovery_summary=None,
):
    ai_errors = ai_errors or []
    normalization_warnings = normalization_warnings or []
    verification_errors = verification_errors or []
    by_status = {s: [] for s in Eligibility}
    for job, match in items: by_status[match.eligibility].append((job,match))
    lines = ["# Daily AI Job Hunter", "", f"Generated: {datetime.now(timezone.utc).isoformat()}",
             "", f"Jobs analyzed: {len(items)}; eligible: {len(by_status[Eligibility.eligible])}; review: {len(by_status[Eligibility.review])}; rejected: {len(by_status[Eligibility.rejected])}",
             "", "> Verification is conservative. 'Eligible' requires a successful official ATS job-detail check and explicit remote/Poland evidence. A successful ATS detail response does not guarantee the application form accepts submissions.", ""]

    if discovery_summary is not None:
        lines += [
            "## Discovery summary",
            "",
            f"Status: {discovery_summary['status']}",
            (
                f"Sources: {discovery_summary['successful_sources']} succeeded, "
                f"{discovery_summary['failed_sources']} failed, "
                f"{discovery_summary['total_sources']} total"
            ),
            f"Jobs collected: {discovery_summary['jobs_collected']}",
            "",
        ]

    for status in (Eligibility.eligible, Eligibility.review, Eligibility.rejected):
        lines += [f"## {status.value.title()} ({len(by_status[status])})", ""]
        for job, match in sorted(by_status[status], key=lambda x: x[1].score, reverse=True)[:20]:
            lines += [f"### {job.title} — {job.company}",
                      f"- **Fit:** {match.score}/100 | **AI transition:** {match.ai_transition_score}/100 | **AI analyzed:** {match.ai_analyzed}",
                      f"- **Location:** {job.location} | **Source:** {job.provider} | **Verified ATS detail:** {job.verified_live} ({job.verified_at or 'not checked'})",
                      f"- **Job:** {job.url} | **Apply:** {job.apply_url or 'unknown'}",
                      f"- **Reasons:** {'; '.join(match.reasons) or 'None established'}",
                      f"- **Concerns:** {'; '.join(match.concerns) or 'None established'}", ""]
            if getattr(match, 'ai_backend', None):
                lines.insert(len(lines) - 1, f"- **AI backend:** {match.ai_backend}")
    if errors:
        lines += ["## Collection / verification errors", ""]

        for error in errors:
            status = (
                f"HTTP {error['status_code']}"
                if error["status_code"] is not None
                else error["error_type"]
            )

            lines.append(
                f"- Collection failure: "
                f"{safe_identifier(error['provider'])}/"
                f"{safe_identifier(error['board'])} — "
                f"{error['category']} ({status})"
            )

    if ai_errors:
        lines += ["", "## AI analysis errors", ""]

        for error in ai_errors:
            lines.append(
                f"- AI analysis failure: "
                f"{safe_identifier(error['job_key'])} — "
                f"{error['error_type']}"
            )

    if normalization_warnings:
        lines += ["", "## Malformed ATS records", ""]

        for warning in normalization_warnings:
            lines.append(
                f"- {safe_identifier(warning['provider'])}/"
                f"{safe_identifier(warning['board'])}: "
                f"{warning['skipped_invalid']} invalid records skipped"
            )

    if verification_errors:
        lines += ["", "## Job verification failures", ""]

        for error in verification_errors:
            status = (
                f"HTTP {error['status_code']}"
                if error["status_code"] is not None
                else error["error_type"]
            )

            lines.append(
                f"- Verification failure: "
                f"{safe_identifier(error['provider'])}/"
                f"{safe_identifier(error['board'])} — "
                f"{safe_identifier(error['job_key'])} — "
                f"{error['category']} ({status})"
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(args):
    profile = yaml.safe_load(Path(args.profile).read_text(encoding='utf-8'))
    cfg = yaml.safe_load(Path(args.sources).read_text(encoding='utf-8'))
    boards = cfg.get('boards', []) or []
    collection_errors = []
    ai_errors = []
    normalization_warnings = []
    verification_errors = []
    jobs = []

    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={'User-Agent':'AIJobHunter/0.1 (personal research)'}) as client:
        for board in boards:
            try:
                result = await collect_with_diagnostics(client, board['provider'], board['slug'], board['company'])
                jobs.extend(result.jobs)

                if result.skipped_invalid > 0:
                    normalization_warnings.append({
                        "provider": board["provider"],
                        "board": board["slug"],
                        "skipped_invalid": result.skipped_invalid,
                    })
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                collection_errors.append(
                    describe_source_error(
                        provider=board.get("provider", "unknown"),
                        board=board.get("slug", "unknown"),
                        error=exc,
                    )
                )
        unique = {job.key: job for job in jobs}
        jobs = list(unique.values())

        jobs_collected = len(jobs)
        for job in jobs:
            result = await verify_detail(client, job)

            if not result.verified:
                verification_errors.append({
                    "job_key": job.key,
                    "provider": job.provider,
                    "board": job.board,
                    "error_type": result.error_type,
                    "category": result.category,
                    "status_code": result.status_code,
                })

    conn = sqlite3.connect(args.database)
    db_init(conn)
    known = {row[0]:row[1] for row in conn.execute('SELECT key,status FROM jobs')}
    items = []
    ai_attempts = 0
    max_ai_jobs = getattr(args, 'max_ai_jobs', None)
    for job in jobs:
        if known.get(job.key) in ('applied','skipped','dismissed'):
            continue
        match = evaluate(job, profile)
        if (args.ai and match.eligibility != Eligibility.rejected
                and max_ai_jobs is not None and ai_attempts >= max_ai_jobs):
            match.eligibility = Eligibility.review
            match.concerns.append("AI assessment skipped: --max-ai-jobs limit reached; technical eligibility requires review")
        elif args.ai and match.eligibility != Eligibility.rejected:
            match.ai_backend = getattr(args, 'ai_backend', 'gemini')
            ai_attempts += 1
            try:
                assessor = assess_requirements_agent if match.ai_backend == 'agent' else assess_requirements
                assessment = await assessor(profile, job.description, args.model)
                technical = grounded_technical_eligibility(assessment, profile, job.description)
                match.eligibility = combine_eligibility(match.eligibility, technical)
                match.ai_analyzed = True
                if technical == Eligibility.review:
                    match.concerns.append("AI technical requirements need review: missing, uncertain, or ungrounded evidence")
                else:
                    match.reasons.append("AI technical assessment passed quotation checks; manual semantic verification remains necessary")
            except Exception as exc:
                match.ai_analyzed = False
                match.eligibility = Eligibility.review
                match.concerns.append("AI analysis failed; technical eligibility requires review")
                ai_errors.append({
                    "job_key": job.key,
                    "error_type": type(exc).__name__,
                })
        save_job(conn, job)
        items.append((job, match))
    conn.commit(); conn.close()
    total_sources = len(boards)
    failed_sources = len(collection_errors)
    successful_sources = total_sources - failed_sources

    discovery_status = calculate_discovery_status(
        total_sources=total_sources,
        failed_sources=failed_sources,
    )

    emit_log(
        logger,
        make_log_event(
            event="discovery_completed",
            component="discovery",
            outcome=discovery_status.value,
            level=discovery_log_level(discovery_status),
        ),
    )

    discovery_summary = {
        "status": discovery_status.value,
        "total_sources": total_sources,
        "successful_sources": successful_sources,
        "failed_sources": failed_sources,
        "jobs_collected": jobs_collected,
    }

    report(
        items,
        collection_errors,
        Path(args.output),
        ai_errors=ai_errors,
        normalization_warnings=normalization_warnings,
        verification_errors=verification_errors,
        discovery_summary=discovery_summary,
    )
    warning_count = (
            len(collection_errors)
            + len(ai_errors)
            + len(normalization_warnings)
            + len(verification_errors)
    )

    print(
        f"Wrote {args.output}; "
        f"{len(items)} results, {warning_count} warnings"
    )

def main():
    from dotenv import load_dotenv
    load_dotenv()
    parser = argparse.ArgumentParser(description='Daily AI Job Hunter')
    parser.add_argument('--profile', default=str(ROOT/'config/profile.yaml'))
    parser.add_argument('--sources', default=str(ROOT/'config/sources.yaml'))
    parser.add_argument('--database', default='jobs.sqlite3')
    parser.add_argument('--output', default='reports/daily.md')
    parser.add_argument('--ai', action='store_true', help='Enable evidence-checked Gemini technical analysis')
    parser.add_argument('--ai-backend', choices=('gemini', 'agent'), default='gemini',
                        help='AI execution backend (default: gemini HTTP; agent requires the [ai] extra)')
    parser.add_argument('--model', help='Gemini model ID; defaults to GEMINI_MODEL')
    parser.add_argument('--max-ai-jobs', type=int, default=None,
                        help='Positive maximum AI assessment attempts in collection order (default: unlimited)')
    args = parser.parse_args()
    if args.max_ai_jobs is not None:
        if args.max_ai_jobs <= 0:
            parser.error('--max-ai-jobs must be a positive integer')
        if not args.ai:
            parser.error('--max-ai-jobs requires --ai')
    if args.ai_backend != 'gemini' and not args.ai:
        parser.error('--ai-backend agent requires --ai')
    if args.ai:
        try:
            gemini_config(args.model)
        except ValueError as exc:
            parser.error(str(exc))
    asyncio.run(run(args))

if __name__ == '__main__': main()
