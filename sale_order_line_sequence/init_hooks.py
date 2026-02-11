# Copyright 2017 ForgeFlow S.L.
# Copyright 2017 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import SUPERUSER_ID, api


def post_init_hook(env: api.Environment):
    """Recompute sale order line sequences after module installation.

    Since Odoo 16.0+, post-init hooks receive an Environment instead of
    ``cr, pool``. This version is adapted for Odoo 19.0.
    """
    sale_orders = env["sale.order"].with_user(SUPERUSER_ID).search([])
    sale_orders._reset_sequence()
