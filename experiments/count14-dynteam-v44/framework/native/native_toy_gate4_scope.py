"""Explicit WORKERS=2 toy-only native scope; NOT scientific TOOL ancestry.

An OPTIONAL packaging component, not a default/fallback in any native bridge.
Uses only Ledger's pre-existing RUNNING/unparented operation contract. Existing
MCP/Git peer, capability, policy, scope and physical custody remain authoritative.
Toy model costs belong to the independent agensh_feasibility relay, never this
native-startup-only ledger. No request/TOOL/ACK/snapshot is fabricated here.
"""
from pathlib import Path
import re
from common import need, digest, sha

ROLES = ('worker-00', 'worker-01')
PURPOSE = 'TOY_GATE4_ONLY_NOT_SCIENTIFIC'

def startup_manifest(root):
    """Exact existing OPS no-model startup registration, not a science manifest."""
    p = Path(root)
    need(p.is_absolute() and p.resolve() == p and p.is_dir(), 'TOY_GATE4_CANONICAL_ROOT')
    return digest({'purpose': 'HOST_NATIVE_STARTUP_NO_MODEL', 'root': str(p), 'roles': list(ROLES)})

class ToyGate4NativeScope:
    """Trusted owner explicitly opts into a toy, closes before native drain.

    This is intentionally NOT NativeModelToolParents and has no tool-terminal
    port, ACP hook, scientific capture, same-live checkpoint or FINAL interface.
    Construct before owner.start(), seal_prime() after prime, then activate()
    ONLY after the existing full pre-CLI collector PASS. The caller is OPS,
    never a worker. No automatic activation or reopening after close exists.
    """
    def __init__(self, ledger, trajectory, root, *, purpose):
        need(purpose == PURPOSE and type(trajectory) is str and re.fullmatch(
            r'agensh-feasibility-gate4-[A-Za-z0-9_.+-]{1,100}', trajectory), 'TOY_GATE4_EXPLICIT_SCOPE')
        self.ledger, self.trajectory = ledger, trajectory
        self.manifest = startup_manifest(root)
        self.phase = 'PRIMING'
        with ledger.tx():
            self._account()
            # A startup ledger cannot silently become a scientific search ledger.
            need(ledger.db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0] == 1,
                 'TOY_GATE4_SINGLE_STARTUP_ACCOUNT')
            need(ledger.db.execute("SELECT 1 FROM events WHERE trajectory=? AND kind='TOY_GATE4_EXPLICIT_NATIVE_SCOPE'",
                                   (trajectory,)).fetchone() is None, 'TOY_GATE4_NATIVE_SCOPE_NO_REOPEN')
            ledger.event(trajectory, 'TOY_GATE4_EXPLICIT_NATIVE_SCOPE',
                         {'purpose': PURPOSE, 'manifest_sha256': self.manifest,
                          'science_qualified': False, 'model_accounting': 'separate_agensh_feasibility'})

    def _account(self):
        a = self.ledger.account(self.trajectory)
        need(a['manifest_sha'] == self.manifest and a['roles'] == '["worker-00","worker-01"]'
             and a['targets'] == '[100000,200000]' and a['request_cap'] == 2
             and a['stage'] == 0 and a['generation'] == 1,
             'TOY_GATE4_EXACT_ORIGINAL_STARTUP_ACCOUNT')
        need(a['state'] == 'RUNNING' and not self.ledger.admission_fault(self.trajectory),
             'TOY_GATE4_RUNNING_ONLY')
        need(self.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0] == 0
             and self.ledger.db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0] == 0
             and self.ledger.db.execute('SELECT COUNT(*) FROM aux_scopes').fetchone()[0] == 0,
             'TOY_GATE4_NOT_SCIENTIFIC_LEDGER')
        return a

    def seal_prime(self):
        with self.ledger.tx():
            need(self.phase == 'PRIMING', 'TOY_GATE4_PRIME_ONCE')
            self._account()
            need(self.ledger.frontier(self.trajectory)['active_operations'] == 0,
                 'TOY_GATE4_PRIME_NOT_PHYSICALLY_TERMINAL')
            self.phase = 'HELD'
            self.ledger.event(self.trajectory, 'TOY_GATE4_PRIME_SEALED', {'purpose': PURPOSE})

    def activate(self, precli_summary):
        # Reference the already-required collector; don't manufacture a new gate.
        with self.ledger.mutex:
            with self.ledger.tx():
                need(self.phase == 'HELD', 'TOY_GATE4_EXPLICIT_ACTIVATION_ONCE')
                self._account()
                need(type(precli_summary) is dict
                     and precli_summary.get('schema') == 'agensh-native-team2-no-model-dry-start-summary-v1'
                     and precli_summary.get('status') == 'PRECLI_DRY_START_PASS_NOT_REAL_GATE4_PASS'
                     and precli_summary.get('failed_checks') == []
                     and type(precli_summary.get('model_requests')) is int and precli_summary['model_requests'] == 0
                     and precli_summary.get('published_release') is False
                     and precli_summary.get('started_cli_or_acp') is False,
                     'TOY_GATE4_PRECLI_PASS_REQUIRED')
                need(self.ledger.frontier(self.trajectory)['active_operations'] == 0,
                     'TOY_GATE4_ACTIVATION_NOT_DRAINED')
                pin = digest(precli_summary); sha(pin)
                self.ledger.event(self.trajectory, 'TOY_GATE4_RUNTIME_ACTIVATED',
                                  {'purpose': PURPOSE, 'precli_summary_sha256': pin,
                                   'scientific_parent_or_capture_qualified': False})
            self.phase = 'TOY_RUNNING'

    def __call__(self, binding):
        with self.ledger.mutex:
            need(self.phase in ('PRIMING', 'TOY_RUNNING'), 'TOY_GATE4_NATIVE_ADMISSION_CLOSED')
            self._account()
            need(binding.trajectory == self.trajectory and binding.role in ROLES
                 and type(binding.generation) is int and binding.generation == 1,
                 'TOY_GATE4_NATIVE_SCOPE_IDENTITY')
            # A real unparented operation is recorded by the ORIGINAL broker;
            # no request/model TOOL is inferred or invented.
            return None

    def close_admission(self):
        with self.ledger.mutex:
            if self.phase == 'CLOSED':
                return
            self.phase = 'CLOSED'
            # Fail closed first. Never release accepted native operations here.
            with self.ledger.tx():
                self.ledger.event(self.trajectory, 'TOY_GATE4_NATIVE_ADMISSION_CLOSED', {'purpose': PURPOSE})
            if self.ledger.account(self.trajectory)['state'] == 'RUNNING':
                self.ledger.close_admission(self.trajectory, 'TOY_GATE4_STOP_NO_NEW_NATIVE_OPERATION')
