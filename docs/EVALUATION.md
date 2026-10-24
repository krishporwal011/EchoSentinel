# EchoSentinel offline evaluation

This workflow evaluates the existing detector locally. It does not change the
production threshold, model, API, or frontend. Model scores are uncalibrated
screening outputs. Metrics from the bundled fixtures describe only those
fixtures and are not estimates of real-world performance.

## Manifest

Use a version 1 JSON document matching
[`tests/audio/manifest.schema.json`](../tests/audio/manifest.schema.json):

```json
{
  "schema_version": 1,
  "samples": [
    {
      "sample_id": "opaque-sample-001",
      "audio_path": "audio/opaque-sample-001.wav",
      "ground_truth": "bonafide",
      "source_type": "human_recording",
      "speaker_id": null,
      "source_recording_id": null,
      "synthetic_generator": null,
      "synthetic_generator_version": null,
      "language": null,
      "codec": "wav",
      "sample_rate": 16000,
      "recording_conditions": ["unknown"],
      "dataset_source": "dataset name or unknown",
      "provenance": "unknown",
      "consent_status": "unknown",
      "partition": "development",
      "notes": "",
      "uncertainty": "Speaker identity and provenance not documented."
    }
  ]
}
```

All schema fields must be present. Use JSON `null` or the literal string
`unknown` when a scalar is unavailable, and `['unknown']` for unavailable
recording conditions. `not_applicable` is appropriate only when the field truly
does not apply (for example, a synthetic generator for a known human recording).
Do not infer a person’s identity from a filename; use opaque sample IDs and
anonymous speaker-group IDs. Keep names, contact details, and private notes out
of evaluation reports.

Keep the manifest with its dataset version. Record the dataset source, original
provenance, and permitted-use/consent status when known. Do not overwrite the
ground-truth label merely because the model disagrees. Speaker and source IDs
are scoped by `dataset_source`; IDs that are unknown are not treated as distinct
and prevent a complete independence check.

The checked-in `tests/audio/evaluation_manifest.json` describes the existing
24 fixture files. Its labels follow the existing directory labels, partition is
`development` because the samples have already been repeatedly inspected, and
undocumented source, identity, language, and consent fields remain unknown.

## Live API decision labels and score meaning

The live `/detect` response schema supports three labels:

* `likely_human_recorded` means the model's bonafide score is higher than its
  spoof score. It is not proof that a recording is genuine or that the speaker
  is who they claim to be.
* `inconclusive` is returned when the spoof score is equal to or higher than the
  bonafide score. The current checkpoint has produced false positives on the
  bundled development fixtures, and there is no representative validation or
  probability calibration that supports an AI-generated classification.
* `likely_ai_generated` would mean an approved, validated decision policy
  classifies the recording as likely synthetic; it would not be proof. The value
  is included in the public response schema for compatibility, but the current
  live decision policy does not emit it. A future policy should only do so after
  a separate validation plan establishes and approves suitable criteria.

The model's softmax outputs are uncalibrated scores, not calibrated
real-world probabilities, confidence estimates, accuracy rates, or proof of
authenticity. The API therefore reports `confidence: null`. The 24 bundled
clips are a development fixture set and cannot establish real-world
generalization or production accuracy.

Demo-mode results are simulated examples. They do not analyze an uploaded file
and must not be interpreted as actual model inference or evaluation results.

## Validate and evaluate

Run from the repository root with an environment containing the project's
audio and model dependencies. Offline mode prevents Hugging Face downloads:

```bash
HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 \
  /path/to/backend/venv/bin/python tests/validate_dataset.py \
  --manifest tests/audio/evaluation_manifest.json \
  --dataset-root tests/audio \
  --report /tmp/echosentinel-validation.json

HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 \
  /path/to/backend/venv/bin/python tests/evaluate_detector.py \
  --manifest tests/audio/evaluation_manifest.json \
  --dataset-root tests/audio \
  --partition development \
  --output-dir /tmp/echosentinel-evaluation
```

The evaluator writes `per_sample_predictions.csv` and
`evaluation_summary.json`. The CSV reports sample IDs, outputs, source/model
audio dimensions, and available heuristic quality measurements. It excludes
speaker and source-recording identifiers. JSON includes a confusion matrix,
rates, Wilson intervals for binomial rates, grouped metrics by documented
recording condition, generator, and language, plus false-positive and
false-negative sample IDs. Undefined rates and AUC are JSON `null`; AUC is only
computed when both classes and valid scores are present.

### Reproducible offline run for the bundled development fixtures

The checked-in manifest is schema version 1 and currently contains 24 entries:
12 `bonafide` and 12 `spoof`, all assigned to `development`. Every manifest
path is relative to `tests/audio`; confirm the files are present before running.
Do not select `validation` or `test` for this fixture set: it has no samples in
those partitions. This is a compatibility/baseline run, not independent or
representative performance evidence.

The evaluator imports `torch`, `transformers`, `librosa`, `soundfile`, `numpy`,
and `certifi` through the existing model and audio-processing modules. Install
or provision the project-pinned packages from `backend/requirements.txt` in a
compatible environment before running; `torch` is specified there as
`torch>=2.4.0`. `pytest` is not needed to run the evaluator itself. `scikit-learn`
is optional and only enables ROC-AUC; without it the report records ROC-AUC as
unavailable. The project documents Python 3.10–3.13, but the current system
environment has not been validated for inference because the required ML/audio
packages are absent.

Run from the repository root. Point `MODEL_ID` at the already cached checkpoint
directory, enable offline mode for both Hugging Face components, and create a
new report directory so existing reports are not overwritten:

```bash
MODEL_ID="$HOME/.cache/huggingface/hub/models--HyperMoon--wav2vec2-base-960h-finetuned-deepfake/snapshots/c73de548282dd35b6dec0844b924e3a931f3abfc"
test -f "$MODEL_ID/config.json" && test -f "$MODEL_ID/preprocessor_config.json" && test -f "$MODEL_ID/pytorch_model.bin"
OUTPUT_DIR="$(mktemp -d /tmp/echosentinel-evaluation.XXXXXX)"
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MODEL_ID="$MODEL_ID" PYTHONDONTWRITEBYTECODE=1 \
  /path/to/compatible/python tests/evaluate_detector.py \
  --manifest tests/audio/evaluation_manifest.json \
  --dataset-root tests/audio \
  --partition development \
  --output-dir "$OUTPUT_DIR"
```

Using the cached snapshot path as `MODEL_ID` makes the model loader resolve a
local directory; the offline environment flags also make missing cache files
fail instead of fetching them. Replace `/path/to/compatible/python` with the
interpreter whose required packages are already available. On completion, keep
the printed output directory and verify it contains `per_sample_predictions.csv`
and `evaluation_summary.json`. Confirm the JSON has `partition: "development"`,
24 sample predictions, both classes, nonzero inference coverage, and the model
revision/label mapping you expect. Treat the scores as uncalibrated model
outputs and quality indicators as separate signal measurements. If loading or
any sample inference fails, the evaluator exits with an error; do not interpret
a partial or absent report as a successful evaluation. The historical metrics
in the README remain historical until this command completes successfully.

The validator checks required metadata fields, labels, unique IDs, safe paths
(including symlinks), decodability, source duration/rate, sample-rate metadata,
SHA-256 duplicates, and known speaker/source-recording partition leakage. It
reports unknown provenance and consent rather than filling them in. No
near-duplicate detector is included because the installed project has no
validated audio fingerprinting method; byte-identical files are checked.

## Threshold exploration

Threshold exploration only accepts a manifest selection explicitly marked
`validation`:

```bash
HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 \
  /path/to/backend/venv/bin/python tests/evaluate_detector.py \
  --manifest path/to/manifest.json --dataset-root path/to/audio \
  --partition validation --threshold-sweep \
  --output-dir /tmp/echosentinel-validation-sweep
```

The development or final test partition cannot be used for this mode. A
threshold tradeoff is exploratory until evaluated on a suitable independent
test set. Keep the final test partition untouched while making model or
threshold choices. A screening tool should report both missed synthetic speech
and false alarms on genuine speech; the preferred tradeoff depends on the
deployment context and must be defined before evaluating the final test set.

## Held-out evaluation protocol

Build partitions by known speaker and source-recording IDs so the same person
or source recording cannot cross development, validation, and test. Include
multiple human speakers, microphones, rooms, noise levels, codecs, and
languages, and synthetic samples from multiple documented generators and
versions. Favor sources and conditions not used during development. Preserve
source and transformation provenance so clean and degraded variants cannot
silently leak across partitions. Use hashes for exact duplicates and add a
validated perceptual fingerprinting process before claiming near-duplicate
independence.

Record class balance and intended use. Report per-class confusion counts, FPR,
FNR, precision, recall, F1, accuracy, ROC-AUC where defined, and uncertainty
intervals with denominators. Keep the test set untouched during threshold
selection. The current 24 local fixtures are too small and undocumented to
support model selection, score calibration, or claims about all AI speech.

## Offline detector comparison adapters

The comparison adapters live in `tests/detector_adapters.py`. They are used
only by the test/evaluation tooling and are not connected to the production API.
The shared contract accepts a one-dimensional mono `float32` waveform and its
sample rate, has an explicit `ModelMetadata` record, and returns a predicted
label, native scores, score type, score direction, and inference time. The
contract distinguishes logits, uncalibrated softmax/sigmoid scores, calibrated
probabilities, and model-native scores. A scalar spoof score remains a scalar;
the evaluator never manufactures a bonafide score.

Adapters register in `REGISTRY` with a unique detector ID. An available adapter
must validate the waveform/sample rate, load the configured local checkpoint,
verify its pinned revision and label semantics, and raise a structured
`DetectorAdapterError` for load, unsupported-input, or inference failures.
Metadata-only adapters use `status="not_evaluated"` with a reason until local
weights and all checkpoint-specific details are verified. Do not add a guessed
class mapping to make an unavailable model appear runnable.

The existing current detector adapter pins revision
`c73de548282dd35b6dec0844b924e3a931f3abfc` and checks the loaded checkpoint
revision after loading from the cache. Offline mode is enforced before loading.
Its source/license field is explicitly marked for review because the local
project does not document the model card license. Alternative adapters are
registered but unavailable when weights are not present; they are not fetched.

Run the current detector plus the registered candidates through the existing
evaluator:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 \
  /path/to/backend/venv/bin/python tests/evaluate_detector.py \
  --manifest tests/audio/evaluation_manifest.json \
  --dataset-root tests/audio --partition development \
  --detectors current,sara1708_wav2vec2,aasist_l \
  --output-dir /tmp/echosentinel-model-comparison
```

The comparison writes `model_comparison.json`. Choose one ID for a single-model
run or several comma-separated IDs for multiple adapters. The top-level model
summary gives status, samples in scope, attempts, successful and failed
inferences, coverage, failure reasons, metrics, preprocessing, and timing. Each
sample has a row per selected detector, including structured errors or an
explicit `not_evaluated` state. Grouped false-positive/false-negative
summaries are included where recording-condition, generator, or language
metadata is present. Pairwise metrics are computed only on samples
successfully processed by both models in that pair; separate model metrics also
show each model's successful subset and coverage. Model-provided decisions are
used as-is; this mode does not tune thresholds. Threshold sweeps remain
restricted to the existing validation-only path.

On CPU, the comparison records model load time, first inference after load, and
warm p50/p95 inference times. These are descriptive measurements for the run;
use a controlled duration mix and repeated runs before making deployment
claims. Peak memory is reported as unmeasured because this runner has no
reliable per-model peak-memory measurement. It does not assume MPS is available
or faster. Models should be pinned by immutable revision and checkpoint hash;
the runner refuses the current adapter if its loaded revision does not match
the configured pin.

To add an independent dataset, create a new manifest using
`tests/audio/manifest.schema.json`, retain opaque sample IDs, document source,
provenance, consent, labels, speaker and source-recording groups, generator and
version, codec, language, and conditions, then assign development/validation/
test groups without speaker/source overlap. Keep final test data untouched
until the model, threshold, and any calibration are locked. Review dataset and
model terms before use. Run the manifest validator and check exact duplicates;
add an independently validated perceptual duplicate check before claiming
near-duplicate independence.

The bundled 24 fixtures remain development-only compatibility/baseline data.
Their undocumented speaker/source metadata prevents verifying independent
generalization, and their metrics are not real-world performance.

## Running tests with the current system Python

The repository does not require a virtualenv for its standard-library-only
ingestion regression tests. Run those without installing packages:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/run_safe_tests.py
```

The runner executes `tests/test_ingest_in_the_wild.py` and lists dependency-
blocked test modules as `SKIP`; skipped modules are not reported as passed.
The full evaluation and audio-dependent validator require `torch`,
`transformers`, `librosa`, and `soundfile` in a compatible environment. The
current interpreter lacks these dependencies, so this command does not run
model inference and cannot refresh the 24-fixture baseline. The checked-in
baseline numbers remain historical fixture results, not a fresh evaluation.

The frontend request-state regression tests can run independently with the
project's already-installed Node dependencies:

```bash
cd frontend
node --experimental-strip-types --test tests/*.test.mjs
```

## Local In-The-Wild ingestion

The local-only importer is `tests/ingest_in_the_wild.py`. The original owner
repository documents one full ZIP, not its internal metadata filename, column
names, label strings, or extracted folder layout. A separate
[benchmark re-packaging script](https://huggingface.co/datasets/SpeechAntiSpoofingBenchmarks/InTheWild/blob/main/build_parquet.py)
reports a candidate source format `meta.csv` with `file,speaker,label`, exact
labels `bona-fide` and `spoof`, and 16 kHz mono float WAV inputs. This is
dataset-specific corroboration, not the original owner's archive specification.
The importer fails closed for other schemas and defaults to
`evaluation_ready=false`; pass `--confirm-candidate-schema` only after checking
the actual local metadata against that candidate. Filenames never determine
class labels.

```bash
python3 tests/ingest_in_the_wild.py \
  --dataset-dir /path/to/local/release_in_the_wild \
  --manifest /path/to/reports/in_the_wild_manifest.json \
  --report /path/to/reports/in_the_wild_ingestion.json \
  --partition development \
  --confirm-candidate-schema

python3 tests/validate_dataset.py \
  --manifest /path/to/reports/in_the_wild_manifest.json \
  --dataset-root /path/to/local/release_in_the_wild

HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python3 tests/evaluate_detector.py \
  --manifest /path/to/reports/in_the_wild_manifest.json \
  --dataset-root /path/to/local/release_in_the_wild \
  --partition development --detectors current \
  --output-dir /path/to/reports/in_the_wild_baseline
```

The manifest references source audio in place; it does not move or rewrite
audio. Speaker names are converted to stable opaque IDs for group analysis.
The report records sample rates and durations, available speaker/source/
generator fields, exact byte duplicates, and missing, unsupported, corrupt,
silent, or otherwise invalid samples. Problem samples are omitted from the
evaluator-compatible manifest and detailed in the report; any issue makes
`evaluation_ready` false, so review/fix the local data before evaluation. The
audio decode check uses the same local preprocessing entry point as production.
The default partition is `development` because the source release does not
document train/validation/test splits. This dataset is intended for evaluation;
do not use its records for fine-tuning and then report evaluation on those same
records. Unknown speaker/source separation and unknown training-data overlap
must be reported as limitations.

The original Fraunhofer page reports 37.9 hours of audio and an Apache 2.0
dataset/documentation license. The [`mueller91/In-The-Wild` Hugging Face card](https://huggingface.co/datasets/mueller91/In-The-Wild)
reports CC-BY-SA-4.0. The terms conflict; resolve the license and underlying
recording-rights questions before use. The original repository contains only
`release_in_the_wild.zip`, currently listed as 8,161,489,023 bytes (8.16 GB / 
7.60 GiB) by Hugging Face. The owner card says its download options retrieve
the full ZIP; no official per-recording download is documented. At 37.9 hours,
16 kHz mono float32 WAVs would occupy about 8.13 GiB uncompressed (estimate
based on the re-packaging script's source-audio description). Keeping the ZIP
while extracting therefore needs at least about 15.7 GiB, before temporary
files, filesystem headroom, and reports. Reserve at least 20 GiB free; allow
roughly 28 GiB if a separate full-size download staging copy is also kept.

### File-level exploratory subset option

The original owner repo offers no documented file-level audio endpoint. A
separate [SpeechAntiSpoofingBenchmarks re-packaging](https://huggingface.co/datasets/SpeechAntiSpoofingBenchmarks/InTheWild)
does publish eight audio-bearing Parquet shards with `path`, `audio`, `label`,
and `notes`; its builder documents the `audio` bytes and label mapping. Each
shard is about 278–285 MB, and the repo advertises Apache 2.0, but this is a
third-party re-packaging and the license discrepancy above still needs review.
The Hugging Face dataset-server preview has not been treated as an audio
download method. A feature-schema probe returned 404; therefore no audio bytes
or row previews were fetched during this task.

After license review and once a Parquet reader is available, an exact
file-level option is to download one pinned shard only, then inspect its local
labels/speaker groups and select a stratified sample from it. For example, the
current pinned repository revision is
`f36fbe7e4e009e444a4985c66d76ab1d9439f901`; shard 0 is 282,098,059 bytes with
SHA-256 `fbf8ffc7966278b07b7afbaa32d6e68215c241a2f97ef7e68391aec03e3a4ce7`:

```bash
curl -L --fail \
  -o /path/to/staging/itw-test-00000-of-00008.parquet \
  https://huggingface.co/datasets/SpeechAntiSpoofingBenchmarks/InTheWild/resolve/f36fbe7e4e009e444a4985c66d76ab1d9439f901/data/test-00000-of-00008.parquet
shasum -a 256 /path/to/staging/itw-test-00000-of-00008.parquet
```

Do not assume one shard contains both classes or enough distinct speakers.
Inspect its label/speaker counts first; if needed, fetch another pinned shard
after checking its size/hash in the repository API. Select approximately 50
bonafide and 50 spoof clips across as many speaker groups as the available
shard permits, using a recorded deterministic seed. Keep every selected
In-The-Wild clip out of training. A 100-clip result is an exploratory check
only, not a real-world performance estimate. This route requires accepting the
re-packaging and license provenance; it is not equivalent to verifying the
original archive's internal schema.

## Future fine-tuning

`docs/FINE_TUNING_PLAN.md` describes the isolated training requirements, and
`configs/finetune.example.json` is an inactive template. No training script is
currently present. The existing checkpoint is a two-class
`Wav2Vec2ForSequenceClassification` model with `bonafide` index 0 and `spoof`
index 1, so it is architecturally fine-tunable; current Python environment
availability and dataset separation still determine whether an experiment can
actually run. Keep any new checkpoint outside `backend/models` until it passes
the documented independent evaluation and review.
