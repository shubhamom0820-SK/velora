"""`python -m app.workers`: the worker (`make worker`, and Fly's worker app)."""

import sys

from app.workers.main import main

sys.exit(main(sys.argv[1:]))
