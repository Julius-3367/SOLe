# -*- coding: utf-8 -*-
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestSupportProjectSync(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ticket = cls.env["sole.support.ticket"]
        cls.partner = cls.env["res.partner"].create({"name": "Sync Test Customer"})
        cls.user = cls.env["res.users"].create({
            "name": "Sync Test Agent",
            "login": "sync_test_agent",
            "email": "sync_test_agent@example.com",
        })
        cls.stage_backlog = cls.env.ref("sole_support.stage_backlog")
        cls.stage_in_progress = cls.env.ref("sole_support.stage_in_progress")
        cls.stage_complete = cls.env.ref("sole_support.stage_complete")
        cls.task_backlog = cls.env.ref("sole_support_project.task_stage_backlog")
        cls.task_in_progress = cls.env.ref("sole_support_project.task_stage_in_progress")
        cls.task_complete = cls.env.ref("sole_support_project.task_stage_complete")

    def _create_ticket(self, **kwargs):
        vals = {
            "subject": "Sync test ticket",
            "partner_id": self.partner.id,
            "assigned_to": self.user.id,
        }
        vals.update(kwargs)
        return self.Ticket.create(vals)

    # ── Stage mapping ───────────────────────────────────────────────────────
    def test_support_to_task_stage_mapping_is_three_stages(self):
        from odoo.addons.sole_support_project.models.support_project_sync import (
            SUPPORT_TO_TASK_STAGE,
            TASK_TO_SUPPORT_STAGE,
        )
        self.assertEqual(
            SUPPORT_TO_TASK_STAGE,
            {
                "stage_backlog": "task_stage_backlog",
                "stage_in_progress": "task_stage_in_progress",
                "stage_complete": "task_stage_complete",
            },
        )
        self.assertEqual(
            TASK_TO_SUPPORT_STAGE,
            {
                "task_stage_backlog": "stage_backlog",
                "task_stage_in_progress": "stage_in_progress",
                "task_stage_complete": "stage_complete",
            },
        )

    def test_ticket_creates_task_on_canonical_backlog_stage(self):
        ticket = self._create_ticket()
        self.assertTrue(ticket.task_id)
        self.assertEqual(ticket.task_id.stage_id, self.task_backlog)

    def test_ticket_stage_change_syncs_task_stage(self):
        ticket = self._create_ticket()

        ticket.write({"stage_id": self.stage_in_progress.id})
        self.assertEqual(ticket.task_id.stage_id, self.task_in_progress)

        ticket.write({"stage_id": self.stage_complete.id})
        self.assertEqual(ticket.task_id.stage_id, self.task_complete)

    def test_task_stage_change_syncs_ticket_stage(self):
        ticket = self._create_ticket()
        task = ticket.task_id

        task.write({"stage_id": self.task_complete.id})
        self.assertEqual(ticket.stage_id, self.stage_complete)

    # ── SLA visibility on the project task ───────────────────────────────────
    def test_task_sla_deadline_mirrors_ticket(self):
        ticket = self._create_ticket()
        deadline = "2026-06-20 12:00:00"
        ticket.sla_deadline = deadline

        self.assertEqual(str(ticket.task_id.sla_deadline), deadline)

    def test_task_sla_deadline_empty_without_ticket(self):
        task = self.env["project.task"].create({
            "name": "Standalone task",
            "project_id": self.env.ref("sole_support_project.project_support_duties").id,
        })
        self.assertFalse(task.support_ticket_id)
        self.assertFalse(task.sla_deadline)

    # ── Deadline sync ────────────────────────────────────────────────────────
    def test_task_date_deadline_set_from_sla_on_create(self):
        """date_deadline on the task is populated from the ticket's sla_deadline at creation."""
        ticket = self._create_ticket()
        deadline = "2026-07-01 09:00:00"
        ticket.sla_deadline = deadline
        # sla_deadline write triggers a sync
        self.assertEqual(str(ticket.task_id.date_deadline), deadline)

    def test_task_date_deadline_updates_when_sla_changes(self):
        """Changing sla_deadline on an existing ticket propagates to the task's date_deadline."""
        ticket = self._create_ticket()
        ticket.sla_deadline = "2026-07-01 09:00:00"
        ticket.sla_deadline = "2026-07-15 17:00:00"
        self.assertEqual(str(ticket.task_id.date_deadline), "2026-07-15 17:00:00")

    # ── Priority 1:1 mapping ─────────────────────────────────────────────────
    def test_priority_three_syncs_as_three(self):
        """Support priority '3' (Critical) must arrive on the task as '3', not '2'."""
        ticket = self._create_ticket(priority="3")
        self.assertEqual(ticket.task_id.priority, "3")

    def test_priority_two_syncs_as_two(self):
        ticket = self._create_ticket(priority="2")
        self.assertEqual(ticket.task_id.priority, "2")

    def test_priority_change_syncs_to_task(self):
        ticket = self._create_ticket(priority="1")
        ticket.write({"priority": "3"})
        self.assertEqual(ticket.task_id.priority, "3")
