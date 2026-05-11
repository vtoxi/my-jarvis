from __future__ import annotations

import time
from typing import Any


def collect_performance_metrics(*, metrics_enabled: bool) -> dict[str, Any]:
    if not metrics_enabled:
        return {"available": False, "error": "JARVIS_SYSTEM_METRICS_ENABLED=false"}
    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:
        return {"available": False, "error": "psutil not installed"}
    try:
        cpu = float(psutil.cpu_percent(interval=0.1))
        vm = psutil.virtual_memory()
        return {
            "available": True,
            "cpu_percent": round(cpu, 2),
            "ram_used_mb": round(vm.used / (1024 * 1024), 1),
            "ram_total_mb": round(vm.total / (1024 * 1024), 1),
            "collected_at_unix": time.time(),
        }
    except Exception as e:  # noqa: BLE001
        return {"available": False, "error": str(e)}
