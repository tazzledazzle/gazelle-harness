import unittest

from pyapp.app import main


class AppTest(unittest.TestCase):
    def test_main(self):
        self.assertEqual(main(), 'HELLO!')


if __name__ == '__main__':
    unittest.main()
