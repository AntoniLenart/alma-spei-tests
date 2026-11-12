"""Auth/account response contracts.

Mirrors ``src/common/alma_spei/common/contracts/auth.cljc``:

    principal          [:map {:closed true} [:id :string] [:username :string]
                        [:display-name :string] [:administrator :boolean]
                        [:active :boolean] [:password-change-required :boolean]]
    session-response   [:map {:closed true} [:user [:maybe principal]] [:csrf :string]]
    account-response   [:map {:closed true} [:user principal]]
    temporary-response [:map {:closed true} [:user principal]
                        [:temporary-password [:string {:min 20}]]]
    accounts-response  [:map {:closed true} [:users [:vector principal]]]
"""

from alma_spei_tests.constants import TEMPORARY_PASSWORD_MIN_LENGTH
from alma_spei_tests.contracts.schema import BOOLEAN, STRING, ClosedMap, Maybe, Predicate, Vector

PRINCIPAL = ClosedMap(
    {
        "id": STRING,
        "username": STRING,
        "display-name": STRING,
        "administrator": BOOLEAN,
        "active": BOOLEAN,
        "password-change-required": BOOLEAN,
    }
)

TEMPORARY_PASSWORD = Predicate(
    f"a string of at least {TEMPORARY_PASSWORD_MIN_LENGTH} characters",
    lambda v: isinstance(v, str) and len(v) >= TEMPORARY_PASSWORD_MIN_LENGTH,
)

SESSION_RESPONSE = ClosedMap({"user": Maybe(PRINCIPAL), "csrf": STRING})
ACCOUNT_RESPONSE = ClosedMap({"user": PRINCIPAL})
TEMPORARY_RESPONSE = ClosedMap({"user": PRINCIPAL, "temporary-password": TEMPORARY_PASSWORD})
ACCOUNTS_RESPONSE = ClosedMap({"users": Vector(PRINCIPAL)})
