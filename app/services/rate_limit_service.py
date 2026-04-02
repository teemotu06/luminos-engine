import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple


DEFAULT_RATE_LIMIT_SPECS = [
    ("/lesson/tts/prompt", 5, 60),
    ("/admin/", 10, 60),
    ("/lesson/", 180, 60),
]


class InMemoryRateLimiter:
    def __init__(self, specs: list[tuple[str, int, int]]):
        self._specs = sorted(specs, key=lambda item: len(item[0]), reverse=True)
        self._lock = threading.Lock()
        self._requests: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)

    def limit_for(self, path: str) -> Optional[Tuple[int, int]]:
        for prefix, limit, window_seconds in self._specs:
            if path.startswith(prefix):
                return limit, window_seconds
        return None

    def allow(self, path: str, key: str, now: Optional[float] = None) -> Tuple[bool, Optional[int], Optional[int]]:
        matched = self.limit_for(path)
        if matched is None:
            return True, None, None

        limit, window_seconds = matched
        current = time.time() if now is None else now
        bucket_key = (path, key)

        with self._lock:
            bucket = self._requests[bucket_key]
            cutoff = current - window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(int(bucket[0] + window_seconds - current), 1)
                return False, retry_after, limit
            bucket.append(current)
            return True, None, limit
