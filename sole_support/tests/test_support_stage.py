# -*- coding: utf-8 -*-
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestSupportStage(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Stage = cls.env["sole.support.stage"]
        cls.Ticket = cls.env["sole.support.ticket"]
        cls.backlog = cls.env.ref("sole_support.stage_backlog")
        cls.in_progress = cls.env.ref("sole_support.stage_in_progress")
        cls.complete = cls.env.ref("sole_support.stage_complete")
        cls.partner = cls.env["res.partner"].create({"name": "Support Stage Test Customer"})

    def _create_ticket(self, **kwargs):
        vals = {"subject": "Test ticket", "partner_id": self.partner.id}
        vals.update(kwargs)
        return self.Ticket.create(vals)

    # ── Canonical pipeline ──────────────────────────────────────────────────
    def test_canonical_stages_form_three_column_pipeline(self):
        stages = self.Stage.search([], order="sequence, id")
        self.assertEqual(
            stages.mapped("name"), ["Backlog", "In Progress", "Complete"]
        )
        self.assertFalse(self.backlog.is_resolved)
        self.assertFalse(self.backlog.is_closed)
        self.assertFalse(self.backlog.fold)

        self.assertFalse(self.in_progress.is_resolved)
        self.assertFalse(self.in_progress.is_closed)
        self.assertFalse(self.in_progress.fold)

        self.assertTrue(self.complete.is_resolved)
        self.assertTrue(self.complete.is_closed)
        self.assertTrue(self.complete.fold)

    def test_new_ticket_defaults_to_backlog(self):
        ticket = self._create_ticket()
        self.assertEqual(ticket.stage_id, self.backlog)

    def test_resolve_and_close_actions_move_to_complete(self):
        resolve_ticket = self._create_ticket()
        resolve_ticket.action_resolve()
        self.assertEqual(resolve_ticket.stage_id, self.complete)

        close_ticket = self._create_ticket()
        close_ticket.action_close()
        self.assertEqual(close_ticket.stage_id, self.complete)
        self.assertTrue(close_ticket.date_closed)

    # ── Kanban grouping ──────────────────────────────────────────────────────
    def test_read_group_stage_ids_always_returns_all_three_stages(self):
        # Even with an empty/unrelated domain, every canonical stage must
        # be returned so the kanban always shows Backlog / In Progress /
        # Complete as columns.
        result = self.Ticket._read_group_stage_ids(self.Stage.browse(), [])
        self.assertEqual(
            result.mapped("name"), ["Backlog", "In Progress", "Complete"]
        )

    # ── Legacy stage migration ───────────────────────────────────────────────
    def test_migrate_legacy_stage_collapses_open_stage_onto_backlog(self):
        legacy = self.Stage.create({"name": "New", "sequence": 5})
        ticket = self._create_ticket(stage_id=legacy.id)

        self.Stage._migrate_legacy_stages()

        self.assertEqual(ticket.stage_id, self.backlog)
        self.assertFalse(legacy.exists())

    def test_migrate_legacy_stage_collapses_resolved_stage_onto_complete(self):
        legacy = self.Stage.create({
            "name": "Resolved", "sequence": 40, "is_resolved": True,
        })
        ticket = self._create_ticket(stage_id=legacy.id)

        self.Stage._migrate_legacy_stages()

        self.assertEqual(ticket.stage_id, self.complete)
        self.assertFalse(legacy.exists())

    def test_migrate_legacy_stage_collapses_adhoc_kanban_column(self):
        # Simulates a stage a user created on the fly via "+ Add a column".
        legacy = self.Stage.create({"name": "Hello", "sequence": 10})
        ticket = self._create_ticket(stage_id=legacy.id)

        self.Stage._migrate_legacy_stages()

        self.assertEqual(ticket.stage_id, self.backlog)
        self.assertFalse(legacy.exists())

    def test_migrate_leaves_canonical_stages_untouched(self):
        self.Stage._migrate_legacy_stages()
        stages = self.Stage.search([], order="sequence, id")
        self.assertEqual(
            stages.mapped("name"), ["Backlog", "In Progress", "Complete"]
        )
