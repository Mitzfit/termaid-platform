"""
logging_config.py — Termaid observability foundation (structured logging + tracing).

Author: Misfit
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Iterable, Mapping

_TRACE_ID: ContextVar[str] = ContextVar("termaid_trace_id", default="")

TRACE_REQUEST_HEADER = b"x-request-id"
TRACE_RESPONSE_HEADER = b"x-trace-id"


def new_trace_id() -> str:
    tid = uuid.uuid4().hex
    _TRACE_ID.set(tid)
    return tid


def get_trace_id() -> str:
    return _TRACE_ID.get()


_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "password", "passwd", "pwd", "secret", "token", "jwt",
    "accesstoken", "refreshtoken", "apikey", "authorization",
    "cookie", "setcookie", "xapikey", "sessionid", "clientsecret",
})

_REDACTED = "[REDACTED]"
_norm = re.compile(r"[^a-z0-9]")


def _is_sensitive_key(key: str) -> bool:
    return _norm.sub("", key.lower()) in _SENSITIVE_KEYS


_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)\b((?:access[_-]?|refresh[_-]?|api[_-]?|x[_-]?api[_-]?)?"
        r"(?:password|passwd|pwd|secret|token|jwt|key|authorization|cookie))"
        r"(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s&]+)"
    ),
    re.compile(r"(?i)\b(bearer)\s+[a-z0-9._~+/-]+=*"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\b"),
)


def scrub_text(message: str) -> str:
    try:
        out = _TEXT_PATTERNS[0].sub(
            lambda m: f"{
                m.group(1)}{
                m.group(2)}{_REDACTED}",
            message)
        out = _TEXT_PATTERNS[1].sub(lambda m: f"{m.group(1)} {_REDACTED}", out)
        return _TEXT_PATTERNS[2].sub(_REDACTED, out)
    except Exception:
        return _REDACTED


def scrub(value: Any, _depth: int = 0) -> Any:
    try:
        if _depth > 8:
            return _REDACTED
        if isinstance(value, Mapping):
            return {
                str(k): (
                    _REDACTED if _is_sensitive_key(
                        str(k)) else scrub(
                        v,
                        _depth +
                        1)) for k,
                v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [scrub(v, _depth + 1) for v in value]
        if isinstance(value, str):
            return scrub_text(value)
        return value
    except Exception:
        return _REDACTED


_RESERVED_RECORD_ATTRS: frozenset[str] = frozenset(
    logging.LogRecord("x", 0, "x", 0, "", (), None).__dict__
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        try:
            payload: dict[str, Any] = {
                "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
                + f".{int(record.msecs):03d}Z",
                "level": record.levelname,
                "logger": record.name,
                "message": scrub_text(record.getMessage()),
            }
            tid = get_trace_id()
            if tid:
                payload["trace_id"] = tid
            for key, val in record.__dict__.items():
                if key not in _RESERVED_RECORD_ATTRS and not key.startswith(
                        "_"):
                    payload[key] = _REDACTED if _is_sensitive_key(
                        key) else scrub(val)
            if record.exc_info:
                payload["exc_info"] = scrub_text(
                    self.formatException(record.exc_info))
            return json.dumps(payload, default=str, ensure_ascii=False)
        except Exception:
            return json.dumps(
                {"level": "ERROR", "logger": "termaid.logging",
                 "message": "log record could not be formatted"}
            )


class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except Exception:
            pass

    def handleError(self, record: logging.LogRecord) -> None:
        pass


_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.raiseExceptions = False

    handler = SafeStreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers[:] = [handler]

    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def _client_of(scope: Mapping[str, Any]) -> str:
    client = scope.get("client")
    return f"{client[0]}:{client[1]}" if client else ""


def _safe_target(scope: Mapping[str, Any]) -> str:
    path = scope.get("path", "")
    raw_q = scope.get("query_string", b"")
    if not raw_q:
        return path
    try:
        parts = []
        for pair in raw_q.decode("latin-1").split("&"):
            key, sep, _val = pair.partition("=")
            parts.append(
                f"{key}{sep}{_REDACTED}" if sep and _is_sensitive_key(key) else pair)
        return f"{path}?{'&'.join(parts)}"
    except Exception:
        return path


class TraceIDMiddleware:
    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app
        self.log = get_logger("termaid.access")

    @staticmethod
    def _inbound_trace(scope: Mapping[str, Any]) -> str:
        try:
            headers: Iterable[tuple[bytes, bytes]] = scope.get("headers") or ()
            for key, val in headers:
                if key.lower() == TRACE_REQUEST_HEADER:
                    tid = val.decode("latin-1").strip()[:64]
                    if tid and re.fullmatch(r"[A-Za-z0-9._-]+", tid):
                        return tid
        except Exception:
            pass
        return uuid.uuid4().hex

    async def __call__(
            self,
            scope: dict,
            receive: Callable,
            send: Callable) -> None:
        kind = scope.get("type")
        if kind not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        tid = self._inbound_trace(scope)
        token = _TRACE_ID.set(tid)
        start = time.perf_counter()
        status_holder = {"status": 0}

        async def send_traced(message: dict) -> None:
            if message.get("type") == "http.response.start":
                status_holder["status"] = message.get("status", 0)
                try:
                    headers = list(message.get("headers") or [])
                    headers.append(
                        (TRACE_RESPONSE_HEADER, tid.encode("latin-1")))
                    message = {**message, "headers": headers}
                except Exception:
                    pass
            await send(message)

        try:
            if kind == "websocket":
                self._safe_log("websocket session opened",
                               event="ws.open", target=_safe_target(scope),
                               client=_client_of(scope))
            await self.app(scope, receive, send_traced)
        except Exception:
            self._safe_log("unhandled application error", level=logging.ERROR,
                           event="request.error", target=_safe_target(scope),
                           exc=True)
            raise
        finally:
            dur = round((time.perf_counter() - start) * 1000, 2)
            if kind == "http":
                self._safe_log("request completed", event="http.request",
                               method=scope.get("method", ""),
                               target=_safe_target(scope),
                               status=status_holder["status"],
                               duration_ms=dur, client=_client_of(scope))
            else:
                self._safe_log("websocket session closed", event="ws.close",
                               target=_safe_target(scope), duration_ms=dur)
            _TRACE_ID.reset(token)

    def _safe_log(self, msg: str, level: int = logging.INFO,
                  exc: bool = False, **fields: Any) -> None:
        try:
            self.log.log(level, msg, extra=fields, exc_info=exc or None)
        except Exception:
            pass


def log_execution(logger_name: str = "termaid.engine",
                  event: str = "engine.execute") -> Callable:
    def decorator(func: Callable[..., dict]) -> Callable[..., dict]:
        log = get_logger(logger_name)

        def wrapper(*args: Any, **kwargs: Any) -> dict:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception:
                try:
                    log.error(
                        "command dispatch raised",
                        extra={
                            "event": event,
                            "ok": False,
                            "duration_ms": round(
                                (time.perf_counter() - start) * 1000,
                                2),
                        },
                        exc_info=True)
                except Exception:
                    pass
                raise
            try:
                log.info("command executed", extra={
                    "event": event,
                    "ok": bool(result.get("ok")) if isinstance(result, dict) else None,
                    "module_name": result.get("module") if isinstance(result, dict) else None,
                    "command": result.get("command") if isinstance(result, dict) else None,
                    "duration_ms": result.get("ms") if isinstance(result, dict)
                    else round((time.perf_counter() - start) * 1000, 2),
                })
            except Exception:
                pass
            return result

        wrapper.__name__ = getattr(func, "__name__", "execute")
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator
