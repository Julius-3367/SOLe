# -*- coding: utf-8 -*-
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestAddRecipientsWizard(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["sole.sms.provider"].create({
            "name": "Test Provider",
            "provider_type": "generic_http",
            "api_url": "https://example.test/sms",
            "sender_id": "TESTSENDER",
        })
        cls.batch = cls.env["sole.sms.batch"].create({
            "name": "Test Campaign",
            "provider_id": cls.provider.id,
            "message": "Hello {customer_name}",
        })

        # All test contacts share this tag so filter-mode tests only ever
        # match contacts created by this test, never pre-existing demo data.
        cls.tag_test = cls.env["res.partner.category"].create({"name": "SMS Wizard Test"})
        cls.tag_vip = cls.env["res.partner.category"].create({"name": "SMS Wizard VIP"})

        cls.customer_with_phone = cls.env["res.partner"].create({
            "name": "Alice Customer",
            "phone": "0712345678",
            "customer_rank": 1,
            "category_id": [(6, 0, [cls.tag_test.id, cls.tag_vip.id])],
        })
        cls.customer_with_phone_only = cls.env["res.partner"].create({
            "name": "Bob Customer",
            "phone": "0798765432",
            "customer_rank": 1,
            "category_id": [(6, 0, [cls.tag_test.id])],
        })
        cls.customer_no_phone = cls.env["res.partner"].create({
            "name": "Carol Customer",
            "customer_rank": 1,
            "category_id": [(6, 0, [cls.tag_test.id])],
        })
        cls.non_customer_with_phone = cls.env["res.partner"].create({
            "name": "Dave Vendor",
            "phone": "0711111111",
            "customer_rank": 0,
            "category_id": [(6, 0, [cls.tag_test.id])],
        })

    def test_filter_customers_only_skips_non_customers_and_no_phone(self):
        wizard = self.env["sole.sms.add.recipients.wizard"].create({
            "batch_id": self.batch.id,
            "source": "filter",
            "customers_only": True,
            "category_ids": [(6, 0, [self.tag_test.id])],
        })

        wizard.action_add()

        phones = self.batch.line_ids.mapped("phone")
        self.assertIn("0712345678", phones)
        self.assertIn("0798765432", phones)
        self.assertNotIn("0711111111", phones, "non-customers must be excluded")
        self.assertEqual(
            len(self.batch.line_ids), 2,
            "the contact without a phone number must be skipped",
        )

    def test_added_lines_link_partner_and_name_for_placeholder(self):
        wizard = self.env["sole.sms.add.recipients.wizard"].create({
            "batch_id": self.batch.id,
            "source": "manual",
            "partner_ids": [(6, 0, [self.customer_with_phone.id])],
        })

        wizard.action_add()

        line = self.batch.line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.partner_id, self.customer_with_phone)
        self.assertEqual(line.name, "Alice Customer")
        self.assertEqual(line.phone, "0712345678")

    def test_skip_existing_avoids_duplicate_phone_numbers(self):
        # Pre-seed the batch with a line for the same number, in a different format.
        self.env["sole.sms.batch.line"].create({
            "batch_id": self.batch.id,
            "phone": "+254712345678",
            "name": "Already Here",
        })

        wizard = self.env["sole.sms.add.recipients.wizard"].create({
            "batch_id": self.batch.id,
            "source": "filter",
            "customers_only": True,
            "category_ids": [(6, 0, [self.tag_test.id])],
            "skip_existing": True,
        })
        wizard.action_add()

        phones = self.batch.line_ids.mapped("phone")
        # Alice's 0712345678 normalizes to the same number as +254712345678
        # and must not be added a second time.
        self.assertEqual(
            len(self.batch.line_ids), 2,
            "duplicate normalized phone number must not be re-added",
        )
        self.assertIn("0798765432", phones)

    def test_category_filter_limits_results(self):
        wizard = self.env["sole.sms.add.recipients.wizard"].create({
            "batch_id": self.batch.id,
            "source": "filter",
            "customers_only": True,
            "category_ids": [(6, 0, [self.tag_vip.id])],
        })
        wizard.action_add()

        self.assertEqual(len(self.batch.line_ids), 1)
        self.assertEqual(self.batch.line_ids.partner_id, self.customer_with_phone)

    def test_compute_counts_reflects_matches(self):
        wizard = self.env["sole.sms.add.recipients.wizard"].create({
            "batch_id": self.batch.id,
            "source": "filter",
            "customers_only": True,
            "category_ids": [(6, 0, [self.tag_test.id])],
        })

        self.assertEqual(wizard.match_count, 3, "Alice, Bob and Carol are customers in this tag")
        self.assertEqual(wizard.with_phone_count, 2, "Carol has no phone number")
