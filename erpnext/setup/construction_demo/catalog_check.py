"""Offline catalogue quality checks (stdlib only, no Frappe/database required).

This verifies DEMO data naming and dimensions without requiring a running site.
The real v16 API/GL workflow still requires pilot integration on Docker.
"""
from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path


def _catalog():
    filepath = Path(__file__).with_name("config.py")
    spec = importlib.util.spec_from_file_location("_demo_catalog_config", filepath)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the construction catalogue")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    config = _catalog()
    expected = {
        "companies": 3, "employees": 155, "projects": 22,
        "equipment": 74, "customers": 58,
        "suppliers": 90, "materials": 240,
    }
    assert config.expected_totals("full") == expected
    assert config.START_DATE == "2023-11-01"
    assert config.END_DATE == "2026-10-31"

    assert len(config.COMPANIES) == 3
    assert len(set(p.abbr for p in config.COMPANIES)) == 3
    all_names = []
    for company in config.COMPANIES:
        plans = config.PROJECT_CATALOG[company.abbr]
        assert len(plans) == company.projects
        assert len({(p.name, p.district) for p in plans}) == len(plans)
        for project in plans:
            assert len(project.name.strip()) >= 8
            assert len(project.scope.strip()) >= 24
            assert project.district.strip()
            assert 8 <= project.duration_months <= 25
            all_names.append((company.abbr, project.name, project.district))
    assert len(all_names) == expected["projects"]

    models = config.EQUIPMENT_CATALOG
    assert len(models) >= 15
    assert len({(e.manufacturer, e.model) for e in models}) == len(models)
    assert len({e.kind for e in models}) >= 9
    for machine in models:
        assert machine.manufacturer and machine.model and machine.kind_ar
        assert machine.estimated_kwd > 0 and machine.fuel_lph > 0
    assert Counter(p.country for p in config.COMPANIES) == {
        "Kuwait": 1, "Qatar": 1, "Syria": 1,
    }
    print("PASS: unique named projects, authentic manufacturer/model identifiers,"
          " coherent counts and 36-month date range")


if __name__ == "__main__":
    main()
