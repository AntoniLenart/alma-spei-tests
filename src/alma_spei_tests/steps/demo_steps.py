"""Reusable steps for the synthetic demo population (``bb seed-demo``)."""

from alma_spei_tests.orchestration import SeedResult, Stack
from alma_spei_tests.steps import step


@step("Run seed-demo with {username} as the audit actor")
def seed_demo(stack: Stack, username: str) -> SeedResult:
    return stack.seed_demo(username)
