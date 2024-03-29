import os, sys
if 'COV_CORE_SOURCE' in os.environ:
 try:
  from pytest_cov.embed import init
  init()
 except ImportError as exc:
  sys.stderr.write(
   "Failed to setup coverage."
   "Sources: {[COV_CORE_SOURCE]!r}"
   "Config: {[COV_CORE_CONFIG]!r}"
   "Exception: {!r}\n".format(os.environ, exc))
