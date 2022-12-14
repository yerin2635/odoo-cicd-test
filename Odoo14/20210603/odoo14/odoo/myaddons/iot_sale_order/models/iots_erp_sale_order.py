from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # original_cost 為 import 暫存用
    original_cost = fields.Float()
    standard_price = fields.Float(string='Cost', compute='_compute_standard_price', store=True, copy=True)
    view_cost = fields.Float(compute='_show_view_cost', store=True, copy=True)
    # standard_price = fields.Float(string='Cost', store=True, copy=True)

    # import_check 為 import 標籤，用於確認輸入方式，以辨別成本
    import_check = fields.Boolean(default=False)
    
    standard_price_subtotal = fields.Monetary(compute='_compute_cost_amount', string='Cost Subtotal', readonly=True, store=True)

    # 成本預設為產品成本，當變動時不改變他的值
    # 新增的產品，帶入預設的值
    @api.onchange('product_id')
    def _show_view_cost(self):
        for line in self:
            # 新的sale_order_line
            if type(line.id) != int:
                line.standard_price = line.product_id.standard_price
    
    # import file 將 temp_cost 更新到 standard_price
    @api.depends('original_cost')
    def _compute_standard_price(self):
        for line in self:
            # 確認是 import 進來的再改變
            if line.original_cost:
                line.standard_price = line.original_cost

    @api.depends('standard_price', 'product_uom_qty')
    def _compute_cost_amount(self):
        """
        Compute the cost amounts of the SO line.
        """
        for line in self:
            price = line.standard_price * line.product_uom_qty
            line.update({
                'standard_price_subtotal': price,
            })

    # # 測試 cron 排程
    # def _init_original_cost(self):
    #     for line in self.env['sale.order.line'].search([]):
    #         line.original_cost = 100.0

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cost_amount = fields.Monetary(compute='_compute_cost_amount', string='Cost Amount', readonly=True, store=True)
    gross_profit_margin = fields.Float(compute='_compute_gp', string='GP(%)', readonly=True, store=True)

    @api.depends('order_line.standard_price_subtotal')
    def _compute_cost_amount(self):
        for order in self:
            print('---------------------------')
            print(f"lang_active: {self.env['res.lang'].search([('name', '=', 'Chinese (Traditional) / 繁體中文'), ('active', '=', False)])}")
            print(f"lang_active: {self.env['res.lang'].search([('name', '=', 'English (US)')]).name}")
            self.env['res.lang'].search([('name', '=', 'Chinese (Traditional) / 繁體中文')]).write({'active': True})
            print(f"lang_active: {self.env['res.lang'].browse([12]).active}")
            print(f"lang_id: {self.env['res.lang'].browse([12]).id}")
            print(f"lang_id: {self.env['res.lang'].browse([12]).name}")
            print(f"lang: {self.env['res.lang'].search([('name', '=', 'Chinese (Traditional) / 繁體中文')]).active}")
            print('---------------------------')
            cost_amount = 0.0
            for line in order.order_line:
                cost_amount += line.standard_price_subtotal
            order.update({
                'cost_amount': cost_amount,
            })

    # 回傳毛利修改為百分位數，取到小數點後第二位(float預設即取兩位)
    @api.depends('cost_amount', 'amount_untaxed', 'discount_total')
    def _compute_gp(self):
        for order in self:
            gross_profit_margin = 0.0
            if order.discount_total:
                gross_profit_margin = (order.discount_total - order.cost_amount) / order.discount_total
            elif order.amount_untaxed != 0.0:
                    gross_profit_margin = (order.amount_untaxed - order.cost_amount) / order.amount_untaxed

            order.update({
                'gross_profit_margin': gross_profit_margin*100
            })            

    # 覆蓋原始的 合計(未稅) 稅金(5%) 含稅總計，計算方式
    # sale models sale.py, line 39-53，直接貼過來當作覆蓋
    # 如果有放優惠價格那就更新 稅金 含稅總計；沒有優惠價格照原本的計算方式
    @api.depends('order_line.price_total', 'discount_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = amount_total = float(0)
            if order.discount_total:
                for line in order.order_line:
                    amount_untaxed += line.price_subtotal
                amount_total = order.discount_total
                if order.currency_id.name == 'TWD':
                    amount_tax = order.discount_total * 0.05
                    amount_total = order.discount_total * 1.05
            else:
                for line in order.order_line:
                    amount_untaxed += line.price_subtotal
                    amount_tax += line.price_tax
                    amount_total = amount_untaxed + amount_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_total,
            })
