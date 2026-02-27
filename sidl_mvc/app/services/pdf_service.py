"""
SERVICE — Generación de PDF con ReportLab
Genera el reporte profesional de auditoría QA en 3 páginas.
"""

from pathlib import Path
from datetime import datetime

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable, PageBreak
    )
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False
    print("⚠️  ReportLab no instalado. Instala con: pip install reportlab")


def generar_pdf(auditoria: dict, ruta_salida: Path) -> Path:
    """Genera el PDF completo del reporte. Retorna la ruta del archivo."""
    if not REPORTLAB_OK:
        raise RuntimeError("ReportLab no está instalado. Ejecuta: pip install reportlab")

    # ── Paleta de colores ─────────────────────────────────────────────────────
    C_INK    = colors.HexColor("#050b14")
    C_MED    = colors.HexColor("#0c1829")
    C_CARD   = colors.HexColor("#101f35")
    C_COB    = colors.HexColor("#0f4c8a")
    C_SKY    = colors.HexColor("#38bdf8")
    C_GREEN  = colors.HexColor("#10b981")
    C_AMBER  = colors.HexColor("#f59e0b")
    C_RED    = colors.HexColor("#ef4444")
    C_PURPLE = colors.HexColor("#a78bfa")
    C_WHITE  = colors.white
    C_GREY   = colors.HexColor("#7ca3c4")
    C_GREY_D = colors.HexColor("#3d6484")

    COLOR_SEV = {"critical": C_RED, "high": C_AMBER, "medium": C_SKY, "low": C_GREEN}
    ETIQ_SEV  = {"critical": "CRÍTICO", "high": "ALTO", "medium": "MEDIO", "low": "BAJO"}

    doc = SimpleDocTemplate(
        str(ruta_salida), pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm,  bottomMargin=18*mm,
        title="SiDL — Reporte de Auditoría QA",
        author="SiDL v2.0",
    )

    W = 180*mm  # ancho útil
    estilos = getSampleStyleSheet()

    def est(nombre, **kw):
        base = kw.pop("base", "Normal")
        return ParagraphStyle(nombre, parent=estilos[base], **kw)

    e_titulo  = est("T", fontSize=30, textColor=C_WHITE,  fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4)
    e_sub     = est("S", fontSize=11, textColor=C_GREY,   fontName="Helvetica",      alignment=TA_CENTER, spaceAfter=6)
    e_sec     = est("SE",fontSize=11, textColor=C_SKY,    fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=6)
    e_clausula= est("CL",fontSize=8,  textColor=C_SKY,    fontName="Helvetica-Oblique", spaceBefore=3, spaceAfter=3)
    e_desc    = est("DE",fontSize=8,  textColor=C_GREY,   fontName="Helvetica",      spaceBefore=3, spaceAfter=3, leading=12)
    e_tec     = est("TE",fontSize=7,  textColor=C_PURPLE, fontName="Helvetica-Oblique", spaceAfter=2)
    e_ik      = est("IK",fontSize=8,  textColor=C_SKY,    fontName="Helvetica-Bold")
    e_iv      = est("IV",fontSize=8,  textColor=C_WHITE,  fontName="Helvetica")
    e_pie     = est("PI",fontSize=6,  textColor=C_GREY_D, fontName="Helvetica",      alignment=TA_CENTER)
    e_wh      = est("WH",fontSize=7,  textColor=C_SKY,    fontName="Helvetica-Bold")
    e_wc      = est("WC",fontSize=7,  textColor=C_WHITE,  fontName="Helvetica")
    e_ch      = est("CH",fontSize=7,  textColor=C_SKY,    fontName="Helvetica-Bold")

    story = []
    hallazgos = auditoria.get("hallazgos", [])
    casos     = auditoria.get("casos",     [])
    wcag      = auditoria.get("wcag",      [])
    puntaje   = auditoria.get("puntaje",   0)
    fuente    = auditoria.get("fuente_analisis", auditoria.get("fuente", "—"))
    color_p   = C_GREEN if puntaje >= 80 else C_AMBER if puntaje >= 55 else C_RED

    # ═══════════════ PORTADA ══════════════════════════════════════════════════
    story.append(Paragraph("SiDL", e_titulo))
    story.append(Paragraph("Smart Interface &amp; Documentation Lens", e_sub))

    t_badge = Table([[Paragraph("REPORTE DE AUDITORÍA MULTIMODAL QA", est("B", fontSize=8, textColor=C_INK, fontName="Helvetica-Bold", alignment=TA_CENTER))]],
                    colWidths=[120*mm])
    t_badge.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),C_SKY),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story.append(t_badge)
    story.append(Spacer(1, 8*mm))

    sesion   = auditoria.get("sesion_id", "—")[:8] if auditoria.get("sesion_id") else "—"
    info_rows = [
        [Paragraph("Documento SRS:",       e_ik), Paragraph(auditoria.get("archivo_srs", "—"), e_iv)],
        [Paragraph("Captura de Pantalla:", e_ik), Paragraph(auditoria.get("archivo_ui",  "—"), e_iv)],
        [Paragraph("Fecha de Generación:", e_ik), Paragraph(auditoria.get("fecha", datetime.now().strftime("%d/%m/%Y %H:%M")), e_iv)],
        [Paragraph("Motor de Análisis:",   e_ik), Paragraph(f"Gemini 1.5 Pro + LangChain + PyMuPDF (fuente: {fuente})", e_iv)],
        [Paragraph("ID de Auditoría:",     e_ik), Paragraph(auditoria.get("id", "—"), e_iv)],
    ]
    t_info = Table(info_rows, colWidths=[45*mm, 135*mm])
    t_info.setStyle(TableStyle([
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[C_MED, C_CARD]),
        ("TOPPADDING",    (0,0),(-1,-1), 4), ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 6), ("LINEBELOW",(0,0),(-1,-1), 0.2, C_GREY_D),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 8*mm))

    # Puntaje + severidades
    crit = auditoria.get("criticos", sum(1 for h in hallazgos if h.get("severidad")=="critical"))
    alto = auditoria.get("altos",    sum(1 for h in hallazgos if h.get("severidad")=="high"))
    med  = auditoria.get("medios",   sum(1 for h in hallazgos if h.get("severidad")=="medium"))
    bajo = auditoria.get("bajos",    sum(1 for h in hallazgos if h.get("severidad")=="low"))

    def p_sev(n, color, label):
        return Paragraph(
            f"<font color='#{color.hexval()[2:]}' size='20'><b>{n}</b></font><br/>"
            f"<font size='6' color='#{C_GREY_D.hexval()[2:]}'>{label}</font>",
            estilos["Normal"]
        )

    sev_row = [[
        p_sev(crit, C_RED,   "CRÍTICO"),
        p_sev(alto, C_AMBER, "ALTO"),
        p_sev(med,  C_SKY,   "MEDIO"),
        p_sev(bajo, C_GREEN, "BAJO"),
        Paragraph(
            f"<font color='#{color_p.hexval()[2:]}' size='28'><b>{puntaje}</b></font><br/>"
            f"<font size='6' color='#{C_GREY_D.hexval()[2:]}'>PUNTAJE QA / 100</font>",
            estilos["Normal"]
        ),
    ]]
    t_sev = Table(sev_row, colWidths=[W/5]*5)
    t_sev.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), C_CARD),
        ("ALIGN",         (0,0),(-1,-1), "CENTER"),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 8), ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ("LINEAFTER",     (0,0),(-2,-1), 0.5, C_GREY_D),
    ]))
    story.append(t_sev)
    story.append(PageBreak())

    # ═══════════════ HALLAZGOS ════════════════════════════════════════════════
    story.append(Paragraph("HALLAZGOS DETALLADOS — INSIDE THE LENS", e_sec))
    story.append(HRFlowable(width=W, thickness=0.5, color=C_SKY, spaceAfter=6))

    for h in hallazgos:
        col  = COLOR_SEV.get(h.get("severidad","low"), C_GREY)
        etiq = ETIQ_SEV.get(h.get("severidad","low"), "—")

        t_head = Table([[
            Paragraph(etiq, est("SH", fontSize=7, textColor=C_INK, fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(f"[{h.get('id','')}] {h.get('titulo','')}", est("TH", fontSize=9, textColor=C_WHITE, fontName="Helvetica-Bold")),
        ]], colWidths=[18*mm, W-18*mm])
        t_head.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(0,0), col), ("BACKGROUND",(1,0),(1,0), C_CARD),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4),
            ("LEFTPADDING",(1,0),(1,0),6),
        ]))
        story.append(t_head)
        story.append(Paragraph(f"↳ {h.get('clausula','')}", e_clausula))
        story.append(Paragraph(h.get("desc","") or h.get("descripcion",""), e_desc))

        t_ev = Table([[
            Paragraph(f"<b>ESPERADO:</b> {h.get('esperado','')}", est("ES", fontSize=7, textColor=C_GREEN, fontName="Courier")),
            Paragraph(f"<b>OBTENIDO:</b> {h.get('obtenido','')}", est("OB", fontSize=7, textColor=C_RED,   fontName="Courier")),
        ]], colWidths=[W/2, W/2])
        t_ev.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1), C_INK),
            ("TOPPADDING",(0,0),(-1,-1),3), ("BOTTOMPADDING",(0,0),(-1,-1),3),
            ("LEFTPADDING",(0,0),(-1,-1),5), ("LINEAFTER",(0,0),(0,-1),0.3, C_GREY_D),
        ]))
        story.append(t_ev)

        tecnicas = h.get("tecnicas", [])
        if isinstance(tecnicas, str):
            import json as _json
            try: tecnicas = _json.loads(tecnicas)
            except: tecnicas = [tecnicas]
        story.append(Paragraph("Técnicas: " + " · ".join(tecnicas), e_tec))
        story.append(HRFlowable(width=W, thickness=0.3, color=C_GREY_D, spaceBefore=4, spaceAfter=6))

    story.append(PageBreak())

    # ═══════════════ WCAG + CASOS ═════════════════════════════════════════════
    story.append(Paragraph("CUMPLIMIENTO WCAG 2.1 AA — ACCESIBILIDAD", e_sec))
    story.append(HRFlowable(width=W, thickness=0.5, color=C_SKY, spaceAfter=4))

    COLOR_ESTADO = {"pass": C_GREEN, "fail": C_RED, "warn": C_AMBER}
    ETIQ_ESTADO  = {"pass": "PASA",  "fail": "FALLA", "warn": "AVISO"}

    wcag_rows = [[Paragraph(t, e_wh) for t in ["Criterio","Nombre","Nivel","Resultado","Observación"]]]
    for w in wcag:
        col_e  = COLOR_ESTADO.get(w.get("estado","warn"), C_GREY)
        etiq_e = ETIQ_ESTADO.get(w.get("estado","warn"), "—")
        wcag_rows.append([
            Paragraph(w.get("id",""),     est("wc2", fontSize=7, textColor=C_GREY,  fontName="Courier")),
            Paragraph(w.get("nombre",""), e_wc),
            Paragraph(w.get("nivel",""),  est("wn",  fontSize=7, textColor=C_GREY,  fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(etiq_e,             est("we",  fontSize=7, textColor=col_e,   fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(w.get("nota",""),   est("wno", fontSize=6, textColor=C_GREY,  fontName="Helvetica")),
        ])
    t_wcag = Table(wcag_rows, colWidths=[18*mm, 40*mm, 12*mm, 16*mm, W-86*mm])
    t_wcag.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  C_COB),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [C_MED, C_CARD]),
        ("TOPPADDING",    (0,0),(-1,-1), 3), ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 4), ("LINEBELOW",(0,0),(-1,-1), 0.2, C_GREY_D),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(t_wcag)
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("CASOS DE PRUEBA GENERADOS", e_sec))
    story.append(HRFlowable(width=W, thickness=0.5, color=C_SKY, spaceAfter=4))

    ETIQ_PRIO = {"critical":"CRÍTICO","high":"ALTO","medium":"MEDIO","low":"BAJO"}
    cp_rows = [[Paragraph(t, e_ch) for t in ["ID","Prioridad","Nombre del Caso","Resultado Esperado","Ref."]]]
    for c in casos:
        col_p  = COLOR_SEV.get(c.get("prioridad","low"), C_GREY)
        etiq_p = ETIQ_PRIO.get(c.get("prioridad",""), "—")
        nombre  = c.get("nombre","")
        esperado = c.get("esperado","")
        ref     = c.get("ref","") or c.get("ref_srs","")
        cp_id   = c.get("id","")
        prio    = c.get("prioridad","")
        cp_rows.append([
            Paragraph(cp_id, est("ci", fontSize=7, textColor=C_SKY,   fontName="Courier")),
            Paragraph(etiq_p, est("cp", fontSize=7, textColor=col_p,  fontName="Helvetica-Bold")),
            Paragraph(nombre, est("cn", fontSize=7, textColor=C_WHITE, fontName="Helvetica")),
            Paragraph(esperado, est("ce", fontSize=7, textColor=C_GREY, fontName="Helvetica")),
            Paragraph(ref, est("cr", fontSize=7, textColor=C_SKY,    fontName="Courier")),
        ])
    t_cp = Table(cp_rows, colWidths=[16*mm, 18*mm, 60*mm, 70*mm, 16*mm])
    t_cp.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  C_COB),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [C_MED, C_CARD]),
        ("TOPPADDING",    (0,0),(-1,-1), 3), ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 4), ("LINEBELOW",(0,0),(-1,-1), 0.2, C_GREY_D),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(t_cp)

    # ── Pie de página ─────────────────────────────────────────────────────────
    def pie(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFillColor(C_GREY_D)
        canvas_obj.setFont("Helvetica", 6)
        canvas_obj.drawCentredString(
            A4[0]/2, 10*mm,
            f"SiDL v2.0  |  Reporte de Auditoría QA  |  Pág. {doc_obj.page}"
        )
        canvas_obj.setStrokeColor(C_SKY)
        canvas_obj.setLineWidth(0.3)
        canvas_obj.line(15*mm, 12*mm, A4[0]-15*mm, 12*mm)
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=pie, onLaterPages=pie)
    print(f"✅  PDF generado: {ruta_salida}")
    return ruta_salida
