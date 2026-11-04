# ERPNext Construction Multi-Company Seeder V3

**Branch:** `feature/construction-complete-seeder-v3`  
**Repository:** `Barahariri/erpnext`  
**Target:** `erpnext-clean-backend-1`, site `frontend`, domain `https://newerp.holotechnology.net`

> This is a **training/demo data generator**, not a production migration or tax/payroll certification. It is not yet verified against the user's running ERPNext database.

## البيانات

الشركات الثلاث مستقلة وبعملات مختلفة:

| Company | Country | Currency | Code |
|---|---|---|---|
| Al Muhannadi Contracting | Qatar | QAR | AMQ |
| Al Furqan Contracting | Kuwait | KWD | AFK |
| Al Salem Contracting | Syria | SYP | ALS |

- حسابات ERPNext القياسية + حسابات المقاولات المتخصصة، و`Account.account_number` من ست خانات.
- عملاء وموردون ومقاولون باطن، موظفون وسائقون، مشاريع ومهام ومراكز تكلفة ومستودعات.
- أوامر بيع وشراء، فواتير وتحصيلات وقيود افتتاحية، استلام وصرف مخزون.
- أسطول مركبات مع وقود وسجلات استخدام وصيانة، وعينات أصول ومعدات.
- HRMS + حضور وإعداد هياكل رواتب تجريبية (بدون اعتماد مسيرات رواتب فعلية).
- حساب بنكي منفصل لكل شركة وحركات بنك تجريبية ولوحات إحصائية مفلترة حسب الشركة.
- عينات **سبتمبر وأكتوبر ونوفمبر 2026**؛ بيانات نوفمبر تنتهي في أو قبل **4 نوفمبر 2026**.

## التنزيل من GitHub على السيرفر

هذا المستودع يتضمن تطبيق ERPNext كاملًا، لذلك نستخدم `sparse checkout` لتنزيل ملفات الـSeeder فقط، **بدون build أو تحديث صور Docker**.

```bash
set -e
BRANCH=feature/construction-complete-seeder-v3
REPO=https://github.com/Barahariri/erpnext.git
DEST=/root/erpnext-seeder-src

if [ ! -d "$DEST/.git" ]; then
  git clone --depth 1 --filter=blob:none --sparse     --single-branch --branch "$BRANCH" "$REPO" "$DEST"
  git -C "$DEST" sparse-checkout set tools/construction_demo
else
  git -C "$DEST" switch "$BRANCH"
  git -C "$DEST" pull --ff-only origin "$BRANCH"
fi

cd "$DEST/tools/construction_demo"
python3 verify_kit_static.py
bash run_from_git.sh
```

في المرات التالية، يكفي:

```bash
git -C /root/erpnext-seeder-src pull --ff-only origin feature/construction-complete-seeder-v3
bash /root/erpnext-seeder-src/tools/construction_demo/run_from_git.sh
```

**مهم:** التشغيل الثاني يعيد التحقق ويستعمل مفاتيح عمل ثابتة لتفادي تكرار معظم السجلات. لا تُعد التشغيل تلقائيًا إذا ظهر خطأ في التحقق؛ احفظ أول traceback لمعالجة السبب.

## تدقيق فقط (بعد إتمام التعبئة)

```bash
bash /root/erpnext-seeder-src/tools/construction_demo/run_from_git.sh --audit
```

علامة النجاح: `CONSTRUCTION_DEMO_V3_READY` و`report.issues = []`.  
فحوص Python وGitHub Actions **لا تثبت** نجاح القيود والفواتير في ERPNext. يجب التحقق من سجلات السيرفر ونتائج تقرير التدقيق ومراجعة عمل أقسام Banking/Projects/Stock/HR/Fleet.

## الأمان

- السكربت يستهدف مشروع Compose `erpnext-clean` فقط، ويرفض التنفيذ إذا اختلف اسم الحاوية أو دومين الموقع.
- يأخذ نسخة احتياطية للموقع الجديد قبل تعبئة البيانات.
- لا ينفّذ `docker compose down` ولا يغيّر Proxy أو `erp.holotechnology.net`.
- قد تزداد موارد CPU وRAM أثناء تعبئة البيانات في السيرفر؛ عدم إعادة تشغيل النسخة القديمة ليس ضمانًا لعدم تأثر أدائها تحت الضغط.
- جميع الشركات والأشخاص والمشاريع وأرقام الحسابات البنكية والأنشطة **وهمية لأغراض الاختبار**.
- لا تنقل بيانات التجربة إلى نظام إنتاج حقيقي.


## إصلاح تعليق مرحلة Account Numbering في V3

إذا توقف الإصدار القديم عند `=== Phase 1` وكانت الشركات الثلاث موجودة لكن الحسابات القياسية بلا أرقام، **لا تشغّل Seeder ثانية بالتوازي**. أُصلحت خوارزمية الترقيم في هذا الـBranch: تُكتب أرقام الحسابات مباشرةً في `Account.account_number` في قاعدة DEMO الجديدة الخالية من قيود GL، من دون إعادة تسمية معرفات الحسابات المرتبطة بالمستندات. هذه ليست عملية إعادة ترقيم معتمدة للإنتاج.

على الخادم:

```bash
git -C /root/erpnext-seeder-src pull --ff-only origin feature/construction-complete-seeder-v3
bash /root/erpnext-seeder-src/tools/construction_demo/resume_after_numbering_hang.sh
```

فحص الأمان في الاستكمال يتحقق من اسم حاوية النسخة الجديدة، ويقطع عملية Python القديمة المحددة وحدها بإشارة SIGINT، ويرفض بدء Seeder جديدة إذا بقيت العملية أو قفل التشغيل نشطين. لا يوقف أي حاوية Docker. سكربت التشغيل الأساسي يأخذ نسخة احتياطية جديدة قبل محاولة الاستكمال.

علامات التقدم بعد التصحيح: `NUMBERED:` ثم `COA READY:` ثم `MASTERS:` ثم `FLEET READY:` ثم `Phase 2` ثم `CONSTRUCTION_DEMO_V3_READY`. إذا ظهر STOP أو Traceback، أرسل أول خطأ ولا تكرر التشغيل دون تشخيص.

