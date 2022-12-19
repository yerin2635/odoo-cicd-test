# -*- coding: utf-8 -*-
{
    'name': "Iot Sale Order",
    'summary': """
    """,
    'description': """
        Iot Sale Order
    """,
    'author': "Iot",
    'category': 'iot_sale_order',
    'version': '0.1',
    # any module necessary for this one to work correctly
    # l10n_us 為 USA accounting package, 拿掉 base
    'depends': [
        'sale', 'sale_management', 'purchase', 'mail', 'sequence_reset_period', 'l10n_us'
    ],
    # always loaded
    'data': [
        'security/salemanager_group.xml',
        'views/sale_order_list_view.xml',
        'views/action_menu.xml',
        'views/users_salesperson_number.xml',
        'views/iots_erp_column_modify.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/mapping_table.xml',
        'report/iot_sale_order_report_templates.xml',
        'report/iot_sale_quotations_report_templates.xml',
        'report/sale_report_call.xml',
        'report/iot_basic_pricet_templates.xml',
        'report/iot_FET_templates.xml',
        'views/sale_purchase_view_adjustment.xml',
        'views/asset.xml',     
        'views/payment_method_view.xml', 
        'data/sale_order_list_cron_test.xml'
    ],
    'qweb':[
        'static/src/xml/iots_erp_template_modify.xml',
    ],

    # only loaded in demonstration mode
    'demo': [
    ],
    # execute after addon installed
    'post_init_hook': 'update_init_data'
}
