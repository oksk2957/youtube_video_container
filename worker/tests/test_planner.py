import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import validate_cuts, make_plan

SEGMENTS = [{"start": float(i * 5), "end": float(i * 5 + 5), "text": "Sentence " + str(i)}
            for i in range(18)]


class PlanTests(unittest.TestCase):
    def test_valid_cut_sequence(self):
        plan = validate_cuts({"title": "Explainer", "cuts": [
            {"first": 2, "last": 5, "reason": "Context"},
            {"first": 8, "last": 12, "reason": "Result"},
        ]}, SEGMENTS, 45, 90)
        self.assertEqual(plan["actualSeconds"], 45)
        self.assertEqual(plan["cuts"][0]["start"], 10)

    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):
            validate_cuts({"title": "Bad", "cuts": [
                {"first": 1, "last": 4}, {"first": 3, "last": 5},
            ]}, SEGMENTS, 45, 90)

    def test_invalid_index_rejected(self):
        with self.assertRaises(ValueError):
            validate_cuts({"title": "Bad", "cuts": [{"first": 1, "last": 99}]}, SEGMENTS, 45, 90)

    def test_overlong_edit_rejected(self):
        with self.assertRaises(ValueError):
            validate_cuts({"title": "Bad", "cuts": [{"first": 0, "last": 17}]}, SEGMENTS, 45, 90)

    def test_ai_retry(self):
        class MockAI:
            calls = 0
            def chat_json(self, *_):
                self.calls += 1
                if self.calls == 1:
                    return {"title": "Too long", "cuts": [{"first": 0, "last": 17}]}
                return {"title": "Good", "cuts": [{"first": 2, "last": 10}]}
        ai = MockAI()
        plan = make_plan(ai, SEGMENTS, 45, 90, "news")
        self.assertEqual(plan["actualSeconds"], 45)
        self.assertEqual(ai.calls, 2)

if __name__ == "__main__":
    unittest.main()
