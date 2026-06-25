from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


CUSTOM_FIELDS = {
    "Sales Invoice": [
        {"fieldname": "custom_babyhouse_idempotency_key", "label": "Baby House Idempotency Key", "fieldtype": "Data", "unique": 1, "read_only": 1},
        {"fieldname": "custom_babyhouse_source_channel", "label": "Baby House Source Channel", "fieldtype": "Data", "read_only": 1},
        {"fieldname": "custom_babyhouse_local_invoice", "label": "Baby House Local Invoice", "fieldtype": "Data", "read_only": 1},
        {"fieldname": "custom_babyhouse_server_invoice", "label": "Baby House Server Invoice", "fieldtype": "Data", "read_only": 1},
        {"fieldname": "custom_babyhouse_branch", "label": "Baby House Branch", "fieldtype": "Data", "read_only": 1},
        {"fieldname": "custom_babyhouse_cashier", "label": "Baby House Cashier", "fieldtype": "Data", "read_only": 1},
        {"fieldname": "custom_babyhouse_session_uuid", "label": "Baby House Session UUID", "fieldtype": "Data", "read_only": 1},
    ],
    "POS Opening Entry": [
        {"fieldname": "custom_babyhouse_idempotency_key", "label": "Baby House Idempotency Key", "fieldtype": "Data", "unique": 1, "read_only": 1},
        {"fieldname": "custom_babyhouse_session_uuid", "label": "Baby House Session UUID", "fieldtype": "Data", "unique": 1, "read_only": 1},
    ],
    "POS Closing Entry": [
        {"fieldname": "custom_babyhouse_idempotency_key", "label": "Baby House Idempotency Key", "fieldtype": "Data", "unique": 1, "read_only": 1},
        {"fieldname": "custom_babyhouse_session_uuid", "label": "Baby House Session UUID", "fieldtype": "Data", "unique": 1, "read_only": 1},
    ],
    "Journal Entry": [
        {"fieldname": "custom_babyhouse_idempotency_key", "label": "Baby House Idempotency Key", "fieldtype": "Data", "unique": 1, "read_only": 1},
        {"fieldname": "custom_babyhouse_session_uuid", "label": "Baby House Session UUID", "fieldtype": "Data", "read_only": 1},
    ],
    "Employee": [
        {"fieldname": "custom_babyhouse_cashier_uuid", "label": "Baby House Cashier UUID", "fieldtype": "Data", "unique": 1, "read_only": 1},
        {"fieldname": "custom_babyhouse_employee_code", "label": "Baby House Employee Code", "fieldtype": "Data", "unique": 1, "read_only": 1},
    ],
}


def after_install():
    create_custom_fields(CUSTOM_FIELDS, update=True)


def after_migrate():
    create_custom_fields(CUSTOM_FIELDS, update=True)
