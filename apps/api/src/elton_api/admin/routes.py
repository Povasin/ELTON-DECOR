from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from elton_api.admin.auth import AdminPrincipal, admin_csrf_token, admin_dependency, admin_if_match, issue_login, revoke_current_session
from elton_api.admin.schemas import AdminDraftDTO, AdminLoginDTO, AdminProductListQuery, AdminSessionDTO, BundleAdminDTO, BundleWriteDTO, DraftListQuery, DraftPageDTO, ProductAdminDTO, ProductAdminPageDTO, ProductCreateDTO, ProductWriteDTO, SitePriceWriteDTO
from elton_api.admin.service import AdminCatalogService, AdminDraftService
from elton_api.guest.service import database_session

router = APIRouter(prefix="/api/v1/admin", tags=["admin foundation"])


def _session_dto(request: Request, admin: AdminPrincipal) -> AdminSessionDTO:
    if admin.expires_at is None:
        raise RuntimeError("active admin session must have expiry")
    return AdminSessionDTO(
        id=admin.id, email=admin.email, permissions=sorted(admin.permissions),
        csrf_token=admin_csrf_token(admin.session_id, request.app.state.settings.session_csrf_key.get_secret_value()),
        expires_at=admin.expires_at,
    )


def _secure_cookie(request: Request) -> bool:
    return not (request.url.scheme == "http" and request.url.hostname in {"localhost", "127.0.0.1", "::1"})


@router.post("/auth/login", response_model=AdminSessionDTO, responses={401: {"description": "Invalid credentials"}, 403: {"description": "Origin rejected"}, 429: {"description": "Rate limited"}})
def login(command: AdminLoginDTO, request: Request, response: Response, session: Session = Depends(database_session, scope="function")) -> AdminSessionDTO:
    admin, proof = issue_login(request, email=command.email, password=command.password.get_secret_value(), session=session)
    response.set_cookie("elton_admin", proof, path="/api", max_age=request.app.state.settings.admin_session_ttl_seconds, httponly=True, secure=_secure_cookie(request), samesite="lax")
    return _session_dto(request, admin)


@router.get("/session", response_model=AdminSessionDTO, responses={401: {"description": "Admin session required"}, 403: {"description": "Origin rejected"}})
def admin_session(request: Request, admin: AdminPrincipal = Depends(admin_dependency("catalog.read"))) -> AdminSessionDTO:
    return _session_dto(request, admin)


@router.post("/auth/logout", status_code=204, responses={401: {"description": "Admin session required"}, 403: {"description": "CSRF or Origin rejected"}})
def logout(request: Request, response: Response, admin: AdminPrincipal = Depends(admin_dependency("catalog.read", mutation=True)), session: Session = Depends(database_session, scope="function")) -> Response:
    revoke_current_session(request, admin, session)
    response.delete_cookie("elton_admin", path="/api", httponly=True, secure=_secure_cookie(request), samesite="lax")
    response.status_code = 204
    return response


@router.get("/products", response_model=ProductAdminPageDTO, responses={401: {"description": "Admin session required"}, 403: {"description": "Permission denied"}})
def list_products(query: AdminProductListQuery = Depends(), admin: AdminPrincipal = Depends(admin_dependency("catalog.read")), session: Session = Depends(database_session, scope="function")) -> ProductAdminPageDTO:
    return AdminCatalogService(session).list_products(q=query.q, limit=query.limit, cursor=query.cursor)


@router.post("/products", response_model=ProductAdminDTO, status_code=201, responses={401: {"description": "Admin session required"}, 403: {"description": "Permission or CSRF rejected"}, 409: {"description": "SKU or slug already exists"}})
def create_product(command: ProductCreateDTO, request: Request, response: Response, admin: AdminPrincipal = Depends(admin_dependency("catalog.write", mutation=True)), session: Session = Depends(database_session, scope="function")) -> ProductAdminDTO:
    result = AdminCatalogService(session).create_product(admin, command)
    response.headers["ETag"] = f'"{result.version}"'
    return result


@router.get("/products/{product_id}", response_model=ProductAdminDTO, responses={401: {"description": "Admin session required"}, 403: {"description": "Permission denied"}, 404: {"description": "Unknown product"}})
def get_product(product_id: UUID, admin: AdminPrincipal = Depends(admin_dependency("catalog.read")), session: Session = Depends(database_session, scope="function")) -> ProductAdminDTO:
    return AdminCatalogService(session).get_product(product_id)


@router.get("/products/{product_id}/bundle", response_model=BundleAdminDTO, responses={401: {"description": "Admin session required"}, 403: {"description": "Permission denied"}, 404: {"description": "Unknown bundle"}})
def get_bundle(product_id: UUID, admin: AdminPrincipal = Depends(admin_dependency("catalog.read")), session: Session = Depends(database_session, scope="function")) -> BundleAdminDTO:
    return AdminCatalogService(session).get_bundle(product_id)


@router.patch("/products/{product_id}", response_model=ProductAdminDTO, responses={401: {"description": "Admin session required"}, 403: {"description": "Permission or CSRF rejected"}, 409: {"description": "Stale product version"}})
def update_product(product_id: UUID, command: ProductWriteDTO, request: Request, response: Response, admin: AdminPrincipal = Depends(admin_dependency("catalog.write", mutation=True)), version: int = Depends(admin_if_match, scope="function"), session: Session = Depends(database_session, scope="function")) -> ProductAdminDTO:
    result = AdminCatalogService(session).update_product(admin, product_id, command, version)
    response.headers["ETag"] = f'"{result.version}"'
    return result


@router.put("/products/{product_id}/site-price", response_model=ProductAdminDTO, responses={401: {"description": "Admin session required"}, 403: {"description": "Permission or CSRF rejected"}, 409: {"description": "Stale product version"}})
def set_site_price(product_id: UUID, command: SitePriceWriteDTO, request: Request, response: Response, admin: AdminPrincipal = Depends(admin_dependency("catalog.write", mutation=True)), version: int = Depends(admin_if_match, scope="function"), session: Session = Depends(database_session, scope="function")) -> ProductAdminDTO:
    result = AdminCatalogService(session).set_site_price(admin, product_id, command, version)
    response.headers["ETag"] = f'"{result.version}"'
    return result


@router.put("/products/{product_id}/bundle", response_model=BundleAdminDTO, responses={401: {"description": "Admin session required"}, 403: {"description": "Permission or CSRF rejected"}, 409: {"description": "Stale product version"}})
def replace_bundle(product_id: UUID, command: BundleWriteDTO, request: Request, response: Response, admin: AdminPrincipal = Depends(admin_dependency("catalog.write", mutation=True)), version: int = Depends(admin_if_match, scope="function"), session: Session = Depends(database_session, scope="function")) -> BundleAdminDTO:
    result = AdminCatalogService(session).replace_bundle(admin, product_id, command, version)
    response.headers["ETag"] = f'"{version + 1}"'
    return result


@router.get("/checkout-drafts", response_model=DraftPageDTO, responses={401: {"description": "Admin session required"}, 403: {"description": "Permission denied"}})
def list_drafts(request: Request, query: DraftListQuery = Depends(), admin: AdminPrincipal = Depends(admin_dependency("drafts.read")), session: Session = Depends(database_session, scope="function")) -> DraftPageDTO:
    return AdminDraftService(session).list_drafts(admin, cursor=query.cursor, created_from=query.created_from, created_to=query.created_to, trace_id=getattr(request.state, "trace_id", None))


@router.get("/checkout-drafts/{draft_id}", response_model=AdminDraftDTO, responses={401: {"description": "Admin session required"}, 403: {"description": "Permission denied"}, 404: {"description": "Unknown draft"}})
def get_draft(draft_id: UUID, request: Request, admin: AdminPrincipal = Depends(admin_dependency("drafts.read")), session: Session = Depends(database_session, scope="function")) -> AdminDraftDTO:
    return AdminDraftService(session).get_draft(admin, draft_id, getattr(request.state, "trace_id", None))
