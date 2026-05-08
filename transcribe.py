"""
YEKA MedDikte — STT + Tıbbi Düzeltme Pipeline
Tamamen yerel — hiçbir veri dışarı çıkmaz.
  STT : faster-whisper (Mac + Linux, CPU/CUDA)
  LLM : Ollama         (yerel, nous-hermes2)
"""

import os
import logging
import tempfile
import threading
import requests
from faster_whisper import WhisperModel
from dotenv import load_dotenv

from medical_terms import WHISPER_PROMPTS, MEDICAL_GLOSSARY, REPORT_TYPES

load_dotenv()
logger = logging.getLogger("meddikte.transcribe")

WHISPER_MODEL  = os.getenv("WHISPER_MODEL",  "large-v3-turbo")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL",  "nous-hermes2")
OLLAMA_VISION  = os.getenv("OLLAMA_VISION", "llava:13b")
OLLAMA_URL     = os.getenv("OLLAMA_URL",    "http://localhost:11434")

_model: WhisperModel = None
_lock  = threading.Lock()


def get_whisper() -> WhisperModel:
    global _model
    if _model is None:
        device = "cuda" if _cuda_available() else "cpu"
        logger.info(f"⏳ Whisper '{WHISPER_MODEL}' yükleniyor ({device})...")
        _model = WhisperModel(WHISPER_MODEL, device=device, compute_type="int8")
        logger.info("✅ Whisper hazır!")
    return _model


def _cuda_available():
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


# ──────────────────────────────────────────────
# Katman 1: STT — faster-whisper
# ──────────────────────────────────────────────
def transcribe_audio(audio_data: bytes, report_type: str = "genel") -> str:
    prompt = WHISPER_PROMPTS.get(report_type, WHISPER_PROMPTS["genel"])

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        with _lock:
            model = get_whisper()
            segments, info = model.transcribe(
                tmp_path,
                language="tr",
                initial_prompt=prompt,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 200,
                    "speech_pad_ms": 400,
                    "threshold": 0.3,
                },
            )
            text = " ".join(s.text.strip() for s in segments).strip()
        logger.info(f"📝 STT ({info.duration:.1f}s ses): {text[:100]}...")
        return text
    finally:
        os.unlink(tmp_path)


def transcribe_chunk(audio_data: bytes, report_type: str = "genel") -> str:
    return transcribe_audio(audio_data, report_type)


# ──────────────────────────────────────────────
# Katman 2: Tıbbi Düzeltme — Ollama
# ──────────────────────────────────────────────
SYSTEM_PROMPT = """Sen bir radyoloji rapor editörüsün. Ham sesli dikteyi düzeltiyor ve yapılandırılmış tıbbi rapor oluşturuyorsun.

Kurallar:
1. Tıbbi terimleri doğru yaz (aşağıdaki sözlüğe bak)
2. Noktalama işaretlerini ekle
3. Raporu bölümlere ayır: BULGULAR, SONUÇ, ÖNERİ
4. Tekrar eden/anlamsız kelimeleri kaldır
5. "nokta" "virgül" "yeni satır" komutlarını gerçek noktalamaya çevir
6. Orijinal tıbbi içeriği değiştirme — sadece düzelt ve formatla
7. SADECE düzeltilmiş rapor metnini döndür, başka açıklama ekleme

Tıbbi Terim Sözlüğü:
{glossary}

Rapor Tipi: {report_type}"""


def correct_medical_text(raw_text: str, report_type: str = "genel") -> str:
    report_name = REPORT_TYPES.get(report_type, "Genel Radyoloji Raporu")
    system = SYSTEM_PROMPT.format(glossary=MEDICAL_GLOSSARY, report_type=report_name)

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": f"Aşağıdaki ham dikteyi düzelt:\n\n{raw_text}"},
                ],
            },
            timeout=180,
        )
        resp.raise_for_status()
        corrected = resp.json()["message"]["content"].strip()
        logger.info(f"✅ Düzeltme tamamlandı ({len(corrected)} karakter)")
        return corrected

    except Exception as e:
        logger.error(f"❌ Ollama hatası: {e}")
        return raw_text


# ──────────────────────────────────────────────
# Katman 3: Görüntü Analizi — Ollama llava:13b
# ──────────────────────────────────────────────
IMAGE_ANALYSIS_PROMPT = """You are an expert radiologist. Analyze this medical image carefully.

Describe exactly what you see:
- Identify the type of imaging (X-ray, MRI, CT, ultrasound)
- Describe visible anatomical structures
- Note any abnormalities, pathologies, or normal findings
- Be specific and concise
- Do NOT hallucinate findings not visible in the image

Write findings in English only."""

TRANSLATION_PROMPT = """Sen uzman bir radyologsun. Aşağıdaki İngilizce radyoloji bulgularını Türkçe'ye çevir ve düzgün bir radyoloji raporu BULGULAR bölümü oluştur.

Kurallar:
- Doğru tıbbi Türkçe terminoloji kullan
- Kısa ve net cümleler yaz
- Sadece BULGULAR bölümünü yaz, başka açıklama ekleme

İngilizce bulgular:
{english_findings}"""


def analyze_medical_image(image_base64: str, report_type: str = "genel") -> str:
    """Tıbbi görüntüyü llava (İngilizce) + qwen3 (Türkçe çeviri) ile analiz eder."""
    try:
        # Adım 1: llava ile İngilizce analiz
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_VISION,
                "prompt": IMAGE_ANALYSIS_PROMPT,
                "images": [image_base64],
                "stream": False,
            },
            timeout=180,
        )
        resp.raise_for_status()
        english_findings = resp.json()["response"].strip()
        logger.info(f"📷 İngilizce analiz: {english_findings[:100]}...")

        # Adım 2: qwen3 ile Türkçe'ye çevir
        translation_prompt = TRANSLATION_PROMPT.format(english_findings=english_findings)
        resp2 = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "messages": [{"role": "user", "content": translation_prompt}],
            },
            timeout=120,
        )
        resp2.raise_for_status()
        turkish_analysis = resp2.json()["message"]["content"].strip()
        logger.info(f"✅ Görüntü analizi tamamlandı ({len(turkish_analysis)} karakter)")
        return turkish_analysis

    except Exception as e:
        logger.error(f"❌ Görüntü analizi hatası: {e}")
        return "Görüntü analizi yapılamadı. Doktor diktesi ile devam edin."


# ──────────────────────────────────────────────
# Tam Pipeline: STT → Düzeltme
# ──────────────────────────────────────────────
def full_pipeline(audio_data: bytes, report_type: str = "genel") -> dict:
    raw_text = transcribe_audio(audio_data, report_type)

    if not raw_text.strip():
        return {
            "raw_text": "",
            "corrected_text": "Ses algılanamadı. Lütfen tekrar deneyin.",
            "report_type": report_type,
        }

    return {
        "raw_text": raw_text,
        "corrected_text": correct_medical_text(raw_text, report_type),
        "report_type": report_type,
    }
