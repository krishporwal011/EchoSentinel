"""Regression tests for metadata-driven, local-only In-The-Wild ingestion."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from ingest_in_the_wild import MetadataFormatError, ingest_dataset


def _write_metadata(root: Path, rows, columns=("file", "speaker", "label")):
    with (root / "meta.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def _inspector(path: Path):
    payload = path.read_bytes()
    if payload == b"corrupt":
        raise ValueError("decode failed")
    if payload == b"silent":
        raise ValueError("Audio does not contain enough meaningful speech for analysis.")
    return {"sample_rate": 16000, "duration_seconds": 1.25, "channels": 1}


class InTheWildIngestionTests(unittest.TestCase):
    def test_verified_metadata_drives_labels_and_audio_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audio = root / "a-file-named-fake.wav"
            audio.write_bytes(b"real audio bytes")
            _write_metadata(root, [{"file": audio.name, "speaker": "Public Figure", "label": "bona-fide"}])
            before = audio.read_bytes()

            manifest, report = ingest_dataset(root, confirm_candidate_schema=True, audio_inspector=_inspector)

            sample = manifest["samples"][0]
            self.assertEqual(set(sample), {
                "sample_id", "audio_path", "ground_truth", "source_type", "speaker_id",
                "source_recording_id", "synthetic_generator", "synthetic_generator_version",
                "language", "codec", "sample_rate", "recording_conditions", "dataset_source",
                "provenance", "consent_status", "partition", "notes", "uncertainty",
            })
            self.assertEqual(sample["ground_truth"], "bonafide")
            self.assertEqual(sample["source_type"], "human_recording")
            self.assertEqual(sample["sample_rate"], 16000)
            self.assertEqual(report["durations_seconds_by_sample_id"][sample["sample_id"]], 1.25)
            self.assertTrue(sample["speaker_id"].startswith("speaker-"))
            self.assertNotIn("Public Figure", sample["speaker_id"])
            self.assertEqual(audio.read_bytes(), before)
            self.assertTrue(report["evaluation_ready"])

    def test_spoof_mapping_is_exact_and_unknown_label_is_never_guessed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "spoof.wav").write_bytes(b"valid")
            (root / "fake.wav").write_bytes(b"valid but not enough to infer label")
            _write_metadata(root, [
                {"file": "spoof.wav", "speaker": "Speaker A", "label": "spoof"},
                {"file": "fake.wav", "speaker": "Speaker B", "label": "fake"},
            ])

            manifest, report = ingest_dataset(root, confirm_candidate_schema=True, audio_inspector=_inspector)

            self.assertEqual([row["ground_truth"] for row in manifest["samples"]], ["spoof"])
            self.assertEqual(manifest["samples"][0]["source_type"], "synthetic_speech")
            self.assertEqual(report["issue_counts"], {"unknown_label": 1})
            self.assertFalse(report["evaluation_ready"])

    def test_missing_corrupt_silent_duplicate_and_unsupported_audio_are_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "good.wav").write_bytes(b"good")
            (root / "copy.wav").write_bytes(b"good")
            (root / "broken.wav").write_bytes(b"corrupt")
            (root / "quiet.wav").write_bytes(b"silent")
            (root / "unsupported.txt").write_bytes(b"text")
            _write_metadata(root, [
                {"file": "good.wav", "speaker": "A", "label": "bona-fide"},
                {"file": "copy.wav", "speaker": "B", "label": "spoof"},
                {"file": "missing.wav", "speaker": "C", "label": "spoof"},
                {"file": "broken.wav", "speaker": "D", "label": "spoof"},
                {"file": "quiet.wav", "speaker": "E", "label": "bona-fide"},
                {"file": "unsupported.txt", "speaker": "F", "label": "spoof"},
            ])

            manifest, report = ingest_dataset(root, confirm_candidate_schema=True, audio_inspector=_inspector)

            self.assertEqual(len(manifest["samples"]), 1)
            self.assertEqual(report["issue_counts"], {
                "duplicate_content": 1,
                "missing_audio": 1,
                "corrupt_audio": 1,
                "silent_audio": 1,
                "unsupported_audio": 1,
            })
            self.assertFalse(report["evaluation_ready"])

    def test_refuses_unverified_metadata_headers_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_metadata(root, [{"filename": "a.wav", "speaker": "A", "label": "spoof"}], columns=("filename", "speaker", "label"))
            with self.assertRaises(MetadataFormatError):
                ingest_dataset(root, audio_inspector=_inspector)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_metadata(root, [{"file": "../outside.wav", "speaker": "A", "label": "spoof"}])
            manifest, report = ingest_dataset(root, confirm_candidate_schema=True, audio_inspector=_inspector)
            self.assertEqual(manifest["samples"], [])
            self.assertEqual(report["issue_counts"], {"path_traversal": 1})

    def test_missing_metadata_fails_without_guessing_an_archive_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(MetadataFormatError):
                ingest_dataset(Path(temporary), audio_inspector=_inspector)

    def test_candidate_schema_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample.wav").write_bytes(b"valid")
            _write_metadata(root, [{"file": "sample.wav", "speaker": "A", "label": "spoof"}])

            _manifest, report = ingest_dataset(root, audio_inspector=_inspector)

            self.assertEqual(report["metadata_schema_status"], "unconfirmed_candidate")
            self.assertIn("schema_confirmation_required", report["issue_counts"])
            self.assertFalse(report["evaluation_ready"])


if __name__ == "__main__":
    unittest.main()
