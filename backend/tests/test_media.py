import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media import probe, render, srt_captions, timestamp
from visual import visual_windows

FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


class UnitTests(unittest.TestCase):
    def test_timecodes(self):
        self.assertEqual(timestamp(61.001), "00:01:01,001")

    def test_subtitles_skip_removed_segments(self):
        plan = {"cuts": [
            {"first": 0, "last": 0, "start": 0.0, "end": 1.5},
            {"first": 2, "last": 2, "start": 2.5, "end": 4.0},
        ]}
        items = [
            {"start": 0, "end": 1.5, "text": "첫 번째 문장"},
            {"start": 1.5, "end": 2.5, "text": "제외"},
            {"start": 2.5, "end": 4.0, "text": "두 번째 문장"},
        ]
        caption = srt_captions(plan, items)
        self.assertIn("00:00:00,000 --> 00:00:01,500", caption)
        self.assertIn("00:00:01,500 --> 00:00:03,000", caption)
        self.assertNotIn("제외", caption)


@unittest.skipUnless(FFMPEG, "FFmpeg/FFprobe not installed")
class VideoSmokeTests(unittest.TestCase):
    def make_source(self, root: Path, audio: bool):
        source = root / ("with-sound.mp4" if audio else "silent.mp4")
        command = [
            "ffmpeg", "-nostdin", "-hide_banner", "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25",
        ]
        if audio:
            command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
        command += ["-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if audio:
            command += ["-c:a", "aac"]
        command.append(str(source))
        subprocess.run(command, check=True, timeout=90)
        return source

    def test_video_and_audio_9x16_16x9(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = self.make_source(root, True)
            plan = {"cuts": [
                {"first": 0, "last": 0, "start": 0.0, "end": 1.5},
                {"first": 2, "last": 2, "start": 2.5, "end": 4.0},
            ], "actualSeconds": 3.0}
            transcript = [
                {"start": 0, "end": 1.5, "text": "첫 번째 문장"},
                {"start": 1.5, "end": 2.5, "text": "삭제"},
                {"start": 2.5, "end": 4.0, "text": "두 번째 문장"},
            ]
            for fmt, size in [("shorts", (720, 1280)), ("wide", (1280, 720))]:
                result_path = root / ("result-" + fmt + ".mp4")
                result = render(source, result_path, plan, transcript, fmt, True, True)
                self.assertEqual((result["width"], result["height"]), size)
                self.assertLess(abs(result["duration"] - 3.0), 1.5)
                self.assertTrue(result["has_audio"])

    def test_no_audio_visual_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = self.make_source(root, False)
            segments, _ = visual_windows(source, 4.0)
            self.assertTrue(segments)
            self.assertFalse(probe(source)["has_audio"])
            plan = {"cuts": [{"first": 0, "last": 0, "start": 0.0, "end": 4.0}],
                    "actualSeconds": 4.0}
            target = root / "silent-result.mp4"
            result = render(source, target, plan, [], "shorts", False, False)
            self.assertTrue(result["has_audio"])
            self.assertLess(abs(result["duration"] - 4), 1.5)


if __name__ == "__main__":
    unittest.main()
