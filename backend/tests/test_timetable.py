"""Regresi kontrak REST untuk timetable aktif mahasiswa (/me/timetable)."""

import uuid

import pytest
from sqlalchemy import func, select

from models import (
    AcademicPeriod,
    ClassSection,
    Course,
    CourseOffering,
    CourseOfferingEligibility,
    Curriculum,
    CurriculumCourse,
    OfferingComponent,
    StudentCurriculumAssignment,
    Timetable,
    TimetableItem,
    User,
)
from rate_limit import limiter
from tests.conftest import SEEDED_ADMIN, SEEDED_PJ, SEEDED_STUDENT

V1 = "/api/v1"
TIMETABLE_PATH = f"{V1}/me/timetable"
DASHBOARD_PATH = f"{V1}/dashboard/me"
TSD_DEMO_STUDENT = ("mahasiswa.tsd@ftmm.unair.ac.id", "Mahasiswa2026!")
SEEDED_TIMETABLE_CODES = {f"TSD20{number}" for number in range(1, 7)}


def _login_headers(client, credentials: tuple[str, str]) -> dict[str, str]:
    limiter.reset()
    response = client.post(
        f"{V1}/auth/login",
        json={"identifier": credentials[0], "password": credentials[1]},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _get_timetable(client, headers: dict[str, str]) -> dict:
    response = client.get(TIMETABLE_PATH, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _put_timetable(client, headers: dict[str, str], selections: list[dict]) -> dict:
    return client.put(TIMETABLE_PATH, json={"selections": selections}, headers=headers)


def _dashboard_schedule(client, headers: dict[str, str]) -> list[dict]:
    response = client.get(DASHBOARD_PATH, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["schedule"]


def _discover_sections(
    client,
    db_session,
    *,
    limit: int = 1,
    exclude_codes: set[str] | None = None,
) -> list[dict[str, str]]:
    """Cari section yang memenuhi syarat untuk kurikulum aktif mahasiswa TSD."""

    async def read() -> list[dict[str, str]]:
        stmt = (
            select(
                Course.course_code,
                ClassSection.class_section_id,
                ClassSection.section_code,
            )
            .select_from(StudentCurriculumAssignment)
            .join(User, StudentCurriculumAssignment.user_id == User.user_id)
            .join(
                Curriculum,
                StudentCurriculumAssignment.curriculum_id == Curriculum.curriculum_id,
            )
            .join(
                CurriculumCourse,
                Curriculum.curriculum_id == CurriculumCourse.curriculum_id,
            )
            .join(
                CourseOfferingEligibility,
                CurriculumCourse.curriculum_course_id
                == CourseOfferingEligibility.curriculum_course_id,
            )
            .join(
                CourseOffering,
                CourseOfferingEligibility.course_offering_id
                == CourseOffering.course_offering_id,
            )
            .join(
                OfferingComponent,
                CourseOffering.course_offering_id == OfferingComponent.course_offering_id,
            )
            .join(
                ClassSection,
                OfferingComponent.offering_component_id
                == ClassSection.offering_component_id,
            )
            .join(Course, CourseOffering.course_id == Course.course_id)
            .join(
                AcademicPeriod,
                CourseOffering.academic_period_id == AcademicPeriod.academic_period_id,
            )
            .where(User.email == TSD_DEMO_STUDENT[0])
            .where(StudentCurriculumAssignment.is_current.is_(True))
            .where(AcademicPeriod.is_active.is_(True))
            .distinct()
            .order_by(Course.course_code, ClassSection.section_code)
        )
        if exclude_codes:
            stmt = stmt.where(Course.course_code.not_in(list(exclude_codes)))
        rows = (await db_session.execute(stmt.limit(limit))).all()
        return [
            {
                "course_code": course_code,
                "section_id": str(section_id),
                "section_code": section_code,
            }
            for course_code, section_id, section_code in rows
        ]

    found = client.portal.call(read)
    if len(found) < limit:
        pytest.fail(f"Tidak ditemukan {limit} section kelas untuk katalog mahasiswa uji.")
    return found


def _selection_input(item: dict[str, str]) -> dict[str, str]:
    return {"course_code": item["course_code"], "section_id": item["section_id"]}


def _selection_keys(selections: list[dict]) -> set[tuple[str, str, str]]:
    return {
        (item["course_code"], item["section_id"], item["section_code"])
        for item in selections
    }


def _assert_error(response, status_code: int, code: str) -> None:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["error"]["code"] == code
    assert body["detail"]


def _timetable_counts(client, db_session, email: str) -> tuple[int, int]:
    async def read() -> tuple[int, int]:
        user_id = (
            await db_session.execute(select(User.user_id).where(User.email == email))
        ).scalar_one()
        timetable_ids = (
            (
                await db_session.execute(
                    select(Timetable.timetable_id).where(
                        Timetable.user_id == user_id,
                        Timetable.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not timetable_ids:
            return 0, 0
        item_count = (
            await db_session.execute(
                select(func.count())
                .select_from(TimetableItem)
                .where(TimetableItem.timetable_id.in_(timetable_ids))
            )
        ).scalar_one()
        return len(timetable_ids), item_count

    return client.portal.call(read)


def test_demo_student_starts_with_seeded_timetable(client, db_session):
    headers = _login_headers(client, TSD_DEMO_STUDENT)

    body = _get_timetable(client, headers)

    assert {item["course_code"] for item in body["selections"]} == {
        "SIA104",
        "SIP107",
    }
    assert "academic_period_id" in body
    assert "updated_at" in body


def test_put_and_get_selection_round_trip(client, db_session):
    headers = _login_headers(client, TSD_DEMO_STUDENT)
    item = _discover_sections(client, db_session)[0]

    response = _put_timetable(client, headers, [_selection_input(item)])

    assert response.status_code == 200, response.text
    expected = {
        (item["course_code"], item["section_id"], item["section_code"])
    }
    assert _selection_keys(response.json()["selections"]) == expected
    assert _selection_keys(_get_timetable(client, headers)["selections"]) == expected


def test_dashboard_schedule_contains_saved_course(client, db_session):
    headers = _login_headers(client, TSD_DEMO_STUDENT)
    item = _discover_sections(client, db_session)[0]

    response = _put_timetable(client, headers, [_selection_input(item)])
    assert response.status_code == 200, response.text

    schedule = _dashboard_schedule(client, headers)
    assert schedule
    assert any(entry["course_code"] == item["course_code"] for entry in schedule)


def test_repeated_put_reuses_one_timetable_and_replaces_items(client, db_session):
    headers = _login_headers(client, TSD_DEMO_STUDENT)
    items = _discover_sections(client, db_session, limit=2)
    selections = [_selection_input(item) for item in items]

    for _ in range(2):
        response = _put_timetable(client, headers, selections)
        assert response.status_code == 200, response.text

    active_rows, item_count = _timetable_counts(client, db_session, TSD_DEMO_STUDENT[0])
    assert active_rows == 1
    assert item_count == len(selections)
    assert _selection_keys(_get_timetable(client, headers)["selections"]) == {
        (item["course_code"], item["section_id"], item["section_code"])
        for item in items
    }


def test_empty_put_clears_items_and_dashboard_schedule(client, db_session):
    headers = _login_headers(client, TSD_DEMO_STUDENT)
    item = _discover_sections(client, db_session)[0]
    response = _put_timetable(client, headers, [_selection_input(item)])
    assert response.status_code == 200, response.text
    assert _dashboard_schedule(client, headers)

    response = _put_timetable(client, headers, [])

    assert response.status_code == 200, response.text
    assert response.json()["selections"] == []
    assert _get_timetable(client, headers)["selections"] == []
    active_rows, item_count = _timetable_counts(client, db_session, TSD_DEMO_STUDENT[0])
    assert active_rows == 0
    assert item_count == 0
    assert _dashboard_schedule(client, headers) == []


@pytest.mark.parametrize(
    "credentials", [SEEDED_ADMIN, SEEDED_PJ], ids=["admin", "pj"]
)
def test_non_student_roles_are_forbidden(client, db_session, credentials):
    headers = _login_headers(client, credentials)

    _assert_error(client.get(TIMETABLE_PATH, headers=headers), 403, "forbidden")
    _assert_error(
        _put_timetable(client, headers, []),
        403,
        "forbidden",
    )


def test_unknown_section_is_rejected(client, db_session):
    headers = _login_headers(client, TSD_DEMO_STUDENT)
    item = _discover_sections(client, db_session)[0]

    response = _put_timetable(
        client,
        headers,
        [{"course_code": item["course_code"], "section_id": str(uuid.uuid4())}],
    )

    _assert_error(response, 422, "section_not_found")


def test_duplicate_course_is_rejected(client, db_session):
    headers = _login_headers(client, TSD_DEMO_STUDENT)
    item = _discover_sections(client, db_session)[0]
    selection = _selection_input(item)

    response = _put_timetable(client, headers, [selection, selection])

    _assert_error(response, 422, "duplicate_course")


def test_student_cannot_see_another_students_selections(client, db_session):
    headers = _login_headers(client, TSD_DEMO_STUDENT)
    other_headers = _login_headers(client, SEEDED_STUDENT)
    item = _discover_sections(
        client, db_session, exclude_codes=SEEDED_TIMETABLE_CODES
    )[0]

    response = _put_timetable(client, headers, [_selection_input(item)])
    assert response.status_code == 200, response.text

    assert _selection_keys(_get_timetable(client, headers)["selections"]) == {
        (item["course_code"], item["section_id"], item["section_code"])
    }
    other_selections = _get_timetable(client, other_headers)["selections"]
    assert item["section_id"] not in {
        selection["section_id"] for selection in other_selections
    }
    assert all(
        entry["course_code"] != item["course_code"]
        for entry in _dashboard_schedule(client, other_headers)
    )
