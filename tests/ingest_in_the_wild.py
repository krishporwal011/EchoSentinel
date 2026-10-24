#!/usr/bin/env python3
"""Create an EchoSentinel manifest from a locally inspected In-The-Wild release.

The dataset owner's card documents a ZIP archive but not its internal
metadata schema. A separate benchmark re-packaging script reports a candidate
``meta.csv`` format (``file,speaker,label``; labels ``bona-fide`` / ``spoof``).
The candidate must be confirmed against the local archive before this tool
marks the manifest evaluation-ready. Audio is referenced in place.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path, PureWindowsPath
from typing import Any, Callable


DATASET_NAME = "mueller91/In-The-Wild"
DATASET_PAGE = "https://deepfake-demo.aisec.fraunhofer.de/in_the_wild"
OWNER_REPOSITORY = "https://huggingface.co/datasets/mueller91/In-The-Wild"
SCHEMA_EVIDENCE_URL = "https://huggingface.co/datasets/SpeechAntiSpoofingBenchmarks/InTheWild/blob/main/build_parquet.py"
METADATA_FILENAME = "meta.csv"
REQUIRED_METADATA_COLUMNS = {"file", "speaker", "label"}
LABEL_MAP = {"bona-fide": "bonafide", "spoof": "spoof"}
SUPPORTED_AUDIO_SUFFIXES = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".wma"}
VALID_PARTITIONS = {"development", "validation", "test"}


class MetadataFormatError(ValueError):
    """The local dataset catalogue does not match a verified format."""


def _default_audio_inspector(path: Path) -> dict[str, Any]:
    """Use EchoSentinel's production decoder and preprocessing validation."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from audio_processor import decode_and_preprocess_audio

    _, details = decode_and_preprocess_audio(path.read_bytes(), return_details=True)
    return {
        "sample_rate": int(details["source_sample_rate"]),
        "duration_seconds": float(details["duration_seconds"]),
        "channels": int(details["channels"]),
    }


def _opaque_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def _safe_audio_path(dataset_root: Path, raw_path: str) -> tuple[Path | None, str | None]:
    candidate = Path(raw_path)
    if not raw_path or candidate.is_absolute() or PureWindowsPath(raw_path).is_absolute():
        return None, "invalid_audio_path"
    resolved = (dataset_root / candidate).resolve()
    if not resolved.is_relative_to(dataset_root):
        return None, "path_traversal"
    return resolved, None


def _read_catalogue(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        raise MetadataFormatError(
            f"Expected {METADATA_FILENAME} directly inside the selected dataset directory. "
            "Set --dataset-dir to the directory that contains the actual metadata file; "
            "the importer does not guess archive layouts."
        )
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            missing = sorted(REQUIRED_METADATA_COLUMNS - fields)
            if missing:
                raise MetadataFormatError(
                    f"Unsupported meta.csv header; missing required columns {missing}. "
                    f"Found {sorted(fields)}. No labels were inferred."
                )
            rows = list(reader)
    except UnicodeDecodeError as exc:
        raise MetadataFormatError("meta.csv is not valid UTF-8 text.") from exc
    except csv.Error as exc:
        raise MetadataFormatError(f"Could not parse meta.csv: {exc}") from exc
    return rows, list(reader.fieldnames or [])


def ingest_dataset(
    dataset_dir: Path,
    *,
    partition: str = "development",
    confirm_candidate_schema: bool = False,
    audio_inspector: Callable[[Path], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a version-1 evaluation manifest and an issue/count report.

    Only metadata rows whose exact label is documented and whose audio passes
    the project's decoder are included in the manifest. Issues remain visible
    in the report; no source files are modified.
    """
    if partition not in VALID_PARTITIONS:
        raise ValueError(f"partition must be one of {sorted(VALID_PARTITIONS)}")
    root = dataset_dir.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("dataset_dir must be an existing directory")
    inspect = audio_inspector or _default_audio_inspector
    catalogue, columns = _read_catalogue(root / METADATA_FILENAME)

    manifest_samples: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    included_label_counts: Counter[str] = Counter()
    generator_values: set[str] = set()
    source_values: set[str] = set()
    seen_files: dict[str, str] = {}
    seen_content: dict[str, str] = {}
    duplicate_groups: dict[str, list[str]] = defaultdict(list)

    if not confirm_candidate_schema:
        issues.append({
            "code": "schema_confirmation_required",
            "message": "The local header and exact label vocabulary must be checked against the inspected archive; the owner card does not document this schema.",
        })

    for index, row in enumerate(catalogue, start=2):
        row_label = (row.get("label") or "").strip()
        ground_truth = LABEL_MAP.get(row_label)
        if ground_truth is None:
            issues.append({"row": index, "code": "unknown_label", "message": "Metadata label is not one of the documented exact values: bona-fide, spoof."})
            continue
        label_counts[ground_truth] += 1

        raw_path = (row.get("file") or "").strip()
        normalized_key = Path(raw_path).as_posix().casefold()
        sample_id = _opaque_id("itw", normalized_key or f"row-{index}")
        if normalized_key in seen_files:
            issues.append({"row": index, "sample_id": sample_id, "code": "duplicate_metadata_path", "duplicate_of": seen_files[normalized_key]})
            continue
        seen_files[normalized_key] = sample_id

        audio_path, path_error = _safe_audio_path(root, raw_path)
        if path_error:
            issues.append({"row": index, "sample_id": sample_id, "code": path_error, "message": "Metadata audio path must resolve inside the selected dataset directory."})
            continue
        if not audio_path.is_file():
            issues.append({"row": index, "sample_id": sample_id, "code": "missing_audio", "message": "Metadata references an audio file that is not present."})
            continue
        if audio_path.suffix.lower() not in SUPPORTED_AUDIO_SUFFIXES:
            issues.append({"row": index, "sample_id": sample_id, "code": "unsupported_audio", "message": f"Unsupported audio extension {audio_path.suffix or '(none)'}."})
            continue

        try:
            content_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
        except OSError as exc:
            issues.append({"row": index, "sample_id": sample_id, "code": "audio_read_error", "message": type(exc).__name__})
            continue
        if content_hash in seen_content:
            if not duplicate_groups[content_hash]:
                duplicate_groups[content_hash].append(seen_content[content_hash])
            duplicate_groups[content_hash].append(sample_id)
            issues.append({"row": index, "sample_id": sample_id, "code": "duplicate_content", "duplicate_of": seen_content[content_hash]})
            continue
        seen_content[content_hash] = sample_id

        try:
            audio_info = inspect(audio_path)
        except Exception as exc:
            message = str(exc).lower()
            code = "silent_audio" if "enough meaningful speech" in message or "silence" in message else "corrupt_audio"
            issues.append({"row": index, "sample_id": sample_id, "code": code, "message": f"Audio could not pass local decode/quality validation ({type(exc).__name__})."})
            continue

        raw_speaker = (row.get("speaker") or "").strip()
        speaker_id = _opaque_id("speaker", raw_speaker) if raw_speaker else None
        generator = (row.get("synthetic_generator") or "").strip() or None
        source_id = (row.get("source_recording_id") or "").strip() or None
        language = (row.get("language") or "en").strip() or "unknown"
        if generator:
            generator_values.add(generator)
        if source_id:
            source_values.add(source_id)

        extra_metadata = {
            key: value.strip()
            for key, value in row.items()
            if key not in REQUIRED_METADATA_COLUMNS and value and value.strip()
        }
        manifest_samples.append({
            "sample_id": sample_id,
            "audio_path": Path(raw_path).as_posix(),
            "ground_truth": ground_truth,
            "source_type": "human_recording" if ground_truth == "bonafide" else "synthetic_speech",
            "speaker_id": speaker_id,
            "source_recording_id": source_id,
            "synthetic_generator": generator if ground_truth == "spoof" else "not_applicable",
            "synthetic_generator_version": (row.get("synthetic_generator_version") or "").strip() or None,
            "language": language,
            "codec": audio_path.suffix.lower().lstrip("."),
            "sample_rate": int(audio_info["sample_rate"]),
            "recording_conditions": ["publicly sourced online audio; per-sample conditions unknown"],
            "dataset_source": DATASET_NAME,
            "provenance": f"Dataset project: {DATASET_PAGE}; labels read from local {METADATA_FILENAME}.",
            "consent_status": "Individual consent and rights in source recordings are not established by this importer; review dataset and source terms.",
            "partition": partition,
            "notes": json.dumps({"source_metadata_columns": columns, "additional_metadata": extra_metadata}, sort_keys=True),
            "uncertainty": "Speaker/source partitions and generator details are only available when explicitly present in local metadata; no filename-based label inference was used.",
            "duration_seconds": float(audio_info["duration_seconds"]),
        })
        included_label_counts[ground_truth] += 1

    # The v1 evaluator schema intentionally has no duration field. Keep duration
    # in the ingestion report keyed by opaque sample ID and emit compatible rows.
    durations = {sample["sample_id"]: sample.pop("duration_seconds") for sample in manifest_samples}
    manifest = {"schema_version": 1, "samples": manifest_samples}
    report = {
        "dataset": DATASET_NAME,
        "metadata_schema_status": "user_confirmed_candidate" if confirm_candidate_schema else "unconfirmed_candidate",
        "metadata_schema_evidence": SCHEMA_EVIDENCE_URL,
        "owner_documentation": OWNER_REPOSITORY,
        "metadata_schema_note": "The owner card documents a single ZIP download, not its internal metadata schema. The expected columns and label strings are corroborated by an independent benchmark re-packaging script and must be checked against this local archive.",
        "dataset_root": root.name,
        "metadata_file": METADATA_FILENAME,
        "metadata_columns": columns,
        "metadata_rows": len(catalogue),
        "metadata_label_counts": {label: label_counts[label] for label in ("bonafide", "spoof")},
        "included_sample_count": len(manifest_samples),
        "included_label_counts": {label: included_label_counts[label] for label in ("bonafide", "spoof")},
        "available_metadata": {
            "speaker": "speaker" in columns and any((row.get("speaker") or "").strip() for row in catalogue),
            "source_recording_id": bool(source_values),
            "synthetic_generator": bool(generator_values),
            "optional_columns": [column for column in columns if column not in REQUIRED_METADATA_COLUMNS],
        },
        "speaker_group_count": len({sample["speaker_id"] for sample in manifest_samples if sample["speaker_id"]}),
        "source_recording_group_count": len(source_values),
        "generator_values": sorted(generator_values),
        "durations_seconds_by_sample_id": durations,
        "duplicate_content_groups": [sorted(group) for group in duplicate_groups.values()],
        "issue_counts": dict(Counter(issue["code"] for issue in issues)),
        "issues": issues,
        "evaluation_ready": bool(manifest_samples) and not issues,
        "limitations": [
            "Metadata rows are included only when the exact documented label and locally decoded audio are available.",
            "Speaker names are converted to stable opaque group IDs; filenames and speaker names are not used as labels.",
            "The source dataset documentation does not establish independent speaker/source partitions or per-sample consent.",
            "Only byte-identical duplicates are detected; no perceptual near-duplicate check is performed.",
        ],
    }
    return manifest, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True, help="Existing local directory containing meta.csv and audio files.")
    parser.add_argument("--manifest", type=Path, help="Output manifest path; defaults to <dataset-dir>/evaluation_manifest.json.")
    parser.add_argument("--report", type=Path, help="Output report path; defaults to <dataset-dir>/ingestion_report.json.")
    parser.add_argument("--partition", choices=sorted(VALID_PARTITIONS), default="development", help="Explicit manifest partition; defaults to development because source splits are not assumed.")
    parser.add_argument("--confirm-candidate-schema", action="store_true", help="Acknowledge that you inspected this local archive and confirmed its metadata header and label values match the candidate schema evidence.")
    args = parser.parse_args()
    manifest_path = args.manifest or args.dataset_dir / "evaluation_manifest.json"
    report_path = args.report or args.dataset_dir / "ingestion_report.json"
    try:
        manifest, report = ingest_dataset(
            args.dataset_dir,
            partition=args.partition,
            confirm_candidate_schema=args.confirm_candidate_schema,
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        parser.exit(2, f"Ingestion failed: {type(exc).__name__}: {exc}\n")
    print(json.dumps({"manifest": str(manifest_path), "report": str(report_path), "included": report["included_sample_count"], "issues": report["issue_counts"], "evaluation_ready": report["evaluation_ready"]}, indent=2))
    return 0 if report["evaluation_ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
