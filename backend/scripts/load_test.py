"""Load test script for VAAP API endpoints.

Usage:
    python scripts/load_test.py [--base-url URL] [--concurrency N] [--duration SECS]

Defaults: http://localhost:8000, 10 concurrent, 30 seconds.
No external dependencies required (uses stdlib only).
"""

import argparse
import json
import statistics
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field


@dataclass
class EndpointResult:
    path: str
    status: int
    latency_ms: float
    error: str = ""


@dataclass
class EndpointStats:
    path: str
    count: int = 0
    success: int = 0
    errors: int = 0
    latencies: list = field(default_factory=list)

    @property
    def p50(self) -> float:
        if not self.latencies:
            return 0
        s = sorted(self.latencies)
        return s[len(s) // 2]

    @property
    def p95(self) -> float:
        if not self.latencies:
            return 0
        s = sorted(self.latencies)
        return s[int(len(s) * 0.95)]

    @property
    def avg(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0


# Endpoints to test (method, path, description)
ENDPOINTS = [
    ("GET", "/api/v1/ads?page=1&page_size=20", "Ad listing"),
    ("GET", "/api/v1/ads/health/data-integrity", "Data integrity"),
    ("GET", "/api/v1/ads/connected-platforms", "Connected platforms"),
    ("GET", "/api/v1/rankings/dashboard-summary", "Dashboard summary"),
    ("GET", "/api/v1/rankings/score-distribution", "Score distribution"),
    ("GET", "/api/v1/rankings/timeout-policy", "Timeout policy"),
    ("GET", "/api/v1/media/crawl-history", "Crawl history"),
    ("GET", "/api/v1/media/gallery?page=1&page_size=20", "Media gallery"),
    ("GET", "/health", "Health check"),
]


def make_request(base_url: str, method: str, path: str) -> EndpointResult:
    url = f"{base_url}{path}"
    start = time.monotonic()
    try:
        req = urllib.request.Request(url, method=method)
        req.add_header("User-Agent", "VAAP-LoadTest/1.0")
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
            latency = (time.monotonic() - start) * 1000
            return EndpointResult(path=path, status=resp.status, latency_ms=latency)
    except urllib.error.HTTPError as e:
        latency = (time.monotonic() - start) * 1000
        return EndpointResult(path=path, status=e.code, latency_ms=latency, error=str(e))
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return EndpointResult(path=path, status=0, latency_ms=latency, error=str(e))


def run_load_test(base_url: str, concurrency: int, duration_secs: int):
    print(f"Load test: {base_url} | concurrency={concurrency} | duration={duration_secs}s")
    print(f"Endpoints: {len(ENDPOINTS)}")
    print("-" * 80)

    stats: dict[str, EndpointStats] = {}
    for _, path, _ in ENDPOINTS:
        stats[path] = EndpointStats(path=path)

    end_time = time.monotonic() + duration_secs
    total_requests = 0
    idx = 0

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {}
        while time.monotonic() < end_time:
            # Submit a batch
            for method, path, _ in ENDPOINTS:
                if time.monotonic() >= end_time:
                    break
                f = pool.submit(make_request, base_url, method, path)
                futures[f] = path

            # Collect completed
            done = []
            for f in list(futures):
                if f.done():
                    done.append(f)

            for f in done:
                path = futures.pop(f)
                try:
                    result = f.result(timeout=1)
                    s = stats[path]
                    s.count += 1
                    s.latencies.append(result.latency_ms)
                    if 200 <= result.status < 400:
                        s.success += 1
                    else:
                        s.errors += 1
                    total_requests += 1
                except Exception:
                    stats[path].errors += 1
                    total_requests += 1

            time.sleep(0.05)

        # Wait for remaining
        for f in as_completed(futures, timeout=30):
            path = futures[f]
            try:
                result = f.result(timeout=1)
                s = stats[path]
                s.count += 1
                s.latencies.append(result.latency_ms)
                if 200 <= result.status < 400:
                    s.success += 1
                else:
                    s.errors += 1
                total_requests += 1
            except Exception:
                stats[path].errors += 1

    # Print results
    print(f"\n{'Endpoint':<50} {'Count':>6} {'OK':>6} {'Err':>5} {'Avg':>8} {'P50':>8} {'P95':>8}")
    print("=" * 100)

    all_latencies = []
    total_ok = 0
    total_err = 0

    for _, path, desc in ENDPOINTS:
        s = stats[path]
        all_latencies.extend(s.latencies)
        total_ok += s.success
        total_err += s.errors
        print(f"{desc:<50} {s.count:>6} {s.success:>6} {s.errors:>5} {s.avg:>7.1f}ms {s.p50:>7.1f}ms {s.p95:>7.1f}ms")

    print("=" * 100)
    overall_p95 = sorted(all_latencies)[int(len(all_latencies) * 0.95)] if all_latencies else 0
    overall_avg = statistics.mean(all_latencies) if all_latencies else 0
    print(f"{'TOTAL':<50} {total_ok + total_err:>6} {total_ok:>6} {total_err:>5} {overall_avg:>7.1f}ms {'':>8} {overall_p95:>7.1f}ms")
    print(f"\nRPS: {total_requests / duration_secs:.1f}")

    # Budget check
    budget_pass = overall_p95 < 500
    print(f"\nPerformance budget (P95 < 500ms): {'PASS' if budget_pass else 'FAIL'} ({overall_p95:.1f}ms)")
    return 0 if budget_pass else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VAAP API Load Test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--duration", type=int, default=30)
    args = parser.parse_args()
    sys.exit(run_load_test(args.base_url, args.concurrency, args.duration))
