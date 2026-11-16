"""Final-only SAME retirement custody for already-started original Game execs.

No checkpoint waits for a Game round. This cold instance seam runs only AFTER
the original two snapshots/K3/physical-paid-zero retirement qualification. It
refreshes FINAL/HOLD metadata before thaw, reaps existing custodian/exec IDs,
and refuses to stop the background container while its exact Game is live.
It never calls manager.poll (which could schedule another round), publishes
new tests, cancels futures, sends signals, rewrites history or touches fees.
"""
from __future__ import annotations

from types import MethodType
import copy

from common import need


class RacingRetirementCustody:
    def __init__(self, retirement, *, manager, consumer):
        from smoke_checkpoint_final_retirement import SmokeFinalRetirement
        from smoke_racing_tools_game_manager import NativeRacingGameManager
        from native_racing_shared_tests import RacingSharedPublicTests
        need(type(retirement) is SmokeFinalRetirement and type(manager) is NativeRacingGameManager and
             type(consumer) is RacingSharedPublicTests and
             retirement.core is manager.core is consumer.core and retirement.t == manager.t == consumer.t and
             retirement.core.rows[retirement.t]['arm'] == 'DYNTEAM_RACING' and
             retirement.state == 'SEARCH_AND_K3_COMPLETE_NOT_RETIRED' and consumer.closing and
             consumer.active is None and not hasattr(retirement, 'racing_game_custody'),
             'RACING_RETIREMENT_ONLY_REAL_COMPLETE_SAME_OWNER_COLD_INSTANCE')
        self.retirement, self.manager, self.consumer = retirement, manager, consumer
        self.original_step, self.original_stop = retirement.step, retirement._stop_one
        self.original_public = retirement.public
        self.failure = None
        self.natural_terminal_receipt = False
        retirement.racing_game_custody = self
        retirement.step = MethodType(lambda own: self.step(), retirement)
        retirement._stop_one = MethodType(lambda own, item: self.stop_one(item), retirement)
        retirement.public = MethodType(lambda own: self.public(), retirement)

    def outside_locks(self):
        need(not self.retirement.core.ledger.mutex._is_owned(),
             'RACING_RETIREMENT_NO_IO_UNDER_SCIENCE_LOCK')

    def all_existing_terminal(self):
        # A registered orchestration control PID is NOT a terminal proof. The
        # original daemon exec terminal AND the original retained Popen matter.
        return all(game['terminal'] is True and game['child'] is not None and
                   game['child'].poll() == 0 for game in self.manager.games)

    def reap_existing(self):
        self.outside_locks()
        need(self.manager.failure is None, 'RACING_RETIREMENT_RETAIN_FAILED_ORIGINAL_GAME')
        for game in self.manager.games:
            if not game['terminal']:
                self.manager._game_step(game)  # same existing exec ID, not a new Game
            child = game['child']
            need(child is not None and child.poll() in (None, 0),
                 'RACING_RETIREMENT_ORIGINAL_GAME_CUSTODIAN_FAILED_RETAIN')
        if self.manager.games and self.all_existing_terminal() and not self.natural_terminal_receipt:
            self.retirement._receipt('RACING_EXISTING_GAMES_NATURALLY_TERMINAL',
                original_games=len(self.manager.games), no_new_rounds=True,
                published_public_tests_retained=self.manager.published_public,
                notifications_already_done=self.consumer.completed,
                unnotified_public_tests_retained=max(0, self.manager.published_public - self.consumer.completed),
                new_system_publications=0, official_verdict=False)
            self.natural_terminal_receipt = True

    def stop_one(self, item):
        self.outside_locks()
        if item['component'] == 'agent' and item['role'] == 'racing-background-00':
            if not self.all_existing_terminal():
                return False
        return self.original_stop(item)

    def step(self):
        own = self.retirement
        if own.state in ('SMOKE_FULLY_RETIRED', 'PARTIAL_RETAINED_NO_RETRY'):
            return self.public()
        try:
            self.outside_locks()
            if own.state in ('WAITING_ORIGINAL_SYSTEM_AND_RESOURCE_TERMINAL',
                             'THAWING_FINAL_WRITERS_NO_SEARCH_RESUME'):
                # Final snapshot is already immutable COMMITTED. This is only
                # fresh FINAL/HOLD control before the SAME original normal thaw.
                self.manager._control(force=True)
            elif own.state not in ('SEARCH_AND_K3_COMPLETE_NOT_RETIRED',):
                self.manager._control(force=True)
                self.reap_existing()
            self.original_step()
            if own.core.closed:
                # Same live terminal view only. Original immutable receipts and
                # original acceptance/audit/financial records stay untouched.
                own.cached_public.update(self.fields())
                own.core.smoke_terminal_public = copy.deepcopy(own.cached_public)
            return self.public()
        except Exception as error:
            locations, tb = [], error.__traceback__
            while tb:
                locations.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                                      function=tb.tb_frame.f_code.co_name))
                tb = tb.tb_next
            self.failure = dict(PUBLIC_code='RACING_RETIREMENT_ORIGINAL_GAME_RETAINED_NO_RETRY',
                exception_type=type(error).__name__, locations=locations)
            own.failure = copy.deepcopy(self.failure)
            own.state = 'PARTIAL_RETAINED_NO_RETRY'
            own._receipt('RACING_FAILED_RETAINED', **self.failure)
            return self.public()

    def fields(self):
        started = len(self.manager.games)
        terminal = sum(game['terminal'] and game['child'] is not None and game['child'].poll() == 0
                       for game in self.manager.games)
        return dict(racing_rounds_started=started, racing_rounds_naturally_terminal=terminal,
            racing_public_tests_published=self.manager.published_public,
            racing_original_test_suite_notifications_done=self.consumer.completed,
            racing_unnotified_tests_retained=max(0, self.manager.published_public - self.consumer.completed),
            racing_mechanism_exercised=started > 0 and terminal > 0 and self.consumer.completed > 0,
            racing_game_control_is_not_terminal_evidence=True,
            original_graph_acceptance_is_not_racing_mechanism_acceptance=True,
            racing_retirement_failure=copy.deepcopy(self.failure))

    def public(self):
        result = self.original_public()
        result.update(self.fields())
        return result


def install_racing_retirement(retirement, *, manager, consumer):
    return RacingRetirementCustody(retirement, manager=manager, consumer=consumer)
