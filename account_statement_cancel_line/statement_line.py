# -*- coding: utf-8 -*-
###############################################################################
#                                                                             #
#   Author: Leonardo Pistone
#   Copyright 2014 Camptocamp SA
#                                                                             #
#   This program is free software: you can redistribute it and/or modify      #
#   it under the terms of the GNU Affero General Public License as            #
#   published by the Free Software Foundation, either version 3 of the        #
#   License, or (at your option) any later version.                           #
#                                                                             #
#   This program is distributed in the hope that it will be useful,           #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of            #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the             #
#   GNU Affero General Public License for more details.                       #
#                                                                             #
#   You should have received a copy of the GNU Affero General Public License  #
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.     #
#                                                                             #
###############################################################################
"""Account Statement Cancel Line."""

from openerp.osv import fields, orm

from openerp.tools.translate import _


class StatementLine(orm.Model):

    """Add a state to the statement line."""

    _inherit = "account.bank.statement.line"

    _columns = {
        'state': fields.selection(
            [('draft', 'Draft'), ('confirmed', 'Confirmed')],
            'State',
            readonly=True,
            required=True
        ),
    }

    _defaults = {
        'state': 'draft',
    }

    def confirm(self, cr, uid, ids, context=None):
        """Confirm just one statement line, return true.

        The module account_banking does have a similar method, but at the
        moment it uses a different logic (for example, it uses vouchers, where
        the bank-statement-reconcile branch does not).

        """
        if context is None:
            context = {}
        local_ctx = context.copy()
        # if account_constraints is installed, we need to tell it that moves
        # are being created by a statement, which is OK.
        # The module tries to prevent direct changes to the moves created by
        # bank statements.
        local_ctx['from_parent_object'] = True
        statement_pool = self.pool.get('account.bank.statement')

        for st_line in self.browse(cr, uid, ids, context):
            if st_line.state != 'draft':
                continue
            st = st_line.statement_id
            curr_id = st.journal_id.company_id.currency_id.id

            st_number = st.name
            st_line_number = statement_pool.get_next_st_line_number(
                cr, uid, st_number, st_line, context)

            # We pass the local_ctx so that account_constraints allows us to
            # work on the moves generated by the bank statement
            statement_pool.create_move_from_st_line(
                cr,
                uid,
                st_line.id,
                curr_id,
                st_line_number,
                local_ctx)
            self.write(cr, uid, st_line.id, {
                'state': 'confirmed'
            }, context)
        return True

    def cancel(self, cr, uid, ids, context=None):
        """Cancel one statement line, return True.

        This is again similar to the method cancel in the account_banking
        module.

        """
        if context is None:
            context = {}
        local_ctx = context.copy()
        # if account_constraints is installed, we need to tell it that moves
        # are being created by a statement, which is OK.
        # The module tries to prevent direct changes to the moves created by
        # bank statements.
        local_ctx['from_parent_object'] = True

        move_pool = self.pool.get('account.move')

        set_draft_ids = []
        move_unlink_ids = []
        # harvest ids for various actions
        for st_line in self.browse(cr, uid, ids, context):
            if st_line.state != 'confirmed':
                continue

            for move in st_line.move_ids:
                # We allow for people canceling and removing
                # the associated payments, which can lead to confirmed
                # statement lines without an associated move
                move_unlink_ids.append(move.id)
                # do we need to check that?
                if move.state != 'draft':
                    raise orm.except_orm(
                        _('Confirmed Journal Entry'),
                        _('You cannot delete a confirmed Statement Line '
                          'associated to a Journal Entry that is posted.'))
            set_draft_ids.append(st_line.id)

        move_pool.button_cancel(
            cr, uid, move_unlink_ids, context=context)

        move_pool.unlink(cr, uid, move_unlink_ids, context=local_ctx)
        self.write(
            cr, uid, set_draft_ids, {'state': 'draft'}, context=context)
        return True

    def unlink(self, cr, uid, ids, context=None):
        """Don't allow deletion of a confirmed statement line. Return super."""
        if type(ids) is int:
            ids = [ids]
        for line in self.browse(cr, uid, ids, context=context):
            if line.state == 'confirmed':
                raise orm.except_orm(
                    _('Confirmed Statement Line'),
                    _("You cannot delete a confirmed Statement Line"
                      ": '%s'") % line.name)
        return super(StatementLine, self).unlink(
            cr, uid, ids, context=context)
