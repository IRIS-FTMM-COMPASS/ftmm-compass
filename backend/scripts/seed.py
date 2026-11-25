import asyncio
import datetime
import glob
import json
import os
import sys

from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from academics import current_period, semester_end, semester_start
from auth import get_password_hash
from catalog import get_all_courses, prodi_code, refresh_from_db
from database import AsyncSessionLocal
from features.scheduling.scheduler import generate_schedule
from section_codes import format_section_code, section_prefix
from models import (
    StudyProgram,
    LecturerSchedulePreference,
    ClassInstructorAssignment,
    User,
    LecturerProfile,
    StudentProfile,
    AcademicPeriod,
    Course,
    Curriculum,
    CurriculumCourse,
    StudentCurriculumAssignment,
    DegreePlan,
    DegreePlanItem,
    StudentCourseRecord,
    CourseOffering,
    CourseOfferingEligibility,
    OfferingComponent,
    ClassSection,
    ClassSchedule,
    Room,
    Timetable,
    TimetableItem,
    ElectivePollingPeriod,
    ElectiveCourseVote,
    UserNotification,
    ScheduleRun,
    CourseInstructorReference,
    ClassCountOverride,
)
from plan_storage import NoCurriculumAssignment, ensure_assignment
from scheduling_assignment_rules import snake_candidate_index, snake_order

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

PRODIS = [
    {
        "program_code": "TSD",
        "program_name": "Teknologi Sains Data",
        "degree_level": "sarjana",
    },
    {
        "program_code": "TRKB",
        "program_name": "Teknik Robotika & Kecerdasan Buatan",
        "degree_level": "sarjana",
    },
    {
        "program_code": "RN",
        "program_name": "Rekayasa Nanoteknologi",
        "degree_level": "sarjana",
    },
    {
        "program_code": "TI",
        "program_name": "Teknik Industri",
        "degree_level": "sarjana",
    },
    {
        "program_code": "TE",
        "program_name": "Teknik Elektro",
        "degree_level": "sarjana",
    },
]

PJ_PRODI_CODES = ("TSD", "TRKB", "RN", "TI", "TE")
PJ_PASSWORD = "PjProdi2026!"
LEGACY_LECTURER_EMAIL = "dosen.testing@ftmm.unair.ac.id"
VOTERS_PER_PRODI = 9
SEED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "database", "seed")
LECTURER_PASSWORD = "DosenFTMM2026!"
EKSTRAK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "Ekstrak")

COURSES_DATA = [
    {"code": "KIK101", "name": "Kalkulus I", "credits": 3, "sem": 1, "term": "ganjil", "type": "wajib"},
    {"code": "KIK102", "name": "Fisika Dasar", "credits": 3, "sem": 1, "term": "ganjil", "type": "wajib"},
    {"code": "TSD101", "name": "Pengantar Sains Data", "credits": 3, "sem": 1, "term": "ganjil", "type": "wajib"},
    {"code": "PDB101", "name": "Bahasa Indonesia Akademik", "credits": 2, "sem": 1, "term": "ganjil", "type": "wajib"},
    {"code": "PDB102", "name": "Pendidikan Kewarganegaraan", "credits": 2, "sem": 1, "term": "ganjil", "type": "wajib"},
    {"code": "PDB103", "name": "Agama Islam I", "credits": 2, "sem": 1, "term": "ganjil", "type": "wajib"},
    {"code": "KIK104", "name": "Kimia Dasar", "credits": 3, "sem": 1, "term": "ganjil", "type": "wajib"},
    {"code": "TSD103", "name": "Logika Pemrograman", "credits": 4, "sem": 1, "term": "ganjil", "type": "wajib"},

    {"code": "KIK103", "name": "Kalkulus II", "credits": 3, "sem": 2, "term": "genap", "type": "wajib"},
    {"code": "TSD102", "name": "Statistika Deskriptif", "credits": 3, "sem": 2, "term": "genap", "type": "wajib"},
    {"code": "TSD104", "name": "Pemrograman Python Lanjut", "credits": 3, "sem": 2, "term": "genap", "type": "wajib"},
    {"code": "TSD105", "name": "Aljabar Linier Elementer", "credits": 3, "sem": 2, "term": "genap", "type": "wajib"},
    {"code": "PDB104", "name": "Bahasa Inggris Komunikasi", "credits": 2, "sem": 2, "term": "genap", "type": "wajib"},
    {"code": "PDB105", "name": "Pancasila", "credits": 2, "sem": 2, "term": "genap", "type": "wajib"},
    {"code": "TSD106", "name": "Etika & Regulasi Data", "credits": 2, "sem": 2, "term": "genap", "type": "wajib"},
    {"code": "TSD107", "name": "Komputasi Numerik", "credits": 4, "sem": 2, "term": "genap", "type": "wajib"},

    {"code": "TSD201", "name": "Algoritma & Struktur Data", "credits": 3, "sem": 3, "term": "ganjil", "type": "wajib"},
    {"code": "TSD202", "name": "Statistika Inferensial", "credits": 3, "sem": 3, "term": "ganjil", "type": "wajib"},
    {"code": "TSD203", "name": "Basis Data Sains Data", "credits": 3, "sem": 3, "term": "ganjil", "type": "wajib"},
    {"code": "TSD204", "name": "Matematika Diskrit", "credits": 3, "sem": 3, "term": "ganjil", "type": "wajib"},
    {"code": "TSD205", "name": "Organisasi & Arsitektur Komputer", "credits": 3, "sem": 3, "term": "ganjil", "type": "wajib"},
    {"code": "TSD206", "name": "Kalkulus Multivariabel", "credits": 2, "sem": 3, "term": "ganjil", "type": "wajib"},

    {"code": "TSD301", "name": "Penambangan Data", "credits": 3, "sem": 5, "term": "ganjil", "type": "wajib"},
    {"code": "TSD302", "name": "Pembelajaran Mesin", "credits": 3, "sem": 5, "term": "ganjil", "type": "wajib"},
    {"code": "TSD303", "name": "Sains Data Spasial", "credits": 3, "sem": 5, "term": "ganjil", "type": "pilihan"},

    {"code": "TSD401", "name": "Pemrosesan Bahasa Alami", "credits": 3, "sem": 6, "term": "genap", "type": "pilihan"},
    {"code": "TSD402", "name": "Sistem Rekomendasi", "credits": 3, "sem": 6, "term": "genap", "type": "pilihan"},
    {"code": "TSD403", "name": "Komputasi Awan", "credits": 3, "sem": 6, "term": "genap", "type": "pilihan"},
]


async def _seed_demo_preferences(session, period, lecturers: list[User]) -> int:
    if not lecturers:
        return 0
    user_ids = {lecturer.user_id for lecturer in lecturers}
    existing = set(
        (
            await session.execute(
                select(LecturerSchedulePreference.user_id).where(
                    LecturerSchedulePreference.academic_period_id
                    == period.academic_period_id,
                    LecturerSchedulePreference.user_id.in_(user_ids),
                )
            )
        ).scalars()
    )
    created = 0
    for lecturer in sorted(lecturers, key=lambda item: item.email):
        if lecturer.user_id in existing:
            continue
        for day in range(1, 6):
            session.add(
                LecturerSchedulePreference(
                    user_id=lecturer.user_id,
                    academic_period_id=period.academic_period_id,
                    day_of_week=day,
                    start_time=datetime.time(7, 0),
                    end_time=datetime.time(17, 0),
                    kind="preferred",
                )
            )
            created += 1
    await session.flush()
    return created


async def _seed_period_instructor_mappings(
    session,
    period,
    program_ids: set,
    lecturers_by_program: dict,
) -> int:
    if not program_ids:
        return 0
    rows = (
        await session.execute(
            select(
                CurriculumCourse.curriculum_course_id,
                Curriculum.study_program_id,
                Course.course_code,
                Curriculum.curriculum_year,
            )
            .join(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
            .join(Course, Course.course_id == CurriculumCourse.course_id)
            .join(
                StudyProgram,
                StudyProgram.study_program_id == Curriculum.study_program_id,
            )
            .where(
                Curriculum.study_program_id.in_(program_ids),
                Curriculum.is_active.is_(True),
                CurriculumCourse.is_active.is_(True),
                Course.is_active.is_(True),
            )
            .order_by(
                StudyProgram.program_code,
                Course.course_code,
                Curriculum.curriculum_year,
                CurriculumCourse.curriculum_course_id,
            )
        )
    ).all()
    if not rows:
        return 0
    curriculum_course_ids = {row.curriculum_course_id for row in rows}
    references = (
        await session.execute(
            select(CourseInstructorReference).where(
                CourseInstructorReference.curriculum_course_id.in_(
                    curriculum_course_ids
                ),
                CourseInstructorReference.academic_period_id
                == period.academic_period_id,
            )
        )
    ).scalars()
    by_course: dict[object, list[CourseInstructorReference]] = {
        curriculum_course_id: [] for curriculum_course_id in curriculum_course_ids
    }
    for reference in references:
        by_course[reference.curriculum_course_id].append(reference)
    legacy_sources = (
        await session.execute(
            select(
                CourseInstructorReference.curriculum_course_id,
                CourseInstructorReference.user_id,
                CourseInstructorReference.instructor_reference_id,
            ).where(
                CourseInstructorReference.curriculum_course_id.in_(
                    curriculum_course_ids
                ),
                CourseInstructorReference.academic_period_id.is_(None),
                CourseInstructorReference.user_id.is_not(None),
            )
        )
    ).all()
    source_by_user = {
        (row.curriculum_course_id, row.user_id): row.instructor_reference_id
        for row in legacy_sources
    }
    program_offsets: dict[object, int] = {}
    created = 0
    for row in rows:
        lecturers = sorted(
            lecturers_by_program.get(row.study_program_id, []),
            key=lambda item: item.email,
        )
        if not lecturers:
            continue
        offset = program_offsets.get(row.study_program_id, 0)
        program_offsets[row.study_program_id] = offset + 1
        course_references = by_course[row.curriculum_course_id]
        had_references = bool(course_references)
        used_positions = {
            reference.position
            for reference in course_references
            if reference.position is not None
        }
        pool_users = {
            reference.user_id
            for reference in course_references
            if reference.user_id is not None
        }

        def add_reference(lecturer: User, role: str) -> None:
            nonlocal created
            position = 1
            while position in used_positions:
                position += 1
            reference = CourseInstructorReference(
                curriculum_course_id=row.curriculum_course_id,
                academic_period_id=period.academic_period_id,
                instructor_name=lecturer.full_name,
                instructor_role=role,
                user_id=lecturer.user_id,
                position=position,
                source_reference_id=source_by_user.get(
                    (row.curriculum_course_id, lecturer.user_id)
                ),
            )
            session.add(reference)
            course_references.append(reference)
            used_positions.add(position)
            pool_users.add(lecturer.user_id)
            created += 1

        if not any(reference.instructor_role == "pjmk" for reference in course_references):
            add_reference(lecturers[offset % len(lecturers)], "pjmk")
        if not had_references:
            for step in range(1, len(lecturers)):
                lecturer = lecturers[(offset + step) % len(lecturers)]
                if lecturer.user_id not in pool_users:
                    add_reference(lecturer, "teaching_team")
                if len(pool_users) >= 3:
                    break
    await session.flush()
    return created


async def _seed_demo_assignments(session, period, admin: User) -> int:
    contexts = (
        await session.execute(
            select(
                ClassSection.class_section_id,
                ClassSection.section_code,
                ClassSection.offering_component_id,
                CurriculumCourse.curriculum_course_id,
                StudyProgram.program_code,
                Course.course_code,
            )
            .join(
                OfferingComponent,
                OfferingComponent.offering_component_id
                == ClassSection.offering_component_id,
            )
            .join(
                CourseOffering,
                CourseOffering.course_offering_id
                == OfferingComponent.course_offering_id,
            )
            .join(
                CourseOfferingEligibility,
                CourseOfferingEligibility.course_offering_id
                == CourseOffering.course_offering_id,
            )
            .join(
                CurriculumCourse,
                CurriculumCourse.curriculum_course_id
                == CourseOfferingEligibility.curriculum_course_id,
            )
            .join(
                Curriculum,
                Curriculum.curriculum_id == CurriculumCourse.curriculum_id,
            )
            .join(
                StudyProgram,
                StudyProgram.study_program_id == Curriculum.study_program_id,
            )
            .join(Course, Course.course_id == CurriculumCourse.course_id)
            .where(
                CourseOffering.academic_period_id == period.academic_period_id,
                Course.is_active.is_(True),
            )
            .order_by(
                ClassSection.offering_component_id,
                StudyProgram.program_code,
                Course.course_code,
                CurriculumCourse.curriculum_course_id,
            )
        )
    ).all()
    if not contexts:
        return 0
    by_class: dict[object, list] = {}
    curriculum_course_ids = set()
    for row in contexts:
        by_class.setdefault(row.class_section_id, []).append(row)
        curriculum_course_ids.add(row.curriculum_course_id)
    pool_rows = (
        await session.execute(
            select(
                CourseInstructorReference.curriculum_course_id,
                CourseInstructorReference.instructor_role,
                CourseInstructorReference.position,
                CourseInstructorReference.user_id,
                User.email,
            )
            .join(User, User.user_id == CourseInstructorReference.user_id)
            .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
            .where(
                CourseInstructorReference.curriculum_course_id.in_(
                    curriculum_course_ids
                ),
                CourseInstructorReference.academic_period_id
                == period.academic_period_id,
                CourseInstructorReference.instructor_role.in_(("pjmk", "teaching_team")),
                User.role == "lecturer",
                User.is_active.is_(True),
            )
            .order_by(
                CourseInstructorReference.curriculum_course_id,
                CourseInstructorReference.instructor_role != "pjmk",
                CourseInstructorReference.position.is_(None),
                CourseInstructorReference.position,
                User.email,
                CourseInstructorReference.instructor_reference_id,
            )
        )
    ).all()
    pools: dict[object, list] = {
        curriculum_course_id: [] for curriculum_course_id in curriculum_course_ids
    }
    seen: dict[object, set] = {
        curriculum_course_id: set() for curriculum_course_id in curriculum_course_ids
    }
    for row in pool_rows:
        if row.user_id in seen[row.curriculum_course_id]:
            continue
        seen[row.curriculum_course_id].add(row.user_id)
        pools[row.curriculum_course_id].append(row)
    existing = set(
        (
            await session.execute(
                select(ClassInstructorAssignment.class_section_id).where(
                    ClassInstructorAssignment.academic_period_id
                    == period.academic_period_id,
                    ClassInstructorAssignment.is_active.is_(True),
                )
            )
        ).scalars()
    )
    groups: dict[object, list] = {}
    for class_rows in by_class.values():
        groups.setdefault(class_rows[0].offering_component_id, []).extend(class_rows)
    created = 0
    for context_rows in groups.values():
        rows = {row.class_section_id: row for row in context_rows}
        candidates = {}
        for row in context_rows:
            for pool_row in pools[row.curriculum_course_id]:
                key = pool_row.user_id
                candidate = (
                    pool_row.instructor_role != "pjmk",
                    pool_row.position or 10_000,
                    pool_row.email,
                    str(key),
                )
                candidates[key] = min(candidates.get(key, candidate), candidate)
        pool = [
            user_id
            for user_id, _ in sorted(candidates.items(), key=lambda item: item[1])
        ]
        classes = snake_order(
            sorted(
                rows.values(),
                key=lambda row: (row.section_code, str(row.class_section_id)),
            )
        )
        for class_index, row in enumerate(classes):
            if row.class_section_id in existing:
                continue
            pool_index = snake_candidate_index(len(pool), class_index)
            if pool_index is None:
                continue
            session.add(
                ClassInstructorAssignment(
                    class_section_id=row.class_section_id,
                    academic_period_id=period.academic_period_id,
                    curriculum_course_id=row.curriculum_course_id,
                    user_id=pool[pool_index],
                    source="auto",
                    is_pinned=False,
                    is_active=True,
                    assigned_by=admin.user_id,
                )
            )
            existing.add(row.class_section_id)
            created += 1
    await session.flush()
    return created


async def _run_demo_schedule_once(session, period, admin: User) -> None:
    completed_run = (
        await session.execute(
            select(ScheduleRun.run_id)
            .where(
                ScheduleRun.academic_period_id == period.academic_period_id,
                ScheduleRun.status == "completed",
                ScheduleRun.mode == "fill_empty",
            )
            .limit(1)
        )
    ).scalar()
    if completed_run is not None:
        print("  [SKIP] Scheduler demo sudah pernah selesai untuk periode aktif")
        return
    stats = await generate_schedule(
        session,
        period,
        mode="fill_empty",
        triggered_by=admin.user_id,
    )
    print(
        f"  [OK] Penjadwalan otomatis: {stats.assigned_count} kelas terjadwal, "
        f"{stats.unassigned_count} belum terjadwal, {stats.conflict_count} konflik"
    )


async def _seed_demo_sections(session, period) -> int:
    """Bound demo demand and materialize every section before assignment."""
    rows = (
        await session.execute(
            select(
                CourseOffering.course_id,
                CourseOffering.course_offering_id,
                CourseOffering.offering_code,
                StudyProgram.study_program_id,
                StudyProgram.program_code,
                CurriculumCourse.course_scope,
                Course.course_code,
            )
            .join(
                CourseOfferingEligibility,
                CourseOfferingEligibility.course_offering_id
                == CourseOffering.course_offering_id,
            )
            .join(
                CurriculumCourse,
                CurriculumCourse.curriculum_course_id
                == CourseOfferingEligibility.curriculum_course_id,
            )
            .join(
                Curriculum,
                Curriculum.curriculum_id == CurriculumCourse.curriculum_id,
            )
            .join(
                StudyProgram,
                StudyProgram.study_program_id == Curriculum.study_program_id,
            )
            .join(Course, Course.course_id == CourseOffering.course_id)
            .where(
                CourseOffering.academic_period_id == period.academic_period_id,
                Course.is_active.is_(True),
            )
            .order_by(Course.course_code, CourseOffering.offering_code)
        )
    ).all()
    pairs = {(row.course_id, row.study_program_id) for row in rows}
    overrides = {
        (override.course_id, override.study_program_id): override.class_count
        for override in (
            await session.execute(
                select(ClassCountOverride).where(
                    ClassCountOverride.academic_period_id
                    == period.academic_period_id
                )
            )
        ).scalars()
    }
    for course_id, program_id in sorted(pairs, key=lambda pair: tuple(map(str, pair))):
        if (course_id, program_id) not in overrides:
            session.add(
                ClassCountOverride(
                    academic_period_id=period.academic_period_id,
                    course_id=course_id,
                    study_program_id=program_id,
                    class_count=1,
                )
            )
            overrides[(course_id, program_id)] = 1
    offerings_by_course: dict[object, list] = {}
    for row in rows:
        offerings = offerings_by_course.setdefault(row.course_id, [])
        if row.course_offering_id not in {item.course_offering_id for item in offerings}:
            offerings.append(row)
    programs_by_course: dict[object, set[str]] = {}
    scopes_by_course: dict[object, set[str]] = {}
    for row in rows:
        programs_by_course.setdefault(row.course_id, set()).add(row.program_code)
        scopes_by_course.setdefault(row.course_id, set()).add(row.course_scope)
    created = 0
    for course_id, offerings in offerings_by_course.items():
        target = max(
            (
                count
                for (target_course_id, _), count in overrides.items()
                if target_course_id == course_id
            ),
            default=1,
        )
        component = (
            await session.execute(
                select(OfferingComponent)
                .where(
                    OfferingComponent.course_offering_id
                    == offerings[0].course_offering_id
                )
                .order_by(OfferingComponent.component_code)
                .limit(1)
            )
        ).scalar()
        if component is None:
            continue
        sections = (
            (
                await session.execute(
                    select(ClassSection).where(
                        ClassSection.offering_component_id
                        == component.offering_component_id
                    )
                )
            )
            .scalars()
            .all()
        )
        codes = {section.section_code for section in sections}
        prefix = section_prefix(
            programs_by_course[course_id], scopes_by_course[course_id]
        )
        ordinal = len(codes) + 1
        while len(codes) < target:
            section_code = format_section_code(prefix, ordinal)
            session.add(
                ClassSection(
                    offering_component_id=component.offering_component_id,
                    section_code=section_code,
                    capacity=40,
                    enrollment_status="open",
                )
            )
            codes.add(section_code)
            created += 1
            ordinal += 1
    await session.flush()
    return created


async def seed_data():
    async with AsyncSessionLocal() as session:
        print("[SEED 1/8] Checking and seeding Study Programs...")
        prodi_map = {}
        for p_data in PRODIS:
            stmt = select(StudyProgram).where(StudyProgram.program_code == p_data["program_code"])
            res = await session.execute(stmt)
            prodi = res.scalars().first()
            if not prodi:
                prodi = StudyProgram(
                    program_code=p_data["program_code"],
                    program_name=p_data["program_name"],
                    degree_level=p_data["degree_level"],
                    is_active=True,
                )
                session.add(prodi)
                await session.flush()
                print(f"  [CREATED] Study program: {prodi.program_code} - {prodi.program_name}")
            else:
                print(f"  [EXISTS] Study program: {prodi.program_code}")
            prodi_map[prodi.program_code] = prodi

        print("\n[SEED 2/8] Checking and seeding Academic Periods...")
        today = datetime.date.today()
        current_year, current_term = current_period(today)
        period_configs = [
            {
                "year": current_year - offset,
                "term": term,
                "active": offset == 0 and term == current_term,
            }
            for offset in (2, 1, 0)
            for term in ("ganjil", "genap")
        ]
        period_map = {}
        for pcfg in period_configs:
            stmt = select(AcademicPeriod).where(
                AcademicPeriod.academic_year_start == pcfg["year"],
                AcademicPeriod.term == pcfg["term"],
            )
            p_obj = (await session.execute(stmt)).scalars().first()
            start_date = semester_start(pcfg["year"], pcfg["term"])
            end_date = semester_end(pcfg["year"], pcfg["term"])
            if pcfg["year"] < current_year:
                semester_number = 1 if pcfg["term"] == "ganjil" else 2
            else:
                semester_number = 3 if pcfg["term"] == "ganjil" else 4
            if not p_obj:
                p_obj = AcademicPeriod(
                    academic_year_start=pcfg["year"],
                    term=pcfg["term"],
                    is_active=pcfg["active"],
                    semester_number=semester_number,
                    start_date=start_date,
                    end_date=end_date,
                )
                session.add(p_obj)
                await session.flush()
                print(f"  [CREATED] Academic period: {pcfg['year']} {pcfg['term']} (active: {pcfg['active']})")
            else:
                p_obj.is_active = pcfg["active"]
                p_obj.start_date = start_date
                p_obj.end_date = end_date
                print(f"  [EXISTS] Academic period: {pcfg['year']} {pcfg['term']}")
            p_obj.semester_number = semester_number
            period_map[f"{pcfg['year']}_{pcfg['term']}"] = p_obj

        # Hanya satu periode aktif, termasuk periode lama di database.
        for existing in (await session.execute(select(AcademicPeriod))).scalars():
            existing.is_active = False
        active_period = period_map[f"{current_year}_{current_term}"]
        active_period.is_active = True

        print("\n[SEED 3/8] Checking and seeding Test Users...")

        admin_email = "admin@ftmm.unair.ac.id"
        stmt = select(User).where(User.email == admin_email)
        admin_user = (await session.execute(stmt)).scalars().first()
        if not admin_user:
            admin_user = User(
                email=admin_email,
                full_name="Super Admin FTMM",
                role="admin",
                password_hash=get_password_hash("AdminFTMM2026!"),
                is_active=True,
            )
            session.add(admin_user)
            await session.flush()
            print(f"  [CREATED] Admin user: {admin_email}")
        else:
            admin_user.password_hash = get_password_hash("AdminFTMM2026!")
            admin_user.full_name = "Super Admin FTMM"
            print(f"  [EXISTS] Admin user: {admin_email}")

        mhs_email = "mahasiswa.testing@ftmm.unair.ac.id"
        stmt = (
            select(User)
            .options(selectinload(User.student_profile))
            .where(User.email == mhs_email)
        )
        mhs_user = (await session.execute(stmt)).scalars().first()
        tsd_prodi = prodi_map.get("TSD")
        if not mhs_user:
            mhs_user = User(
                email=mhs_email,
                full_name="Budi Santoso",
                role="student",
                password_hash=get_password_hash("Mahasiswa2026!"),
                is_active=True,
            )
            session.add(mhs_user)
            await session.flush()

            profile = StudentProfile(
                user_id=mhs_user.user_id,
                study_program_id=tsd_prodi.study_program_id,
                student_number="164231001",
                admission_year=2023,
                current_semester=3,
            )
            session.add(profile)
            print(f"  [CREATED] Mahasiswa user: {mhs_email} with NIM 164231001")
        else:
            mhs_user.password_hash = get_password_hash("Mahasiswa2026!")
            mhs_user.full_name = "Budi Santoso"
            if not mhs_user.student_profile:
                profile = StudentProfile(
                    user_id=mhs_user.user_id,
                    study_program_id=tsd_prodi.study_program_id,
                    student_number="164231001",
                    admission_year=2023,
                    current_semester=3,
                )
                session.add(profile)
            print(f"  [EXISTS] Mahasiswa user: {mhs_email}")

        demo_students = [
            ("TSD", "164231062", "mahasiswa.tsd", "Mahasiswa TSD"),
            ("TRKB", "163231062", "mahasiswa.trkb", "Mahasiswa TRKB"),
            ("RN", "162231062", "mahasiswa.rn", "Mahasiswa RN"),
            ("TI", "165231062", "mahasiswa.ti", "Mahasiswa TI"),
            ("TE", "166231062", "mahasiswa.te", "Mahasiswa TE"),
        ]
        for code, nim, email_local, full_name in demo_students:
            demo_email = f"{email_local}@ftmm.unair.ac.id"
            stmt_demo = (
                select(User)
                .options(selectinload(User.student_profile))
                .where(User.email == demo_email)
            )
            demo_user = (await session.execute(stmt_demo)).scalars().first()
            if demo_user is None:
                demo_user = User(
                    email=demo_email,
                    full_name=full_name,
                    role="student",
                    password_hash=get_password_hash("Mahasiswa2026!"),
                    is_active=True,
                )
                session.add(demo_user)
                await session.flush()
                session.add(
                    StudentProfile(
                        user_id=demo_user.user_id,
                        study_program_id=prodi_map[code].study_program_id,
                        student_number=nim,
                        admission_year=2023,
                        current_semester=3,
                    )
                )
                print(f"  [CREATED] Mahasiswa user: {demo_email} with NIM {nim}")
            else:
                demo_user.full_name = full_name
                demo_user.password_hash = get_password_hash("Mahasiswa2026!")
                demo_user.role = "student"
                demo_user.is_active = True
                if demo_user.student_profile is None:
                    session.add(
                        StudentProfile(
                            user_id=demo_user.user_id,
                            study_program_id=prodi_map[code].study_program_id,
                            student_number=nim,
                            admission_year=2023,
                            current_semester=3,
                        )
                    )
                print(f"  [EXISTS] Mahasiswa user: {demo_email}")

        # Akun dosen uji lama tidak dipakai lagi: nonaktifkan bila sudah ada,
        # dan jangan pernah dibuat ulang sebagai akun aktif.
        legacy_lecturer = (
            await session.execute(
                select(User)
                .options(selectinload(User.lecturer_profile))
                .where(User.email == LEGACY_LECTURER_EMAIL)
            )
        ).scalars().first()
        if legacy_lecturer:
            legacy_lecturer.is_active = False
            if legacy_lecturer.lecturer_profile is not None:
                legacy_lecturer.lecturer_profile.is_program_coordinator = False
            print(f"  [DEACTIVATED] Legacy lecturer user: {LEGACY_LECTURER_EMAIL}")

        with open(os.path.join(SEED_DIR, "lecturers.json"), encoding="utf-8") as handle:
            lecturer_seed = json.load(handle)
        coordinator_by_prodi = {
            item["prodi_code"]: item
            for item in lecturer_seed["lecturers"]
            if item["is_coordinator"]
        }

        for code in PJ_PRODI_CODES:
            coordinator = coordinator_by_prodi.get(code)
            pj_email = (
                coordinator["email"]
                if coordinator is not None
                else f"pj.{code.lower()}@ftmm.unair.ac.id"
            )
            legacy_email = f"pj.{code.lower()}@ftmm.unair.ac.id"
            stmt_pj = (
                select(User)
                .options(selectinload(User.lecturer_profile))
                .where(User.email == pj_email)
            )
            pj_user = (await session.execute(stmt_pj)).scalars().first()
            if pj_user is None and legacy_email != pj_email:
                stmt_legacy = (
                    select(User)
                    .options(selectinload(User.lecturer_profile))
                    .where(User.email == legacy_email)
                )
                pj_user = (await session.execute(stmt_legacy)).scalars().first()
                if pj_user is not None:
                    pj_user.email = pj_email
            prodi = prodi_map[code]
            if pj_user is None:
                pj_user = User(
                    email=pj_email,
                    full_name=f"PJ Prodi {code}",
                    role="lecturer",
                    password_hash=get_password_hash(PJ_PASSWORD),
                    is_active=True,
                )
                session.add(pj_user)
                await session.flush()
                session.add(
                    LecturerProfile(
                        user_id=pj_user.user_id,
                        study_program_id=prodi.study_program_id,
                        is_program_coordinator=True,
                        employee_number=None,
                    )
                )
                print(f"  [CREATED] PJ Prodi user: {pj_email}")
            else:
                pj_user.full_name = f"PJ Prodi {code}"
                pj_user.role = "lecturer"
                pj_user.is_active = True
                pj_user.password_hash = get_password_hash(PJ_PASSWORD)
                pj_profile = pj_user.lecturer_profile
                if pj_profile is None:
                    session.add(
                        LecturerProfile(
                            user_id=pj_user.user_id,
                            study_program_id=prodi.study_program_id,
                            is_program_coordinator=True,
                            employee_number=None,
                        )
                    )
                else:
                    pj_profile.study_program_id = prodi.study_program_id
                    pj_profile.is_program_coordinator = True
                    pj_profile.employee_number = None
                print(f"  [EXISTS] PJ Prodi user: {pj_email}")

        await session.flush()
        print(f"  [OK] {len(PJ_PRODI_CODES)} akun PJ Prodi aktif, satu PJ per prodi")
        with open(os.path.join(SEED_DIR, "rooms.json"), encoding="utf-8") as handle:
            room_seed = json.load(handle)
        for item in room_seed["rooms"]:
            existing = (
                await session.execute(
                    select(Room).where(Room.room_code == item["room_code"])
                )
            ).scalars().first()
            if existing is None:
                session.add(
                    Room(
                        room_code=item["room_code"],
                        building=item["building"],
                        floor=item.get("floor"),
                        capacity=room_seed["capacity"],
                        owner_study_program_id=None,
                        is_active=True,
                    )
                )
            else:
                existing.building = item["building"]
                existing.floor = item.get("floor")
                existing.capacity = room_seed["capacity"]
                existing.is_active = True
        await session.flush()
        print(f"  [OK] {len(room_seed['rooms'])} ruangan master tersedia")

        for item in lecturer_seed["lecturers"]:
            prodi = prodi_map[item["prodi_code"]]
            if item["is_coordinator"]:
                legacy_email = f"pj.{item['prodi_code'].lower()}@ftmm.unair.ac.id"
                account = (
                    await session.execute(
                        select(User)
                        .options(selectinload(User.lecturer_profile))
                        .where(User.email == item["email"])
                    )
                ).scalars().first()
                if account is None and item["email"] != legacy_email:
                    account = (
                        await session.execute(
                            select(User)
                            .options(selectinload(User.lecturer_profile))
                            .where(User.email == legacy_email)
                        )
                    ).scalars().first()
                    if account is not None:
                        account.email = item["email"]
                if account is None:
                    continue
                account.full_name = item["name"]
                if account.lecturer_profile is not None:
                    account.lecturer_profile.employee_number = item["employee_number"]
                    account.lecturer_profile.is_program_coordinator = True
                continue

            account = (
                await session.execute(
                    select(User)
                    .options(selectinload(User.lecturer_profile))
                    .where(User.email == item["email"])
                )
            ).scalars().first()
            if account is None:
                account = User(
                    email=item["email"],
                    full_name=item["name"],
                    role="lecturer",
                    password_hash=get_password_hash(LECTURER_PASSWORD),
                    is_active=True,
                )
                session.add(account)
                await session.flush()
                session.add(
                    LecturerProfile(
                        user_id=account.user_id,
                        study_program_id=prodi.study_program_id,
                        is_program_coordinator=False,
                        employee_number=item["employee_number"],
                    )
                )
            else:
                account.full_name = item["name"]
                account.role = "lecturer"
                account.is_active = True
                if account.lecturer_profile is None:
                    session.add(
                        LecturerProfile(
                            user_id=account.user_id,
                            study_program_id=prodi.study_program_id,
                            is_program_coordinator=False,
                            employee_number=item["employee_number"],
                        )
                    )
                else:
                    account.lecturer_profile.study_program_id = prodi.study_program_id
                    account.lecturer_profile.employee_number = item["employee_number"]
                    account.lecturer_profile.is_program_coordinator = False
        await session.flush()
        print(f"  [OK] {len(lecturer_seed['lecturers'])} profil dosen tersinkron")

        print("\n[SEED 4/8] Checking and seeding Curriculum & Courses...")
        stmt_curr = select(Curriculum).where(
            Curriculum.study_program_id == tsd_prodi.study_program_id,
            Curriculum.curriculum_year == 2023,
        )
        curriculum = (await session.execute(stmt_curr)).scalars().first()
        if not curriculum:
            curriculum = Curriculum(
                study_program_id=tsd_prodi.study_program_id,
                curriculum_name="Kurikulum TSD 2023",
                curriculum_year=2023,
                minimum_graduation_credits=144,
                standard_duration_semesters=8,
                is_active=True,
            )
            session.add(curriculum)
            await session.flush()
            print("  [CREATED] Curriculum: Kurikulum TSD 2023")
        else:
            print("  [EXISTS] Curriculum: Kurikulum TSD 2023")

        stmt_assign = select(StudentCurriculumAssignment).where(
            StudentCurriculumAssignment.user_id == mhs_user.user_id,
            StudentCurriculumAssignment.curriculum_id == curriculum.curriculum_id,
        )
        assignment = (await session.execute(stmt_assign)).scalars().first()
        if not assignment:
            assignment = StudentCurriculumAssignment(
                user_id=mhs_user.user_id,
                curriculum_id=curriculum.curriculum_id,
                is_current=True,
            )
            session.add(assignment)
            await session.flush()
            print(f"  [ASSIGNED] Curriculum to student: {mhs_user.email}")

        course_map = {}
        curriculum_course_map = {}
        for cdata in COURSES_DATA:
            stmt_c = select(Course).where(Course.course_code == cdata["code"])
            c_obj = (await session.execute(stmt_c)).scalars().first()
            if not c_obj:
                c_obj = Course(
                    course_code=cdata["code"],
                    course_name=cdata["name"],
                    is_active=True,
                )
                session.add(c_obj)
                await session.flush()
            course_map[cdata["code"]] = c_obj

            stmt_cc = select(CurriculumCourse).where(
                CurriculumCourse.curriculum_id == curriculum.curriculum_id,
                CurriculumCourse.course_id == c_obj.course_id,
            )
            cc_obj = (await session.execute(stmt_cc)).scalars().first()
            if not cc_obj:
                cc_obj = CurriculumCourse(
                    curriculum_id=curriculum.curriculum_id,
                    course_id=c_obj.course_id,
                    credits_total=cdata["credits"],
                    recommended_semester=cdata["sem"],
                    term=cdata["term"],
                    course_type=cdata["type"],
                    course_scope="program_studi",
                    is_active=True,
                )
                session.add(cc_obj)
                await session.flush()
            curriculum_course_map[cdata["code"]] = cc_obj

        print(f"  [OK] Verified and mapped {len(COURSES_DATA)} courses in curriculum")

        print("\n[SEED 5/8] Checking and seeding Student Course Records (Transkrip Akademik)...")
        sem1_records = [
            ("KIK101", "A"),
            ("KIK102", "AB"),
            ("TSD101", "A"),
            ("PDB101", "A"),
            ("PDB102", "A"),
            ("PDB103", "A"),
            ("KIK104", "AB"),
            ("TSD103", "A"),
        ]
        p_2023_ganjil = period_map[f"{current_year - 1}_ganjil"]
        for code, grade in sem1_records:
            cc = curriculum_course_map[code]
            stmt_r = select(StudentCourseRecord).where(
                StudentCourseRecord.user_id == mhs_user.user_id,
                StudentCourseRecord.curriculum_course_id == cc.curriculum_course_id,
            )
            rec = (await session.execute(stmt_r)).scalars().first()
            if rec:
                rec.academic_period_id = p_2023_ganjil.academic_period_id
            if not rec:
                rec = StudentCourseRecord(
                    user_id=mhs_user.user_id,
                    student_curriculum_assignment_id=assignment.student_curriculum_assignment_id,
                    curriculum_course_id=cc.curriculum_course_id,
                    academic_period_id=p_2023_ganjil.academic_period_id,
                    record_status="passed",
                    final_grade=grade,
                )
                session.add(rec)

        sem2_records = [
            ("KIK103", "A"),
            ("TSD102", "A"),
            ("TSD104", "AB"),
            ("TSD105", "B"),
            ("PDB104", "A"),
            ("PDB105", "A"),
            ("TSD106", "A"),
            ("TSD107", "AB"),
        ]
        p_2023_genap = period_map[f"{current_year - 1}_genap"]
        for code, grade in sem2_records:
            cc = curriculum_course_map[code]
            stmt_r = select(StudentCourseRecord).where(
                StudentCourseRecord.user_id == mhs_user.user_id,
                StudentCourseRecord.curriculum_course_id == cc.curriculum_course_id,
            )
            rec = (await session.execute(stmt_r)).scalars().first()
            if rec:
                rec.academic_period_id = p_2023_genap.academic_period_id
            if not rec:
                rec = StudentCourseRecord(
                    user_id=mhs_user.user_id,
                    student_curriculum_assignment_id=assignment.student_curriculum_assignment_id,
                    curriculum_course_id=cc.curriculum_course_id,
                    academic_period_id=p_2023_genap.academic_period_id,
                    record_status="passed",
                    final_grade=grade,
                )
                session.add(rec)

        sem3_codes = ["TSD201", "TSD202", "TSD203", "TSD204", "TSD205", "TSD206"]
        for code in sem3_codes:
            cc = curriculum_course_map[code]
            stmt_r = select(StudentCourseRecord).where(
                StudentCourseRecord.user_id == mhs_user.user_id,
                StudentCourseRecord.curriculum_course_id == cc.curriculum_course_id,
            )
            rec = (await session.execute(stmt_r)).scalars().first()
            if rec:
                rec.academic_period_id = active_period.academic_period_id
            if not rec:
                rec = StudentCourseRecord(
                    user_id=mhs_user.user_id,
                    student_curriculum_assignment_id=assignment.student_curriculum_assignment_id,
                    curriculum_course_id=cc.curriculum_course_id,
                    academic_period_id=active_period.academic_period_id,
                    record_status="taking",
                    final_grade=None,
                )
                session.add(rec)

        await session.flush()
        print("  [OK] Seeded 16 passed records (44 SKS lulus, IPK 3.82) and 6 active records (20 SKS taking)")

        print("\n[SEED 6/8] Checking and seeding Timetables & Class Schedules...")
        stmt_tt = select(Timetable).where(
            Timetable.user_id == mhs_user.user_id,
            Timetable.academic_period_id == active_period.academic_period_id,
        )
        timetable = (await session.execute(stmt_tt)).scalars().first()
        if not timetable:
            timetable = Timetable(
                user_id=mhs_user.user_id,
                student_curriculum_assignment_id=assignment.student_curriculum_assignment_id,
                academic_period_id=active_period.academic_period_id,
                timetable_name="Jadwal Utama Semester 3",
                is_active=False,
            )
            session.add(timetable)
            await session.flush()
            print("  [CREATED] Timetable for student")

        # Day: 1=Senin, 2=Selasa, 3=Rabu, 4=Kamis, 5=Jumat
        schedule_configs = [
            {
                "code": "TSD201",
                "section": "A",
                "day": 1,
                "start": datetime.time(8, 0),
                "end": datetime.time(10, 30),
                "room": "Lab Komputasi A (Gedung Nano Lt. 2)",
            },
            {
                "code": "TSD202",
                "section": "A",
                "day": 2,
                "start": datetime.time(8, 0),
                "end": datetime.time(10, 30),
                "room": "Ruang Kuliah 3.01 (Gedung Nano)",
            },
            {
                "code": "TSD203",
                "section": "A",
                "day": 2,
                "start": datetime.time(13, 0),
                "end": datetime.time(15, 30),
                "room": "Lab Komputasi B (Gedung Nano Lt. 2)",
            },
            {
                "code": "TSD204",
                "section": "A",
                "day": 3,
                "start": datetime.time(10, 0),
                "end": datetime.time(12, 30),
                "room": "Ruang Kuliah 3.02 (Gedung Nano)",
            },
            {
                "code": "TSD205",
                "section": "A",
                "day": 4,
                "start": datetime.time(8, 0),
                "end": datetime.time(10, 30),
                "room": "Ruang Kuliah 2.04 (Gedung Nano)",
            },
            {
                "code": "TSD206",
                "section": "A",
                "day": 4,
                "start": datetime.time(13, 0),
                "end": datetime.time(14, 40),
                "room": "Ruang Kuliah 3.01 (Gedung Nano)",
            },
            {
                "code": "TSD302",
                "section": "A",
                "day": 3,
                "start": datetime.time(13, 0),
                "end": datetime.time(15, 30),
                "room": "Ruang Kuliah 3.01 (Gedung Nano)",
            },
            {
                "code": "TSD301",
                "section": "B",
                "day": 5,
                "start": datetime.time(8, 0),
                "end": datetime.time(10, 30),
                "room": "Lab Komputasi A (Gedung Nano Lt. 2)",
            },
        ]

        for scfg in schedule_configs:
            c_obj = course_map[scfg["code"]]
            stmt_off = select(CourseOffering).where(
                CourseOffering.academic_period_id == active_period.academic_period_id,
                CourseOffering.course_id == c_obj.course_id,
            )
            offering = (await session.execute(stmt_off)).scalars().first()
            if not offering:
                offering = CourseOffering(
                    academic_period_id=active_period.academic_period_id,
                    course_id=c_obj.course_id,
                    offering_code=f"{scfg['code']}-2024-GANJIL",
                )
                session.add(offering)
                await session.flush()

            cc_obj = curriculum_course_map[scfg["code"]]
            stmt_coe = select(CourseOfferingEligibility).where(
                CourseOfferingEligibility.course_offering_id == offering.course_offering_id,
                CourseOfferingEligibility.curriculum_course_id == cc_obj.curriculum_course_id,
            )
            coe = (await session.execute(stmt_coe)).scalars().first()
            if not coe:
                coe = CourseOfferingEligibility(
                    course_offering_id=offering.course_offering_id,
                    curriculum_course_id=cc_obj.curriculum_course_id,
                )
                session.add(coe)
                await session.flush()

            stmt_comp = select(OfferingComponent).where(
                OfferingComponent.course_offering_id == offering.course_offering_id,
                OfferingComponent.component_code == "KULIAH",
            )
            comp = (await session.execute(stmt_comp)).scalars().first()
            if not comp:
                comp = OfferingComponent(
                    course_offering_id=offering.course_offering_id,
                    component_code="KULIAH",
                    component_type="lecture",
                )
                session.add(comp)
                await session.flush()

            prefix = section_prefix({tsd_prodi.program_code}, {cc_obj.course_scope})
            section_code = format_section_code(
                prefix, ord(scfg["section"]) - ord("A") + 1
            )
            stmt_sec = select(ClassSection).where(
                ClassSection.offering_component_id == comp.offering_component_id,
                ClassSection.section_code == section_code,
            )
            sec = (await session.execute(stmt_sec)).scalars().first()
            if not sec:
                sec = ClassSection(
                    offering_component_id=comp.offering_component_id,
                    section_code=section_code,
                    capacity=40,
                    enrollment_status="open",
                )
                session.add(sec)
                await session.flush()

            stmt_cs = select(ClassSchedule).where(
                ClassSchedule.class_section_id == sec.class_section_id,
                ClassSchedule.day_of_week == scfg["day"],
                ClassSchedule.start_time == scfg["start"],
            )
            cs = (await session.execute(stmt_cs)).scalars().first()
            if not cs:
                cs = ClassSchedule(
                    class_section_id=sec.class_section_id,
                    day_of_week=scfg["day"],
                    start_time=scfg["start"],
                    end_time=scfg["end"],
                    room_name=scfg["room"],
                )
                session.add(cs)
                await session.flush()

            if scfg["code"] in sem3_codes:
                stmt_ti = select(TimetableItem).where(
                    TimetableItem.timetable_id == timetable.timetable_id,
                    TimetableItem.class_section_id == sec.class_section_id,
                )
                ti = (await session.execute(stmt_ti)).scalars().first()
                if not ti:
                    ti = TimetableItem(
                        timetable_id=timetable.timetable_id,
                        class_section_id=sec.class_section_id,
                    )
                    session.add(ti)

        await session.flush()
        timetable.is_active = True
        await session.flush()
        print("  [OK] Activated student timetable with scheduled class items")
        print("  [OK] Seeded course offerings, sections, schedules, and timetable items")

        # Seluruh MK wajib pada periode aktif dari semua kurikulum aktif mendapat
        # satu penawaran per course_id; eligibility dibuat per curriculum_course
        # agar timetable lolos trg_timetable_items_validate. Penjadwalan seksi
        # diserahkan ke solver setelah data penawaran dan dosen lengkap.
        stmt_mandatory = (
            select(CurriculumCourse, Course.course_code, StudyProgram.program_code)
            .join(Course, Course.course_id == CurriculumCourse.course_id)
            .join(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
            .join(
                StudyProgram, StudyProgram.study_program_id == Curriculum.study_program_id
            )
            .where(
                Curriculum.is_active.is_(True),
                CurriculumCourse.is_active.is_(True),
                CurriculumCourse.course_type == "wajib",
                CurriculumCourse.term == active_period.term,
                Course.is_active.is_(True),
            )
            .order_by(
                Course.course_code,
                Curriculum.curriculum_year,
                Curriculum.curriculum_id,
                CurriculumCourse.curriculum_course_id,
            )
        )
        mandatory_rows = (await session.execute(stmt_mandatory)).all()
        programs_by_course: dict[object, set[str]] = {}
        scopes_by_course: dict[object, set[str]] = {}
        for cc_obj, _, program_code in mandatory_rows:
            programs_by_course.setdefault(cc_obj.course_id, set()).add(program_code)
            scopes_by_course.setdefault(cc_obj.course_id, set()).add(cc_obj.course_scope)

        offerings_by_course: dict[object, CourseOffering] = {}
        for cc_obj, code, _ in mandatory_rows:
            course_id = cc_obj.course_id
            offering = offerings_by_course.get(course_id)
            first_for_course = offering is None
            if first_for_course:
                offering_code = f"{code}-2024-GANJIL-KURIKULUM"
                stmt_off = select(CourseOffering).where(
                    CourseOffering.academic_period_id == active_period.academic_period_id,
                    CourseOffering.course_id == course_id,
                    CourseOffering.offering_code == offering_code,
                )
                offering = (await session.execute(stmt_off)).scalars().first()
                if not offering:
                    offering = CourseOffering(
                        academic_period_id=active_period.academic_period_id,
                        course_id=course_id,
                        offering_code=offering_code,
                    )
                    session.add(offering)
                    await session.flush()
                offerings_by_course[course_id] = offering

            stmt_coe = select(CourseOfferingEligibility).where(
                CourseOfferingEligibility.course_offering_id == offering.course_offering_id,
                CourseOfferingEligibility.curriculum_course_id == cc_obj.curriculum_course_id,
            )
            coe = (await session.execute(stmt_coe)).scalars().first()
            if not coe:
                session.add(
                    CourseOfferingEligibility(
                        course_offering_id=offering.course_offering_id,
                        curriculum_course_id=cc_obj.curriculum_course_id,
                    )
                )
                await session.flush()

            if not first_for_course:
                continue

            prefix = section_prefix(
                programs_by_course[course_id], scopes_by_course[course_id]
            )
            stmt_comp = select(OfferingComponent).where(
                OfferingComponent.course_offering_id == offering.course_offering_id,
                OfferingComponent.component_code == "KULIAH",
            )
            comp = (await session.execute(stmt_comp)).scalars().first()
            if not comp:
                comp = OfferingComponent(
                    course_offering_id=offering.course_offering_id,
                    component_code="KULIAH",
                    component_type="lecture",
                )
                session.add(comp)
                await session.flush()

            # Seksi kanonik memakai seksi yang sudah ada; kode baru mengikuti
            # aturan penamaan section per prodi atau UM untuk MK bersama.
            canonical_section_code = format_section_code(prefix, 1)
            stmt_sec = select(ClassSection).where(
                ClassSection.offering_component_id == comp.offering_component_id,
            )
            sec = (await session.execute(stmt_sec)).scalars().first()
            if not sec:
                sec = ClassSection(
                    offering_component_id=comp.offering_component_id,
                    section_code=canonical_section_code,
                    capacity=40,
                    enrollment_status="open",
                )
                session.add(sec)
                await session.flush()

        await session.flush()

        # Referensi dosen pengampu dari Ekstrak disimpan sebagai nama tim;
        # pemetaan ke akun dosen dilakukan manual oleh PJ.
        instructor_refs_created = 0
        if os.path.exists(EKSTRAK_DIR):
            stmt_cc = (
                select(CurriculumCourse, Course.course_code)
                .join(Course, Course.course_id == CurriculumCourse.course_id)
                .join(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
                .where(
                    Curriculum.is_active.is_(True),
                    CurriculumCourse.is_active.is_(True),
                )
            )
            cc_ids_by_code: dict[str, list[object]] = {}
            for cc_obj, course_code in (await session.execute(stmt_cc)).all():
                cc_ids_by_code.setdefault(course_code, []).append(cc_obj.curriculum_course_id)

            existing_ref_pairs: set[tuple[object, str]] = {
                (row.curriculum_course_id, row.instructor_name)
                for row in (
                    await session.execute(
                        select(
                            CourseInstructorReference.curriculum_course_id,
                            CourseInstructorReference.instructor_name,
                        ).where(
                            CourseInstructorReference.academic_period_id.is_(None)
                        )
                    )
                ).all()
            }

            for filepath in sorted(glob.glob(os.path.join(EKSTRAK_DIR, "FIX *.json"))):
                try:
                    with open(filepath, encoding="utf-8") as handle:
                        ekstrak = json.load(handle)
                except (OSError, json.JSONDecodeError):
                    continue
                for item in ekstrak.get("mata_kuliah", []):
                    cc_ids = cc_ids_by_code.get(str(item.get("kode_mk") or "").strip(), [])
                    if not cc_ids:
                        continue
                    for raw_name in item.get("dosen_pengampu") or []:
                        instructor_name = str(raw_name).strip()
                        if not instructor_name:
                            continue
                        for cc_id in cc_ids:
                            pair = (cc_id, instructor_name)
                            if pair in existing_ref_pairs:
                                continue
                            session.add(
                                CourseInstructorReference(
                                    curriculum_course_id=cc_id,
                                    instructor_name=instructor_name,
                                    instructor_role="teaching_team",
                                    user_id=None,
                                )
                            )
                            existing_ref_pairs.add(pair)
                            instructor_refs_created += 1
            await session.flush()
        print(
            f"  [OK] Seeded course instructor references "
            f"({instructor_refs_created} referensi)"
        )
        await session.flush()

        scheduler_admin = (
            await session.execute(select(User).where(User.role == "admin"))
        ).scalars().first()
        if scheduler_admin is None:
            print("  [WARN] Penjadwalan otomatis dilewati: akun admin tidak ditemukan")
        else:
            demo_program_ids = {
                prodi_map[code].study_program_id for code in PJ_PRODI_CODES
            }
            demo_lecturers = (
                (
                    await session.execute(
                        select(User)
                        .options(selectinload(User.lecturer_profile))
                        .where(
                            User.email.in_(
                                [item["email"] for item in lecturer_seed["lecturers"]]
                            ),
                            User.role == "lecturer",
                            User.is_active.is_(True),
                        )
                        .order_by(User.email)
                    )
                )
                .scalars()
                .all()
            )
            lecturers_by_program: dict[object, list[User]] = {
                program_id: [] for program_id in demo_program_ids
            }
            for lecturer in demo_lecturers:
                profile = lecturer.lecturer_profile
                if profile is not None and profile.study_program_id in lecturers_by_program:
                    lecturers_by_program[profile.study_program_id].append(lecturer)
            sections_created = await _seed_demo_sections(session, active_period)
            preferences_created = await _seed_demo_preferences(
                session, active_period, demo_lecturers
            )
            mappings_created = await _seed_period_instructor_mappings(
                session,
                active_period,
                demo_program_ids,
                lecturers_by_program,
            )
            assignments_created = await _seed_demo_assignments(
                session, active_period, scheduler_admin
            )
            print(
                f"  [OK] Input scheduling demo siap: {sections_created} kelas, "
                f"{preferences_created} preferensi, {mappings_created} mapping, "
                f"{assignments_created} assignment dibuat"
            )

        # Kelima mahasiswa demo harus punya rencana studi aktif yang bisa
        # dipakai. Rencana yang sudah berisi item tidak pernah diubah.
        demo_plan_emails = [
            "mahasiswa.tsd@ftmm.unair.ac.id",
            "mahasiswa.trkb@ftmm.unair.ac.id",
            "mahasiswa.rn@ftmm.unair.ac.id",
            "mahasiswa.ti@ftmm.unair.ac.id",
            "mahasiswa.te@ftmm.unair.ac.id",
        ]
        stmt_demo_plan_users = (
            select(User)
            .options(selectinload(User.student_profile))
            .where(User.email.in_(demo_plan_emails))
        )
        demo_plan_users = (await session.execute(stmt_demo_plan_users)).scalars().all()
        plans_created = 0
        items_created = 0
        want_odd = active_period.term != "genap"
        minimum_semester = 1 if want_odd else 2
        for user in demo_plan_users:
            if user.student_profile is None:
                continue
            try:
                assignment = await ensure_assignment(session, user)
            except NoCurriculumAssignment:
                print(
                    f"  [WARN] Skip demo plan {user.email}: "
                    "kurikulum prodi belum tersedia"
                )
                continue
            stmt_active_plan = (
                select(DegreePlan)
                .options(selectinload(DegreePlan.items))
                .where(
                    DegreePlan.user_id == user.user_id,
                    DegreePlan.status == "active",
                )
                .order_by(DegreePlan.created_at)
            )
            plan = (await session.execute(stmt_active_plan)).scalars().first()
            if plan is None:
                plan = DegreePlan(
                    user_id=user.user_id,
                    student_curriculum_assignment_id=(
                        assignment.student_curriculum_assignment_id
                    ),
                    plan_name="Draft 1",
                    status="active",
                )
                session.add(plan)
                await session.flush()
                plans_created += 1
            elif plan.items:
                continue

            stmt_plan_courses = (
                select(CurriculumCourse)
                .join(Course, Course.course_id == CurriculumCourse.course_id)
                .join(
                    Curriculum,
                    Curriculum.curriculum_id == CurriculumCourse.curriculum_id,
                )
                .where(
                    CurriculumCourse.curriculum_id == assignment.curriculum_id,
                    CurriculumCourse.course_type == "wajib",
                    CurriculumCourse.term == active_period.term,
                    CurriculumCourse.is_active.is_(True),
                    Curriculum.is_active.is_(True),
                    Course.is_active.is_(True),
                )
                .order_by(
                    CurriculumCourse.recommended_semester,
                    Course.course_code,
                )
                .limit(6)
            )
            plan_courses = (await session.execute(stmt_plan_courses)).scalars().all()
            for course in plan_courses:
                recommended = course.recommended_semester
                if recommended is None or recommended < minimum_semester:
                    semester = minimum_semester
                elif (recommended % 2 == 1) == want_odd:
                    semester = recommended
                else:
                    semester = recommended - 1
                    if semester < minimum_semester:
                        semester = recommended + 1
                session.add(
                    DegreePlanItem(
                        degree_plan_id=plan.degree_plan_id,
                        curriculum_course_id=course.curriculum_course_id,
                        planned_semester=semester,
                        planning_status="planned",
                    )
                )
                items_created += 1
            await session.flush()
        print(
            f"  [OK] Active degree plans ready for {len(demo_plan_users)} demo students "
            f"({plans_created} plans, {items_created} items created)"
        )
        # Jadwal demo mengikuti rencana studi aktif. Seksi dipilih hanya jika
        # penawarannya memenuhi syarat kurikulum pada item rencana tersebut.
        timetables_reconciled = 0
        for user in demo_plan_users:
            stmt_demo_plan = select(DegreePlan).where(
                DegreePlan.user_id == user.user_id,
                DegreePlan.status == "active",
            ).order_by(DegreePlan.created_at)
            plan = (await session.execute(stmt_demo_plan)).scalars().first()
            if plan is None:
                continue

            stmt_plan_course_ids = select(DegreePlanItem.curriculum_course_id).where(
                DegreePlanItem.degree_plan_id == plan.degree_plan_id
            )
            plan_course_ids = (
                (await session.execute(stmt_plan_course_ids)).scalars().all()
            )
            desired_sections: list[tuple[str, object]] = []
            seen_course_codes: set[str] = set()
            if plan_course_ids:
                stmt_eligible_sections = (
                    select(
                        CurriculumCourse,
                        Course.course_code,
                        ClassSection.class_section_id,
                    )
                    .join(Course, Course.course_id == CurriculumCourse.course_id)
                    .join(
                        CourseOfferingEligibility,
                        CourseOfferingEligibility.curriculum_course_id
                        == CurriculumCourse.curriculum_course_id,
                    )
                    .join(
                        CourseOffering,
                        CourseOffering.course_offering_id
                        == CourseOfferingEligibility.course_offering_id,
                    )
                    .join(
                        OfferingComponent,
                        OfferingComponent.course_offering_id
                        == CourseOffering.course_offering_id,
                    )
                    .join(
                        ClassSection,
                        ClassSection.offering_component_id
                        == OfferingComponent.offering_component_id,
                    )
                    .where(
                        CurriculumCourse.curriculum_course_id.in_(plan_course_ids),
                        CourseOffering.academic_period_id
                        == active_period.academic_period_id,
                    )
                    .order_by(
                        Course.course_code,
                        OfferingComponent.component_code,
                        ClassSection.section_code,
                        ClassSection.class_section_id,
                    )
                )
                for _cc, course_code, section_id in (
                    await session.execute(stmt_eligible_sections)
                ).all():
                    if course_code in seen_course_codes:
                        continue
                    seen_course_codes.add(course_code)
                    desired_sections.append((course_code, section_id))

            stmt_existing = (
                select(Timetable)
                .where(
                    Timetable.user_id == user.user_id,
                    Timetable.academic_period_id
                    == active_period.academic_period_id,
                )
                .order_by(Timetable.is_active.desc())
            )
            existing = (await session.execute(stmt_existing)).scalars().all()
            active_timetables = [t for t in existing if t.is_active]

            if not desired_sections:
                if active_timetables:
                    for timetable in active_timetables:
                        timetable.is_active = False
                    await session.flush()
                    timetables_reconciled += 1
                continue

            desired_ids = {section_id for _, section_id in desired_sections}
            timetable = (
                active_timetables[0]
                if active_timetables
                else (existing[0] if existing else None)
            )
            if timetable is not None and timetable.is_active:
                stmt_current = select(TimetableItem.class_section_id).where(
                    TimetableItem.timetable_id == timetable.timetable_id
                )
                current_ids = set((await session.execute(stmt_current)).scalars().all())
                if current_ids == desired_ids:
                    continue

            if timetable is None:
                timetable = Timetable(
                    user_id=user.user_id,
                    student_curriculum_assignment_id=(
                        plan.student_curriculum_assignment_id
                    ),
                    academic_period_id=active_period.academic_period_id,
                    timetable_name="Jadwal Utama",
                    is_active=False,
                )
                session.add(timetable)
            else:
                for active in active_timetables:
                    active.is_active = False
                if (
                    timetable.student_curriculum_assignment_id
                    != plan.student_curriculum_assignment_id
                ):
                    timetable.student_curriculum_assignment_id = (
                        plan.student_curriculum_assignment_id
                    )
            # Trigger menolak perubahan item pada timetable aktif.
            await session.flush()

            await session.execute(
                delete(TimetableItem).where(
                    TimetableItem.timetable_id == timetable.timetable_id
                )
            )
            await session.flush()
            for _course_code, section_id in desired_sections:
                session.add(
                    TimetableItem(
                        timetable_id=timetable.timetable_id,
                        class_section_id=section_id,
                    )
                )
            await session.flush()
            timetable.is_active = True
            await session.flush()
            timetables_reconciled += 1
        print(
            f"  [OK] Demo timetables reconciled from active degree plans "
            f"({timetables_reconciled} updated)"
        )

        print("\n[SEED 7/8] Checking and seeding Active Polling Period & Votes Peminatan...")
        stmt_poll = select(ElectivePollingPeriod).where(ElectivePollingPeriod.status == "open")
        polling_period = (await session.execute(stmt_poll)).scalars().first()
        if not polling_period:
            polling_period = ElectivePollingPeriod(
                title="Polling Peminatan MK Pilihan Semester Genap 2024/2025",
                academic_year="2024/2025",
                target_term="genap",
                target_semester=4,
                start_date=datetime.datetime.now(datetime.timezone.utc),
                end_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30),
                status="open",
                min_quota_threshold=15,
                max_votes_per_student=3,
                description="Periode polling resmi mahasiswa FTMM untuk proyeksi kelas pilihan semester genap.",
            )
            session.add(polling_period)
            await session.flush()
            print(f"  [CREATED] Active Polling Period: {polling_period.title}")
        else:
            print(f"  [EXISTS] Active Polling Period: {polling_period.title}")

        # 7a. Voter demo: sembilan mahasiswa per prodi, satu semester sebelum target
        # periode, sehingga memilih MK untuk semester berikutnya. Vote diambil dari
        # katalog, bukan daftar kode hardcoded, dan vote demo lama dihapus agar idempoten.
        target_term = (polling_period.target_term or "ganjil").strip().lower()
        target_parity = "odd" if target_term == "ganjil" else "even"
        target_semester = int(
            polling_period.target_semester or (1 if target_parity == "odd" else 2)
        )
        if (target_semester % 2 == 1) != (target_parity == "odd"):
            target_semester += 1
        voter_semester = target_semester - 1
        max_votes = max(1, int(polling_period.max_votes_per_student or 3))

        await refresh_from_db(session)
        catalog_courses = get_all_courses()
        elective_by_prodi: dict[str, list] = {}
        for code in PJ_PRODI_CODES:
            candidates = [
                course
                for course in catalog_courses
                if course.type == "Pilihan" and prodi_code(course.program) == code
            ]
            in_term = [course for course in candidates if course.parity == target_parity]
            elective_by_prodi[code] = in_term or candidates

        voter_users: list[tuple[User, str]] = []
        voter_count = VOTERS_PER_PRODI * len(PJ_PRODI_CODES)
        for i in range(1, voter_count + 1):
            voter_prodi_code = PJ_PRODI_CODES[(i - 1) % len(PJ_PRODI_CODES)]
            prodi = prodi_map[voter_prodi_code]
            v_email = f"student.voter{i:02d}@ftmm.unair.ac.id"
            stmt_vu = (
                select(User)
                .options(selectinload(User.student_profile))
                .where(User.email == v_email)
            )
            vu = (await session.execute(stmt_vu)).scalars().first()
            if vu is None:
                vu = User(
                    email=v_email,
                    full_name=f"Mahasiswa Pemilih {i:02d}",
                    role="student",
                    password_hash=get_password_hash("VoterPass2026!"),
                    is_active=True,
                )
                session.add(vu)
                await session.flush()
                session.add(
                    StudentProfile(
                        user_id=vu.user_id,
                        study_program_id=prodi.study_program_id,
                        student_number=f"VOTER{i:04d}",
                        admission_year=today.year - 2,
                        current_semester=voter_semester,
                    )
                )
            else:
                profile = vu.student_profile
                if profile is None:
                    session.add(
                        StudentProfile(
                            user_id=vu.user_id,
                            study_program_id=prodi.study_program_id,
                            student_number=f"VOTER{i:04d}",
                            admission_year=today.year - 2,
                            current_semester=voter_semester,
                        )
                    )
                else:
                    profile.study_program_id = prodi.study_program_id
                    if not profile.student_number:
                        profile.student_number = f"VOTER{i:04d}"
                    profile.current_semester = voter_semester
            voter_users.append((vu, voter_prodi_code))

        demo_user_ids = [user.user_id for user, _ in voter_users] + [mhs_user.user_id]
        await session.execute(
            delete(ElectiveCourseVote).where(
                ElectiveCourseVote.polling_period_id == polling_period.polling_period_id,
                ElectiveCourseVote.user_id.in_(demo_user_ids),
            )
        )

        for index, (voter, code) in enumerate(voter_users):
            candidates = elective_by_prodi[code]
            if not candidates:
                continue
            take = min(max_votes, len(candidates))
            offset = index % len(candidates)
            for priority, step in enumerate(range(take), start=1):
                course = candidates[(offset + step) % len(candidates)]
                session.add(
                    ElectiveCourseVote(
                        polling_period_id=polling_period.polling_period_id,
                        user_id=voter.user_id,
                        course_id=course.id,
                        course_code=course.code or course.id,
                        course_name=course.name,
                        credits=course.credits,
                        priority=priority,
                    )
                )

        mhs_candidates = elective_by_prodi["TSD"]
        for priority, course in enumerate(mhs_candidates[:max_votes], start=1):
            session.add(
                ElectiveCourseVote(
                    polling_period_id=polling_period.polling_period_id,
                    user_id=mhs_user.user_id,
                    course_id=course.id,
                    course_code=course.code or course.id,
                    course_name=course.name,
                    credits=course.credits,
                    priority=priority,
                )
            )

        await session.flush()
        print(f"  [OK] Seeded {len(voter_users)} prodi-scoped voters with up to {max_votes} elective votes each")

        if scheduler_admin is not None:
            await _run_demo_schedule_once(session, active_period, scheduler_admin)

        print("\n[SEED 8/8] Checking and seeding Persistent Notifications...")
        notifications_seed_data = [
            {
                "target_role": "student",
                "title": "Deteksi Bentrok Jadwal Kuliah",
                "message": "Terdapat bentrok jadwal antara II4042 (Machine Learning) dan II4045 (Data Visualization) pada Selasa 10:00.",
                "type": "warning",
                "is_read": False,
                "action_url": "dashboard",
            },
            {
                "target_role": "student",
                "title": "Batas Akhir Revisi KRS (PRS)",
                "message": "Periode perubahan rencana studi semester aktif ditutup pada 30 Agustus 2024 pukul 23:59 WIB.",
                "type": "deadline",
                "is_read": False,
                "action_url": "dashboard",
            },
            {
                "target_role": "student",
                "title": "Hasil Polling Peminatan MK Pilihan",
                "message": "Mata kuliah pilihan yang kamu vote (SIC304 - Natural Language Processing) telah memenuhi kuorum 42 mahasiswa dan siap membuka 2 kelas.",
                "type": "info",
                "is_read": False,
                "action_url": "course-finder",
            },
            {
                "target_role": "student",
                "title": "Compass AI: Rekomendasi Tersedia",
                "message": "Rencana studi optimal untuk Semester 5 dan 6 telah diperbarui berdasarkan target peminatanmu.",
                "type": "info",
                "is_read": True,
                "action_url": "chatbot",
            },
            {
                "target_role": "lecturer",
                "title": "Pengajuan Rencana Studi Mahasiswa",
                "message": "5 mahasiswa bimbingan akademik mengajukan draft KRS untuk diverifikasi dan disetujui dosen wali.",
                "type": "warning",
                "is_read": False,
                "action_url": "dashboard",
            },
            {
                "target_role": "lecturer",
                "title": "Batas Entri RPS & Presensi Perkuliahan",
                "message": "Entri presensi dan silabus/RPS semester aktif wajib dilengkapi sebelum perkuliahan Week 5.",
                "type": "deadline",
                "is_read": False,
                "action_url": "dashboard",
            },
            {
                "target_role": "lecturer",
                "title": "Update Kuorum MK Pilihan Anda",
                "message": "Mata kuliah TSD302 (Pembelajaran Mesin Lanjut) mencapai kuorum 42 peminat (siap buka 2 kelas paralel).",
                "type": "info",
                "is_read": False,
                "action_url": "course-finder",
            },
            {
                "target_role": "lecturer",
                "title": "Jadwal Mengajar Terkonfirmasi",
                "message": "Alokasi ruang kuliah TSD201 Kelas A telah ditetapkan di Ruang Kuliah Bersama 3.02.",
                "type": "info",
                "is_read": True,
                "action_url": "dashboard",
            },
            {
                "target_role": "admin",
                "title": "Monitoring Polling Pra-KRS",
                "message": "Periode pemilihan MK Pilihan Semester Genap 2024/2025 aktif: 45 mahasiswa telah submit preferensi peminatan.",
                "type": "info",
                "is_read": False,
                "action_url": "dashboard",
            },
            {
                "target_role": "admin",
                "title": "Mata Kuliah di Bawah Kuorum",
                "message": "Mata kuliah TI301 (8 peminat) belum memenuhi batas minimum kuorum 15 mahasiswa.",
                "type": "warning",
                "is_read": False,
                "action_url": "course-finder",
            },
            {
                "target_role": "admin",
                "title": "Audit Integritas Kurikulum",
                "message": "Sinkronisasi otomatis katalog 5 prodi dengan SSOT lokal berhasil (195 matkul terverifikasi).",
                "type": "info",
                "is_read": True,
                "action_url": "course-finder",
            },
            {
                "target_role": "admin",
                "title": "Verifikasi Akun Pengajar Baru",
                "message": "2 akun dosen baru terdaftar dari Cybercampus dan memerlukan verifikasi penugasan unit prodi.",
                "type": "deadline",
                "is_read": True,
                "action_url": "dashboard",
            },
        ]

        for ncfg in notifications_seed_data:
            stmt_n = select(UserNotification).where(
                UserNotification.target_role == ncfg["target_role"],
                UserNotification.title == ncfg["title"],
            )
            n_exists = (await session.execute(stmt_n)).scalars().first()
            if not n_exists:
                new_notif = UserNotification(
                    target_role=ncfg["target_role"],
                    title=ncfg["title"],
                    message=ncfg["message"],
                    type=ncfg["type"],
                    is_read=ncfg["is_read"],
                    action_url=ncfg["action_url"],
                )
                session.add(new_notif)

        await session.execute(
            update(ClassSchedule)
            .where(ClassSchedule.room_id.is_(None))
            .values(room_name=None)
        )

        await session.commit()
        print(f"  [OK] Seeded {len(notifications_seed_data)} persistent user notifications across all roles")
        print("\n[DONE] All seed data successfully populated and verified.")


if __name__ == "__main__":
    asyncio.run(seed_data())
