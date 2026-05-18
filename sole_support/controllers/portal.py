# -*- coding: utf-8 -*-
"""
Customer portal controller for SOLe Support Center.

Routes:
  GET  /support              — list user's tickets
  GET  /support/new          — new ticket form
  POST /support/new          — submit new ticket
  GET  /support/<int:ticket_id>  — view ticket details
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
