import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media import srt_captions, timestamp, video_filter


class MediaTests(unittest.TestCase):
    def test_caption_timeline_offset(self):
        plan = {"cuts": [{"first": 0, "last": 0, "start": 2, "end": 5},
                         {"first": 2, "last": 2, "start": 8, "end": 11}]}
        words = [{"start": 2, "end": 5, "text": "hello"},
                 {"start": 5, "end": 7, "text": "skipped"},
                 {"start": 8, "end": 11, "text": "world"}]
        srt = srt_captions(plan, words)
        self.assertIn("00:00:00,000 --> 00:00:03,000", srt)
        self.assertIn("00:00:03,000 --> 00:00:06,000", srt)
        self.assertNotIn("skipped", srt)

    def test_time_format(self):
        self.assertEqual(timestamp(61.001), "00:01:01,001")

    def test_formats_preserve_full_frame(self):
        self.assertIn("pad=", video_filter("wide"))
        self.assertIn("overlay=", video_filter("shorts"))

if __name__ == "__main__":
    unittest.main()
