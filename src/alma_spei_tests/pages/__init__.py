"""Playwright page objects for the Alma Spei UI."""

from alma_spei_tests.pages.accounts_page import AccountMessages, AccountsPage
from alma_spei_tests.pages.app_page import AppPage, ShellMessages
from alma_spei_tests.pages.base_page import BasePage
from alma_spei_tests.pages.donors_page import DonorCardPage, DonorListPage, DonorMessages
from alma_spei_tests.pages.execution_page import ExecutionMessages, ExecutionPage
from alma_spei_tests.pages.imports_page import ImportMessages, ImportsPage
from alma_spei_tests.pages.login_page import AuthMessages, LoginPage
from alma_spei_tests.pages.review_page import ReviewMessages, ReviewPage

__all__ = [
    "AccountMessages",
    "AccountsPage",
    "AppPage",
    "AuthMessages",
    "BasePage",
    "DonorCardPage",
    "DonorListPage",
    "DonorMessages",
    "ExecutionMessages",
    "ExecutionPage",
    "ImportMessages",
    "ImportsPage",
    "LoginPage",
    "ReviewMessages",
    "ReviewPage",
    "ShellMessages",
]
