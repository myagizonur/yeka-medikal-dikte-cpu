const socket = io(window.location.origin);
let isRecording = false;
let imageAnalysisEnabled = true;

fetch("/api/config").then(r => r.json()).then(cfg => {
  imageAnalysisEnabled = cfg.image_analysis_enabled;
  if (!imageAnalysisEnabled) {
    document.getElementById("step-2").style.display = "none";
  }
});
let mediaRecorder = null;
let audioChunks = [];
let fullTranscript = "";
let timerInterval = null;
let seconds = 0;
let liveInterval = null;
let isProcessing = false;
let aiDraftText = "";

// ── WebSocket ──
socket.on("connect", () => {
  document.getElementById("conn-badge").textContent = "✓ Bağlı";
});
socket.on("disconnect", () => {
  document.getElementById("conn-badge").textContent = "Bağlantı kesildi";
});

// ── Adım Navigasyonu ──
function goToStep(step) {
  // Görüntü analizi kapalıysa adım 2'yi atla
  if (!imageAnalysisEnabled && step === 2) { step = 3; }

  [1, 2, 3, 4].forEach(s => {
    document.getElementById(`panel-${s}`).classList.toggle("hidden", s !== step);
    const el = document.getElementById(`step-${s}`);
    el.classList.remove("active", "done");
    if (s < step) el.classList.add("done");
    if (s === step) el.classList.add("active");
  });

  if (step === 3 && aiDraftText) {
    document.getElementById("ai-draft-reminder").classList.remove("hidden");
    document.getElementById("ai-draft-reminder-text").textContent = aiDraftText;
  } else if (step === 3) {
    document.getElementById("ai-draft-reminder").classList.add("hidden");
  }
}

function skipImage() {
  aiDraftText = "";
  goToStep(3);
}

// ── Görüntü Yükleme ──
function handleDrop(e) {
  e.preventDefault();
  document.getElementById("upload-area").classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) loadImagePreview(file);
}

function handleDragOver(e) {
  e.preventDefault();
  document.getElementById("upload-area").classList.add("drag-over");
}

function handleDragLeave() {
  document.getElementById("upload-area").classList.remove("drag-over");
}

function handleImageSelect(e) {
  const file = e.target.files[0];
  if (file) loadImagePreview(file);
}

function loadImagePreview(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    document.getElementById("image-preview").src = e.target.result;
    document.getElementById("image-preview-area").classList.remove("hidden");
    document.getElementById("upload-area").classList.add("hidden");
    document.getElementById("analyze-btn").disabled = false;
    document.getElementById("ai-draft-area").classList.add("hidden");
    document.getElementById("continue-btn").classList.add("hidden");
    aiDraftText = "";
  };
  reader.readAsDataURL(file);
}

function clearImage() {
  document.getElementById("image-preview").src = "";
  document.getElementById("image-preview-area").classList.add("hidden");
  document.getElementById("upload-area").classList.remove("hidden");
  document.getElementById("analyze-btn").disabled = true;
  document.getElementById("ai-draft-area").classList.add("hidden");
  document.getElementById("continue-btn").classList.add("hidden");
  document.getElementById("image-input").value = "";
  aiDraftText = "";
}

async function analyzeImage() {
  const imgEl = document.getElementById("image-preview");
  if (!imgEl.src) return;

  showStatus("status-bar-img", "⏳ Görüntü analiz ediliyor (llava:13b)...", "info");
  document.getElementById("analyze-btn").disabled = true;

  try {
    // base64 veri URL'den sadece base64 kısmını al
    const base64 = imgEl.src.split(",")[1];
    const reportType = document.getElementById("report-type").value;

    const resp = await fetch("/api/analyze-image", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_base64: base64, report_type: reportType }),
    });

    if (resp.ok) {
      const result = await resp.json();
      aiDraftText = result.analysis;
      document.getElementById("ai-draft").textContent = aiDraftText;
      document.getElementById("ai-draft-area").classList.remove("hidden");
      document.getElementById("continue-btn").classList.remove("hidden");
      showStatus("status-bar-img", "✅ Analiz tamamlandı!", "success");
    } else {
      showStatus("status-bar-img", "Analiz hatası, dikteye geçebilirsiniz.", "error");
      document.getElementById("continue-btn").classList.remove("hidden");
    }
  } catch (err) {
    showStatus("status-bar-img", "Bağlantı hatası: " + err.message, "error");
    document.getElementById("continue-btn").classList.remove("hidden");
  } finally {
    document.getElementById("analyze-btn").disabled = false;
  }
}

// ── Mikrofon Kaydı ──
async function toggleRecording() {
  if (isRecording) stopRecording();
  else await startRecording();
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }
    });

    let mimeType = "audio/webm;codecs=opus";
    if (!MediaRecorder.isTypeSupported(mimeType)) mimeType = "audio/webm";
    mediaRecorder = new MediaRecorder(stream, { mimeType });
    audioChunks = [];

    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.start(1000);
    isRecording = true;

    document.getElementById("mic-btn").classList.add("recording");
    document.getElementById("mic-btn").textContent = "⏹";
    document.getElementById("mic-status").textContent = "Kaydediliyor... Bitirmek için tekrar tıklayın";
    document.getElementById("mic-timer").classList.remove("hidden");
    document.getElementById("waveform").classList.remove("hidden");

    seconds = 0;
    timerInterval = setInterval(() => {
      seconds++;
      const m = Math.floor(seconds / 60).toString().padStart(2, "0");
      const s = (seconds % 60).toString().padStart(2, "0");
      document.getElementById("mic-timer").textContent = `${m}:${s}`;
    }, 1000);

    liveInterval = setInterval(() => {
      if (!isProcessing && audioChunks.length > 0) sendLiveAudio();
    }, 5000);

  } catch (err) {
    showStatus("status-bar", "Mikrofon erişimi reddedildi. Tarayıcı ayarlarından izin verin.", "error");
  }
}

async function sendLiveAudio() {
  if (audioChunks.length === 0) return;
  isProcessing = true;
  const audioBlob = new Blob(audioChunks, { type: "audio/webm;codecs=opus" });
  const formData = new FormData();
  formData.append("audio", audioBlob, "live.webm");
  formData.append("report_type", document.getElementById("report-type").value);

  try {
    const response = await fetch("/api/transcribe-live", { method: "POST", body: formData });
    if (response.ok) {
      const result = await response.json();
      if (result.raw_text && result.raw_text.trim()) {
        fullTranscript = result.raw_text;
        updateTranscriptUI();
        document.getElementById("finalize-btn").disabled = false;
      }
    }
  } catch (err) { console.error("Canlı transkript hatası:", err); }
  isProcessing = false;
}

function stopRecording() {
  if (liveInterval) { clearInterval(liveInterval); liveInterval = null; }
  clearInterval(timerInterval);
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
  }
  isRecording = false;

  document.getElementById("mic-btn").classList.remove("recording");
  document.getElementById("mic-btn").textContent = "🎤";
  document.getElementById("mic-status").textContent = "Kayıt durduruldu";
  document.getElementById("waveform").classList.add("hidden");

  if (audioChunks.length > 0) {
    showStatus("status-bar", "⏳ Son transkript işleniyor...", "info");
    sendFinalAudio();
  }
}

async function sendFinalAudio() {
  const audioBlob = new Blob(audioChunks, { type: "audio/webm;codecs=opus" });
  const formData = new FormData();
  formData.append("audio", audioBlob, "final.webm");
  formData.append("report_type", document.getElementById("report-type").value);

  try {
    const response = await fetch("/api/transcribe", { method: "POST", body: formData });
    if (response.ok) {
      const result = await response.json();
      if (result.raw_text) {
        fullTranscript = result.raw_text;
        updateTranscriptUI();
        document.getElementById("finalize-btn").disabled = false;
        showStatus("status-bar", "✅ Transkript hazır!", "success");
      }
    }
  } catch (err) {
    showStatus("status-bar", "Sunucu hatası: " + err.message, "error");
  }
}

function updateTranscriptUI() {
  const box = document.getElementById("transcript");
  box.classList.remove("empty");
  box.textContent = fullTranscript.trim();
  box.scrollTop = box.scrollHeight;
}

function clearTranscript() {
  fullTranscript = "";
  const box = document.getElementById("transcript");
  box.textContent = "Konuşmaya başladığınızda metin burada görünecek...";
  box.classList.add("empty");
  document.getElementById("finalize-btn").disabled = true;
}

// ── Dikteyi Bitir & Düzelt ──
async function finalize() {
  const hasTranscript = fullTranscript.trim();
  const hasAI = aiDraftText.trim();

  if (!hasTranscript && !hasAI) return;

  showStatus("status-bar", "⏳ Rapor hazırlanıyor...", "info");
  document.getElementById("finalize-btn").disabled = true;

  // AI taslağı + doktor diktesini birleştir
  let combinedText = "";
  if (hasAI && hasTranscript) {
    combinedText = `[Görüntü Analizi]\n${aiDraftText}\n\n[Doktor Eklentisi]\n${fullTranscript}`;
  } else if (hasAI) {
    combinedText = aiDraftText;
  } else {
    combinedText = fullTranscript;
  }

  try {
    const response = await fetch("/api/correct", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: combinedText,
        report_type: document.getElementById("report-type").value,
      }),
    });

    if (response.ok) {
      const result = await response.json();
      document.getElementById("editor").value = result.corrected_text;
      goToStep(4);
      showStatus("status-bar", "✅ Rapor hazır!", "success");
    } else {
      document.getElementById("editor").value = combinedText;
      goToStep(4);
    }
  } catch (err) {
    document.getElementById("editor").value = combinedText;
    goToStep(4);
  } finally {
    document.getElementById("finalize-btn").disabled = false;
    hideLoading();
  }
}

// ── PDF İndirme ──
async function downloadPDF() {
  const text = document.getElementById("editor").value;
  if (!text.trim()) { showStatus("status-bar-2", "Rapor metni boş!", "error"); return; }
  showStatus("status-bar-2", "⏳ PDF oluşturuluyor...", "info");

  try {
    const response = await fetch("/api/generate-pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        report_type: document.getElementById("report-type").value,
        patient_name: document.getElementById("patient-name").value,
        patient_tc: document.getElementById("patient-tc").value,
        doctor_name: document.getElementById("doctor-name").value,
        doctor_title: document.getElementById("doctor-title").value,
      }),
    });

    if (response.ok) {
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `rapor_${new Date().toISOString().slice(0,10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      showStatus("status-bar-2", "✅ PDF indirildi!", "success");
    } else {
      showStatus("status-bar-2", "PDF hatası", "error");
    }
  } catch (err) {
    showStatus("status-bar-2", "Bağlantı hatası", "error");
  }
}

function copyText() {
  navigator.clipboard.writeText(document.getElementById("editor").value)
    .then(() => showStatus("status-bar-2", "📋 Kopyalandı!", "success"));
}

function newReport() {
  fullTranscript = "";
  aiDraftText = "";
  clearTranscript();
  clearImage();
  document.getElementById("editor").value = "";
  document.getElementById("patient-name").value = "";
  document.getElementById("patient-tc").value = "";
  document.getElementById("ai-draft-area").classList.add("hidden");
  document.getElementById("continue-btn").classList.add("hidden");
  goToStep(1);
}

function showStatus(id, message, type) {
  const bar = document.getElementById(id);
  bar.className = `status-bar visible ${type}`;
  bar.innerHTML = type === "info" ? `<span class="spinner"></span> ${message}` : message;
  if (type !== "info") setTimeout(() => bar.classList.remove("visible"), 5000);
}

function hideLoading() {
  const bar = document.getElementById("status-bar");
  if (bar.classList.contains("info")) bar.classList.remove("visible");
}
