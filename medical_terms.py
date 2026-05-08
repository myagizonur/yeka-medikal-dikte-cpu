"""
YEKA MedDikte — Tıbbi Terim Sözlüğü (Radyoloji)

Bu sözlük iki amaçla kullanılır:
1. Whisper'ın initial_prompt'una verilerek STT doğruluğu artırılır
2. LLM düzeltme adımında bağlam olarak kullanılır
"""

# ═══════════════════════════════════════════════════
# Rapor tipine göre Whisper prompt'ları
# Whisper max ~224 token alır — her biri kısa tutulmalı
# Gerçek radyoloji rapor cümleleri en iyi sonucu verir
# ═══════════════════════════════════════════════════

WHISPER_PROMPTS = {
    "kranial_mr": (
        "Kranial MR incelemesinde serebral parankimde T2 ve FLAIR sekanslarda "
        "hiperintens sinyal değişiklikleri izlenmektedir. Lateral ventriküller "
        "doğal boyuttadır. Serebellar tonsiller foramen magnum düzeyindedir. "
        "Hipotalamik bölgede, hipofiz bezinde patolojik sinyal saptanmamıştır. "
        "Difüzyon kısıtlanması gösterilmemiştir. Orta hat yapıları doğal "
        "yerleşimdedir. Mastoid hücrelerde havalanma doğaldır."
    ),

    "lomber_mr": (
        "Lomber MR incelemesinde L4-L5 düzeyinde posterior santral disk "
        "protrüzyonu izlenmektedir. L5-S1 düzeyinde posterolateral disk "
        "herniasyonu mevcuttur. Spinal kanal anteroposterior çapı daralmıştır. "
        "Nöroforaminal stenoz saptanmıştır. Konus medullaris T12-L1 düzeyinde "
        "sonlanmaktadır. Vertebra korpuslarında sinyal kayıpları izlenmektedir. "
        "Ligamentum flavum hipertrofisi mevcuttur. Faset eklem dejenerasyonu."
    ),

    "akciger_grafi": (
        "Akciğer grafisinde her iki akciğer parankimi doğal havalanmaktadır. "
        "Kardiyotorasik oran doğal sınırlardadır. Kostofrenik sinüsler açıktır. "
        "Mediastinal genişleme izlenmemektedir. Trakea orta hattadır. "
        "Plevral efüzyon veya pnömotoraks saptanmamıştır. Kemik yapılarda "
        "patolojik bulgu yoktur. Konsolidasyon alanı izlenmemektedir."
    ),

    "toraks_bt": (
        "Toraks BT incelemesinde pulmoner parankim pencerelerinde her iki "
        "akciğerde buzlu cam dansitesinde opasiteler izlenmektedir. Mediastinal "
        "pencerede lenfadenopati saptanmamıştır. Plevral effüzyon yoktur. "
        "Perikardial effüzyon izlenmemektedir. Ana pulmoner arter çapı doğaldır. "
        "Trakea ve ana bronşlar doğal kalibrasyondadır."
    ),

    "abdomen_usg": (
        "Batın ultrasonografisinde karaciğer boyutları ve parankim ekojenitesi "
        "doğaldır. Safra kesesi duvar kalınlığı normal olup lümeninde kalkül "
        "izlenmemektedir. İntrahepatik ve ekstrahepatik safra yolları doğal "
        "çaptadır. Pankreas, dalak boyutları ve ekojenitesi doğaldır. Her iki "
        "böbrek boyutları ve parankim kalınlıkları doğaldır. Pelvikalisiyel "
        "sistemde dilatasyon yoktur. Serbest sıvı izlenmemektedir."
    ),

    "genel": (
        "Radyoloji raporu. İncelemede patolojik bulgu saptanmamıştır. "
        "Sinyal değişikliği izlenmektedir. Kontrastlı serilerde enhancement "
        "gözlenmemektedir. Boyutları doğaldır. Konfigürasyon doğaldır."
    ),
}


# ═══════════════════════════════════════════════════
# LLM düzeltme için kapsamlı tıbbi terim listesi
# ═══════════════════════════════════════════════════

MEDICAL_GLOSSARY = """
## Radyoloji Tıbbi Terim Sözlüğü

### Anatomik Yapılar
serebrum, serebellum, serebellar tonsil, beyin sapı, pons, medulla oblongata,
hipotalamus, talamus, hipokampus, amigdala, bazal ganglionlar, kaudat nükleus,
putamen, globus pallidus, korpus kallozum, forniks, singulat girus,
lateral ventrikül, üçüncü ventrikül, dördüncü ventrikül, akueduktus sylvii,
hipofiz bezi, pineal bez, koroid pleksus, foramen magnum,
medulla spinalis, konus medullaris, kauda ekuina, filum terminale,
vertebra korpusu, pedikül, lamina, spinöz proses, transvers proses,
disk, anulus fibrozus, nükleus pulpozus, ligamentum flavum,
nöroforamen, spinal kanal, epidural mesafe, subaraknoid mesafe,
faset eklem, sakroiliak eklem, interkondiler çentik,
aorta, vena kava, pulmoner arter, pulmoner ven,
trakea, bronş, bronşiol, alveoler yapılar,
karaciğer, safra kesesi, pankreas, dalak, böbrek,
pelvis, mesane, uterus, overler, prostat

### Patolojik Terimler
hiperintens, hipointens, izointens, heterojen, homojen,
sinyal değişikliği, sinyal artışı, sinyal kaybı,
difüzyon kısıtlanması, kontrastlanma, enhancement,
lezyon, kitle, nodül, kist, apse, hematom,
ödem, gliozis, demiyelinizasyon, ensefalomalazi,
stenoz, oklüzyon, tromboz, anevrizma, diseksiyon,
protrüzyon, ekstrüzyon, herniasyon, sekestrasyon,
konsolidasyon, atelektazi, ampiyem, pnömotoraks,
efüzyon, plevral efüzyon, perikardiyal efüzyon, asit,
lenfadenopati, hepatomegali, splenomegali, nefromegali,
kalsifikasyon, ossifikasyon, skleroz, erozyon,
fraktür, subluksasyon, dislokasyon, dejenerasyon,
fibrozis, nekroz, inflamasyon, infiltrasyon,
buzlu cam opasitesi, buzlu cam dansitesi, ground-glass,
hidrosefalus, hidronefrozis, hidroüreter

### MR Sekansları ve Teknik Terimler
T1 ağırlıklı, T2 ağırlıklı, FLAIR, DWI, ADC, SWI, GRE,
kontrastlı seriler, kontrastsız seriler, post-kontrast,
aksiyel plan, sagittal plan, koronal plan, oblik plan,
gadolinyum, intravenöz kontrast madde,
sinyal-gürültü oranı, artefakt, hareket artefaktı,
intrakranial, ekstrakranial, intradural, ekstradural,
intramedüller, ekstramedüller, intraparankimal,
anteroposterior, mediolateral, kraniokaudal,
anterolateral, posterolateral, posterosantral,
subkondral, subkortikal, perivasküler, periventriküler

### Rapor Kalıpları
izlenmektedir, izlenmemektedir, saptanmamıştır, saptanmıştır,
mevcuttur, mevcut değildir, gözlenmektedir, gözlenmemektedir,
uyumludur, düşündürmektedir, ekarte edilemez,
doğal boyuttadır, doğal sınırlardadır, doğal konfigürasyondadır,
patolojik bulgu yoktur, patolojik sinyal saptanmamıştır,
klinik korelasyon önerilir, kontrol önerilir,
ileri tetkik önerilir, kontrastlı inceleme önerilir
"""


# Rapor tipleri ve Türkçe isimleri
REPORT_TYPES = {
    "kranial_mr": "Kranial MR",
    "lomber_mr": "Lomber MR",
    "akciger_grafi": "Akciğer Grafisi (PA)",
    "toraks_bt": "Toraks BT",
    "abdomen_usg": "Abdomen USG",
    "genel": "Genel Radyoloji Raporu",
}
