"""Exact frozen v1094 predicate; explicit adapter export mapping is separate."""
MAX_FILE=256*2**20
MAX_TOTAL=16*2**30
def candidate(parts):
 return bool(parts) and parts[0]!='repo' and 'pocs' in parts[:-1]
