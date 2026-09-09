"""
Ministry of Ayush – Smart MediKiosk
Prakriti-AI Model Training Pipeline
Government of India / Bharat • Clinical History Platform

Separation of Concerns:
This script trains the clinical intent classifier, regional symptom entity categorizer,
and Ayush constitutional pattern recognition model, saving the trained model artifact
to models/prakriti_ai/intent_classifier.json for runtime inference by the Flask backend.
"""

import os
import json
import math
import re
from collections import defaultdict

# -------------------------------------------------------------
# 1. CLINICAL MULTILINGUAL CASE-TAKING TRAINING DATASET
# -------------------------------------------------------------
TRAINING_DATA = [
    # CHIEF COMPLAINT - GASTROINTESTINAL
    {"text": "I have severe burning sensation in my stomach and acid coming up", "label": "chief_complaint_gi"},
    {"text": "kadupulo manta ga undi chala rojula nundi", "label": "chief_complaint_gi"},
    {"text": "chhati me jalan aur khatti dakar aa rahi hai", "label": "chief_complaint_gi"},
    {"text": "pet me dard aur marod hai khana khane ke baad", "label": "chief_complaint_gi"},
    {"text": "indigestion and acidity after oily food", "label": "chief_complaint_gi"},
    {"text": "vayiru erichal and pasiyinmai", "label": "chief_complaint_gi"},
    {"text": "hotte uritha aagide aahara thindamele", "label": "chief_complaint_gi"},
    {"text": "motion aithaledu 3 days nunchi chala ibbandi", "label": "chief_complaint_gi"},

    # CHIEF COMPLAINT - RESPIRATORY
    {"text": "I have bad dry cough and difficulty breathing at night", "label": "chief_complaint_respiratory"},
    {"text": "dhummu pattindi aayasam ekkuva ayyindi", "label": "chief_complaint_respiratory"},
    {"text": "saans phool rahi hai aur seene me kharkharahat hai", "label": "chief_complaint_respiratory"},
    {"text": "dammu vasthondi nadusthe aagipothunna", "label": "chief_complaint_respiratory"},
    {"text": "persistent wheezing and chest phlegm", "label": "chief_complaint_respiratory"},
    {"text": "moochu thinaral irumal jaasthi", "label": "chief_complaint_respiratory"},

    # CHIEF COMPLAINT - MUSCULOSKELETAL / JOINT
    {"text": "severe knee pain and morning joint stiffness", "label": "chief_complaint_joint"},
    {"text": "kaallu peekuthunnayi sandhullo noppulu", "label": "chief_complaint_joint"},
    {"text": "ghutno me dard aur soojan hai chalte waqt", "label": "chief_complaint_joint"},
    {"text": "sarvangam noppulu unnay ontlo rasalu poyinattu", "label": "chief_complaint_joint"},
    {"text": "lower back pain radiating to legs", "label": "chief_complaint_joint"},
    {"text": "kaal vali nadakka mudiyavillai", "label": "chief_complaint_joint"},

    # CHIEF COMPLAINT - GENERAL / FEVER / DIZZINESS
    {"text": "feeling very weak tired and feverish since yesterday", "label": "chief_complaint_general"},
    {"text": "ontlo jwaram laaga undi ontlo baaledu", "label": "chief_complaint_general"},
    {"text": "tez bukhar aur badan me dard hai", "label": "chief_complaint_general"},
    {"text": "thalakay thiruguthundi kallu maathulu pothunnayi", "label": "chief_complaint_general"},
    {"text": "chakkar aa rahe hai aur sar bhari lag raha hai", "label": "chief_complaint_general"},

    # ONSET & DURATION
    {"text": "it started suddenly two days ago in the morning", "label": "onset_duration"},
    {"text": "gata moodu rojula nunchi vasthundi", "label": "onset_duration"},
    {"text": "pichhle ek hafte se chal raha hai", "label": "onset_duration"},
    {"text": "since 6 months it is continuous problem", "label": "onset_duration"},
    {"text": "yesterday evening after having dinner", "label": "onset_duration"},
    {"text": "ninna rathri start ayyindi", "label": "onset_duration"},

    # SEVERITY & CHARACTER
    {"text": "the pain is sharp and unbearable around 8 out of 10", "label": "severity_character"},
    {"text": "it is dull throbbing ache on left side", "label": "severity_character"},
    {"text": "noppi chala ghoram ga undi thattukolenu", "label": "severity_character"},
    {"text": "bahut tez chubhan jaisa dard hai", "label": "severity_character"},
    {"text": "mild discomfort and heaviness", "label": "severity_character"},

    # AGGRAVATING & RELIEVING
    {"text": "it becomes worse after eating spicy food or drinking tea", "label": "aggravating_relieving"},
    {"text": "resting and taking warm water makes it slightly better", "label": "aggravating_relieving"},
    {"text": "karam tinte ekkuva aithadi padukunte tagguddi", "label": "aggravating_relieving"},
    {"text": "teekha khane se badhta hai garam pani peene se aaram milta hai", "label": "aggravating_relieving"},
    {"text": "walking increases the pain, lying down gives relief", "label": "aggravating_relieving"},

    # PAST MEDICAL & DRUG HISTORY
    {"text": "I have high blood pressure and sugar for past 5 years taking metformin", "label": "past_history"},
    {"text": "naku bp sugar unnay roju tablet vesukunta", "label": "past_history"},
    {"text": "mujhe diabetes aur hypertension hai telmisartan le raha hu", "label": "past_history"},
    {"text": "had gall bladder surgery three years back", "label": "past_history"},
    {"text": "no known previous chronic diseases", "label": "past_history"},
    {"text": "allergic to penicillin and sulfa drugs", "label": "past_history"},

    # AYUSH LIFESTYLE (Agni, Ahara, Nidana, Sleep)
    {"text": "my appetite is very low and digestion is very sluggish", "label": "ayush_lifestyle"},
    {"text": "aakali aithaledu nidra sarigga pattatledu tension valla", "label": "ayush_lifestyle"},
    {"text": "bhookh kam lagti hai pet me gas aur anidra rehti hai", "label": "ayush_lifestyle"},
    {"text": "sleep is restless I wake up frequently at 2 am", "label": "ayush_lifestyle"},
    {"text": "hard dry stools once in two days with bloating", "label": "ayush_lifestyle"},
    {"text": "eat mostly outside food irregular meal timings", "label": "ayush_lifestyle"},

    # RED FLAG / EMERGENCY
    {"text": "sudden crushing chest pain radiating to left arm and sweating", "label": "red_flag_emergency"},
    {"text": "gunde batte pothundi ghabrahat chematalu", "label": "red_flag_emergency"},
    {"text": "chhati me bhayankar dard aur baye hath me ja raha hai", "label": "red_flag_emergency"},
    {"text": "cannot breathe at all lips turning blue gasping", "label": "red_flag_emergency"},
    {"text": "sudden paralysis on right side of face and arm cannot speak", "label": "red_flag_emergency"},
    {"text": "vomiting continuous fresh blood", "label": "red_flag_emergency"}
]

def clean_and_tokenize(text):
    """Normalize text, remove punctuation, extract unigrams and bigrams."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t for t in text.split() if len(t) > 1]
    
    # Extract unigrams + bigrams for regional slang capture
    features = list(tokens)
    for i in range(len(tokens) - 1):
        features.append(f"{tokens[i]}_{tokens[i+1]}")
    return features

class PrakritiClinicalClassifier:
    """Multinomial Naive Bayes & Pattern Recognizer for Prakriti-AI."""
    def __init__(self):
        self.class_counts = defaultdict(int)
        self.feature_counts = defaultdict(lambda: defaultdict(int))
        self.vocabulary = set()
        self.total_docs = 0

    def train(self, data):
        print(f"[ML Training] Preprocessing {len(data)} clinical interaction samples...")
        for row in data:
            label = row["label"]
            features = clean_and_tokenize(row["text"])
            self.class_counts[label] += 1
            self.total_docs += 1
            for f in features:
                self.feature_counts[label][f] += 1
                self.vocabulary.add(f)
        print(f"[ML Training] Extracted {len(self.vocabulary)} distinct clinical linguistic features.")
        print(f"[ML Training] Classes registered: {list(self.class_counts.keys())}")

    def evaluate(self, data):
        correct = 0
        total = len(data)
        for row in data:
            pred, _ = self.predict(row["text"])
            if pred == row["label"]:
                correct += 1
        accuracy = (correct / total) * 100
        print(f"[ML Evaluation] Training Set Accuracy: {accuracy:.2f}% ({correct}/{total})")
        return accuracy

    def predict(self, text):
        features = clean_and_tokenize(text)
        best_label = None
        best_score = -float('inf')
        scores = {}

        vocab_size = max(len(self.vocabulary), 1)
        for label, count in self.class_counts.items():
            # Log prior
            score = math.log(count / self.total_docs)
            total_words_in_class = sum(self.feature_counts[label].values()) + vocab_size
            
            for f in features:
                if f in self.vocabulary:
                    word_freq = self.feature_counts[label][f] + 1  # Laplace smoothing
                    score += math.log(word_freq / total_words_in_class)
            
            scores[label] = score
            if score > best_score:
                best_score = score
                best_label = label

        return best_label, scores

    def save(self, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        model_payload = {
            "total_docs": self.total_docs,
            "class_counts": dict(self.class_counts),
            "feature_counts": {k: dict(v) for k, v in self.feature_counts.items()},
            "vocabulary": list(self.vocabulary),
            "classes": list(self.class_counts.keys())
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(model_payload, f, indent=2)
        print(f"[ML Artifact] Model successfully saved to {filepath}")

def main():
    print("=" * 60)
    print("MINISTRY OF AYUSH – SMART MEDIKIOSK")
    print("PRAKRITI-AI CLINICAL MODEL TRAINING")
    print("=" * 60)
    
    classifier = PrakritiClinicalClassifier()
    classifier.train(TRAINING_DATA)
    classifier.evaluate(TRAINING_DATA)

    model_dir = os.path.join(os.path.dirname(__file__), "models", "prakriti_ai")
    model_path = os.path.join(model_dir, "intent_classifier.json")
    classifier.save(model_path)

    # Test sample inference
    test_samples = [
        "gunde batte pothundi chala ghoram ga",
        "kadupulo manta karam tinnaka",
        "dhummu aayasam tho nidra pattaledu",
        "ghutno me tez dard subah ke waqt"
    ]
    print("\n--- Validation Inferences ---")
    for s in test_samples:
        pred, _ = classifier.predict(s)
        print(f"Text: '{s}' -> Classified Intent: [{pred}]")
    print("=" * 60)

if __name__ == "__main__":
    main()
