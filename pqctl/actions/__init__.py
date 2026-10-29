"""Small command-line actions behind the dashboard's interactive tools (X-ray, attack lab, tamper lab, signing lab).

Each action is a normal script run by the pqctl runner, so its output appears in the job log like any other step.
It reuses the project's own tested functions (verify/, embedding/, attacks/, crypto/) and finishes with one line

    PQCTL_JSON {...}

that the dashboard turns into pictures. Nothing here writes to keys/, release/ or runs/; lab models go to .pqctl/lab/.
"""
import json
import sys
import traceback


def emit(obj):
    print("PQCTL_JSON " + json.dumps(obj, separators=(",", ":")), flush=True)


def run_main(fn):
    """Run fn(); on any error print the reason, emit {"error": ...} and exit 1."""
    try:
        code = fn()
        sys.exit(code or 0)
    except SystemExit:
        raise
    except Exception as e:  # report every failure to the dashboard instead of a bare traceback
        traceback.print_exc()
        emit({"error": "%s: %s" % (type(e).__name__, e)})
        sys.exit(1)


def r(x, d=3):
    return round(float(x), d)
