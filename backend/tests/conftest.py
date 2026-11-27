"""Shared test setup: allow local repo paths.

Several API tests ingest repos built in tmp dirs. Production disables
local/file/ssh repo URLs (PRISM_ALLOW_LOCAL_REPOS=false); the unit tests in
test_git_parser.py cover the deny-by-default behavior explicitly with
allow_local=False, so the suite flips it on here for the integration paths.
"""

import os

os.environ.setdefault("PRISM_ALLOW_LOCAL_REPOS", "true")
# The suite ingests a fresh local repo per API test from one TestClient
# "IP"; the production ingest cap (20/hour) would 429 later tests.
os.environ.setdefault("PRISM_RATE_LIMIT_INGEST_PER_HOUR", "1000")
