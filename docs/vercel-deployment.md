# Vercel deploy (T-Port)

## Tuzilma

Repo ildizidagi `vercel.json` Vercel Services orqali bitta loyihada ikki service ochadi:

- `frontend/`: Next.js. Sahifalar shu yerga yo'naltiriladi.
- `backend/`: FastAPI (`main:app`). `/api/*`, `/health`, `/health/providers`, `/metrics` shu yerga boradi.
- Frontend serveridagi `API_INTERNAL_URL` qiymatini Vercel binding yaratadi: har bir Preview o'z
  backendiga ulanadi. Uni qo'lda kiritmang. Browser faqat saytning o'z domeniga so'rov yuboradi;
  session va CSRF cookie'lari bir domenda ishlaydi.

`http://localhost:2028/` uchun eski ishga tushirish tartibi o'zgarmaydi: web 2028, API 8000.
Docker rejimida `API_INTERNAL_URL=http://api:8000` avvalgidek ishlaydi.

## 1. Vercel loyihasi

Vercel CLI 62.1+ ishlating (yoki Dashboard -> Add New Project -> GitHub repo).

- Repo: `uzleeder/t-port`.
- **Root Directory: repo ildizi (`.`)**. `frontend/`ni tanlamang: Services ikkala papkani olishi kerak.
- Repo'dagi `vercel.json` service frameworklarini belgilaydi. Dashboard'dagi eski Build Command,
  Install Command va Output Directory override'larini tozalang; `npm run build`ni repo ildizida ishlatmang.
- Frontend uchun Node.js **22.x**, backend uchun Python **3.12** (`backend/.python-version`).
- Services feature loyiha uchun mavjud bo'lishi kerak; joriy konfiguratsiya shu imkoniyatga tayangan.

Lokal production build ham Node 22 bilan tekshiriladi. Windowsda Node 22 uchun Turbopack
worker-thread rejimi yoqilgan; Vercel/Linux standart rejimda ishlaydi. Node 24 yordamchi
process bilan ushbu kompyuterda xato berdi, shuning uchun loyihada Node 22 tanlandi.

## 2. PostgreSQL va environment

Storage/Marketplace'dan Neon yoki boshqa managed PostgreSQL ulang. Preview va Production uchun
**alohida bazalar** ishlating. Supabase ishlatilsa serverless uchun provider tavsiya qilgan pooler URLni oling.
SQLite faylini Vercel bazasi sifatida ishlatmang: function fayllari doimiy yoziladigan saqlash emas.

`deploy/vercel.env.example`dagi qiymatlarni tegishli Environment Variables bo'limiga kiriting:

| O'zgaruvchi | Qiymat |
|---|---|
| `TPORT_DATABASE_URL` yoki `DATABASE_URL` | Pooled PostgreSQL URL, TLS bilan; birinchisi ustun |
| `TPORT_MIGRATION_DATABASE_URL` yoki `DATABASE_URL_UNPOOLED` | Direct URL, migratsiyalar uchun |
| `TPORT_CORS_ORIGINS` | Saytingizning aniq HTTPS originlari JSON list shaklida |
| `TPORT_ENVIRONMENT` | `production` (Vercel entrypoint Preview'da ham production himoyasini majburlaydi) |
| `TPORT_AI_ENGINE` | `rules`: kalitsiz parser; AI key ixtiyoriy |
| `TPORT_LOG_FORMAT` | `json` |
| `TPORT_RATE_LIMIT_BACKEND` | `database` |

`postgres://` va `postgresql://` URLlar avtomatik `psycopg` driveriga moslashtiriladi. Parolda maxsus
belgilar bo'lsa, provider bergan URL-encoded shaklini saqlang. URL yoki kalitlarni chatga yubormang.

`TPORT_CORS_ORIGINS`ga Production domeni va ishlatilayotgan Preview domenini aniq kiriting.
Preview URL ma'lum bo'lgach environmentni yangilab redeploy qiling; wildcard yoki barcha domenlarga
ruxsat bermang. `API_INTERNAL_URL`ni Vercel binding boshqaradi; `localhost` bilan override qilmang.
Ikkala test flagi ham `false` bo'lishi kerak; server entrypoint ularni yoqishga ruxsat bermaydi.

## 3. Bir martalik database setup

Cold start va frontend build migratsiya yoki seed bajarmaydi. Avval backup oling, migratsiyalarni
ko'rib chiqing. Faqat tanlangan muhit bazasiga ulanadigan xavfsiz terminalda, repo ildizidan:

```powershell
Set-Location backend
# URLlarni oldindan process environmentga xavfsiz kiriting (yoki git-ignore qilingan backend/.env).
.venv/Scripts/python -m scripts.vercel_setup
Set-Location ..
```

Linux'da `.venv/bin/python -m scripts.vercel_setup`. Buyruq `alembic upgrade head` va idempotent
reference seed bajaradi; foydalanuvchi akkauntlari yoki parollar yaratmaydi. Direct URL bo'lmasa
runtime URL ishlatiladi. Bir vaqtda faqat bitta setup buyrug'ini bajaring. Yangi migratsiyalar
paydo bo'lganda shu release qadamini qaytaring. Production sirlari bilan lokal testlar ishlatmang.

## 4. Preview, tekshirish, Production

Repo ildizidan (CLI bilan) yoki GitHub integration orqali:

```powershell
vercel link
vercel deploy
```

Preview'da quyidagilarni tekshiring:

- Bosh sahifa va qidiruv natijalari yuklanadi; demo belgisi ko'rinadi.
- `/health` javobi `database: "ok"` bo'ladi.
- `/api/v1/locations?q=Toshkent` va journey search ishlaydi.
- Register -> login -> save -> logout -> login -> saved journey saqlanib qoladi.
- AI assistant `rules` bilan ishlaydi; demo journey bookingga ruxsat bermaydi.
- Ops token bo'lmasa `/metrics` va `/health/providers` 404 qaytaradi.

Himoyalangan Preview'ni Vercel login bilan tekshiring. Provision qilingan baza va URL ishlashini
tekshirmasdan deploy muvaffaqiyatli deb hisoblamang. Tekshiruvdan keyin Production uchun:

```powershell
vercel deploy --prod
```

Bu qo'llanma tayyorlashni tushuntiradi; ushbu o'zgarishning o'zi cloud deploy yoki baza yaratmaydi.

## Serverless chegaralari

- DB ulanishlar instance ichida ushlab turilmaydi (`NullPool`); managed poolerdan foydalaning.
- In-memory umumiy API limiter va metrics har bir function instance uchun alohida; auth/AI
  limiterlari PostgreSQL orqali umumiy. Metricsni to'liq fleet statistikasi deb talqin qilmang.
- `python -m app.cli scheduler` doimiy loopini request function ichida ishlatmang. Stored/live
  importlar uchun alohida tashqi scheduler/worker va provider ruxsati kerak. Hozir demo `live`
  rejimi request paytida simulyatsiya ma'lumotini yaratadi, cron talab qilmaydi.
- Function timeout, upstream latency va DB regionini Preview'da o'lchang. Og'ir importni request
  yoki frontend build ichiga joylashtirmang.
- Rollback: Vercel oldingi deploymentni qaytaradi; database migratsiyasi avtomatik qaytmaydi.
  `docs/deployment.md`dagi migratsiya va rollback tartibini bajaring.

## Manbalar

- https://vercel.com/docs/frameworks/backend/fastapi
- https://vercel.com/docs/services/routing
- https://vercel.com/docs/services/bindings
- https://vercel.com/kb/guide/python-backend-on-vercel
