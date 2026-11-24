"""Точка входа: uvicorn app.main:app"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.api import router
from app.keitaro import KeitaroError
from app.services import ServiceError

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

class FreshStaticFiles(StaticFiles):
    """Раздаёт файлы страницы так, чтобы браузер каждый раз сверялся с сервером.

    Без этого после обновления приложения браузер мог бы ещё долго брать старые скрипты из своего кэша:
    страница новая, а поведение прежнее. Сверка дешёвая: если файл не менялся, сервер отвечает «не изменился».
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app = FastAPI(title="Создаватор кампаний Keitaro", docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
app.include_router(router)
app.mount("/static", FreshStaticFiles(directory=STATIC_DIR), name="static")


def _page(name: str) -> FileResponse:
    return FileResponse(STATIC_DIR / name, headers={"Cache-Control": "no-cache"})


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Форма новой кампании."""
    return _page("index.html")


@app.get("/campaigns", include_in_schema=False)
def campaigns_page() -> FileResponse:
    """Список кампаний из Keitaro."""
    return _page("campaigns.html")


@app.get("/campaigns/{campaign_id}", include_in_schema=False)
def editor_page(campaign_id: int) -> FileResponse:
    """Редактор офферов одной кампании. Номер кампании страница берёт из адреса."""
    return _page("editor.html")


# Любая ошибка уходит на страницу в одном виде: {"detail": "текст для человека", "fields": {...}}.


@app.exception_handler(KeitaroError)
def keitaro_error(_: Request, error: KeitaroError) -> JSONResponse:
    return JSONResponse({"detail": error.message}, status_code=502)


@app.exception_handler(ServiceError)
def service_error(_: Request, error: ServiceError) -> JSONResponse:
    body: dict = {"detail": error.message}
    if error.field:
        body["fields"] = {error.field: error.message}
    return JSONResponse(body, status_code=error.status_code)


@app.exception_handler(RequestValidationError)
def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    fields: dict[str, str] = {}
    for item in error.errors():
        field = str(item["loc"][-1]) if item.get("loc") else "form"
        message = str(item.get("msg", ""))
        # Наши собственные проверки приходят с приставкой pydantic, остальное заменяем общей фразой.
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        else:
            message = "Поле заполнено неверно."
        fields.setdefault(field, message)
    return JSONResponse({"detail": "Проверьте поля формы.", "fields": fields}, status_code=422)


@app.exception_handler(OperationalError)
@app.exception_handler(ProgrammingError)
def database_error(_: Request, error: Exception) -> JSONResponse:
    log.error("Ошибка базы данных: %s", error)
    return JSONResponse(
        {"detail": "База данных не готова. Выполните команду «alembic upgrade head» и обновите страницу."},
        status_code=503,
    )
