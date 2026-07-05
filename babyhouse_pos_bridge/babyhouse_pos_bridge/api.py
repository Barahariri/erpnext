from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, get_datetime, now_datetime, nowdate


def _value(value):
    return frappe.parse_json(value) if isinstance(value, str) else (value or {})


def _existing(doctype: str, key: str):
    name = frappe.db.get_value(doctype, {"custom_babyhouse_idempotency_key": key}, "name")
    return frappe.get_doc(doctype, name) if name else None


def _result(doc, created: bool):
    return {"doctype": doc.doctype, "name": doc.name, "created": created, "docstatus": doc.docstatus}


def _document_result(doc, idempotency_key=None):
    return {
        "doctype": doc.doctype,
        "name": doc.name,
        "docstatus": doc.docstatus,
        "idempotency_key": idempotency_key or getattr(doc, "custom_babyhouse_idempotency_key", None),
    }


@frappe.whitelist()
def upsert_cashier(idempotency_key=None, cashier=None):
    data = _value(cashier)
    if not idempotency_key or not data.get("uuid") or not data.get("email"):
        frappe.throw(_("idempotency_key, cashier uuid, and email are required"))

    employee_name = frappe.db.get_value("Employee", {"custom_babyhouse_cashier_uuid": data["uuid"]}, "name")
    if employee_name:
        employee = frappe.get_doc("Employee", employee_name)
        return {"doctype": "Employee", "name": employee.name, "user_id": employee.user_id, "created": False}

    user = frappe.db.exists("User", data["email"])
    if not user:
        user_doc = frappe.get_doc({
            "doctype": "User", "email": data["email"], "first_name": data.get("name") or data["employee_code"],
            "enabled": 1 if data.get("active", True) else 0, "send_welcome_email": 0, "user_type": "System User",
        }).insert(ignore_permissions=True)
        user = user_doc.name

    company = data.get("company") or frappe.defaults.get_global_default("company")
    if not company:
        frappe.throw(_("A company is required to provision a POS employee"))
    employee = frappe.get_doc({
        "doctype": "Employee", "first_name": data.get("name") or data["employee_code"], "company": company,
        "user_id": user, "status": "Active" if data.get("active", True) else "Inactive",
        "gender": data.get("gender") or "Prefer not to say",
        "date_of_birth": getdate(data.get("date_of_birth") or "1970-01-01"),
        "date_of_joining": getdate(data.get("date_of_joining") or nowdate()),
        "custom_babyhouse_cashier_uuid": data["uuid"], "custom_babyhouse_employee_code": data["employee_code"],
    }).insert(ignore_permissions=True)
    return {"doctype": "Employee", "name": employee.name, "user_id": user, "created": True}


@frappe.whitelist()
def upsert_pos_sale(idempotency_key=None, sale=None):
    data = _value(sale)
    if existing := _existing("Sales Invoice", idempotency_key):
        return _result(existing, False)
    branch = data.get("branch") or {}
    cashier = data.get("cashier") or {}
    customer = data.get("customer") or branch.get("default_customer")
    if not customer:
        frappe.throw(_("A customer or branch default customer is required"))
    posting = get_datetime(data.get("posting_datetime"))
    invoice = frappe.get_doc({
        "doctype": "Sales Invoice", "customer": customer, "company": branch.get("company"), "currency": data.get("currency"),
        "is_pos": 1, "pos_profile": branch.get("pos_profile"), "update_stock": 1, "set_warehouse": branch.get("warehouse"),
        "posting_date": getdate(posting), "posting_time": posting.time(), "set_posting_time": 1,
        "custom_babyhouse_idempotency_key": idempotency_key, "custom_babyhouse_source_channel": "pos",
        "custom_babyhouse_local_invoice": data.get("local_invoice_no"), "custom_babyhouse_server_invoice": data.get("server_invoice_no"),
        "custom_babyhouse_branch": branch.get("code"), "custom_babyhouse_cashier": cashier.get("code"),
        "custom_babyhouse_session_uuid": data.get("session_uuid"), "remarks": frappe.as_json(data.get("metadata") or {}),
        "items": [{"item_code": row.get("sku"), "qty": row.get("quantity"), "rate": row.get("rate"), "warehouse": branch.get("warehouse"), "cost_center": branch.get("cost_center")} for row in data.get("items", [])],
        "payments": [{"mode_of_payment": row.get("mode_of_payment") or row.get("method"), "amount": row.get("amount"), "account": row.get("account"), "reference_no": row.get("reference")} for row in data.get("payments", [])],
    }).insert(ignore_permissions=True)
    invoice.submit()
    return _result(invoice, True)


@frappe.whitelist()
def upsert_pos_return(idempotency_key=None, **kwargs):
    data = _value(kwargs.get("return"))
    if existing := _existing("Sales Invoice", idempotency_key):
        return _result(existing, False)
    original = data.get("original_erpnext_invoice")
    if not original or not frappe.db.exists("Sales Invoice", original):
        frappe.throw(_("The original HoloERP Sales Invoice must be synchronized first"))
    source = frappe.get_doc("Sales Invoice", original)
    posting = get_datetime(data.get("posting_datetime"))
    invoice = frappe.copy_doc(source)
    invoice.name = None
    invoice.is_return = 1
    invoice.return_against = original
    invoice.posting_date = getdate(posting)
    invoice.posting_time = posting.time()
    invoice.set_posting_time = 1
    invoice.custom_babyhouse_idempotency_key = idempotency_key
    invoice.custom_babyhouse_source_channel = "pos"
    invoice.custom_babyhouse_server_invoice = data.get("refund_number")
    invoice.remarks = data.get("reason")
    invoice.set("items", [])
    for row in data.get("items", []):
        invoice.append("items", {"item_code": row.get("sku"), "qty": -abs(row.get("quantity") or 0), "rate": row.get("rate"), "warehouse": (data.get("branch") or {}).get("warehouse")})
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return _result(invoice, True)


@frappe.whitelist()
def upsert_cash_movement(idempotency_key=None, movement=None):
    data = _value(movement)
    if existing := _existing("Journal Entry", idempotency_key):
        return _result(existing, False)
    if not data.get("cash_account") or not data.get("counterparty_account"):
        frappe.throw(_("Cash and counterparty accounts are required for POS cash movements"))
    amount = abs(float(data.get("amount") or 0))
    cash_debit = data.get("type") == "in"
    doc = frappe.get_doc({
        "doctype": "Journal Entry", "company": data.get("company"), "posting_date": getdate(data.get("occurred_at")),
        "user_remark": data.get("reason"), "custom_babyhouse_idempotency_key": idempotency_key,
        "custom_babyhouse_session_uuid": data.get("session_uuid"),
        "accounts": [
            {"account": data.get("cash_account"), "debit_in_account_currency": amount if cash_debit else 0, "credit_in_account_currency": 0 if cash_debit else amount},
            {"account": data.get("counterparty_account"), "debit_in_account_currency": 0 if cash_debit else amount, "credit_in_account_currency": amount if cash_debit else 0},
        ],
    }).insert(ignore_permissions=True)
    doc.submit()
    return _result(doc, True)


@frappe.whitelist()
def upsert_pos_session(idempotency_key=None, session=None):
    data = _value(session)
    doctype = "POS Closing Entry" if data.get("status") == "closed" else "POS Opening Entry"
    if existing := _existing(doctype, idempotency_key):
        return _result(existing, False)
    branch = data.get("branch") or {}
    cashier = data.get("cashier") or {}
    if doctype == "POS Opening Entry":
        opened = get_datetime(data.get("opened_at"))
        payments = data.get("payment_totals") or {"Cash": data.get("opening_cash") or 0}
        doc = frappe.get_doc({
            "doctype": doctype, "period_start_date": opened, "posting_date": getdate(opened), "company": branch.get("company"),
            "pos_profile": branch.get("pos_profile"), "user": cashier.get("user_id"),
            "balance_details": [{"mode_of_payment": mode, "opening_amount": amount} for mode, amount in payments.items()],
            "custom_babyhouse_idempotency_key": idempotency_key, "custom_babyhouse_session_uuid": data.get("uuid"),
        }).insert(ignore_permissions=True)
        doc.submit()
        return _result(doc, True)

    opening_name = frappe.db.get_value("POS Opening Entry", {"custom_babyhouse_session_uuid": data.get("uuid")}, "name")
    if not opening_name:
        frappe.throw(_("The HoloERP POS Opening Entry must be synchronized first"))
    opened, closed = get_datetime(data.get("opened_at")), get_datetime(data.get("closed_at"))
    payments = data.get("payment_totals") or {}
    doc = frappe.get_doc({
        "doctype": doctype, "period_start_date": opened, "period_end_date": closed, "posting_date": getdate(closed),
        "posting_time": closed.time(), "company": branch.get("company"), "pos_profile": branch.get("pos_profile"),
        "user": cashier.get("user_id"), "pos_opening_entry": opening_name,
        "payment_reconciliation": [{"mode_of_payment": mode, "opening_amount": data.get("opening_cash") or 0, "expected_amount": amount, "closing_amount": amount, "difference": 0} for mode, amount in payments.items()],
        "custom_babyhouse_idempotency_key": idempotency_key, "custom_babyhouse_session_uuid": data.get("uuid"),
    }).insert(ignore_permissions=True)
    doc.submit()
    return _result(doc, True)


@frappe.whitelist()
def upsert_ecommerce_sale(idempotency_key=None, sale=None):
    data = _value(sale)
    if existing := _existing("Sales Invoice", idempotency_key):
        return _result(existing, False)

    company = data.get("company") or frappe.defaults.get_global_default("company")
    warehouse = data.get("warehouse")
    customer = _get_or_create_ecommerce_customer(data)
    posting = get_datetime(data.get("posting_datetime") or now_datetime())
    items = []

    for row in data.get("items", []):
        if not row.get("sku"):
            frappe.throw(_("Every ecommerce invoice item must include an item SKU"))
        items.append({
            "item_code": row.get("sku"),
            "item_name": row.get("name") or row.get("sku"),
            "qty": row.get("quantity") or 0,
            "rate": row.get("rate") or 0,
            "warehouse": warehouse,
            "cost_center": data.get("cost_center"),
            "discount_amount": row.get("discount") or 0,
        })

    if not items:
        frappe.throw(_("Ecommerce invoice must contain at least one item"))

    invoice_data = {
        "doctype": "Sales Invoice",
        "customer": customer,
        "company": company,
        "currency": data.get("currency"),
        "update_stock": 1,
        "set_warehouse": warehouse,
        "posting_date": getdate(posting),
        "posting_time": posting.time(),
        "set_posting_time": 1,
        "custom_babyhouse_idempotency_key": idempotency_key,
        "custom_babyhouse_source_channel": data.get("source_channel") or "web",
        "custom_babyhouse_server_invoice": data.get("order_number"),
        "remarks": frappe.as_json(data.get("metadata") or {}),
        "items": items,
    }

    shipping_total = float(data.get("shipping_total") or 0)
    if shipping_total > 0 and data.get("shipping_income_account"):
        invoice_data["taxes"] = [{
            "charge_type": "Actual",
            "account_head": data.get("shipping_income_account"),
            "description": _("Shipping"),
            "tax_amount": shipping_total,
        }]

    invoice = frappe.get_doc(invoice_data).insert(ignore_permissions=True)
    invoice.submit()
    return _result(invoice, True)


@frappe.whitelist()
def upsert_ecommerce_payment(idempotency_key=None, payment=None):
    data = _value(payment)
    if existing := _existing("Payment Entry", idempotency_key):
        return _result(existing, False)

    invoice_name = data.get("sales_invoice")
    if not invoice_name or not frappe.db.exists("Sales Invoice", invoice_name):
        frappe.throw(_("The HoloERP ecommerce Sales Invoice must be synchronized before payment"))

    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    payments = data.get("payments") or []
    amount = sum(float(row.get("amount") or 0) for row in payments)
    if amount <= 0:
        frappe.throw(_("Payment amount must be greater than zero"))

    paid_to = data.get("default_payment_account")
    if not paid_to:
        frappe.throw(_("A default payment account is required for ecommerce payments"))

    posting = get_datetime((payments[0] or {}).get("paid_at") if payments else now_datetime())
    doc = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": invoice.customer,
        "company": data.get("company") or invoice.company,
        "posting_date": getdate(posting),
        "paid_amount": amount,
        "received_amount": amount,
        "paid_from": data.get("receivable_account") or invoice.debit_to,
        "paid_to": paid_to,
        "reference_no": data.get("order_number") or idempotency_key,
        "reference_date": getdate(posting),
        "custom_babyhouse_idempotency_key": idempotency_key,
        "references": [{
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice.name,
            "allocated_amount": min(amount, float(invoice.outstanding_amount or amount)),
        }],
    }).insert(ignore_permissions=True)
    doc.submit()
    return _result(doc, True)


@frappe.whitelist()
def upsert_ecommerce_return(idempotency_key=None, **kwargs):
    data = _value(kwargs.get("return"))
    if existing := _existing("Sales Invoice", idempotency_key):
        return _result(existing, False)

    original = data.get("original_sales_invoice")
    if not original or not frappe.db.exists("Sales Invoice", original):
        frappe.throw(_("The original HoloERP ecommerce Sales Invoice must be synchronized first"))

    source = frappe.get_doc("Sales Invoice", original)
    posting = get_datetime(data.get("posting_datetime") or now_datetime())
    invoice = frappe.copy_doc(source)
    invoice.name = None
    invoice.is_return = 1
    invoice.return_against = original
    invoice.posting_date = getdate(posting)
    invoice.posting_time = posting.time()
    invoice.set_posting_time = 1
    invoice.custom_babyhouse_idempotency_key = idempotency_key
    invoice.custom_babyhouse_source_channel = "web"
    invoice.custom_babyhouse_server_invoice = data.get("refund_number")
    invoice.remarks = data.get("reason")
    invoice.set("items", [])
    for row in data.get("items", []):
        invoice.append("items", {
            "item_code": row.get("sku"),
            "qty": -abs(row.get("quantity") or 0),
            "rate": row.get("rate") or 0,
            "warehouse": data.get("warehouse"),
        })
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return _result(invoice, True)


def _get_or_create_ecommerce_customer(data):
    configured = data.get("default_customer")
    customer_data = data.get("customer") or {}
    customer_name = customer_data.get("name") or customer_data.get("phone") or configured

    if customer_data.get("phone"):
        existing = frappe.db.get_value("Customer", {"mobile_no": customer_data.get("phone")}, "name")
        if existing:
            return existing

    if configured and frappe.db.exists("Customer", configured):
        return configured

    if not customer_name:
        frappe.throw(_("A customer or default customer is required for ecommerce invoices"))

    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": customer_name,
        "customer_type": "Individual",
        "mobile_no": customer_data.get("phone"),
        "email_id": customer_data.get("email"),
        "custom_babyhouse_customer_id": customer_data.get("id"),
    }).insert(ignore_permissions=True)
    return customer.name


@frappe.whitelist()
def pos_sync_audit(idempotency_keys=None, limit=500):
    keys = _value(idempotency_keys)
    if not isinstance(keys, list):
        frappe.throw(_("idempotency_keys must be a list"))

    limit = int(limit or 500)
    documents = []
    found = set()

    for key in keys:
        key = str(key)
        document = _find_by_idempotency_key(key)
        if document:
            documents.append(_document_result(document, key))
            found.add(key)

    orphan_documents = _orphan_pos_documents(set(keys), limit)

    return {
        "documents": documents,
        "missing_keys": [key for key in keys if key not in found],
        "orphan_documents": orphan_documents,
    }


def _find_by_idempotency_key(key):
    if key.startswith("pos-cashier:"):
        cashier_uuid = key.split(":", 1)[1]
        employee_name = frappe.db.get_value("Employee", {"custom_babyhouse_cashier_uuid": cashier_uuid}, "name")
        return frappe.get_doc("Employee", employee_name) if employee_name else None

    for doctype in ["Sales Invoice", "Payment Entry", "POS Opening Entry", "POS Closing Entry", "Journal Entry"]:
        if doc := _existing(doctype, key):
            return doc
    return None


def _orphan_pos_documents(known_keys, limit):
    rows = []
    for doctype in ["Sales Invoice", "Payment Entry", "POS Opening Entry", "POS Closing Entry", "Journal Entry"]:
        rows.extend(_get_all_pos_documents(doctype, known_keys, limit - len(rows)))
        if len(rows) >= limit:
            break
    return rows


def _get_all_pos_documents(doctype, known_keys, limit):
    if limit <= 0:
        return []
    filters = {"custom_babyhouse_source_channel": "pos"} if doctype == "Sales Invoice" else [["custom_babyhouse_idempotency_key", "is", "set"]]
    try:
        docs = frappe.get_all(
            doctype,
            filters=filters,
            fields=["name", "docstatus", "custom_babyhouse_idempotency_key"],
            limit_page_length=limit,
        )
    except Exception:
        return []

    return [
        {
            "doctype": doctype,
            "name": row.get("name"),
            "docstatus": row.get("docstatus"),
            "idempotency_key": row.get("custom_babyhouse_idempotency_key"),
        }
        for row in docs
        if row.get("custom_babyhouse_idempotency_key") and row.get("custom_babyhouse_idempotency_key") not in known_keys
    ]
