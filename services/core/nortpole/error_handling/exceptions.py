"""NortPoleError — the single exception type for all NortPole business errors.

Raise ``NortPoleError`` instead of ``HTTPException`` in business code.  A global
FastAPI exception handler (registered via ``register_evolvxsi_exception_handlers``)
converts it into a JSON response with the standard
``{"error_code": "...", "detail": "..."}`` shape.

Usage::

    from nortpole.error_handling.error_codes import NortPoleErrorCode
    from nortpole.error_handling.exceptions import NortPoleError

    raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Session not found")

For upstream errors with a dynamic HTTP status (e.g. billing service),
use ``status_code_override``::

    raise NortPoleError(
        NortPoleErrorCode.BAD_GATEWAY,
        detail,
        status_code_override=upstream_status,
    )
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.utils.logger import setup_logger

logger = setup_logger()


class NortPoleError(Exception):
    """Structured error that maps to a specific ``NortPoleErrorCode``.

    Attributes:
        error_code: The ``NortPoleErrorCode`` enum member.
        detail: Human-readable detail (defaults to the error code string).
        status_code: HTTP status — either overridden or from the error code.
    """

    def __init__(
        self,
        error_code: NortPoleErrorCode,
        detail: str | None = None,
        *,
        status_code_override: int | None = None,
        extra: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        resolved_detail = detail or error_code.code
        super().__init__(resolved_detail)
        self.error_code = error_code
        self.detail = resolved_detail
        self._status_code_override = status_code_override
        # extra: machine-readable fields merged into the JSON body (e.g. reset_at).
        # headers: response headers the FE/clients need (e.g. Retry-After).
        self.extra = extra
        self.headers = headers

    @property
    def status_code(self) -> int:
        return self._status_code_override or self.error_code.status_code


def log_evolvxsi_error(exc: NortPoleError) -> None:
    detail = exc.detail
    status_code = exc.status_code
    if status_code >= 500:
        logger.error("NortPoleError %s: %s", exc.error_code.code, detail)
    elif status_code >= 400:
        logger.warning("NortPoleError %s: %s", exc.error_code.code, detail)


def evolvxsi_error_to_json_response(exc: NortPoleError) -> JSONResponse:
    content = exc.error_code.detail(exc.detail)
    if exc.extra:
        # extra first so the canonical error_code/detail can't be overwritten.
        content = {**exc.extra, **content}
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers,
    )


def register_evolvxsi_exception_handlers(app: FastAPI) -> None:
    """Register a global handler that converts ``NortPoleError`` to JSON responses.

    Must be called *after* the app is created but *before* it starts serving.
    The handler logs at WARNING for 4xx and ERROR for 5xx.
    """

    @app.exception_handler(NortPoleError)
    async def _handle_evolvxsi_error(
        request: Request,  # noqa: ARG001
        exc: NortPoleError,
    ) -> JSONResponse:
        log_evolvxsi_error(exc)
        return evolvxsi_error_to_json_response(exc)
