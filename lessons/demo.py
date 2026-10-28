"""Demo lessons for showcasing the portal (REQ-OPS-009).

Everything is owned by two demo users that can't sign in, so `remove()` deletes exactly the
demo data and nothing real. Images are drawn with Pillow and saved through process_image, like
an upload.
"""

import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from core.audit import audit
from lessons.images import process_image
from lessons.models import (
    BuildingComponent,
    Discipline,
    IssueType,
    Lesson,
    LessonImage,
    Phase,
    Project,
)

DEMO_STAFF = "demo-staff"
DEMO_QA = "demo-qa"
DEMO_PROJECTS = [
    "Riverside Public Library",
    "Harbour View Condominiums",
    "St. Clair Medical Clinic",
    "Westview Secondary School",
    "Lakeshore Fire Hall",
    "Ambassador Logistics Centre",
]

A, S, R = Lesson.Status.APPROVED, Lesson.Status.SUBMITTED, Lesson.Status.REJECTED
H, M, L = Lesson.Impact.HIGH, Lesson.Impact.MEDIUM, Lesson.Impact.LOW

# title, project index, phase, discipline, issue type, component, impact, status, days ago,
# drawing, failed note, fixed note, extras (anonymise, incorporation, cost, delay), description,
# lesson. One row per lesson reads better than the formatter's layout.
# fmt: off
LESSONS = [
    ("Missing parapet flashing at roof edge", 0, "CD", "Architecture", "Omission", "Roofing",
     H, A, 6, "elevation", "NO FLASHING SHOWN", "CAP FLASHING ADDED",
     {"in_specs": True, "cost_impact": 18500, "time_impact_days": 6},
     "The parapet section showed the membrane turned up but no metal cap flashing. Water got "
     "behind the membrane during the first storm and stained the new ceiling below.",
     "Every parapet section must show cap flashing, membrane termination and blocking. Use "
     "standard detail A-501 as the starting point."),
    ("Door swing clashes with corridor handrail", 1, "DD", "Architecture", "Coordination clash",
     "Interiors", M, A, 14, "plan", "DOOR HITS RAIL", "RAIL RETURNED",
     {"anonymise": True},
     "Suite entry doors swung into the corridor where the accessibility handrail runs, leaving "
     "under 400 mm clear when open.",
     "Check door swings against handrails and wall-mounted items on every corridor plan before "
     "issuing DD."),
    ("Fire damper not shown at rated wall", 2, "CD", "Mechanical", "Omission", "MEP services",
     H, A, 21, "section", "DUCT THROUGH 1 HR WALL", "FIRE DAMPER ADDED",
     {"in_specs": True, "in_standard_details": True, "cost_impact": 9200, "time_impact_days": 4},
     "A supply duct crossed a 1-hour corridor wall with no fire damper on the mechanical "
     "drawings. The inspector flagged it at cover-up.",
     "Overlay the life-safety plan on the mechanical plans and mark a damper at every rated "
     "wall the ductwork crosses."),
    ("Window sill height below guard requirement", 3, "SD", "Architecture", "Error",
     "Envelope/Facade", H, A, 33, "elevation", "SILL 450 AFF", "SILL 1070 AFF",
     {},
     "Second-floor classroom windows had sills at 450 mm with operable sashes and no guard, "
     "below the code minimum for openings above grade.",
     "Set operable window sills at 1070 mm or add a guard; check every elevation above the "
     "ground floor at SD."),
    ("Slab edge missing insulation", 4, "CD", "Structural", "Omission", "Structure",
     M, A, 47, "section", "THERMAL BRIDGE", "SLAB EDGE INSULATED",
     {"in_standard_details": True, "cost_impact": 4100},
     "Exposed slab edges at the apparatus bay had no insulation or thermal break, causing "
     "condensation inside along the floor line.",
     "Show slab-edge insulation or a thermal break on every wall section where the slab meets "
     "the envelope."),
    ("Grab bar blocks transfer space", 0, "CA", "Interiors", "Site lesson", "Interiors",
     L, A, 58, "plan", "BAR IN TRANSFER ZONE", "BAR RELOCATED",
     {"in_onboarding": True},
     "Accessible washroom grab bars were installed per the elevation, but the elevation put "
     "the side bar across the wheelchair transfer space.",
     "Dimension grab bars from the toilet centreline on accessible washroom elevations, and "
     "check against the transfer space."),
    ("Rooftop unit exceeds structural allowance", 5, "DD", "Mechanical", "Coordination clash",
     "Roofing", H, A, 66, "section", "RTU 2,900 KG", "DUNNAGE ON COLUMNS",
     {"anonymise": True, "cost_impact": 32000, "time_impact_days": 15},
     "The selected rooftop unit was 40% heavier than the load structural had allowed. "
     "Reinforcement was needed after the steel was ordered.",
     "Send equipment weights to structural at DD and confirm the roof allowance in writing "
     "before the steel is released."),
    ("Exit sign missing at corridor turn", 2, "TA", "Electrical", "Omission", "MEP services",
     M, A, 80, "plan", "NO EXIT SIGN", "EXIT SIGN ADDED",
     {"in_specs": True},
     "The corridor turned twice between the waiting area and the stair, but the plan only had "
     "exit signs at the doors. An addendum was needed during tender.",
     "Walk every exit path on the plan and add a sign wherever the exit is not visible."),
    ("Stair nosing contrast not specified", 3, "PC", "Architecture", "Site lesson", "Interiors",
     L, A, 95, "detail", "NO CONTRAST STRIP", "CONTRASTING NOSING",
     {},
     "Students reported the main stair hard to read in low light. The specification did not "
     "call for contrasting nosings.",
     "Specify contrasting nosings on all stairs in the finishes schedule and in the stair "
     "detail."),
    ("Curtain wall anchor misses slab edge", 1, "CA", "Structural", "Coordination clash",
     "Envelope/Facade", H, A, 110, "detail", "ANCHOR OFF SLAB", "EMBED PLATE ADDED",
     {"anonymise": True, "cost_impact": 21000, "time_impact_days": 10},
     "Curtain wall anchors landed 60 mm beyond the slab edge at three floors because the slab "
     "edge was revised after the shop drawings were reviewed.",
     "Re-check curtain wall shop drawings against every slab edge revision issued after the "
     "first review."),
    ("Sump pit not coordinated with footing", 4, "SD", "Plumbing", "Error", "Foundations",
     M, A, 128, "section", "PIT IN FOOTING", "PIT SHIFTED 1.2 M",
     {"in_onboarding": True, "time_impact_days": 3},
     "The plumbing sump pit was located inside a column footing. It was found when the "
     "foundations were set out.",
     "Overlay below-grade plumbing on the foundation plan before SD sign-off."),
    ("Loading dock canopy below truck clearance", 5, "DD", "Architecture", "Error", "Structure",
     H, S, 2, "elevation", "CLEAR 3.9 M", "CLEAR 4.6 M",
     {"cost_impact": 15000},
     "The dock canopy was drawn at 3.9 m clear, lower than the 4.6 m the operator's trailers "
     "need.",
     "Confirm vehicle clearances with the operator and note them on the dock elevations."),
    ("Ceiling access panel missing at valves", 2, "CD", "Mechanical", "Omission", "MEP services",
     L, S, 1, "plan", "NO ACCESS PANEL", "PANEL 600 x 600",
     {},
     "Isolation valves above a drywall ceiling in the exam rooms had no access panels shown on "
     "the reflected ceiling plans.",
     "Mark access panels on the RCP wherever valves, dampers or junction boxes sit above a "
     "hard ceiling."),
    ("Bike rack placed on fire route", 3, "CA", "Landscape", "Site lesson", "Site works",
     L, R, 40, "plan", "RACK IN FIRE ROUTE", "RACK MOVED TO PLAZA",
     {},
     "The bike rack was shown inside the painted fire route. This was a site decision, not a "
     "design error, so it was rejected as a lesson.",
     "Not published."),
]
# fmt: on


def _font(size):
    return ImageFont.load_default(size=size)


def _draw(view, failed, note, seed):
    """A simple redline-style drawing: grid, linework, then a red cloud or a green fix."""
    image = Image.new("RGB", (1200, 800), (250, 250, 246))
    draw = ImageDraw.Draw(image)
    for x in range(0, 1200, 40):
        draw.line([(x, 0), (x, 800)], fill=(231, 233, 236))
    for y in range(0, 800, 40):
        draw.line([(0, y), (1200, y)], fill=(231, 233, 236))
    ink = (45, 45, 48)
    if view == "elevation":
        draw.rectangle([180, 220, 1020, 640], outline=ink, width=6)
        draw.line([(160, 220), (1040, 220)], fill=ink, width=10)
        for i in range(4):
            x = 240 + i * 190 + (seed % 3) * 6
            draw.rectangle([x, 330, x + 120, 470], outline=ink, width=4)
        target = (780, 160, 1060, 300)
    elif view == "plan":
        draw.rectangle([140, 160, 1060, 660], outline=ink, width=8)
        draw.line([(140, 410), (1060, 410)], fill=ink, width=5)
        for i in range(3):
            x = 260 + i * 260
            draw.arc([x, 410, x + 160, 570], 270, 360, fill=ink, width=3)
            draw.line([(x, 410), (x, 490)], fill=ink, width=3)
        target = (520, 300, 820, 520)
    elif view == "section":
        draw.rectangle([160, 520, 1040, 580], fill=(200, 200, 196), outline=ink, width=4)
        draw.rectangle([160, 200, 1040, 250], fill=(200, 200, 196), outline=ink, width=4)
        draw.rectangle([480, 250, 560, 520], outline=ink, width=4)
        draw.line([(160, 380), (1040, 380)], fill=ink, width=3)
        target = (380, 300, 700, 460)
    else:  # detail
        draw.rectangle([300, 180, 520, 640], fill=(210, 210, 206), outline=ink, width=5)
        draw.rectangle([520, 380, 980, 460], fill=(225, 225, 221), outline=ink, width=5)
        draw.line([(520, 300), (980, 300)], fill=ink, width=3)
        target = (440, 260, 760, 520)
    draw.text((180, 80), f"{view.upper()}  1:{20 + seed * 5}", fill=ink, font=_font(28))
    if failed:
        red = (210, 41, 48)
        draw.ellipse(target, outline=red, width=9)
        tip = (target[2] - 20, target[1] + 20)
        draw.line([tip, (tip[0] + 90, tip[1] - 90)], fill=red, width=6)
        draw.text((min(tip[0] - 200, 820), max(tip[1] - 140, 20)), note, fill=red, font=_font(30))
    else:
        green = (30, 125, 69)
        x0, y0, x1, y1 = target
        draw.line([(x0 + 40, (y0 + y1) // 2), (x1 - 40, (y0 + y1) // 2)], fill=green, width=12)
        draw.text((min(x0, 820), max(y0 - 60, 20)), note, fill=green, font=_font(30))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return SimpleUploadedFile("demo.png", buffer.getvalue(), content_type="image/png")


def _lookup(model, name):
    """The seeded row by name, or the first active row if an admin renamed it."""
    return model.objects.filter(name=name).first() or model.objects.active().first()


def is_loaded():
    return get_user_model().objects.filter(username__in=[DEMO_STAFF, DEMO_QA]).exists()


@transaction.atomic
def load():
    """Create the demo users, projects and lessons. Returns the number of lessons."""
    User = get_user_model()
    staff, qa = (
        User.objects.create_user(username=name, first_name="Demo", last_name=role)
        for name, role in [(DEMO_STAFF, "Staff"), (DEMO_QA, "Reviewer")]
    )  # create_user with no password sets an unusable one: these accounts can't sign in
    projects = [Project.objects.get_or_create(name=name)[0] for name in DEMO_PROJECTS]
    now = timezone.now()
    for seed, row in enumerate(LESSONS):
        (
            title,
            project,
            phase,
            discipline,
            issue_type,
            component,
            impact,
            status,
            days_ago,
            view,
            failed_note,
            fixed_note,
            extras,
            description,
            lesson_text,
        ) = row
        lesson = Lesson.objects.create(
            title=title,
            description=description,
            lesson=lesson_text,
            project=projects[project],
            phase=Phase.objects.filter(code=phase).first() or Phase.objects.active().first(),
            discipline=_lookup(Discipline, discipline),
            issue_type=_lookup(IssueType, issue_type),
            building_component=_lookup(BuildingComponent, component),
            impact=impact,
            submitted_by=staff,
            **extras,
        )
        submitted_at = now - timedelta(days=days_ago + 3)
        reviewed = None if status == S else now - timedelta(days=days_ago)
        Lesson.objects.filter(pk=lesson.pk).update(
            status=status,
            submitted_at=submitted_at,
            reviewed_by=None if status == S else qa,
            reviewed_at=reviewed,
            approved_at=reviewed if status == A else None,
        )
        for kind, failed, note in [
            (LessonImage.Kind.FAILED, True, failed_note),
            (LessonImage.Kind.FIXED, False, fixed_note),
        ]:
            LessonImage.objects.create(
                lesson=lesson, kind=kind, file=process_image(_draw(view, failed, note, seed))
            )
    audit("demo_load", count=len(LESSONS))
    return len(LESSONS)


@transaction.atomic
def remove():
    """Delete the demo lessons, their image files, demo projects and demo users."""
    User = get_user_model()
    users = User.objects.filter(username__in=[DEMO_STAFF, DEMO_QA])
    lessons = Lesson.objects.filter(submitted_by__in=users)
    count = lessons.count()
    for image in LessonImage.objects.filter(lesson__in=lessons):
        image.file.delete(save=False)
    lessons.delete()
    # Only demo projects that no real lesson uses.
    Project.objects.filter(name__in=DEMO_PROJECTS, lessons__isnull=True).delete()
    users.delete()
    audit("demo_remove", count=count)
    return count
