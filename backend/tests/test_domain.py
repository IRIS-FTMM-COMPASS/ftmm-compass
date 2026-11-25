from schemas import PlacedCourseModel
from features.planning.validator import validate_plan_constraints


def _course(name, code, credits, semester, parity, course_type="Wajib"):
    return PlacedCourseModel(
        name=name,
        code=code,
        credits=credits,
        semester=semester,
        type=course_type,
        parity=parity,
    )


def test_validator_rejects_two_religions():
    plan = {
        1: [
            _course("Agama Islam", "AGI101", 2, 1, "odd"),
            _course("Agama Katolik", "AGK101", 2, 1, "odd"),
        ]
    }
    result = validate_plan_constraints(plan, [])
    assert result.is_valid is False
