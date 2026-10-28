import unittest
from pathlib import Path

import yaml

from job_hunter.model.CandidateExperience import CandidateProfile


class LoadProfileTestCase(unittest.TestCase):
    def test_loading_profile(self):
        root = Path(__file__).resolve().parents[2]
        profile_path = root / 'config/profile.yaml'
        profile = CandidateProfile.model_validate(
            yaml.safe_load(profile_path.read_text(encoding='utf-8'))
        )

        assert "php" in profile.core_skills
        assert profile.skill_experiences[0].technology == "PHP"
        assert profile.skill_experiences[0].production is True
        assert profile.skill_experiences[0].years == 10

    def test_legacy_profile_without_skill_experiences(self):
        profile = CandidateProfile.model_validate(
            {
                "core_skills": ["php", "laravel"],
            }
        )

        self.assertEqual(profile.core_skills, ["php", "laravel"])
        self.assertEqual(profile.skill_experiences, [])


if __name__ == '__main__':
    unittest.main()
