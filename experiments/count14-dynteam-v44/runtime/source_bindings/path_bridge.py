"""Only 51 proven same-role requests aliases, no general symlink relaxation."""
from pathlib import Path

def install(observer,aliases):
    observer.need(not getattr(observer,'_count14_exact_request_alias_bridge',False))
    strict=observer.canonical;original_sources=observer.scale_sources
    mapping={Path(a):Path(b)for a,b in aliases.items()}
    for a,b in mapping.items():
        observer.need(a.is_absolute()and b.is_absolute()and a.name==b.name=='requests'and a.parent.name==b.parent.name)
        # Same exact setting/role, one original recovery epoch segment only.
        prefix=b.parent.parent.parent
        observer.need(b==prefix/'roles'/a.parent.name/'requests'and a.parent.parent.parent.parent==prefix/'recovery-epochs')
        observer.need(a.is_symlink()and a.resolve()==strict(b))
    def canonical(p):
        p=Path(p)
        for a,b in mapping.items():
            if p==a:
                observer.need(a.is_symlink()and a.resolve()==b);return strict(b)
            if p.is_relative_to(a):
                tail=p.relative_to(a)
                observer.need(len(tail.parts)==2 and tail.name=='receipt-terminal.json')
                observer.need(a.is_symlink()and a.resolve()==b and p.resolve()==b/tail);return strict(b/tail)
        return strict(p)
    def sources(value):
        books,roots=original_sources(value)
        return books,sorted({str(canonical(p))for p in roots})
    observer.canonical=canonical;observer.scale_sources=sources;observer._count14_exact_request_alias_bridge=True
