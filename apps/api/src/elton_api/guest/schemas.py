from datetime import datetime
from elton_api.catalog.schemas import DTO


class SessionDTO(DTO):
    csrf_token: str
    expires_at: datetime
