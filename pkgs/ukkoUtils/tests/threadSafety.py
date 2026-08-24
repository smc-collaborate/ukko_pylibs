"""
Concurrency stress test for ThreadSafe (threadSafety.py).

Goals:
  1. Prove the lock actually serializes access under heavy contention
     (catches lost-update race conditions).
  2. Prove RLock reentrancy works within one thread, and across many
     threads reentering at once (catches self-deadlock bugs).
  3. Prove the lock is released even when the protected block raises
     (catches "exception leaves lock held" bugs).
  4. Demonstrate that a genuine deadlock (the classic two-lock AB/BA
     ordering problem) is detected by this harness rather than hanging
     the test run forever. This is a sanity check on the harness itself,
     not a defect in ThreadSafe -- no single-lock wrapper can stop a
     caller from creating a multi-lock deadlock; the point is to prove
     that IF ThreadSafe ever did deadlock, this suite would catch it
     instead of hanging CI.

Every worker thread is joined with a timeout instead of joined forever.
If a join times out we treat it as a suspected deadlock, dump every
thread's stack with faulthandler, and fail that test.
"""

import queue
import sys
import threading
import time
import traceback

from ..src.threadSafety import ThreadSafe

FAILURES = []


def join_all(threads, timeout, label):
    """Join every thread against one overall deadline.

    Returns the list of threads still alive when the deadline passed.
    Empty list == everyone finished cleanly. Non-empty == suspected
    deadlock (or just something slower than expected).
    """
    deadline = time.monotonic() + timeout
    stuck = []
    for t in threads:
        remaining = max(0.0, deadline - time.monotonic())
        t.join(remaining)
        if t.is_alive():
            stuck.append(t)
    if stuck:
        print(
            f"[{label}] TIMED OUT waiting for {len(stuck)} thread(s) -- "
            f"suspected deadlock. Stack dump:\n{_dump_all_thread_stacks()}"
        )
    return stuck


def _dump_all_thread_stacks():
    """Pure-Python stand-in for faulthandler.dump_traceback that works with
    any output (faulthandler itself requires a real fileno, which print
    capture / non-file streams don't have)."""
    id_to_name = {t.ident: t.name for t in threading.enumerate()}
    frames = sys._current_frames()
    chunks = []
    for ident, frame in frames.items():
        name = id_to_name.get(ident, "unknown")
        chunks.append(
            f"--- Thread {name} (id {ident}) ---\n"
            + "".join(traceback.format_stack(frame))
        )
    return "\n".join(chunks)


def report(label, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{label}] {status}{': ' + detail if detail else ''}")
    if not ok:
        FAILURES.append(label)


# ---------------------------------------------------------------------------
# 1. Lost-update race condition under heavy contention
# ---------------------------------------------------------------------------
def test_race_condition_counter():
    label = "race_condition_counter"
    locked = ThreadSafe({"count": 0})
    errors = queue.Queue()

    n_threads = 40
    n_iters = 2000
    barrier = threading.Barrier(n_threads)

    def worker():
        try:
            barrier.wait()  # start everyone at once to maximize contention
            for _ in range(n_iters):
                with locked as d:
                    # Split the read and the write with a scheduler hint,
                    # so a lock that isn't really held would show up as
                    # lost updates almost immediately.
                    val = d["count"]
                    time.sleep(0)
                    d["count"] = val + 1
        except Exception as e:  # pragma: no cover
            errors.put(e)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    start = time.monotonic()
    for t in threads:
        t.start()

    stuck = join_all(threads, timeout=30, label=label)
    elapsed = time.monotonic() - start
    if stuck:
        report(label, False, "threads hung (deadlock)")
        return

    if not errors.empty():
        report(label, False, f"worker raised: {errors.get()}")
        return

    with locked as d:
        final = d["count"]
    expected = n_threads * n_iters
    report(
        label,
        final == expected,
        f"{final}/{expected} increments in {elapsed:.2f}s"
        + ("" if final == expected else " -- LOST UPDATES DETECTED"),
    )


# ---------------------------------------------------------------------------
# 2. Reentrancy: nested `with` in the same thread must not self-deadlock
# ---------------------------------------------------------------------------
def test_reentrancy_same_thread():
    label = "reentrancy_same_thread"
    locked = ThreadSafe([])

    def recurse(depth):
        if depth == 0:
            return
        with locked as lst:
            lst.append(depth)
            recurse(depth - 1)

    done = queue.Queue()

    def worker():
        try:
            recurse(50)
            done.put(True)
        except Exception as e:
            done.put(e)

    t = threading.Thread(target=worker)
    t.start()
    stuck = join_all([t], timeout=10, label=label)
    if stuck:
        report(label, False, "nested with-blocks deadlocked")
        return
    result = done.get()
    report(label, result is True, "" if result is True else f"raised {result}")


# ---------------------------------------------------------------------------
# 3. Many threads reentering concurrently (each thread nests 3 deep)
# ---------------------------------------------------------------------------
def test_reentrancy_many_threads():
    label = "reentrancy_many_threads"
    locked = ThreadSafe({"depth_seen": 0})
    errors = queue.Queue()
    n_threads = 30

    def worker():
        try:
            with locked as d:
                with locked as d2:
                    with locked as d3:
                        assert d is d2 is d3
                        d3["depth_seen"] += 1
        except Exception as e:
            errors.put(e)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    stuck = join_all(threads, timeout=15, label=label)
    if stuck:
        report(label, False, "concurrent nested with-blocks deadlocked")
        return
    if not errors.empty():
        report(label, False, f"worker raised: {errors.get()}")
        return
    with locked as d:
        final = d["depth_seen"]
    report(label, final == n_threads, f"expected {n_threads}, got {final}")


# ---------------------------------------------------------------------------
# 4. Exception inside the `with` block must not leave the lock held
# ---------------------------------------------------------------------------
def test_exception_releases_lock():
    label = "exception_releases_lock"
    locked = ThreadSafe([1, 2, 3])

    def bad_worker():
        with locked as lst:
            lst.append("about to blow up")
            raise ValueError("boom")

    t = threading.Thread(target=bad_worker)
    t.start()
    t.join(timeout=5)
    if t.is_alive():
        report(label, False, "thread that raised never finished")
        return

    # If the lock leaked, this second acquire (from a *different* thread)
    # will hang forever -- catch that with a timeout instead of blocking.
    acquired = queue.Queue()

    def check_worker():
        with locked as lst:
            acquired.put(len(lst))

    t2 = threading.Thread(target=check_worker)
    t2.start()
    t2.join(timeout=5)
    if t2.is_alive():
        report(label, False, "lock still held after exception -- leaked")
        return
    ok = (not acquired.empty()) and acquired.get() == 4
    report(label, ok, "" if ok else "lock released but state looks wrong")


# ---------------------------------------------------------------------------
# 5. Harness sanity check: a genuine two-lock AB/BA deadlock IS caught
# ---------------------------------------------------------------------------
def test_harness_detects_real_deadlock():
    label = "harness_detects_real_deadlock"
    lock_a = ThreadSafe("A")
    lock_b = ThreadSafe("B")
    ready = threading.Barrier(2)

    def thread1():
        with lock_a:
            ready.wait()
            time.sleep(0.2)
            with lock_b:
                pass

    def thread2():
        with lock_b:
            ready.wait()
            time.sleep(0.2)
            with lock_a:
                pass

    # daemon=True: if this really deadlocks, the process must still be able
    # to exit cleanly -- these threads should not hang the whole test run.
    t1 = threading.Thread(target=thread1, daemon=True)
    t2 = threading.Thread(target=thread2, daemon=True)
    t1.start()
    t2.start()
    stuck = join_all([t1, t2], timeout=3, label=label)
    # We WANT this to deadlock -- that's what proves the harness's timeout
    # + stack dump actually catches a real deadlock instead of hanging.
    report(
        label,
        len(stuck) > 0,
        (
            "correctly detected the AB/BA deadlock via timeout"
            if stuck
            else "expected a deadlock but threads finished cleanly"
        ),
    )


def main():
    tests = [
        test_race_condition_counter,
        test_reentrancy_same_thread,
        test_reentrancy_many_threads,
        test_exception_releases_lock,
        test_harness_detects_real_deadlock,
    ]
    for test in tests:
        test()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} test(s) failed: {FAILURES}")
        sys.exit(1)
    else:
        print("All stress tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
