"""Page objects - one class per screen of the Student Portal."""

from .base_page import BasePage, LoggedInPage
from .dashboard_pages import DashboardPage, TeacherDashboardPage
from .admin_students_page import AdminStudentsPage
from .login_page import LoginPage, TeacherLoginPage
from .register_page import RegisterPage, TeacherRegisterPage
from .students_pages import (
    DeleteConfirmPage,
    StudentDetailPage,
    StudentFormPage,
    StudentsListPage,
)

__all__ = [
    "BasePage",
    "LoggedInPage",
    "DashboardPage",
    "TeacherDashboardPage",
    "AdminStudentsPage",
    "LoginPage",
    "TeacherLoginPage",
    "RegisterPage",
    "TeacherRegisterPage",
    "DeleteConfirmPage",
    "StudentDetailPage",
    "StudentFormPage",
    "StudentsListPage",
]
