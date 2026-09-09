"""
Ministry of Ayush – Smart MediKiosk
Language & Dialect Normalization Service
Government of India / Bharat • Clinical History Platform
"""

import os
import json
import re

DIALECT_FILE = os.path.join(os.path.dirname(__file__), "..", "models", "prakriti_ai", "dialect_mappings.json")

# Load dialect mappings
with open(DIALECT_FILE, 'r', encoding='utf-8') as f:
    DIALECT_MAP = json.load(f)

SUPPORTED_LANGUAGES = {
    "en": {"name": "English", "bcp47": "en-IN", "script": "Latin"},
    "hi": {"name": "Hindi (हिंदी)", "bcp47": "hi-IN", "script": "Devanagari"},
    "te": {"name": "Telugu (తెలుగు)", "bcp47": "te-IN", "script": "Telugu"},
    "ta": {"name": "Tamil (தமிழ்)", "bcp47": "ta-IN", "script": "Tamil"},
    "kn": {"name": "Kannada (ಕನ್ನಡ)", "bcp47": "kn-IN", "script": "Kannada"},
    "ml": {"name": "Malayalam (മലയാളം)", "bcp47": "ml-IN", "script": "Malayalam"},
    "mr": {"name": "Marathi (मराठी)", "bcp47": "mr-IN", "script": "Devanagari"},
    "bn": {"name": "Bengali (বাংলা)", "bcp47": "bn-IN", "script": "Bengali"},
    "gu": {"name": "Gujarati (ગુજરાતી)", "bcp47": "gu-IN", "script": "Gujarati"},
    "pa": {"name": "Punjabi (ਪੰਜਾਬੀ)", "bcp47": "pa-IN", "script": "Gurmukhi"},
    "or": {"name": "Odia (ଓଡ଼ିଆ)", "bcp47": "or-IN", "script": "Odia"}
}

# Regional UI prompts and audio guidance texts
CONSENT_TEXTS = {
    "en": {
        "title": "Patient Consent & Clinical Data Notice",
        "description": "Welcome to Ministry of Ayush Smart MediKiosk. Prakriti-AI will assist you in preparing your clinical history before consulting the physician. The AI does NOT provide a final medical diagnosis and does NOT prescribe medicines. A qualified doctor will review, verify, and finalize your health record.",
        "button": "I Understand and Consent",
        "decline": "Decline & Exit"
    },
    "hi": {
        "title": "रोगी सहमति एवं नैदानिक डेटा सूचना",
        "description": "आयुष मंत्रालय स्मार्ट मेडिकियोस्क में आपका स्वागत है। प्रकृति-एआई डॉक्टर से मिलने से पहले आपका नैदानिक इतिहास तैयार करने में सहायता करेगा। एआई कोई अंतिम निदान या दवा नहीं देता है। एक योग्य डॉक्टर आपके रिकॉर्ड की समीक्षा और पुष्टि करेंगे।",
        "button": "मैं समझता/समझती हूँ और सहमत हूँ",
        "decline": "अस्वीकार करें"
    },
    "te": {
        "title": "రోగి సమ్మతి మరియు వైద్య సమాచార ప్రకటన",
        "description": "ఆయుష్ మంత్రిత్వ శాఖ స్మార్ట్ మెడికియోస్క్‌కు స్వాగతం. ప్రకృతి-AI మీ వైద్యుడిని సంప్రదించడానికి ముందు మీ ఆరోగ్య చరిత్రను సేకరించడంలో సహాయపడుతుంది. AI వ్యాధి నిర్ధారణ లేదా మందుల ప్రిస్క్రిప్షన్ ఇవ్వదు. అర్హత కలిగిన వైద్యుడు ప్రతి వివరాలను సమీక్షించి ధృవీకరిస్తారు.",
        "button": "నేను అర్థం చేసుకున్నాను మరియు అంగీకరిస్తున్నాను",
        "decline": "తిరస్కరించండి"
    }
}

def normalize_dialect_and_slang(text: str, lang: str = "te") -> dict:
    """
    Scans input text for Indian regional dialects and slang expressions.
    Returns normalized clinical concept, detected region, and red flag alert if any.
    Crucially, does NOT alter the original text!
    """
    clean_text = text.lower().strip()
    detected_concepts = []
    red_flag_alert = False

    # Check language dialect map
    lang_key = lang if lang in DIALECT_MAP else "te"
    dialect_data = DIALECT_MAP.get(lang_key, {})

    # Check nested regions (like in Telugu)
    if "dialect_regions" in dialect_data:
        for region_name, phrases in dialect_data["dialect_regions"].items():
            for phrase, info in phrases.items():
                if phrase in clean_text:
                    detected_concepts.append({
                        "original_phrase": phrase,
                        "region": region_name,
                        "standard_term": info.get("standard_term"),
                        "clinical_concept": info.get("clinical_concept"),
                        "system": info.get("system"),
                        "ayush_parameter": info.get("ayush_parameter")
                    })
                    if info.get("red_flag"):
                        red_flag_alert = True
    else:
        # Flat structure (Hindi, Tamil, etc.)
        for phrase, info in dialect_data.items():
            if phrase in clean_text:
                detected_concepts.append({
                    "original_phrase": phrase,
                    "region": "standard",
                    "standard_term": info.get("standard_term"),
                    "clinical_concept": info.get("clinical_concept"),
                    "system": info.get("system"),
                    "ayush_parameter": info.get("ayush_parameter")
                })
                if info.get("red_flag"):
                    red_flag_alert = True

    # Also search across all other supported dialects regardless of selected language tag
    # (patients often mix Telugu, Hindi, and English phrases)
    for other_lang, other_data in DIALECT_MAP.items():
        if other_lang == lang_key:
            continue
        if "dialect_regions" in other_data:
            for region_name, phrases in other_data["dialect_regions"].items():
                for phrase, info in phrases.items():
                    if phrase in clean_text and phrase not in [c["original_phrase"] for c in detected_concepts]:
                        detected_concepts.append({
                            "original_phrase": phrase,
                            "region": f"{other_lang}_{region_name}",
                            "standard_term": info.get("standard_term"),
                            "clinical_concept": info.get("clinical_concept"),
                            "system": info.get("system"),
                            "ayush_parameter": info.get("ayush_parameter")
                        })
                        if info.get("red_flag"):
                            red_flag_alert = True
        else:
            for phrase, info in other_data.items():
                if phrase in clean_text and phrase not in [c["original_phrase"] for c in detected_concepts]:
                    detected_concepts.append({
                        "original_phrase": phrase,
                        "region": other_lang,
                        "standard_term": info.get("standard_term"),
                        "clinical_concept": info.get("clinical_concept"),
                        "system": info.get("system"),
                        "ayush_parameter": info.get("ayush_parameter")
                    })
                    if info.get("red_flag"):
                        red_flag_alert = True

    return {
        "original_text": text,
        "concepts": detected_concepts,
        "red_flag": red_flag_alert
    }

def get_bcp47_code(lang_code: str) -> str:
    """Return browser speech recognition language code."""
    return SUPPORTED_LANGUAGES.get(lang_code, {}).get("bcp47", "en-IN")
