#!/bin/bash
# YEKA MedDikte — Ubuntu Sunucu Kurulum Scripti
# Ubuntu 22.04 LTS — tek komutla çalıştır:
#   bash setup.sh

set -e

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║    YEKA MedDikte — Sunucu Kurulumu       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Docker kurulumu ──
if ! command -v docker &> /dev/null; then
    echo "📦 Docker kuruluyor..."
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker $USER
    echo "✅ Docker kuruldu"
else
    echo "✅ Docker mevcut: $(docker --version)"
fi

# ── Docker Compose kurulumu ──
if ! command -v docker compose &> /dev/null; then
    echo "📦 Docker Compose kuruluyor..."
    apt-get install -y docker-compose-plugin
fi

# ── Servisleri başlat ──
echo ""
echo "🚀 Servisler başlatılıyor..."
docker compose up -d --build

# ── Ollama model indir ──
echo ""
echo "📥 Ollama modeli indiriliyor (nous-hermes2 ~6GB, bir kez indirilir)..."
sleep 5
docker exec meddikte-ollama ollama pull nous-hermes2

# ── Servis durumu ──
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║           ✅ KURULUM TAMAMLANDI           ║"
echo "║                                          ║"
echo "║  Uygulama: http://SUNUCU_IP:5050         ║"
echo "║                                          ║"
echo "║  Komutlar:                               ║"
echo "║    Durdur : docker compose down          ║"
echo "║    Başlat : docker compose up -d         ║"
echo "║    Log    : docker compose logs -f app   ║"
echo "╚══════════════════════════════════════════╝"
echo ""
