"""Self-contained DEMO fields on Project and Asset, no upstream DocType edits.

ERPNext v16 supports persistent Custom Field metadata. These are installed
ONLY by explicit seed.setup() on an opted-in disposable demo site.
"""
from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def install_demo_fields():
    custom_fields = {
        "Project": [
            {
                "fieldname": "custom_demo_district",
                "label": "موقع المشروع / Demo District",
                "fieldtype": "Data",
                "insert_after": "project_name",
                "read_only": 0,
            },
            {
                "fieldname": "custom_demo_scope",
                "label": "نطاق الأعمال / Demo Scope of Work",
                "fieldtype": "Small Text",
                "insert_after": "custom_demo_district",
            },
            {
                "fieldname": "custom_demo_sector",
                "label": "نوع المشروع / Demo Sector",
                "fieldtype": "Data",
                "insert_after": "custom_demo_scope",
            },
        ],
        "Asset": [
            {
                "fieldname": "custom_demo_asset_code",
                "label": "رقم المعدة / Demo Asset Code",
                "fieldtype": "Data",
                "insert_after": "asset_name",
            },
            {
                "fieldname": "custom_demo_manufacturer",
                "label": "الشركة المصنعة / Manufacturer",
                "fieldtype": "Data",
                "insert_after": "custom_demo_asset_code",
            },
            {
                "fieldname": "custom_demo_model",
                "label": "الموديل / Model",
                "fieldtype": "Data",
                "insert_after": "custom_demo_manufacturer",
            },
            {
                "fieldname": "custom_demo_machine_type",
                "label": "نوع المعدة / Equipment Type",
                "fieldtype": "Data",
                "insert_after": "custom_demo_model",
            },
            {
                "fieldname": "custom_demo_serial",
                "label": "رقم تسلسلي اصطناعي / Synthetic Serial",
                "fieldtype": "Data",
                "insert_after": "custom_demo_machine_type",
            },
            {
                "fieldname": "custom_demo_manufacture_year",
                "label": "سنة الصنع التجريبية / Model Year",
                "fieldtype": "Int",
                "insert_after": "custom_demo_serial",
            },
            {
                "fieldname": "custom_demo_hour_meter",
                "label": "ساعات التشغيل التجريبية / Hour Meter",
                "fieldtype": "Float",
                "insert_after": "custom_demo_manufacture_year",
            },
            {
                "fieldname": "custom_demo_fuel_lph",
                "label": "وقود تقريبي لتر/ساعة / Demo Fuel L/h",
                "fieldtype": "Float",
                "insert_after": "custom_demo_hour_meter",
            },
            {
                "fieldname": "custom_demo_assigned_project",
                "label": "المشروع المخصص / Assigned Project",
                "fieldtype": "Link",
                "options": "Project",
                "insert_after": "custom_demo_fuel_lph",
            },
            {
                "fieldname": "custom_demo_operating_site",
                "label": "موقع التشغيل / Operating Site",
                "fieldtype": "Data",
                "insert_after": "custom_demo_assigned_project",
            },
            {
                "fieldname": "custom_demo_operating_state",
                "label": "حالة التشغيل التجريبية / Equipment State",
                "fieldtype": "Select",
                "options": "Available\nAssigned\nUnder Maintenance\nIdle",
                "insert_after": "custom_demo_operating_site",
            },
        ],
    }
    create_custom_fields(custom_fields, update=True)
    frappe.clear_cache(doctype="Project")
    frappe.clear_cache(doctype="Asset")
