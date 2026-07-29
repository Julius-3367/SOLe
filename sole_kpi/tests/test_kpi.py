# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestKpiAchievement(TransactionCase):
    """Gate tests for KPI achievement computation and status thresholds."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cat = cls.env['sole.kpi.category'].create({'name': 'Test Category', 'color': 4})
        cls.indicator_higher = cls.env['sole.kpi.indicator'].create({
            'name': 'Revenue',
            'category_id': cls.cat.id,
            'target': 1_000_000,
            'unit': 'currency',
            'direction': 'higher',
        })
        cls.indicator_lower = cls.env['sole.kpi.indicator'].create({
            'name': 'Critical Incidents',
            'category_id': cls.cat.id,
            'target': 2,
            'unit': 'count',
            'direction': 'lower',
        })
        cls.period = cls.env['sole.kpi.period'].create({
            'name': 'Test Period 2026',
            'date_start': '2026-01-01',
            'date_end': '2026-12-31',
        })
        cls.user = cls.env.ref('base.user_admin')

    def _entry(self, indicator, actual):
        return self.env['sole.kpi.entry'].create({
            'period_id': self.period.id,
            'indicator_id': indicator.id,
            'user_id': self.user.id,
            'actual': actual,
        })

    # ── Higher-is-better ──────────────────────────────────────────

    def test_higher_green(self):
        entry = self._entry(self.indicator_higher, 900_000)
        self.assertEqual(entry.achievement_pct, 90.0)
        self.assertEqual(entry.status, 'green')

    def test_higher_amber(self):
        entry = self._entry(self.indicator_higher, 750_000)
        self.assertAlmostEqual(entry.achievement_pct, 75.0)
        self.assertEqual(entry.status, 'amber')

    def test_higher_red(self):
        entry = self._entry(self.indicator_higher, 620_000)
        self.assertAlmostEqual(entry.achievement_pct, 62.0)
        self.assertEqual(entry.status, 'red')

    def test_higher_black(self):
        entry = self._entry(self.indicator_higher, 500_000)
        self.assertAlmostEqual(entry.achievement_pct, 50.0)
        self.assertEqual(entry.status, 'black')

    def test_higher_green_boundary(self):
        """Exactly 80% must be green."""
        entry = self._entry(self.indicator_higher, 800_000)
        self.assertAlmostEqual(entry.achievement_pct, 80.0)
        self.assertEqual(entry.status, 'green')

    def test_higher_zero_actual(self):
        entry = self._entry(self.indicator_higher, 0)
        self.assertEqual(entry.achievement_pct, 0.0)
        self.assertEqual(entry.status, 'black')

    # ── Lower-is-better ───────────────────────────────────────────

    def test_lower_at_or_below_target_is_100(self):
        """Zero incidents ≤ target → 100% achievement → green."""
        entry = self._entry(self.indicator_lower, 0)
        self.assertEqual(entry.achievement_pct, 100.0)
        self.assertEqual(entry.status, 'green')

    def test_lower_at_target_is_100(self):
        entry = self._entry(self.indicator_lower, 2)
        self.assertEqual(entry.achievement_pct, 100.0)
        self.assertEqual(entry.status, 'green')

    def test_lower_above_target_penalised(self):
        """4 incidents vs target 2 → (2/4)*100 = 50% → black."""
        entry = self._entry(self.indicator_lower, 4)
        self.assertAlmostEqual(entry.achievement_pct, 50.0)
        self.assertEqual(entry.status, 'black')

    # ── Grey / no-target ──────────────────────────────────────────

    def test_grey_when_no_target(self):
        ind = self.env['sole.kpi.indicator'].create({
            'name': 'No Target',
            'category_id': self.cat.id,
            'target': 0,
            'unit': 'count',
            'direction': 'higher',
        })
        entry = self._entry(ind, 5)
        self.assertEqual(entry.status, 'grey')

    # ── Period date validation ─────────────────────────────────────

    def test_period_invalid_dates_raises(self):
        with self.assertRaises(ValidationError):
            self.env['sole.kpi.period'].create({
                'name': 'Bad Period',
                'date_start': '2026-12-31',
                'date_end': '2026-01-01',
            })

    # ── Unique entry constraint ────────────────────────────────────

    def test_duplicate_entry_blocked(self):
        self._entry(self.indicator_higher, 500_000)
        with self.assertRaises(ValidationError):
            self.env['sole.kpi.entry'].create({
                'period_id': self.period.id,
                'indicator_id': self.indicator_higher.id,
                'user_id': self.user.id,
                'actual': 600_000,
            })

    # ── Generate entries ──────────────────────────────────────────

    def test_generate_entries_creates_shells(self):
        role = self.env['sole.kpi.role'].create({
            'name': 'Test Role',
            'code': 'TST',
            'user_ids': [(4, self.user.id)],
        })
        ind = self.env['sole.kpi.indicator'].create({
            'name': 'Gen Test KPI',
            'category_id': self.cat.id,
            'target': 10,
            'unit': 'count',
            'direction': 'higher',
            'role_ids': [(4, role.id)],
        })
        period = self.env['sole.kpi.period'].create({
            'name': 'Gen Test Period',
            'date_start': '2026-01-01',
            'date_end': '2026-03-31',
        })
        period.action_generate_entries()
        entry = self.env['sole.kpi.entry'].search([
            ('period_id', '=', period.id),
            ('indicator_id', '=', ind.id),
            ('user_id', '=', self.user.id),
        ])
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry.actual, 0.0)

    def test_generate_entries_locked_period_raises(self):
        period = self.env['sole.kpi.period'].create({
            'name': 'Locked Period',
            'date_start': '2026-01-01',
            'date_end': '2026-03-31',
            'state': 'locked',
        })
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            period.action_generate_entries()

    # ── Category color_hex ────────────────────────────────────────

    def test_category_color_hex(self):
        cat = self.env['sole.kpi.category'].create({'name': 'Blue', 'color': 4})
        self.assertEqual(cat.color_hex, '#6cc1ed')

    def test_category_color_hex_default(self):
        cat = self.env['sole.kpi.category'].create({'name': 'Default', 'color': 0})
        self.assertEqual(cat.color_hex, '#e4e3e3')
