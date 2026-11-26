from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "academic-humanize" / "src" / "academic_humanizer.py"


spec = importlib.util.spec_from_file_location("academic_humanizer_regression", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AcademicHumanizerRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import spacy
        except ImportError:
            raise unittest.SkipTest("spaCy unavailable")
        cls.spacy = spacy
        cls.nlp = spacy.blank("en")
        cls.nlp.add_pipe("sentencizer")

    def make_humanizer(self):
        humanizer = module.AcademicHumanizer.__new__(module.AcademicHumanizer)
        humanizer.nlp = self.nlp
        humanizer.model = None
        return humanizer

    def test_paragraph_lf_separator_is_preserved(self):
        humanizer = self.make_humanizer()
        text = "The team can't finish the model.\n\nSecond paragraph stays here."
        result = humanizer.humanize(text, ai_score=0.0)
        self.assertEqual(result.count("\n"), text.count("\n"))
        self.assertIn("model.\n\nSecond", result)

    def test_crlf_separator_is_preserved(self):
        humanizer = self.make_humanizer()
        text = "The team can't finish the model.\r\n\r\nSecond paragraph stays here."
        result = humanizer.humanize(text, ai_score=0.0)
        self.assertEqual(result.count("\r\n"), text.count("\r\n"))
        self.assertIn("model.\r\n\r\nSecond", result)

    def test_passive_preserves_past_tense(self):
        humanizer = self.make_humanizer()
        self.assertEqual(
            humanizer.convert_to_active("The plan was made by the team"),
            "The team made the plan",
        )
        self.assertEqual(
            humanizer.convert_to_active("The experiment was conducted by researchers"),
            "Researchers conducted the experiment",
        )

    def test_passive_after_leading_space_does_not_duplicate_capitalization(self):
        humanizer = self.make_humanizer()
        self.assertEqual(
            humanizer.convert_to_active(" That was made by the team"),
            " The team made that",
        )


if __name__ == "__main__":
    unittest.main()
