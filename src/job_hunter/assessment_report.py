"""Local Markdown presentation of untrusted technical assessment content."""
import html
import re

from job_hunter.model.RequirementAssessment import TechnicalAssessment
from job_hunter.validation.validate_candidate_evidence import validate_candidate_evidence


def markdown_text(value: str) -> str:
    """Keep source text on one line without active Markdown or HTML."""
    text = html.escape(' '.join(value.split()), quote=False)
    return re.sub(r'([\\`*_{}\[\]()#+!|~])', r'\\\1', text)


def assessment_lines(assessment: TechnicalAssessment, candidate_contexts: list[str] | None) -> list[str]:
    lines = []
    if assessment.technical_fit is not None:
        lines += [f'**Technical fit (model assessment):** {assessment.technical_fit.value.title()}', '']
    lines += [f'**Model confidence:** {assessment.confidence:g} (not a calibrated probability)', '']
    if assessment.summary.strip():
        lines += [f'**Model summary:** {markdown_text(assessment.summary)}', '']
    lines += [
        '> Quotation checks establish source provenance only. Model statuses, explanations, fit, and confidence do not prove semantic suitability or candidate experience. Review mandatory gaps and any missing, unchecked, or invalid evidence manually.',
        '', '#### Technical requirements', '',
    ]
    if not assessment.requirements:
        return lines + ['No technical requirements returned; technical eligibility remains unverified.', '']
    lines += [
        '| Requirement | Type | Model status | Employer quotation provenance | Candidate quotation provenance |',
        '| --- | --- | --- | --- | --- |',
    ]
    details = ['', '<details>', f'<summary>Evidence details ({len(assessment.requirements)} requirements)</summary>', '']
    for requirement in assessment.requirements:
        validation = requirement.evidence_validation
        employer = 'Not checked' if validation is None else ('Yes' if validation.valid else 'No')
        if not requirement.candidate_evidence.strip():
            candidate = 'Not established'
        elif candidate_contexts is None:
            candidate = 'Not checked'
        else:
            candidate = 'Yes' if validate_candidate_evidence(candidate_contexts, requirement.candidate_evidence).valid else 'No'
        name = markdown_text(requirement.name) or '(No name supplied)'
        kind = 'Mandatory' if requirement.mandatory else 'Preferred'
        status = requirement.status.value.title()
        lines.append(f'| {name} | {kind} | {status} | {employer} | {candidate} |')
        details += [
            f'**{name}**', '',
            f'- **Classification:** {kind}; model status: {status}',
            f'- **Employer evidence (model quotation):** {markdown_text(requirement.job_evidence) if requirement.job_evidence.strip() else "Not established"}',
            f'- **Employer quotation provenance:** {employer}' + (f' — {markdown_text(validation.reason)}' if validation is not None else ''),
            f'- **Candidate evidence (model quotation):** {markdown_text(requirement.candidate_evidence) if requirement.candidate_evidence.strip() else "Not established"}',
            f'- **Candidate quotation provenance:** {candidate}',
        ]
        if requirement.explanation.strip():
            details.append(f'- **Model explanation (unverified):** {markdown_text(requirement.explanation)}')
        details += ['']
    return lines + details + ['</details>', '']
