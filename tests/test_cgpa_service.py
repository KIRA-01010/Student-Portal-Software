"""Unit tests for CGPA/SGPA calculation — pure, no DB session required."""

from dataclasses import dataclass

import pytest

from app.services import cgpa_service


@dataclass
class FakeCourseGrade:
    semester: int
    course_name: str
    credit_hours: int
    grade: str


def test_grade_point_known_grades():
    assert cgpa_service.grade_point("A") == 4.00
    assert cgpa_service.grade_point("A-") == 3.67
    assert cgpa_service.grade_point("F") == 0.00


def test_grade_point_unknown_grade_raises():
    with pytest.raises(ValueError):
        cgpa_service.grade_point("Z")


def test_compute_gpa_worked_example_from_spec():
    # Programming — 3cr — A- (3.67); Database — 3cr — B+ (3.33);
    # Software Engineering — 3cr — A (4.00)
    courses = [
        FakeCourseGrade(1, "Programming", 3, "A-"),
        FakeCourseGrade(1, "Database", 3, "B+"),
        FakeCourseGrade(1, "Software Engineering", 3, "A"),
    ]
    # (3.67*3 + 3.33*3 + 4.00*3) / 9 = 33.00 / 9 = 3.6667 -> rounds to 3.67
    assert cgpa_service.compute_gpa(courses) == pytest.approx(3.67)


def test_compute_gpa_no_courses_returns_none():
    assert cgpa_service.compute_gpa([]) is None


def test_compute_gpa_all_same_grade():
    courses = [FakeCourseGrade(1, "X", 3, "A"), FakeCourseGrade(1, "Y", 3, "A")]
    assert cgpa_service.compute_gpa(courses) == 4.00


def test_compute_sgpa_scopes_by_semester():
    class FakeRecord:
        def __init__(self, course_grades):
            self.course_grades = course_grades

    record = FakeRecord(
        [
            FakeCourseGrade(1, "Programming", 3, "A"),
            FakeCourseGrade(2, "Database", 3, "C"),
        ]
    )
    assert cgpa_service.compute_sgpa(record, 1) == 4.00
    assert cgpa_service.compute_sgpa(record, 2) == 2.00
    assert cgpa_service.compute_sgpa(record, 3) is None
