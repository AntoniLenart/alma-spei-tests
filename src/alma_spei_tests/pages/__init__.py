"""Playwright page objects for the Alma Spei UI."""

from alma_spei_tests.pages.app_page import AppPage, ShellMessages
from alma_spei_tests.pages.base_page import BasePage
from alma_spei_tests.pages.donors_page import DonorCardPage, DonorListPage, DonorMessages
from alma_spei_tests.pages.imports_page import ImportMessages, ImportsPage
from alma_spei_tests.pages.login_page import AuthMessages, LoginPage

__all__ = [
    "AppPage",
    "AuthMessages",
    "BasePage",
    "DonorCardPage",
    "DonorListPage",
    "DonorMessages",
    "ImportMessages",
    "ImportsPage",
    "LoginPage",
    "ShellMessages",
]
