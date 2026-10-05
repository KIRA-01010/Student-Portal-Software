"""Form objects for teacher-managed student academic records."""

from dataclasses import dataclass
from typing import Dict

from app.utils import validators as v


@dataclass
class StudentRecordForm:
    registration_number: str = ""
    first_name: str = ""
    last_name: str = ""
    department: str = ""
    current_semester: str = ""

    @classmethod
    def from_raw(
        cls,
        registration_number: str,
        first_name: str,
        last_name: str,
        department: str,
        current_semester: str,
    ) -> "StudentRecordForm":
        return cls(
            registration_number=v.clean(registration_number),
            first_name=v.clean(first_name),
            last_name=v.clean(last_name),
            department=v.clean(department),
            current_semester=v.clean(current_semester),
        )

    def validate(self) -> Dict[str, str]:
        errors: Dict[str, str] = {}
        if error := v.validate_registration_number(self.registration_number):
            errors["registration_number"] = error
        if error := v.validate_name(self.first_name, "First name"):
            errors["first_name"] = error
        if error := v.validate_name(self.last_name, "Last name"):
            errors["last_name"] = error
        if error := v.validate_department(self.department):
            errors["department"] = error
        if error := v.validate_semester(self.current_semester):
            errors["current_semester"] = error
        return errors

    def as_form_values(self) -> Dict[str, str]:
        return {
            "registration_number": self.registration_number,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "department": self.department,
            "current_semester": self.current_semester,
        }

    @property
    def current_semester_int(self) -> int:
        return int(self.current_semester)


@dataclass
class CourseGradeForm:
    semester: str = ""
    course_name: str = ""
    credit_hours: str = ""
    grade: str = ""

    @classmethod
    def from_raw(
        cls, semester: str, course_name: str, credit_hours: str, grade: str
    ) -> "CourseGradeForm":
        return cls(
            semester=v.clean(semester),
            course_name=v.clean(course_name),
            credit_hours=v.clean(credit_hours),
            grade=v.clean(grade).upper(),
        )

    def validate(self) -> Dict[str, str]:
        errors: Dict[str, str] = {}
        if error := v.validate_semester(self.semester):
            errors["semester"] = error
        if error := v.validate_course_name(self.course_name):
            errors["course_name"] = error
        if error := v.validate_credit_hours(self.credit_hours):
            errors["credit_hours"] = error
        if error := v.validate_grade(self.grade):
            errors["grade"] = error
        return errors

    def as_form_values(self) -> Dict[str, str]:
        return {
            "semester": self.semester,
            "course_name": self.course_name,
            "credit_hours": self.credit_hours,
            "grade": self.grade,
        }

    @property
    def semester_int(self) -> int:
        return int(self.semester)

    @property
    def credit_hours_int(self) -> int:
        return int(self.credit_hours)
