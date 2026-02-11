# academics/pdf_views.py

from django.http import HttpResponse
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.response import Response

from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
    OpenApiResponse,
)

from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

from academics.models import AcademicClass, Section, Schedule, ScheduleKind
from batch.models import AcademicBatch
from utils.get_school_id_by_token import get_school_for_user
from common.permissions import IsAuthenticatedAndActive, IsSchoolManagement


# As per your requirement: DB index 0 = Sunday, ... 6 = Saturday
DAYS_SUN_TO_SAT = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def fmt_time_range(start, end):
    # 1:00 PM - 1:59 PM
    return f"{start.strftime('%-I:%M %p')} - {end.strftime('%-I:%M %p')}"


def safe_teacher_name(teacher):
    if not teacher:
        return ""
    fn = getattr(teacher, "get_full_name", None)
    if callable(fn):
        return fn() or ""
    first = getattr(teacher, "first_name", "") or ""
    last = getattr(teacher, "last_name", "") or ""
    return f"{first} {last}".strip()


def build_slots_and_lookup(schedules_qs):
    schedules = list(schedules_qs)
    slots = sorted({(s.start_time, s.end_time) for s in schedules})
    lookup = {(s.day_of_week, s.start_time, s.end_time): s for s in schedules}
    return slots, lookup


def make_styles(title_size: int, text_size: int, table_size: int):
    base = getSampleStyleSheet()

    title = ParagraphStyle(
        "Title",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=title_size,
        leading=title_size + 4,
        alignment=1,
        spaceAfter=4,
    )

    text = ParagraphStyle(
        "Text",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=text_size,
        leading=text_size + 4,
        alignment=1,
        spaceAfter=2,
    )

    routine = ParagraphStyle(
        "Routine",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=text_size,
        leading=text_size + 4,
        alignment=1,
        spaceAfter=8,
    )

    cell = ParagraphStyle(
        "Cell",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=table_size,
        leading=table_size + 2,
        alignment=1,
    )

    cell_bold = ParagraphStyle(
        "CellBold",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=table_size,
        leading=table_size + 2,
        alignment=1,
    )

    return {
        "title": title,
        "text": text,
        "routine": routine,
        "cell": cell,
        "cell_bold": cell_bold,
    }


def choose_font_sizes(num_slots: int) -> tuple[int, int, int]:
    """
    Simple responsiveness:
      - Normal: title 18, text 14, table 12
      - Medium rows: title 16, text 13, table 11
      - Large rows: title 14, text 12, table 10
    """
    if num_slots >= 14:
        return (14, 12, 10)
    if num_slots >= 10:
        return (16, 13, 11)
    return (18, 14, 12)


def build_header_flowables(school, routine_title, styles):
    name = Paragraph(str(school.name or ""), styles["title"])
    address = Paragraph(str(school.address or ""), styles["text"])
    contact = Paragraph(
        f"Phone: {school.phone or '-'} | Email: {school.email or '-'}",
        styles["text"],
    )
    routine = Paragraph(str(routine_title), styles["routine"])

    return [
        name,
        address,
        contact,
        Spacer(1, 4),
        routine,
        Spacer(1, 10),
    ]


@extend_schema(
    tags=["Schedule"],
    summary="Generate Schedule Routine PDF",
    description=(
        "Generate and download class routine PDF in landscape format.\n\n"
        "- Day index: 0=Sunday ... 6=Saturday.\n"
        "- Days ordered Sunday → Saturday.\n"
        "- Rows ordered by time.\n"
        "- academic_class=all generates all classes in batch (sorted by class sort_order).\n"
        "- If class has sections, routine generated per section (page per section).\n"
        "- Watermark logo included (if available)."
    ),
    parameters=[
        OpenApiParameter(
            name="batch",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=True,
            description="AcademicBatch ID",
        ),
        OpenApiParameter(
            name="academic_class",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Class UUID or "all" (default).',
        ),
    ],
    responses={
        200: OpenApiResponse(response=OpenApiTypes.BINARY, description="PDF file (application/pdf)."),
        400: OpenApiResponse(description="Validation error."),
        404: OpenApiResponse(description="Batch/Class not found."),
        403: OpenApiResponse(description="Forbidden."),
    },
)
class SchedulePdfView(APIView):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]

    def get(self, request):
        batch_id = request.query_params.get("batch")
        class_param = request.query_params.get("academic_class") or "all"

        if not batch_id:
            return Response({"detail": "batch is required"}, status=400)

        school = get_school_for_user(request.user)

        batch = AcademicBatch.objects.filter(id=batch_id, school=school).first()
        if not batch:
            return Response({"detail": "Invalid batch"}, status=404)

        # ---- classes selection ----
        if class_param == "all":
            classes = list(
                AcademicClass.objects.filter(batch=batch, is_active=True).order_by("sort_order", "name")
            )
        else:
            cls = AcademicClass.objects.filter(id=class_param, batch=batch, is_active=True).first()
            if not cls:
                return Response({"detail": "Invalid class"}, status=404)
            classes = [cls]

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="routine.pdf"'

        doc = SimpleDocTemplate(
            response,
            pagesize=landscape(A4),
            leftMargin=0.5 * inch,
            rightMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )

        elements = []

        # ---- watermark (30% opacity) ----
        def watermark(canvas_obj, _doc):
            try:
                logo = getattr(school, "logo_file", None)
                if not logo:
                    return
                file_field = getattr(logo, "file", None)
                if not file_field:
                    return

                file_field.open("rb")
                img = ImageReader(file_field)

                canvas_obj.saveState()
                # 30% opacity (best effort; some environments may ignore alpha)
                try:
                    canvas_obj.setFillAlpha(0.30)
                except Exception:
                    pass

                page_w, page_h = landscape(A4)
                w = page_w * 0.45
                h = page_h * 0.45
                x = (page_w - w) / 2
                y = (page_h - h) / 2 - 10

                canvas_obj.drawImage(
                    img,
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                canvas_obj.restoreState()
            except Exception:
                return

        for class_index, academic_class in enumerate(classes):
            sections = list(
                Section.objects.filter(academic_class=academic_class, is_active=True).order_by("sort_order", "name")
            )

            page_units = [("class", None)]
            if sections:
                page_units = [("section", s) for s in sections]

            for unit_index, (unit_type, section) in enumerate(page_units):
                if unit_type == "section" and section:
                    routine_title = f"Routine: {academic_class.name} - {section.name}"
                else:
                    routine_title = f"Routine: {academic_class.name}"

                base = Schedule.objects.select_related("subject", "teacher").filter(batch=batch)

                if unit_type == "section" and section:
                    schedules_qs = base.filter(
                        Q(academic_class__isnull=True, section__isnull=True) |
                        Q(academic_class=academic_class, section__isnull=True) |
                        Q(academic_class=academic_class, section=section)
                    )
                else:
                    schedules_qs = base.filter(
                        Q(academic_class__isnull=True, section__isnull=True) |
                        Q(academic_class=academic_class)
                    )

                slots, lookup = build_slots_and_lookup(schedules_qs)

                # responsive sizes
                title_size, text_size, table_size = choose_font_sizes(len(slots))
                styles = make_styles(title_size, text_size, table_size)

                elements.extend(build_header_flowables(school, routine_title, styles))

                # Header row
                header_row = [Paragraph("<b>Time</b>", styles["cell_bold"])] + [
                    Paragraph(f"<b>{d}</b>", styles["cell_bold"]) for d in DAYS_SUN_TO_SAT
                ]
                data = [header_row]

                # Row highlighting per row type
                break_rows = []
                holiday_rows = []

                for start, end in slots:
                    row_index = len(data)
                    row_cells = [Paragraph(fmt_time_range(start, end), styles["cell"])]

                    row_has_break = False
                    row_has_holiday = False

                    for day_index in range(7):  # DB uses 0=Sunday..6=Saturday
                        block = lookup.get((day_index, start, end))

                        if not block:
                            row_cells.append(Paragraph("", styles["cell"]))
                            continue

                        if block.kind == ScheduleKind.CLASS:
                            subj = block.subject.name if block.subject_id else ""
                            tname = safe_teacher_name(block.teacher) if block.teacher_id else ""

                            # teacher name italic
                            if tname:
                                text = f"{subj}<br/>{tname}" if subj else f"<i>{tname}</i>"
                            else:
                                text = subj

                            row_cells.append(Paragraph(text, styles["cell"]))

                        elif block.kind == ScheduleKind.BREAK:
                            row_has_break = True
                            row_cells.append(Paragraph(block.title or "Break", styles["cell"]))

                        else:  # HOLIDAY
                            row_has_holiday = True
                            row_cells.append(Paragraph(block.title or "Holiday", styles["cell"]))

                    data.append(row_cells)

                    if row_has_break:
                        break_rows.append(row_index)
                    if row_has_holiday:
                        holiday_rows.append(row_index)

                time_w = doc.width * 0.16
                day_w = (doc.width - time_w) / 7
                col_widths = [time_w] + [day_w] * 7

                table = Table(data, repeatRows=1, colWidths=col_widths, hAlign="CENTER")

                tbl_style = [
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]

                # Row background colors
                break_bg = colors.HexColor("#FFF2CC")   # light yellow
                holiday_bg = colors.HexColor("#F8D7DA") # light red/pink

                for r in break_rows:
                    tbl_style.append(("BACKGROUND", (0, r), (-1, r), break_bg))
                for r in holiday_rows:
                    tbl_style.append(("BACKGROUND", (0, r), (-1, r), holiday_bg))

                table.setStyle(TableStyle(tbl_style))

                elements.append(table)

                # page break except last page
                is_last_class = (class_index == len(classes) - 1)
                is_last_unit = (unit_index == len(page_units) - 1)
                if not (is_last_class and is_last_unit):
                    elements.append(PageBreak())

        doc.build(elements, onFirstPage=watermark, onLaterPages=watermark)
        return response
