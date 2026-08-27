#!/usr/bin/env python3
from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "research_supervisor.py"
VERSION = ROOT / "VERSION"

REPLACEMENT = '''# V325_WINDOWS_STREAM_COMPAT

def run_streamed(command, env, max_runtime, log_path, profile):
    """Portable subprocess streaming: thread+queue instead of selectors on pipes."""
    import queue as _queue
    import subprocess as _subprocess
    import threading as _threading
    import time as _time

    started = _time.monotonic()
    deadline = started + max(1, float(max_runtime))
    last_heartbeat = started
    q = _queue.Queue()
    eof = object()
    timed_out = False
    line_count = 0

    process = _subprocess.Popen(
        command,
        cwd=globals().get("ROOT"),
        env=env,
        stdout=_subprocess.PIPE,
        stderr=_subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def _reader():
        try:
            if process.stdout is not None:
                for line in iter(process.stdout.readline, ""):
                    q.put(line)
        finally:
            q.put(eof)

    reader = _threading.Thread(
        target=_reader,
        name="legacy-stdout-reader",
        daemon=True,
    )
    reader.start()

    try:
        parent = getattr(log_path, "parent", None)
        if parent is not None:
            parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    saw_eof = False
    with open(log_path, "a", encoding="utf-8", errors="replace") as log_handle:
        while True:
            now = _time.monotonic()
            if process.poll() is None and now >= deadline:
                timed_out = True
                print(
                    f"supervisor timeout: {profile} · {int(now-started)}s elapsed · terminating child",
                    flush=True,
                )
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass

            try:
                item = q.get(timeout=0.5)
                if item is eof:
                    saw_eof = True
                else:
                    line_count += 1
                    print(item, end="", flush=True)
                    log_handle.write(item)
                    log_handle.flush()
            except _queue.Empty:
                pass

            now = _time.monotonic()
            if process.poll() is None and now - last_heartbeat >= 30:
                print(
                    f"supervisor heartbeat: {profile} · {int(now-started)}s elapsed · process active",
                    flush=True,
                )
                last_heartbeat = now

            if process.poll() is not None and (saw_eof or not reader.is_alive()) and q.empty():
                break

        while True:
            try:
                item = q.get_nowait()
            except _queue.Empty:
                break
            if item is eof:
                continue
            line_count += 1
            print(item, end="", flush=True)
            log_handle.write(item)

    try:
        if process.stdout is not None:
            process.stdout.close()
    except Exception:
        pass

    rc = process.wait()
    elapsed = round(_time.monotonic() - started, 1)
    return rc, {
        "status": "timeout" if timed_out else ("success" if rc == 0 else "failed"),
        "timed_out": timed_out,
        "returncode": rc,
        "elapsed_seconds": elapsed,
        "lines": line_count,
        "stream_backend": "thread_queue",
    }

'''


def _find_function_span(text: str, function_name: str) -> tuple[int, int]:
    """Return character offsets for a function using Python's AST.

    Works with single-line or multiline signatures and decorators, unlike the
    previous regex-based installer.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise SystemExit(f"ERROR: scripts/research_supervisor.py no compila antes del parche: {exc}")

    node = None
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == function_name:
            node = item
            break
    if node is None or getattr(node, "end_lineno", None) is None:
        raise SystemExit(
            f"ERROR: Python AST no ha localizado {function_name}(...) en scripts/research_supervisor.py; no se modifica nada"
        )

    lines = text.splitlines(keepends=True)
    start_line = node.lineno
    if node.decorator_list:
        start_line = min(d.lineno for d in node.decorator_list)
    start = sum(len(line) for line in lines[: start_line - 1])
    end = sum(len(line) for line in lines[: node.end_lineno])
    return start, end


def patch_legacy(path: Path):
    if not path.exists():
        raise SystemExit(
            f"ERROR: no existe {path}; la v3.2.5 necesita el supervisor legacy de tu repositorio"
        )

    text = path.read_text(encoding="utf-8")
    if "V325_WINDOWS_STREAM_COMPAT" in text:
        print("legacy stream ya estaba parcheado")
        return

    start, end = _find_function_span(text, "run_streamed")
    backup = path.with_name(
        path.name + ".v324-" + datetime.now().strftime("%Y%m%d%H%M%S") + ".bak"
    )
    shutil.copy2(path, backup)

    patched = text[:start] + REPLACEMENT + text[end:]
    try:
        compile(patched, str(path), "exec")
    except Exception as exc:
        raise SystemExit(
            f"ERROR: el parche generado no compila ({type(exc).__name__}: {exc}); se conserva el fichero original"
        )

    path.write_text(patched, encoding="utf-8")
    print(f"legacy stream parcheado; backup: {backup.name}")


def main():
    patch_legacy(TARGET)
    VERSION.write_text("3.2.5\n", encoding="utf-8")

    for p in [
        TARGET,
        ROOT / "scripts" / "research_supervisor_v31.py",
        ROOT / "scripts" / "research_supervisor_v32.py",
    ]:
        if not p.exists():
            raise SystemExit(f"ERROR: falta {p}")
        compile(p.read_text(encoding="utf-8"), str(p), "exec")

    print("v3.2.5 aplicada: compatibilidad Windows del legacy + estado de foundation visible.")
    print("Prueba corta: python scripts/research_supervisor.py --profile daily --max-runtime 60")
    print("Prueba integral después: python scripts/research_supervisor_v32.py --profile daily --max-runtime 720")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
