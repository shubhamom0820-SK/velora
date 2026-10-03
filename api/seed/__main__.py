"""`make seed` runs this: `python -m seed`, from `api/`."""

import asyncio
import sys

from seed.run import main

sys.exit(asyncio.run(main()))
