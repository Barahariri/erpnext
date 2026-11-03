"""Fast, deterministic regression tests for the construction demo specification.

These do not require seeding a database. Integration tests still require a
disposable ERPNext v16.53/Frappe v16.54/HRMS v16 site.
"""
import unittest

from erpnext.setup.construction_demo.config import (
    COMPANIES,
    END_DATE,
    START_DATE,
    expected_totals,
    scaled,
)
from erpnext.setup.construction_demo.contracts import BOQ_SPLIT
from erpnext.setup.construction_demo.taxes import TAX_RATE_TEST, TAX_STATUS


class TestConstructionDemoConfig(unittest.TestCase):
    def test_three_independent_companies(self):
        self.assertEqual(len(COMPANIES), 3)
        self.assertEqual({p.country for p in COMPANIES}, {"Kuwait", "Qatar", "Syria"})
        self.assertEqual({p.currency for p in COMPANIES}, {"KWD", "QAR", "SYP"})
        self.assertEqual(len({p.abbr for p in COMPANIES}), 3)
        self.assertTrue(all(len(p.sites) >= 1 for p in COMPANIES))
        self.assertEqual(len(COMPANIES[0].sites), 2)

    def test_full_counts(self):
        self.assertEqual(
            expected_totals("full"),
            {
                "companies": 3,
                "employees": 155,
                "projects": 22,
                "equipment": 74,
                "customers": 58,
                "suppliers": 90,
                "materials": 240,
            },
        )

    def test_small_pilot(self):
        got = expected_totals("pilot")
        self.assertEqual(got["companies"], 3)
        self.assertEqual(got["employees"], 3)
        self.assertEqual(got["projects"], 3)
        self.assertEqual(got["equipment"], 3)
        self.assertEqual(got["materials"], 3)
        for value in got.values():
            self.assertGreaterEqual(value, 1)

    def test_scale_validation(self):
        with self.assertRaises(ValueError):
            scaled(14, "unrecognized")

    def test_boq_percentages(self):
        from decimal import Decimal

        self.assertEqual(sum(Decimal(w) for w in BOQ_SPLIT), Decimal("1.00"))

    def test_36_complete_months(self):
        self.assertEqual(START_DATE, "2023-11-01")
        self.assertEqual(END_DATE, "2026-10-31")

    def test_tax_mode_is_not_statutory(self):
        self.assertEqual(TAX_RATE_TEST, 5)
        self.assertEqual(set(TAX_STATUS), {"KRC", "RDC", "MSE"})
        for note in TAX_STATUS.values():
            self.assertIn("no", note.lower())


if __name__ == "__main__":
    unittest.main()
