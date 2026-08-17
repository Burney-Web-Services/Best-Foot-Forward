"""
BFF_ROLE environment variable.
  standard  — standalone user, no sharing behavior (default)
  primary   — primary machine: receives leads, does tailoring
  secondary — secondary machine: generates leads, exports to primary
"""

import os

BFF_ROLE = os.environ.get("BFF_ROLE", "standard")
