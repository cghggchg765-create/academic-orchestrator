#!/usr/bin/env python3
"""容错工具：重试（指数退避）与自适应并发（限流降级）。

纯标准库，供宿主/脚本在调用子代理、批量任务时使用：

- retry_with_backoff：单任务失败后指数退避重试（如子代理调用失败自动重新调起）；
- adaptive_parallel：高并发批量执行，检测限流错误后自动降级并发（多→减半→串行），
  每项失败可先重试；耗尽/无法再降级时归入 failures 并如实报告。

用法示例见文件底部 __main__（自检）。
"""
from __future__ import annotations

import concurrent.futures as _cf
import time
from typing import Any, Callable, Optional, Sequence, Tuple

DEFAULT_RATE_LIMIT_EXC: tuple = (Exception,)


class EmptyResultError(ValueError):
    """Raised when a producer exhausts retries without a usable result."""

    def __init__(self, message: str, attempts: int = 0, last_result: Any = None,
                 validation_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_result = last_result
        self.validation_error = validation_error


def _is_empty_result(value: Any) -> bool:
    """Recognize empty or whitespace-only producer output."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (bytes, bytearray)):
        return not value.strip()
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return len(value) == 0
    return False


def retry_with_nonempty(
    func: Callable[[], Any],
    attempts: int = 2,
    validator: Optional[Callable[[Any], Any]] = None,
    base_delay: float = 0.0,
    factor: float = 2.0,
    on_retry: Optional[Callable[[int, int, float, Exception], None]] = None,
    raise_on_empty: bool = False,
) -> Any:
    """Retry until ``func`` returns a non-empty, validator-approved value.

    Empty/whitespace output and validator failures are treated as retryable.
    The default exhaustion behavior is a structured ``EMPTY_RETURN`` object so
    callers can persist a machine-readable blocked result.  Set
    ``raise_on_empty`` to receive :class:`EmptyResultError` instead.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    last_result: Any = None
    last_error: Optional[Exception] = None
    delay = max(0.0, float(base_delay))
    for attempt in range(1, attempts + 1):
        try:
            candidate = func()
            last_result = candidate
            if _is_empty_result(candidate):
                last_error = EmptyResultError("producer returned an empty result", attempt, candidate)
            elif validator is not None:
                try:
                    valid = validator(candidate)
                    if valid is False:
                        raise EmptyResultError("result validator rejected producer output", attempt, candidate)
                except EmptyResultError:
                    raise
                except Exception as exc:  # validator failures are retryable
                    raise EmptyResultError("result validator failed: {}".format(exc), attempt, candidate, exc)
                return candidate
            else:
                return candidate
        except EmptyResultError as exc:
            last_error = exc
        except Exception as exc:  # producer failures are retryable here
            last_error = exc
        if attempt >= attempts:
            break
        if on_retry is not None:
            on_retry(attempt, attempts, delay, last_error or EmptyResultError("empty result", attempt, last_result))
        if delay:
            time.sleep(delay)
            delay *= factor
    message = "producer returned no usable result after {} attempt(s)".format(attempts)
    if last_error is not None:
        message += ": {}".format(last_error)
    if raise_on_empty:
        raise EmptyResultError(message, attempts, last_result, last_error)
    return {
        "status": "EMPTY_RETURN",
        "attempts": attempts,
        "reason": str(last_error or "empty result"),
        "last_result": last_result,
    }


def retry_with_backoff(
    func: Callable[[], Any],
    attempts: int = 3,
    base_delay: float = 1.0,
    factor: float = 2.0,
    exceptions: tuple = DEFAULT_RATE_LIMIT_EXC,
    on_retry: Callable[[int, int, float, Exception], None] | None = None,
) -> Any:
    """执行 func，失败按指数退避重试（base_delay * factor**attempt），耗尽后抛最后一次异常。

    典型场景：子代理调用失败/超时/被限流 → 自动重新调起。
    """
    delay = base_delay
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except exceptions as exc:  # noqa: BLE001
            last = exc
            if attempt >= attempts:
                break
            if on_retry is not None:
                on_retry(attempt, attempts, delay, exc)
            time.sleep(delay)
            delay *= factor
    assert last is not None
    raise last


def adaptive_parallel(
    items: Sequence[Any],
    worker: Callable[[Any], Any],
    max_workers: int = 8,
    min_workers: int = 1,
    rate_limit_exc: tuple = DEFAULT_RATE_LIMIT_EXC,
    attempts_per_item: int = 2,
    base_delay: float = 1.0,
    factor: float = 2.0,
    on_degrade: Callable[[int], None] | None = None,
    on_retry: Callable[[Any, int, int, Exception], None] | None = None,
) -> dict[str, Any]:
    """高并发批量执行，限流自动降级。

    策略（容错阶梯）：
      1. 以 max_workers 并发执行；单项失败先按指数退避重试 attempts_per_item 次；
      2. 重试仍失败且属于限流错误（rate_limit_exc）→ 并发减半（workers //= 2），
         该项放回后续批次，直到 min_workers（串行）；
      3. 串行档仍限流/失败，或非限流错误 → 记入 failures；
      4. 有防护轮次上限，避免死循环。

    返回 {"results": {item: value}, "failures": {item: error}, "final_workers": n}。
    """
    results: dict[Any, Any] = {}
    failures: dict[Any, Exception] = {}
    pending: list[Any] = list(items)
    workers = max_workers
    rounds = 0
    max_rounds = max_workers * 4 + len(items)  # 防死循环
    while pending and workers >= min_workers and rounds < max_rounds:
        rounds += 1
        batch, pending = pending[:workers], pending[workers:]
        degraded = False
        with _cf.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(worker, item): item for item in batch}
            for future in _cf.as_completed(futures):
                item = futures[future]
                try:
                    results[item] = future.result()
                    continue
                except Exception as exc:  # noqa: BLE001
                    last = exc
                # 单项重试
                for attempt in range(1, attempts_per_item + 1):
                    if on_retry is not None:
                        on_retry(item, attempt, attempts_per_item, last)
                    time.sleep(base_delay * (factor ** (attempt - 1)))
                    try:
                        results[item] = worker(item)
                        last = None
                        break
                    except Exception as exc:  # noqa: BLE001
                        last = exc
                if last is None:
                    continue
                if isinstance(last, rate_limit_exc) and workers > min_workers:
                    degraded = True
                    pending.append(item)  # 降级后重试
                else:
                    failures[item] = last
        if degraded:
            workers = max(min_workers, workers // 2)
            if on_degrade is not None:
                on_degrade(workers)
    for item in pending:
        failures.setdefault(item, RuntimeError("rate limited or retries exhausted"))
    return {"results": results, "failures": failures, "final_workers": workers}


if __name__ == "__main__":
    # 自检：重试成功 / 重试耗尽 / 限流降级
    calls = {"n": 0}
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("simulated rate limit")
        return "ok"
    value = retry_with_backoff(flaky, attempts=4, base_delay=0.01)
    assert value == "ok" and calls["n"] == 3, calls
    print("retry_with_backoff: 第 3 次成功后返回 ok ✓")

    def always_fail():
        raise ValueError("boom")
    try:
        retry_with_backoff(always_fail, attempts=2, base_delay=0.01)
        raise AssertionError("应耗尽后抛错")
    except ValueError:
        print("retry_with_backoff: 耗尽后抛出最后异常 ✓")

    degraded_to = []
    def worker(item):
        if item >= 0:
            raise TimeoutError("rate limited")
        return item
    out = adaptive_parallel([0, 1, 2, 3], worker, max_workers=4, min_workers=1,
                            attempts_per_item=1, base_delay=0.01,
                            on_degrade=lambda w: degraded_to.append(w))
    assert out["final_workers"] == 1 and len(out["failures"]) == 4, out
    print(f"adaptive_parallel: 全部限流 → 降级至串行({degraded_to})，failures 如实记录 ✓")
    print("容错工具自检全部通过")
