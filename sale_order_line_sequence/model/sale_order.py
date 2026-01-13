# Copyright 2017 ForgeFlow S.L.
# Copyright 2017 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.depends("order_line")
    def _compute_max_line_sequence(self):
        """Allow to know the highest sequence entered in sale order lines.
        Then we add 1 to this value for the next sequence.
        This value is given to the context of the o2m field in the view.
        So when we create new sale order lines, the sequence is automatically
        added as :  max_sequence + 1
        """
        for sale in self:
            sale.max_line_sequence = max(sale.mapped("order_line.sequence") or [0]) + 1

    max_line_sequence = fields.Integer(
        string="Max sequence in lines", compute="_compute_max_line_sequence", store=True
    )

    def _reset_sequence(self):
        for rec in self:
            current_sequence = 1
            section_sequence = 1
            for line in rec.order_line:
                if line.display_type == 'line_section':
                    section_sequence += 1000
                    line.sequence2 = section_sequence
                if line.display_type != 'line_section':
                    if line.section_id:
                        line.sequence2 = line.section_id.sequence2+current_sequence
                    else:
                        line.sequence2 = section_sequence+current_sequence
                    current_sequence += 1
     
    # def create(self, line_values):
    #     seq=1000
    #     for l in line_values['order_line']:
    #         l[2]['sequence2'] = seq 
    #         seq+=1
    #     return super(SaleOrder, self).create(line_values)

    def write(self, line_values):
        res = super(SaleOrder, self).write(line_values)
        self._reset_sequence()
        return res

    def copy(self, default=None):
        return super(SaleOrder, self.with_context(keep_line_sequence=True)).copy(
            default
        )


class AddSection(models.TransientModel):
    _name = 'add.section'
    _description = 'Section'

    order_id = fields.Many2one("sale.order", string="Order")
    product_id = fields.Many2one("product.product", string="Product")
    display_type = fields.Selection([('product','Product'),('section','Section'),('note','Note')], default="product")
    section = fields.Char(string="Section")
    note = fields.Char(string="Note")
    seq = fields.Integer()

    def add_line(self):
        if self.env.context.get('active_id'):
            if self.display_type == 'product':
                line = self.env['sale.order.line'].create({'product_id': self.product_id.id,'name':'aaa','order_id':self.order_id.id,'sequence2':self.seq})
                line.product_id_change()
                next_lines = self.env['sale.order.line'].search([('order_id','=',self.order_id.id),('sequence','>',self.seq),('sequence','<',self.seq+999)])
                for ll in next_lines:
                    ll.sequence2 = self.seq+1
            if self.display_type == 'section':
                line = self.env['sale.order.line'].create({'name':self.section,'order_id':self.order_id.id,'display_type':'line_section','sequence2':self.seq-1})
            if self.display_type == 'note':
                line = self.env['sale.order.line'].create({'name':self.note,'order_id':self.order_id.id,'display_type':'line_note','sequence2':self.seq-1})

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"


    # re-defines the field to change the default
    sequence = fields.Integer(
        help="Gives the sequence of this line when displaying the sale order.",
        related="sequence2",
        store=True,
    )

    # displays sequence on the order line
    sequence2 = fields.Integer(
        help="Shows the sequence of this line in the sale order.",
        #related="sequence",
        string="Line Number",
        default=0,
        #readonly=False,
        #store=True,
    )
    section_id = fields.Many2one('sale.order.line', string="Section")

    @api.model
    def create(self, values):
        line = super(SaleOrderLine, self).create(values)
        # We do not reset the sequence if we are copying a complete sale order
        if self.env.context.get("keep_line_sequence"):
            line.order_id._reset_sequence()
        return line

    def action_add_section(self):
        return {
            'name': _('Add Section'),
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'add.section',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'domain':[('display_type', '=', 'line_section'), ('order_id', '=', self.order_id)],
            'context': {'default_order_id': self.order_id.id,'default_seq':self.sequence2+1}
        }        
