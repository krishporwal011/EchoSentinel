# Controlled fine-tuning plan

This document prepares an offline experiment only. There is no training entry
point in the current project, and no training is performed by the dataset
ingester or evaluator. The live API continues to use the existing configured
checkpoint. Use `configs/finetune.example.json` as an inactive starting
template; replace every data/artifact path and complete the review flags before
writing a future trainer.

## Verified local model capability

The cached snapshot at revision
`c73de548282dd35b6dec0844b924e3a931f3abfc` contains a
`Wav2Vec2ForSequenceClassification` configuration, a PyTorch checkpoint, and a
feature-extractor configuration. Its local `config.json` declares exactly two
classes: `bonafide` index 0 and `spoof` index 1. The production wrapper loads a
sequence-classification head and evaluates with softmax. These facts establish
that this checkpoint is structurally suitable for continued supervised
training. They do not establish training-data provenance, license compatibility,
generalization, or accuracy beyond the existing reported fixture results.

The current environment used for this preparation has no importable `torch`,
`transformers`, `torchaudio`, `librosa`, `soundfile`, `pytest`, or
`scikit-learn`. The project requirements declare PyTorch and Transformers, but
those packages are not installed in this interpreter. Fine-tuning and actual
model inference are therefore unavailable here without a separately prepared
environment. Do not install packages as part of dataset preparation.

## Data contract and separation

Training samples must use the existing v1 evaluation manifest contract and
verified labels only: `bonafide` and `spoof`. Source IDs and speaker IDs should
be stable opaque group identifiers. Partition at the group level before
training: the same speaker, original recording, or related transformed source
must not appear across train, validation, and final test. When generator
metadata exists, reserve at least one generator/version for an explicitly
documented generalization analysis. Do not create splits by random clip alone.

The In-The-Wild dataset is being prepared as an external baseline/evaluation
source. Do not fine-tune on any In-The-Wild clips if results on that same
dataset are to be reported as held-out performance. The existing 24 fixture
clips remain development-only. A 100-sample run is an exploratory pipeline
smoke experiment, not evidence of real-world accuracy or a production model
selection result.

## Required training interface

A future offline trainer should accept a config path and resolve only local
manifest/audio/checkpoint files (`local_files_only=True`, offline environment).
It must validate the manifest, inspect exact duplicate content and known group
leakage, require both classes in train and validation, and stop before training
if any required sample is missing or invalid. Report unsupported, corrupt,
silent, and skipped samples instead of silently dropping them.

Preprocessing must match the production path: decode locally, downmix to mono,
resample to 16 kHz, apply the existing duration and level checks, peak-normalize
to 0.95, then use the checkpoint feature extractor's own configured
normalization. The intended objective is two-class cross-entropy over logits
with class index mapping read from and checked against the checkpoint config.
Do not assume indices if the checkpoint changes. Document any augmentation and
apply it only to training examples; do not use label-dependent transformations.

Use fixed random seeds for Python, NumPy, and PyTorch, deterministic algorithms
where supported, a recorded software/runtime manifest, and a recorded SHA-256
for the source manifest, preprocessing code/config, and output checkpoint.
Log per-epoch train/validation loss and metrics. Select checkpoints and any
threshold only on validation data. Run final evaluation once on untouched test
groups after model and threshold choices are locked. Report class counts,
coverage and failures, confusion matrix, accuracy, precision, recall, F1, FPR,
FNR, ROC-AUC when defined, per-condition errors, latency, and limitations.
Softmax outputs are not calibrated real-world probabilities.

Write every experiment checkpoint and report to a new, uniquely named output
directory outside `backend/models`. Never overwrite the production checkpoint.
An approval gate before production integration must review checkpoint hashes,
label mapping, held-out results, split integrity, license/provenance, false
positive and false negative costs, CPU latency/memory, and rollback behavior.

## MacBook Air M1 resource notes

Wav2Vec2 base has a large feature encoder and transformer stack. CPU fine-tuning
is technically possible but likely slow and memory intensive, particularly if
all encoder layers are updated. Measure a small representative batch before
starting a longer run; use small batches, gradient accumulation, and gradient
checkpointing if supported. MPS behavior is not assumed. If the machine has
insufficient memory or disk, stop rather than deleting caches, source data, or
existing checkpoints. A feature-extractor-frozen experiment can be considered
as a separate exploratory configuration, but it must be identified as such and
compared under the same held-out protocol.

## Storage estimate

The official project page reports about 37.9 hours total. The Hugging Face
owner repository currently lists its one ZIP at 8,161,489,023 bytes (7.60 GiB).
A conservative uncompressed source-audio estimate at 16 kHz, mono, float32 is
about 8.13 GiB (`duration × sample_rate × 4 bytes`), based on the separate
re-packaging script's description of the source WAVs. Keeping the archive
while extracting therefore needs about 15.7 GiB before reports and safety
headroom. Reserve at least 20 GiB free, or roughly 28 GiB if a second full
archive staging copy is retained. Check the exact revision/size before any
future download. No data or model was downloaded in this task.
