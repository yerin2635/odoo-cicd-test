from odoo import api, SUPERUSER_ID
from odoo.addons.base.wizard.base_language_install import BaseLanguageInstall

def update_init_data(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # 新增 administrator 業務代碼、分機、員工編號
    env['res.users'].search([('name', '=', 'Administrator')]).write({'salesperson_number': 'test_admin1', 'employee_serial_number': 'test_admin2', 'employee_tel': 'test_admin3'})
    
    # 新增 sale, purchase tax 5%
    env['account.tax'].create({'name': '5%', 'type_tax_use': 'sale', 'amount': 5.0})
    env['account.tax'].create({'name': '5%', 'type_tax_use': 'purchase', 'amount': 5.0})

    # 啟用繁體中文
    env['res.lang'].search([('name', '=', 'Chinese (Traditional) / 繁體中文'), ('active', '=', False)]).write({'active': True})

    # 啟用美金, 台幣
    env['res.currency'].search([('name', '=', 'TWD'), ('active', '=', False)]).write({'active': True})
    env['res.currency'].search([('name', '=', 'USD'), ('active', '=', False)]).write({'active': True})

    # 將公司預設幣額改為台幣, 名子改IOT (因為是第一家公司預設 id 為 1)
    env['res.company'].browse([1]).write({'name': '物聯網股份有限公司', 'currency_id': 140})

    # 將 sale, purchase 預設稅率改成新增的 5%
    env['res.company'].browse([1]).write({'account_sale_tax_id': env['account.tax'].search([("name", "=", "5%"), ("type_tax_use", "=", "sale")])})
    env['res.company'].browse([1]).write({'account_purchase_tax_id': env['account.tax'].search([("name", "=", "5%"), ("type_tax_use", "=", "purchase")])})

    # 將 base_language_install 啟用 zh_TW
    env['base.language.install'].create({'lang': 'zh_TW', 'overwrite': True, 'state': 'done'})

    # 啟用 zh_TW 後執行繁體中文界面更新
    BaseLanguageInstall.lang_install(env['base.language.install'].search([('lang', '=', 'zh_TW'), ('overwrite', '=', True), ('state', '=', 'done')]))