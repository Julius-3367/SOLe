# -*- coding: utf-8 -*-
"""
Customer portal controller for SOLe Support Center.

Routes:
  GET  /support                  — list user's tickets          (login required)
  GET  /support/new              — new ticket form              (login required)
  POST /support/new              — submit new ticket            (login required)
  GET  /support/<int:ticket_id>  — view ticket details          (login required)
  GET  /support/request          — public request form          (open to anyone)
  POST /support/request          — public submission            (open to anyone)

The public route exists so visitors who have no portal account can still raise
a ticket. It is protected by reCAPTCHA and creates a res.partner from the email
address given, because sole.support.ticket.partner_id is required.
"""
import logging

from odoo import _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request, route

try:
    from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
except ImportError:
    from odoo.addons.portal.controllers.mail import CustomerPortal
    portal_pager = None

_logger = logging.getLogger(__name__)


class SoleSupportPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "ticket_count" in counters:
            partner = request.env.user.partner_id
            values["ticket_count"] = (
                request.env["sole.support.ticket"]
                .sudo()
                .search_count([("partner_id", "=", partner.id)])
            )
        return values

    @route(["/support", "/support/page/<int:page>"], type="http", auth="user", website=True)
    def portal_tickets(self, page=1, **kwargs):
        partner = request.env.user.partner_id
        Ticket = request.env["sole.support.ticket"].sudo()
        domain = [("partner_id", "=", partner.id)]
        ticket_count = Ticket.search_count(domain)
        step = 10
        pager = None
        if portal_pager:
            pager = portal_pager(
                url="/support",
                total=ticket_count,
                page=page,
                step=step,
            )
        tickets = Ticket.search(
            domain,
            order="create_date desc",
            limit=step,
            offset=pager["offset"] if pager else 0,
        )
        return request.render("sole_support.portal_ticket_list", {
            "tickets": tickets,
            "pager": pager,
            "page_name": "support",
        })

    @route(["/support/new"], type="http", auth="user", website=True, methods=["GET", "POST"])
    def portal_new_ticket(self, **post):
        categories = request.env["sole.support.category"].sudo().search([("is_active", "=", True)])
        if request.httprequest.method == "POST":
            partner = request.env.user.partner_id
            subject = post.get("subject", "").strip()
            description = post.get("description", "").strip()
            category_id = int(post.get("category_id", 0)) or False
            if subject:
                request.env["sole.support.ticket"].sudo().create({
                    "subject": subject,
                    "description": description,
                    "partner_id": partner.id,
                    "category_id": category_id,
                    "is_portal": True,
                })
                return request.redirect("/support?message=created")
        return request.render("sole_support.portal_new_ticket", {
            "categories": categories,
            "page_name": "support",
        })

    @route(["/support/<int:ticket_id>"], type="http", auth="user", website=True)
    def portal_ticket_detail(self, ticket_id, **kwargs):
        partner = request.env.user.partner_id
        ticket = request.env["sole.support.ticket"].sudo().browse(ticket_id)
        if not ticket.exists() or ticket.partner_id.id != partner.id:
            return request.redirect("/support")
        return request.render("sole_support.portal_ticket_detail", {
            "ticket": ticket,
            "page_name": "support",
        })

    # ── Public submission ─────────────────────────────────────────────────────

    def _support_recaptcha_passed(self, post):
        """Whether an anonymous submission clears reCAPTCHA.

        Returns True when no site keys are configured, so the form keeps
        working before reCAPTCHA is set up. Once keys are entered under
        Settings > Website > reCAPTCHA, verification becomes real.
        """
        try:
            result = request.env["ir.http"]._verify_recaptcha_token(
                post.get("recaptcha_token_response"), action="support_request"
            )
        except Exception:
            # Never let a captcha outage swallow a genuine support request.
            _logger.exception("reCAPTCHA verification errored; allowing submission")
            return True
        if result not in ("is_human", "is_admin", "no_secret"):
            _logger.info("Support request rejected by reCAPTCHA: %s", result)
            return False
        return True

    def _support_find_or_create_partner(self, name, email, phone):
        """Match an existing contact on email, or create one."""
        Partner = request.env["res.partner"].sudo()
        partner = Partner.search([("email", "=ilike", email)], limit=1)
        if partner:
            # Fill in details we did not have before, never overwrite them.
            updates = {}
            if phone and not partner.phone:
                updates["phone"] = phone
            if updates:
                partner.write(updates)
            return partner
        return Partner.create({
            "name": name or email,
            "email": email,
            "phone": phone or False,
        })

    @route(["/support/request"], type="http", auth="public", website=True,
           methods=["GET", "POST"], sitemap=True)
    def public_ticket_request(self, **post):
        """Ticket submission open to visitors without a portal account."""
        Config = request.env["ir.config_parameter"].sudo()
        is_public = request.env.user._is_public()
        values = {
            "categories": request.env["sole.support.category"].sudo().search(
                [("is_active", "=", True)]
            ),
            "page_name": "support_request",
            "is_public": is_public,
            "recaptcha_site_key": Config.get_param("recaptcha_public_key"),
            "post": post,
            "error": None,
        }

        if request.httprequest.method != "POST":
            return request.render("sole_support.portal_public_ticket", values)

        subject = (post.get("subject") or "").strip()
        description = (post.get("description") or "").strip()
        category_id = int(post.get("category_id") or 0) or False

        if is_public:
            name = (post.get("contact_name") or "").strip()
            email = (post.get("email") or "").strip()
            phone = (post.get("phone") or "").strip()
            if not subject or not email:
                values["error"] = _("Please give your email address and a subject.")
                return request.render("sole_support.portal_public_ticket", values)
            if not self._support_recaptcha_passed(post):
                values["error"] = _(
                    "We could not confirm that you are a person. Please try again."
                )
                return request.render("sole_support.portal_public_ticket", values)
            partner = self._support_find_or_create_partner(name, email, phone)
        else:
            if not subject:
                values["error"] = _("Please give a subject.")
                return request.render("sole_support.portal_public_ticket", values)
            partner = request.env.user.partner_id
            email = partner.email or ""
            phone = partner.phone or ""

        ticket = request.env["sole.support.ticket"].sudo().create({
            "subject": subject,
            "description": description,
            "partner_id": partner.id,
            "category_id": category_id,
            "email": email or False,
            "phone": phone or False,
            "is_portal": True,
        })

        if is_public:
            return request.render("sole_support.portal_public_ticket_thanks", {
                "ticket": ticket,
                "page_name": "support_request",
            })
        return request.redirect("/support?message=created")
