from threading import Lock


class RuntimeMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = {}
        self._timers: dict[str, dict[str, float | int]] = {}

    def increment(self, name: str, delta: int = 1) -> None:
        with self._lock:
            self._counters[name] = int(self._counters.get(name, 0)) + delta

    def record_duration(self, name: str, duration_ms: float) -> None:
        with self._lock:
            bucket = self._timers.setdefault(
                name,
                {"calls": 0, "total_ms": 0.0, "max_ms": 0.0},
            )
            bucket["calls"] = int(bucket["calls"]) + 1
            bucket["total_ms"] = float(bucket["total_ms"]) + duration_ms
            bucket["max_ms"] = max(float(bucket["max_ms"]), duration_ms)

    def snapshot(self) -> dict:
        with self._lock:
            counters = {key: int(value) for key, value in self._counters.items()}
            timers: dict[str, dict[str, float | int]] = {}
            for key, bucket in self._timers.items():
                calls = int(bucket["calls"])
                total_ms = float(bucket["total_ms"])
                timers[key] = {
                    "calls": calls,
                    "total_ms": round(total_ms, 2),
                    "avg_ms": round(total_ms / calls, 2) if calls else 0.0,
                    "max_ms": round(float(bucket["max_ms"]), 2),
                }
            return {"counters": counters, "timers": timers}

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._timers.clear()


_runtime_metrics = RuntimeMetrics()


def increment_metric(name: str, delta: int = 1) -> None:
    _runtime_metrics.increment(name, delta)


def record_duration_metric(name: str, duration_ms: float) -> None:
    _runtime_metrics.record_duration(name, duration_ms)


def get_runtime_metrics_snapshot() -> dict:
    return _runtime_metrics.snapshot()


def reset_runtime_metrics() -> None:
    _runtime_metrics.reset()
