"""
YEKA MedDikte — Flask Backend
WebSocket ile gerçek zamanlı ses streaming + REST API
"""

import os
import io
import base64
import logging
import tempfile
from datetime import datetime

from flask import Flask, send_from_directory, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from dotenv import load_dotenv

from transcribe import transcribe_audio, transcribe_chunk, full_pipeline, correct_medical_text, get_whisper, analyze_medical_image

IMAGE_ANALYSIS_ENABLED = os.getenv("IMAGE_ANALYSIS_ENABLED", "true").lower() == "true"
from report_generator import generate_pdf
from medical_terms import REPORT_TYPES

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("meddikte")

app = Flask(__name__, static_folder="static")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", max_http_buffer_size=16 * 1024 * 1024)

# Exports klasörü
EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "exports")
os.makedirs(EXPORTS_DIR, exist_ok=True)


# ══════════════════════════════════════════════
# Statik Dosyalar
# ══════════════════════════════════════════════
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("static", path)


# ══════════════════════════════════════════════
# REST API
# ══════════════════════════════════════════════
@app.route("/api/report-types", methods=["GET"])
def get_report_types():
    """Kullanılabilir rapor tiplerini döndür."""
    return jsonify(REPORT_TYPES)


@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    """
    Ses dosyasını alır, tam pipeline'dan geçirir.
    Body: multipart/form-data ile audio dosyası + report_type
    """
    if "audio" not in request.files:
        return jsonify({"error": "Ses dosyası gerekli"}), 400

    audio_file = request.files["audio"]
    report_type = request.form.get("report_type", "genel")
    audio_data = audio_file.read()

    result = full_pipeline(audio_data, report_type)
    return jsonify(result)


@app.route("/api/transcribe-live", methods=["POST"])
def api_transcribe_live():
    """
    Canlı transkript — sadece STT, LLM düzeltme yok (hız için).
    Kayıt sırasında her 5 saniyede çağrılır.
    """
    if "audio" not in request.files:
        return jsonify({"error": "Ses dosyası gerekli"}), 400

    audio_file = request.files["audio"]
    report_type = request.form.get("report_type", "genel")
    audio_data = audio_file.read()

    raw_text = transcribe_audio(audio_data, report_type)
    return jsonify({"raw_text": raw_text})


@app.route("/api/analyze-image", methods=["POST"])
def api_analyze_image():
    if not IMAGE_ANALYSIS_ENABLED:
        return jsonify({"error": "Görüntü analizi bu sunucuda aktif değil."}), 503

    data = request.get_json()
    image_base64 = data.get("image_base64", "")
    report_type = data.get("report_type", "genel")

    if not image_base64:
        return jsonify({"error": "Görüntü gerekli"}), 400

    analysis = analyze_medical_image(image_base64, report_type)
    return jsonify({"analysis": analysis})


@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify({"image_analysis_enabled": IMAGE_ANALYSIS_ENABLED})


@app.route("/api/correct", methods=["POST"])
def api_correct():
    """
    Ham metni tıbbi düzeltmeden geçirir.
    Body: JSON { "text": "...", "report_type": "..." }
    """
    data = request.get_json()
    raw_text = data.get("text", "")
    report_type = data.get("report_type", "genel")

    if not raw_text.strip():
        return jsonify({"error": "Metin gerekli"}), 400

    corrected = correct_medical_text(raw_text, report_type)
    return jsonify({"corrected_text": corrected})


@app.route("/api/generate-pdf", methods=["POST"])
def api_generate_pdf():
    """
    Rapor metninden PDF üretir.
    Body: JSON { "text", "report_type", "patient_name", "patient_tc", "doctor_name" }
    """
    data = request.get_json()
    report_text = data.get("text", "")
    report_type = data.get("report_type", "genel")
    patient_name = data.get("patient_name", "")
    patient_tc = data.get("patient_tc", "")
    doctor_name = data.get("doctor_name", "")
    doctor_title = data.get("doctor_title", "Uzm. Dr.")

    if not report_text.strip():
        return jsonify({"error": "Rapor metni gerekli"}), 400

    pdf_bytes = generate_pdf(
        report_text=report_text,
        report_type=report_type,
        patient_name=patient_name,
        patient_tc=patient_tc,
        doctor_name=doctor_name,
        doctor_title=doctor_title,
    )

    # Dosyayı kaydet
    filename = f"rapor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(EXPORTS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(pdf_bytes)

    from flask import Response
    response = Response(pdf_bytes, mimetype="application/pdf")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "YEKA MedDikte"})


# ══════════════════════════════════════════════
# WebSocket — Gerçek Zamanlı Ses Streaming
# ══════════════════════════════════════════════
@socketio.on("connect")
def handle_connect():
    logger.info("🔌 WebSocket bağlantısı kuruldu")
    emit("status", {"message": "Bağlantı kuruldu"})


@socketio.on("audio_chunk")
def handle_audio_chunk(data):
    """
    Tarayıcıdan gelen ses chunk'ını işler.
    data: { "audio": base64_encoded_wav, "report_type": "..." }
    """
    try:
        audio_b64 = data.get("audio", "")
        report_type = data.get("report_type", "genel")

        if not audio_b64:
            return

        audio_bytes = base64.b64decode(audio_b64)

        # Minimum ses boyutu kontrolü (çok kısa chunk'ları atla)
        if len(audio_bytes) < 1000:
            return

        text = transcribe_chunk(audio_bytes, report_type)

        if text.strip():
            emit("transcription", {"text": text, "is_final": False})

    except Exception as e:
        logger.error(f"❌ Chunk işleme hatası: {e}")
        emit("error", {"message": str(e)})


@socketio.on("finalize")
def handle_finalize(data):
    """
    Dikte tamamlandığında tüm metni düzeltir.
    data: { "full_text": "...", "report_type": "..." }
    """
    try:
        full_text = data.get("full_text", "")
        report_type = data.get("report_type", "genel")

        if not full_text.strip():
            emit("corrected", {"text": "Metin algılanamadı."})
            return

        emit("status", {"message": "Tıbbi düzeltme yapılıyor..."})

        corrected = correct_medical_text(full_text, report_type)
        emit("corrected", {"text": corrected})

        logger.info(f"✅ Dikte tamamlandı ve düzeltildi ({len(corrected)} karakter)")

    except Exception as e:
        logger.error(f"❌ Finalize hatası: {e}")
        emit("corrected", {"text": full_text})


@socketio.on("disconnect")
def handle_disconnect():
    logger.info("🔌 WebSocket bağlantısı kapandı")


# ══════════════════════════════════════════════
# Başlatma
# ══════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))

    print("\n" + "=" * 60)
    print("  🏥 YEKA MedDikte — Tıbbi Ses Dikte Sistemi")
    print("  🔒 Tüm veri yerel — hiçbir API çağrısı yok")
    print(f"  🌐 http://localhost:{port}")
    print("=" * 60)

    # Whisper modelini önceden yükle
    print("\n⏳ Whisper modeli yükleniyor...")
    get_whisper()
    print("✅ Sistem hazır!\n")

    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
