import unittest

from xed_autosave.config import AUTOSAVE_DELAY_MS


class ConfigTest(unittest.TestCase):
    def test_autosave_delay_is_half_second(self):
        self.assertEqual(AUTOSAVE_DELAY_MS, 500)


if __name__ == "__main__":
    unittest.main()
