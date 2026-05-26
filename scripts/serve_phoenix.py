"""Start a local self-hosted Phoenix server on http://localhost:6006.

Run this in a separate terminal before the spike or any agent. It blocks until
you stop it (Ctrl+C). The Phoenix UI is reachable in a browser at the same URL.
"""
import sys

# Force UTF-8 stdout/stderr — Phoenix prints Unicode characters that fail on
# Windows' default cp1252 codec.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import phoenix as px


def main() -> None:
    print("Starting Phoenix locally at http://localhost:6006 ...")
    print("Open that URL in a browser to see traces as they arrive.")
    print("Ctrl+C to stop.")
    session = px.launch_app(host="0.0.0.0", port=6006)
    try:
        session.wait()
    except KeyboardInterrupt:
        print("\nStopping Phoenix.")


if __name__ == "__main__":
    main()
