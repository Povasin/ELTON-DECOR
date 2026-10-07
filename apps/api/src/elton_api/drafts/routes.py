from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from elton_api.drafts.quote_service import QuoteService
from elton_api.drafts.save_service import SaveService
from elton_api.drafts.schemas import DraftDTO, DraftQuoteDTO, DraftSaveCommand, QuoteCommand
from elton_api.guest.csrf import require_csrf
from elton_api.guest.service import GuestPrincipal, database_session, resolve_guest

router = APIRouter(prefix="/api/v1", tags=["local drafts"])


def mutation_guest(request: Request, principal: GuestPrincipal = Depends(resolve_guest, scope="function")) -> GuestPrincipal:
    require_csrf(request, principal)
    return principal


def save_key(key: str | None = Header(default=None, alias="Idempotency-Key"), principal: GuestPrincipal = Depends(mutation_guest, scope="function")) -> str:
    if key is None:
        raise HTTPException(428, detail="PRECONDITION_REQUIRED")
    try:
        if str(UUID(key)) != key.lower():
            raise ValueError
    except ValueError:
        raise HTTPException(422, detail="VALIDATION_ERROR") from None
    return key


@router.post("/draft-quotes", status_code=201, response_model=DraftQuoteDTO, responses={409: {"description": "Cart changed"}})
def create_quote(command: QuoteCommand, request: Request, principal: GuestPrincipal = Depends(mutation_guest, scope="function"), session: Session = Depends(database_session, scope="function")) -> DraftQuoteDTO:
    return QuoteService(session, request.app.state.settings.draft_quote_ttl_seconds).create_quote(principal, command.cart_version)


@router.post("/checkout-drafts", status_code=201, response_model=DraftDTO, responses={409: {"description": "Idempotency, cart or quote conflict"}, 410: {"description": "Quote expired"}, 428: {"description": "Idempotency-Key required"}})
def save_draft(command: DraftSaveCommand, response: Response, principal: GuestPrincipal = Depends(mutation_guest, scope="function"), key: str = Depends(save_key, scope="function"), session: Session = Depends(database_session, scope="function")) -> DraftDTO:
    result = SaveService(session).save_draft(principal, command, key)
    if result.replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return result.dto


@router.get("/checkout-drafts/{draft_id}", response_model=DraftDTO, responses={404: {"description": "Unknown or foreign draft"}})
def get_draft(draft_id: UUID, principal: GuestPrincipal = Depends(resolve_guest, scope="function"), session: Session = Depends(database_session, scope="function")) -> DraftDTO:
    return SaveService(session).get_draft(principal, draft_id)
