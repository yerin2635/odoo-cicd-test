from odoo import http, _
from odoo.addons.web.controllers.main import ReportController, Binary
import json, base64
from odoo.http import request
from odoo.exceptions import ValidationError

# 引用 connection_pool
# from ..models.dbconnect import psSQL

# 引用 merge pdf module
from odoo.tools.pdf import merge_pdf

# 報價單毛利率限制值
gross_profit_limitation = 15

# 繼承 web addon 底下的 controller: ReportController
class PrintPDF(ReportController):
    @http.route([
        '/report/<converter>/<reportname>',
        '/report/<converter>/<reportname>/<docids>',
    ], type='http', auth='user', website=True)
    def report_routes(self, reportname, docids=None, converter=None, **data):
        # 如果是 pdf 除了原步驟外加入附件合併
        # docids = 這張 iot_sale_order 的 id
        if (converter == 'pdf') and (reportname == 'iot_sale_order.order_report'):
            if docids:
                docids = [int(i) for i in docids.split(',')]
            iot_sale_order_id = request.env['iot.sale.order'].browse([docids[0]])
            # 列印時判斷
            if (iot_sale_order_id.iot_sale_order_total != iot_sale_order_id.performance_total) | (iot_sale_order_id.iot_sale_order_total != iot_sale_order_id.invoice_total):
                raise ValidationError(_(f"請確認案件總價(未稅)、業績總額(未稅)、發票總額(未稅)，三項數值需相等\n案件總價(未稅): {iot_sale_order_id.iot_sale_order_total}\n業績總額(未稅): {iot_sale_order_id.performance_total}\n發票總額(未稅): {iot_sale_order_id.invoice_total}\n"))

            report = request.env['ir.actions.report']._get_report_from_name(reportname)
            context = dict(request.env.context)


            if data.get('options'):
                data.update(json.loads(data.pop('options')))
            if data.get('context'):
                # Ignore 'lang' here, because the context in data is the one from the webclient *but* if
                # the user explicitely wants to change the lang, this mechanism overwrites it.
                data['context'] = json.loads(data['context'])
                if data['context'].get('lang') and not data.get('force_context_lang'):
                    del data['context']['lang']
                context.update(data['context'])
            
            pdf = report.with_context(context)._render_qweb_pdf(docids, data=data)[0]
            pdfhttpheaders = [('Content-Type', 'application/pdf'), ('Content-Length', len(pdf))]
            upload_attachment_result = request.env['upload.attachments'].search([('attachment_iot_rel', '=', docids[0])])

            # # 取 pool 出來用，並建立連線
            # connection_pool = psSQL.get_connecitonpool()
            # psgre_connection = connection_pool.getconn()

            # attachment_bytes_list = []
            # DB query 後是 class 物件要轉換型別 int(attachment_id)
            for attachment_id in upload_attachment_result:
                # # 建立 cursor
                # psgre_cursor = psgre_connection.cursor()
                # psgre_cursor.execute(f"SELECT id FROM ir_attachment WHERE res_model = 'upload.attachments' AND res_id = '{int(attachment_id)}'")
                # pdf_rowdata = psgre_cursor.fetchall()[0]
                # print(pdf_rowdata)
                # attachment_list.append({"store_fname": pdf_rowdata[0], "checksum": pdf_rowdata[1], "mimetype": pdf_rowdata[2]})
                # psgre_cursor.close()
                
                # 引用 odoo 內建合併 pdf module
                attachment_file = DownloadIOT().content_common(model='upload.attachments', id=int(attachment_id), field='documents', filename_field='undefined', download=True, token='dummy-because-api-expects-one', access_token='merge_file')
                pdf = merge_pdf([pdf, attachment_file.response[0]])

            # # db 使用完畢，release the connection object and send back to connection pool
            # connection_pool.putconn(psgre_connection)
            return request.make_response(pdf, headers=pdfhttpheaders)
        
        # 如果是 pdf 且要列印 iot_sale_order.iot_Quotation 這份 report 且毛利低於 15%，且非主管，跳出報錯
        # docids = 這張 iot_sale_order 的 id
        # 主管人員 group_id: request.env.ref("iot_sale_order.group_salesmanager")
        # 當下使用者所屬群組 list: request.env.user.groups_id
        elif (request.env.ref("iot_sale_order.group_salesmanager") not in request.env.user.groups_id):
            if (converter == 'pdf') and (reportname == 'iot_sale_order.iot_Quotation') and (request.env['sale.order'].browse([int(docids)]).gross_profit_margin < gross_profit_limitation):
                raise ValidationError(_(f"報價毛利率低於 {gross_profit_limitation}%，請通知主管協助列印"))
        # 如果是 pdf 且要列印 iot_sale_order.iot_Quotation 這份 report 且毛利低於 15%，且非主管，跳出報錯
        # docids = 這張 iot_sale_order 的 id
            if (converter == 'pdf') and (reportname == 'iot_sale_order.iot_Quotation_FET') and (request.env['sale.order'].browse([int(docids)]).gross_profit_margin < gross_profit_limitation):
                raise ValidationError(_(f"報價毛利率低於 {gross_profit_limitation}%，請通知主管協助列印"))
        res = super(PrintPDF, self).report_routes(reportname, docids, converter, **data)
        return res

class DownloadIOT(Binary):
    @http.route(['/web/content',
        '/web/content/<string:xmlid>',
        '/web/content/<string:xmlid>/<string:filename>',
        '/web/content/<int:id>',
        '/web/content/<int:id>/<string:filename>',
        '/web/content/<int:id>-<string:unique>',
        '/web/content/<int:id>-<string:unique>/<string:filename>',
        '/web/content/<int:id>-<string:unique>/<path:extra>/<string:filename>',
        '/web/content/<string:model>/<int:id>/<string:field>',
        '/web/content/<string:model>/<int:id>/<string:field>/<string:filename>'], type='http', auth="public")
    def content_common(self, xmlid=None, model='ir.attachment', id=None, field='datas',
                       filename=None, filename_field='name', unique=None, mimetype=None,
                       download=None, data=None, token=None, access_token=None, **kw):
        status, headers, content = request.env['ir.http'].binary_content(
            xmlid=xmlid, model=model, id=id, field=field, unique=unique, filename=filename,
            filename_field=filename_field, download=download, mimetype=mimetype, access_token=access_token)

        if status != 200:
            return request.env['ir.http']._response_by_status(status, headers, content)
        else:
            content_base64 = base64.b64decode(content)
            headers.append(('Content-Length', len(content_base64)))
            response = request.make_response(content_base64, headers)
        if token:
            response.set_cookie('fileToken', token)

        # 用來判斷是不是要 merge pdf, 要的話直接回傳 base64 decode 後的檔案, 但注意回傳值包在 decorator 中所以是 response type
        if access_token == 'merge_file':
            return content_base64
        return response