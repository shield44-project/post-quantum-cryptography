"""pqctl: control centre for the Post-Quantum AI Provenance Watermarking project.

One place to run every phase (0 to 6), watch live logs and read the results:

    python -m pqctl serve        # web dashboard on http://127.0.0.1:8765 (local only)
    python -m pqctl              # interactive terminal menu
    python -m pqctl --help       # every command

Standard library only: it runs the project's own scripts as subprocesses with the SAME Python that
started it, so start it from your venv (venv\\Scripts\\python -m pqctl serve on Windows).
"""

__version__ = "1.0.0"
