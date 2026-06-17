# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from odoo import fields


@tagged("post_install", "-at_install")
class TestEscalation(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ticket = cls.env["sole.support.ticket"]
        cls.partner = cls.env["res.partner"].create({"name": "Escalation Test Customer"})

    def _create_ticket(self, priority="1", **kwargs):
        vals = {
            "subject": "Escalation test ticket",
            "partner_id": self.partner.id,
            "priority": priority,
        }
        vals.update(kwargs)
        return self.Ticket.create(vals)

    def test_new_ticket_is_not_escalated(self):
        """Fresh ticket must have is_escalated=False."""
        ticket = self._create_ticket()
        self.assertFalse(ticket.is_escalated)
        self.assertFalse(ticket.escalated_date)

    def test_escalate_sets_flag_and_timestamp(self):
        """action_escalate must set is_escalated=True and record the datetime."""
        ticket = self._create_ticket()
        ticket.action_escalate()
        self.assertTrue(ticket.is_escalated)
        self.assertTrue(ticket.escalated_date)

    def test_escalate_bumps_low_priority_to_high(self):
        """Escalating a Low or Normal ticket must raise priority to at least High."""
        for start_priority in ("0", "1"):
            ticket = self._create_ticket(priority=start_priority)
            ticket.action_escalate()
            self.assertIn(ticket.priority, ("2", "3"),
                msg=f"Priority {start_priority} should bump to at least High on escalation")

    def test_escalate_preserves_critical_priority(self):
        """Escalating a Critical ticket must not change its priority."""
        ticket = self._create_ticket(priority="3")
        ticket.action_escalate()
        self.assertEqual(ticket.priority, "3")

    def test_escalate_logs_chatter_message(self):
        """action_escalate must post a note in the chatter."""
        ticket = self._create_ticket()
        msg_count_before = len(ticket.message_ids)
        ticket.action_escalate()
        self.assertGreater(len(ticket.message_ids), msg_count_before,
            "Escalation must post a chatter message")

    def test_deescalate_clears_fields(self):
        """action_deescalate must clear is_escalated, escalated_to, reason, date."""
        manager = self.env["res.users"].search([], limit=1)
        ticket = self._create_ticket()
        ticket.action_escalate()
        ticket.write({
            "escalated_to": manager.id,
            "escalation_reason": "Customer SLA breach imminent",
        })
        self.assertTrue(ticket.is_escalated)

        ticket.action_deescalate()
        self.assertFalse(ticket.is_escalated)
        self.assertFalse(ticket.escalated_to)
        self.assertFalse(ticket.escalation_reason)
        self.assertFalse(ticket.escalated_date)

    def test_deescalate_logs_chatter_message(self):
        """action_deescalate must also post a chatter note."""
        ticket = self._create_ticket()
        ticket.action_escalate()
        msg_count_before = len(ticket.message_ids)
        ticket.action_deescalate()
        self.assertGreater(len(ticket.message_ids), msg_count_before)

    def test_escalated_to_field_stores_correctly(self):
        """escalated_to must persist the assigned user."""
        manager = self.env["res.users"].search([], limit=1)
        ticket = self._create_ticket()
        ticket.action_escalate()
        ticket.escalated_to = manager
        self.assertEqual(ticket.escalated_to, manager)

    def test_escalation_reason_persists(self):
        """escalation_reason must be writable and persisted."""
        ticket = self._create_ticket()
        ticket.action_escalate()
        ticket.escalation_reason = "VIP customer, SLA at risk"
        self.assertEqual(ticket.escalation_reason, "VIP customer, SLA at risk")
