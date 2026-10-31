# Timing rules for a team run: budget, staggered wake, idle phases and reminders.
# Pure functions, so the driver's schedule can be unit tested.

DELIVERY_PHASE_SHORT_SECONDS = 300
DELIVERY_PHASE_LONG_SECONDS = 2700
MINIMUM_REMAINING_SECONDS = 60


def budget_seconds(hours):
    return int(round(float(hours) * 3600))


def remaining_after(total_seconds, elapsed_seconds):
    # Startup is charged to the budget, but workers always get at least a minute.
    return max(total_seconds - elapsed_seconds, MINIMUM_REMAINING_SECONDS)


def idle_phase(total_seconds, remaining_seconds):
    # Long runs deliver in their last 45 minutes, short runs in their last five.
    window = (DELIVERY_PHASE_LONG_SECONDS if total_seconds > DELIVERY_PHASE_LONG_SECONDS
              else DELIVERY_PHASE_SHORT_SECONDS)
    return 'delivery' if remaining_seconds <= window else 'development'


def wake_stagger(index, base_seconds=30, fast_seconds=3, ramp_seconds=3600):
    # The switch is by worker index, not elapsed time: startup can exceed either target.
    switch = ramp_seconds // base_seconds
    return base_seconds if index <= switch else fast_seconds


def reminder_times(total_seconds, reminders):
    """Return (offset_seconds, reminder) pairs, in order, for reminders still ahead.

    Each reminder fires `before_end_seconds` before the end of the run; reminders
    whose time has already passed when the run starts are skipped.
    """
    due = [(total_seconds - reminder['before_end_seconds'], reminder) for reminder in reminders]
    return sorted([(offset, reminder) for offset, reminder in due if offset > 0], key=lambda pair: pair[0])


def should_nudge(idle_seconds, now, last_nudge, threshold_seconds=600, repeat_seconds=600):
    return idle_seconds >= threshold_seconds and now - last_nudge >= repeat_seconds
