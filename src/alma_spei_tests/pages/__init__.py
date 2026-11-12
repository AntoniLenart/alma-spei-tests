"""Playwright page objects for the Alma Spei UI."""

from alma_spei_tests.pages.app_page import AppPage, ShellMessages
from alma_spei_tests.pages.base_page import BasePage
from alma_spei_tests.pages.donors_page import DonorListPage, DonorMessages
from alma_spei_tests.pages.login_page import AuthMessages, LoginPage

__all__ = [
    "AppPage",
    "AuthMessages",
    "BasePage",
    "DonorListPage",
    "DonorMessages",
    "LoginPage",
    "ShellMessages",
]
