#!/usr/bin/python3
"""Isolated original-container guest entry. No PYTHONPATH/cwd fallback."""
from pathlib import Path
import sys

ROOT=Path('/opt/count14-racing-code')
if Path(__file__).resolve()!=ROOT/'smoke_racing_tools_game_entry.py' or ROOT.resolve()!=ROOT:
    raise SystemExit(2)
sys.path.insert(0,str(ROOT))
from smoke_racing_tools_game_runtime import main

try:
    main()
except Exception as error:
    import json
    locations=[];tb=error.__traceback__
    while tb:
        locations.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
    print(json.dumps(dict(PUBLIC_code='DYNTEAM_RACING_GAME_FAILED_RETAIN_NO_REPLAY',
        exception_type=type(error).__name__,locations=locations)),flush=True)
    raise SystemExit(2)
