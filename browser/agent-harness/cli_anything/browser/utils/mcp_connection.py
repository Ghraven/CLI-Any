"""A session-owned MCP connection that survives synchronous wrapper calls."""

import asyncio
import threading
from concurrent.futures import Future, InvalidStateError
from typing import Any, Awaitable, Callable

from mcp import ClientSession, StdioServerParameters


def _failure_message(error: BaseException) -> str:
    """Expose underlying errors wrapped by AnyIO task groups."""
    children = getattr(error, "exceptions", None)
    if children:
        return "; ".join(_failure_message(child) for child in children)
    return str(error) or type(error).__name__


class PersistentConnection:
    """Own the transport and its context managers in one long-lived task.

    Operations are serialized on a private event loop. Entering and leaving
    the MCP contexts in the same task preserves AnyIO cancel-scope ownership.
    Failed operations are never replayed automatically.
    """

    def __init__(
        self,
        params: StdioServerParameters,
        transport_factory: Callable,
        client_factory: Callable,
        timeout: float = 60.0,
    ) -> None:
        self._params = params
        self._transport_factory = transport_factory
        self._client_factory = client_factory
        self._timeout = timeout
        self._lock = threading.Lock()
        self._closed = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        self._queue: asyncio.Queue | None = None
        self._ready: Future = Future()
        self._pending: set[Future] = set()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    async def run(self, operation: Callable[[ClientSession], Awaitable[Any]]) -> Any:
        """Run an operation on the owning loop, connecting lazily."""
        with self._lock:
            if self._closed:
                raise RuntimeError("DOMShell connection is closed")
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._worker,
                    name="domshell-session",
                    daemon=True,
                )
                self._thread.start()

        try:
            await asyncio.shield(asyncio.wrap_future(self._ready))
            result: Future = Future()
            with self._lock:
                if self._closed:
                    raise RuntimeError("DOMShell connection is closed")
                self._pending.add(result)
                assert self._loop is not None and self._queue is not None
                self._loop.call_soon_threadsafe(
                    self._queue.put_nowait,
                    (operation, result),
                )
            return await asyncio.wrap_future(result)
        except asyncio.CancelledError:
            # A cancelled browser action must not continue on an orphaned
            # connection after its caller has left.
            await asyncio.to_thread(self.close)
            raise

    def close(self) -> None:
        """Cancel outstanding work and release the proxy process and thread."""
        with self._lock:
            was_closed = self._closed
            self._closed = True
            thread = self._thread
            if not was_closed and self._loop is not None and self._task is not None:
                try:
                    self._loop.call_soon_threadsafe(self._task.cancel)
                except RuntimeError:
                    # The worker may already have closed its event loop.
                    pass
        if thread is not None:
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("Timed out closing the DOMShell connection")

    def _worker(self) -> None:
        error: BaseException = RuntimeError("DOMShell connection is closed")
        try:
            asyncio.run(self._serve())
        except asyncio.CancelledError:
            pass
        except BaseException as exc:
            error = RuntimeError(_failure_message(exc))
            error.__cause__ = exc
        finally:
            with self._lock:
                self._closed = True
                self._loop = None
                self._task = None
                pending = list(self._pending)
                self._pending.clear()
            # Publish failure only after the transport has finished cleanup,
            # so a subsequent command can safely establish a new connection.
            for future in [self._ready, *pending]:
                try:
                    future.set_exception(error)
                except InvalidStateError:
                    pass

    async def _serve(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._loop = asyncio.get_running_loop()
            self._task = asyncio.current_task()
            self._queue = asyncio.Queue()

        async with self._transport_factory(self._params) as (read, write):
            async with self._client_factory(read, write) as client:
                await self._with_timeout(client.initialize(), "initialization")
                self._ready.set_result(None)
                while True:
                    operation, result = await self._queue.get()
                    if not result.set_running_or_notify_cancel():
                        with self._lock:
                            self._pending.discard(result)
                        continue
                    value = await self._with_timeout(operation(client), "request")
                    result.set_result(value)
                    with self._lock:
                        self._pending.discard(result)

    async def _with_timeout(self, operation: Awaitable[Any], phase: str) -> Any:
        try:
            return await asyncio.wait_for(operation, self._timeout)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"DOMShell {phase} timed out after {self._timeout:g} seconds"
            ) from exc
