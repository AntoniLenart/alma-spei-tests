"""Health response contract.

Mirrors the app's shared Malli schema:

    ;; src/common/alma_spei/common/contracts/health.cljc
    (def response
      [:map {:closed true}
       [:status [:enum "ok" "unavailable"]]])
"""

from alma_spei_tests.constants import HEALTH_STATUS_VALUES
from alma_spei_tests.contracts.schema import ClosedMap, Enum

HEALTH_RESPONSE = ClosedMap({"status": Enum(*HEALTH_STATUS_VALUES)})
