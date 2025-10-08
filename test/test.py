#!/usr/bin/env python3
import argparse
import os
import random
import signal
import sys
import time
from multiprocessing import Process
from statistics import mean

# Ensure we can import local_comm.py from the same directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import local_comm as lc  # noqa


def _service_proc(service_name: str):
    """Server process: echo bytes back (minimal processing)."""
    def callback(data_in: bytes) -> bytes:
        # Do minimal work to simulate a hop; you can add real processing here.
        return data_in

    ep = lc.EndPoint()
    ep.create_service(service_name, callback)
    try:
        ep.spin()
    except KeyboardInterrupt:
        pass


def _percentiles(samples, ps=(50, 95, 99)):
    if not samples:
        return {p: float("nan") for p in ps}
    xs = sorted(samples)
    n = len(xs)
    out = {}
    for p in ps:
        k = max(0, min(n - 1, int(round((p / 100.0) * (n - 1)))))
        out[p] = xs[k]
    return out


def human_mb(nbytes):
    return nbytes / (1024.0 * 1024.0)


def run_bench(service_name: str, sizes, iters: int, file_path: str = None, connect_timeout: float = 2.0):
    # Start server in a separate process
    srv = Process(target=_service_proc, args=(service_name,), daemon=True)
    srv.start()

    # Give the server a moment to create the socket
    time.sleep(0.15)

    ep = lc.EndPoint()
    client = ep.create_service_caller(service_name)

    # Warm-up a couple calls to avoid cold-start effects
    for _ in range(3):
        payload = os.urandom(1024)
        client.call(payload, timeout=5.0)

    results = []

    if file_path:
        data = open(file_path, "rb").read()
        print(f"\n== File benchmark: {file_path} ({human_mb(len(data)):.2f} MiB)")
        lat = []
        for _ in range(iters):
            t0 = time.perf_counter()
            _ = client.call(data, timeout=10.0)
            lat.append(time.perf_counter() - t0)
        pct = _percentiles(lat)
        size_mb = human_mb(len(data))
        print(f"  iters={iters} | size={size_mb:.2f} MiB | avg={mean(lat)*1000:.2f} ms "
              f"| p50={pct[50]*1000:.2f} ms | p95={pct[95]*1000:.2f} ms | p99={pct[99]*1000:.2f} ms "
              f"| thrpt≈{(size_mb/mean(lat)):.2f} MiB/s")

    print("\n== Synthetic sizes (RGB bytes):")
    for (w, h, c) in sizes:
        nbytes = w * h * c
        lat = []
        # Reuse the same payload each iteration to avoid generating cost in the loop
        payload = os.urandom(nbytes)
        print(f"  {w}x{h}x{c}  ({human_mb(nbytes):.2f} MiB), iters={iters} ... ", end="", flush=True)
        for _ in range(iters):
            t0 = time.perf_counter()
            _ = client.call(payload, timeout=10.0)
            lat.append(time.perf_counter() - t0)
        pct = _percentiles(lat)
        size_mb = human_mb(nbytes)
        print(f"avg={mean(lat)*1000:.2f} ms | p50={pct[50]*1000:.2f} ms | "
              f"p95={pct[95]*1000:.2f} ms | p99={pct[99]*1000:.2f} ms | "
              f"thrpt≈{(size_mb/mean(lat)):.2f} MiB/s")

    # Cleanup server
    if srv.is_alive():
        # Terminate the process; EndPoint.spin() will clean sockets on exit
        srv.terminate()
        try:
            srv.join(timeout=1.0)
        except Exception:
            pass


def parse_size(arg):
    # format: WIDTHxHEIGHTxCHANNELS (e.g., 640x480x3)
    try:
        w, h, c = arg.lower().split("x")
        return (int(w), int(h), int(c))
    except Exception:
        raise argparse.ArgumentTypeError("size must be like 640x480x3")


def main():
    parser = argparse.ArgumentParser(description="local_comm speed test (Linux, stdlib-only)")
    parser.add_argument("--service", default=f"local_comm_bench_{random.randint(1, 1_000_000)}",
                        help="service name to use (defaults to random)")
    parser.add_argument("--iters", type=int, default=200, help="iterations per size")
    parser.add_argument("--sizes", nargs="*", type=parse_size,
                        default=[(640, 480, 3), (1280, 720, 3), (1920, 1080, 3)],
                        help="sizes like 640x480x3 1280x720x3")
    parser.add_argument("--file", help="optional: benchmark this file's bytes (e.g., PNG/JPEG)")
    args = parser.parse_args()

    print(f"Service: {args.service}")
    print(f"Iters:   {args.iters}")
    print(f"Sizes:   {', '.join(f'{w}x{h}x{c}' for (w,h,c) in args.sizes)}")
    if args.file:
        print(f"File:    {args.file}")

    run_bench(args.service, args.sizes, args.iters, file_path=args.file)


if __name__ == "__main__":
    main()
