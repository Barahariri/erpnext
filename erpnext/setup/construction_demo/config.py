"""Deterministic, fictional construction-company demo definitions.

Everything in this module is synthetic and must never be used as legal, tax,
banking, payroll or foreign-exchange reference data.
"""

from dataclasses import dataclass

START_DATE = "2023-11-01"
END_DATE = "2026-10-31"
SEED_VERSION = "construction-demo-v1"
CONFIRMATION = "GENERATE_CONSTRUCTION_DEMO"

# Counts are per company: 1,080 employees; 86 projects; 470 pieces of
# equipment; 250 customers; 360 suppliers across all three.
@dataclass(frozen=True)
class CompanyPlan:
    name: str
    abbr: str
    country: str
    currency: str
    headquarters: str
    sites: tuple[str, ...]
    employees: int
    projects: int
    equipment: int
    customers: int
    suppliers: int


COMPANIES = (
    CompanyPlan(
        "شركة ركيزة الأفق للمقاولات العامة",
        "KRC",
        "Kuwait",
        "KWD",
        "الشويخ الصناعية",
        ("الشويخ الصناعية", "الأحمدي"),
        410, 34, 190, 100, 140,
    ),
    CompanyPlan(
        "شركة رواسي الدوحة للإنشاءات",
        "RDC",
        "Qatar",
        "QAR",
        "الدوحة",
        ("الدوحة", "الريان"),
        350, 28, 150, 80, 120,
    ),
    CompanyPlan(
        "شركة مدائن الشام للهندسة والمقاولات",
        "MSE",
        "Syria",
        "SYP",
        "دمشق",
        ("دمشق", "ريف دمشق"),
        320, 24, 130, 70, 100,
    ),
)

PROJECT_TYPES = (
    "مجمع سكني", "مبنى تجاري", "تطوير طرق", "شبكة مياه",
    "مستودعات صناعية", "مدرسة", "مركز طبي", "أعمال كهرباء",
    "أعمال ميكانيكا", "صيانة منشآت", "بنية تحتية", "تشطيبات",
)
PROJECT_STAGES = (
    "التحضير والتصميم", "تجهيز الموقع", "الهيكل الإنشائي",
    "الأعمال الميكانيكية والكهربائية", "التشطيبات والتسليم",
)
EQUIPMENT_TYPES = (
    "حفارة جنزير", "رافعة متنقلة", "شيول", "شاحنة قلاب",
    "مولد كهرباء", "مدحلة", "خلاطة خرسانة", "رافعة شوكية",
    "ضاغط هواء", "مضخة خرسانة", "جرافة", "صهريج مياه",
)
MATERIALS = (
    "أسمنت بورتلاندي", "حديد تسليح", "بلوك خرساني",
    "رمل مغسول", "حصى متدرج", "خرسانة جاهزة", "كيبل كهربائي",
    "ماسورة PVC", "عازل مائي", "دهان داخلي", "سيراميك أرضيات",
    "قواطع كهربائية", "ألواح جبس", "مسامير", "زجاج أمان",
    "أبواب مقاومة للحريق", "شبك تسليح", "أنابيب نحاسية",
)
DEPARTMENTS = (
    "Engineering", "Projects", "Procurement", "Finance",
    "Human Resources", "Safety", "Warehouse", "Operations",
)
DESIGNATIONS = (
    "Project Manager", "Site Engineer", "Civil Engineer",
    "Electrician", "Mechanical Technician", "Accountant",
    "Procurement Officer", "Storekeeper", "Safety Officer",
    "Equipment Operator", "Driver", "Construction Worker",
)
FIRST_NAMES = (
    "أحمد", "محمد", "يوسف", "خالد", "عمر", "سامر", "علي",
    "محمود", "حسام", "ياسر", "فاطمة", "سارة", "نور", "ليلى",
)
LAST_NAMES = (
    "الحسن", "العلي", "الخالد", "الناصر", "الحموي", "الشامي",
    "المطيري", "العتيبي", "الهاجري", "المنصور", "الغانم",
)
ORG_NAMES = (
    "الأفق", "المتحدة", "المنارة", "الابتكار", "رواد البناء",
    "السند", "الصفوة", "العمران", "النخبة", "الإنجاز",
)


def scaled(total: int, scale: str) -> int:
    """Pilot mode allows cheap schema and dependency verification first."""
    if scale == "full":
        return total
    if scale == "pilot":
        return max(1, min(total, (total + 99) // 100))
    raise ValueError("scale must be 'pilot' or 'full'")


def expected_totals(scale: str = "full") -> dict[str, int]:
    """Exact planned counts; not proof that anything has been inserted."""
    return {
        "companies": len(COMPANIES),
        "employees": sum(scaled(c.employees, scale) for c in COMPANIES),
        "projects": sum(scaled(c.projects, scale) for c in COMPANIES),
        "equipment": sum(scaled(c.equipment, scale) for c in COMPANIES),
        "customers": sum(scaled(c.customers, scale) for c in COMPANIES),
        "suppliers": sum(scaled(c.suppliers, scale) for c in COMPANIES),
        "materials": scaled(1200, scale),
    }
