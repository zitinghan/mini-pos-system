"""Run with pytest, or unittest when only the Python standard library is available."""
import unittest

from app.services.pricing import SelectionGroup, PriceValidationError, calculate_price


WANTAN = [
    SelectionGroup(1, '酱汁', 1, 1, {1: 0, 2: 0, 3: 0}),
    SelectionGroup(2, '辣度', 1, 1, {4: 0, 5: 0}),
    SelectionGroup(3, '份量', 1, 1, {6: 0, 7: 200}),
]
KUEH = [
    SelectionGroup(4, '做法', 1, 1, {8: 0, 9: 0}),
    SelectionGroup(5, '鸡蛋', 1, 1, {10: 0, 11: 100}),
]
RICE = [SelectionGroup(6, '份量', 1, 1, {12: 0, 13: 200})]


class MenuPrices(unittest.TestCase):
    def test_wantan_regular(self):
        self.assertEqual(calculate_price(800, 1, WANTAN, [1, 4, 6]).unit_price, 800)

    def test_wantan_extra_noodles(self):
        self.assertEqual(calculate_price(800, 1, WANTAN, [3, 5, 7]).unit_price, 1000)

    def test_kueh_regular(self):
        self.assertEqual(calculate_price(800, 1, KUEH, [8, 10]).unit_price, 800)

    def test_kueh_with_egg(self):
        self.assertEqual(calculate_price(800, 1, KUEH, [9, 11]).unit_price, 900)

    def test_rice_regular(self):
        self.assertEqual(calculate_price(800, 1, RICE, [12]).unit_price, 800)

    def test_rice_large(self):
        self.assertEqual(calculate_price(800, 1, RICE, [13]).unit_price, 1000)

    def test_acceptance_bill(self):
        first = calculate_price(800, 2, WANTAN, [1, 5, 7])
        additional = calculate_price(800, 1, KUEH, [8, 11])
        self.assertEqual(first.line_total, 2000)
        self.assertEqual(first.line_total + additional.line_total, 2900)
        self.assertEqual(5000 - first.line_total - additional.line_total, 2100)

    def test_invalid_selections(self):
        for options in ([], [1, 6], [1, 4, 6, 7], [1, 1, 4, 6], [1, 4, 999], [1, 4, 6, 11]):
            with self.subTest(options=options), self.assertRaises(PriceValidationError):
                calculate_price(800, 1, WANTAN, options)

    def test_invalid_quantities(self):
        for quantity in (0, -1, 100, 1.5, True):
            with self.subTest(quantity=quantity), self.assertRaises(PriceValidationError):
                calculate_price(800, quantity, RICE, [12])

    def test_fractional_or_negative_money_rejected(self):
        for price in (8.0, -1, True):
            with self.subTest(price=price), self.assertRaises(PriceValidationError):
                calculate_price(price, 1, RICE, [12])
        for surcharge in (1.5, -1):
            with self.subTest(surcharge=surcharge), self.assertRaises(PriceValidationError):
                calculate_price(800, 1, [SelectionGroup(1, 'extra', 1, 1, {1: surcharge})], [1])

    def test_optional_and_multiple_selections(self):
        group = SelectionGroup(1, 'Extras', 0, 2, {1: 100, 2: 200, 3: 300})
        self.assertEqual(calculate_price(800, 1, [group], []).unit_price, 800)
        self.assertEqual(calculate_price(800, 2, [group], [1, 2]).line_total, 2200)
        with self.assertRaises(PriceValidationError):
            calculate_price(800, 1, [group], [1, 2, 3])

    def test_previous_quote_unchanged_after_menu_edit(self):
        prices = {1: 200}
        group = SelectionGroup(1, 'Extra noodles', 1, 1, prices)
        before = calculate_price(800, 2, [group], [1])
        prices[1] = 400
        after = calculate_price(900, 2, [group], [1])
        self.assertEqual(before.line_total, 2000)
        self.assertEqual(after.line_total, 2600)


if __name__ == '__main__':
    unittest.main()
