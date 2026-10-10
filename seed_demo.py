"""Create demo data for the public live demo.

Run AFTER `alembic upgrade head`, from the project root:

    python seed_demo.py

Safe to run on every start: if the demo admin already exists, it does nothing.
Everything here goes through the app's own models and services, so the demo
data obeys the same rules as data entered through the website.

The passwords below are PUBLIC (they go in the README so visitors can log in).
Never reuse them anywhere real.
"""

from datetime import timedelta

from app.database.session import SessionLocal
from app.models.student_record import CourseGrade
from app.models.teacher import Teacher, TeacherStatus
from app.services import course_service, student_service, teacher_service
from app.utils.clock import utcnow
from app.utils.security import hash_password

# --- Public demo logins --------------------------------------------------------
ADMIN_USERNAME = "demo_admin"
ADMIN_PASSWORD = "DemoAdmin#2026"

TEACHER_USERNAME = "demo_teacher"
TEACHER_PASSWORD = "DemoTeacher#2026"

STUDENT_PASSWORD = "DemoStudent#2026"
STUDENTS = [
    # (registration number, first, last, email)
    ("20250001", "Ayesha", "Khan", "ayesha.demo@example.com"),
    ("20250002", "Bilal", "Ahmed", "bilal.demo@example.com"),
]

# --- Offering shared by the demo students and courses --------------------------
DEPARTMENT = "Software Engineering"
SEASON = "Fall"
ACADEMIC_YEAR = 2025
CURRENT_SEMESTER = 3
ENTRY_TYPE = "Regular"

# Live courses for the CURRENT semester (these students get enrolled automatically).
COURSES = [
    ("Data Structures", "CS201", "Arrays, linked lists, trees, graphs and complexity."),
    ("Database Systems", "CS230", "Relational modelling, SQL and normalisation."),
    ("Web Engineering", "SE240", "HTTP, REST APIs and server-side frameworks."),
]

# Past results that feed CGPA/SGPA: (semester, course name, credit hours, grade)
PAST_GRADES = {
    "20250001": [
        (1, "Programming Fundamentals", 4, "A"),
        (1, "Calculus I", 3, "B+"),
        (1, "Islamic Studies", 2, "A-"),
        (2, "Object-Oriented Programming", 4, "A-"),
        (2, "Discrete Mathematics", 3, "B"),
        (2, "Communication Skills", 2, "A"),
    ],
    "20250002": [
        (1, "Programming Fundamentals", 4, "B+"),
        (1, "Calculus I", 3, "B"),
        (1, "Islamic Studies", 2, "B+"),
        (2, "Object-Oriented Programming", 4, "B"),
        (2, "Discrete Mathematics", 3, "C+"),
        (2, "Communication Skills", 2, "A-"),
    ],
}


def main() -> None:
    with SessionLocal() as db:
        if teacher_service.get_by_username(db, ADMIN_USERNAME):
            print("Demo data already present - nothing to do.")
            return

        # 1. Administrator (a teacher account with the admin flag, pre-approved).
        admin = teacher_service.create(
            db,
            first_name="Demo",
            last_name="Admin",
            email="demo.admin@example.com",
            username=ADMIN_USERNAME,
            password_hash=hash_password(ADMIN_PASSWORD),
            department=DEPARTMENT,
            status=TeacherStatus.APPROVED,
        )
        admin.is_admin = True
        db.commit()

        # 2. An approved ordinary teacher (so visitors can see the teacher role).
        teacher = teacher_service.create(
            db,
            first_name="Demo",
            last_name="Teacher",
            email="demo.teacher@example.com",
            username=TEACHER_USERNAME,
            password_hash=hash_password(TEACHER_PASSWORD),
            department=DEPARTMENT,
            status=TeacherStatus.APPROVED,
        )

        # 3. Course catalog first, so students are auto-enrolled on creation.
        courses = []
        for name, code, description in COURSES:
            course = course_service.create_course(
                db,
                name=name,
                code=code,
                description=description,
                season=SEASON,
                academic_year=ACADEMIC_YEAR,
                semester=CURRENT_SEMESTER,
                department=DEPARTMENT,
                entry_type=ENTRY_TYPE,
            )
            # The teacher claims every course (admin creates, teacher teaches).
            course_service.claim_course(db, teacher.id, course.id)
            courses.append(course)

        # 4. Students. create_admin_student also creates each student's academic
        #    record, linked to the account.
        for reg_no, first, last, email in STUDENTS:
            student = student_service.create_admin_student(
                db,
                registration_number=reg_no,
                first_name=first,
                last_name=last,
                email=email,
                password=STUDENT_PASSWORD,
                department=DEPARTMENT,
                season=SEASON,
                academic_year=ACADEMIC_YEAR,
                entry_type=ENTRY_TYPE,
                current_semester=CURRENT_SEMESTER,
                created_by_teacher_id=admin.id,
            )
            course_service.enroll_student_in_matching_courses(db, student)

            for semester, course_name, credit_hours, grade in PAST_GRADES[reg_no]:
                db.add(
                    CourseGrade(
                        student_record_id=student.academic_record.id,
                        semester=semester,
                        course_name=course_name,
                        credit_hours=credit_hours,
                        grade=grade,
                    )
                )
            db.commit()

        # 5. Assignments: one still open, one already past its deadline.
        now = utcnow()
        course_service.create_assignment(
            db, courses[0], "Linked List Implementation",
            "Implement a singly linked list with insert, delete and reverse.",
            now + timedelta(days=7),
        )
        course_service.create_assignment(
            db, courses[1], "ER Diagram and Schema",
            "Design an ER diagram for a library system and write the schema.",
            now + timedelta(days=14),
        )
        course_service.create_assignment(
            db, courses[2], "REST API Report",
            "Write a short report comparing two REST API designs.",
            now - timedelta(days=3),
        )

    print("Demo data created.")
    print(f"  Admin:   {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
    print(f"  Teacher: {TEACHER_USERNAME} / {TEACHER_PASSWORD}")
    for reg_no, *_ in STUDENTS:
        print(f"  Student: {reg_no} / {STUDENT_PASSWORD}")


if __name__ == "__main__":
    main()
