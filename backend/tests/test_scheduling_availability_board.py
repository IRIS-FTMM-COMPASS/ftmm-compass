"""Kontrak HTTP Papan Jadwal Bersama dan status dashboard."""

import uuid
from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from models import (
    ClassSchedule,
    ClassSection,
    Course,
    CourseOffering,
    CourseOfferingEligibility,
    Curriculum,
    CurriculumCourse,
    OfferingComponent,
    ScheduleProgramStatus,
    StudyProgram,
    User,
)
from scheduling_common import all_study_program_ids, current_period_id, status_label
from tests.conftest import SEEDED_STUDENT

V1 = "/api/v1"



def test_board_contains_classes_programs_unassigned_and_conflicts(
    client, db_session, admin_headers
):
    section_a, section_b = client.portal.call(_create_overlapping_sections, db_session)

    response = client.get(f"{V1}/scheduling/board", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    data = body["data"]
    assert data["academic_period_id"]
    assert data["period_label"]
    assert len(data["programs"]) == 5
    assert len(body["meta"]) >= 3

    classes = data["classes"]
    assert classes
    assert all(
        {
            "class_section_id",
            "course_code",
            "day_of_week",
            "start_hour",
            "end_hour",
            "state",
        }
        <= set(item)
        for item in classes
    )
    assert {item["study_program_code"] for item in classes} <= {
        item["study_program_code"] for item in data["programs"]
    } | {""}
    assert isinstance(data["unassigned"], list)

    ids = {section_a, section_b}
    room_conflicts = [
        item
        for item in data["conflicts"]
        if item["class_section_a_id"] in ids and item["kind"] == "room"
    ]
    assert room_conflicts
    assert room_conflicts[0]["day_of_week"] == 1
    assert room_conflicts[0]["start_hour"] == 9
    assert room_conflicts[0]["end_hour"] == 10

    conflicts = client.get(f"{V1}/scheduling/conflicts", headers=admin_headers)
    assert conflicts.status_code == 200, conflicts.text
    assert conflicts.json()["data"] == data["conflicts"]

    statuses = client.portal.call(_status_rows, db_session)
    assert len(statuses) >= 5
    assert all(state == "draft" for state in statuses.values())


def test_board_separates_two_sks_block_and_face_to_face_minutes(
    client, db_session, admin_headers
):
    course_id = client.portal.call(_course_uuid, db_session, "TSD206")

    response = client.get(f"{V1}/scheduling/board", headers=admin_headers)
    assert response.status_code == 200, response.text
    items = [
        item
        for item in response.json()["data"]["classes"]
        if item["course_code"] == "TSD206" and item["credits"] == 2
    ]
    assert items
    item = items[0]
    assert (item["end_hour"] - item["start_hour"]) * 60 == 120
    assert item["face_to_face_minutes"] == 100
    assert item["course_id"] == str(course_id)


def test_board_rejects_unknown_period(client, admin_headers):
    response = client.get(
        f"{V1}/scheduling/board",
        params={"period_id": str(uuid.uuid4())},
        headers=admin_headers,
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "period_not_found"

    conflicts = client.get(
        f"{V1}/scheduling/conflicts",
        params={"period_id": "bukan-uuid"},
        headers=admin_headers,
    )
    assert conflicts.status_code == 404
    assert conflicts.json()["error"]["code"] == "period_not_found"


def test_dashboard_exposes_schedule_status(
    client, student_headers, lecturer_headers, db_session
):
    for headers in (student_headers, lecturer_headers):
        response = client.get(f"{V1}/dashboard/me", headers=headers)
        assert response.status_code == 200, response.text
        status = response.json().get("schedule_status")
        assert isinstance(status, str)
        assert status == status_label("draft")

    client.portal.call(_finalize_student_program, db_session)
    partial = client.get(f"{V1}/dashboard/me", headers=student_headers)
    assert partial.status_code == 200
    assert partial.json()["schedule_status"] == status_label("draft")

    client.portal.call(_finalize_all_programs, db_session)
    finalized = client.get(f"{V1}/dashboard/me", headers=student_headers)
    assert finalized.status_code == 200
    assert finalized.json()["schedule_status"] == status_label("final")



async def _course_uuid(db_session, course_code):
    return (
        await db_session.execute(
            select(Course.course_id).where(Course.course_code == course_code)
        )
    ).scalar_one()



async def _create_overlapping_sections(db_session):
    period_id = await current_period_id(db_session)
    source = (
        await db_session.execute(
            select(
                ClassSection.offering_component_id, CourseOffering.course_offering_id
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
            .where(CourseOffering.academic_period_id == period_id)
            .limit(1)
        )
    ).first()
    assert source is not None, "seed harus memuat kelas pada periode aktif"

    suffix = uuid.uuid4().hex[:6]
    sections = [
        ClassSection(
            offering_component_id=source.offering_component_id,
            section_code=f"KONFLIK-{label}-{suffix}",
            capacity=20,
        )
        for label in ("A", "B")
    ]
    db_session.add_all(sections)
    await db_session.flush()
    room_name = f"Ruang Uji Konflik {suffix}"
    db_session.add_all(
        [
            ClassSchedule(
                class_section_id=sections[0].class_section_id,
                day_of_week=1,
                start_time=time(8, 0),
                end_time=time(10, 0),
                room_name=room_name,
            ),
            ClassSchedule(
                class_section_id=sections[1].class_section_id,
                day_of_week=1,
                start_time=time(9, 0),
                end_time=time(11, 0),
                room_name=room_name,
            ),
        ]
    )
    await db_session.commit()
    return str(sections[0].class_section_id), str(sections[1].class_section_id)


async def _status_rows(db_session):
    period_id = await current_period_id(db_session)
    rows = (
        await db_session.execute(
            select(ScheduleProgramStatus.study_program_id, ScheduleProgramStatus.state)
            .where(ScheduleProgramStatus.academic_period_id == period_id)
        )
    ).all()
    return {str(row.study_program_id): row.state for row in rows}


async def _finalize_student_program(db_session):
    period_id = await current_period_id(db_session)
    user = (
        await db_session.execute(
            select(User)
            .options(selectinload(User.student_profile))
            .where(User.email == SEEDED_STUDENT[0])
        )
    ).scalars().one()
    program_id = user.student_profile.study_program_id
    row = (
        await db_session.execute(
            select(ScheduleProgramStatus).where(
                ScheduleProgramStatus.academic_period_id == period_id,
                ScheduleProgramStatus.study_program_id == program_id,
            )
        )
    ).scalars().first()
    if row is None:
        db_session.add(
            ScheduleProgramStatus(
                academic_period_id=period_id,
                study_program_id=program_id,
                state="final",
            )
        )
    else:
        row.state = "final"
    await db_session.commit()


async def _finalize_all_programs(db_session):
    period_id = await current_period_id(db_session)
    for program_id in await all_study_program_ids(db_session):
        row = (
            await db_session.execute(
                select(ScheduleProgramStatus).where(
                    ScheduleProgramStatus.academic_period_id == period_id,
                    ScheduleProgramStatus.study_program_id == program_id,
                )
            )
        ).scalars().first()
        if row is None:
            db_session.add(
                ScheduleProgramStatus(
                    academic_period_id=period_id,
                    study_program_id=program_id,
                    state="final",
                )
            )
        else:
            row.state = "final"
    await db_session.commit()


def _ordinary_lecturer_headers(client) -> dict[str, str]:
    response = client.post(
        f"{V1}/auth/login",
        json={
            "identifier": "aisyahdm@ftmm.unair.ac.id",
            "password": "DosenFTMM2026!",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_ordinary_lecturer_reads_shared_board_but_cannot_mutate(client):
    headers = _ordinary_lecturer_headers(client)
    board = client.get(f"{V1}/scheduling/board", headers=headers)
    assert board.status_code == 200, board.text
    body = board.json()
    assert len(body["data"]["programs"]) == 5
    assert body["meta"]["read_only"] is True
    assert body["meta"]["can_edit"] is False
    assert body["data"]["classes"]
    for item in body["data"]["classes"]:
        assert item["can_edit"] is False
        assert item["read_only"] is True
        assert item["programs"]
        assert all(
            program["study_program_id"]
            and program["study_program_code"]
            and program["study_program_name"]
            for program in item["programs"]
        )

    assigned = next(
        item for item in body["data"]["classes"] if item["assigned_lecturer_id"]
    )
    assert assigned["assigned_lecturer_name"] in assigned["lecturers"]
    section_id = body["data"]["classes"][0]["class_section_id"]
    period_id = body["data"]["academic_period_id"]
    mutations = (
        client.post(
            f"{V1}/scheduling/generate",
            json={"mode": "fill_empty", "academic_period_id": period_id},
            headers=headers,
        ),
        client.patch(
            f"{V1}/scheduling/classes/{section_id}",
            json={
                "day_of_week": 1,
                "start_hour": 8,
                "reason": "Uji peran dosen biasa",
            },
            headers=headers,
        ),
        client.put(
            f"{V1}/scheduling/assignments",
            json={
                "decisions": [
                    {
                        "class_section_id": section_id,
                        "user_id": assigned["assigned_lecturer_id"],
                        "source": "manual",
                        "is_pinned": False,
                    }
                ]
            },
            headers=headers,
        ),
        client.post(
            f"{V1}/scheduling/periods/{period_id}/finalize", headers=headers
        ),
    )
    assert all(response.status_code == 403 for response in mutations)


def test_cross_program_board_reports_program_identities_and_mixed_state(
    client, db_session, admin_headers
):
    section_id, _ = client.portal.call(_create_overlapping_sections, db_session)

    async def add_program_and_finalize():
        section = await db_session.get(ClassSection, uuid.UUID(section_id))
        component = await db_session.get(
            OfferingComponent, section.offering_component_id
        )
        offering = await db_session.get(CourseOffering, component.course_offering_id)
        period_id = offering.academic_period_id
        program = (
            await db_session.execute(
                select(StudyProgram).where(StudyProgram.program_code == "TRKB")
            )
        ).scalars().one()
        curriculum = Curriculum(
            study_program_id=program.study_program_id,
            curriculum_name=f"Kurikulum Papan Lintas Prodi {uuid.uuid4().hex[:8]}",
            curriculum_year=2099,
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.flush()
        curriculum_course = CurriculumCourse(
            curriculum_id=curriculum.curriculum_id,
            course_id=offering.course_id,
            credits_total=3,
            recommended_semester=1,
            term="ganjil",
            course_type="wajib",
            is_active=True,
        )
        db_session.add(curriculum_course)
        await db_session.flush()
        db_session.add(
            CourseOfferingEligibility(
                course_offering_id=offering.course_offering_id,
                curriculum_course_id=curriculum_course.curriculum_course_id,
            )
        )
        for code, state in (("TSD", "draft"), ("TRKB", "final")):
            status_row = (
                await db_session.execute(
                    select(ScheduleProgramStatus)
                    .join(
                        StudyProgram,
                        StudyProgram.study_program_id
                        == ScheduleProgramStatus.study_program_id,
                    )
                    .where(
                        ScheduleProgramStatus.academic_period_id == period_id,
                        StudyProgram.program_code == code,
                    )
                )
            ).scalars().first()
            if status_row is None:
                program_id = (
                    await db_session.execute(
                        select(StudyProgram.study_program_id).where(
                            StudyProgram.program_code == code
                        )
                    )
                ).scalar_one()
                status_row = ScheduleProgramStatus(
                    academic_period_id=period_id,
                    study_program_id=program_id,
                )
                db_session.add(status_row)
            status_row.state = state
        await db_session.commit()

    client.portal.call(add_program_and_finalize)
    response = client.get(f"{V1}/scheduling/board", headers=admin_headers)
    assert response.status_code == 200, response.text
    item = next(
        row
        for row in response.json()["data"]["classes"]
        if row["class_section_id"] == section_id
    )
    assert item["state"] == "mixed"
    programs = {row["study_program_code"]: row for row in item["programs"]}
    assert set(programs) == {"TSD", "TRKB"}
    assert programs["TSD"]["state"] == "draft"
    assert programs["TRKB"]["state"] == "final"
    assert programs["TRKB"]["study_program_name"] == "Teknik Robotika dan Kecerdasan Buatan"


def test_conflict_payload_names_room_classes_day_and_time(
    client, db_session, admin_headers
):
    section_a, section_b = client.portal.call(
        _create_overlapping_sections, db_session
    )
    response = client.get(f"{V1}/scheduling/board", headers=admin_headers)
    assert response.status_code == 200, response.text
    conflict = next(
        item
        for item in response.json()["data"]["conflicts"]
        if item["kind"] == "room"
        and {item["class_section_a_id"], item["class_section_b_id"]}
        == {section_a, section_b}
    )
    assert conflict["object_id"]
    assert conflict["object_name"]
    assert conflict["day_name"] == "Senin"
    assert (conflict["start_hour"], conflict["end_hour"]) == (9, 10)
    assert conflict["class_section_a_label"]
    assert conflict["class_section_b_label"]
    assert conflict["object_name"] in conflict["label"]
    assert conflict["class_section_a_label"] in conflict["label"]
    assert conflict["class_section_b_label"] in conflict["label"]
    assert "Senin" in conflict["label"]
    assert "09.00" in conflict["label"]
