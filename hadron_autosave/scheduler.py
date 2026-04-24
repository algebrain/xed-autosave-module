from .debug import debug


class AutosaveScheduler:
    def __init__(self, clock, delay_ms, save_callback, logger=debug):
        self._clock = clock
        self._delay_ms = delay_ms
        self._save_callback = save_callback
        self._logger = logger
        self._timers = {}

    @property
    def pending_count(self):
        return len(self._timers)

    def changed(self, document):
        old_timer = self._timers.pop(document, None)
        if old_timer is not None:
            self._clock.cancel(old_timer)
            self._logger("cancelled autosave timer", timer_id=old_timer)

        timer_id = self._clock.call_later(
            self._delay_ms,
            self._run,
            document,
        )
        self._timers[document] = timer_id
        self._logger("scheduled autosave", timer_id=timer_id, delay_ms=self._delay_ms)

    def forget(self, document):
        timer_id = self._timers.pop(document, None)
        if timer_id is not None:
            self._clock.cancel(timer_id)
            self._logger("cancelled autosave timer", timer_id=timer_id)

    def cancel_all(self):
        for timer_id in list(self._timers.values()):
            self._clock.cancel(timer_id)
            self._logger("cancelled autosave timer", timer_id=timer_id)
        self._timers.clear()

    def _run(self, document):
        self._timers.pop(document, None)
        self._save_callback(document)
        return False
