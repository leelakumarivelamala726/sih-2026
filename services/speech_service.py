"""
Ministry of Ayush – Smart MediKiosk
Speech Service & Multilingual Audio Configuration
Government of India / Bharat • Clinical History Platform
"""

from typing import Dict, Any

# BCP-47 Language mappings for Web Speech API (SpeechRecognition & SpeechSynthesis)
SPEECH_LANGUAGES = {
    "en": {"code": "en-IN", "name": "English (India)", "voice_hint": "en-IN"},
    "hi": {"code": "hi-IN", "name": "Hindi (हिंदी)", "voice_hint": "hi-IN"},
    "te": {"code": "te-IN", "name": "Telugu (తెలుగు)", "voice_hint": "te-IN"},
    "ta": {"code": "ta-IN", "name": "Tamil (தமிழ்)", "voice_hint": "ta-IN"},
    "kn": {"code": "kn-IN", "name": "Kannada (ಕನ್ನಡ)", "voice_hint": "kn-IN"},
    "ml": {"code": "ml-IN", "name": "Malayalam (മലയാളം)", "voice_hint": "ml-IN"},
    "mr": {"code": "mr-IN", "name": "Marathi (मराठी)", "voice_hint": "mr-IN"},
    "bn": {"code": "bn-IN", "name": "Bengali (বাংলা)", "voice_hint": "bn-IN"},
    "gu": {"code": "gu-IN", "name": "Gujarati (ગુજરાતી)", "voice_hint": "gu-IN"},
    "pa": {"code": "pa-IN", "name": "Punjabi (ਪੰਜਾਬੀ)", "voice_hint": "pa-IN"},
    "or": {"code": "or-IN", "name": "Odia (ଓଡ଼ିଆ)", "voice_hint": "or-IN"}
}

def get_speech_config(lang: str = "en") -> Dict[str, Any]:
    """Return speech recognition and synthesis parameters for the client."""
    return SPEECH_LANGUAGES.get(lang, SPEECH_LANGUAGES["en"])
