#!/usr/bin/env python3
"""Generate public-only no-model plan from pinned developer/OPS source layout."""
from pathlib import Path
import argparse
from native_dry_start_probe import make_plan, canonical

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-base',required=True)
    parser.add_argument('--actor',required=True)
    parser.add_argument('--phase',required=True,choices=('held','ports'))
    parser.add_argument('--front-port',required=True,type=int)
    parser.add_argument('--relay-health-url',required=True)
    a=parser.parse_args()
    value=make_plan(Path(a.source_base).resolve(),actor=a.actor,phase=a.phase,port=a.front_port,relay_health_url=a.relay_health_url)
    print(canonical(value).decode())

if __name__=='__main__':main()
