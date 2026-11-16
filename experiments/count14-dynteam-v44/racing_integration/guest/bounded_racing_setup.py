"""User msg260: ONE first-background setup completion, never a phase replay.

Scientific guest only. Both this fixed marker under the original persistent
workspace and the router's independent O_EXCL marker survive the normal whole
RW-mount physical checkpoint. Neither marker is cleared or reset at a cut.
Import performs no filesystem, native, model or constructor action.
"""
from pathlib import Path
import json
import os
import stat

AUTHORITY = 'CARETAKER_USER_APPROVE_ONE_BOUNDED_PAID_RACING_SETUP_COMPLETION'
APPROVED_PROPOSAL_SHA256 = 'c44c0eeaecad6a306e1a7396b12a6f5700d11390a0e740fc57df6c88c77857a7'
PROGRAM_METADATA = '/work/.count14-racing/public-program.json'
USED = '/work/.count14-racing/RACING_SETUP_COMPLETION_PUBLIC.json'
POLICY = 'AT_MOST_ONCE_FIRST_BACKGROUND_NORMAL_ENDTURN_EXACT_METADATA_MISSING'
INSTRUCTION = (
    'Complete ONLY the public-program setup already required by the preceding '
    'background instruction, in this SAME original background session. Keep all '
    'original background material and brainstorming unchanged; do not generate '
    'another background, brainstorm, candidate set, role or task. Use only the '
    'original public task tools and the already approved task/source workspace. '
    'Finish the existing executable public wrapper under '
    '/work/.count14-racing/public-program/ and write '
    '/work/.count14-racing/public-program.json with exactly '
    '{"schema":"count14-racing-public-program-v1","task_slot":<the same selected '
    'integer 1..14>,"program":"/work/.count14-racing/public-program/<existing '
    'executable public wrapper>"}. Both files must have the original normal '
    'UID10000 and original path/mode/executable protections. No official evaluator, '
    'private reference, hidden tests or fabricated wrapper are permitted. '
    'This is the sole authorized paid setup-completion continuation; all native '
    'API/tool turns remain charged to the same SEARCH account and budget. '
    'Do not redo the original background or request another continuation.'
)


def try_first_setup_completion(error, *, manifest, llm, log, emit_public):
    """Consume once BEFORE native IPC, even if admission/result is ambiguous."""
    if not (type(error) is FileNotFoundError and error.filename == PROGRAM_METADATA and
            manifest['round_ordinal'] == 1 and llm.last_background_stop_reason == 'end_turn'):
        return False
    # This validates original typed receipt/SID/turn identity before any marker
    # or native request. Missing/unknown identity is never a session fallback.
    llm.require_first_background_setup_anchor()
    path = Path(USED)
    parent = path.parent
    info = parent.lstat()
    if not (os.getuid() == os.getgid() == 10000 and parent.resolve() == parent and
            stat.S_ISDIR(info.st_mode) and info.st_uid == 10000 and not info.st_mode & 0o022):
        raise ValueError('RACING_SETUP_COMPLETION_ONLY_ORIGINAL_PERSISTENT_UID_WORKSPACE')
    value = dict(schema='count14-racing-setup-completion-intent-public-v1',
        authority=AUTHORITY, approved_proposal_sha256=APPROVED_PROPOSAL_SHA256,
        trajectory=manifest['trajectory'], contract_sha256=manifest['contract_sha256'],
        round_ordinal=1, trigger_count=1, policy=POLICY,
        stage='INTENT_BEFORE_SAME_SID_PROMPT_NO_REPLAY',
        first_background_normal_end_turn=True, original_receipts_physical_terminal=True,
        all_calls_charged_SEARCH=True, used_per_trajectory=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    except FileExistsError:
        return False  # Never read, delete, reset, or reuse an earlier intent.
    try:
        with os.fdopen(fd, 'wb', closefd=False) as out:
            out.write((json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode())
            out.flush()
            os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        current = os.fstat(directory)
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError('RACING_SETUP_COMPLETION_ORIGINAL_PARENT_IDENTITY_CHANGED')
        os.fsync(directory)
    finally:
        os.close(directory)
    error._count14_setup_completion_attempted = True
    emit_public(dict(schema='count14-racing-setup-completion-public-v1',
        round_ordinal=1, trigger_count=1, policy=POLICY,
        stage='INTENT_BEFORE_SAME_SID_PROMPT_NO_REPLAY',
        first_background_normal_end_turn=True, original_receipts_physical_terminal=True,
        all_calls_charged_SEARCH=True))
    # No loop/retry. The native port independently persists an O_EXCL bit and
    # verifies unchanged connection/SID/turn before the original promptText.
    text = llm.complete_first_background_setup(INSTRUCTION)
    log.write_text('setup-completion.md', text)
    return True
