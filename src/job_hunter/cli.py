import argparse
import asyncio
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import httpx
import yaml
from job_hunter.collectors.ats import collect
from job_hunter.evaluate import evaluate
from job_hunter.agent import analyze
from job_hunter.models import Job, Eligibility

ROOT = Path(__file__).resolve().parents[2]

def db_init(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS jobs (key TEXT PRIMARY KEY, company TEXT, title TEXT, url TEXT, last_seen TEXT, status TEXT DEFAULT "new")')
    conn.commit()

def save_job(conn, job):
    conn.execute('INSERT INTO jobs(key,company,title,url,last_seen) VALUES(?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET last_seen=excluded.last_seen',
                 (job.key, job.company, job.title, str(job.url), datetime.now(timezone.utc).isoformat()))

def report(items, errors, path):
    by_status = {s: [] for s in Eligibility}
    for job, match in items: by_status[match.eligibility].append((job,match))
    lines = ["# Daily AI Job Hunter", "", f"Generated: {datetime.now(timezone.utc).isoformat()}",
             "", f"Jobs analyzed: {len(items)}; eligible: {len(by_status[Eligibility.eligible])}; review: {len(by_status[Eligibility.review])}; rejected: {len(by_status[Eligibility.rejected])}",
             "", "> Verification is conservative. 'Eligible' requires a successful official ATS job-detail check and explicit remote/Poland evidence. A successful ATS detail response does not guarantee the application form accepts submissions.", ""]
    for status in (Eligibility.eligible, Eligibility.review, Eligibility.rejected):
        lines += [f"## {status.value.title()} ({len(by_status[status])})", ""]
        for job, match in sorted(by_status[status], key=lambda x: x[1].score, reverse=True)[:20]:
            lines += [f"### {job.title} — {job.company}",
                      f"- **Fit:** {match.score}/100 | **AI transition:** {match.ai_transition_score}/100 | **AI analyzed:** {match.ai_analyzed}",
                      f"- **Location:** {job.location} | **Source:** {job.provider} | **Verified ATS detail:** {job.verified_live} ({job.verified_at or 'not checked'})",
                      f"- **Job:** {job.url} | **Apply:** {job.apply_url or 'unknown'}",
                      f"- **Reasons:** {'; '.join(match.reasons) or 'None established'}",
                      f"- **Concerns:** {'; '.join(match.concerns) or 'None established'}", ""]
    if errors:
        lines += ["## Collection / verification errors", ""] + [f"- {e}" for e in errors]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

async def verify_detail(client, job):
    # Only canonical job-specific ATS GET URLs establish live status; page/ATS form functionality is NOT verified.
    endpoint = None
    if job.provider == 'greenhouse':
        endpoint = f'https://boards-api.greenhouse.io/v1/boards/{job.board}/jobs/{job.external_id}'
    elif job.provider == 'lever':
        endpoint = f'https://api.lever.co/v0/postings/{job.board}/{job.external_id}'
    elif job.provider == 'ashby':
        # Ashby public posting API publishes current postings; confirmation comes from the live board response,
        # not from validating a possibly inaccessible application URL.
        job.verified_live = True
        job.verified_at = datetime.now(timezone.utc).isoformat()
        return
    if endpoint:
        try:
            r = await client.get(endpoint)
            r.raise_for_status()
            job.verified_live = True
            job.verified_at = datetime.now(timezone.utc).isoformat()
        except (httpx.HTTPError, ValueError):
            pass

async def run(args):
    profile = yaml.safe_load(Path(args.profile).read_text(encoding='utf-8'))
    cfg = yaml.safe_load(Path(args.sources).read_text(encoding='utf-8'))
    boards = cfg.get('boards', []) or []
    errors = []; jobs = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={'User-Agent':'AIJobHunter/0.1 (personal research)'}) as client:
        for board in boards:
            try:
                new = await collect(client, board['provider'], board['slug'], board['company'])
                jobs.extend(new)
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                errors.append(f"{board}: {type(exc).__name__}: {exc}")
        unique = {job.key: job for job in jobs}
        jobs = list(unique.values())
        for job in jobs:
            await verify_detail(client, job)
    conn = sqlite3.connect(args.database)
    db_init(conn)
    known = {row[0]:row[1] for row in conn.execute('SELECT key,status FROM jobs')}
    items = []
    for job in jobs:
        if known.get(job.key) in ('applied','skipped','dismissed'):
            continue
        match = evaluate(job, profile)
        if args.ai and match.eligibility != Eligibility.rejected:
            try:
                match = await analyze(job, match, profile, args.model)
            except Exception as exc:
                errors.append(f"AI analysis {job.key}: {type(exc).__name__}: {exc}")
        save_job(conn, job)
        items.append((job, match))
    conn.commit(); conn.close()
    report(items, errors, Path(args.output))
    print(f"Wrote {args.output}; {len(items)} results, {len(errors)} warnings")

def main():
    from dotenv import load_dotenv
    load_dotenv()
    parser = argparse.ArgumentParser(description='Daily AI Job Hunter')
    parser.add_argument('--profile', default=str(ROOT/'config/profile.yaml'))
    parser.add_argument('--sources', default=str(ROOT/'config/sources.yaml'))
    parser.add_argument('--database', default='jobs.sqlite3')
    parser.add_argument('--output', default='reports/daily.md')
    parser.add_argument('--ai', action='store_true', help='Enable OpenAI Agents SDK analysis')
    parser.add_argument('--model', default=os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite') if os.getenv('GEMINI_API_KEY') else os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'))
    args = parser.parse_args()
    if args.ai and not (os.getenv('GEMINI_API_KEY') or os.getenv('OPENAI_API_KEY')):
        parser.error('--ai requires GEMINI_API_KEY or OPENAI_API_KEY and pip install -e ".[ai]"')
    asyncio.run(run(args))

if __name__ == '__main__': main()