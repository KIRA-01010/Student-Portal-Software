"""Route registration.

Add new feature routers here (courses, attendance, grades…) and they are picked
up automatically by the app factory.
"""

from fastapi import APIRouter

from app.routes import (
    admin,
    auth,
    dashboard,
    assignments,
    courses,
    pages,
    teacher_auth,
    teacher_dashboard,
    teacher_students,
)

api_router = APIRouter()
api_router.include_router(pages.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(courses.router)
api_router.include_router(assignments.student_router)
api_router.include_router(assignments.teacher_router)
api_router.include_router(teacher_auth.router)
api_router.include_router(teacher_dashboard.router)
api_router.include_router(teacher_students.router)
api_router.include_router(admin.router)

__all__ = ["api_router"]
