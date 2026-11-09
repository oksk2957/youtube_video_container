import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import make_plan, validate_cuts

SEGMENTS = [
    {"start": float(i * 5), "end": float(i * 5 + 5), "text": "문장 " + str(i)}
    for i in range(18)
]


class PlannerTests(unittest.TestCase):
    def test_valid_edit_plan(self):
        plan = validate_cuts({"title": "핵심 정리", "cuts": [
            {"first": 2, "last": 5}, {"first": 8, "last": 12},
        ]}, SEGMENTS, 45, 90)
        self.assertEqual(plan["actualSeconds"], 45)
        self.assertEqual(plan["cuts"][1]["start"], 40)

    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):
            validate_cuts({"title": "bad", "cuts": [
                {"first": 1, "last": 5}, {"first": 4, "last": 8},
            ]}, SEGMENTS, 45, 90)

    def test_out_of_bounds_rejected(self):
        with self.assertRaises(ValueError):
            validate_cuts({"title": "bad", "cuts": [{"first": 0, "last": 99}]},
                          SEGMENTS, 45, 90)

    def test_overlong_plan_rejected(self):
        with self.assertRaises(ValueError):
            validate_cuts({"title": "bad", "cuts": [{"first": 0, "last": 17}]},
                          SEGMENTS, 45, 90)

    def test_ai_retries_invalid_response(self):
        class MockProvider:
            calls = 0
            def chat_json(self, *_):
                self.calls += 1
                if self.calls == 1:
                    return {"title": "too long", "cuts": [{"first": 0, "last": 17}]}
                return {"title": "good", "cuts": [{"first": 2, "last": 10}]}
        model = MockProvider()
        plan = make_plan(model, SEGMENTS, 45, 90, "news")
        self.assertEqual(plan["actualSeconds"], 45)
        self.assertEqual(model.calls, 2)

    def test_no_hallucinated_noninteger_index(self):
        with self.assertRaises(ValueError):
            validate_cuts({"title": "bad", "cuts": [{"first": "0", "last": 2}]},
                          SEGMENTS, 45, 90)


if __name__ == "__main__":
    unittest.main()
