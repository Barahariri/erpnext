"""Deterministic, synthetic construction-company demonstration catalogue.

Project names/locations are fictitious contract examples in real districts.
Equipment manufacturers/model families are authentic product names, while
all assigned asset numbers, years, hours, locations and ownership are invented.
No taxpayer numbers, asset serials, official contracts or exchange rates here.
"""
from __future__ import annotations

from dataclasses import dataclass

START_DATE = "2023-11-01"
END_DATE = "2026-10-31"
SEED_VERSION = "construction-demo-v2-realistic-catalog"
CONFIRMATION = "GENERATE_CONSTRUCTION_DEMO"
MATERIAL_COUNT = 240


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


@dataclass(frozen=True)
class ProjectPlan:
    name: str
    district: str
    sector: str
    scope: str
    duration_months: int


@dataclass(frozen=True)
class EquipmentModel:
    kind: str
    kind_ar: str
    manufacturer: str
    model: str
    estimated_kwd: int
    fuel_lph: float


COMPANIES = (
    CompanyPlan(
        "شركة ركيزة الأفق للمقاولات العامة", "KRC", "Kuwait", "KWD",
        "الشويخ الصناعية", ("الشويخ الصناعية", "الأحمدي"),
        60, 9, 30, 24, 35,
    ),
    CompanyPlan(
        "شركة رواسي الدوحة للإنشاءات", "RDC", "Qatar", "QAR",
        "الدوحة", ("الدوحة", "الريان"),
        50, 7, 24, 18, 30,
    ),
    CompanyPlan(
        "شركة مدائن الشام للهندسة والمقاولات", "MSE", "Syria", "SYP",
        "دمشق", ("دمشق", "ريف دمشق"),
        45, 6, 20, 16, 25,
    ),
)

# Descriptive, geographically plausible PRIVATE projects; none asserts that
# this construction contract, owner or development actually exists.
PROJECT_CATALOG = {
    "KRC": (
        ProjectPlan("مجمع النخيل السكني", "الأحمدي", "Buildings",
                    "إنشاء مبنيين سكنيين من الخرسانة المسلحة مع أعمال التكييف والكهرباء والتشطيبات", 20),
        ProjectPlan("مركز الشويخ للخدمات اللوجستية", "الشويخ الصناعية", "Industrial",
                    "تشييد مستودعات وهيكل معدني وأرضيات صناعية ومرافق تحميل", 16),
        ProjectPlan("توسعة مبنى الأعمال الشرقي", "شرق", "Buildings",
                    "توسعة مبنى إداري بأعمال إنشائية وواجهات ألمنيوم وشبكات كهرباء", 15),
        ProjectPlan("تأهيل تصريف مياه الأمطار بالفحيحيل", "الفحيحيل", "Infrastructure",
                    "تنفيذ خطوط تصريف وغرف تفتيش وأعمال حفر وردم وإعادة سفلتة", 14),
        ProjectPlan("ورش الصيانة الصناعية", "صبحان", "Industrial",
                    "بناء ورش صيانة وساحات خرسانية وشبكات مكافحة حريق", 18),
        ProjectPlan("تطوير الممرات والمواقف", "السالمية", "Roads",
                    "أعمال أرصفة وممرات مشاة ومواقف سيارات وإنارة خارجية", 11),
        ProjectPlan("مبنى العيادات التخصصية", "حولي", "Buildings",
                    "تنفيذ الهيكل والتشطيبات الطبية وأنظمة التهوية والكهرباء", 22),
        ProjectPlan("تمديد خدمات موقع الجهراء", "الجهراء", "Infrastructure",
                    "تمديد مجاري خدمات واتصالات ومياه وأعمال إعادة تأهيل الطرق", 13),
        ProjectPlan("مجمع المحال التجارية", "العقيلة", "Buildings",
                    "مبنى تجاري منخفض الارتفاع مع أنظمة التكييف والمواقف", 17),
    ),
    "RDC": (
        ProjectPlan("برج الواحة السكني", "لوسيل", "Buildings",
                    "هيكل مبنى سكني متعدد الطوابق وواجهات وأعمال MEP", 23),
        ProjectPlan("مستودعات المنطقة الصناعية", "المنطقة الصناعية", "Industrial",
                    "إنشاء مستودعات معدنية وأرضيات عالية التحمل ومناطق تحميل", 15),
        ProjectPlan("تأهيل مرافق المدرسة", "الريان", "Buildings",
                    "تجديد مختبرات وقاعات وشبكات تكييف وكهرباء ومكافحة حريق", 10),
        ProjectPlan("مبنى الأعمال الإداري", "الخليج الغربي", "Buildings",
                    "أعمال خرسانة وتشطيبات ومصاعد وتكييف مركزي", 19),
        ProjectPlan("تطوير مواقف المركز التجاري", "الوكرة", "Roads",
                    "سفلتة مواقف وأنظمة تصريف وإنارة وعلامات أرضية", 12),
        ProjectPlan("المرافق الخدمية بأم صلال", "أم صلال", "Infrastructure",
                    "إنشاء غرف مضخات وخطوط أنابيب ومرافق خدمات أساسية", 16),
        ProjectPlan("تحديث أنظمة مبنى الأعمال", "الدوحة", "MEP",
                    "استبدال وحدات تكييف ومضخات وخطوط إطفاء ولوحات توزيع", 9),
    ),
    "MSE": (
        ProjectPlan("تأهيل بناية الروابي السكنية", "المزة", "Renovation",
                    "ترميم عناصر إنشائية وواجهات وتجديد الشبكات الصحية والكهربائية", 14),
        ProjectPlan("ترميم مركز تعليمي", "الميدان", "Renovation",
                    "إعادة تأهيل صفوف وممرات ودورات مياه وشبكات إنارة", 9),
        ProjectPlan("مستودع عدرا الإنشائي", "عدرا الصناعية", "Industrial",
                    "تنفيذ مستودع بهيكل معدني وأرضيات خرسانية ومناطق تحميل", 17),
        ProjectPlan("تأهيل صرف صحي داخلي", "جرمانا", "Infrastructure",
                    "استبدال مقاطع صرف وغرف تفتيش وإعادة تأهيل الحفريات", 11),
        ProjectPlan("مبنى الإدارة والخدمات", "صحنايا", "Buildings",
                    "إنشاء مبنى إداري صغير مع شبكات ميكانيكية وكهربائية", 18),
        ProjectPlan("تحديث أنظمة الخدمات", "قدسيا", "MEP",
                    "تجديد أنظمة تكييف وكهرباء ومضخات مياه لمبنى قائم", 10),
    ),
}

# Manufacturer/model names reflect actual machine product families.
# No claim is made that a particular machine was built, purchased or registered.
EQUIPMENT_CATALOG = (
    EquipmentModel("Excavator", "حفارة جنزير", "Caterpillar", "320 GC", 52000, 15.0),
    EquipmentModel("Excavator", "حفارة جنزير", "Komatsu", "PC210-10M0", 50000, 15.5),
    EquipmentModel("Excavator", "حفارة جنزير", "Volvo", "EC220D", 56000, 16.5),
    EquipmentModel("Backhoe", "حفار لودر", "JCB", "3CX", 29000, 8.0),
    EquipmentModel("Wheel Loader", "شيول", "Caterpillar", "950 GC", 65000, 17.0),
    EquipmentModel("Wheel Loader", "شيول", "Komatsu", "WA380-8", 62000, 17.5),
    EquipmentModel("Bulldozer", "بلدوزر", "Caterpillar", "D6", 110000, 23.0),
    EquipmentModel("Mobile Crane", "رافعة متنقلة", "Liebherr", "LTM 1050-3.1", 165000, 20.0),
    EquipmentModel("Rough Terrain Crane", "رافعة مواقع وعرة", "Tadano", "GR-500EX", 140000, 19.0),
    EquipmentModel("Road Roller", "مدحلة اهتزازية", "BOMAG", "BW 211 D-5", 47000, 12.0),
    EquipmentModel("Road Roller", "مدحلة اهتزازية", "HAMM", "3411", 46000, 11.5),
    EquipmentModel("Dump Truck", "شاحنة قلاب", "Volvo", "FMX 420", 40000, 21.0),
    EquipmentModel("Dump Truck", "شاحنة قلاب", "Mercedes-Benz", "Arocs 3342", 42000, 22.0),
    EquipmentModel("Concrete Pump", "مضخة خرسانة", "Putzmeister", "M36-4", 115000, 20.0),
    EquipmentModel("Telehandler", "رافعة تلسكوبية", "JCB", "540-170", 37000, 11.0),
    EquipmentModel("Forklift", "رافعة شوكية", "Toyota", "8FD30", 12000, 5.0),
    EquipmentModel("Generator", "مولد ديزل", "FG Wilson", "P220-3", 19000, 13.0),
    EquipmentModel("Air Compressor", "ضاغط هواء متنقل", "Atlas Copco", "XAS 188", 11000, 10.0),
)

# The remaining legacy constants are used by the generic master seed.
PROJECT_TYPES = tuple(x.name for p in PROJECT_CATALOG.values() for x in p)
PROJECT_STAGES = (
    "التحضير والتصميم", "تجهيز الموقع", "الهيكل الإنشائي",
    "الأعمال الميكانيكية والكهربائية", "التشطيبات والتسليم",
)
EQUIPMENT_TYPES = tuple(m.kind_ar for m in EQUIPMENT_CATALOG)
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


def billing_cycles(plan: CompanyPlan, index: int) -> int:
    """Number of realistic two-month certification cycles within project duration."""
    specification = PROJECT_CATALOG[plan.abbr][index - 1]
    return min(8, max(3, (specification.duration_months + 1) // 2))


def scaled(total: int, scale: str) -> int:
    if scale == "full":
        return total
    if scale == "pilot":
        return max(1, min(total, (total + 99) // 100))
    raise ValueError("scale must be 'pilot' or 'full'")


def expected_totals(scale: str = "full") -> dict[str, int]:
    return {
        "companies": len(COMPANIES),
        "employees": sum(scaled(c.employees, scale) for c in COMPANIES),
        "projects": sum(scaled(c.projects, scale) for c in COMPANIES),
        "equipment": sum(scaled(c.equipment, scale) for c in COMPANIES),
        "customers": sum(scaled(c.customers, scale) for c in COMPANIES),
        "suppliers": sum(scaled(c.suppliers, scale) for c in COMPANIES),
        "materials": scaled(MATERIAL_COUNT, scale),
    }
