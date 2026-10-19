"""Cache em memória com expiração, usado para reduzir chamadas à RAWG.

Cada entrada tem um prazo de validade (`ttl`) e um prazo de "obsolescência
tolerada" (`stale_ttl`): depois que expira, o valor deixa de ser servido
normalmente, mas continua disponível como último recurso se a RAWG falhar.
"""
from __future__ import annotations

import copy
import threading
import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    def __init__(self, max_entries: int = 1000):
        self._max = max_entries
        self._data: OrderedDict[Any, tuple[float, float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any | None:
        """Valor ainda válido, ou None."""
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            fresh_until, _, value = item
            if now > fresh_until:
                return None
            self._data.move_to_end(key)
            return copy.deepcopy(value)

    def get_stale(self, key: Any) -> Any | None:
        """Valor mesmo expirado, desde que dentro da tolerância."""
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            _, stale_until, value = item
            if now > stale_until:
                del self._data[key]
                return None
            return copy.deepcopy(value)

    def set(self, key: Any, value: Any, ttl: float, stale_ttl: float | None = None) -> None:
        now = time.monotonic()
        stale_for = max(stale_ttl if stale_ttl is not None else ttl, ttl)
        with self._lock:
            self._data[key] = (now + ttl, now + stale_for, copy.deepcopy(value))
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
