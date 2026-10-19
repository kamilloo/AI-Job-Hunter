import pytest
import httpx
from job_hunter.collectors.ats import collect, normalize
from job_hunter.evaluate import evaluate
from job_hunter.models import Job, Eligibility

PROFILE = {'core_skills':['php','postgresql','elasticsearch'], 'skipped_companies':['Skipped Inc'], 'culture_flags':['whatever it takes']}

def job(**changes):
    data = dict(provider='greenhouse',board='acme',external_id='1',company='Acme',title='Senior Backend Engineer',location='Remote - Poland',
                description='Fully remote from Poland. PHP PostgreSQL reliability.',url='https://boards.greenhouse.io/acme/jobs/1',verified_live=True)
    data.update(changes)
    return Job(**data)

def test_relevant_eligible():
    r = evaluate(job(), PROFILE)
    assert r.eligibility == Eligibility.eligible
    assert r.score >= 55

def test_unknown_remote_needs_review():
    assert evaluate(job(location='Berlin',description='PHP PostgreSQL'), PROFILE).eligibility == Eligibility.review

def test_hybrid_rejected():
    assert evaluate(job(location='Hybrid - Warsaw'), PROFILE).eligibility == Eligibility.rejected

def test_not_verified_review():
    assert evaluate(job(verified_live=False), PROFILE).eligibility == Eligibility.review

def test_skipped_company():
    assert evaluate(job(company='Skipped Inc'), PROFILE).eligibility == Eligibility.rejected

def test_off_target():
    assert evaluate(job(title='Sales Director'), PROFILE).eligibility == Eligibility.rejected

def test_ashby_normalize():
    j = normalize('ashby','acme','Acme',{'title':'Senior Backend Engineer','jobUrl':'https://jobs.ashbyhq.com/acme/abc','isRemote':True,'descriptionHtml':'<p>PHP</p>'})
    assert j.remote is True and j.description == 'PHP'

def test_greenhouse_collector_mock():
    async def scenario():
        transport=httpx.MockTransport(lambda request: httpx.Response(200,json={'jobs':[{'id':12,'title':'Backend Engineer','location':{'name':'Poland'},'absolute_url':'https://job.example/12','content':'<b>PHP</b>'}]}))
        async with httpx.AsyncClient(transport=transport) as client:
            j=await collect(client,'greenhouse','acme','Acme')
            assert len(j)==1 and j[0].description=='PHP'
    import asyncio
    asyncio.run(scenario())
