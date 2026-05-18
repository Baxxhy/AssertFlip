from decimal import Decimal
from django.utils.numberformat import format
from django.test import SimpleTestCase

class NumberFormatTests(SimpleTestCase):
    def test_small_decimal_formatting_exponential(self):
        small_decimal = Decimal('1e-200')  # This should trigger the bug
        decimal_pos = 2

        result = format(small_decimal, '.', decimal_pos=decimal_pos)

        # The expected output should be '0.00' when the bug is fixed
        self.assertEqual(result, '0.00')  # This checks for the correct behavior when the bug is fixed
