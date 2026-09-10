"""
Ministry of Ayush – Smart MediKiosk
Prakriti-AI Clinical Dialogue & Adaptive Questioning Service
Government of India / Bharat • Clinical History Platform

Safety Principles:
- Prakriti-AI strictly collects, structures, and summarizes history.
- Minimum 10 relevant questions with zero repetition.
- AI NEVER independently prescribes medicines.
- AI NEVER provides a final diagnosis.
- Identifies red flags for immediate physician/triage attention.
"""

import os
AI_API_KEY = os.getenv("AI_API_KEY")

import json
import math
import re
import requests
from typing import Dict, Any, Tuple, Optional, List, Set
from database.db import (
    get_clinical_history,
    update_clinical_history,
    add_transcript,
    get_db_connection
)
from services.language_service import normalize_dialect_and_slang

def get_live_ai_key() -> Optional[str]:
    """Retrieve AI_API_KEY from environment."""
    return os.getenv("AI_API_KEY") or AI_API_KEY

def check_live_ai_status() -> Dict[str, Any]:
    """Check connectivity to live Prakriti-AI backend via AI_API_KEY."""
    key = get_live_ai_key()
    if not key or key == "your_ai_api_key_here":
        return {
            "live_ai_enabled": False,
            "status": "offline_local_mode",
            "message": "AI_API_KEY is not configured. Running in high-reliability local offline mode."
        }
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={key}"
    try:
        resp = requests.post(
            url,
            json={"contents": [{"parts": [{"text": "Ping"}]}]},
            timeout=8
        )
        if resp.status_code == 200:
            return {
                "live_ai_enabled": True,
                "status": "online",
                "provider": "Google Generative AI (Gemini 3.5 Flash)",
                "latency_ms": int(resp.elapsed.total_seconds() * 1000),
                "model": "gemini-3.5-flash"
            }
        else:
            return {
                "live_ai_enabled": False,
                "status": "degraded",
                "http_status": resp.status_code,
                "message": "Fallback to local offline Prakriti-AI engine."
            }
    except Exception as e:
        return {
            "live_ai_enabled": False,
            "status": "offline_fallback",
            "error": str(e),
            "message": "Fallback to local offline Prakriti-AI engine."
        }

def query_live_ai(
    prompt: str,
    system_instruction: Optional[str] = None,
    response_json: bool = False,
    timeout: int = 15
) -> Optional[str]:
    """
    Query the live Google Gemini API using AI_API_KEY.
    Tries stable models in sequence: gemini-3.5-flash, gemini-3-flash-preview, gemini-3.6-flash.
    Returns the string text or None if offline/failed.
    """
    key = get_live_ai_key()
    if not key or key == "your_ai_api_key_here":
        return None

    candidate_models = ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-3.6-flash"]
    
    for model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
        if response_json:
            payload["generationConfig"] = {
                "responseMimeType": "application/json",
                "temperature": 0.2
            }
        else:
            payload["generationConfig"] = {
                "temperature": 0.3
            }

        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
        except Exception:
            continue

    return None

def query_live_ai_patient_turn(
    patient_input: str,
    language: str,
    session_id: int,
    history: dict,
    ai_question_count: int,
    answered_fields: set,
    detected_concepts: list
) -> Optional[Dict[str, Any]]:
    """
    Use live Gemini model with AI_API_KEY to intelligently evaluate patient turn:
    - Extracts multi-entities (symptoms, duration, severity, past conditions, Ayush parameters)
    - Detects emergency red flags
    - Formulates the next compassionate, clinically relevant question in the patient's language
    - STRICT: Never diagnoses or prescribes medicines
    - Guarantees minimum 10 questions before completion
    """
    system_instruction = (
        "You are AYUSH KRITI, an empathetic and intelligent medical case-taking assistant for the Ministry of Ayush Smart MediKiosk in the Government of Bharat.\n"
        "Your duty is to conduct a polite, structured clinical and AYUSH history-taking conversation with the patient before they see the doctor.\n"
        "\nCRITICAL CLINICAL & SAFETY RULES:\n"
        "1. HEALTH-RELATED QUESTIONS ONLY: You are strictly a medical case-taking assistant. Every question you ask MUST have a clear clinical purpose related to understanding the patient's health condition:\n"
        "   - Current health problem & chief complaints\n"
        "   - Nature, duration, onset, severity, and anatomical location of symptoms\n"
        "   - Aggravating and relieving factors, and associated symptoms\n"
        "   - Past medical illnesses, past surgeries, and hospitalizations\n"
        "   - Current medications (allopathic and AYUSH), and drug/food allergies\n"
        "   - Health-relevant lifestyle: sleep, diet, physical activity, and stress/mental wellbeing\n"
        "   - Relevant AYUSH parameters (Agni/digestion, Koshta/bowels, Ama/heaviness, Prakriti/Vikriti constitutional aspects)\n"
        "   NEVER ask general casual questions, entertainment questions, unnecessary social questions, or personal questions unrelated to healthcare.\n"
        "   Before formulating any question, check: 'Is this question medically relevant to understanding the patient's health condition?' If NO, do NOT ask it.\n"
        "2. NON-DIAGNOSTIC SAFETY: NEVER make a definitive medical diagnosis or name a specific disease.\n"
        "3. ZERO PRESCRIPTIONS: NEVER prescribe, recommend, suggest, or name medications, treatments, or dosages independently.\n"
        "4. RED-FLAG DETECTION: Detect critical emergency symptoms (e.g. crushing chest pain, sudden severe breathlessness, hemoptysis, acute paralysis, severe head injury) so the triage desk can be alerted.\n"
        "5. EXACTLY ONE QUESTION AT A TIME: Keep each question concise, caring, and focused.\n"
        "6. ZERO REPETITION: Never re-ask about details or symptoms the patient has already explained.\n"
        "\nSPECIAL TELUGU LANGUAGE (language='te') CONVERSATION RULES:\n"
        "- Communicate in natural, clear, polite, everyday spoken Telugu (సరళమైన, సహజమైన మాట్లాడే తెలుగు) as a caring healthcare professional speaking respectfully to a patient.\n"
        "- Do NOT use awkward literal machine translations from English (e.g., NEVER say 'మీ అసౌకర్యం యొక్క స్వభావాన్ని వివరించగలరా?'; instead say 'మీకు ఉన్న ఇబ్బంది ఎలా అనిపిస్తోంది? మంటగా ఉందా, నొప్పిగా ఉందా, లేక బరువుగా అనిపిస్తుందా?').\n"
        "- Do NOT use 'మీ నిద్ర వ్యవధి ఎంత?'; instead say 'మీరు సాధారణంగా రోజుకు ఎన్ని గంటలు నిద్రపోతారు?'.\n"
        "- Avoid overly formal, literary, or bookish Telugu (గ్రంథిక భాష), and avoid obscure or incorrect regional slang.\n"
        "- Do NOT mix unnecessary English words or sentences into Telugu.\n"
        "- If a common medical term is universally understood in Telugu context (such as షుగర్, బీపీ, ఆపరేషన్, అలర్జీ, మాత్రలు), write it naturally in Telugu.\n"
        "- Ensure respectful patient-friendly honorifics (మీకు, మీరు, చెప్పండి, అనిపిస్తుందా).\n"
        "- Maintain precise clinical meaning with effortless conversational warmth.\n"
        "7. Return strictly valid JSON."
    )

    prompt = f"""
Patient's current message: "{patient_input}"
Patient's language: {language} (Options: en for English, hi for Hindi, te for Telugu, etc.)
Questions asked so far: {ai_question_count}
Currently answered fields in clinical history: {list(answered_fields)}
Existing structured history: {json.dumps(history, default=str)}
Vernacular concepts detected: {json.dumps(detected_concepts, default=str)}

Return a JSON object with:
1. "extracted_entities": key-value dictionary of clinical entities found in the patient's message. Keys can include:
   - "chief_complaint": string (if this is their primary reason for visit)
   - "onset": string (when it started)
   - "duration": string (how long it has lasted)
   - "severity": string (e.g. "Mild", "Moderate", "Severe", or "7/10")
   - "location": string (anatomical region)
   - "aggravating_factors": string (what worsens it)
   - "relieving_factors": string (what relieves it)
   - "associated_symptoms": string (other accompanying symptoms)
   - "past_medical_history": string (chronic conditions like diabetes, HTN, asthma)
   - "past_surgical_history": string (past surgeries)
   - "medication_history": string (current medications)
   - "allergy_history": string (known drug/food allergies)
   - "agni": string ("mandagni" [poor], "tikshnagni" [excessive], "samagni" [balanced], "vishamagni" [irregular])
   - "appetite": string
   - "koshta": string ("krura" [hard/constipated], "mridu" [soft/frequent], "madhyama" [normal])
   - "bowel_habits": string
   - "ama": string ("Sama" [sluggish/heavy/coated tongue] or "Nirama")
   - "nidra": string ("Sound sleep" or "Anidra / Disturbed")
   - "sleep": string
   - "ahara": string (dietary pattern)
   - "vihara": string (physical activity/lifestyle)
   - "manasika": string (stress/anxiety/mental state)
2. "red_flag": boolean (true if emergency symptoms requiring urgent doctor/triage attention are detected)
3. "red_flag_reason": string or null
4. "field_name": string (the clinical field being explored next, e.g. "symptom_nature", "onset_duration", "severity_location", "aggravating_factors", "ayush_agni", "ayush_koshta", "ayush_nidra", etc.)
5. "next_question": string (the next empathetic, medically relevant question in language '{language}'. If completed, provide a courteous closing statement for consultation.)
6. "is_completed": boolean (true ONLY if questions asked so far >= 10 and core clinical history is satisfactorily gathered; otherwise false)
"""

    raw_response = query_live_ai(prompt, system_instruction=system_instruction, response_json=True, timeout=12)
    if not raw_response:
        return None

    try:
        parsed = json.loads(raw_response)
        if isinstance(parsed, dict) and "next_question" in parsed:
            return parsed
    except Exception:
        pass
    return None

# Paths to models & rules
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "prakriti_ai")
CLASSIFIER_PATH = os.path.join(MODEL_DIR, "intent_classifier.json")
ENTITY_RULES_PATH = os.path.join(MODEL_DIR, "entity_rules.json")

# Load trained intent classifier
with open(CLASSIFIER_PATH, "r", encoding="utf-8") as f:
    CLASSIFIER_MODEL = json.load(f)

# Load clinical entity & safety rules
with open(ENTITY_RULES_PATH, "r", encoding="utf-8") as f:
    ENTITY_RULES = json.load(f)

# Comprehensive 20-Stage Clinical & AYUSH Question Ontology
# Telugu questions are crafted in natural, polite, everyday spoken healthcare Telugu (సరళమైన మాట్లాడే తెలుగు)
QUESTION_CATALOG = [
    {
        "field": "chief_complaint",
        "question": {
            "en": "Please tell me what health problem or symptoms you are experiencing today.",
            "hi": "कृपया बताएं कि आज आपको क्या स्वास्थ्य समस्या या लक्षण हो रहे हैं।",
            "te": "నమస్కారం, ఈ రోజు మీకు ఎలాంటి ఆరోగ్య సమస్య లేదా ఇబ్బంది ఉంది? దయచేసి వివరంగా చెప్పండి."
        }
    },
    {
        "field": "symptom_nature",
        "question": {
            "en": "What does the discomfort feel like? Is it sharp, dull, burning, cramping, or throbbing?",
            "hi": "यह दर्द या तकलीफ किस प्रकार की है? क्या इसमें जलन, चुभन, ऐंठन या भारीपन है?",
            "te": "మీకు ఉన్న ఇబ్బంది ఎలా అనిపిస్తోంది? మంటగా ఉందా, నొప్పిగా ఉందా, లేక బరువుగా అనిపిస్తుందా?"
        }
    },
    {
        "field": "onset_duration",
        "question": {
            "en": "When did this problem start, and did it begin suddenly or develop gradually?",
            "hi": "यह समस्या कब शुरू हुई, और क्या यह अचानक हुई या धीरे-धीरे बढ़ी?",
            "te": "ఈ సమస్య ఎప్పటి నుంచి మొదలైంది? ఒక్కసారిగా వచ్చిందా లేక కొద్దికొద్దిగా పెరిగిందా?"
        }
    },
    {
        "field": "severity_location",
        "question": {
            "en": "Where exactly is the symptom located, and on a scale of 1 to 10, how severe is it?",
            "hi": "यह तकलीफ ठीक किस जगह पर है, और 1 से 10 के पैमाने पर यह कितनी तीव्र है?",
            "te": "ఈ బాధ లేదా నొప్పి శరీరంలో సరిగ్గా ఎక్కడ ఉంది? 1 నుండి 10 వరకు చూస్తే తీవ్రత ఎంతవరకు ఉండవచ్చు?"
        }
    },
    {
        "field": "aggravating_factors",
        "question": {
            "en": "What makes your symptoms worse (e.g. eating spicy food, exertion, posture, or weather)?",
            "hi": "किस वजह से तकलीफ बढ़ जाती है (जैसे तीखा खाना, चलने-फिरने से, झुकने से या मौसम से)?",
            "te": "ఏం చేసినప్పుడు మీ సమస్య ఎక్కువగా అనిపిస్తోంది? (ఉదాహరణకు: కారం ఆహారం తిన్నప్పుడు, నడిచినప్పుడు లేదా పడుకున్నప్పుడు?)"
        }
    },
    {
        "field": "relieving_factors",
        "question": {
            "en": "Does anything provide relief (e.g. resting, warm water, lying down, or specific food)?",
            "hi": "किस चीज़ से कुछ आराम मिलता है (जैसे आराम करने से, गर्म पानी से या लेटने से)?",
            "te": "ఏం చేస్తే మీకు కాస్త ఉపశమనం లభిస్తోంది? (విశ్రాంతి తీసుకుంటేనా, వేడి నీళ్లు తాగితేనా, లేక విశ్రాంతిగా పడుకుంటేనా?)"
        }
    },
    {
        "field": "associated_symptoms",
        "question": {
            "en": "Are you experiencing any other symptoms, such as fever, chills, nausea, vomiting, dizziness, or breathlessness?",
            "hi": "क्या बुखार, कंपकंपी, जी मिचलाना, उल्टी, चक्कर या सांस फूलने जैसे कोई अन्य लक्षण भी हैं?",
            "te": "దీనితో పాటు మీకు జ్వరం, చలి, వికారం, వాంతులు, తలతిరగడం లేదా ఆయాసం వంటి ఇతర ఇబ్బందులు ఏమైనా ఉన్నాయా?"
        }
    },
    {
        "field": "previous_episodes",
        "question": {
            "en": "Have you experienced similar episodes in the past, or is this the first time?",
            "hi": "क्या पहले भी आपको ऐसी समस्या हुई है, या यह पहली बार हो रहा है?",
            "te": "గతంలో కూడా మీకు ఇలాంటి సమస్య ఎప్పుడైనా వచ్చిందా, లేక ఇదే మొదటిసారా?"
        }
    },
    {
        "field": "past_medical_history",
        "question": {
            "en": "Do you have any long-term medical conditions like diabetes, high blood pressure, asthma, or thyroid disorders?",
            "hi": "क्या आपको डायबिटीज, हाई ब्लड प्रेशर, दमा या थायरॉइड जैसी कोई पुरानी बीमारी है?",
            "te": "మీకు గతంలో షుగర్ (మధుమేహం), బీపీ (రక్తపోటు), ఆస్తమా లేదా థైరాయిడ్ వంటి దీర్ఘకాలిక సమస్యలు ఏమైనా ఉన్నాయా?"
        }
    },
    {
        "field": "past_surgical_history",
        "question": {
            "en": "Have you undergone any surgeries, major medical procedures, or hospitalizations?",
            "hi": "क्या पहले आपकी कोई सर्जरी, ऑपरेशन या अस्पताल में भर्ती होने का इतिहास है?",
            "te": "గతంలో మీకు ఏదైనా ఆపరేషన్ జరిగిందా? ఎప్పుడైనా ఆసుపత్రిలో చేరాల్సి వచ్చిందా?"
        }
    },
    {
        "field": "current_medications",
        "question": {
            "en": "What medications, tablets, or Ayurvedic herbal remedies are you currently taking?",
            "hi": "वर्तमान में आप कौन सी दवाएं, गोलियां या आयुर्वेदिक औषधियां ले रहे हैं?",
            "te": "మీరు ప్రస్తుతం రోజువారీగా ఏవైనా ఇంగ్లీష్ మందులు, మాత్రలు లేదా ఆయుర్వేద ఔషధాలు వాడుతున్నారా?"
        }
    },
    {
        "field": "allergy_history",
        "question": {
            "en": "Do you have any known allergies to medicines (such as penicillin or pain killers) or foods?",
            "hi": "क्या आपको किसी दवा (जैसे पेनिसिलिन, दर्द निवारक) या खाद्य पदार्थ से कोई एलर्जी है?",
            "te": "మీకు ఏవైనా మందులు లేదా ఆహార పదార్థాల వల్ల అలర్జీ వచ్చే అవకాశం ఉందా?"
        }
    },
    {
        "field": "family_history",
        "question": {
            "en": "Does anyone in your direct family have a history of diabetes, hypertension, heart disease, or asthma?",
            "hi": "क्या आपके परिवार में किसी को डायबिटीज, हृदय रोग, ब्लड प्रेशर या दमे की समस्या रही है?",
            "te": "మీ కుటుంబంలో ఎవరికైనా షుగర్, బీపీ, గుండె జబ్బులు లేదా ఆస్తమా సమస్యలు ఉన్నాయా?"
        }
    },
    {
        "field": "ayush_agni",
        "question": {
            "en": "To assess your digestive fire (Agni): How is your appetite—is it poor (Mandagni), sharp (Tikshnagni), or irregular (Vishamagni)?",
            "hi": "आपकी पाचक अग्नि को समझने के लिए: आपकी भूख कैसी है—कम (मंदाग्नि), बहुत तेज (तीक्ष्णाग्नि) या घटती-बढ़ती (विषमाग्नि)?",
            "te": "మీ జీర్ణశక్తి మరియు ఆకలి ఎలా ఉన్నాయి? ఆకలి తక్కువగా ఉందా, ఎక్కువగా ఉందా, లేదా సమయానికి కాకుండా హెచ్చుతగ్గులుగా ఉందా?"
        }
    },
    {
        "field": "ayush_ama",
        "question": {
            "en": "Do you feel heavy in the abdomen after food, have a coated tongue, bad breath, or sluggishness (Ama signs)?",
            "hi": "क्या भोजन के बाद पेट भारी रहता है, जीभ पर सफेद मैल जमती है या शरीर में भारीपन/आलस रहता है?",
            "te": "భోజనం చేశాక కడుపులో బరువుగా ఉండటం, నాలుకపై తెల్లటి పొర రావడం, లేదా నీరసంగా ఉండటం జరుగుతోందా?"
        }
    },
    {
        "field": "ayush_koshta",
        "question": {
            "en": "How are your bowel habits (Koshta)—are stools hard/infrequent (Krura), soft/frequent (Mridu), or normal once daily?",
            "hi": "पेट साफ होने की स्थिति (कोष्ठ) कैसी है—कब्ज/कड़ा मल, बार-बार ढीला मल, या दिन में एक बार सामान्य रूप से?",
            "te": "మీకు ప్రతిరోజూ మలవిసర్జన (మోషన్) సాఫీగా అవుతోందా? మలబద్ధకం లేదా విరోచనాలు ఏమైనా ఉన్నాయా?"
        }
    },
    {
        "field": "ayush_nidra",
        "question": {
            "en": "How is your sleep (Nidra)—do you fall asleep easily, or do you experience broken sleep or insomnia?",
            "hi": "आपकी नींद (निद्रा) कैसी है—क्या आसानी से नींद आ जाती है, या रात में बार-बार टूटती है/अनिद्रा रहती है?",
            "te": "మీరు సాధారణంగా రోజుకు ఎన్ని గంటలు నిద్రపోతారు? పడుకోగానే నిద్రపడుతుందా, లేదా రాత్రిపూట మెలకువలు వస్తూ నిద్రలేమి ఉందా?"
        }
    },
    {
        "field": "ayush_ahara_vihara",
        "question": {
            "en": "Tell me about your daily routine: What are your regular food habits, and do you engage in regular physical exercise (Vyayama)?",
            "hi": "आपके खान-पान और दिनचर्या के बारे में बताएं: क्या आप नियमित व्यायाम या सैर करते हैं?",
            "te": "మీ ఆహారపు అలవాట్లు మరియు దినచర్య ఎలా ఉంటాయి? రోజూ వ్యాయామం, నడక లేదా యోగా వంటివి చేస్తారా?"
        }
    },
    {
        "field": "ayush_manasika",
        "question": {
            "en": "How has your mental state been recently—are you experiencing excessive stress, anxiety, irritability, or mood swings?",
            "hi": "हाल ही में आपकी मानसिक स्थिति कैसी है—क्या अत्यधिक तनाव, चिंता, चिड़चिड़ापन या उदासी महसूस हो रही है?",
            "te": "ఇటీవల మీ మానసిక స్థితి ఎలా ఉంది? ఎక్కువ మానసిక ఒత్తిడి, ఆందోళన లేదా చిరాకు వంటివి అనిపిస్తున్నాయా?"
        }
    }
]

COMPLETION_MESSAGE = {
    "en": "Thank you. I have structured your comprehensive clinical and AYUSH history for the physician. You may now review or edit your information, scan previous documents, or proceed to consultation.",
    "hi": "धन्यवाद। चिकित्सक के परामर्श हेतु आपका सम्पूर्ण नैदानिक एवं आयुष इतिहास तैयार कर लिया गया है। अब आप अपनी जानकारी की समीक्षा कर सकते हैं या पिछली रिपोर्ट स्कैन कर सकते हैं।",
    "te": "ధన్యవాదాలు. వైద్యుల పరిశీలన కోసం మీ ఆరోగ్య వివరాలు సిద్ధం చేయబడ్డాయి. ఇప్పుడు మీరు మీ వివరాలను సరిచూసుకోవచ్చు లేదా పాత రిపోర్టులు స్కాన్ చేయవచ్చు."
}

def clean_and_tokenize(text: str) -> List[str]:
    """Normalize text and extract unigram + bigram features."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t for t in text.split() if len(t) > 1]
    features = list(tokens)
    for i in range(len(tokens) - 1):
        features.append(f"{tokens[i]}_{tokens[i+1]}")
    return features

def classify_intent(text: str) -> Tuple[str, float]:
    """Run inference against the trained Prakriti-AI model."""
    features = clean_and_tokenize(text)
    total_docs = CLASSIFIER_MODEL["total_docs"]
    class_counts = CLASSIFIER_MODEL["class_counts"]
    feature_counts = CLASSIFIER_MODEL["feature_counts"]
    vocab = set(CLASSIFIER_MODEL["vocabulary"])
    vocab_size = max(len(vocab), 1)

    best_label = "general"
    best_score = -float("inf")

    for label, count in class_counts.items():
        score = math.log(count / total_docs)
        total_features_in_class = sum(feature_counts[label].values()) + vocab_size
        for f in features:
            if f in vocab:
                freq = feature_counts[label].get(f, 0) + 1
                score += math.log(freq / total_features_in_class)
        if score > best_score:
            best_score = score
            best_label = label

    return best_label, best_score

def detect_red_flags(text: str) -> list:
    """Detect critical emergency health indicators for triage safety."""
    detected = []
    text_lower = text.lower()
    for rule in ENTITY_RULES.get("red_flags", []):
        for pattern in rule["pattern"]:
            if pattern in text_lower:
                detected.append({
                    "pattern_matched": pattern,
                    "concern": rule["concern"],
                    "action": rule["action"],
                    "priority": rule["priority"]
                })
                break
    return detected

def extract_multi_entities(text: str) -> Dict[str, Any]:
    """
    Extract multiple clinical entities simultaneously from natural language
    (e.g., duration, severity, location, associated symptoms, AYUSH attributes).
    This prevents asking redundant questions if the patient provides multiple details at once!
    """
    text_lower = text.lower()
    extracted = {}

    # 1. Duration / Onset detection
    duration_match = re.search(
        r"(\d+)\s*(days?|rojulu?|hafte|weeks?|months?|nelalu?|hours?|gantalu?|years?|samvatsaralu?)",
        text_lower
    )
    if duration_match:
        extracted["duration"] = duration_match.group(0)
        extracted["onset"] = f"{duration_match.group(0)} ago"
    elif any(k in text_lower for k in ["since yesterday", "ninna nunchi", "kal se", "from morning", "podununchi"]):
        extracted["duration"] = "1 day / since yesterday"
        extracted["onset"] = "yesterday / recent"

    # 2. Severity detection
    scale_match = re.search(r"\b([1-9]|10)\s*(?:out of 10|/10)\b", text_lower)
    if scale_match:
        extracted["severity"] = f"{scale_match.group(1)}/10"
    elif any(k in text_lower for k in ["severe", "unbearable", "ghoram", "chala ekkuva", "bahut tez"]):
        extracted["severity"] = "Severe (8-9/10)"
    elif any(k in text_lower for k in ["mild", "slight", "konchem", "thoda"]):
        extracted["severity"] = "Mild (2-3/10)"
    elif any(k in text_lower for k in ["moderate", "medium"]):
        extracted["severity"] = "Moderate (5-6/10)"

    # 3. Location detection
    locations = {
        "chest": ["chest", "gunde", "chhati", "seena"],
        "abdomen / stomach": ["stomach", "kadupu", "pet", "abdomen", "belly"],
        "head": ["head", "tala", "sar", "thalakay"],
        "knee / joints": ["knee", "joint", "sandhi", "ghutna", "kaallu", "legs"],
        "lower back": ["back", "venuka", "kamar", "spine"],
        "throat": ["throat", "gonthu", "gala"]
    }
    for loc_name, keywords in locations.items():
        if any(k in text_lower for k in keywords):
            extracted["location"] = loc_name
            break

    # 4. Aggravating triggers
    if any(k in text_lower for k in ["spicy", "karam", "oily", "food", "tinnaka", "khane ke baad", "teekha"]):
        extracted["aggravating_factors"] = "Spicy / oily foods, post-prandial"
    elif any(k in text_lower for k in ["walking", "moving", "nadusthe", "chalte waqt", "exertion"]):
        extracted["aggravating_factors"] = "Physical exertion / walking"

    # 5. Relieving triggers
    if any(k in text_lower for k in ["rest", "lying down", "padukunte", "aaram", "warm water", "challa neellu"]):
        extracted["relieving_factors"] = "Rest / warm fluids"

    # 6. Past medical condition triggers
    past_conditions = []
    if "diabetes" in text_lower or "sugar" in text_lower:
        past_conditions.append("Type 2 Diabetes Mellitus")
    if "bp" in text_lower or "blood pressure" in text_lower or "hypertension" in text_lower:
        past_conditions.append("Hypertension")
    if "asthma" in text_lower or "wheezing" in text_lower:
        past_conditions.append("Bronchial Asthma")
    if "thyroid" in text_lower:
        past_conditions.append("Thyroid Disorder")
    if past_conditions:
        extracted["past_medical_history"] = ", ".join(past_conditions)

    # 7. Surgical history
    if any(k in text_lower for k in ["surgery", "operation", "aparesan"]):
        extracted["past_surgical_history"] = text
    elif "no surgery" in text_lower or "operation avvaledu" in text_lower or "koi surgery nahi" in text_lower:
        extracted["past_surgical_history"] = "Nil surgical history"

    # 8. Medications
    if any(k in text_lower for k in ["tablet", "medicine", "metformin", "paracetamol", "pantoprazole", "mandoo", "goli"]):
        extracted["medication_history"] = text

    # 9. Allergies
    if any(k in text_lower for k in ["allergy", "penicillin", "sulfa"]):
        extracted["allergy_history"] = text
    elif "no allergy" in text_lower or "allergy ledu" in text_lower or "koi allergy nahi" in text_lower:
        extracted["allergy_history"] = "NKDA (No known drug allergies)"

    # 10. AYUSH Parameters
    ayush_rules = ENTITY_RULES.get("ayush_parameters", {})

    # Agni & Appetite
    for agni, indicators in ayush_rules.get("agni_types", {}).items():
        if any(ind in text_lower for ind in indicators):
            extracted["agni"] = agni
            extracted["appetite"] = "Reduced / Poor" if agni == "mandagni" else ("Sharp / Excessive" if agni == "tikshnagni" else "Variable")
            break

    # Koshta & Bowels
    for koshta, indicators in ayush_rules.get("koshtha_types", {}).items():
        if any(ind in text_lower for ind in indicators):
            extracted["koshta"] = koshta
            extracted["bowel_habits"] = f"Koshta: {koshta}"
            break

    # Sleep / Nidra
    if any(k in text_lower for k in ["anidra", "insomnia", "sleepless", "nidra pattatledu", "neend nahi aati", "broken sleep"]):
        extracted["nidra"] = "Disturbed / Anidra"
        extracted["sleep"] = "Disturbed / Insomnia"
    elif any(k in text_lower for k in ["good sleep", "sound sleep", "manchi nidra", "acchi neend"]):
        extracted["nidra"] = "Sukhapurvaka (Sound sleep)"
        extracted["sleep"] = "Sound sleep (6-8 hours)"

    # Ama
    if any(k in text_lower for k in ["heaviness", "coated tongue", "bad breath", "sticky stools", "alasa", "sluggish"]):
        extracted["ama"] = "Sama (Ama present - metabolic sluggishness)"
    elif any(k in text_lower for k in ["lightness", "clear tongue", "no heaviness"]):
        extracted["ama"] = "Nirama (No ama signs)"

    # Manasika
    if any(k in text_lower for k in ["stress", "tension", "anxiety", "worry", "chinta", "anger", "irritability"]):
        extracted["manasika"] = "Rajasika / Stress & Anxiety indicated"

    return extracted

def extract_ayush_attributes(text: str) -> Dict[str, Any]:
    """Extract AYUSH parameters specifically (Agni, Koshta, Prakriti, etc.)."""
    extracted = extract_multi_entities(text)
    return {
        "agni_type": extracted.get("agni", "samagni"),
        "koshtha_type": extracted.get("koshta", "madhyama"),
        "prakriti_features": extracted.get("prakriti", ""),
        "ama": extracted.get("ama", ""),
        "all_extracted": extracted
    }

def get_already_answered_fields(history: dict) -> Set[str]:
    """Identify which clinical fields have already been answered/provided."""
    answered = set()
    if not history:
        return answered

    field_mappings = {
        "chief_complaint": ["chief_complaint"],
        "symptom_nature": ["history_of_present_illness"],
        "onset_duration": ["onset", "duration"],
        "severity_location": ["severity", "location"],
        "aggravating_factors": ["aggravating_factors"],
        "relieving_factors": ["relieving_factors"],
        "associated_symptoms": ["associated_symptoms"],
        "past_medical_history": ["past_medical_history"],
        "past_surgical_history": ["past_surgical_history"],
        "current_medications": ["medication_history"],
        "allergy_history": ["allergy_history"],
        "family_history": ["family_history"],
        "ayush_agni": ["agni", "appetite"],
        "ayush_ama": ["ama"],
        "ayush_koshta": ["koshta", "bowel_habits"],
        "ayush_nidra": ["nidra", "sleep"],
        "ayush_ahara_vihara": ["ahara", "vihara", "diet", "lifestyle"],
        "ayush_manasika": ["manasika"]
    }

    for catalog_field, db_cols in field_mappings.items():
        for col in db_cols:
            val = history.get(col)
            if val and len(str(val).strip()) > 1:
                answered.add(catalog_field)
                break

    return answered

def select_next_question(
    session_id: int,
    history: dict,
    language: str = "en"
) -> Tuple[str, str, bool]:
    """
    Dynamically select the next clinically relevant question:
    1. Check questions already asked in this session (`transcripts` table for AI questions).
    2. Check fields already answered by the patient.
    3. Ensure at least 10 relevant questions are asked before completion.
    4. Return (field_name, question_text, is_completed).
    """
    with get_db_connection() as conn:
        ai_transcripts = conn.execute(
            "SELECT original_transcript FROM transcripts WHERE session_id = ? AND speaker = 'ai'",
            (session_id,)
        ).fetchall()
        ai_question_count = len(ai_transcripts)

    answered_fields = get_already_answered_fields(history)
    lang_key = language if language in ["en", "hi", "te"] else "en"

    # Search QUESTION_CATALOG for the next unasked and unanswered relevant question
    selected_item = None
    for item in QUESTION_CATALOG:
        field = item["field"]
        # If field is already answered, SKIP IT (zero repetition!)
        if field in answered_fields:
            continue
        
        # Also check if this exact question was already asked
        q_text = item["question"].get(lang_key, item["question"]["en"])
        already_asked = any(q_text in row["original_transcript"] for row in ai_transcripts)
        if already_asked:
            continue

        selected_item = item
        break

    # If minimum 10 questions have been asked AND core questions are covered, or catalog exhausted
    MINIMUM_QUESTIONS = 10
    if ai_question_count >= MINIMUM_QUESTIONS and (not selected_item or len(answered_fields) >= 8):
        completion_text = COMPLETION_MESSAGE.get(lang_key, COMPLETION_MESSAGE["en"])
        return ("completed", completion_text, True)

    if selected_item:
        q_text = selected_item["question"].get(lang_key, selected_item["question"]["en"])
        return (selected_item["field"], q_text, False)

    # Fallback if catalog exhausted before 10
    completion_text = COMPLETION_MESSAGE.get(lang_key, COMPLETION_MESSAGE["en"])
    return ("completed", completion_text, True)

def process_patient_turn(
    session_id: int,
    patient_id: int,
    patient_input: str,
    language: str = "en"
) -> Dict[str, Any]:
    """
    Process one turn of patient interaction:
    1. Log patient verbatim statement in transcripts table (NEVER overwrite).
    2. Normalize regional dialect/slangs (e.g. Telugu/Hindi variations).
    3. Detect emergency red flags.
    4. Extract multi-entities (symptoms, duration, severity, AYUSH traits).
    5. Query live Prakriti-AI via AI_API_KEY with robust local fallback.
    6. Update structured clinical_history.
    7. Guarantee at least 10 relevant questions before completion.
    8. Log AI question in transcripts table.
    """
    is_initial_call = (patient_input == "START_SESSION")

    # 1. Log patient verbatim transcript (unless it's just the initial START click)
    if not is_initial_call:
        add_transcript(
            patient_id=patient_id,
            session_id=session_id,
            speaker="patient",
            language=language,
            original_text=patient_input
        )

    # 2. Regional slang and dialect normalization
    norm_result = normalize_dialect_and_slang(patient_input, lang=language) if not is_initial_call else {"concepts": [], "red_flag": False}
    detected_concepts = norm_result.get("concepts", [])

    # 3. Red flag safety evaluation (Local rules)
    red_flags = detect_red_flags(patient_input) if not is_initial_call else []
    if norm_result.get("red_flag"):
        for c in detected_concepts:
            if c.get("red_flag"):
                red_flags.append({
                    "pattern_matched": c["original_phrase"],
                    "concern": f"Regional urgent complaint: {c.get('clinical_concept')}",
                    "action": "Immediate medical attention suggested.",
                    "priority": "urgent"
                })

    is_urgent = len(red_flags) > 0

    # 4. Multi-entity extraction and update
    updates = {}
    multi_entities = {}
    live_result = None

    if not is_initial_call:
        # Run local rule-based entity extraction first
        multi_entities = extract_multi_entities(patient_input)
        updates.update(multi_entities)

        # Check chief complaint
        history = get_clinical_history(session_id) or {}
        if not history.get("chief_complaint"):
            updates["chief_complaint"] = patient_input
            if detected_concepts:
                notes = [f"{c['original_phrase']} [{c['region']} -> {c['clinical_concept']}]" for c in detected_concepts]
                updates["history_of_present_illness"] = f"Vernacular concepts: {'; '.join(notes)}"

        # Query Live AI if available
        with get_db_connection() as conn:
            ai_count_now = conn.execute(
                "SELECT COUNT(*) FROM transcripts WHERE session_id = ? AND speaker = 'ai'",
                (session_id,)
            ).fetchone()[0]

        answered_fields = get_already_answered_fields(history)
        live_result = query_live_ai_patient_turn(
            patient_input=patient_input,
            language=language,
            session_id=session_id,
            history=history,
            ai_question_count=ai_count_now,
            answered_fields=answered_fields,
            detected_concepts=detected_concepts
        )

        if live_result:
            # Merge live AI extracted entities
            live_entities = live_result.get("extracted_entities") or {}
            for k, v in live_entities.items():
                if v and str(v).strip():
                    updates[k] = str(v).strip()
                    multi_entities[k] = str(v).strip()

            # Check if live AI triggered a red flag
            if live_result.get("red_flag"):
                is_urgent = True
                red_flags.append({
                    "pattern_matched": patient_input[:50],
                    "concern": live_result.get("red_flag_reason") or "Emergency symptom detected by live clinical evaluation",
                    "action": "Immediate clinical attention advised.",
                    "priority": "urgent"
                })

        # Synthesize AYUSH specific summary string if AYUSH fields extracted
        ayush_parts = []
        if updates.get("agni"): ayush_parts.append(f"Agni: {updates['agni']}")
        if updates.get("ama"): ayush_parts.append(f"Ama: {updates['ama']}")
        if updates.get("koshta"): ayush_parts.append(f"Koshta: {updates['koshta']}")
        if updates.get("nidra"): ayush_parts.append(f"Nidra: {updates['nidra']}")
        if updates.get("manasika"): ayush_parts.append(f"Manasika: {updates['manasika']}")
        if ayush_parts:
            existing_ayush = history.get("ayush_specific_history") or ""
            updates["ayush_specific_history"] = f"{existing_ayush} | {' ; '.join(ayush_parts)}".strip(" |")

        if red_flags:
            existing_flags = json.loads(history.get("red_flags") or "[]")
            existing_flags.extend(red_flags)
            updates["red_flags"] = json.dumps(existing_flags)

        if updates:
            update_clinical_history(session_id, updates)

    # If urgent, set priority_level
    if is_urgent:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE patient_sessions SET priority_level = 'urgent' WHERE id = ?",
                (session_id,)
            )
            conn.commit()

    # 5. Determine next question (Live AI if available, otherwise local question catalog)
    updated_history = get_clinical_history(session_id) or {}
    
    with get_db_connection() as conn:
        ai_question_count = conn.execute(
            "SELECT COUNT(*) FROM transcripts WHERE session_id = ? AND speaker = 'ai'",
            (session_id,)
        ).fetchone()[0]

    if live_result and live_result.get("next_question"):
        field_name = live_result.get("field_name", "live_clinical_intake")
        next_question_text = live_result["next_question"]
        is_completed = bool(live_result.get("is_completed")) and (ai_question_count >= 10)
    else:
        field_name, next_question_text, is_completed = select_next_question(
            session_id=session_id,
            history=updated_history,
            language=language
        )

    # If urgent red flag detected, prepend emergency notice
    ai_response_text = ""
    if is_urgent:
        emergency_notices = {
            "en": "⚠️ ATTENTION: The symptoms you described may require immediate medical attention. Our triage desk has been alerted. Please inform the kiosk attendant or hospital staff right away. ",
            "hi": "⚠️ ध्यान दें: आपके द्वारा बताए गए लक्षणों के लिए तत्काल चिकित्सीय ध्यान की आवश्यकता हो सकती है। कृपया तुरंत अस्पताल कर्मचारियों को सूचित करें। ",
            "te": "⚠️ గమనిక: మీరు తెలిపిన లక్షణాలు అత్యవసర వైద్య పరీక్ష అవసరం కావచ్చు. దయచేసి వెంటనే ఆసుపత్రి సిబ్బందిని సంప్రదించండి. "
        }
        lang_key = language if language in ["en", "hi", "te"] else "en"
        ai_response_text += emergency_notices[lang_key]

    ai_response_text += next_question_text

    # 6. Log AI question in transcripts table
    add_transcript(
        patient_id=patient_id,
        session_id=session_id,
        speaker="ai",
        language=language,
        original_text=ai_response_text
    )

    # Update session status if completed
    if is_completed:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE patient_sessions SET status = 'AI Completed' WHERE id = ?",
                (session_id,)
            )
            conn.commit()

    # Count total questions asked so far
    with get_db_connection() as conn:
        ai_count = conn.execute(
            "SELECT COUNT(*) FROM transcripts WHERE session_id = ? AND speaker = 'ai'",
            (session_id,)
        ).fetchone()[0]

    return {
        "status": "success",
        "ai_status": "🔴 Emergency Alert" if is_urgent else ("🟢 Live AYUSH KRITI Active" if (live_result or os.getenv("AI_API_KEY")) else "🟢 AYUSH KRITI Active"),
        "current_field": field_name,
        "questions_asked_count": ai_count,
        "is_completed": is_completed,
        "is_urgent": is_urgent,
        "red_flags": red_flags,
        "dialect_detected": detected_concepts,
        "extracted_info": multi_entities,
        "answered_fields": list(updates.keys()),
        "ai_response": ai_response_text
    }
