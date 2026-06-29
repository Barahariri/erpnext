import frappe


HOLOERP_APP_NAME = "HoloERP"
HOLOERP_SETTINGS_TITLE = "HoloERP Settings"
HOLOERP_LOGO_URL = "/assets/erpnext/images/holoerp-logo.png"
HOLOERP_FAVICON_URL = "/assets/erpnext/images/holoerp-favicon.png"


def execute():
	"""Apply HoloERP user-facing branding to already-installed sites.

	Internal app/module identifiers remain unchanged as `erpnext` so migrations,
	imports, doctypes, and upstream-compatible integrations keep working.
	"""

	set_single_value_if_field_exists("System Settings", "app_name", HOLOERP_APP_NAME)
	set_single_value_if_field_exists("Website Settings", "app_name", HOLOERP_APP_NAME)
	set_single_value_if_field_exists("Website Settings", "favicon", HOLOERP_FAVICON_URL)
	set_single_value_if_field_exists("Website Settings", "splash_image", HOLOERP_LOGO_URL)

	update_doc_if_exists(
		"Desktop Icon",
		"ERPNext",
		{
			"label": HOLOERP_APP_NAME,
			"logo_url": HOLOERP_LOGO_URL,
		},
	)
	update_doc_if_exists(
		"Desktop Icon",
		"ERPNext Settings",
		{
			"label": HOLOERP_SETTINGS_TITLE,
		},
	)
	update_doc_if_exists(
		"Workspace",
		"ERPNext Settings",
		{
			"label": HOLOERP_SETTINGS_TITLE,
			"title": HOLOERP_SETTINGS_TITLE,
		},
	)
	update_doc_if_exists(
		"Workspace Sidebar",
		"ERPNext Settings",
		{
			"title": HOLOERP_SETTINGS_TITLE,
		},
	)

	frappe.clear_cache()


def set_single_value_if_field_exists(doctype, fieldname, value):
	if not frappe.db.exists("DocType", doctype):
		return

	meta = frappe.get_meta(doctype)
	if not meta.has_field(fieldname):
		return

	frappe.db.set_single_value(doctype, fieldname, value)


def update_doc_if_exists(doctype, name, values):
	if not frappe.db.exists("DocType", doctype) or not frappe.db.exists(doctype, name):
		return

	meta = frappe.get_meta(doctype)
	safe_values = {field: value for field, value in values.items() if meta.has_field(field)}
	if safe_values:
		frappe.db.set_value(doctype, name, safe_values, update_modified=False)
