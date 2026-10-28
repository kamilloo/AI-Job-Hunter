import unittest

from pydantic import ValidationError
from job_hunter.model.CandidateExperience import CandidateExperience


class TestCandidateExperience(unittest.TestCase):

    def test_documented_production_technology_with_known_years(self):
        experience = CandidateExperience(
            technology="PHP",
            context="5 years building production PHP backend services",
            production=True,
            years=5,
        )

        self.assertEqual(experience.technology, "PHP")
        self.assertEqual(
            experience.context,
            "5 years building production PHP backend services",
        )
        self.assertIs(experience.production, True)
        self.assertEqual(experience.years, 5)

    def test_technology_without_supporting_context(self):
        experience = CandidateExperience(
            technology="PHP",
            context="",
        )

        self.assertEqual(experience.context, "")
        self.assertIsNone(experience.production)
        self.assertIsNone(experience.years)

    def test_invalid_negative_number_of_years(self):
        with self.assertRaises(ValidationError):
            CandidateExperience(
                technology="PHP",
                context="Strong backend experience with PHP",
                production=True,
                years=-1,
            )

    def test_unknown_is_different_from_no_production_experience(self):
        unknown = CandidateExperience(
            technology="Go",
            context="",
        )

        not_production = CandidateExperience(
            technology="Go",
            context="Used Go in personal projects only",
            production=False,
            years=None,
        )

        self.assertIsNone(unknown.production)
        self.assertIs(not_production.production, False)