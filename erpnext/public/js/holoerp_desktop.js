frappe.provide("erpnext.holo_desktop");

erpnext.holo_desktop.get_workspaces = function () {
	const boot_pages =
		frappe.boot.allowed_workspaces || (frappe.boot.workspaces && frappe.boot.workspaces.pages) || [];
	const unique_pages = new Map();

	for (const page of boot_pages) {
		if (!page || !page.name || page.is_hidden || page.title === "Welcome Workspace") {
			continue;
		}

		unique_pages.set(page.name, page);
	}

	return Array.from(unique_pages.values());
};

erpnext.holo_desktop.get_route = function (page) {
	if (page.link_type === "URL" && page.external_link) {
		return page.external_link;
	}

	if (page.link_type && page.link_to) {
		return frappe.utils.get_form_link(page.link_type, page.link_to);
	}

	return `/desk/${frappe.router.slug(page.name)}`;
};

erpnext.holo_desktop.get_icon = function (page, label) {
	if (page.icon && frappe.utils.icon) {
		return frappe.utils.icon(page.icon, "lg", "", "", "holoerp-workspace-svg", true);
	}

	return frappe.utils.desktop_icon(label, "blue", "lg", "Solid");
};

erpnext.holo_desktop.render = function (desktop, pages) {
	if (!desktop || !desktop.wrapper || !pages.length) {
		return;
	}

	const $container = desktop.wrapper.find(".icons-container").first();
	if (!$container.length) {
		return;
	}

	$container
		.empty()
		.addClass("holoerp-workspace-icons-container")
		.attr("data-holoerp-workspace-count", pages.length);

	const $grid = $(`<div class="holoerp-workspace-icons icons"></div>`).appendTo($container);

	for (const page of pages) {
		const label = page.title || page.label || page.name;
		const route = erpnext.holo_desktop.get_route(page);
		const translated_label = __(label);
		const icon_html = erpnext.holo_desktop.get_icon(page, label);

		const $icon = $(
			`<a class="desktop-icon holoerp-workspace-icon" style="text-decoration:none"></a>`
		)
			.attr("href", route)
			.attr("aria-label", translated_label);

		if (route.startsWith("http")) {
			$icon.attr("target", "_blank").attr("rel", "noopener noreferrer");
		}

		$(`<div class="icon-container holoerp-workspace-icon-container"></div>`)
			.html(icon_html)
			.appendTo($icon);

		$(`<div class="icon-caption"></div>`)
			.append(
				$(`<div class="icon-title" data-toggle="tooltip"></div>`)
					.text(translated_label)
					.attr("data-original-title", translated_label)
			)
			.appendTo($icon);

		$grid.append($icon);
	}

	$('[data-toggle="tooltip"]').tooltip({ placement: "bottom" });
};

erpnext.holo_desktop.load_and_render = function (desktop) {
	const pages = erpnext.holo_desktop.get_workspaces();
	if (pages.length) {
		erpnext.holo_desktop.render(desktop, pages);
		return;
	}

	frappe.call({
		method: "frappe.desk.desktop.get_workspaces",
		callback: function (response) {
			const message = response && response.message;
			if (!message || !message.pages) {
				return;
			}

			frappe.boot.workspaces = message;
			frappe.boot.allowed_workspaces = message.pages;
			erpnext.holo_desktop.render(desktop, erpnext.holo_desktop.get_workspaces());
		},
	});
};

$(document).on("desktop_screen", function (event, data) {
	window.requestAnimationFrame(() => {
		erpnext.holo_desktop.load_and_render(data.desktop);
	});
});
