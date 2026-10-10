# Student Portal – Update Notes

## Latest update: grade-access fix + automatic course enrollment

### Fix: a teacher could edit any course grade for a student on their roster
Previously, a teacher who could only *view* a student's record (because the
student happened to be enrolled in one of that teacher's live courses) could
still add, edit or delete **any** grade on that record — including grades for
courses that teacher never taught. `student_record_service.can_manage_grades`
now draws that line: only the record's owner, a teacher it was explicitly
shared with, or an administrator may touch grades. Roster-based access is
view-only. No database changes needed — `app/routes/teacher_students.py` and
`app/services/student_record_service.py` are the only files touched.

### New: automatic course enrollment by category
Admins no longer need a teacher to add students to a course one by one.
A course's Season + Academic Year + Semester + Department is its "category" —
the same four fields already on both `Course` and `Student`, so no schema
change was needed.
- **Admin Course Catalog page** is now two steps: pick a category (season,
  year, semester, department) first, then add one or more courses to it —
  the category fields stay fixed while you keep adding courses.
- Creating a course immediately enrolls every existing student whose
  season/year/semester/department already match it.
- Creating a student account immediately enrolls them in every existing,
  non-archived course that matches their offering.
- Editing a student's offering fields re-syncs new matches (it only adds
  missing enrollments — it never removes ones that no longer match; a
  teacher can still unenroll individual students from the course roster by
  hand).
- Teachers can still add/remove individual students on their own course
  roster (`teacher/courses.html`) — auto-enrollment replaces the *need* to
  do that for every student, not the ability to fine-tune it afterward.

## What changed

### Student accounts and academic records
- Students can no longer self-register.
- Only administrators can create student accounts.
- Student sign-in uses an exactly 8-digit registration number.
- Registration numbers are unique at the database level and cannot be assigned to more than one student.
- When an admin creates a student, the student's linked academic record is created automatically in the same transaction.
- Admin sets the student's email, password, department, season, academic year, semester (1–8), and Regular/Lateral classification.
- The student list can be filtered and categorized by Season, Year, Semester, and Department.
- Registration number is immutable after creation.
- Student profile is read-only; students cannot edit academic/profile fields.
- Teachers can view academic records for students enrolled in their courses, but automated linked records cannot be edited/deleted by teachers.

### Courses
- Only administrators create courses in the course catalog.
- Courses have Season, Year, Semester, Department, and Regular/Lateral classification.
- A course offering is protected against duplicate creation for the same code + academic classification.
- Newly created courses start unassigned.
- A teacher claims an available course from the catalog.
- A course can have only one teacher; claiming is atomic.
- Teachers can release courses they currently teach. Releasing preserves students, assignments, and submissions and makes the course claimable again.
- Administrators can permanently delete only courses with no enrollments and no assignments. Populated courses should be archived instead.
- Administrators can archive and restore courses without deleting their historical data.

### Assignments and submissions
- Teachers can create assignments only for courses currently assigned to them.
- Teachers can set an assignment deadline using Pakistan local time shown by the form.
- Students can view assignments for their enrolled courses and submit PDF/image files.
- Submission timestamps are compared with the deadline automatically. Submissions after the deadline receive a **Late** status; on-time submissions receive **On time**.
- A student has one active submission per assignment and can replace it; the latest submission retains the correct late/on-time status.

## Migration

This release adds Alembic migration **0009_student_academic_classification_and_course_lifecycle** on top of migration 0008.

The migration adds:
- `students.current_semester`
- `courses.semester`
- `courses.archived`
- unique course-offering protection
- course archive index

When the application starts in its normal debug configuration, pending migrations are applied automatically.

## Updating an existing local installation

1. Back up your current project folder.
2. Extract this update into the existing `student-portal` folder and replace the application source files.
3. Keep your existing `student_portal.db` if you want to preserve your current users, courses, enrollments, assignments, and submissions.
4. Keep your existing virtual environment and `.env` file.
5. Keep your existing `uploads` folder so previously submitted assignment files remain available.
6. Start the application normally and allow migration 0009 to run.

## Clean/demo package

A separate demo-ready package can include a migrated copy of the current database and existing uploads. The source/update package intentionally excludes the database, virtual environment, `.git`, caches, and generated ZIPs so it can safely be applied to an existing installation.