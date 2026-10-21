"""
n64-docs build [--fast]          : build the HTML into _build/html
n64-docs serve [--full] [--port] : build, serve on localhost and rebuild on changes
"""
import argparse
import functools
import http.server
import os
import runpy
import shutil
import subprocess
import sys
import threading
import time

from . import ENV_FAST, ENV_SKIP_DOXYGEN

_IGNORED_DIRS = {"_build", ".venv", "__pycache__", ".git"}


def _sphinx(env_extra=None):
    env = dict(os.environ, **(env_extra or {}))
    cmd = [sys.executable, "-m", "sphinx", "-M", "html", ".", "_build"]
    return subprocess.run(cmd, env=env).returncode


def _snapshot(roots, skip):
    files = {}
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS
                           and os.path.abspath(os.path.join(dirpath, d)) not in skip]
            for f in filenames:
                p = os.path.abspath(os.path.join(dirpath, f))
                try:
                    files[p] = os.stat(p).st_mtime_ns
                except OSError:
                    pass
    return files


def _wait_for_change(roots, skip, prev):
    while True:
        time.sleep(0.5)
        cur = _snapshot(roots, skip)
        if cur != prev:
            changed = {p for p in cur.keys() | prev.keys() if cur.get(p) != prev.get(p)}
            return cur, changed


def _serve_http(port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=os.path.abspath("_build/html"))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("localhost", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def cmd_build(args):
    if args.fast:
        os.environ[ENV_FAST] = "1"
    return _sphinx()


def cmd_serve(args):
    fast = not args.full
    if fast:
        os.environ[ENV_FAST] = "1"
        print("=" * 64)
        print(" FAST mode: C++ API docs are skipped")
        print("=" * 64)
    else:
        os.environ.pop(ENV_FAST, None)

    api = runpy.run_path("conf.py").get("n64_docs_cpp_api")
    api_inputs = [os.path.abspath(p) for p in api["input"]] if api else []
    # Generated API pages are rewritten on every full build; watching them
    # would cause an endless rebuild loop.
    skip = {os.path.abspath(api["out_dir"])} if api else set()
    roots = ["."] + api_inputs

    shutil.rmtree("_build/html", ignore_errors=True)
    os.makedirs("_build/html")
    _serve_http(args.port)
    print("Server started at http://localhost:{0}".format(args.port))

    _sphinx()
    print("Watching for changes...")
    files = _snapshot(roots, skip)
    while True:
        files, changed = _wait_for_change(roots, skip, files)
        print("Change detected: " + ", ".join(sorted(os.path.relpath(p) for p in changed)))

        if fast:
            shutil.rmtree("_build/html", ignore_errors=True)
            _sphinx()
        elif any(p.startswith(tuple(api_inputs)) or p.endswith("conf.py") for p in changed):
            # The regenerated API pages don't survive Sphinx incremental builds
            # (stale symbols carry over in the cached doctrees and members get
            # silently dropped), so clear the doctrees to force a full rebuild.
            print("  -> C++ API input changed: full rebuild (Doxygen + _apigen).")
            shutil.rmtree("_build/html", ignore_errors=True)
            shutil.rmtree("_build/doctrees", ignore_errors=True)
            _sphinx()
        else:
            # Reuse the already-built C++ API and only rebuild what changed.
            print("  -> non-API change: quick refresh (reusing C++ API).")
            _sphinx({ENV_SKIP_DOXYGEN: "1"})
        print("Build complete.")


def main():
    parser = argparse.ArgumentParser(prog="n64-docs")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build", help="build the HTML docs into _build/html")
    p.add_argument("--fast", action="store_true", help="skip the C++ API")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("serve", help="build, serve and rebuild on changes")
    p.add_argument("--full", "--api", action="store_true", help="include the C++ API (slower)")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    # keep our messages in order with sphinx' output when piped
    sys.stdout.reconfigure(line_buffering=True)
    if not os.path.exists("conf.py"):
        parser.error("no conf.py in the current directory")
    try:
        sys.exit(args.func(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
