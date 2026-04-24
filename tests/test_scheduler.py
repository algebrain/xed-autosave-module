import unittest

from xed_autosave.scheduler import AutosaveScheduler


class FakeClock:
    def __init__(self):
        self.next_id = 1
        self.pending = {}
        self.cancelled = []

    def call_later(self, delay_ms, callback, *args):
        timer_id = self.next_id
        self.next_id += 1
        self.pending[timer_id] = (delay_ms, callback, args)
        return timer_id

    def cancel(self, timer_id):
        self.cancelled.append(timer_id)
        self.pending.pop(timer_id, None)

    def fire(self, timer_id):
        delay_ms, callback, args = self.pending.pop(timer_id)
        return callback(*args)


class AutosaveSchedulerTest(unittest.TestCase):
    def test_second_change_cancels_first_timer(self):
        clock = FakeClock()
        calls = []
        scheduler = AutosaveScheduler(clock, 10_000, lambda doc: calls.append(doc))

        scheduler.changed("doc-1")
        scheduler.changed("doc-1")

        self.assertEqual(clock.cancelled, [1])
        self.assertEqual(list(clock.pending), [2])
        self.assertEqual(calls, [])

    def test_firing_timer_saves_document_and_clears_timer(self):
        clock = FakeClock()
        calls = []
        scheduler = AutosaveScheduler(clock, 10_000, lambda doc: calls.append(doc))

        scheduler.changed("doc-1")
        clock.fire(1)

        self.assertEqual(calls, ["doc-1"])
        self.assertEqual(scheduler.pending_count, 0)

    def test_cancel_all_removes_pending_timers(self):
        clock = FakeClock()
        scheduler = AutosaveScheduler(clock, 10_000, lambda doc: None)

        scheduler.changed("doc-1")
        scheduler.changed("doc-2")
        scheduler.cancel_all()

        self.assertEqual(clock.cancelled, [1, 2])
        self.assertEqual(clock.pending, {})
        self.assertEqual(scheduler.pending_count, 0)


if __name__ == "__main__":
    unittest.main()
