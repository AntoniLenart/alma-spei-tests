"""Custom test markers/decorators.

`@disruptive` tags tests that disturb the shared running stack (for example by
restarting the backend). Such tests are:

  * opt-in   - deselected unless you pass ``--run-disruptive`` (or run the
               ``disruptive`` execution group, which enables it implicitly); and
  * isolated - placed in a single xdist group so that, if collected under
               parallel execution, they land on one worker and never run
               concurrently with unrelated tests.

Usage::

    from alma_spei_tests.markers import disruptive

    @disruptive
    class TestBackendRestart(BaseE2ETest):
        ...

It works on both test classes and functions.
"""

import pytest

#: Tests tagged disruptive share this xdist group so they never split across
#: workers (and thus never interleave with each other or with other tests when
#: ``--dist loadgroup`` is active).
DISRUPTIVE_XDIST_GROUP = "disruptive"


def disruptive(obj):
    """Mark a test (function or class) as disruptive and isolate it."""
    obj = pytest.mark.disruptive(obj)
    obj = pytest.mark.xdist_group(DISRUPTIVE_XDIST_GROUP)(obj)
    return obj
