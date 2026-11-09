import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media import render, probe


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg binary not installed")
class FfmpegSmokeTest(unittest.TestCase):
    def test_9x16_and_16x9_render(self):
        with tempfile.TemporaryDirectory(prefix="ffmpeg-smoke-") as folder:
            root = Path(folder)
            source = root / "sample.mp4"
            subprocess.run([
                "ffmpeg", "-nostdin", "-y", "-v", "error",
                "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", str(source),
            ], check=True, timeout=90)
            plan = {
                "cuts": [
                    {"first": 0, "last": 0, "start": 0.0, "end": 1.5},
                    {"first": 2, "last": 2, "start": 2.5, "end": 4.0},
                ], "actualSeconds": 3.0,
            }
            transcript = [
                {"start": 0, "end": 1.5, "text": "첫 번째 문장"},
                {"start": 1.5, "end": 2.5, "text": "삭제되는 부분"},
                {"start": 2.5, "end": 4.0, "text": "두 번째 문장"},
            ]
            for output_format, size in [("wide", (1280, 720)), ("shorts", (720, 1280))]:
                output = root / ("result_" + output_format + ".mp4")
                result = render(source, output, plan, transcript, output_format)
                self.assertEqual((result["width"], result["height"]), size)
                self.assertLess(abs(result["duration"] - 3), 1.5)
                self.assertGreater(output.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
