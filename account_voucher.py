# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2014 RyePDX LLC (<http://ryepdx.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

from openerp import netsvc
from openerp.osv import osv, fields

class account_voucher(osv.osv):
    '''
    This represents payment lines in an account journal and on an invoice.
    This particular variation of the account.voucher model adds a reference
    to a giftcard to payment lines, allowing us to keep track of how gift
    cards have been used, as well as which gift card was used on any given
    payment line.

    '''
    
    _inherit = 'account.voucher'
    
    _columns = {
        'origin': fields.char('Origin', size=16, help='Mentions the reference of Sale/Purchase document'),
        'giftcard_id': fields.many2one('gift.card', 'Gift Card', { 'required': False }) 
    }

    def check_card_transaction(self, vouchers):
        '''
        Makes sure the giftcards used on the passed-in payment lines have enough
        on them to actually cover the charges they are supposed to cover.
        Raises an error if they don't.

        '''
        
        # We want to grab all the vouchers with gift cards and make an index
        # of their gift cards' balances, keyed off the gift card numbers, to
        # facilitate checking those balances against the charges against them.
        # We're doing it this way because it's possible for a single gift card
        # to be used on multiple account_vouchers, so we can't just check gift
        # card balances against the account_voucher they happen to belong to.
        vouchers_with_giftcards = [
            voucher for voucher in vouchers if voucher.giftcard_id
        ]
        giftcards = dict([(voucher.giftcard_id.number, voucher.giftcard_id.value)
            for voucher in vouchers_with_giftcards
        ])

        # Doing the balance checks we prepped for above.
        # Raises an exception if a gift card doesn't have enough of a balance.
        # This is the only way to bubble error messages up to the user in OERP.
        for voucher in vouchers_with_giftcards:
            giftcards[voucher.giftcard_id.number] -= voucher.amount
            if giftcards[voucher.giftcard_id.number] <= 0:
                raise osv.except_osv(_('Error'), _("Gift card has insufficient funds!"))
        return True

    def authorize_card(self, cr, uid, ids, context=None):
        '''
        Subtracts the invoice line charges from the gift card balances after
        first checking to make sure that each gift card has enough on it to
        actually cover the charges being attempted against it.
        
        '''

        # Make sure the requested charges can actually be made
        # against the given gift cards.
        vouchers = [self.browse(cr, uid, res_id, context) for res_id in ids]
        self.check_card_transaction(vouchers)
        giftcard_orm = self.pool.get('gift.card')

        # Subtract charges from gift cards.
        for voucher in filter(lambda voucher: voucher.giftcard_id, vouchers):
            giftcard_orm.write(cr, uid, [voucher.giftcard_id.id], {
                'value': voucher.giftcard_id.value - voucher.amount
            })

        # Mark the payment lines as processed/validated.
        wf_service = netsvc.LocalService("workflow")

        for res_id in ids:
            wf_service.trg_validate(uid, 'account.voucher', res_id, 'proforma_voucher', cr)

        return True

    def proforma_voucher(self, cr, uid, ids, context=None):
        self.authorize_card(cr, uid, ids, context=context)
        return super(account_voucher, self).proforma_voucher(cr, uid, ids, context=context)
    
account_voucher()