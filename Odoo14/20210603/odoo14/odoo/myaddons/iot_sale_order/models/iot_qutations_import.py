# from odoo import api, models
# import logging
# import itertools
# import psycopg2
# from odoo.exceptions import ValidationError
# from odoo.tools.translate import _

# _logger = logging.getLogger(__name__)

# class ImportTemplate(models.TransientModel):
#     _inherit = "base_import.import"

#     # 報價單上限 99 筆
#     quotation_limitation = 99

#     # addons\base_import\models\base_import line 885
#     def do(self, fields, columns, options, dryrun=False):
#         # 判斷匯入報價單格式再走自己改的，其他的格式都走原生的
#         if self.res_model != "sale.order":
#             return super(ImportTemplate, self).do(fields, columns, options, dryrun)
#         # self.res_model => res.partner / sale.order
#         """ Actual execution of the import

#         :param fields: import mapping: maps each column to a field,
#                        ``False`` for the columns to ignore
#         :type fields: list(str|bool)
#         :param columns: columns label
#         :type columns: list(str|bool)
#         :param dict options:
#         :param bool dryrun: performs all import operations (and
#                             validations) but rollbacks writes, allows
#                             getting as much errors as possible without
#                             the risk of clobbering the database.
#         :returns: A list of errors. If the list is empty the import
#                   executed fully and correctly. If the list is
#                   non-empty it contains dicts with 3 keys ``type`` the
#                   type of error (``error|warning``); ``message`` the
#                   error message associated with the error (a string)
#                   and ``record`` the data which failed to import (or
#                   ``false`` if that data isn't available or provided)
#         :rtype: dict(ids: list(int), messages: list({type, message, record}))
#         """
#         self.ensure_one()
#         self._cr.execute('SAVEPOINT import')

#         try:
#             data, import_fields = self._convert_import_data(fields, options)
#             # Parse date and float field
#             data = self._parse_import_data(data, import_fields, options)
#             # 將公司與聯絡人合併，符合原生 database schema
#             if self.res_model == 'sale.order':
#                 for row in data:
#                     if row[1]:
#                         row[1] = row[0] + ', ' + row[1]

#         except ValueError as error:
#             return {
#                 'messages': [{
#                     'type': 'error',
#                     'message': str(error),
#                     'record': False,
#                 }]
#             }

#         _logger.info('importing %d rows...', len(data))

#         # # 紀錄是否要報錯
#         # raise_over_limitation = False
#         # # Error record
#         # error_record = str()
#         # 清理 row data，依業務人員與報價日期來判斷是否超過當日 99 筆報價單上限
#         # sequence_record = { 業務名稱： {報價日期: {sequence: 初始 sequence, total: 初始 sequence 與目前匯入單數加總值} }
#         sequence_record = dict()
#         for row in data:
#             if row[4] not in sequence_record:
#                 sequence_record[row[4]] = dict()
#             if row[2] not in sequence_record[row[4]]:
#                 sequence_record[row[4]][row[2]] = dict()
#                 # 取得該業務業務代碼
#                 salesperson_number = self.env['res.users'].search([('name', '=', row[4])]).salesperson_number
#                 # 儲存初始的報價單編號
#                 sequence_record[row[4]][row[2]]['sequence'] = self.env['ir.sequence.date_range'].search([('date_from', '=', row[2]), ('sale_business_number', '=', salesperson_number)]).number_next_actual
#                 sequence_record[row[4]][row[2]]['total'] = sequence_record[row[4]][row[2]]['sequence'] + 1
#             # 如果此筆報價單資料加總後超過 99 筆，報錯且終止後續程序
#             if sequence_record[row[4]][row[2]]['total'] > self.quotation_limitation:
#                 raise ValidationError(_(f'業務 {row[4]} 於 {row[2][:-9]} 報價單編號超過 {self.quotation_limitation} 筆'))
#                 # raise_over_limitation = True
#                 # error_record += f"業務 {row[4]} 於 {row[2][:-9]} 報價單編號超過 {self.quotation_limitation} 筆\n"
#         # if raise_over_limitation:
#             # raise ValidationError(_(error_record))

#         name_create_enabled_fields = options.pop('name_create_enabled_fields', {})
#         import_limit = options.pop('limit', None)
#         model = self.env[self.res_model].with_context(import_file=True, name_create_enabled_fields=name_create_enabled_fields, _import_limit=import_limit)
#         import_result = model.load(import_fields, data)
#         _logger.info('done')

#         # If transaction aborted, RELEASE SAVEPOINT is going to raise
#         # an InternalError (ROLLBACK should work, maybe). Ignore that.
#         # TODO: to handle multiple errors, create savepoint around
#         #       write and release it in case of write error (after
#         #       adding error to errors array) => can keep on trying to
#         #       import stuff, and rollback at the end if there is any
#         #       error in the results.
#         # Test => dryrun = True; Import => dryrun = False
#         # 如果是 test 把該單號碼復原        
#         try:
#             if dryrun:
#                 self._cr.execute('ROLLBACK TO SAVEPOINT import')
#                 # cancel all changes done to the registry/ormcache
#                 self.pool.clear_caches()
#                 self.pool.reset_changes()
#                 # 將測試增加的 sequence number 還原
#                 for sales in sequence_record:
#                     for date in sequence_record[sales]:
#                         # 取得該業務業務代碼
#                         salesperson_number = self.env['res.users'].search([('name', '=', sales)]).salesperson_number
#                         self.env['ir.sequence.date_range'].search([('date_from', '=', date), ('sale_business_number', '=', salesperson_number)]).number_next_actual = sequence_record[sales][date]['sequence']                
#             else:
#                 self._cr.execute('RELEASE SAVEPOINT import')
#         except psycopg2.InternalError:
#             pass

#         # Insert/Update mapping columns when import complete successfully
#         if import_result['ids'] and options.get('headers'):
#             BaseImportMapping = self.env['base_import.mapping']
#             for index, column_name in enumerate(columns):
#                 if column_name:
#                     # Update to latest selected field
#                     mapping_domain = [('res_model', '=', self.res_model), ('column_name', '=', column_name)]
#                     column_mapping = BaseImportMapping.search(mapping_domain, limit=1)
#                     if column_mapping:
#                         if column_mapping.field_name != fields[index]:
#                             column_mapping.field_name = fields[index]
#                     else:
#                         BaseImportMapping.create({
#                             'res_model': self.res_model,
#                             'column_name': column_name,
#                             'field_name': fields[index]
#                         })
#         if 'name' in import_fields:
#             index_of_name = import_fields.index('name')
#             skipped = options.get('skip', 0)
#             # pad front as data doesn't contain anythig for skipped lines
#             r = import_result['name'] = [''] * skipped
#             # only add names for the window being imported
#             r.extend(x[index_of_name] for x in data[:import_limit])
#             # pad back (though that's probably not useful)
#             r.extend([''] * (len(data) - (import_limit or 0)))
#         else:
#             import_result['name'] = []

#         skip = options.get('skip', 0)
#         # convert load's internal nextrow to the imported file's
#         if import_result['nextrow']: # don't update if nextrow = 0 (= no nextrow)
#             import_result['nextrow'] += skip

#         return import_result