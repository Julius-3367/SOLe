# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class Document(models.Model):
    _name = 'document.document'
    _description = 'Document'
    _parent_name = 'parent_id'
    _parent_store = True
    _parent_order = 'sequence, name'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    parent_path = fields.Char(index=True)

    # ── Core ─────────────────────────────────────────────────────────────────
    active = fields.Boolean(default=True, tracking=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer()
    name = fields.Char('Title', required=True, tracking=True)
    description = fields.Text('Summary')
    content = fields.Html('Content', sanitize=True)

    # ── Hierarchy ─────────────────────────────────────────────────────────────
    parent_id = fields.Many2one(
        'document.document', 'Parent Folder',
        ondelete='cascade', index=True,
        domain="[('id', '!=', id)]",
        tracking=True,
    )
    child_ids = fields.One2many('document.document', 'parent_id', string='Children')
    child_count = fields.Integer(compute='_compute_child_count', string='Sub-documents')

    # ── Metadata ──────────────────────────────────────────────────────────────
    user_id = fields.Many2one(
        'res.users', 'Owner',
        default=lambda self: self.env.user,
        index=True, tracking=True,
    )
    tag_ids = fields.Many2many('document.tag', string='Tags')

    # ── Favorites ─────────────────────────────────────────────────────────────
    favorite_user_ids = fields.Many2many(
        'res.users', 'document_favorite_rel', 'document_id', 'user_id',
        string='Favorited By', copy=False,
    )
    is_favorite = fields.Boolean(
        compute='_compute_is_favorite',
        inverse='_inverse_is_favorite',
        search='_search_is_favorite',
        string='Favorite',
    )

    # ── Attachments ───────────────────────────────────────────────────────────
    attachment_count = fields.Integer(compute='_compute_attachment_count', string='Files')

    name_parent_uniq = models.Constraint(
        'UNIQUE(parent_id, name)',
        'A document with this name already exists in this folder.',
    )

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('Cannot set a document as its own ancestor.'))

    # ── Computed fields ───────────────────────────────────────────────────────

    def _compute_child_count(self):
        count_data = self.env['document.document']._read_group(
            [('parent_id', 'in', self.ids)],
            ['parent_id'],
            ['__count'],
        )
        mapped = {parent.id: count for parent, count in count_data}
        for record in self:
            record.child_count = mapped.get(record.id, 0)

    def _compute_is_favorite(self):
        for doc in self:
            doc.is_favorite = self.env.user in doc.favorite_user_ids

    def _inverse_is_favorite(self):
        for doc in self:
            if doc.is_favorite:
                doc.sudo().favorite_user_ids |= self.env.user
            else:
                doc.sudo().favorite_user_ids -= self.env.user

    def _search_is_favorite(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise UserError(_('Operation not supported.'))
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('favorite_user_ids', 'in', [self.env.uid])]
        return [('favorite_user_ids', 'not in', [self.env.uid])]

    def _compute_attachment_count(self):
        count_data = self.env['ir.attachment']._read_group(
            [('res_model', '=', 'document.document'), ('res_id', 'in', self.ids)],
            ['res_id'],
            ['__count'],
        )
        mapped = {res_id: count for res_id, count in count_data}
        for doc in self:
            doc.attachment_count = mapped.get(doc.id, 0)

    def _compute_display_name(self):
        if not self.env.context.get('display_full_name'):
            return super()._compute_display_name()
        for record in self:
            parts = []
            current = record
            while current:
                parts.append(current.name or '')
                current = current.parent_id
            record.display_name = ' / '.join(reversed(parts))

    # ── ORM ──────────────────────────────────────────────────────────────────

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = _('%s (copy)') % (self.name or '')
        return super().copy(default)

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_open_children(self):
        """Open this document's children in kanban/list/form."""
        self.ensure_one()
        return {
            'name': self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'document.document',
            'view_mode': 'kanban,list,form',
            'domain': [('parent_id', '=', self.id)],
            'context': dict(
                self.env.context,
                default_parent_id=self.id,
            ),
        }

    def action_toggle_favorite(self):
        self.ensure_one()
        self.is_favorite = not self.is_favorite

    def action_open_attachments(self):
        self.ensure_one()
        return {
            'name': _('Files — %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [('res_model', '=', 'document.document'), ('res_id', '=', self.id)],
            'context': {
                'default_res_model': 'document.document',
                'default_res_id': self.id,
            },
        }
