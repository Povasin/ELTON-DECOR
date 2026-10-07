from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from elton_api.cart.schemas import CartDTO, QuantityCommand
from elton_api.cart.service import CartService, expected_version
from elton_api.guest.csrf import require_csrf
from elton_api.guest.service import GuestPrincipal, database_session, resolve_guest

router = APIRouter(prefix="/api/v1/cart", tags=["cart"])


def mutation_version(request: Request, principal: GuestPrincipal = Depends(resolve_guest, scope="function")) -> int:
    require_csrf(request, principal)
    return expected_version(request)


def etag(response: Response, cart: CartDTO) -> CartDTO:
    response.headers["ETag"] = f'"{cart.version}"'
    return cart


@router.get("", response_model=CartDTO)
def get_cart(response: Response, principal: GuestPrincipal = Depends(resolve_guest, scope="function"), session: Session = Depends(database_session, scope="function")) -> CartDTO:
    return etag(response, CartService(session).get_cart(principal))


@router.put("/items/{product_id}", response_model=CartDTO, responses={428: {"description": "If-Match required"}, 409: {"description": "Version conflict"}})
def set_quantity(product_id: UUID, command: QuantityCommand, response: Response, principal: GuestPrincipal = Depends(resolve_guest, scope="function"), version: int = Depends(mutation_version, scope="function"), session: Session = Depends(database_session, scope="function")) -> CartDTO:
    return etag(response, CartService(session).mutate(principal, product_id, version, command.quantity))


@router.delete("/items/{product_id}", response_model=CartDTO, responses={428: {"description": "If-Match required"}, 409: {"description": "Version conflict"}})
def delete_item(product_id: UUID, response: Response, principal: GuestPrincipal = Depends(resolve_guest, scope="function"), version: int = Depends(mutation_version, scope="function"), session: Session = Depends(database_session, scope="function")) -> CartDTO:
    return etag(response, CartService(session).mutate(principal, product_id, version, None))
