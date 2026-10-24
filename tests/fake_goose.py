"""Stand-in for the goose binary: echoes its argv and GOOSE_/EXTRA_ env as JSON."""

import json
import os
import sys
import time

print(
    json.dumps(
        {
            "argv": sys.argv[1:],
            "env": {
                k: v for k, v in os.environ.items() if k.startswith(("GOOSE_", "EXTRA_"))
            },
        }
    )
)
if stderr := os.environ.get("FAKE_STDERR"):
    print(stderr, file=sys.stderr)
if sleep := os.environ.get("FAKE_SLEEP"):
    time.sleep(float(sleep))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
