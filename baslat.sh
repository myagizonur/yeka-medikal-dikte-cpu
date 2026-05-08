#!/bin/bash
# YEKA MedDikte — Başlatma Scripti

PORT=5050
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     🏥 YEKA MedDikte Başlatılıyor...     ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Eski süreçleri temizle
pkill -f "python3 app.py" 2>/dev/null
pkill -f "ngrok http" 2>/dev/null
sleep 1

# Flask uygulamasını arka planda başlat
cd "$SCRIPT_DIR"
echo "⏳ Uygulama başlatılıyor (Whisper modeli ilk açılışta birkaç dakika sürebilir)..."
python3 app.py > /tmp/meddikte.log 2>&1 &
APP_PID=$!

# Uygulamanın ayağa kalkmasını bekle
for i in {1..30}; do
    if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
    echo "❌ Uygulama başlatılamadı! Log:"
    tail -20 /tmp/meddikte.log
    exit 1
fi

echo "✅ Uygulama hazır!"
echo ""

# Ngrok tünelini başlat
ngrok http $PORT --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!
sleep 3

# Public URL'i al
PUBLIC_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null \
    | python3 -c "import sys,json; t=json.load(sys.stdin)['tunnels']; print([x['public_url'] for x in t if x['proto']=='https'][0])" 2>/dev/null)

if [ -z "$PUBLIC_URL" ]; then
    echo "⚠️  Ngrok URL alınamadı, yeniden deneniyor..."
    sleep 3
    PUBLIC_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null \
        | python3 -c "import sys,json; t=json.load(sys.stdin)['tunnels']; print([x['public_url'] for x in t if x['proto']=='https'][0])" 2>/dev/null)
fi

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                  🌐 ERİŞİM LİNKİ                        ║"
echo "║                                                          ║"
printf  "║  %-56s  ║\n" "$PUBLIC_URL"
echo "║                                                          ║"
echo "║  Bu linki babanıza gönderin — tarayıcıdan açabilir.     ║"
echo "║  Kapatmak için Ctrl+C'ye basın.                         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Ctrl+C ile temizce kapat
trap "echo ''; echo 'Kapatılıyor...'; kill $APP_PID $NGROK_PID 2>/dev/null; exit 0" INT TERM

# Canlı tut
wait $APP_PID
