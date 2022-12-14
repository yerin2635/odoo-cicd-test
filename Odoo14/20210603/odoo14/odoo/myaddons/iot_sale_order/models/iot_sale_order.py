from odoo import api, fields, models, _
import logging
from odoo.exceptions import ValidationError, UserError
from odoo.addons.base.models.ir_sequence import _select_nextval, _update_nogap
from datetime import date as datetime_date, timedelta

# 初始化 log 設定
_logger = logging.getLogger(__name__)

class PaymentTermsMapping(models.Model):
    _name = 'payment.terms.mapping'
    _description = 'Payment Terms Mapping'

    name = fields.Char(size=32)
    code = fields.Char(size=16)
    rel = fields.One2many('invoice.notification', 'payment_terms')


class PaymentTimesMapping(models.Model):
    _name = 'payment.times.mapping'
    _description = 'Payment Times Mapping'

    name = fields.Char(size=32)
    code = fields.Char(size=16)
    rel = fields.One2many('invoice.notification', 'payment_times')

class PaymentMethodMapping(models.Model):
    _name = 'payment.method.mapping'
    _description = 'Payment Method Mapping'

    code = fields.Char(size=16)
    name = fields.Char(size=32)
    payment_days = fields.Char(size=16)
    ticket_days = fields.Char(size=16)
    rel = fields.One2many('invoice.notification', 'payment_method')

    # 覆寫函數，更改many2one顯示值的名稱及返回ID
    def name_get(self):    
        result = []
        for record in self:
            name = record.code
            result.append((record.id, name))
        return result

    # 覆寫name_search函數，把code欄位也加入搜尋的目標中
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('code', operator, name)]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)


class IotSaleOrder(models.Model):
    _name = 'iot.sale.order'
    _description = 'Iot Sale Order'

    name = fields.Char(string='Order Reference', required=True, copy=False,
                       states={'draft': [('readonly', False)]}, index=True, default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, tracking=3, default='draft')

    # 客戶國名
    customer_country = fields.Many2one("res.country", string="客戶國名", store=True)
    # 客戶名稱
    customer_name = fields.Many2one("res.partner", domain="[('customer_rank', '=', 1)]", string="客戶名稱", store=True)
    # 案名
    project_name = fields.Char(size=128, string="案名")
    # 工令號
    work_order_number = fields.Char(size=32, string="工令號")
    # 客戶編號
    customer_number = fields.Char(size=32, string="客戶編號", related="customer_name.vat", force_save="1", store=True)
    # 簽約/開工日
    signing_date = fields.Datetime(string="簽約/開工日")
    # 預定完工日
    completion_day = fields.Datetime(string="預定完工日")
    # 業務代表與人員資訊同步
    business_representative = fields.Char(size=16, string="業務代表", default=lambda self: self.env.user.name)
    # 業務員編號
    business_representative_id = fields.Char(size=16, string="業務員編號", default=lambda self: self.env.user.employee_serial_number)
    # 業務電話分機
    business_representative_phone = fields.Char(size=16, string="業務電話分機", default=lambda self: self.env.user.employee_tel)
    # 計畫主持人
    program_host = fields.Char(size=32, string="計畫主持人")
    # 員工編號
    program_host_id = fields.Char(size=32, string="員工編號")
    # 簽約當日即期買匯
    spot_foreign_exchange = fields.Char(size=32, string="簽約當日即期買匯")
    # 備註資料
    note = fields.Text()
    # 案件總價
    iot_sale_order_total = fields.Float(string="案件總價(未稅)")
    # 總價與發票、業績金額不符警告
    total_warning = fields.Boolean(default=False)
    # 業績總額(未稅)
    performance_total = fields.Float(string="業績總額(未稅)", compute="_compute_performance_total", store=True, readonly=True)
    # 發票總額(未稅)
    invoice_total = fields.Float(string="發票總額(未稅)", compute="_compute_invoice_total", store=True, readonly=True)

    sale_order_rel = fields.One2many('sale.order', 'sale_iot_sale_order_rel')
    purchase_order_rel = fields.One2many('purchase.order', 'purchase_iot_sale_order_rel')

    sale_order_line_rel = fields.One2many('sale.order.line', 'sale_iot_sale_order_line_rel')
    purchase_order_line_rel = fields.One2many('purchase.order.line', 'purchase_iot_sale_order_line_rel')

    # 此銷貨清單業績紀錄
    # One2many (related model, field for "this" on related model)
    sales_performance_rel = fields.One2many('sales.performance', 'sales_id')

    # 此銷貨清單預定開立發票通知單
    # One2many (related model, field for "this" on related model)
    sales_invoice_rel = fields.One2many('invoice.notification', 'invoice_iot_rel')

    # One2many 對 upload.attachments table
    iot_attachment_rel = fields.One2many('upload.attachments', 'attachment_iot_rel')

    @api.model
    def create(self, vals):
        if 'company_id' in vals:
            self = self.with_company(vals['company_id'])
        if vals.get('name', _('New')) == _('New'):
            seq_date = None
            if 'date_order' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date_order']))
            vals['name'] = self.env['ir.sequence'].next_by_code('iot.sale.order', sequence_date=seq_date) or _('New')
        result = super(IotSaleOrder, self).create(vals)
        # 將報價單資料複製到預定開立發票通知單
        if vals["sale_order_rel"]:
            for order in self.env['sale.order'].browse(vals["sale_order_rel"][0][2]):
                for line in order.order_line:
                    self.env['invoice.notification'].sudo().create({"invoice_iot_rel": result.id, "sale_item": line.name,
                                                                    "sale_order_line_id": int(line.id),
                                                                    "sale_item_amount": line.product_uom_qty,
                                                                    "sale_item_single_price": line.price_unit,
                                                                    "sale_item_currency": int(line.currency_id),
                                                                    "sale_item_single_price_origin": line.price_subtotal})           
        return result

    def write(self, values):
        # 檢查是否為 pdf 檔案；非 pdf 報錯，pdf 繼續上傳動作
        if 'iot_attachment_rel' in values:
            for file in values['iot_attachment_rel']:
                if file[2]:
                    split_filename = file[2]['document_name'].split('.')
                    if split_filename[-1] != 'pdf':
                        raise ValidationError(_(f"附件檔案須為 pdf 格式，{file[2]['document_name']} 為 {split_filename[-1]}。"))
        result = super(IotSaleOrder, self).write(values)
        # 將報價單資料複製到預定開立發票通知單
        if "sale_order_rel" in values.keys():
            for order in self.env['sale.order'].browse(values["sale_order_rel"][0][2]):
                for line in order.order_line:
                    sale_order_line_id_list = list(set([i.sale_order_line_id for i in self.sales_invoice_rel]))
                    if int(line.id) not in sale_order_line_id_list:           
                        self.env['invoice.notification'].sudo().create({"invoice_iot_rel": self.id, "sale_item": line.name, "sale_order_line_id": int(line.id),
                                                                        "sale_item_amount": line.product_uom_qty, "sale_item_single_price": line.price_unit,
                                                                        "sale_item_currency": int(line.currency_id), "sale_item_single_price_origin": line.price_subtotal})           
        return result

    # # 判斷案件總計與發票金額、業績金額是否相等
    # @api.constrains('iot_sale_order_total', 'performance_total', 'invoice_total')
    # def judge_total_value(self):
    #     for rec in self:
    #         if (rec.iot_sale_order_total != rec.performance_total) | (rec.iot_sale_order_total != rec.invoice_total):
    #             raise ValidationError(_(f"請確認案件總價(未稅)、業績總額(未稅)、發票總額(未稅)，三項數值需相等\n案件總價(未稅): {rec.iot_sale_order_total}\n業績總額(未稅): {rec.performance_total}\n發票總額(未稅): {rec.invoice_total}\n"))
    
    # 計算業績總額
    @api.depends('sales_performance_rel.deal_total')
    def _compute_performance_total(self):
        for line in self:
            line.update({
                'performance_total': self.sum_total(line.sales_performance_rel, 'deal_total')
            })

    # 計算發票總額
    @api.depends('sales_invoice_rel.sale_item_single_price_twd')
    def _compute_invoice_total(self):
        for line in self:
            line.update({
                'invoice_total': self.sum_total(line.sales_invoice_rel, 'sale_item_single_price_twd')
            })

    # 加總 function，參數1：各筆 record；參數2：小計數值的 key
    def sum_total(self, data_set, key):
        total_sum = 0
        for line in data_set:
            total_sum += line[key]
        return total_sum

class TransactionTermsDescription1(models.Model):
    _name = 'transaction.terms.description.1'
    _description = 'Transaction Terms Description1'

    name = fields.Char()
    sale_order_id = fields.One2many('sale.order', 'transaction_terms_description_1')
    default_select = fields.Boolean()

class TransactionTermsDescription2(models.Model):
    _name = 'transaction.terms.description.2'
    _description = 'Transaction Terms Description2'

    name = fields.Char()
    sale_order_id = fields.One2many('sale.order', 'transaction_terms_description_2')
    default_select = fields.Boolean()

class TransactionTermsDescription3(models.Model):
    _name = 'transaction.terms.description.3'
    _description = 'Transaction Terms Description3'

    name = fields.Char()
    sale_order_id = fields.One2many('sale.order', 'transaction_terms_description_3')
    default_select = fields.Boolean()

class TransactionTermsDescription4(models.Model):
    _name = 'transaction.terms.description.4'
    _description = 'Transaction Terms Description4'

    name = fields.Char()
    sale_order_id = fields.One2many('sale.order', 'transaction_terms_description_4')
    default_select = fields.Boolean()

class TransactionTermsDescription5(models.Model):
    _name = 'transaction.terms.description.5'
    _description = 'Transaction Terms Description5'

    name = fields.Char()
    sale_order_id = fields.One2many('sale.order', 'transaction_terms_description_5')
    default_select = fields.Boolean()

class TransactionTermsDescription6(models.Model):
    _name = 'transaction.terms.description.6'
    _description = 'Transaction Terms Description6'

    name = fields.Char()
    sale_order_id = fields.One2many('sale.order', 'transaction_terms_description_6')
    default_select = fields.Boolean()

class TransactionTermsDescription7(models.Model):
    _name = 'transaction.terms.description.7'
    _description = 'Transaction Terms Description7'

    name = fields.Char()
    sale_order_id = fields.One2many('sale.order', 'transaction_terms_description_7')
    default_select = fields.Boolean()

class TransactionTermsDescription8(models.Model):
    _name = 'transaction.terms.description.8'
    _description = 'Transaction Terms Description8'

    name = fields.Char()
    sale_order_id = fields.One2many('sale.order', 'transaction_terms_description_8')
    default_select = fields.Boolean()

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sale_iot_sale_order_rel = fields.Many2one('iot.sale.order')

    # 最大值到 99，下一張編號 100 報錯
    max_sequence = 99

    # 交易條件
    transaction_terms_description_1 = fields.Many2one('transaction.terms.description.1', default=1, domain=[("default_select", "=", True)])
    transaction_terms_description_2 = fields.Many2one('transaction.terms.description.2', default=1, domain=[("default_select", "=", True)])
    transaction_terms_description_3 = fields.Many2one('transaction.terms.description.3', default=1, domain=[("default_select", "=", True)])
    transaction_terms_description_4 = fields.Many2one('transaction.terms.description.4', default=1, domain=[("default_select", "=", True)])
    transaction_terms_description_5 = fields.Many2one('transaction.terms.description.5', default=1, domain=[("default_select", "=", True)])
    transaction_terms_description_6 = fields.Many2one('transaction.terms.description.6', default=1, domain=[("default_select", "=", True)])
    transaction_terms_description_7 = fields.Many2one('transaction.terms.description.7', default=1, domain=[("default_select", "=", True)])
    transaction_terms_description_8 = fields.Many2one('transaction.terms.description.8', default=1, domain=[("default_select", "=", True)])
    transaction_terms_description_char_1 = fields.Char(related='transaction_terms_description_1.name', store=True)
    transaction_terms_description_char_2 = fields.Char(related='transaction_terms_description_2.name', store=True)
    transaction_terms_description_char_3 = fields.Char(related='transaction_terms_description_3.name', store=True)
    transaction_terms_description_char_4 = fields.Char(related='transaction_terms_description_4.name', store=True)
    transaction_terms_description_char_5 = fields.Char(related='transaction_terms_description_5.name', store=True)
    transaction_terms_description_char_6 = fields.Char(related='transaction_terms_description_6.name', store=True)
    transaction_terms_description_char_7 = fields.Char(related='transaction_terms_description_7.name', store=True)
    transaction_terms_description_char_8 = fields.Char(related='transaction_terms_description_8.name', store=True)
    # 業務代碼
    salesperson_number = fields.Char(related="user_id.salesperson_number", store=True, copy=True)

    # 優惠總計
    discount_total = fields.Float()

    # 報價日期
    quote_date = fields.Datetime(string='報價日期')

    # 客戶欄位拆成客戶+聯絡人 先選客戶再選聯絡人
    # 客戶
    customer_company = fields.Many2one(
        'res.partner', string='Company', readonly=True,
        states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        required=True, change_default=True, index=True, tracking=1,
        domain="['&', ('parent_id', '=', False), ('customer_rank', '!=', 0)]")
    # 聯絡人
    customer_contact_person = fields.Many2one(
        'res.partner', string='Contact person', readonly=True,
        states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        required=False, change_default=True, index=True, tracking=1,
        domain="[('parent_id', '=', customer_company)]")

    # 客戶相關資訊，供使用者確認
    customer_street = fields.Char(related='customer_company.street', store=True, force_save="1", copy=True)
    customer_city = fields.Char(related='customer_company.city', store=True, force_save="1", copy=True)
    customer_phone = fields.Char(store=True, copy=True)
    customer_email = fields.Char(store=True, copy=True)

    # 新增稅金欄位，如果幣別非台幣則稅金為0%，此欄位只有顯示該單有無稅金，沒有其他作用
    show_tax_percent = fields.Char(compute='_show_tax_percent', store=True)

    # 新增flag，是否啟用折扣價
    discount_flag = fields.Boolean()

    # 修改選擇報價員的條件(只有業務才能被選為報價員)
    def _default_user_id(self):
        groups = list(self.env.user.groups_id)
        sales_groups = self.env.ref('iot_sale_order.group_sales')
        
        if sales_groups in groups:
            return self.env.user

    user_id = fields.Many2one(
        'res.users', string='Salesperson', index=True, tracking=2, default=_default_user_id,
        domain=lambda self: [('groups_id', 'in', self.env.ref('iot_sale_order.group_sales').id)])

    @api.model
    def create(self, vals):
        # 確認是不是批次輸入進來的資料
        if 'import_file' in self.env.context:
            vals['partner_id'] = vals['customer_company']
        if 'company_id' in vals:
            self = self.with_company(vals['company_id'])
        if vals.get('name', _('New')) == _('New'):
            seq_date = None
            salesperson_number=None            
            # 直接取 salesperson_number 避免只用到該次登入者的序號
            # salesperson_number = vals['salesperson_number']
            salesperson_number = self.env['res.users'].browse([vals['user_id']]).salesperson_number
            # 讀取下一張報價單的編號值
            # print(f"quote_date: {vals['quote_date']}, type of date: {type(vals['quote_date'])}, sale_business_number: {salesperson_number}")
            # print(vals['quote_date'], type(vals['quote_date']))
            next_sequence = self.env['ir.sequence.date_range'].search([('date_from', '=', vals['quote_date']), ('sale_business_number', '=', salesperson_number)]).number_next_actual
            # print(f'next_sequence: {next_sequence}')
            if next_sequence > self.max_sequence:
                raise ValidationError(_(f"每位業務每日報價單編號，不得超過{self.max_sequence}"))
            if 'quote_date' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['quote_date']))
            vals['name'] = self.env['ir.sequence'].sale_next_by_code('seq.sale.order', sequence_date=seq_date ,
                                                                      sale_business_number=salesperson_number) or _('New')
            vals['name'] = salesperson_number + vals['name']
         # Makes sure partner_invoice_id', 'partner_shipping_id' and 'pricelist_id' are defined
        if any(f not in vals for f in ['partner_invoice_id', 'partner_shipping_id', 'pricelist_id']):
            partner = self.env['res.partner'].browse(vals.get('partner_id'))
            addr = partner.address_get(['delivery', 'invoice'])
            vals['partner_invoice_id'] = vals.setdefault('partner_invoice_id', addr['invoice'])
            vals['partner_shipping_id'] = vals.setdefault('partner_shipping_id', addr['delivery'])
            vals['pricelist_id'] = vals.setdefault('pricelist_id', partner.property_product_pricelist.id)

        result = super(SaleOrder, self).create(vals)
        return result
        
    @api.onchange('customer_contact_person', 'customer_company')
    def onchange_customer(self):
        customer_company = self.customer_company
        customer_contact_person = self.customer_contact_person
        if not customer_contact_person or customer_contact_person.parent_id != customer_company:
            self.update({'partner_id': customer_company,
                         'customer_phone': customer_company.phone,
                         'customer_email': customer_company.email,
                         'customer_contact_person': False})
        else:
            self.update({'partner_id': customer_contact_person,
                         'customer_phone': customer_contact_person.phone,
                         'customer_email': customer_contact_person.email})
    # 轉換稅金%數
    @api.depends('currency_id')
    def _show_tax_percent(self):
        for line in self:
            if line.currency_id.name == 'TWD':
                line.update({'show_tax_percent': ' 5%'})
            else:
                line.update({'show_tax_percent': ' 0%'})


    # 覆寫 原生onchange_partner_id，把變更user_id的功能拿掉
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        """
        Update the following fields when the partner is changed:
        - Pricelist
        - Payment terms
        - Invoice address
        - Delivery address
        - Sales Team
        """
        if not self.partner_id:
            self.update({
                'partner_invoice_id': False,
                'partner_shipping_id': False,
                'fiscal_position_id': False,
            })
            return

        self = self.with_company(self.company_id)

        addr = self.partner_id.address_get(['delivery', 'invoice'])
        partner_user = self.partner_id.user_id or self.partner_id.commercial_partner_id.user_id
        values = {
            'pricelist_id': self.partner_id.property_product_pricelist and self.partner_id.property_product_pricelist.id or False,
            'payment_term_id': self.partner_id.property_payment_term_id and self.partner_id.property_payment_term_id.id or False,
            'partner_invoice_id': addr['invoice'],
            'partner_shipping_id': addr['delivery'],
        }
        user_id = partner_user.id
        if not self.env.context.get('not_self_saleperson'):
            user_id = user_id or None

        groups = list(self.env.user.groups_id)
        sales_groups = self.env.ref('iot_sale_order.group_sales')            
        if sales_groups in groups and not user_id:
            user_id = self.env.user.id
            
        if self.user_id.id != user_id:
            values['user_id'] = user_id

        if self.env['ir.config_parameter'].sudo().get_param('account.use_invoice_terms') and self.env.company.invoice_terms:
            values['note'] = self.with_context(lang=self.partner_id.lang).env.company.invoice_terms
        if not self.env.context.get('not_self_saleperson') or not self.team_id:
            values['team_id'] = self.env['crm.team'].with_context(
                default_team_id=self.partner_id.team_id.id
            )._get_default_team_id(domain=['|', ('company_id', '=', self.company_id.id), ('company_id', '=', False)], user_id=user_id)
        self.update(values)


class AttachmentFile(models.Model):
    _name = 'upload.attachments'
    _description = 'Save the attachments'
    _order = 'sequence'
    
    # 新增sequence
    sequence = fields.Integer(string='Sequence', default=10)

    # many2one 對 iot.sale.order table
    attachment_iot_rel = fields.Many2one('iot.sale.order')
    documents = fields.Binary(string="上傳附件")
    document_name = fields.Char(string="檔案名稱")


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    sale_iot_sale_order_line_rel = fields.Many2one(related='order_id.sale_iot_sale_order_rel')
    name = fields.Text(string='Description', required=False)
    sale_product_name = fields.Char(related='product_id.product_tmpl_id.name', store=True)
    # 項次
    sequence_number = fields.Integer()
    # 料號
    sale_default_code = fields.Char(size=128)
    # 牌價
    suggested_price = fields.Float()
    # 折扣價
    discount_price = fields.Float()
    # 備註(20221109-ert)
    order_notification = fields.Char(size=128)

    # 折扣%數
    discount_percentage = fields.Float()
    # 折扣試算結果
    discount_compute = fields.Float(compute='_compute_discount')
    # 是否啟用折扣欄位
    line_discount_flag = fields.Boolean(related='order_id.discount_flag')
    # 覆寫單價欄位
    price_unit = fields.Float('Unit Price', required=True, digits='Product Price',
                              default=0.0, compute='_copy_discount_to_unit_price', store=True)


    # 改寫計算稅金的method，加入幣別，若幣別不為台幣則稅金為0%
    # 覆寫原生method _compute_amount
    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'currency_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        account_tax_search = self.env['account.tax'].search([('name', '=', '0%')])
        if not account_tax_search:
            self.env['account.tax'].create({
                'name': '0%',
                'amount': 0,
                'description': '0%',
                'type_tax_use': 'sale',
                'amount_type': 'percent',
                'active': True,
            })
            account_tax_search = self.env['account.tax'].search([('name', '=', '0%')])
            
        for line in self:
            if line.currency_id.name == 'TWD':
                tax = line.tax_id
                line.update({'tax_id': line.product_id.product_tmpl_id.taxes_id})
            else:
                tax = account_tax_search
                line.update({'tax_id': account_tax_search})
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = tax.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                    'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                    'price_total': taxes['total_included'],
                    'price_subtotal': taxes['total_excluded'],
                })
            if self.env.context.get('import_file', False) and not self.env.user.user_has_groups('account.group_account_manager'):
                line.tax_id.invalidate_cache(['invoice_repartition_line_ids'], [tax.id])


    @api.depends('suggested_price', 'discount_percentage')
    def _compute_discount(self):
        for line in self:
            price = line.suggested_price * (1 - line.discount_percentage)
            line.update({'discount_compute': price})
    @api.depends('discount_price')
    def _copy_discount_to_unit_price(self):
        for line in self:
            if line.line_discount_flag:
                line.update({'price_unit': line.discount_price})
    
    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        if not self.product_uom or not self.product_id:
            self.price_unit = 0.0
            return
        if self.order_id.pricelist_id and self.order_id.partner_id:
            product = self.product_id.with_context(
                lang=self.order_id.partner_id.lang,
                partner=self.order_id.partner_id,
                quantity=self.product_uom_qty,
                date=self.order_id.date_order,
                pricelist=self.order_id.pricelist_id.id,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )

            # self.price_unit = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    purchase_iot_sale_order_rel = fields.Many2one('iot.sale.order')

    sequence = fields.Integer(string='Sequence', default=10)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    _order = 'order_sequence, order_id, sequence, id'

    purchase_iot_sale_order_line_rel = fields.Many2one(related='order_id.purchase_iot_sale_order_rel', store=True)
    default_code = fields.Char(related='product_id.default_code', store=True)
    name = fields.Text(string='Description', required=False)
    
    # Duplicate for not change original purchase data
    purchase_product_name_modify = fields.Char(related='product_id.product_tmpl_id.name_modify', store=True)
    description_modify = fields.Text(compute='_duplicate_description', store=True)
    product_uom_modify = fields.Char(store=True)
    product_qty_modify = fields.Float(compute='_duplicate_qty', store=True)
    price_unit_modify = fields.Float(compute='_duplicate_unit', store=True)
    price_subtotal_modify = fields.Monetary(compute='_duplicate_subtotal', store=True)
   
    order_sequence = fields.Integer(related="order_id.sequence", store=True)

    @api.depends('name')
    def _duplicate_description(self):
        for line in self:
            if not line.description_modify: 
                line.update({
                    'description_modify': line.name,
                })
    
    @api.depends('product_qty')
    def _duplicate_qty(self):
        for line in self:
            if not line.product_qty_modify: 
                line.update({
                    'product_qty_modify': line.product_qty,
                })
    
    @api.depends('price_unit')
    def _duplicate_unit(self):
        for line in self:
            if not line.price_unit_modify: 
                line.update({
                    'price_unit_modify': line.price_unit,
                })

    @api.depends('price_subtotal')
    def _duplicate_subtotal(self):
        for line in self:
            if not line.price_subtotal_modify: 
                line.update({
                    'price_subtotal_modify': line.price_subtotal,
                })

class Users(models.Model):
    _inherit = 'res.users'

    # 儲存業務代碼
    salesperson_number = fields.Char(size=16, string="業務代碼", store=True, required=False)
    # 儲存員工編號
    employee_serial_number = fields.Char(size=16, string="員工編號", store=True, required=True)
    # 儲存員工分機號碼
    employee_tel = fields.Char(size=16, string="業務電話分機", store=True, required=True)
    name = fields.Char(related="partner_id.name", store=True)
    performance_id = fields.One2many('sales.performance', 'user_id')

class SalesPerformance(models.Model):
    _name = 'sales.performance'
    _description = 'Record Sales Contribution In Each Case'

    # 用來與 iot_sale_order 建立 One2many 關係
    sales_id = fields.Many2one('iot.sale.order')
    # 用來與 res.users 建立關係
    user_id = fields.Many2one('res.users')
    # 員工編號
    sales_serial_number = fields.Char(related='user_id.employee_serial_number', store=True)
    # 類別
    category = fields.Char(size=32, store=True)
    # 用來與 res.currency 建立關係，active_test 用來避免只呈現 active 資料
    # currency_id = fields.Many2one('res.currency', context={'active_test': False})
    currency_id = fields.Many2one('res.currency')
    # 原幣成交金額
    currency_total = fields.Float(store=True)
    # 成交金額(NTD)
    deal_total = fields.Float(store=True)
    # 等量業績(NTD)
    equivalent_performance = fields.Float(store=True)
    # 套數
    pairs = fields.Integer(store=True)
    # 註記
    comment = fields.Char(size=256, store=True)
    # 部門
    department = fields.Char(size=32, store=True)

class InoviceNotification(models.Model):
    _name = 'invoice.notification'
    _description = 'Record Sales Invoice Notification'
    _order = 'sequence'

    sequence = fields.Integer(string='Sequence', default=10)

    # 用來與 iot_sale_order 建立 One2many 關係
    invoice_iot_rel = fields.Many2one('iot.sale.order', ondelete='cascade')

    invoice_date = fields.Datetime(string='發票日期')
    payment_terms = fields.Many2one('payment.terms.mapping', string='付款方式')
    payment_times = fields.Many2one('payment.times.mapping', string='付款時點')
    payment_method = fields.Many2one('payment.method.mapping', string='付款條件')
    payment_method_name = fields.Char(related='payment_method.name', string='交易條件說明')
    ticket_days = fields.Char(related='payment_method.ticket_days', string='票期天數')
    payment_days = fields.Char(related='payment_method.payment_days', string='付款天數')
    serial_number = fields.Integer()
    sale_serial_number = fields.Integer()
    po_number = fields.Boolean()
    sale_item = fields.Char()
    sale_item_amount = fields.Integer(default=None)
    sale_item_single_price = fields.Integer()
    sale_item_currency = fields.Many2one('res.currency')
    sale_item_single_price_origin = fields.Integer(compute='_compute_origin_price', store=True, readonly=False, copy=True)
    sale_item_single_price_twd = fields.Integer(compute='_copy_twd_price', store=True, readonly=False, copy=True)
    sale_order_line_id = fields.Integer()


    # 預定開立發票通知單，當幣別為台幣，將原幣金額帶入台幣金額
    @api.onchange('sale_item_currency', 'sale_item_single_price_origin')
    def _copy_twd_price(self):
        for line in self:
            if line.sale_item_currency.name == 'TWD':
                line.sale_item_single_price_twd = line.sale_item_single_price_origin
            else:
                line.sale_item_single_price_twd = 0
    
    # 預定開立發票通知單，新增資料時，數量*單價=原幣金額
    @api.onchange('sale_item_amount', 'sale_item_single_price')
    def _compute_origin_price(self):
        for line in self:
            line.sale_item_single_price_origin = line.sale_item_amount * line.sale_item_single_price


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    name_modify = fields.Char(compute='_duplicate_name', store=True)

    # 是否使用 group
    use_today = fields.Char(string="群組")
    
    @api.depends('name')
    def _duplicate_name(self):
        for line in self:
            line.update({
                'name_modify': line.name,
            })

class IrSequence(models.Model):
    _inherit = "ir.sequence.date_range"

    sale_business_number = fields.Char()
    #用來建立ir.sequence.date_range 內的業務代碼

    # 用來給予水號的地方
    def replace_next(self,dt):
        if self.sequence_id.implementation == 'standard':
            number_next = _select_nextval(self._cr, 'ir_sequence_%03d_%03d' % (self.sequence_id.id, self.id))
        else:
            number_next = _update_nogap(self, self.sequence_id.number_increment)
        return self.sequence_id.get_next_char_replace(number_next,dt)

#selas 的 ir.sequence 序號建立方式
class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    range_reset = fields.Selection(
        [
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("yearly", "Yearly"),
        ], default="daily"
    )

    def _sale_next(self, sale_business_number,sequence_date=None):
        """ Returns the next number in the preferred sequence in all the ones given in self."""
        if not self.use_date_range:
            return self._next_do()
        # date mode
        dt = sequence_date or self._context.get('ir_sequence_date', fields.Date.today())

        seq_date = self.env['ir.sequence.date_range'].search([('sequence_id', '=', self.id), ('date_from', '<=', dt), ('date_to', '>=', dt),('sale_business_number','=',sale_business_number)], limit=1)
        if not seq_date:
            seq_date = self._create_date_range_seq1(dt,sale_business_number)
        return seq_date.with_context(ir_sequence_date_range=seq_date.date_from).replace_next(dt)

    def next_by_id(self, sequence_date=None):
        """ Draw an interpolated string using the specified sequence."""
        self.check_access_rights('read')
        return self._next(sequence_date=sequence_date)

    @api.model
    def sale_next_by_code(self, sequence_code, sale_business_number,sequence_date=None):
        self.check_access_rights('read')
        company_id = self.env.company.id
        seq_ids = self.search([('code', '=', sequence_code), ('company_id', 'in', [company_id, False])], order='company_id')
        if not seq_ids:
            _logger.debug("No ir.sequence has been found for code '%s'. Please make sure a sequence is set for current company." % sequence_code)
            return False
        seq_id = seq_ids[0]
        return seq_id._sale_next(sequence_date=sequence_date, sale_business_number=sale_business_number)

    def _create_date_range_seq1(self, date,sale_business_number):
        self.ensure_one()
        if not self.range_reset:
            return super()._create_date_range_seq(date)
        date_from, date_to = self._compute_date_from_to(date)
        date_range = self.env["ir.sequence.date_range"].search(
            [
                ("sequence_id", "=", self.id),
                ("date_from", ">=", date),
                ("date_from", "<=", date_to),
                ("sale_business_number", "=" , sale_business_number)
            ],
            order="date_from desc",
            limit=1,
        )
        if date_range:
            date_to = date_range.date_from + timedelta(days=-1)
        date_range = self.env["ir.sequence.date_range"].search(
            [
                ("sequence_id", "=", self.id),
                ("date_to", ">=", date_from),
                ("date_to", "<=", date),
                ("sale_business_number", "=" , sale_business_number)
            ],
            order="date_to desc",
            limit=1,
        )        
        if date_range:
            date_from = date_range.date_to + timedelta(days=1)
        seq_date_range = (
            self.env["ir.sequence.date_range"]
            .sudo()
            .create(
                {"date_from": date_from, "date_to": date_to, "sequence_id": self.id, "sale_business_number" : sale_business_number}
            )
        )
        return seq_date_range

    #給予前綴與後綴的
    def get_next_char_replace(self, number_next,dt):
        interpolated_prefix, interpolated_suffix = self._get_prefix_suffix_replace(dt=dt)
        return interpolated_prefix + '%%0%sd' % self.padding % number_next + interpolated_suffix

    #這裡會將傳進來的時間分割放入res製成dict
    def _get_prefix_suffix_replace(self, date=None, date_range=None,dt=None):
        def _interpolate(s, d):
            return (s % d) if s else ''

        def _interpolation_dict(dt):
            # now = range_date = effective_date = datetime.now(pytz.timezone(self._context.get('tz') or 'UTC'))
            now = range_date = effective_date = dt
            if date or self._context.get('ir_sequence_date'):
                effective_date = fields.Datetime.from_string(date or self._context.get('ir_sequence_date'))

            if date_range or self._context.get('ir_sequence_date_range'):
                range_date = fields.Datetime.from_string(date_range or self._context.get('ir_sequence_date_range'))


            sequences = {
                'year': '%Y', 'month': '%m', 'day': '%d', 'y': '%y', 'doy': '%j', 'woy': '%W',
                'weekday': '%w', 'h24': '%H', 'h12': '%I', 'min': '%M', 'sec': '%S'
            }
            res = {}
            for key, format in sequences.items():
                res[key] = effective_date.strftime(format)
                res['range_' + key] = range_date.strftime(format)
                res['current_' + key] = now.strftime(format)
            return res

        self.ensure_one()
        d = _interpolation_dict(dt)
        try:
            interpolated_prefix = _interpolate(self.prefix, d)
            interpolated_suffix = _interpolate(self.suffix, d)
        except ValueError:
            raise UserError(_('Invalid prefix or suffix for sequence \'%s\'') % self.name)
        return interpolated_prefix, interpolated_suffix

# 修改res_partner name_get() method 
class ResPartner(models.Model):
    _inherit = 'res.partner'


    def _get_name(self):
        """ Utility method to allow name_get to be overrided without re-browse the partner """
        partner = self
        name = partner.name or ''
        if partner.company_name or partner.parent_id:
            if not name and partner.type in ['invoice', 'delivery', 'other']:
                name = dict(self.fields_get(['type'])['type']['selection'])[partner.type]
            if not partner.is_company:
                name = self._get_contact_name(partner, name)

        if self._context.get('show_address_only'):
            name = partner._display_address(without_company=True)
        if self._context.get('show_address'):
            name = name + "\n" + partner._display_address(without_company=True)
        name = name.replace('\n\n', '\n')
        name = name.replace('\n\n', '\n')
        if self._context.get('address_inline'):
            splitted_names = name.split("\n")
            name = ", ".join([n for n in splitted_names if n.strip()])
        if self._context.get('show_email') and partner.email:
            name = "%s <%s>" % (name, partner.email)
        if self._context.get('html_format'):
            name = name.replace('\n', '<br/>')
        if self._context.get('show_vat') and partner.vat:
            name = "%s ‒ %s" % (name, partner.vat)
        return name

    def name_get(self):
        res = []
        for partner in self:
            
            if not self.env.context.get('contact_person'):
                name = partner._get_name()
            else:
                name = partner.name
            res.append((partner.id, name))

        return res



class ProductProduct(models.Model):
    _inherit = "product.product"

    def name_get(self):
        result = []
        for product in self:
            name = product.product_tmpl_id.name
            result.append((product.id,name))

        return result

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    vendor_product_name = fields.Char(compute="_get_vendor_product_info", store=True,
                                      force_save="1", copy=True)
    vendor_product_code = fields.Char(compute="_get_vendor_product_info", store=True,
                                      force_save="1", copy=True, string="供應商產品料號")

    @api.depends('product_id')
    def _get_vendor_product_info(self):
        for line in self:
            tmpl_id = line.product_id.product_tmpl_id
            vendor_product_name = line.vendor_product_name
            vendor_product_code = line.vendor_product_code
            partner_id =  line.partner_id
            search = self.env['product.supplierinfo'].sudo().search([('product_tmpl_id', '=', int(tmpl_id)),
                                                                     ('name', '=', int(partner_id))])
            if search:
                if not vendor_product_name:
                    line.update({"vendor_product_name": search.product_name})
                if not vendor_product_code:
                    line.update({"vendor_product_code": search.product_code})
            else:
                line.update({"vendor_product_name": None,
                             "vendor_product_code": None})
