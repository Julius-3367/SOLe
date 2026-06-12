# -*- coding: utf-8 -*-
from odoo.fields import Command
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestSupportProjectStageMigration(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Task = cls.env["project.task"]
        cls.Type = cls.env["project.task.type"]
        cls.project = cls.env.ref("sole_support_project.project_support_duties")
        cls.task_backlog = cls.env.ref("sole_support_project.task_stage_backlog")
        cls.task_in_progress = cls.env.ref("sole_support_project.task_stage_in_progress")
        cls.task_complete = cls.env.ref("sole_support_project.task_stage_complete")

    def _create_task(self, **kwargs):
        vals = {"name": "Migration test task", "project_id": self.project.id}
        vals.update(kwargs)
        return self.Task.create(vals)

    def test_migrate_moves_open_legacy_stage_tasks_to_backlog(self):
        legacy = self.Type.create({
            "name": "New",
            "sequence": 5,
            "fold": False,
            "project_ids": [Command.set([self.project.id])],
        })
        task = self._create_task(stage_id=legacy.id)

        self.Task._migrate_legacy_support_task_stages()

        self.assertEqual(task.stage_id, self.task_backlog)
        self.assertFalse(legacy.exists())

    def test_migrate_moves_folded_legacy_stage_tasks_to_complete(self):
        legacy = self.Type.create({
            "name": "Resolved",
            "sequence": 40,
            "fold": True,
            "project_ids": [Command.set([self.project.id])],
        })
        task = self._create_task(stage_id=legacy.id)

        self.Task._migrate_legacy_support_task_stages()

        self.assertEqual(task.stage_id, self.task_complete)
        self.assertFalse(legacy.exists())

    def test_migrate_moves_unstaged_tasks_to_backlog(self):
        task = self._create_task(stage_id=False)

        self.Task._migrate_legacy_support_task_stages()

        self.assertEqual(task.stage_id, self.task_backlog)

    def test_migrate_detaches_but_keeps_legacy_stage_shared_with_other_project(self):
        other_project = self.env["project.project"].create({"name": "Other project"})
        legacy = self.Type.create({
            "name": "Ad-hoc",
            "sequence": 15,
            "fold": False,
            "project_ids": [Command.set([self.project.id, other_project.id])],
        })
        task = self._create_task(stage_id=legacy.id)

        self.Task._migrate_legacy_support_task_stages()

        self.assertEqual(task.stage_id, self.task_backlog)
        self.assertTrue(legacy.exists())
        self.assertEqual(legacy.project_ids, other_project)

    def test_migrate_leaves_canonical_stages_untouched(self):
        task = self._create_task(stage_id=self.task_in_progress.id)

        self.Task._migrate_legacy_support_task_stages()

        self.assertEqual(task.stage_id, self.task_in_progress)
        types = self.Type.search([("project_ids", "in", self.project.ids)], order="sequence")
        self.assertEqual(
            types.mapped("name"), ["Backlog", "In Progress", "Complete"]
        )
