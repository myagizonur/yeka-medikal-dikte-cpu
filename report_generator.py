"""
YEKA MedDikte — PDF Rapor Üretici
Bursa Uludağ Üniversitesi kurumsal formatı
"""

import io
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image,
)
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from dotenv import load_dotenv
from medical_terms import REPORT_TYPES

load_dotenv()

LOGO_PATH = os.path.join(os.path.dirname(__file__), "static", "uludag_logo.png")

# Font yükleme — Liberation Sans (Türkçe destekli) veya Helvetica fallback
FONT_NORMAL = "Helvetica"
FONT_BOLD   = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"

_font_candidates = [
    ("/usr/share/fonts/opentype/liberation",  "LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf"),
    ("/usr/share/fonts/truetype/liberation",  "LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf"),
    ("/usr/share/fonts/liberation",           "LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf"),
    ("/System/Library/Fonts/Supplemental",    "Arial.ttf",                  "Arial Bold.ttf",          "Arial Italic.ttf"),
]

for _d, _r, _b, _i in _font_candidates:
    if os.path.exists(os.path.join(_d, _r)):
        try:
            pdfmetrics.registerFont(TTFont("_AppFont",       os.path.join(_d, _r)))
            pdfmetrics.registerFont(TTFont("_AppFont-Bold",  os.path.join(_d, _b)))
            pdfmetrics.registerFont(TTFont("_AppFont-Italic",os.path.join(_d, _i)))
            pdfmetrics.registerFontFamily("_AppFont", normal="_AppFont", bold="_AppFont-Bold", italic="_AppFont-Italic")
            FONT_NORMAL = "_AppFont"
            FONT_BOLD   = "_AppFont-Bold"
            FONT_ITALIC = "_AppFont-Italic"
            break
        except Exception:
            pass

# Kurumsal renkler (Uludağ Üniversitesi lacivert + turkuaz)
NAVY   = HexColor("#1a2456")
TEAL   = HexColor("#009fae")
GRAY   = HexColor("#555555")
LGRAY  = HexColor("#dddddd")
DGRAY  = HexColor("#333333")


def _styles():
    s = getSampleStyleSheet()

    s.add(ParagraphStyle(
        "HospitalName",
        fontSize=13,
        fontName=FONT_BOLD,
        textColor=NAVY,
        spaceAfter=1,
    ))
    s.add(ParagraphStyle(
        "DeptName",
        fontSize=9,
        fontName=FONT_NORMAL,
        textColor=GRAY,
        spaceAfter=2,
    ))
    s.add(ParagraphStyle(
        "ReportTitle",
        fontSize=12,
        fontName=FONT_BOLD,
        textColor=white,
        alignment=TA_CENTER,
        spaceAfter=0,
        spaceBefore=0,
    ))
    s.add(ParagraphStyle(
        "FieldLabel",
        fontSize=8,
        fontName=FONT_BOLD,
        textColor=NAVY,
    ))
    s.add(ParagraphStyle(
        "FieldValue",
        fontSize=9,
        fontName=FONT_NORMAL,
        textColor=DGRAY,
    ))
    s.add(ParagraphStyle(
        "SectionHead",
        fontSize=10,
        fontName=FONT_BOLD,
        textColor=NAVY,
        spaceBefore=10,
        spaceAfter=4,
    ))
    s.add(ParagraphStyle(
        "BodyText2",
        fontSize=10,
        fontName=FONT_NORMAL,
        leading=16,
        textColor=DGRAY,
        spaceAfter=4,
    ))
    s.add(ParagraphStyle(
        "FooterText",
        fontSize=7,
        fontName=FONT_NORMAL,
        textColor=GRAY,
        alignment=TA_CENTER,
    ))
    s.add(ParagraphStyle(
        "DoctorName",
        fontSize=10,
        fontName=FONT_BOLD,
        textColor=DGRAY,
        alignment=TA_LEFT,
    ))
    s.add(ParagraphStyle(
        "DoctorTitle",
        fontSize=8,
        fontName=FONT_NORMAL,
        textColor=GRAY,
        alignment=TA_LEFT,
    ))
    return s


def generate_pdf(
    report_text: str,
    report_type: str = "genel",
    patient_name: str = "",
    patient_tc: str = "",
    doctor_name: str = "",
    doctor_title: str = "Uzm. Dr.",
) -> bytes:
    buffer = io.BytesIO()

    hospital_name = os.getenv("HOSPITAL_NAME", "Bursa Uludağ Üniversitesi Hastanesi")
    hospital_dept = os.getenv("HOSPITAL_DEPT", "Radyoloji Anabilim Dalı")
    report_type_name = REPORT_TYPES.get(report_type, "Radyoloji Raporu")
    now = datetime.now()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = _styles()
    W = A4[0] - 40 * mm  # kullanılabilir genişlik
    elements = []

    # ══════════════════════════════════════════════
    # HEADER: Logo sağ üst, üniversite adı sol
    # ══════════════════════════════════════════════
    logo_cell = ""
    if os.path.exists(LOGO_PATH):
        logo_img = Image(LOGO_PATH)
        logo_img._restrictSize(30 * mm, 30 * mm)
        logo_cell = logo_img

    header_data = [[
        [
            Paragraph(hospital_name, styles["HospitalName"]),
            Paragraph(hospital_dept, styles["DeptName"]),
        ],
        logo_cell,
    ]]
    header_table = Table(header_data, colWidths=[W - 35 * mm, 35 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",        (1, 0), (1, 0),   "RIGHT"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=2, color=NAVY, spaceAfter=4))
    elements.append(HRFlowable(width="100%", thickness=1, color=TEAL, spaceAfter=8))

    # ══════════════════════════════════════════════
    # RAPOR BAŞLIĞI (renkli banner)
    # ══════════════════════════════════════════════
    title_table = Table(
        [[Paragraph(report_type_name.upper(), styles["ReportTitle"])]],
        colWidths=[W],
        rowHeights=[8 * mm],
    )
    title_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), NAVY),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [3, 3, 3, 3]),
    ]))
    elements.append(title_table)
    elements.append(Spacer(1, 8))

    # ══════════════════════════════════════════════
    # HASTA & TARİH BİLGİLERİ
    # ══════════════════════════════════════════════
    col1 = W * 0.22
    col2 = W * 0.30
    col3 = W * 0.22
    col4 = W * 0.26

    info_data = [
        [
            Paragraph("Hasta Adı Soyadı", styles["FieldLabel"]),
            Paragraph(patient_name or "—", styles["FieldValue"]),
            Paragraph("Rapor Tarihi", styles["FieldLabel"]),
            Paragraph(now.strftime("%d.%m.%Y"), styles["FieldValue"]),
        ],
        [
            Paragraph("TC Kimlik No", styles["FieldLabel"]),
            Paragraph(patient_tc or "—", styles["FieldValue"]),
            Paragraph("Rapor Saati", styles["FieldLabel"]),
            Paragraph(now.strftime("%H:%M"), styles["FieldValue"]),
        ],
        [
            Paragraph("Rapor Tipi", styles["FieldLabel"]),
            Paragraph(report_type_name, styles["FieldValue"]),
            Paragraph("Birim", styles["FieldLabel"]),
            Paragraph(hospital_dept, styles["FieldValue"]),
        ],
    ]
    info_table = Table(info_data, colWidths=[col1, col2, col3, col4])
    info_table.setStyle(TableStyle([
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [HexColor("#f5f7fa"), white]),
        ("LINEBELOW",     (0, -1), (-1, -1), 0.5, LGRAY),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=LGRAY, spaceAfter=8))

    # ══════════════════════════════════════════════
    # RAPOR İÇERİĞİ
    # ══════════════════════════════════════════════
    SECTION_KEYWORDS = [
        "BULGULAR", "SONUC", "SONUÇ", "ÖNERİ", "ONERI",
        "TEKNİK", "TEKNIK", "KLİNİK", "KLINIK", "YORUM",
        "BULGU", "DEĞERLENDIRME", "DEĞERLENDİRME",
    ]

    lines = report_text.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            elements.append(Spacer(1, 4))
            continue

        upper = stripped.upper().rstrip(":").rstrip()
        is_section = any(upper == kw or upper.startswith(kw + ":") for kw in SECTION_KEYWORDS)

        if is_section:
            elements.append(Paragraph(stripped, styles["SectionHead"]))
            elements.append(HRFlowable(width="40%", thickness=1, color=TEAL, spaceAfter=4))
        else:
            safe = (stripped
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))
            elements.append(Paragraph(safe, styles["BodyText2"]))

    # ══════════════════════════════════════════════
    # İMZA & ALT BİLGİ
    # ══════════════════════════════════════════════
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=LGRAY, spaceAfter=10))

    if doctor_name:
        sign_data = [[
            [
                Paragraph(f"{doctor_title} {doctor_name}", styles["DoctorName"]),
                Paragraph(hospital_dept, styles["DoctorTitle"]),
                Paragraph(hospital_name, styles["DoctorTitle"]),
            ],
            [
                Paragraph("İmza / Kaşe", styles["DoctorTitle"]),
                Spacer(1, 15 * mm),
            ],
        ]]
        sign_table = Table(sign_data, colWidths=[W * 0.6, W * 0.4])
        sign_table.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("ALIGN",        (1, 0), (1, 0),   "CENTER"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOX",          (1, 0), (1, 0),   0.5, LGRAY),
            ("TOPPADDING",   (1, 0), (1, 0),   4),
            ("LEFTPADDING",  (1, 0), (1, 0),   4),
        ]))
        elements.append(sign_table)
        elements.append(Spacer(1, 8))

    # Alt bant
    footer_table = Table(
        [[Paragraph(
            f"Bu rapor Bursa Uludağ Üniversitesi YEKA MedDikte sistemi tarafından oluşturulmuştur. "
            f"Tarih: {now.strftime('%d.%m.%Y %H:%M')}",
            styles["FooterText"],
        )]],
        colWidths=[W],
    )
    footer_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), HexColor("#f0f3f8")),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("BOX",          (0, 0), (-1, -1), 0.5, LGRAY),
    ]))
    elements.append(footer_table)

    doc.build(elements)
    return buffer.getvalue()
