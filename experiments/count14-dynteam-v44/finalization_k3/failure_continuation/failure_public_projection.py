"""Narrow sanitized OWN-framework observation; NOT a cause/exemption producer."""
from pathlib import Path
import hashlib

PUBLIC_CODE='UNCLASSIFIED_FRAMEWORK_FAILURE_NO_EXEMPTION'


def observe(error,*,framework_source_sha256):
    # Only caller-registered own framework code may be read/hashed. Never
    # scientific paths, private logs, exception args/message or frame locals.
    approved={}
    for name,pin in framework_source_sha256.items():
        p=Path(name)
        if not (p.is_absolute() and p.resolve()==p and not p.is_symlink()
            and hashlib.sha256(p.read_bytes()).hexdigest()==pin):
            raise ValueError('FIXED_PUBLIC_OBSERVER_FRAMEWORK_SOURCE_PIN')
        approved[str(p)]=pin
    kind=type(error).__name__
    if not(kind.isidentifier()and len(kind)<=160):kind='Exception'
    frames=[];tb=error.__traceback__
    while tb is not None:
        code=tb.tb_frame.f_code
        if code.co_filename in approved:
            frames.append(dict(file=code.co_filename,line=tb.tb_lineno,function=code.co_name))
        tb=tb.tb_next
    return dict(schema='count14-framework-narrow-observation-not-cause-proposal-v1',
        PUBLIC_code=PUBLIC_CODE,exception_type=kind,locations=frames,
        cause_known=False,tool_exemption_eligible=False,terminal_binding_present=False,
        messages_or_args_or_locals_read=False)
