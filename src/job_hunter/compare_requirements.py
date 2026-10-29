
import re


def normalize_name(name: str) -> str:
    return " ".join(name.casefold().split())


def contains_skill(name: str, skill: str) -> bool:
    name = normalize_name(name)
    skill = normalize_name(skill)

    pattern = rf"(?<!\w){re.escape(skill)}(?!\w)"
    return re.search(pattern, name) is not None


def compare_requirement_fields(expected: dict, actual: dict) -> bool:
    if expected["mandatory"] != actual["mandatory"]:
        return False

    if expected["status"] != actual["status"]:
        return False

    expected_evidence = expected["candidate_evidence"]
    actual_evidence = actual["candidate_evidence"]

    if expected_evidence == "__nonempty__":
        return bool(actual_evidence.strip())

    return expected_evidence == actual_evidence


def compare_requirements(
    expected: list[dict],
    actual: list[dict],
    expected_skills: set[str] | None = None,
) -> bool:
    if expected_skills is None:
        return (
            len(expected) == len(actual) == 1
            and normalize_name(expected[0]["name"])
            == normalize_name(actual[0]["name"])
            and compare_requirement_fields(expected[0], actual[0])
        )

    if not expected_skills or not expected or not actual:
        return False

    # Supported by this focused suite: all expected requirement
    # entries must agree on the fields being verified.
    reference = expected[0]

    if not all(
        compare_requirement_fields(reference, item)
        for item in expected
    ):
        return False

    covered_skills = set()

    for requirement in actual:
        matched = {
            skill
            for skill in expected_skills
            if contains_skill(requirement["name"], skill)
        }

        # Reject unrelated extracted requirements.
        if not matched:
            return False

        # Validate every relevant extracted requirement.
        if not compare_requirement_fields(reference, requirement):
            return False

        covered_skills.update(matched)

    return covered_skills == expected_skills
