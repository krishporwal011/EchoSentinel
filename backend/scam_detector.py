import json
import logging
import os
import re
from typing import Any, Dict, List, Literal, Optional, Set, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("echosentinel.scam_detector")

ScamRiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"]
ScamAnalysisStatus = Literal["ANALYZED", "UNCERTAIN", "UNAVAILABLE"]

SCAM_RULES_PATH = os.path.join(os.path.dirname(__file__), "scam_rules.json")


class ScamIndicator(BaseModel):
    category: str
    matched_concept: str
    evidence: str
    explanation: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"


class ScamAnalysisResult(BaseModel):
    status: ScamAnalysisStatus
    scam_risk_level: ScamRiskLevel
    scam_risk_score: Optional[int] = Field(None, ge=0, le=100)
    categories: List[str] = Field(default_factory=list)
    indicators: List[ScamIndicator] = Field(default_factory=list)
    detected_threat_phrases: List[str] = Field(default_factory=list)
    threat_alert_text: Optional[str] = None
    recommendations: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    warning_banner: Optional[str] = None
    message: str


# -----------------------------------------------------------------------------
# Configurable Scam Rules Dataset Loader & Validator
# -----------------------------------------------------------------------------

class ScamRulesDataset:
    _instance: Optional["ScamRulesDataset"] = None

    def __init__(self, filepath: Optional[str] = None):
        self.filepath = filepath or SCAM_RULES_PATH
        self.rules: List[Dict[str, Any]] = []
        self.safety_rules: List[Dict[str, Any]] = []
        self.config: Dict[str, Any] = {}
        self.compiled_rules: List[Tuple[Dict[str, Any], re.Pattern]] = []
        self.compiled_safety: List[Tuple[Dict[str, Any], re.Pattern]] = []
        self.load_and_validate()

    @classmethod
    def get_instance(cls, filepath: Optional[str] = None) -> "ScamRulesDataset":
        if cls._instance is None or (filepath and filepath != cls._instance.filepath):
            cls._instance = cls(filepath)
        return cls._instance

    def load_and_validate(self):
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Scam rules dataset not found at {self.filepath}")

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            raise ValueError(f"Failed to parse scam_rules.json: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("Malformed scam_rules.json: root must be a JSON object.")

        self.rules = data.get("rules", [])
        self.safety_rules = data.get("safety_rules", [])
        self.config = data.get("config", {})

        if not self.rules or not isinstance(self.rules, list):
            raise ValueError("Malformed scam_rules.json: 'rules' must be a non-empty list.")

        self.compiled_rules = []
        for r in self.rules:
            self._validate_rule(r)
            pat_str = r.get("pattern") or re.escape(r.get("phrase", ""))
            try:
                flags = re.IGNORECASE | re.UNICODE
                c_pat = re.compile(pat_str, flags)
                self.compiled_rules.append((r, c_pat))
            except re.error as re_err:
                raise ValueError(f"Invalid regex in rule {r.get('id')}: {re_err}") from re_err

        self.compiled_safety = []
        for s in self.safety_rules:
            self._validate_safety_rule(s)
            pat_str = s.get("pattern") or re.escape(s.get("phrase", ""))
            try:
                flags = re.IGNORECASE | re.UNICODE
                c_pat = re.compile(pat_str, flags)
                self.compiled_safety.append((s, c_pat))
            except re.error as re_err:
                raise ValueError(f"Invalid regex in safety rule {s.get('id')}: {re_err}") from re_err

        logger.info(
            "Loaded scam rules dataset: %d threat rules, %d safety rules.",
            len(self.compiled_rules),
            len(self.compiled_safety),
        )

    def _validate_rule(self, rule: Dict[str, Any]):
        required_fields = ["id", "category", "phrase", "intent", "severity", "weight"]
        for f in required_fields:
            if f not in rule:
                raise ValueError(f"Malformed rule missing field '{f}': {rule}")
        if rule["severity"].upper() not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError(f"Invalid severity '{rule['severity']}' in rule {rule['id']}")

    def _validate_safety_rule(self, srule: Dict[str, Any]):
        required_fields = ["id", "category", "intent", "phrase", "pattern", "action"]
        for f in required_fields:
            if f not in srule:
                raise ValueError(f"Malformed safety rule missing field '{f}': {srule}")


# Initialize global dataset instance
def get_scam_dataset() -> ScamRulesDataset:
    return ScamRulesDataset.get_instance()


# -----------------------------------------------------------------------------
# Repetition, Hallucination & Duplicate Cleaner
# -----------------------------------------------------------------------------

def clean_repetitions(text: str) -> str:
    """
    Removes repetitive loops, duplicate phrases, and repeated lines commonly
    produced by speech-to-text hallucination loops or boundary streaming overlaps.
    Handles n-gram phrase repetitions (from 16 down to 1 words) and trailing
    cut-off repetition fragments.
    """
    if not text:
        return ""

    text = re.sub(r"[\r\t\f\v ]+", " ", text).strip()

    # 1. Deduplicate consecutive duplicate lines
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    dedup_lines = []
    for line in lines:
        if not dedup_lines or dedup_lines[-1].lower() != line.lower():
            dedup_lines.append(line)
    text = " ".join(dedup_lines)

    # 2. Token-level n-gram collapse (phrases from length 16 down to 1)
    words = text.split()
    for phrase_len in range(16, 0, -1):
        idx = 0
        new_words = []
        while idx < len(words):
            if idx + phrase_len * 2 <= len(words):
                p1 = [w.lower().strip(".,!?\"'।") for w in words[idx : idx + phrase_len]]
                p2 = [w.lower().strip(".,!?\"'।") for w in words[idx + phrase_len : idx + phrase_len * 2]]
                if p1 == p2:
                    new_words.extend(words[idx : idx + phrase_len])
                    idx += phrase_len * 2
                    while idx + phrase_len <= len(words):
                        pNext = [w.lower().strip(".,!?\"'।") for w in words[idx : idx + phrase_len]]
                        if pNext == p1:
                            idx += phrase_len
                        else:
                            break
                    # If trailing incomplete fragment of p1 was cut off at the very end
                    if idx < len(words) and len(words) - idx < phrase_len:
                        rem = [w.lower().strip(".,!?\"'।") for w in words[idx:]]
                        if rem == p1[: len(rem)]:
                            idx = len(words)
                    continue
            new_words.append(words[idx])
            idx += 1
        words = new_words

    res = " ".join(words)
    # Also clean phrases with 'and/or/comma' repetition: 'X and X and X'
    pattern = r"(\b(?:and\s+)?([a-zA-Z0-9\s\']{4,40}))(?:\s*(?:and|,)?\s*\2\b)+"
    res = re.sub(pattern, r"\1", res, flags=re.IGNORECASE)
    # Strip dangling trailing conjunctions left by cut-off loops
    res = re.sub(r"\s+(?:and|or|that)\s*$", "", res, flags=re.IGNORECASE)
    res = re.sub(r"\s+", " ", res).strip()
    return res


# -----------------------------------------------------------------------------
# Rolling Session Transcript Buffer with Boundary Overlap Deduplication
# -----------------------------------------------------------------------------

def merge_chunk_text(existing_text: str, new_chunk_text: str) -> str:
    """
    Combines sequential audio chunk transcripts, detecting and removing
    overlapping words at the boundary to prevent duplicate text, and collapsing repetitions.
    """
    clean_new = clean_repetitions(new_chunk_text.strip())
    clean_existing = clean_repetitions(existing_text.strip())

    if not clean_existing:
        return clean_new
    if not clean_new:
        return clean_existing

    existing_words = clean_existing.split()
    new_words = clean_new.split()

    max_overlap = min(len(existing_words), len(new_words), 10)
    best_overlap = 0

    for k in range(max_overlap, 0, -1):
        left_slice = [w.lower().strip(".,!?\"'।") for w in existing_words[-k:]]
        right_slice = [w.lower().strip(".,!?\"'।") for w in new_words[:k]]
        if left_slice == right_slice:
            best_overlap = k
            break

    if best_overlap > 0:
        merged = existing_words + new_words[best_overlap:]
    else:
        merged = existing_words + new_words

    return clean_repetitions(" ".join(merged))


class SessionTranscriptBuffer:
    """
    Manages session-based rolling transcripts for live microphone streaming chunks.
    Preserves sequence order, handles boundary deduplication, and bounds buffer size.
    """
    def __init__(self, session_id: str = "default", max_words: int = 600):
        self.session_id = session_id
        self.max_words = max_words
        self.chunks: List[Dict[str, Any]] = []
        self.full_transcript = ""

    def add_chunk(self, sequence_id: int, text: str, timestamp: Optional[float] = None) -> str:
        text = clean_repetitions(text.strip())
        if not text:
            return self.full_transcript

        self.chunks.append({
            "sequence_id": sequence_id,
            "text": text,
            "timestamp": timestamp,
        })
        self.full_transcript = clean_repetitions(merge_chunk_text(self.full_transcript, text))

        # Truncate to maximum word bound if stream runs very long
        words = self.full_transcript.split()
        if len(words) > self.max_words:
            self.full_transcript = " ".join(words[-self.max_words:])

        return self.full_transcript

    def reset(self):
        self.chunks.clear()
        self.full_transcript = ""


# In-memory storage for active session buffers
_SESSION_BUFFERS: Dict[str, SessionTranscriptBuffer] = {}


def get_session_buffer(session_id: str) -> SessionTranscriptBuffer:
    if session_id not in _SESSION_BUFFERS:
        _SESSION_BUFFERS[session_id] = SessionTranscriptBuffer(session_id=session_id)
    return _SESSION_BUFFERS[session_id]


# -----------------------------------------------------------------------------
# Text Normalization & Sentence Splitting
# -----------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Normalize whitespace, tabs, and punctuation and remove repeated phrases/lines."""
    return clean_repetitions(text)


def split_sentences(text: str) -> List[str]:
    """
    Splits text into sentences, supporting English punctuation (.!?)
    and Hindi Devanagari danda (।).
    """
    raw = re.split(r"(?<=[.!?।])\s+", text.strip())
    return [s.strip() for s in raw if s.strip()]


# -----------------------------------------------------------------------------
# Context-Aware Scam Intent Detection Engine
# -----------------------------------------------------------------------------

AMBIGUOUS_PATTERNS = [
    r"^(?:hello|hi|yes|no|okay|ok|thanks|thank you|good morning|namaste|ha|haan)$",
    r"^(?:i think that maybe|could be|perhaps|let me see|um+|uh+|wait a second)\b",
    r"^(?:call about|speaking with)\b",
]

QUESTION_PATTERNS = [
    r"\b(?:did|has|have|is|was)\s+(?:anyone|someone|a caller|they)\s+(?:ask|asking|tell|request)\b",
    r"\b(?:why would|should i|do i need to)\s+(?:give|share|enter)\b",
]


def analyze_scam_intent(
    transcript: Optional[str],
    session_id: Optional[str] = None,
    chunk_sequence_id: Optional[int] = None,
) -> ScamAnalysisResult:
    """
    Context-aware, explainable scam intent detection engine using scam_rules.json.
    Analyzes spoken transcript text for social-engineering patterns, sensitive credential
    solicitation, coercion threats, and suspicious instructions.
    Distinguishes genuine threats from security advice, negation, questions, and reports.
    """
    dataset = get_scam_dataset()

    # If streaming session provided, update rolling buffer
    if session_id and chunk_sequence_id is not None and transcript:
        buffer = get_session_buffer(session_id)
        clean_text = buffer.add_chunk(chunk_sequence_id, transcript)
    else:
        clean_text = normalize_text(transcript or "")

    if not clean_text:
        return ScamAnalysisResult(
            status="UNAVAILABLE",
            scam_risk_level="UNKNOWN",
            scam_risk_score=None,
            categories=[],
            indicators=[],
            recommendations=[
                "Upload an audio recording or speak clearly to evaluate conversational scam intent.",
            ],
            limitations=[
                "No spoken transcript text was available for analysis.",
            ],
            warning_banner=None,
            message="No spoken conversation transcript available to analyze.",
        )

    words = clean_text.split()
    word_count = len(words)

    # Check for incomplete or highly ambiguous single phrases
    is_ambiguous = False
    clean_lower = clean_text.lower()
    for amb_pat in AMBIGUOUS_PATTERNS:
        if re.search(amb_pat, clean_lower):
            is_ambiguous = True
            break

    if is_ambiguous or (word_count < dataset.config.get("uncertain_word_count_threshold", 4) and clean_text.endswith("...")):
        return ScamAnalysisResult(
            status="UNCERTAIN",
            scam_risk_level="UNKNOWN",
            scam_risk_score=None,
            categories=[],
            indicators=[],
            recommendations=[
                "Continue listening or provide more conversational context to evaluate intent accurately.",
            ],
            limitations=[
                "Sample is too short or ambiguous to reliably determine caller intent without further speech.",
            ],
            warning_banner=None,
            message="Incomplete or ambiguous conversation sample; insufficient context to determine intent.",
        )

    sentences = split_sentences(clean_text)
    if not sentences:
        sentences = [clean_text]

    detected_indicators: List[ScamIndicator] = []
    detected_threat_phrases: List[str] = []
    seen_rule_ids: Set[str] = set()
    categories_set: Set[str] = set()

    CATEGORY_ALIASES = {
        "REMOTE_ACCESS_SCREEN_SHARING": ["REMOTE_ACCESS_SCREEN_SHARING", "SUSPICIOUS_INSTRUCTIONS"],
        "ACCOUNT_BLOCK_KYC_THREAT": ["ACCOUNT_BLOCK_KYC_THREAT", "URGENCY_AND_THREATS"],
        "URGENCY_FEAR_COERCION": ["URGENCY_FEAR_COERCION", "URGENCY_AND_THREATS"],
        "UPI_PAYMENT_MANIPULATION": ["UPI_PAYMENT_MANIPULATION", "SUSPICIOUS_INSTRUCTIONS"],
        "DIGITAL_ARREST_IMPERSONATION": ["DIGITAL_ARREST_IMPERSONATION", "URGENCY_AND_THREATS"],
        "SENSITIVE_INFORMATION_REQUEST": ["SENSITIVE_INFORMATION_REQUEST"],
    }

    for sentence in sentences:
        s_clean = sentence.strip()
        if not s_clean:
            continue

        # Check safety & negation rules first
        sentence_safety_match = None
        for srule, spat in dataset.compiled_safety:
            if spat.search(s_clean):
                sentence_safety_match = srule
                break

        # Check for safety questions ("Did anyone ask you for your OTP?")
        is_safety_question = False
        for q_pat in QUESTION_PATTERNS:
            if re.search(q_pat, s_clean, re.IGNORECASE):
                is_safety_question = True
                break

        # If a safety rule matched, record its advisory/reporting indicator
        if sentence_safety_match:
            s_id = sentence_safety_match["id"]
            if s_id not in seen_rule_ids:
                seen_rule_ids.add(s_id)
                detected_indicators.append(
                    ScamIndicator(
                        category=sentence_safety_match["category"],
                        matched_concept=f"Security context ({sentence_safety_match['intent']})",
                        evidence=s_clean,
                        explanation=f"Identified safety or contextual advisory pattern: '{sentence_safety_match['phrase']}'",
                        severity="low",
                    )
                )

        # Match against threat rules
        for rule, rpat in dataset.compiled_rules:
            rule_id = rule["id"]
            if rule_id in seen_rule_ids:
                continue

            # Exact phrase (with punctuation stripped) or regex match
            clean_rule_phrase = rule["phrase"].lower().strip(".!?,; ")
            phrase_match = bool(clean_rule_phrase and clean_rule_phrase in s_clean.lower())
            regex_m = rpat.search(s_clean)
            regex_match = bool(regex_m)

            if phrase_match or regex_match:
                category = rule["category"]

                # If sentence has negation, safety warning, question, or past reporting:
                if sentence_safety_match or is_safety_question:
                    seen_rule_ids.add(rule_id)
                    # Threat is suppressed by safety context
                    continue
                else:
                    # Direct un-negated threat rule match!
                    seen_rule_ids.add(rule_id)
                    aliases = CATEGORY_ALIASES.get(category, [category])
                    for a in aliases:
                        categories_set.add(a)

                    raw_subcat = rule.get("subcategory") or ""
                    concept_text = raw_subcat.replace("_", " ").title() if raw_subcat else (rule.get("notes") or rule["phrase"])
                    if "otp" in rule["id"].lower() and "otp" not in concept_text.lower():
                        concept_text = f"OTP Request: {concept_text}"

                    detected_indicators.append(
                        ScamIndicator(
                            category=category,
                            matched_concept=concept_text,
                            evidence=s_clean,
                            explanation=f"Identified potential {rule['category'].lower().replace('_', ' ')} indicator matching '{rule['phrase']}'.",
                            severity=rule["severity"].lower(),
                        )
                    )
                    if regex_m:
                        matched_snippet = regex_m.group(0).strip()
                        if matched_snippet and matched_snippet not in detected_threat_phrases:
                            detected_threat_phrases.append(matched_snippet)
                    if clean_rule_phrase and clean_rule_phrase in s_clean.lower() and clean_rule_phrase not in detected_threat_phrases:
                        detected_threat_phrases.append(clean_rule_phrase)

    # -------------------------------------------------------------------------
    # Scoring & Risk Level Synthesis based on scam_rules.json Configuration
    # -------------------------------------------------------------------------
    active_threat_indicators = [
        ind for ind in detected_indicators
        if ind.category not in {"SECURITY_AWARENESS", "SECURITY_INQUIRY", "REPORTED_INCIDENT", "NEUTRAL_DISCUSSION"}
    ]

    has_credentials = "SENSITIVE_INFORMATION_REQUEST" in categories_set
    has_remote = "REMOTE_ACCESS_SCREEN_SHARING" in categories_set
    has_arrest = "DIGITAL_ARREST_IMPERSONATION" in categories_set
    has_upi = "UPI_PAYMENT_MANIPULATION" in categories_set
    has_block_threat = "ACCOUNT_BLOCK_KYC_THREAT" in categories_set
    has_urgency = "URGENCY_FEAR_COERCION" in categories_set or has_block_threat
    has_job_prize = "JOB_OFFER_SCAM" in categories_set or "PRIZE_LOTTERY_SCAM" in categories_set
    has_invest = "INVESTMENT_CRYPTO_SCAM" in categories_set
    has_refund = "REFUND_DELIVERY_SCAM" in categories_set

    recommendations: List[str] = []
    warning_banner: Optional[str] = None
    threat_alert_text: Optional[str] = (
        "🚨 THREATENING / SUSPICIOUS MESSAGE DETECTED IN TRANSCRIPT"
        if active_threat_indicators
        else None
    )
    status = "ANALYZED"

    # CRITICAL: High-confidence attack combining credentials with coercion, remote control, or digital arrest
    if (has_credentials and (has_urgency or has_remote or has_upi or has_arrest)) or (has_arrest and (has_urgency or has_upi)) or (has_remote and has_credentials):
        scam_risk_level: ScamRiskLevel = "CRITICAL"
        scam_risk_score = 92
        warning_banner = (
            "CRITICAL ALERT: High-confidence social-engineering attack detected. "
            "The conversation combines sensitive credential solicitation with urgency, intimidation, or remote control instructions. "
            "Never share your OTP, UPI PIN, or banking passwords under any circumstance."
        )
        recommendations.extend([
            "Immediately terminate the conversation. Do NOT disclose OTPs, PINs, passwords, or CVV.",
            "Never install remote desktop software (AnyDesk, TeamViewer) or approve unsolicited collect requests.",
            "Verify your account status directly through official bank customer support.",
        ])

    elif has_arrest:
        scam_risk_level = "CRITICAL"
        scam_risk_score = 88
        warning_banner = (
            "CRITICAL WARNING: Potential Digital Arrest / Law Enforcement Impersonation detected. "
            "Police, CBI, Customs, and judges NEVER demand money transfers or video-call interrogations."
        )
        recommendations.extend([
            "Do not transfer funds to any 'verification account' or government clearance account.",
            "Immediately disconnect and dial 1930 (National Cybercrime Helpline in India).",
        ])

    elif has_credentials:
        scam_risk_level = "HIGH"
        scam_risk_score = 78
        warning_banner = (
            "WARNING: Potential credential harvesting detected. "
            "The speaker appears to request sensitive authentication codes. "
            "Legitimate organizations and banks will never request your secret OTP or PIN over the phone."
        )
        recommendations.extend([
            "Do not disclose your OTP, UPI PIN, or banking passwords.",
            "Ask the caller to identify themselves and verify through an official channel.",
        ])

    elif has_remote or has_job_prize or has_invest or has_refund or (len(categories_set) >= 2 and (has_upi or has_urgency)) or any(ind.severity in ("critical", "high") for ind in active_threat_indicators):
        scam_risk_level = "HIGH"
        scam_risk_score = 78
        warning_banner = (
            "THREATENING / SUSPICIOUS MESSAGE DETECTED: Coercion, bank impersonation, or unverified financial solicitations identified."
        )
        recommendations.extend([
            "Do not rush into making payments or downloading software under pressure.",
            "Never install remote desktop software (AnyDesk, TeamViewer) requested during a call.",
            "Verify claims independently before taking any action.",
        ])

    elif active_threat_indicators:
        scam_risk_level = "MEDIUM"
        scam_risk_score = 48
        warning_banner = (
            "SUSPICIOUS MESSAGE: Unusual requests or pressure tactics detected in transcript."
        )
        recommendations.extend([
            "Exercise caution. Pressure tactics and unusual requests often precede fraud.",
            "Verify claims independently through official support channels.",
        ])

    elif detected_indicators:
        # Only safety warnings, educational context, or reported past events
        scam_risk_level = "LOW"
        scam_risk_score = 12
        recommendations.append("Continue standard vigilance when sharing personal information.")

    else:
        # No indicators matched
        if word_count < 4:
            scam_risk_level = "LOW"
            scam_risk_score = 5
            recommendations.append("No suspicious social-engineering patterns detected in short sample.")
        else:
            scam_risk_level = "LOW"
            scam_risk_score = 8
            recommendations.append("No scam intent indicators detected in this conversation transcript.")

    limitations = [
        "Rule-based heuristic risk assessment based on configured phrase patterns and context; not definitive proof of fraud.",
        "Voice authenticity and scam intent are evaluated by independent systems.",
        "Novel dialect variations or unlisted social engineering scripts may not match configured rules.",
    ]

    message = (
        f"Detected {len(active_threat_indicators)} potential scam intent indicator(s) across "
        f"{len(categories_set)} categories."
        if active_threat_indicators
        else "No active social-engineering or credential harvesting requests detected."
    )

    return ScamAnalysisResult(
        status=status,
        scam_risk_level=scam_risk_level,
        scam_risk_score=scam_risk_score,
        categories=sorted(list(categories_set)),
        indicators=detected_indicators,
        detected_threat_phrases=detected_threat_phrases,
        threat_alert_text=threat_alert_text,
        recommendations=recommendations,
        limitations=limitations,
        warning_banner=warning_banner,
        message=message,
    )
