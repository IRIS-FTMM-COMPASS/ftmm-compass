import datetime

from sqlalchemy import select

import app as app_module
from database import get_db
from models import (
    AcademicPeriod,
    ClassSchedule,
    ClassSection,
    Course,
    CourseOffering,
    OfferingComponent,
)

PATH = "/api/v1/class-sections/validations"


async def _session(client):
    override = app_module.app.dependency_overrides[get_db]
    return await anext(override())


def _parallel_sections(client):
    async def insert():
        session = await _session(client)
        period = (
            await session.execute(
                select(AcademicPeriod).where(AcademicPeriod.is_active.is_(True))
            )
        ).scalars().first()
        assert period is not None

        plans = (
            ("TSD201", "B", 1, "09:00", "10:00"),
            ("TSD201", "C", 1, "12:00", "13:30"),
            ("TSD301", "A", 1, "09:00", "10:00"),
            ("TSD301", "C", 5, "13:00", "14:30"),
            ("TSD301", "D", 1, "08:30", "09:30"),
        )
        by_code = {}
        for code, section_code, day, start, end in plans:
            if code not in by_code:
                course = (
                    await session.execute(
                        select(Course).where(Course.course_code == code)
                    )
                ).scalars().first()
                offering = (
                    await session.execute(
                        select(CourseOffering).where(
                            CourseOffering.course_id == course.course_id,
                            CourseOffering.academic_period_id
                            == period.academic_period_id,
                        )
                    )
                ).scalars().first()
                component = (
                    await session.execute(
                        select(OfferingComponent).where(
                            OfferingComponent.course_offering_id
                            == offering.course_offering_id,
                            OfferingComponent.component_code == "KULIAH",
                        )
                    )
                ).scalars().first()
                by_code[code] = component.offering_component_id

            section = ClassSection(
                offering_component_id=by_code[code],
                section_code=section_code,
                capacity=40,
                enrollment_status="open",
            )
            session.add(section)
            await session.flush()
            hour, minute = map(int, start.split(":"))
            end_hour, end_minute = map(int, end.split(":"))
            session.add(
                ClassSchedule(
                    class_section_id=section.class_section_id,
                    day_of_week=day,
                    start_time=datetime.time(hour, minute),
                    end_time=datetime.time(end_hour, end_minute),
                    room_name="Ruang Uji",
                )
            )
        await session.flush()

        ids = {}
        for code in ("TSD201", "TSD301"):
            rows = (
                await session.execute(
                    select(ClassSection.section_code, ClassSection.class_section_id)
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
                    .join(Course, Course.course_id == CourseOffering.course_id)
                    .where(
                        Course.course_code == code,
                        CourseOffering.academic_period_id
                        == period.academic_period_id,
                    )
                )
            ).all()
            ids[code] = {str(code_): str(uuid) for code_, uuid in rows}
        return ids

    return client.portal.call(insert)


def test_validation_detects_overlap_and_filters_alternatives(client, student_headers):
    ids = _parallel_sections(client)
    response = client.post(
        PATH,
        json={
            "selections": [
                {"course_code": "TSD201", "section_id": ids["TSD201"]["A"]},
                {"course_code": "TSD301", "section_id": ids["TSD301"]["A"]},
            ]
        },
        headers=student_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["meta"]["total_conflicts"] == 1
    conflict = body["data"][0]
    assert {conflict["course_a_code"], conflict["course_b_code"]} == {
        "TSD201",
        "TSD301",
    }
    assert conflict["day"] == "Senin"
    assert conflict["start_time"] == "09:00"
    assert conflict["end_time"] == "10:00"
    assert conflict["course_a_name"] and conflict["course_b_name"]

    alternatives = {
        (item["course_code"], item["section"]["section_code"])
        for item in body["alternatives"]
    }
    assert ("TSD201", "C") in alternatives
    assert ("TSD301", "C") in alternatives
    assert ("TSD301", "A") not in alternatives
    assert ("TSD301", "D") not in alternatives
    assert body["meta"]["total_alternatives"] == len(body["alternatives"])
    for item in body["alternatives"]:
        assert item["section"]["schedules"]

    resolved = client.post(
        PATH,
        json={
            "selections": [
                {"course_code": "TSD201", "section_id": ids["TSD201"]["C"]},
                {"course_code": "TSD301", "section_id": ids["TSD301"]["C"]},
            ]
        },
        headers=student_headers,
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["data"] == []


def test_validation_without_overlap_has_empty_conflicts(client, student_headers):
    ids = _parallel_sections(client)
    response = client.post(
        PATH,
        json={
            "selections": [
                {"course_code": "TSD201", "section_id": ids["TSD201"]["A"]},
                {"course_code": "TSD301", "section_id": ids["TSD301"]["B"]},
            ]
        },
        headers=student_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == []
    assert response.json()["alternatives"] == []


def test_unknown_course_uses_course_not_found_envelope(client, student_headers):
    response = client.post(
        PATH,
        json={
            "selections": [
                {
                    "course_code": "MK-TIDAK-ADA",
                    "section_id": "00000000-0000-0000-0000-000000000000",
                }
            ]
        },
        headers=student_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "course_not_found"


def test_invalid_selection_uses_validation_envelope(client, student_headers):
    for payload in (
        {"selections": []},
        {"selections": [{"course_code": "TSD201", "section_id": "bukan-uuid"}]},
    ):
        response = client.post(PATH, json=payload, headers=student_headers)
        assert response.status_code == 422, response.text
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        assert error["details"]


def test_legacy_validation_alias_matches_canonical(client, student_headers):
    ids = _parallel_sections(client)
    payload = {
        "selections": [
            {"course_code": "TSD201", "section_id": ids["TSD201"]["A"]},
            {"course_code": "TSD301", "section_id": ids["TSD301"]["A"]},
        ]
    }
    canonical = client.post(PATH, json=payload, headers=student_headers)
    legacy = client.post(
        "/api/class-sections/validations", json=payload, headers=student_headers
    )

    assert legacy.status_code == 200
    assert legacy.json() == canonical.json()


def _insert_plan_sections(client, plans):
    async def insert():
        session = await _session(client)
        period = (
            await session.execute(
                select(AcademicPeriod).where(AcademicPeriod.is_active.is_(True))
            )
        ).scalars().first()
        assert period is not None

        components = {}
        for code, section_code, day, start, end in plans:
            if code not in components:
                course = (
                    await session.execute(
                        select(Course).where(Course.course_code == code)
                    )
                ).scalars().first()
                offering = (
                    await session.execute(
                        select(CourseOffering).where(
                            CourseOffering.course_id == course.course_id,
                            CourseOffering.academic_period_id
                            == period.academic_period_id,
                        )
                    )
                ).scalars().first()
                component = (
                    await session.execute(
                        select(OfferingComponent).where(
                            OfferingComponent.course_offering_id
                            == offering.course_offering_id,
                            OfferingComponent.component_code == "KULIAH",
                        )
                    )
                ).scalars().first()
                components[code] = component.offering_component_id

            section = ClassSection(
                offering_component_id=components[code],
                section_code=section_code,
                capacity=40,
                enrollment_status="open",
            )
            session.add(section)
            await session.flush()
            start_hour, start_minute = map(int, start.split(":"))
            end_hour, end_minute = map(int, end.split(":"))
            session.add(
                ClassSchedule(
                    class_section_id=section.class_section_id,
                    day_of_week=day,
                    start_time=datetime.time(start_hour, start_minute),
                    end_time=datetime.time(end_hour, end_minute),
                    room_name="Ruang Uji",
                )
            )
        await session.flush()

        ids = {}
        for code in {plan[0] for plan in plans}:
            rows = (
                await session.execute(
                    select(ClassSection.section_code, ClassSection.class_section_id)
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
                    .join(Course, Course.course_id == CourseOffering.course_id)
                    .where(
                        Course.course_code == code,
                        CourseOffering.academic_period_id
                        == period.academic_period_id,
                    )
                )
            ).all()
            ids[code] = {str(section_code): str(uuid) for section_code, uuid in rows}
        return ids

    return client.portal.call(insert)


def test_validation_without_active_period_uses_validation_envelope(
    client, student_headers
):
    async def deactivate():
        session = await _session(client)
        periods = (await session.execute(select(AcademicPeriod))).scalars().all()
        assert periods
        for period in periods:
            period.is_active = False
        await session.flush()

    client.portal.call(deactivate)

    response = client.post(
        PATH,
        json={
            "selections": [
                {
                    "course_code": "TSD201",
                    "section_id": "00000000-0000-0000-0000-000000000001",
                }
            ]
        },
        headers=student_headers,
    )

    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert "periode akademik aktif" in error["message"].lower()


def test_batch_alternatives_cannot_create_a_new_clash(client, student_headers):
    plans = (
        ("TSD201", "Q1", 1, "09:00", "10:00"),
        ("TSD201", "Q2", 1, "11:00", "12:00"),
        ("TSD201", "Q3", 1, "13:00", "14:00"),
        ("TSD301", "R1", 1, "09:30", "10:30"),
        ("TSD301", "R2", 1, "11:30", "12:30"),
        ("TSD301", "R3", 1, "14:00", "15:00"),
    )
    ids = _insert_plan_sections(client, plans)
    response = client.post(
        PATH,
        json={
            "selections": [
                {"course_code": "TSD201", "section_id": ids["TSD201"]["Q1"]},
                {"course_code": "TSD301", "section_id": ids["TSD301"]["R1"]},
            ]
        },
        headers=student_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["meta"]["total_conflicts"] == 1
    by_code: dict[str, list[str]] = {}
    for alternative in body["alternatives"]:
        by_code.setdefault(alternative["course_code"], []).append(
            alternative["section"]["section_id"]
        )
    assert all(by_code.get(code) for code in ("TSD201", "TSD301"))

    codes = sorted(by_code)
    for first_id in by_code[codes[0]]:
        for second_id in by_code[codes[1]]:
            resolved = client.post(
                PATH,
                json={
                    "selections": [
                        {"course_code": codes[0], "section_id": first_id},
                        {"course_code": codes[1], "section_id": second_id},
                    ]
                },
                headers=student_headers,
            )
            assert resolved.status_code == 200, resolved.text
            assert resolved.json()["data"] == []
