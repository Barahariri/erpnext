from __future__ import annotations

import copy
import importlib
import json
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path


class FrappeThrow(Exception):
    pass


class FakeDoc:
    def __init__(self, frappe, data):
        object.__setattr__(self, "_frappe", frappe)
        object.__setattr__(self, "_data", copy.deepcopy(data))
        self._data.setdefault("docstatus", 0)

    def __getattr__(self, item):
        try:
            return self._data[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def append(self, key, value):
        self._data.setdefault(key, []).append(copy.deepcopy(value))

    def insert(self, ignore_permissions=False):
        doctype = self._data["doctype"]
        if not self._data.get("name"):
            if doctype == "User" and self._data.get("email"):
                self._data["name"] = self._data["email"]
            else:
                self._data["name"] = f"{doctype}-{len(self._frappe._store.get(doctype, {})) + 1}"
        self._frappe._store.setdefault(doctype, {})[self._data["name"]] = self
        return self

    def submit(self):
        self._data["docstatus"] = 1
        return self

    @property
    def doctype(self):
        return self._data["doctype"]

    @property
    def name(self):
        return self._data["name"]

    @property
    def docstatus(self):
        return self._data["docstatus"]

    def as_dict(self):
        return copy.deepcopy(self._data)


class FakeDB:
    def __init__(self, frappe):
        self.frappe = frappe

    def get_value(self, doctype, fieldname, value, as_field):
        for name, doc in self.frappe._store.get(doctype, {}).items():
            if doc.as_dict().get(fieldname) == value:
                return name if as_field == "name" else doc.as_dict().get(as_field)
        return None

    def exists(self, doctype, name):
        return name if name in self.frappe._store.get(doctype, {}) else None


class FakeDefaults:
    @staticmethod
    def get_global_default(key):
        return "Baby House Co" if key == "company" else None


def install_fake_frappe():
    frappe = types.ModuleType("frappe")
    frappe._store = {}
    frappe.db = FakeDB(frappe)
    frappe.defaults = FakeDefaults()
    frappe._ = lambda value: value
    frappe.throw = lambda message: (_ for _ in ()).throw(FrappeThrow(message))
    frappe.parse_json = json.loads
    frappe.as_json = json.dumps
    frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn) if not args else args[0]

    def get_doc(data_or_doctype, name=None):
        if isinstance(data_or_doctype, dict):
            return FakeDoc(frappe, data_or_doctype)
        return frappe._store[data_or_doctype][name]

    frappe.get_doc = get_doc
    frappe.copy_doc = lambda doc: FakeDoc(frappe, doc.as_dict())

    def get_all(doctype, filters=None, fields=None, limit_page_length=None):
        rows = []
        for doc in frappe._store.get(doctype, {}).values():
            data = doc.as_dict()
            if filters == {"custom_babyhouse_source_channel": "pos"} and data.get("custom_babyhouse_source_channel") != "pos":
                continue
            if isinstance(filters, list) and filters and filters[0][0] == "custom_babyhouse_idempotency_key" and not data.get("custom_babyhouse_idempotency_key"):
                continue
            rows.append({field: data.get(field) for field in (fields or data.keys())})
            if limit_page_length and len(rows) >= limit_page_length:
                break
        return rows

    frappe.get_all = get_all

    utils = types.ModuleType("frappe.utils")
    utils.get_datetime = lambda value: value if isinstance(value, datetime) else datetime.fromisoformat(value)
    utils.getdate = lambda value: utils.get_datetime(value).date() if not hasattr(value, "date") else value.date()

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils
    return frappe


class BridgeApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app_path = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(app_path))

    def setUp(self):
        self.frappe = install_fake_frappe()
        sys.modules.pop("babyhouse_pos_bridge.api", None)
        self.api = importlib.import_module("babyhouse_pos_bridge.api")

    def test_upsert_cashier_creates_user_employee_and_is_idempotent(self):
        payload = {"uuid": "cashier-1", "email": "cashier@example.test", "employee_code": "C100", "name": "Cashier"}

        first = self.api.upsert_cashier("cashier-key", payload)
        second = self.api.upsert_cashier("cashier-key", payload)

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["name"], second["name"])
        self.assertIn("cashier@example.test", self.frappe._store["User"])

    def test_upsert_pos_sale_creates_submitted_invoice_and_returns_existing_duplicate(self):
        payload = self.sale_payload()

        first = self.api.upsert_pos_sale("sale-key", payload)
        second = self.api.upsert_pos_sale("sale-key", payload)
        invoice = self.frappe._store["Sales Invoice"][first["name"]].as_dict()

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["name"], second["name"])
        self.assertEqual(1, invoice["docstatus"])
        self.assertEqual("pos", invoice["custom_babyhouse_source_channel"])
        self.assertEqual("WH-KW", invoice["items"][0]["warehouse"])

    def test_upsert_pos_return_creates_linked_credit_note_and_returns_existing_duplicate(self):
        original = self.api.upsert_pos_sale("sale-key", self.sale_payload())
        payload = {
            "original_erpnext_invoice": original["name"],
            "posting_datetime": "2026-06-25T10:05:00",
            "refund_number": "RET-1",
            "reason": "Customer return",
            "branch": {"warehouse": "WH-KW"},
            "items": [{"sku": "SKU-1", "quantity": 1, "rate": 2.5}],
        }

        first = self.api.upsert_pos_return("return-key", **{"return": payload})
        second = self.api.upsert_pos_return("return-key", **{"return": payload})
        credit_note = self.frappe._store["Sales Invoice"][first["name"]].as_dict()

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(original["name"], credit_note["return_against"])
        self.assertEqual(-1, credit_note["items"][0]["qty"])

    def test_upsert_cash_movement_creates_journal_entry_and_returns_existing_duplicate(self):
        payload = {
            "company": "Baby House Co",
            "occurred_at": "2026-06-25T10:00:00",
            "reason": "Cash in",
            "session_uuid": "session-1",
            "cash_account": "Cash - BH",
            "counterparty_account": "POS Clearing - BH",
            "type": "in",
            "amount": 5,
        }

        first = self.api.upsert_cash_movement("movement-key", payload)
        second = self.api.upsert_cash_movement("movement-key", payload)
        journal = self.frappe._store["Journal Entry"][first["name"]].as_dict()

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(1, journal["docstatus"])
        self.assertEqual(5.0, journal["accounts"][0]["debit_in_account_currency"])

    def test_upsert_pos_session_creates_opening_closing_and_returns_existing_duplicates(self):
        opening_payload = {
            "uuid": "session-1",
            "status": "open",
            "opened_at": "2026-06-25T09:00:00",
            "opening_cash": 20,
            "branch": {"company": "Baby House Co", "pos_profile": "KW POS"},
            "cashier": {"user_id": "cashier@example.test"},
        }
        closing_payload = {
            **opening_payload,
            "status": "closed",
            "closed_at": "2026-06-25T17:00:00",
            "payment_totals": {"Cash": 40},
        }

        opening = self.api.upsert_pos_session("opening-key", opening_payload)
        duplicate_opening = self.api.upsert_pos_session("opening-key", opening_payload)
        closing = self.api.upsert_pos_session("closing-key", closing_payload)
        duplicate_closing = self.api.upsert_pos_session("closing-key", closing_payload)
        closing_doc = self.frappe._store["POS Closing Entry"][closing["name"]].as_dict()

        self.assertTrue(opening["created"])
        self.assertFalse(duplicate_opening["created"])
        self.assertTrue(closing["created"])
        self.assertFalse(duplicate_closing["created"])
        self.assertEqual(opening["name"], closing_doc["pos_opening_entry"])

    def test_pos_sync_audit_reports_existing_missing_and_orphan_documents(self):
        self.api.upsert_cashier("cashier-key", {"uuid": "cashier-1", "email": "cashier@example.test", "employee_code": "C100", "name": "Cashier"})
        self.api.upsert_pos_sale("sale-key", self.sale_payload())
        self.api.upsert_pos_sale("orphan-key", {**self.sale_payload(), "server_invoice_no": "S-ORPHAN"})

        result = self.api.pos_sync_audit(["pos-cashier:cashier-1", "sale-key", "missing-key"])

        self.assertEqual({"pos-cashier:cashier-1", "sale-key"}, {row["idempotency_key"] for row in result["documents"]})
        self.assertEqual(["missing-key"], result["missing_keys"])
        self.assertEqual(["orphan-key"], [row["idempotency_key"] for row in result["orphan_documents"]])

    @staticmethod
    def sale_payload():
        return {
            "branch": {"code": "KW", "company": "Baby House Co", "warehouse": "WH-KW", "pos_profile": "KW POS", "default_customer": "Walk In"},
            "cashier": {"code": "C100"},
            "currency": "KWD",
            "posting_datetime": "2026-06-25T10:00:00",
            "local_invoice_no": "L-1",
            "server_invoice_no": "S-1",
            "session_uuid": "session-1",
            "items": [{"sku": "SKU-1", "quantity": 1, "rate": 2.5}],
            "payments": [{"mode_of_payment": "Cash", "amount": 2.5, "account": "Cash - BH"}],
        }


if __name__ == "__main__":
    unittest.main()
