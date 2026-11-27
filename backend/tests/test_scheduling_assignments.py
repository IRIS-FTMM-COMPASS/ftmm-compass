"""HTTP contract for deterministic assignment preview, override, pin, and delete."""

import json
import uuid
from datetime import time
from typing import Any
from sqlalchemy import delete, func, select, text

from auth import get_password_hash
from models import (
    AcademicPeriod,
    ClassInstructorAssignment,
    ClassSchedule,
    ClassSection,
    Course,
    CourseInstructorReference,
    CourseOffering,
    CourseOfferingEligibility,
    Curriculum,
    CurriculumCourse,
    LecturerProfile,
    OfferingComponent,
    SchedulePeriodSettings,
    StudyProgram,
    User,
)
from rate_limit import limiter

V1 = "/api/v1"
LEGACY = "/api"
PREVIEW = f"{V1}/scheduling/assignments/preview"
SAVE = f"{V1}/scheduling/assignments"
PASSWORD = "AssignmentUji2026!"


def _login(client, email: str, password: str = PASSWORD) -> dict[str, str]:
    limiter.reset()
    response = client.post(
        f"{V1}/auth/login", json={"identifier": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _case(client, db_session) -> dict[str, Any]:
    async def setup():
        label = uuid.uuid4().hex[:8]
        max_year = (
            await db_session.execute(select(func.max(AcademicPeriod.academic_year_start)))
        ).scalar()
        period = AcademicPeriod(
            academic_year_start=int(max_year or 2026) + 50,
            semester_number=1,
            term="ganjil",
            is_active=False,
        )
        db_session.add(period)
        await db_session.flush()
        programs = {
            code: StudyProgram(
                program_code=f"A{code}{label[:3].upper()}",
                program_name=f"Program Assignment {code} {label}",
                degree_level="sarjana",
                is_active=True,
            )
            for code in ("TSD", "TI")
        }
        db_session.add_all(programs.values())
        await db_session.flush()

        def account(
            name: str, *, active: bool = True, role: str = "lecturer"
        ) -> User:
            user = User(
                email=f"assignment.{name}.{label}@ftmm.unair.ac.id",
                full_name=f"Dosen Assignment {name}",
                role=role,
                is_active=active,
                password_hash=get_password_hash(PASSWORD),
            )
            db_session.add(user)
            return user

        lead = account("lead")
        first = account("first")
        last = account("last")
        inactive = account("inactive", active=False)
        outsider = account("outsider")
        no_profile = account("no-profile")
        student = account("student", role="student")
        foreign = account("foreign")
        other_pj = account("other-pj")
        await db_session.flush()
        db_session.add_all(
            [
                LecturerProfile(
                    user_id=user.user_id,
                    study_program_id=programs["TSD"].study_program_id,
                    is_program_coordinator=user is lead,
                )
                for user in (lead, first, last, inactive, outsider)
            ]
            + [
                LecturerProfile(
                    user_id=foreign.user_id,
                    study_program_id=programs["TI"].study_program_id,
                    is_program_coordinator=False,
                ),
                LecturerProfile(
                    user_id=other_pj.user_id,
                    study_program_id=programs["TI"].study_program_id,
                    is_program_coordinator=True,
                ),
            ]
        )

        async def course(
            program: StudyProgram, prefix: str
        ) -> tuple[CurriculumCourse, CourseOffering, OfferingComponent]:
            curriculum = Curriculum(
                study_program_id=program.study_program_id,
                curriculum_name=f"Kurikulum Assignment {prefix} {label}",
                curriculum_year=int(max_year or 2026) + 50,
                is_active=True,
            )
            db_session.add(curriculum)
            await db_session.flush()
            course_number = uuid.uuid4().int % 10_000
            course_code = f"AS{course_number:04d}"
            while (
                await db_session.execute(
                    select(Course.course_id).where(Course.course_code == course_code)
                )
            ).first() is not None:
                course_number = (course_number + 1) % 10_000
                course_code = f"AS{course_number:04d}"
            course = Course(
                course_code=course_code,
                course_name=f"Mata Kuliah Assignment {prefix}",
                is_active=True,
            )
            db_session.add(course)
            await db_session.flush()
            curriculum_course = CurriculumCourse(
                curriculum_id=curriculum.curriculum_id,
                course_id=course.course_id,
                credits_total=3,
                recommended_semester=1,
                term="ganjil",
                course_type="wajib",
                course_scope="program_studi",
                is_active=True,
            )
            offering = CourseOffering(
                academic_period_id=period.academic_period_id,
                course_id=course.course_id,
                offering_code=f"ASSIGN-{prefix}-{label}",
            )
            db_session.add_all([curriculum_course, offering])
            await db_session.flush()
            db_session.add(
                CourseOfferingEligibility(
                    course_offering_id=offering.course_offering_id,
                    curriculum_course_id=curriculum_course.curriculum_course_id,
                )
            )
            component = OfferingComponent(
                course_offering_id=offering.course_offering_id,
                component_code="KULIAH",
                component_type="lecture",
            )
            db_session.add(component)
            await db_session.flush()
            return curriculum_course, offering, component

        curriculum_course, offering, component = await course(programs["TSD"], "OWN")
        foreign_course, foreign_offering, foreign_component = await course(
            programs["TI"], "FOREIGN"
        )
        class_ids: dict[str, uuid.UUID] = {}
        for index, section in enumerate(("E", "A", "D", "C", "B")):
            section_row = ClassSection(
                offering_component_id=component.offering_component_id,
                section_code=section,
                capacity=40,
                enrollment_status="open",
            )
            db_session.add(section_row)
            await db_session.flush()
            class_ids[section] = section_row.class_section_id
            db_session.add(
                ClassSchedule(
                    class_section_id=section_row.class_section_id,
                    day_of_week=1,
                    start_time=time(7 + index * 2),
                    end_time=time(9 + index * 2),
                    room_name=f"ASSIGN-{label}-{section}",
                )
            )
        foreign_section = ClassSection(
            offering_component_id=foreign_component.offering_component_id,
            section_code="A",
            capacity=40,
            enrollment_status="open",
        )
        db_session.add(foreign_section)
        await db_session.flush()

        references = [
            CourseInstructorReference(
                curriculum_course_id=curriculum_course.curriculum_course_id,
                academic_period_id=period.academic_period_id,
                instructor_name=lead.full_name,
                instructor_role="pjmk",
                user_id=lead.user_id,
                position=4,
            ),
            CourseInstructorReference(
                curriculum_course_id=curriculum_course.curriculum_course_id,
                academic_period_id=period.academic_period_id,
                instructor_name=first.full_name,
                instructor_role="teaching_team",
                user_id=first.user_id,
                position=2,
            ),
            CourseInstructorReference(
                curriculum_course_id=curriculum_course.curriculum_course_id,
                academic_period_id=period.academic_period_id,
                instructor_name=last.full_name,
                instructor_role="teaching_team",
                user_id=last.user_id,
                position=3,
            ),
            CourseInstructorReference(
                curriculum_course_id=curriculum_course.curriculum_course_id,
                academic_period_id=period.academic_period_id,
                instructor_name=inactive.full_name,
                instructor_role="teaching_team",
                user_id=inactive.user_id,
                position=5,
            ),
            CourseInstructorReference(
                curriculum_course_id=curriculum_course.curriculum_course_id,
                academic_period_id=period.academic_period_id,
                instructor_name="Dosen Eksternal",
                instructor_role="teaching_team",
                user_id=None,
                position=6,
            ),
            CourseInstructorReference(
                curriculum_course_id=foreign_course.curriculum_course_id,
                academic_period_id=period.academic_period_id,
                instructor_name=foreign.full_name,
                instructor_role="pjmk",
                user_id=foreign.user_id,
                position=1,
            ),
        ]
        db_session.add_all(references)
        db_session.add_all(
            [
                SchedulePeriodSettings(
                    academic_period_id=period.academic_period_id,
                    study_program_id=None,
                    input_revision=7,
                ),
                SchedulePeriodSettings(
                    academic_period_id=period.academic_period_id,
                    study_program_id=programs["TSD"].study_program_id,
                    input_revision=4,
                ),
                SchedulePeriodSettings(
                    academic_period_id=period.academic_period_id,
                    study_program_id=programs["TI"].study_program_id,
                    input_revision=3,
                ),
            ]
        )
        await db_session.commit()
        return {
            "period_id": period.academic_period_id,
            "program_id": programs["TSD"].study_program_id,
            "other_program_id": programs["TI"].study_program_id,
            "curriculum_course_id": curriculum_course.curriculum_course_id,
            "foreign_curriculum_course_id": foreign_course.curriculum_course_id,
            "offering_id": offering.course_offering_id,
            "foreign_offering_id": foreign_offering.course_offering_id,
            "classes": class_ids,
            "foreign_class_id": foreign_section.class_section_id,
            "lead_id": lead.user_id,
            "first_id": first.user_id,
            "last_id": last.user_id,
            "inactive_id": inactive.user_id,
            "outsider_id": outsider.user_id,
            "no_profile_id": no_profile.user_id,
            "student_id": student.user_id,
            "foreign_id": foreign.user_id,
            "lead_name": lead.full_name,
            "first_name": first.full_name,
            "last_name": last.full_name,
            "ordinary_email": outsider.email,
            "lead_email": lead.email,
            "other_pj_email": other_pj.email,
        }

    return client.portal.call(setup)


def _preview(client, headers, case: dict[str, Any], prefix: str = V1) -> dict[str, Any]:
    response = client.get(
        f"{prefix}/scheduling/assignments/preview",
        headers=headers,
        params={"academic_period_id": str(case["period_id"])},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _own_group(preview: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    return next(
        group
        for group in preview["data"]
        if group["curriculum_course_id"] == str(case["curriculum_course_id"])
    )


def _decision(
    case: dict[str, Any],
    section: str,
    user_id: uuid.UUID,
    *,
    source: str = "auto",
    pinned: bool = False,
    curriculum_course_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    decision = {
        "class_section_id": str(case["classes"][section]),
        "user_id": str(user_id),
        "source": source,
        "is_pinned": pinned,
    }
    if curriculum_course_id is not None:
        decision["curriculum_course_id"] = str(curriculum_course_id)
    return decision


def _save(client, headers, decisions: list[dict[str, Any]], prefix: str = V1) -> Any:
    return client.put(
        f"{prefix}/scheduling/assignments", headers=headers, json={"decisions": decisions}
    )


def _preview_decisions(case: dict[str, Any], preview: dict[str, Any]) -> list[dict[str, Any]]:
    group = _own_group(preview, case)
    return [
        {
            "class_section_id": item["class_section_id"],
            "curriculum_course_id": group["curriculum_course_id"],
            "user_id": item["candidate"]["user_id"],
            "source": "manual" if item["existing_assignment"] else "auto",
            "is_pinned": bool(item["existing_assignment"] and item["existing_assignment"]["is_pinned"]),
        }
        for item in group["classes"]
    ]


async def _database_state(db_session, case: dict[str, Any]) -> dict[str, Any]:
    class_ids = list(case["classes"].values()) + [case["foreign_class_id"]]
    assignments = (
        await db_session.execute(
            select(ClassInstructorAssignment)
            .where(ClassInstructorAssignment.class_section_id.in_(class_ids))
            .order_by(ClassInstructorAssignment.class_section_id)
        )
    ).scalars().all()
    schedules = (
        await db_session.execute(
            select(ClassSchedule)
            .where(ClassSchedule.class_section_id.in_(class_ids))
            .order_by(ClassSchedule.class_schedule_id)
        )
    ).scalars().all()
    revisions = (
        await db_session.execute(
            select(SchedulePeriodSettings)
            .where(SchedulePeriodSettings.academic_period_id == case["period_id"])
            .order_by(SchedulePeriodSettings.study_program_id)
        )
    ).scalars().all()
    return {
        "assignments": [
            (str(row.assignment_id), str(row.class_section_id), str(row.user_id), row.source, row.is_pinned, row.is_active, str(row.curriculum_course_id) if row.curriculum_course_id else None)
            for row in assignments
        ],
        "schedules": [
            (str(row.class_section_id), row.day_of_week, row.start_time, row.end_time, row.room_id, row.room_name)
            for row in schedules
        ],
        "revisions": sorted((str(row.study_program_id), row.input_revision) for row in revisions),
    }


def _state(client, db_session, case: dict[str, Any]) -> dict[str, Any]:
    return client.portal.call(_database_state, db_session, case)


async def _assignment_audit(db_session, actor_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (
        await db_session.execute(
            text(
                "SELECT action, actor_user_id, field_name, old_value, new_value, created_at "
                "FROM admin_authority_traces "
                "WHERE actor_user_id = CAST(:actor_id AS uuid) "
                "AND action LIKE 'class_instructor_assignment_%' "
                "ORDER BY created_at, action"
            ),
            {"actor_id": str(actor_id)},
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def _audit(client, db_session, actor_id: uuid.UUID) -> list[dict[str, Any]]:
    return client.portal.call(_assignment_audit, db_session, actor_id)


def _admin_id(client, db_session) -> uuid.UUID:
    async def read():
        return (
            await db_session.execute(
                select(User.user_id).where(User.email == "admin@ftmm.unair.ac.id")
            )
        ).scalar_one()

    return client.portal.call(read)


def test_assignment_routes_require_scheduler_authentication_and_role(client, db_session, admin_headers, student_headers):
    case = _case(client, db_session)
    decision = _decision(case, "A", case["lead_id"])
    for prefix in (V1, LEGACY):
        assert client.get(f"{prefix}/scheduling/assignments/preview").status_code == 401
        assert client.put(f"{prefix}/scheduling/assignments", json={"decisions": [decision]}).status_code == 401
        assert client.delete(f"{prefix}/scheduling/assignments/{case['classes']['A']}").status_code == 401
    ordinary_headers = _login(client, case["ordinary_email"])
    for headers in (student_headers, ordinary_headers):
        assert client.get(PREVIEW, headers=headers).status_code == 403
        assert _save(client, headers, [decision]).status_code == 403
        assert client.delete(f"{SAVE}/{case['classes']['A']}", headers=headers).status_code == 403
    assert client.get(PREVIEW, headers=admin_headers).status_code == 200


def test_preview_uses_snake_order_and_is_deterministic_without_writes(client, db_session, admin_headers):
    case = _case(client, db_session)
    before = _state(client, db_session, case)
    first = _preview(client, admin_headers, case)
    second = _preview(client, admin_headers, case)
    assert first == second
    assert first["meta"] == {"academic_period_id": str(case["period_id"]), "input_revision": 7}
    group = _own_group(first, case)
    assert [item["user_id"] for item in group["pool"]] == [
        str(case["lead_id"]), str(case["first_id"]), str(case["last_id"])
    ]
    assert [item["position"] for item in group["pool"]] == [1, 2, 3]
    assert group["pool"][0]["is_pjmk"] is True
    assert [item["section_code"] for item in group["classes"]] == ["A", "E", "D", "C", "B"]
    assert [item["candidate"]["user_id"] for item in group["classes"]] == [
        str(case["lead_id"]), str(case["first_id"]), str(case["last_id"]),
        str(case["last_id"]), str(case["first_id"]),
    ]
    assert all(item["existing_assignment"] is None for item in group["classes"])
    assert _state(client, db_session, case) == before


def test_preview_excludes_external_inactive_and_non_pool_accounts(client, db_session, admin_headers):
    case = _case(client, db_session)
    group = _own_group(_preview(client, admin_headers, case), case)
    pool_ids = {item["user_id"] for item in group["pool"]}
    assert pool_ids.isdisjoint({str(case["inactive_id"]), str(case["outsider_id"]), str(case["no_profile_id"])})
    assert all(item["candidate"]["user_id"] in pool_ids for item in group["classes"])


def test_bulk_save_persists_one_assignment_audits_and_bumps_only_affected_revisions(client, db_session, admin_headers):
    case = _case(client, db_session)
    preview = _preview(client, admin_headers, case)
    schedule_before = _state(client, db_session, case)["schedules"]
    decisions = _preview_decisions(case, preview)
    response = _save(client, admin_headers, decisions)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["data"]) == 5
    assert {item["source"] for item in body["data"]} == {"auto"}
    assert {item["is_active"] for item in body["data"]} == {True}
    assert {item["assigned_by"] for item in body["data"]} == {str(_admin_id(client, db_session))}
    assert all(item["assigned_at"] for item in body["data"])
    assert body["meta"]["input_revision"] == 7
    state = _state(client, db_session, case)
    assert state["schedules"] == schedule_before
    assert len([row for row in state["assignments"] if row[5]]) == 5
    audits = _audit(client, db_session, _admin_id(client, db_session))
    assert len(audits) == 5
    assert all(row["old_value"] is None for row in audits)
    for row in audits:
        after = json.loads(row["new_value"])
        assert after["is_active"] is True
        assert after["assigned_by"] == str(_admin_id(client, db_session))
        assert row["created_at"] is not None
    revisions = dict(state["revisions"])
    assert revisions["None"] == 7
    assert revisions[str(case["program_id"])] == 5
    assert revisions[str(case["other_program_id"])] == 3


def test_manual_override_and_pins_survive_later_preview(client, db_session, admin_headers):
    case = _case(client, db_session)
    pinned = [
        _decision(case, "A", case["first_id"], source="manual", pinned=True),
        _decision(case, "B", case["first_id"], source="manual", pinned=True),
    ]
    saved = _save(client, admin_headers, pinned)
    assert saved.status_code == 200, saved.text
    ids = {item["class_section_id"]: item["assignment_id"] for item in saved.json()["data"]}
    preview = _preview(client, admin_headers, case)
    group = _own_group(preview, case)
    by_section = {item["section_code"]: item for item in group["classes"]}
    for section in ("A", "B"):
        item = by_section[section]
        assert item["candidate"]["user_id"] == str(case["first_id"])
        assert item["existing_assignment"]["assignment_id"] == ids[str(case["classes"][section])]
        assert item["existing_assignment"]["source"] == "manual"
        assert item["existing_assignment"]["is_pinned"] is True
    rest = [
        _decision(case, section, case["lead_id"])
        for section in ("D", "C", "E")
    ]
    assert _save(client, admin_headers, rest).status_code == 200
    after = _own_group(_preview(client, admin_headers, case), case)
    by_section = {item["section_code"]: item for item in after["classes"]}
    for section in ("A", "B"):
        assert by_section[section]["existing_assignment"]["assignment_id"] == ids[str(case["classes"][section])]
        assert by_section[section]["existing_assignment"]["user_id"] == str(case["first_id"])


def test_bulk_save_is_idempotent_without_duplicate_audit_or_revision(client, db_session, admin_headers):
    case = _case(client, db_session)
    decisions = [_decision(case, "A", case["lead_id"]), _decision(case, "B", case["last_id"], source="manual", pinned=True)]
    first = _save(client, admin_headers, decisions)
    assert first.status_code == 200, first.text
    decisions[0] = _decision(case, "A", case["first_id"], source="manual", pinned=True)
    overridden = _save(client, admin_headers, decisions)
    assert overridden.status_code == 200, overridden.text
    state = _state(client, db_session, case)
    audits = _audit(client, db_session, _admin_id(client, db_session))
    assert len(audits) == 3
    changed_audit = next(row for row in audits if row["old_value"] is not None)
    before = json.loads(changed_audit["old_value"])
    after = json.loads(changed_audit["new_value"])
    assert before["user_id"] == str(case["lead_id"])
    assert after["user_id"] == str(case["first_id"])
    assert after["source"] == "manual"
    assert after["is_pinned"] is True
    second = _save(client, admin_headers, decisions)
    assert second.status_code == 200, second.text
    assert second.json() == overridden.json()
    assert _state(client, db_session, case) == state
    assert _audit(client, db_session, _admin_id(client, db_session)) == audits
    assert len([row for row in state["assignments"] if row[5]]) == 2


def test_assignment_change_creates_missing_period_and_program_revisions(client, db_session, admin_headers):
    case = _case(client, db_session)

    async def clear_settings():
        await db_session.execute(
            delete(SchedulePeriodSettings).where(
                SchedulePeriodSettings.academic_period_id == case["period_id"]
            )
        )
        await db_session.commit()

    client.portal.call(clear_settings)
    response = _save(client, admin_headers, [_decision(case, "A", case["lead_id"])])
    assert response.status_code == 200, response.text
    assert response.json()["meta"]["input_revision"] == 1
    state = _state(client, db_session, case)
    assert dict(state["revisions"]) == {str(case["program_id"]): 1}


def test_bulk_save_rejects_invalid_accounts_pool_and_duplicate_classes(client, db_session, admin_headers):
    case = _case(client, db_session)
    for user_id, code in (
        (case["inactive_id"], "invalid_lecturer"),
        (case["no_profile_id"], "invalid_lecturer"),
        (case["student_id"], "invalid_lecturer"),
        (case["outsider_id"], "lecturer_not_in_pool"),
        (uuid.uuid4(), "invalid_lecturer"),
    ):
        response = _save(client, admin_headers, [_decision(case, "A", user_id)])
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == code
    duplicate = _decision(case, "A", case["lead_id"])
    response = _save(client, admin_headers, [duplicate, duplicate])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "duplicate_class"
    assert _state(client, db_session, case)["assignments"] == []


def test_pj_scope_uses_session_and_admin_can_cross_programs(client, db_session, admin_headers, pj_headers):
    case = _case(client, db_session)
    pj_headers = _login(client, case["lead_email"])
    pj_preview = _preview(client, pj_headers, case)
    assert [group["curriculum_course_id"] for group in pj_preview["data"]] == [str(case["curriculum_course_id"])]
    assert pj_preview["meta"]["input_revision"] == 4
    foreign_decision = {
        "class_section_id": str(case["foreign_class_id"]),
        "user_id": str(case["foreign_id"]),
        "source": "auto",
        "is_pinned": False,
    }
    assert _save(client, pj_headers, [foreign_decision]).status_code == 403
    assert client.delete(f"{SAVE}/{case['foreign_class_id']}", headers=pj_headers).status_code == 403
    admin_preview = _preview(client, admin_headers, case)
    assert {group["curriculum_course_id"] for group in admin_preview["data"]} == {
        str(case["curriculum_course_id"]), str(case["foreign_curriculum_course_id"])
    }
    assert _save(client, admin_headers, [foreign_decision]).status_code == 200
    assert client.delete(f"{SAVE}/{case['foreign_class_id']}", headers=pj_headers).status_code == 403
    assert next(
        group for group in _preview(client, admin_headers, case)["data"]
        if group["curriculum_course_id"] == str(case["foreign_curriculum_course_id"])
    )["classes"][0]["existing_assignment"] is not None
    assert client.delete(f"{SAVE}/{case['foreign_class_id']}", headers=admin_headers).status_code == 200


def test_delete_clears_only_scoped_active_assignment_and_is_audited_idempotently(client, db_session, admin_headers, pj_headers):
    case = _case(client, db_session)
    pj_headers = _login(client, case["lead_email"])
    saved = _save(client, admin_headers, [_decision(case, "A", case["lead_id"], source="manual", pinned=True)])
    assert saved.status_code == 200, saved.text
    before_revision = _preview(client, pj_headers, case)["meta"]["input_revision"]
    response = client.delete(f"{LEGACY}/scheduling/assignments/{case['classes']['A']}", headers=pj_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"data": None}
    assert _preview(client, pj_headers, case)["meta"]["input_revision"] == before_revision + 1
    state = _state(client, db_session, case)
    assert len(state["assignments"]) == 1
    assert state["assignments"][0][5] is False
    admin_audits = _audit(client, db_session, _admin_id(client, db_session))
    assert len(admin_audits) == 1
    delete_audits = _audit(client, db_session, _actor_id(client, db_session, case["lead_email"]))
    assert len(delete_audits) == 1
    assert delete_audits[0]["action"] == "class_instructor_assignment_delete"
    assert json.loads(delete_audits[0]["old_value"])["is_active"] is True
    assert json.loads(delete_audits[0]["new_value"])["is_active"] is False
    assert client.delete(f"{SAVE}/{case['classes']['A']}", headers=pj_headers).json() == {"data": None}
    assert _state(client, db_session, case) == state
    assert len(_audit(client, db_session, _actor_id(client, db_session, case["lead_email"]))) == 1
    group = _own_group(_preview(client, pj_headers, case), case)
    assert next(item for item in group["classes"] if item["section_code"] == "A")["existing_assignment"] is None


def _actor_id(client, db_session, email: str) -> uuid.UUID:
    async def read():
        return (await db_session.execute(select(User.user_id).where(User.email == email))).scalar_one()

    return client.portal.call(read)


def _add_ambiguous_context(client, db_session, case: dict[str, Any]) -> uuid.UUID:
    async def add_eligibility():
        curriculum = Curriculum(
            study_program_id=case["other_program_id"],
            curriculum_name=f"Kurikulum Ambigu {uuid.uuid4().hex[:8]}",
            curriculum_year=2099,
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.flush()
        curriculum_course = CurriculumCourse(
            curriculum_id=curriculum.curriculum_id,
            course_id=(
                await db_session.execute(
                    select(Course.course_id)
                    .join(CourseOffering, CourseOffering.course_id == Course.course_id)
                    .where(CourseOffering.course_offering_id == case["offering_id"])
                )
            ).scalar_one(),
            credits_total=3,
            recommended_semester=1,
            term="ganjil",
            course_type="wajib",
            is_active=True,
        )
        db_session.add(curriculum_course)
        await db_session.flush()
        cross_team = User(
            email=f"assignment.cross-team.{uuid.uuid4().hex[:8]}@ftmm.unair.ac.id",
            full_name="Dosen Tim Lintas Prodi",
            role="lecturer",
            is_active=True,
        )
        db_session.add(cross_team)
        await db_session.flush()
        db_session.add(
            LecturerProfile(
                user_id=cross_team.user_id,
                study_program_id=case["other_program_id"],
            )
        )
        db_session.add(
            CourseOfferingEligibility(
                course_offering_id=case["offering_id"],
                curriculum_course_id=curriculum_course.curriculum_course_id,
            )
        )
        db_session.add(
            CourseInstructorReference(
                curriculum_course_id=case["curriculum_course_id"],
                academic_period_id=case["period_id"],
                instructor_name="Dosen PJ Prodi Lain",
                instructor_role="teaching_team",
                user_id=case["foreign_id"],
                position=1,
            )
        )
        db_session.add(
            CourseInstructorReference(
                curriculum_course_id=curriculum_course.curriculum_course_id,
                academic_period_id=case["period_id"],
                instructor_name=cross_team.full_name,
                instructor_role="pjmk",
                user_id=cross_team.user_id,
                position=1,
            )
        )
        case["cross_team_id"] = cross_team.user_id
        await db_session.commit()
        return curriculum_course.curriculum_course_id

    return client.portal.call(add_eligibility)


def test_single_context_assignment_defaults_and_returns_curriculum(
    client, db_session, admin_headers
):
    case = _case(client, db_session)
    saved = _save(
        client,
        admin_headers,
        [_decision(case, "A", case["lead_id"], source="manual")],
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"][0]["curriculum_course_id"] == str(
        case["curriculum_course_id"]
    )
    assert _state(client, db_session, case)["assignments"][0][-1] == str(
        case["curriculum_course_id"]
    )


def test_ambiguous_cross_program_context_requires_explicit_lead_scope(
    client, db_session, admin_headers, pj_headers
):
    case = _case(client, db_session)
    pj_headers = _login(client, case["lead_email"])
    other_context = _add_ambiguous_context(client, db_session, case)
    other_pj_headers = _login(client, case["other_pj_email"])
    preview = _preview(client, admin_headers, case)
    groups = [
        group
        for group in preview["data"]
        if any(
            item["class_section_id"] == str(case["classes"]["A"])
            for item in group["classes"]
        )
    ]
    assert {group["curriculum_course_id"] for group in groups} == {
        str(case["curriculum_course_id"]),
        str(other_context),
    }
    for group in groups:
        pool_ids = [item["user_id"] for item in group["pool"]]
        assert len(pool_ids) == len(set(pool_ids)) == 5
        assert set(pool_ids) == {
            str(case["lead_id"]),
            str(case["first_id"]),
            str(case["last_id"]),
            str(case["foreign_id"]),
            str(case["cross_team_id"]),
        }
        assert {item["curriculum_course_id"] for item in group["pool"]} == {
            str(case["curriculum_course_id"]),
            str(other_context),
        }
        for curriculum_course_id in {
            str(case["curriculum_course_id"]),
            str(other_context),
        }:
            first_from_context = next(
                item
                for item in group["pool"]
                if item["curriculum_course_id"] == curriculum_course_id
            )
            assert first_from_context["is_pjmk"] is True
        item = next(
            item
            for item in group["classes"]
            if item["class_section_id"] == str(case["classes"]["A"])
        )
        assert item["curriculum_course_id"] == group["curriculum_course_id"]
        assert item["context_required"] is True
    for prefix in (V1, LEGACY):
        filtered = client.get(
            f"{prefix}/scheduling/assignments/preview",
            headers=admin_headers,
            params={
                "academic_period_id": str(case["period_id"]),
                "curriculum_course_id": str(case["curriculum_course_id"]),
            },
        )
        assert filtered.status_code == 200, filtered.text
        assert {
            group["curriculum_course_id"] for group in filtered.json()["data"]
        } == {str(case["curriculum_course_id"])}

    for headers in (admin_headers, pj_headers, other_pj_headers):
        visible = _preview(client, headers, case)
        assert any(
            group["curriculum_course_id"] == str(other_context)
            for group in visible["data"]
        )
        denied = _save(client, headers, [_decision(case, "A", case["lead_id"])])
        assert denied.status_code == 409
        assert denied.json()["error"]["code"] == "curriculum_context_required"

    other_pj_save = _save(
        client,
        other_pj_headers,
        [
            _decision(
                case,
                "A",
                case["foreign_id"],
                curriculum_course_id=other_context,
            )
        ],
    )
    assert other_pj_save.status_code == 200, other_pj_save.text
    assert other_pj_save.json()["data"][0]["curriculum_course_id"] == str(
        other_context
    )
    denied = _save(
        client,
        pj_headers,
        [
            _decision(
                case,
                "A",
                case["lead_id"],
                curriculum_course_id=other_context,
            )
        ],
    )
    assert denied.status_code == 403
    assert (
        client.delete(
            f"{SAVE}/{case['classes']['A']}",
            params={"curriculum_course_id": str(other_context)},
            headers=pj_headers,
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"{SAVE}/{case['classes']['A']}",
            params={"curriculum_course_id": str(other_context)},
            headers=other_pj_headers,
        ).status_code
        == 200
    )


def test_legacy_ambiguous_assignment_is_blocked_until_context_is_chosen(
    client, db_session, admin_headers
):
    case = _case(client, db_session)
    other_context = _add_ambiguous_context(client, db_session, case)

    async def add_legacy_assignment():
        db_session.add(
            ClassInstructorAssignment(
                class_section_id=case["classes"]["A"],
                academic_period_id=case["period_id"],
                user_id=case["lead_id"],
                source="manual",
                is_pinned=True,
                is_active=True,
                assigned_by=case["lead_id"],
            )
        )
        await db_session.commit()

    client.portal.call(add_legacy_assignment)
    blocked = client.delete(f"{SAVE}/{case['classes']['A']}", headers=admin_headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "curriculum_context_required"
    adopted = _save(
        client,
        admin_headers,
        [
            _decision(
                case,
                "A",
                case["lead_id"],
                source="manual",
                pinned=True,
                curriculum_course_id=other_context,
            )
        ],
    )
    assert adopted.status_code == 200, adopted.text
    assert adopted.json()["data"][0]["curriculum_course_id"] == str(other_context)
    assert (
        client.delete(f"{SAVE}/{case['classes']['A']}", headers=admin_headers).status_code
        == 200
    )


def test_assignment_rejects_context_outside_class_eligibility(
    client, db_session, admin_headers
):
    case = _case(client, db_session)
    response = _save(
        client,
        admin_headers,
        [
            _decision(
                case,
                "A",
                case["lead_id"],
                curriculum_course_id=uuid.uuid4(),
            )
        ],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_curriculum_context"


def test_canonical_and_legacy_preview_and_save_are_identical(client, db_session, admin_headers):
    case = _case(client, db_session)
    canonical = _preview(client, admin_headers, case)
    legacy = _preview(client, admin_headers, case, LEGACY)
    assert canonical == legacy
    decisions = [_decision(case, "A", case["lead_id"]), _decision(case, "B", case["first_id"], source="manual")]
    first = _save(client, admin_headers, decisions)
    second = _save(client, admin_headers, decisions, LEGACY)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert _preview(client, admin_headers, case) == _preview(client, admin_headers, case, LEGACY)
    assert len(_audit(client, db_session, _admin_id(client, db_session))) == 2


def test_preview_selected_period_and_missing_class_validation(client, db_session, admin_headers):
    case = _case(client, db_session)

    async def empty_period():
        period = AcademicPeriod(academic_year_start=2098, semester_number=1, term="ganjil", is_active=False)
        db_session.add(period)
        await db_session.commit()
        return period.academic_period_id

    period_id = client.portal.call(empty_period)
    response = client.get(PREVIEW, headers=admin_headers, params={"academic_period_id": str(period_id)})
    assert response.status_code == 200
    assert response.json() == {"data": [], "meta": {"academic_period_id": str(period_id), "input_revision": 0}}
    missing = {"class_section_id": str(uuid.uuid4()), "user_id": str(case["lead_id"]), "source": "auto", "is_pinned": False}
    assert _save(client, admin_headers, [missing]).json()["error"]["code"] == "class_not_found"
    assert client.delete(f"{SAVE}/{uuid.uuid4()}", headers=admin_headers).json()["error"]["code"] == "class_not_found"


def _single_assignment(
    client,
    headers,
    case: dict[str, Any],
    user_id: uuid.UUID,
    *,
    prefix: str = V1,
) -> Any:
    return client.put(
        f"{prefix}/scheduling/classes/{case['classes']['A']}/assignment",
        headers=headers,
        json={
            "academic_period_id": str(case["period_id"]),
            "user_id": str(user_id),
            "source": "manual",
            "is_pinned": False,
        },
    )


def test_single_class_assignment_rejects_outsider_on_canonical_and_legacy(
    client, db_session, admin_headers
):
    case = _case(client, db_session)
    for user_id, code in (
        (case["inactive_id"], "invalid_lecturer"),
        (case["no_profile_id"], "invalid_lecturer"),
        (case["student_id"], "invalid_lecturer"),
    ):
        response = _single_assignment(client, admin_headers, case, user_id)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == code
    for prefix in (V1, LEGACY):
        response = _single_assignment(
            client, admin_headers, case, case["outsider_id"], prefix=prefix
        )
        assert response.status_code == 422, response.text
        error = response.json()["error"]
        assert error["code"] == "lecturer_not_in_pool"
        assert any(
            detail.get("field") == "user_id"
            and detail.get("code") == "lecturer_not_in_pool"
            for detail in error["details"]
        )
    assert _state(client, db_session, case)["assignments"] == []


def test_single_class_assignment_rejects_previous_period_only_reference(
    client, db_session, admin_headers
):
    case = _case(client, db_session)

    async def add_previous_reference():
        max_year = (
            await db_session.execute(
                select(func.max(AcademicPeriod.academic_year_start))
            )
        ).scalar()
        previous = AcademicPeriod(
            academic_year_start=int(max_year) + 1,
            semester_number=2,
            term="genap",
            is_active=False,
        )
        db_session.add(previous)
        await db_session.flush()
        db_session.add(
            CourseInstructorReference(
                curriculum_course_id=case["curriculum_course_id"],
                academic_period_id=previous.academic_period_id,
                instructor_name="Dosen Periode Sebelumnya",
                instructor_role="teaching_team",
                user_id=case["outsider_id"],
            )
        )
        await db_session.commit()

    client.portal.call(add_previous_reference)
    single = _single_assignment(client, admin_headers, case, case["outsider_id"])
    bulk = _save(client, admin_headers, [_decision(case, "A", case["outsider_id"])])
    assert single.status_code == bulk.status_code == 422
    assert single.json() == bulk.json()
    assert single.json()["error"]["code"] == "lecturer_not_in_pool"
    assert _state(client, db_session, case)["assignments"] == []


def test_single_class_assignment_accepts_pool_member_on_canonical_and_legacy(
    client, db_session, admin_headers
):
    case = _case(client, db_session)
    canonical = _single_assignment(client, admin_headers, case, case["lead_id"])
    assert canonical.status_code == 200, canonical.text
    assert canonical.json()["data"]["user_id"] == str(case["lead_id"])
    legacy = _single_assignment(
        client, admin_headers, case, case["lead_id"], prefix=LEGACY
    )
    assert legacy.status_code == 200, legacy.text
    assert legacy.json() == canonical.json()
    read_back = client.get(
        f"{V1}/scheduling/classes/{case['classes']['A']}/assignment",
        headers=admin_headers,
    )
    assert read_back.json() == canonical.json()
    state = _state(client, db_session, case)
    assert len([row for row in state["assignments"] if row[5]]) == 1
