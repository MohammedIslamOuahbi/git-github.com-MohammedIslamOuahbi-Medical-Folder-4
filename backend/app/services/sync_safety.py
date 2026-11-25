"""Permanent phase-one barriers. Re-enable only after a reviewed replacement."""
from typing import NoReturn
from fastapi import HTTPException

SAFETY_CODE = "OPERATION_SUSPENDED_FOR_DATA_SAFETY"
SAFETY_MESSAGE = (
    "Operation suspendue pour proteger les donnees. Les elements du stockage actuel "
    "ne sont pas supprimes par cette operation; leur conservation depend de ce stockage "
    "jusqu'a la reprise durable. Aucun element deja efface n'est restaure."
)

def suspend_for_data_safety(operation: str) -> NoReturn:
    # 423 is intentional: this is not a transient network/server failure.
    raise HTTPException(status_code=423, detail={
        "message": f"{SAFETY_CODE}: {SAFETY_MESSAGE}",
        "details": {"code": SAFETY_CODE, "operation": operation, "retryable": False},
    })
