# -*- coding: utf-8 -*-
"""Tests for customer history, resolution suggestions, time metrics, and SLA."""
from datetime import timedelta

from odoo import fields
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestCustomerHistory(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ticket = cls.env["sole.support.ticket"]
        cls.partner_a = cls.env["res.partner"].create({"name": "History Customer A"})
        cls.partner_b = cls.env["res.partner"].create({"name": "History Customer B"})
        cls.backlog = cls.env.ref("sole_support.stage_backlog")
        cls.complete = cls.env.ref("sole_support.stage_complete")

    def _make_ticket(self, partner, subject="Test ticket", stage=None, **kw):
        vals = {"subject": subject, "partner_id": partner.id}
        if stage:
            vals["stage_id"] = stage.id
        vals.update(kw)
        return self.Ticket.create(vals)

    # ── Customer history ──────────────────────────────────────────────────────

    def test_no_history_for_new_customer(self):
        ticket = self._make_ticket(self.partner_a, "First ticket ever")
        self.assertEqual(ticket.previous_ticket_count, 0)
        self.assertFalse(ticket.previous_ticket_ids)

    def test_history_shows_prior_tickets(self):
        t1 = self._make_ticket(self.partner_a, "Prior ticket 1")
        t2 = self._make_ticket(self.partner_a, "Prior ticket 2")
        t3 = self._make_ticket(self.partner_a, "Current ticket")
        history_ids = t3.previous_ticket_ids.ids
        self.assertIn(t1.id, history_ids)
        self.assertIn(t2.id, history_ids)
        self.assertNotIn(t3.id, history_ids)
        self.assertEqual(t3.previous_ticket_count, 2)

    def test_history_excludes_other_customer_tickets(self):
        self._make_ticket(self.partner_b, "Other customer ticket")
        t = self._make_ticket(self.partner_a, "Customer A ticket")
        # Customer B ticket must not appear in customer A's history
        self.assertEqual(t.previous_ticket_count, 0)

    def test_history_clears_when_partner_removed(self):
        self._make_ticket(self.partner_a, "Old ticket")
        t = self._make_ticket(self.partner_a, "Current")
        self.assertGreater(t.previous_ticket_count, 0)
        t.partner_id = False
        self.assertEqual(t.previous_ticket_count, 0)
        self.assertFalse(t.previous_ticket_ids)

    # ── action_view_customer_tickets ──────────────────────────────────────────

    def test_action_view_customer_tickets_returns_act_window(self):
        self._make_ticket(self.partner_a, "Past ticket")
        t = self._make_ticket(self.partner_a, "Current ticket")
        action = t.action_view_customer_tickets()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "sole.support.ticket")
        # domain must filter on partner and exclude current ticket
        domain = action["domain"]
        self.assertTrue(any(
            c[0] == "partner_id" and c[2] == self.partner_a.id
            for c in domain if isinstance(c, (list, tuple)) and len(c) == 3
        ))


@tagged("post_install", "-at_install")
class TestResolutionSuggestions(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ticket = cls.env["sole.support.ticket"]
        cls.partner = cls.env["res.partner"].create({"name": "Suggestion Test Customer"})
        cls.complete = cls.env.ref("sole_support.stage_complete")
        cls.category = cls.env["sole.support.category"].create({"name": "Network Issues"})
        cls.other_cat = cls.env["sole.support.category"].create({"name": "Billing"})

    def _make_ticket(self, category=None, stage=None, subject="Ticket"):
        vals = {"subject": subject, "partner_id": self.partner.id}
        if category:
            vals["category_id"] = category.id
        if stage:
            vals["stage_id"] = stage.id
        return self.Ticket.create(vals)

    def test_no_suggestions_without_resolved_tickets(self):
        t = self._make_ticket(self.category, subject="Open network issue")
        self.assertFalse(t.suggested_ticket_ids)

    def test_suggestions_match_same_category(self):
        resolved = self._make_ticket(self.category, self.complete, "Fixed network issue")
        open_t = self._make_ticket(self.category, subject="New network issue")
        self.assertIn(resolved.id, open_t.suggested_ticket_ids.ids)

    def test_suggestions_exclude_different_category(self):
        resolved_other = self._make_ticket(self.other_cat, self.complete, "Fixed billing")
        open_t = self._make_ticket(self.category, subject="Network issue")
        self.assertNotIn(resolved_other.id, open_t.suggested_ticket_ids.ids)

    def test_suggestions_exclude_open_tickets_in_same_category(self):
        other_open = self._make_ticket(self.category, subject="Another open issue")
        t = self._make_ticket(self.category, subject="My issue")
        self.assertNotIn(other_open.id, t.suggested_ticket_ids.ids)

    def test_suggestions_without_category_show_all_resolved(self):
        resolved = self._make_ticket(self.category, self.complete, "Cross-category resolved")
        open_t = self._make_ticket(None, subject="No category ticket")
        self.assertIn(resolved.id, open_t.suggested_ticket_ids.ids)


@tagged("post_install", "-at_install")
class TestTimeMetrics(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ticket = cls.env["sole.support.ticket"]
        cls.partner = cls.env["res.partner"].create({"name": "Time Metrics Customer"})
        cls.backlog = cls.env.ref("sole_support.stage_backlog")
        cls.in_progress = cls.env.ref("sole_support.stage_in_progress")
        cls.complete = cls.env.ref("sole_support.stage_complete")

    def _make_ticket(self, subject="Time test"):
        return self.Ticket.create({
            "subject": subject,
            "partner_id": self.partner.id,
            "stage_id": self.backlog.id,
        })

    def test_resolution_time_zero_when_not_yet_closed(self):
        t = self._make_ticket()
        self.assertFalse(t.date_closed)
        self.assertEqual(t.resolution_time_hours, 0.0)

    def test_date_closed_set_on_action_close(self):
        t = self._make_ticket()
        t.action_close()
        self.assertTrue(t.date_closed, "date_closed must be set after action_close()")

    def test_resolution_time_formula_is_correct(self):
        """Formula: hours = round((date_closed - create_date).total_seconds() / 3600, 2)."""
        from datetime import datetime
        create = datetime(2026, 1, 1, 8, 0, 0)
        close = datetime(2026, 1, 1, 11, 0, 0)
        expected = round((close - create).total_seconds() / 3600, 2)
        self.assertEqual(expected, 3.0)

    def test_first_response_date_unset_on_new_ticket(self):
        t = self._make_ticket()
        self.assertFalse(t.first_response_date)
        self.assertEqual(t.response_time_hours, 0.0)

    def test_first_response_date_set_when_ticket_leaves_backlog(self):
        t = self._make_ticket()
        t.write({"stage_id": self.in_progress.id})
        self.assertTrue(t.first_response_date,
            "first_response_date must be set when ticket first leaves backlog")

    def test_response_time_formula_is_correct(self):
        """Formula: hours = round((first_response_date - create_date).total_seconds() / 3600, 2)."""
        from datetime import datetime
        create = datetime(2026, 1, 1, 9, 0, 0)
        response = datetime(2026, 1, 1, 9, 30, 0)
        expected = round((response - create).total_seconds() / 3600, 2)
        self.assertAlmostEqual(expected, 0.5, delta=0.01)

    def test_first_response_date_not_overwritten_on_second_stage_move(self):
        t = self._make_ticket()
        t.write({"stage_id": self.in_progress.id})
        first_response = t.first_response_date
        t.write({"stage_id": self.complete.id})
        self.assertEqual(t.first_response_date, first_response)

    def test_response_time_not_set_when_ticket_goes_directly_to_complete(self):
        """Ticket created and immediately closed: first_response_date still set."""
        t = self._make_ticket()
        t.write({"stage_id": self.complete.id})
        # Going from backlog → complete counts as leaving the first stage
        self.assertTrue(t.first_response_date)

    # ── Button visibility flags ───────────────────────────────────────────────

    def test_is_ticket_resolved_false_for_open_ticket(self):
        t = self._make_ticket()
        self.assertFalse(t.is_ticket_resolved)

    def test_is_ticket_closed_false_for_open_ticket(self):
        t = self._make_ticket()
        self.assertFalse(t.is_ticket_closed)

    def test_is_ticket_resolved_and_closed_true_after_action_resolve(self):
        t = self._make_ticket()
        t.action_resolve()
        # Complete stage has both flags
        self.assertTrue(t.is_ticket_resolved)
        self.assertTrue(t.is_ticket_closed)

    def test_is_ticket_closed_true_after_action_close(self):
        t = self._make_ticket()
        t.action_close()
        self.assertTrue(t.is_ticket_closed)


@tagged("post_install", "-at_install")
class TestSLABreach(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ticket = cls.env["sole.support.ticket"]
        cls.partner = cls.env["res.partner"].create({"name": "SLA Test Customer"})
        cls.backlog = cls.env.ref("sole_support.stage_backlog")
        cls.complete = cls.env.ref("sole_support.stage_complete")

    def _make_ticket(self, subject="SLA test", sla_hours=None):
        vals = {"subject": subject, "partner_id": self.partner.id}
        if sla_hours is not None:
            vals["sla_deadline"] = fields.Datetime.now() + timedelta(hours=sla_hours)
        return self.Ticket.create(vals)

    def test_no_sla_deadline_never_breached(self):
        t = self._make_ticket()
        self.assertFalse(t.sla_deadline)
        self.assertFalse(t.is_sla_breached)

    def test_open_ticket_within_deadline_not_breached(self):
        t = self._make_ticket(sla_hours=24)
        self.assertFalse(t.is_sla_breached)

    def test_open_ticket_past_deadline_is_breached(self):
        t = self._make_ticket(sla_hours=-1)   # deadline 1 hour ago
        self.assertTrue(t.is_sla_breached)

    def test_ticket_closed_before_deadline_not_breached(self):
        t = self._make_ticket(sla_hours=24)
        t.action_close()
        self.assertFalse(t.is_sla_breached)

    def test_ticket_closed_after_deadline_is_breached(self):
        t = self._make_ticket(sla_hours=-1)   # deadline already past
        t.action_close()
        self.assertTrue(t.is_sla_breached)

    def test_sla_breach_clears_when_deadline_removed(self):
        t = self._make_ticket(sla_hours=-1)
        self.assertTrue(t.is_sla_breached)
        t.sla_deadline = False
        self.assertFalse(t.is_sla_breached)

    def test_sla_breach_updates_when_deadline_extended(self):
        t = self._make_ticket(sla_hours=-1)   # breached
        self.assertTrue(t.is_sla_breached)
        t.sla_deadline = fields.Datetime.now() + timedelta(hours=48)   # moved to future
        self.assertFalse(t.is_sla_breached)
