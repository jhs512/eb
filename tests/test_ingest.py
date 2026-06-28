"""ingest.py 순수 파싱 로직 테스트 (네트워크/서드파티 없음).

전사 어댑터(youtube-transcript-api/whisper)는 선택 의존이라 여기서 테스트하지 않고,
오프라인으로 검증 가능한 URL 파싱·텍스트 정리·세그먼트 결합만 박제한다.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ingest  # noqa: E402


class IngestParseTest(unittest.TestCase):
    def test_extract_video_id_watch(self):
        self.assertEqual(
            ingest.extract_video_id("https://www.youtube.com/watch?v=z02Y-1OvWSM"),
            "z02Y-1OvWSM")

    def test_extract_video_id_short_and_params(self):
        self.assertEqual(ingest.extract_video_id("https://youtu.be/z02Y-1OvWSM?t=42"),
                         "z02Y-1OvWSM")
        self.assertEqual(
            ingest.extract_video_id("https://m.youtube.com/watch?v=z02Y-1OvWSM&list=x"),
            "z02Y-1OvWSM")

    def test_extract_video_id_none_for_non_url(self):
        self.assertIsNone(ingest.extract_video_id("그냥 텍스트 메모"))

    def test_is_youtube_url(self):
        self.assertTrue(ingest.is_youtube_url("https://youtu.be/z02Y-1OvWSM"))
        self.assertFalse(ingest.is_youtube_url("notes/meeting.md"))
        self.assertFalse(ingest.is_youtube_url("audio.mp3"))

    def test_clean_transcript_strips_cues_and_timestamps(self):
        raw = "00:00:01.000 --> 00:00:03.000\n[Music]  집중은   단련된다 [Applause]"
        self.assertEqual(ingest.clean_transcript(raw), "집중은 단련된다")

    def test_segments_to_text_joins_and_cleans(self):
        segs = [{"text": "딥 워크는"}, {"text": "[Music]"}, {"text": "몰입이다"}]
        self.assertEqual(ingest.segments_to_text(segs), "딥 워크는 몰입이다")

    def test_segments_to_text_empty(self):
        self.assertEqual(ingest.segments_to_text([]), "")


if __name__ == "__main__":
    unittest.main()
