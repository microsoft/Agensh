"""Exact pinned native mtime-fixed function source. Not imported directly.
Infrastructure binding is adapted explicitly by native_materialization.py.
"""
def materialize_terminal(snapshot, workspace, setting):
    """Native frozen terminal workspace, ordinary files only; no live copy.

    Names are used internally for confined extraction, never reported by census.
    Links and special entries are skipped BEFORE any path/mtime interpretation.
    No follow, extractall, hardlink construction, chmod from archive or deletion.
    """
    _,row=load_binding();need(setting==row['setting'],'terminal trajectory')
    snapshot=Path(snapshot);workspace=Path(workspace)
    policy=json.loads((snapshot/'pilot-member-policy.json').read_bytes())
    cap=policy['member_cap'];archive=snapshot/'roles/final/workspace.tar.gz'
    need(workspace.is_dir() and not workspace.is_symlink() and not any(workspace.iterdir()),'fresh empty terminal destination')
    seen=set();entries=0;regular=0;skipped=0
    with tarfile.open(archive,'r|gz',tarinfo=Header,errorlevel=2) as stream:
        for member in stream:
            entries+=1;stream.members.clear()
            need(entries<=cap and entries<=10_000_000,'terminal archive member cap')
            need('\x00' not in member.linkname,'NUL_LINK_TARGET')
            if member.issym() or special_kind(member) is not None:
                skipped+=1;continue
            path=PurePosixPath(member.name)
            need(not path.is_absolute() and '..' not in path.parts and '\x00' not in member.name,'unsafe ordinary terminal path')
            if not path.parts:continue
            dest=workspace.joinpath(*path.parts)
            need(dest.resolve().is_relative_to(workspace),'terminal path escape')
            if member.isdir():dest.mkdir(parents=True,exist_ok=True);continue
            need(member.type in (tarfile.REGTYPE,tarfile.AREGTYPE) and str(path) not in seen,'duplicate/nonordinary terminal entry')
            seen.add(str(path));dest.parent.mkdir(parents=True,exist_ok=True)
            with stream.extractfile(member) as src, dest.open('xb') as out:
                shutil.copyfileobj(src,out,1024*1024)
            need(dest.stat().st_size==member.size,'short terminal materialization')
            # Search finalization is data-only; ordinary files are inert too.
            dest.chmod(0o600)
            # The frozen file time is part of catalog AND model-visible index.
            # Use the same parsed-header ns conversion as the frozen importer;
            # never replace scientific input time with per-K extraction time.
            mtime_ns=int(Decimal(str(member.mtime))*1_000_000_000)
            os.utime(dest,ns=(mtime_ns,mtime_ns),follow_symlinks=False)
            need(dest.stat().st_mtime_ns==mtime_ns,'terminal frozen mtime not preserved')
            regular+=1
    need(entries==policy['roles']['final']['counts']['members'],'terminal complete measured census')
    return dict(members=entries,regular_files_created=regular,links_special_skipped=skipped)
