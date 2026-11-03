"""Arabic/English construction progress invoice print format (DEMO only)."""
from __future__ import annotations

import frappe


TEMPLATE = r'''
<div dir="rtl" style="font-family:DejaVu Sans,Arial,sans-serif;color:#20262e;font-size:11px">
  <div style="border:3px solid #ad2525;text-align:center;color:#ad2525;font-weight:800;padding:7px;margin-bottom:12px">
    بيانات تجريبية فقط — ليست فاتورة قانونية أو مستنداً ضريبياً معتمداً
    <div dir="ltr" style="font-size:10px">SYNTHETIC DEMO — NOT A LEGAL / TAX INVOICE</div>
  </div>
  <div style="display:flex;justify-content:space-between;border-bottom:2px solid #24364c;padding-bottom:12px">
    <div>
      <h2 style="margin:0">{{ doc.company }}</h2>
      <div style="color:#546474;margin-top:4px">مستخلص أعمال / Construction Progress Certificate</div>
    </div>
    <div style="text-align:left" dir="ltr">
      <strong>{{ doc.name }}</strong><br>
      Issue Date: {{ doc.posting_date }}<br>
      Due Date: {{ doc.due_date or "-" }}<br>
      Currency: {{ doc.currency }}
    </div>
  </div>
  <table style="width:100%;margin:15px 0;border-collapse:collapse" dir="rtl">
    <tr>
      <td style="padding:5px"><b>العميل / Customer:</b> {{ doc.customer_name or doc.customer }}</td>
      <td style="padding:5px"><b>المشروع / Project:</b> {{ doc.project or "-" }}</td>
    </tr>
    <tr>
      <td style="padding:5px"><b>رقم العقد / Contract:</b> {{ doc.po_no or "-" }}</td>
      <td style="padding:5px"><b>تاريخ العقد / Reference date:</b> {{ doc.po_date or "-" }}</td>
    </tr>
  </table>
  <table style="width:100%;border-collapse:collapse;border:1px solid #bdc9d4">
    <thead>
      <tr style="background:#e5ecf3">
        <th style="padding:8px;border:1px solid #bdc9d4">#</th>
        <th style="padding:8px;border:1px solid #bdc9d4">البيان / Description</th>
        <th style="padding:8px;border:1px solid #bdc9d4">الكمية</th>
        <th style="padding:8px;border:1px solid #bdc9d4">سعر الوحدة</th>
        <th style="padding:8px;border:1px solid #bdc9d4">الإجمالي</th>
      </tr>
    </thead>
    <tbody>
    {% for item in doc.items %}
      <tr>
        <td style="padding:6px;border:1px solid #bdc9d4">{{ loop.index }}</td>
        <td style="padding:6px;border:1px solid #bdc9d4">{{ item.description or item.item_name }}</td>
        <td style="padding:6px;border:1px solid #bdc9d4">{{ item.qty }} {{ item.uom or "" }}</td>
        <td style="padding:6px;border:1px solid #bdc9d4">{{ item.rate }}</td>
        <td style="padding:6px;border:1px solid #bdc9d4">{{ item.amount }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  <table style="width:45%;margin:15px 0;border-collapse:collapse" dir="rtl">
    <tr><td style="padding:5px">قيمة الأعمال / Net works</td><td style="text-align:left">{{ doc.net_total }} {{ doc.currency }}</td></tr>
    {% for tax in doc.taxes %}
    <tr><td style="padding:5px">{{ tax.description }} ({{ tax.rate }}%)</td><td style="text-align:left">{{ tax.tax_amount }} {{ doc.currency }}</td></tr>
    {% endfor %}
    <tr style="background:#e5ecf3;font-weight:bold"><td style="padding:8px">الإجمالي / Grand Total</td><td style="text-align:left">{{ doc.grand_total }} {{ doc.currency }}</td></tr>
    <tr><td style="padding:5px">المدفوع / Paid</td><td style="text-align:left">{{ doc.grand_total - doc.outstanding_amount }} {{ doc.currency }}</td></tr>
    <tr><td style="padding:5px">المتبقي / Outstanding</td><td style="text-align:left">{{ doc.outstanding_amount }} {{ doc.currency }}</td></tr>
  </table>
  {% if doc.payment_schedule %}
    <h4>جدول الدفعات واحتجاز الضمان (عند تطبيقه)</h4>
    <table style="width:100%;border-collapse:collapse">
      <thead><tr><th>الشرط</th><th>الاستحقاق</th><th>النسبة</th><th>المبلغ</th></tr></thead>
      {% for row in doc.payment_schedule %}
      <tr><td>{{ row.payment_term or "-" }}</td><td>{{ row.due_date }}</td><td>{{ row.invoice_portion }}%</td><td>{{ row.payment_amount }} {{ doc.currency }}</td></tr>
      {% endfor %}
    </table>
  {% endif %}
  <div style="border:1px solid #d4dce3;padding:8px;margin-top:14px">
    <b>المعالجة الضريبية:</b>
    {% if doc.company and ("ركيزة" in doc.company) %}
    الكويت: لا توجد ضريبة قيمة مضافة مطبقة في سيناريو البلد.
    {% elif doc.company and ("رواسي" in doc.company) %}
    قطر: لا توجد ضريبة قيمة مضافة مطبقة في سيناريو البلد.
    {% else %}
    سوريا: لا تُفترض ضريبة قيمة مضافة عامة. رسوم الإنفاق الانتقائية تحتاج تحديد صنف ونطاق.
    {% endif %}
    <div style="font-size:10px;margin-top:5px">أي نسبة 5% مذكورة هنا تحمل عبارة SIMULATED وهي لأغراض اختبار البرنامج فقط ولا تمثل قانوناً سارياً.</div>
  </div>
  <div style="text-align:center;color:#7e8894;margin-top:20px;font-size:10px">
    Demo ERPNext — fictional parties, projects, contract values, taxes, dates and bank details.
  </div>
</div>
'''


def install_print_format(seed):
    name = "DEMO Construction Progress Invoice AR EN"
    if frappe.db.exists("Print Format", name):
        seed.existing["Print Format"] += 1
        return name
    doc = frappe.get_doc({
        "doctype": "Print Format",
        "name": name,
        "__newname": name,
        "doc_type": "Sales Invoice",
        "standard": "No",
        "custom_format": 1,
        "print_format_type": "Jinja",
        "html": TEMPLATE,
        "disabled": 0,
    })
    doc.insert(ignore_permissions=True)
    seed.created["Print Format"] += 1
    return doc.name
