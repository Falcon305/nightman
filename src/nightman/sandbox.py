from __future__ import annotations

import contextlib
import multiprocessing as mp
import signal
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from types import ModuleType
from typing import Any

resource: ModuleType | None
try:
    import resource as _resource

    resource = _resource
except ImportError:
    resource = None


@dataclass
class SandboxOutcome:
    status: str
    value: Any = None
    exc_type: str | None = None
    exc_msg: str = ""
    exitcode: int | None = None
    signal: int | None = None


def _apply_limits(cpu_s: int, mem_mb: int) -> None:
    if resource is None:
        return
    with contextlib.suppress(ValueError, OSError):
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 1))
    if mem_mb:
        byte_cap = mem_mb * 1024 * 1024
        with contextlib.suppress(ValueError, OSError):
            resource.setrlimit(resource.RLIMIT_AS, (byte_cap, byte_cap))
    with contextlib.suppress(ValueError, OSError):
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _raise_cpu(signum: int, frame: Any) -> None:
    raise TimeoutError("cpu time limit exceeded")


def _child(conn: Any, func: Callable[..., Any], args: tuple, cpu_s: int, mem_mb: int) -> None:
    _apply_limits(cpu_s, mem_mb)
    with contextlib.suppress(ValueError, AttributeError, OSError):
        signal.signal(signal.SIGXCPU, _raise_cpu)
    try:
        conn.send(("ok", func(*args)))
    except BaseException as exc:
        with contextlib.suppress(Exception):
            conn.send(("raised", type(exc).__name__, str(exc)))
    finally:
        conn.close()


def run_in_subprocess(
    func: Callable[..., Any],
    args: tuple = (),
    *,
    wall_s: float = 15.0,
    cpu_s: int = 12,
    mem_mb: int = 2048,
) -> SandboxOutcome:
    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(child_conn, func, args, cpu_s, mem_mb))
    proc.start()
    child_conn.close()
    try:
        if parent_conn.poll(wall_s):
            try:
                payload = parent_conn.recv()
            except EOFError:
                payload = None
            proc.join(2)
            if payload and payload[0] == "ok":
                return SandboxOutcome("ok", value=payload[1], exitcode=proc.exitcode)
            if payload and payload[0] == "raised":
                return SandboxOutcome("raised", exc_type=payload[1], exc_msg=payload[2], exitcode=proc.exitcode)
            code = proc.exitcode
            return SandboxOutcome("crash", exitcode=code, signal=-code if code and code < 0 else None)
        return SandboxOutcome("timeout", exitcode=proc.exitcode)
    finally:
        parent_conn.close()
        if proc.is_alive():
            proc.terminate()
            proc.join(1)
        if proc.is_alive():
            proc.kill()
            proc.join()


@contextlib.contextmanager
def call_timeout(seconds: float) -> Iterator[None]:
    if not hasattr(signal, "SIGALRM") or seconds <= 0:
        yield
        return

    def _handler(signum: int, frame: Any) -> None:
        raise TimeoutError(f"call exceeded {seconds:g}s")

    previous = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
