from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "requestId": request_id or f"req_{uuid4().hex}",
            }
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    mapping = {
        400: ("bad_request", "Request parameters are invalid."),
        401: ("unauthorized", "Authentication is required."),
        403: ("forbidden", "You do not have access to this resource."),
        404: ("not_found", "Resource not found."),
        422: ("validation_error", "Validation failed."),
        500: ("internal_server_error", "An unexpected error occurred."),
    }
    code, default_message = mapping.get(exc.status_code, ("internal_server_error", "An unexpected error occurred."))
    details = exc.detail if isinstance(exc.detail, list) else []
    return build_error_response(
        status_code=exc.status_code,
        code=code,
        message=default_message,
        details=details,
        request_id=getattr(request.state, "request_id", None),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for err in exc.errors():
        location = [str(part) for part in err["loc"] if part != "body"]
        details.append({"field": ".".join(location) if location else "body", "issue": err["msg"]})
    return build_error_response(
        status_code=422,
        code="validation_error",
        message="Validation failed.",
        details=details,
        request_id=getattr(request.state, "request_id", None),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return build_error_response(
        status_code=500,
        code="internal_server_error",
        message="An unexpected error occurred.",
        request_id=getattr(request.state, "request_id", None),
    )
