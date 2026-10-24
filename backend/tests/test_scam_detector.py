import pytest
from scam_detector import (
    analyze_scam_intent,
    clean_repetitions,
    merge_chunk_text,
    SessionTranscriptBuffer,
    get_scam_dataset,
    ScamRulesDataset,
)


def test_dataset_loading_and_validation():
    dataset = get_scam_dataset()
    assert len(dataset.rules) >= 100
    assert len(dataset.safety_rules) >= 10
    assert "risk_thresholds" in dataset.config


# Case 1: Direct OTP request
def test_direct_otp_request():
    result = analyze_scam_intent("Please tell me the OTP you received.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level in {"HIGH", "CRITICAL"}
    assert "SENSITIVE_INFORMATION_REQUEST" in result.categories
    assert any("otp" in ind.matched_concept.lower() for ind in result.indicators)


# Case 2: UPI PIN disclosure request
def test_direct_upi_pin_request():
    result = analyze_scam_intent("Enter your UPI PIN to receive the money.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level in {"HIGH", "CRITICAL"}
    assert any(c in result.categories for c in ["UPI_PAYMENT_MANIPULATION", "SUSPICIOUS_INSTRUCTIONS"])


# Case 3: OTP security warning
def test_otp_security_warning():
    result = analyze_scam_intent("Never share your OTP with anyone.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level == "LOW"
    assert "SENSITIVE_INFORMATION_REQUEST" not in result.categories
    assert result.warning_banner is None


# Case 4: Password security warning
def test_password_security_warning():
    result = analyze_scam_intent("Our support team will never ask for your password.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level == "LOW"
    assert "SENSITIVE_INFORMATION_REQUEST" not in result.categories


# Case 5: Educational discussion of scams
def test_educational_scam_discussion():
    result = analyze_scam_intent("Scammers sometimes threaten to block accounts during online fraud.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level == "LOW"
    assert result.warning_banner is None


# Case 6: Reported past OTP request
def test_reported_past_request():
    result = analyze_scam_intent("I received a suspicious call asking for my OTP yesterday.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level == "LOW"
    assert "SENSITIVE_INFORMATION_REQUEST" not in result.categories
    assert any("REPORTED_INCIDENT" in ind.category for ind in result.indicators)


# Case 7: Account-block threat combined with a money transfer
def test_account_block_threat_combined_with_payment():
    result = analyze_scam_intent("Your bank account will be blocked unless you transfer money immediately.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level in {"HIGH", "CRITICAL"}
    assert result.scam_risk_score >= 70
    assert result.warning_banner is not None


# Case 8: Remote access combined with banking instructions
def test_remote_access_with_banking():
    result = analyze_scam_intent("Download AnyDesk right now and share your screen while opening your banking app.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level in {"HIGH", "CRITICAL"}
    assert any(c in result.categories for c in ["REMOTE_ACCESS_SCREEN_SHARING", "SUSPICIOUS_INSTRUCTIONS"])


# Case 9: Negation handling
def test_negation_handling():
    result = analyze_scam_intent("I will never ask you to transfer money to my personal account.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level == "LOW"
    assert result.warning_banner is None


# Case 10: Legitimate bank-support advice
def test_legitimate_bank_advice():
    result = analyze_scam_intent("If you suspect fraud, contact your bank using its official number.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level == "LOW"


# Case 11: Neutral KYC discussion
def test_neutral_kyc_discussion():
    result = analyze_scam_intent("The customer asked whether their KYC was complete.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level == "LOW"
    assert result.warning_banner is None


# Case 12: Hindi/Hinglish OTP request
def test_hinglish_otp_request():
    result = analyze_scam_intent("Apne mobile par aaya hua OTP bataiye.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level in {"HIGH", "CRITICAL"}
    assert "SENSITIVE_INFORMATION_REQUEST" in result.categories


# Case 13: Hindi/Hinglish account-block threat
def test_hinglish_account_block_threat():
    result = analyze_scam_intent("Aapka bank account aaj block ho jayega.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level in {"MEDIUM", "HIGH"}
    assert any(c in result.categories for c in ["ACCOUNT_BLOCK_KYC_THREAT", "URGENCY_AND_THREATS"])


# Case 14: Devanagari phrase handling
def test_devanagari_phrase_handling():
    result = analyze_scam_intent("अपना ओटीपी बताइए।")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level in {"HIGH", "CRITICAL"}
    assert "SENSITIVE_INFORMATION_REQUEST" in result.categories


# Case 15: Refund scam indicators
def test_refund_scam_indicator():
    result = analyze_scam_intent("Enter your UPI PIN to receive the refund.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level in {"HIGH", "CRITICAL"}


# Case 16: Job-related advance payment
def test_job_advance_fee_scam():
    result = analyze_scam_intent("Pay a registration fee to secure your job.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level in {"MEDIUM", "HIGH"}
    assert "JOB_OFFER_SCAM" in result.categories


# Case 17: Investment withdrawal fee
def test_investment_tax_withdrawal_scam():
    result = analyze_scam_intent("You must pay a tax fee before withdrawing your earnings.")
    assert result.status == "ANALYZED"
    assert result.scam_risk_level in {"MEDIUM", "HIGH"}
    assert "INVESTMENT_CRYPTO_SCAM" in result.categories


# Case 18: Repeated phrase deduplication
def test_repeated_phrase_deduplication():
    single_res = analyze_scam_intent("Please tell me your OTP.")
    repeated_res = analyze_scam_intent("Please tell me your OTP. Please tell me your OTP. Please tell me your OTP.")
    # Repeated identical phrases must not inflate risk score or duplicate indicators
    assert len(repeated_res.indicators) == len(single_res.indicators)
    assert repeated_res.scam_risk_score == single_res.scam_risk_score


# Case 19: Multiple independent suspicious indicators
def test_multiple_independent_indicators():
    result = analyze_scam_intent(
        "Congratulations, you have won a cash prize. "
        "Pay the processing fee to receive your reward and install AnyDesk right now."
    )
    assert result.status == "ANALYZED"
    assert result.scam_risk_level in {"HIGH", "CRITICAL"}
    assert len(result.categories) >= 2


# Case 20: Empty transcript
def test_empty_transcript():
    result = analyze_scam_intent("")
    assert result.status == "UNAVAILABLE"
    assert result.scam_risk_level == "UNKNOWN"
    assert result.scam_risk_score is None


# Case 21: Unavailable transcription (None)
def test_none_transcript():
    result = analyze_scam_intent(None)
    assert result.status == "UNAVAILABLE"
    assert result.scam_risk_level == "UNKNOWN"
    assert result.scam_risk_score is None


# Case 22: Ambiguous or incomplete sentence
def test_ambiguous_incomplete_sentence():
    result = analyze_scam_intent("I think that maybe...")
    assert result.status == "UNCERTAIN"
    assert result.scam_risk_level == "UNKNOWN"
    assert result.scam_risk_score is None


# Case 23: Rolling transcript context across chunks
def test_rolling_transcript_buffer():
    session_buf = SessionTranscriptBuffer(session_id="test-session-1")
    # Chunk 1
    t1 = session_buf.add_chunk(sequence_id=1, text="Your bank account will be blocked today.")
    res1 = analyze_scam_intent(t1)
    assert res1.scam_risk_level in {"MEDIUM", "HIGH"}

    # Chunk 2
    t2 = session_buf.add_chunk(sequence_id=2, text="Please tell me your OTP to avoid penalty.")
    res2 = analyze_scam_intent(t2)
    # Combined context contains both account block threat and OTP solicitation -> CRITICAL!
    assert res2.scam_risk_level == "CRITICAL"
    assert res2.scam_risk_score >= 85


# Case 24: Chunk sequence and boundary duplicate handling
def test_chunk_boundary_deduplication():
    merged = merge_chunk_text("Please give me your", "give me your OTP right now")
    assert merged == "Please give me your OTP right now"


# Case 25: Ensuring API failure never produces a SAFE result
def test_failure_never_produces_safe():
    empty_res = analyze_scam_intent("")
    assert empty_res.status == "UNAVAILABLE"
    assert empty_res.scam_risk_level != "LOW"
    assert empty_res.scam_risk_level == "UNKNOWN"


# Case 26: Deduplicating severe speech-to-text repetition loops
def test_clean_repetitions_function():
    repetitive_text = (
        "Namaskar sir, I'm Punjab Nesnal Bank saying "
        + "you are saying " * 40
        + "you are saying you"
    )
    cleaned = clean_repetitions(repetitive_text)
    assert "you are saying you are saying you are saying" not in cleaned
    assert "Punjab Nesnal Bank" in cleaned


# Case 27: User Punjab Nesnal Bank repetitive transcript detects threatening message
def test_user_punjab_nesnal_bank_repetitive_loop():
    repetitive_user_transcript = (
        "Namaskar sir, I'm Punjab Nesnal Bank saying "
        + "you are saying " * 50
    )
    res = analyze_scam_intent(repetitive_user_transcript)
    assert res.scam_risk_level in {"HIGH", "CRITICAL"}
    assert res.scam_risk_score >= 75
    assert res.threat_alert_text is not None
    assert "THREATENING / SUSPICIOUS MESSAGE DETECTED" in res.threat_alert_text
    assert any("Punjab Nesnal Bank" in p or "Punjab National Bank" in p for p in res.detected_threat_phrases)


# Case 28: Punjab National Bank unsolicited money promise threat detection
def test_punjab_national_bank_money_lure_threat_detection():
    transcript = (
        "Namaskar Sir, I am Punjab National Bank saying that you are going to get a lot of money "
        + "and you are going to get a lot of money " * 10
    )
    res = analyze_scam_intent(transcript)
    assert res.scam_risk_level in {"HIGH", "CRITICAL"}
    assert res.scam_risk_score >= 78
    assert res.threat_alert_text == "🚨 THREATENING / SUSPICIOUS MESSAGE DETECTED IN TRANSCRIPT"
    assert "You are going to get a lot of money." in res.detected_threat_phrases or "Get a lot of money." in res.detected_threat_phrases or "going to get a lot of money" in " ".join(res.detected_threat_phrases).lower()


# Case 29: Electricity disconnection scam
def test_electricity_disconnection_scam():
    res = analyze_scam_intent("Your electricity power will be disconnected tonight due to unpaid bill.")
    assert res.scam_risk_level in {"HIGH", "CRITICAL"}
    assert res.scam_risk_score >= 75
    assert res.threat_alert_text is not None


# Case 30: Card CVV request
def test_card_cvv_request():
    res = analyze_scam_intent("Card ke piche ka CVV number bataiye verification ke liye.")
    assert res.scam_risk_level in {"HIGH", "CRITICAL"}
    assert res.scam_risk_score >= 78
    assert res.threat_alert_text is not None


# Case 31: QR code refund trap
def test_qr_code_refund_trap():
    res = analyze_scam_intent("QR code scan karo paise milenge aapke khate me.")
    assert res.scam_risk_level in {"HIGH", "CRITICAL"}
    assert res.scam_risk_score >= 78
    assert res.threat_alert_text is not None


# Case 32: TRAI SIM deactivation threat
def test_trai_sim_deactivation_threat():
    res = analyze_scam_intent("TRAI verification ke liye call kiya hai, aapka SIM band ho jayega.")
    assert res.scam_risk_level in {"HIGH", "CRITICAL"}
    assert res.scam_risk_score >= 75
    assert res.threat_alert_text is not None


# Case 33: Courier illegal drugs threat
def test_courier_drugs_threat():
    res = analyze_scam_intent("Your courier parcel contains illegal drugs and narcotics, police case registered.")
    assert res.scam_risk_level == "CRITICAL"
    assert res.scam_risk_score >= 88
    assert res.threat_alert_text is not None
