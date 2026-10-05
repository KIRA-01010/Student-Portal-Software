"""CGPA / SGPA calculation.

Pure functions, no DB session required, so they are trivially unit-testable
and reusable from any route or service. Nothing here is cached or stored —
callers always recompute from the current `CourseGrade` rows, so a CGPA can
never go stale after a grade or credit-hour edit.
"""

from typing import Dict, List, Optional, Sequence

# Fixed academic scale — not user-editable, so a constant rather than a DB
# table. `grade` is validated against these keys before it ever reaches the
# database (see app.utils.validators.validate_grade).
GRADE_POINTS: Dict[str, float] = {
    "A": 4.00,
    "A-": 3.67,
    "B+": 3.33,
    "B": 3.00,
    "B-": 2.67,
    "C+": 2.33,
    "C": 2.00,
    "D": 1.00,
    "F": 0.00,
}


def grade_point(grade: str) -> float:
    """Return the grade point for a letter grade.

    Raises:
        ValueError: if `grade` is not a recognised letter grade. Should never
            happen once `validate_grade` has run, but fail loudly rather than
            silently treating an unknown grade as 0.0.
    """
    try:
        return GRADE_POINTS[grade]
    except KeyError:
        raise ValueError(f"Unknown grade: {grade!r}") from None


def compute_gpa(course_grades: Sequence) -> Optional[float]:
    """CGPA/SGPA formula: Σ(GradePoint × CreditHours) / Σ(CreditHours).

    Accepts any sequence of objects exposing `.grade` and `.credit_hours`
    (real `CourseGrade` rows, or lightweight stand-ins in tests).

    Returns `None` — not 0.0 — when there are no credit hours, so templates
    can render "N/A" instead of a misleading zero.
    """
    total_credit_hours = sum(course.credit_hours for course in course_grades)
    if total_credit_hours == 0:
        return None

    weighted_sum = sum(
        grade_point(course.grade) * course.credit_hours for course in course_grades
    )
    return round(weighted_sum / total_credit_hours, 2)


def compute_cgpa(student_record) -> Optional[float]:
    """CGPA across every course the student has taken."""
    return compute_gpa(student_record.course_grades)


def compute_sgpa(student_record, semester: int) -> Optional[float]:
    """GPA scoped to a single semester."""
    scoped = [c for c in student_record.course_grades if c.semester == semester]
    return compute_gpa(scoped)


def semester_breakdown(student_record) -> List[Dict]:
    """One entry per semester present, for the student detail page."""
    semesters = sorted({c.semester for c in student_record.course_grades})
    return [
        {
            "semester": semester,
            "courses": [c for c in student_record.course_grades if c.semester == semester],
            "sgpa": compute_sgpa(student_record, semester),
        }
        for semester in semesters
    ]
