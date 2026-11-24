/**
 * Interface text for the public landing page, its navigation and the footer, in English, Uzbek
 * (Latin) and Russian. Every string carries all three languages; <T> renders them all and CSS shows
 * the one matching <html lang> (set before first paint from the visitor's choice), so switching is
 * instant and needs no client JavaScript. The rest of the app is English for now.
 */

export const LANGS = ["en", "uz", "ru"] as const;
export type Lang = (typeof LANGS)[number];
export const LANG_LABEL: Record<Lang, string> = { en: "English", uz: "O‘zbek", ru: "Русский" };
export const LANG_SHORT: Record<Lang, string> = { en: "EN", uz: "UZ", ru: "RU" };
export const LANG_KEY = "tport.lang";

export type Tr = Record<Lang, string>;
const t = (en: string, uz: string, ru: string): Tr => ({ en, uz, ru });

export const I18N = {
  // navigation
  "nav.home": t("Home", "Bosh sahifa", "Главная"),
  "nav.explore": t("Explore", "Kashf etish", "Обзор"),
  "nav.how": t("How It Works", "Qanday ishlaydi", "Как это работает"),
  "nav.ai": t("AI Planner", "AI rejalashtiruvchi", "AI-планировщик"),
  "nav.about": t("About", "Biz haqimizda", "О нас"),
  "nav.signIn": t("Sign in", "Kirish", "Войти"),
  "nav.getStarted": t("Get started", "Boshlash", "Начать"),
  "nav.language": t("Language", "Til", "Язык"),
  "nav.menu": t("Menu", "Menyu", "Меню"),
  "nav.close": t("Close menu", "Menyuni yopish", "Закрыть меню"),

  // intro
  "intro.skip": t("Skip intro", "O‘tkazib yuborish", "Пропустить"),
  slogan: t("One Destination. Every Way to Get There.", "Bitta manzil. Unga yetib borishning barcha yo‘llari.", "Одна цель. Все пути к ней."),

  // hero
  "hero.eyebrow": t("The future of travel", "Sayohatning kelajagi", "Будущее путешествий"),
  "hero.line1": t("One Destination.", "Bitta manzil.", "Одна цель."),
  "hero.line2": t("Every Way to Get There.", "Unga yetib borishning barcha yo‘llari.", "Все пути к ней."),
  "hero.desc": t(
    "Discover, compare, and plan your journeys with intelligent transportation technology. Trains, flights, buses, and taxis — together in one platform.",
    "Aqlli transport texnologiyasi bilan sayohatlaringizni toping, solishtiring va rejalashtiring. Poyezdlar, reyslar, avtobuslar va taksilar — barchasi bitta platformada.",
    "Находите, сравнивайте и планируйте поездки с помощью интеллектуальных транспортных технологий. Поезда, авиарейсы, автобусы и такси — на одной платформе.",
  ),
  "hero.cta": t("Explore T-PORT", "T-PORT bilan tanishing", "Открыть T-PORT"),
  "hero.ai": t("Meet Your AI Planner", "AI rejalashtiruvchi bilan tanishing", "Познакомьтесь с AI-планировщиком"),
  "hero.scroll": t("Scroll down", "Pastga aylantiring", "Листайте вниз"),
  "hero.art": t("Artistic illustration montage", "Badiiy illyustratsiyalar kompozitsiyasi", "Художественная композиция иллюстраций"),

  // search
  "search.title": t("Where to?", "Qayerga?", "Куда?"),
  "search.modes": t("Transport", "Transport", "Транспорт"),
  "search.all": t("All", "Barchasi", "Все"),
  "search.train": t("Train", "Poyezd", "Поезд"),
  "search.flight": t("Flight", "Reys", "Авиарейс"),
  "search.bus": t("Bus", "Avtobus", "Автобус"),
  "search.taxi": t("Taxi", "Taksi", "Такси"),
  "search.multimodal": t("Multimodal", "Multimodal", "Мультимодально"),
  "search.multimodalHint": t(
    "Any mode, combined, up to 2 changes",
    "Har qanday transport, birgalikda, 2 tagacha almashinuv",
    "Любой транспорт в комбинации, до 2 пересадок",
  ),
  "search.from": t("From", "Qayerdan", "Откуда"),
  "search.to": t("To", "Qayerga", "Куда"),
  "search.date": t("Date", "Sana", "Дата"),
  "search.placeholder": t("City, district or region", "Shahar, tuman yoki viloyat", "Город, район или область"),
  "search.swap": t("Swap origin and destination", "Jo‘nash va borish joyini almashtirish", "Поменять пункты местами"),
  "search.submit": t("Search journeys", "Yo‘nalishlarni qidirish", "Найти маршруты"),
  "search.searching": t("Searching…", "Qidirilmoqda…", "Поиск…"),
  "search.errPick": t(
    "Choose an origin and a destination from the list.",
    "Ro‘yxatdan jo‘nash va borish joyini tanlang.",
    "Выберите пункты отправления и назначения из списка.",
  ),
  "search.errSame": t(
    "Origin and destination must be different.",
    "Jo‘nash va borish joyi har xil bo‘lishi kerak.",
    "Пункты отправления и назначения должны различаться.",
  ),
  "search.errDate": t("Choose today or a future date.", "Bugungi yoki keyingi sanani tanlang.", "Выберите сегодняшнюю или будущую дату."),
  "search.errModes": t("Select at least one transport mode.", "Kamida bitta transport turini tanlang.", "Выберите хотя бы один вид транспорта."),

  // explore
  "explore.title": t("Explore Uzbekistan.", "O‘zbekistonni kashf eting.", "Откройте Узбекистан."),
  "explore.sub": t(
    "Fourteen regions. Extraordinary destinations. One connected experience.",
    "O‘n to‘rt hudud. Ajoyib manzillar. Yagona bog‘langan tajriba.",
    "Четырнадцать регионов. Удивительные места. Единый опыт путешествий.",
  ),
  "explore.all": t("All regions and places", "Barcha hududlar va joylar", "Все регионы и места"),
  "explore.illus": t("Illustration", "Illyustratsiya", "Иллюстрация"),
  "explore.open": t("Explore", "Ko‘rish", "Смотреть"),

  // AI showcase
  "ai.title1": t("Your Journey.", "Sayohatingiz.", "Ваше путешествие."),
  "ai.title2": t("Reimagined by AI.", "AI bilan yangicha.", "Переосмыслено с AI."),
  "ai.desc": t(
    "Tell us where you want to go, and T-PORT helps you compare routes based on your time, budget, and travel preferences.",
    "Qayerga borishni xohlayotganingizni ayting — T-PORT vaqtingiz, byudjetingiz va afzalliklaringizga qarab yo‘nalishlarni solishtirishga yordam beradi.",
    "Скажите, куда вы хотите поехать, и T-PORT поможет сравнить маршруты с учётом вашего времени, бюджета и предпочтений.",
  ),
  "ai.example": t(
    "Find the best way to travel from Tashkent to Samarkand tomorrow.",
    "Ertaga Toshkentdan Samarqandga borishning eng yaxshi yo‘lini toping.",
    "Найди лучший способ добраться завтра из Ташкента в Самарканд.",
  ),
  "ai.reply": t(
    "I compared {n} options from Tashkent to Samarkand for tomorrow. Here are the highlights:",
    "Ertangi kun uchun Toshkentdan Samarqandga {n} ta variantni solishtirdim. Asosiylari:",
    "Я сравнил {n} вариантов из Ташкента в Самарканд на завтра. Главное:",
  ),
  "ai.none": t(
    "Live results are unavailable right now. Try the planner to search yourself.",
    "Hozircha natijalar mavjud emas. Qidirish uchun rejalashtiruvchini oching.",
    "Результаты сейчас недоступны. Откройте планировщик, чтобы найти маршрут.",
  ),
  "ai.cheapest": t("Cheapest journey", "Eng arzon yo‘nalish", "Самый дешёвый"),
  "ai.fastest": t("Fastest journey", "Eng tez yo‘nalish", "Самый быстрый"),
  "ai.recommended": t("Recommended journey", "Tavsiya etilgan", "Рекомендуемый"),
  "ai.direct": t("Direct", "To‘g‘ridan-to‘g‘ri", "Без пересадок"),
  "ai.changes": t("{n} change(s)", "{n} ta almashinuv", "Пересадок: {n}"),
  "ai.from": t("from", "dan", "от"),
  "ai.demo": t("Demonstration data", "Namoyish ma’lumotlari", "Демонстрационные данные"),
  "ai.real": t("From T-PORT search", "T-PORT qidiruvidan", "Из поиска T-PORT"),
  "ai.cta": t("Plan with AI", "AI bilan rejalashtirish", "Спланировать с AI"),
  "ai.ask": t("Ask T-AI this", "T-AI dan so‘rash", "Спросить T-AI"),
  "ai.honest": t(
    "T-AI never invents prices, schedules, availability or providers.",
    "T-AI narx, jadval, mavjudlik yoki tashuvchilarni o‘ylab topmaydi.",
    "T-AI не выдумывает цены, расписания, наличие мест и перевозчиков.",
  ),
  "ai.you": t("You", "Siz", "Вы"),

  // how it works
  "how.eyebrow": t("How it works", "Qanday ishlaydi", "Как это работает"),
  "how.title": t("Four steps from idea to journey.", "G‘oyadan sayohatgacha to‘rt qadam.", "Четыре шага от идеи до поездки."),
  "how.s1": t("Search", "Qidiring", "Найдите"),
  "how.s1d": t(
    "Enter your origin, destination, and travel date.",
    "Jo‘nash joyi, manzil va sayohat sanasini kiriting.",
    "Укажите пункт отправления, назначения и дату поездки.",
  ),
  "how.s2": t("Compare", "Solishtiring", "Сравните"),
  "how.s2d": t(
    "Discover transport options based on price, duration, and transfers.",
    "Transport variantlarini narx, davomiylik va almashinuvlar bo‘yicha ko‘ring.",
    "Сравните варианты по цене, времени в пути и пересадкам.",
  ),
  "how.s3": t("Plan", "Rejalashtiring", "Спланируйте"),
  "how.s3d": t(
    "Use the AI assistant to find a journey matching your preferences.",
    "Afzalliklaringizga mos yo‘nalishni topish uchun AI yordamchidan foydalaning.",
    "Используйте AI-помощника, чтобы найти маршрут по вашим предпочтениям.",
  ),
  "how.s4": t("Continue to Provider", "Tashuvchiga o‘ting", "Перейдите к перевозчику"),
  "how.s4d": t(
    "Visit the authorized transport provider to complete your booking.",
    "Bronni yakunlash uchun rasmiy transport tashuvchisi saytiga o‘ting.",
    "Завершите бронирование на сайте официального перевозчика.",
  ),
  "how.note": t(
    "T-PORT is a discovery and planning platform. Tickets and payments are completed with the transport provider, where booking is available.",
    "T-PORT — yo‘nalishlarni topish va rejalashtirish platformasi. Chipta va to‘lov bron mavjud bo‘lgan hollarda transport tashuvchisi orqali amalga oshiriladi.",
    "T-PORT — платформа для поиска и планирования поездок. Билеты и оплата оформляются у перевозчика, если доступно бронирование.",
  ),

  // why
  "why.eyebrow": t("Why T-PORT", "Nega T-PORT", "Почему T-PORT"),
  "why.title": t("Everything you need to choose well.", "To‘g‘ri tanlov uchun kerakli hamma narsa.", "Всё, чтобы выбрать правильно."),
  "why.sub": t(
    "One place to discover, compare and plan every way to travel, with every source shown.",
    "Sayohatning barcha yo‘llarini topish, solishtirish va rejalashtirish uchun bitta joy — har bir manba ko‘rsatiladi.",
    "Одно место, чтобы находить, сравнивать и планировать любые поездки, — с указанием каждого источника.",
  ),
  "why.f1": t("Unified Transportation", "Yagona transport", "Единый транспорт"),
  "why.f1d": t(
    "Multiple transport modes within one experience.",
    "Bir nechta transport turi bitta joyda.",
    "Несколько видов транспорта в одном сервисе.",
  ),
  "why.f2": t("Intelligent Planning", "Aqlli rejalashtirish", "Умное планирование"),
  "why.f2d": t(
    "AI-assisted journey discovery and recommendations.",
    "AI yordamida yo‘nalish topish va tavsiyalar.",
    "Поиск маршрутов и рекомендации с помощью AI.",
  ),
  "why.f3": t("Transparent Comparison", "Shaffof solishtirish", "Прозрачное сравнение"),
  "why.f3d": t(
    "Understand prices, durations, and connections.",
    "Narx, davomiylik va ulanishlarni aniq ko‘ring.",
    "Понятные цены, время в пути и пересадки.",
  ),
  "why.f4": t("Source Transparency", "Manbalar ochiqligi", "Открытые источники"),
  "why.f4d": t(
    "See where journey information comes from.",
    "Ma’lumot qayerdan olinganini ko‘ring.",
    "Видно, откуда взята информация о поездке.",
  ),
  "why.f5": t("Personal Travel Hub", "Shaxsiy sayohat markazi", "Личный центр поездок"),
  "why.f5d": t(
    "Save journeys and revisit your plans.",
    "Yo‘nalishlarni saqlang va rejalaringizga qayting.",
    "Сохраняйте маршруты и возвращайтесь к планам.",
  ),
  "why.f6": t("Responsive Experience", "Har qanday qurilmada", "На любом устройстве"),
  "why.f6d": t(
    "An interface designed for computers, tablets, and smartphones.",
    "Kompyuter, planshet va smartfonlar uchun yaratilgan interfeys.",
    "Интерфейс для компьютеров, планшетов и смартфонов.",
  ),

  // vision / about
  "vision.eyebrow": t("About T-PORT", "T-PORT haqida", "О T-PORT"),
  "vision.title": t("From Uzbekistan to the World.", "O‘zbekistondan dunyoga.", "Из Узбекистана — в мир."),
  "vision.p1": t(
    "Our vision is to create a connected transportation experience that brings people, destinations, and intelligent technology together.",
    "Maqsadimiz — odamlar, manzillar va aqlli texnologiyalarni birlashtiruvchi yagona transport tajribasini yaratish.",
    "Наша цель — единый транспортный опыт, который объединяет людей, направления и интеллектуальные технологии.",
  ),
  "vision.p2": t(
    "Starting in Uzbekistan, T-PORT aims to expand across Central Asia and eventually connect international destinations.",
    "O‘zbekistondan boshlab, T-PORT Markaziy Osiyo bo‘ylab kengayishni va kelajakda xalqaro yo‘nalishlarni bog‘lashni maqsad qilgan.",
    "Начав с Узбекистана, T-PORT планирует расшириться на Центральную Азию, а затем связать международные направления.",
  ),
  "vision.by": t("T-PORT is a project by UzLeeder.", "T-PORT — UzLeeder loyihasi.", "T-PORT — проект UzLeeder."),
  "vision.r1": t("Uzbekistan", "O‘zbekiston", "Узбекистан"),
  "vision.r1d": t("Initial market", "Dastlabki bozor", "Стартовый рынок"),
  "vision.r1s": t("Pilot now", "Hozir: pilot", "Сейчас: пилот"),
  "vision.r2": t("Central Asia", "Markaziy Osiyo", "Центральная Азия"),
  "vision.r2d": t("Future expansion", "Kelgusi kengayish", "Будущее расширение"),
  "vision.r2s": t("Planned", "Rejada", "В планах"),
  "vision.r3": t("Global Network", "Global tarmoq", "Глобальная сеть"),
  "vision.r3d": t("Long-term vision", "Uzoq muddatli maqsad", "Долгосрочное видение"),
  "vision.r3s": t("Vision", "Maqsad", "Видение"),
  "vision.note": t(
    "Central Asian and international routes are plans, not live services.",
    "Markaziy Osiyo va xalqaro yo‘nalishlar hozircha reja, ishlayotgan xizmat emas.",
    "Центральная Азия и международные маршруты — это планы, а не действующие сервисы.",
  ),

  // final CTA
  "cta.title": t("Your Next Journey Starts Here.", "Keyingi sayohatingiz shu yerdan boshlanadi.", "Ваше следующее путешествие начинается здесь."),
  "cta.sub": t(
    "Explore more possibilities. Make smarter travel decisions.",
    "Ko‘proq imkoniyatlarni kashf eting. Aqlliroq qarorlar qabul qiling.",
    "Открывайте больше возможностей. Принимайте более взвешенные решения.",
  ),
  "cta.primary": t("Get started", "Boshlash", "Начать"),
  "cta.secondary": t("Explore destinations", "Manzillarni ko‘rish", "Смотреть направления"),

  // footer
  "footer.product": t("Product", "Mahsulot", "Продукт"),
  "footer.search": t("Search journeys", "Yo‘nalish qidirish", "Поиск маршрутов"),
  "footer.explore": t("Explore Uzbekistan", "O‘zbekistonni kashf etish", "Узбекистан"),
  "footer.ai": t("T-AI planner", "T-AI rejalashtiruvchi", "Планировщик T-AI"),
  "footer.compare": t("Compare journeys", "Solishtirish", "Сравнение"),
  "footer.trips": t("My trips", "Mening sayohatlarim", "Мои поездки"),
  "footer.modes": t("Transport", "Transport", "Транспорт"),
  "footer.company": t("T-PORT", "T-PORT", "T-PORT"),
  "footer.about": t("About T-PORT", "T-PORT haqida", "О T-PORT"),
  "footer.help": t("Help: how it works", "Yordam: qanday ishlaydi", "Помощь: как это работает"),
  "footer.privacy": t("Privacy", "Maxfiylik", "Конфиденциальность"),
  "footer.credits": t("Photo credits", "Foto mualliflari", "Авторы фото"),
  "footer.pilot": t(
    "Pilot · Planning information only — no ticket sales.",
    "Pilot · Faqat rejalashtirish uchun ma’lumot — chipta sotilmaydi.",
    "Пилот · Только информация для планирования — без продажи билетов.",
  ),
  "footer.rights": t("© T-PORT. All rights reserved.", "© T-PORT. Barcha huquqlar himoyalangan.", "© T-PORT. Все права защищены."),
  "footer.by": t("A project by UzLeeder.", "UzLeeder loyihasi.", "Проект UzLeeder."),
} satisfies Record<string, Tr>;

export type Key = keyof typeof I18N;

/** Fill "{name}" placeholders. */
export function fill(text: string, vars?: Record<string, string | number>): string {
  return vars ? text.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? `{${k}}`)) : text;
}

export function isLang(v: unknown): v is Lang {
  return typeof v === "string" && (LANGS as readonly string[]).includes(v);
}

/** Region tiles on the landing page: verified places from the place-card pack, in three languages. */
export const REGION_TEXT: Record<string, { name: Tr; desc: Tr }> = {
  "tashkent-city": {
    name: t("Tashkent", "Toshkent shahri", "Ташкент"),
    desc: t("Hazrati Imam complex and Humo Arena", "Hazrati Imom majmuasi va Humo Arena", "Комплекс Хазрати Имам и «Хумо Арена»"),
  },
  "tashkent-region": {
    name: t("Tashkent Region", "Toshkent viloyati", "Ташкентская область"),
    desc: t("Charvak Dam and the Amirsoy mountain resort", "Chorvoq to‘g‘oni va Amirsoy tog‘ kurorti", "Чарвакская плотина и горный курорт Амирсой"),
  },
  samarkand: {
    name: t("Samarkand", "Samarqand", "Самарканд"),
    desc: t("Registan Square and Shah-i-Zinda", "Registon maydoni va Shohi Zinda", "Площадь Регистан и Шахи-Зинда"),
  },
  bukhara: {
    name: t("Bukhara", "Buxoro", "Бухара"),
    desc: t("Poi Kalon ensemble and Lyabi-Hauz", "Poi Kalon majmuasi va Labi Hovuz", "Ансамбль Пои-Калян и Ляби-Хауз"),
  },
  khorezm: {
    name: t("Khorezm", "Xorazm", "Хорезм"),
    desc: t("Itchan Kala and Kalta Minor in Khiva", "Xivadagi Ichan qal’a va Kalta Minor", "Ичан-Кала и Кальта-Минор в Хиве"),
  },
  fergana: {
    name: t("Fergana", "Farg‘ona", "Фергана"),
    desc: t("Khudayor Khan Palace and Rishtan ceramics", "Xudoyorxon saroyi va Rishton kulolchiligi", "Дворец Худояр-хана и риштанская керамика"),
  },
  andijan: {
    name: t("Andijan", "Andijon", "Андижан"),
    desc: t("Jami complex and Babur Memorial Park", "Jome majmuasi va Bobur memorial bog‘i", "Комплекс Джами и мемориальный парк Бабура"),
  },
  namangan: {
    name: t("Namangan", "Namangan", "Наманган"),
    desc: t("Mulla Kyrgyz Madrasa and the Chartak valley", "Mulla Qirg‘iz madrasasi va Chortoq", "Медресе Мулла-Кыргыз и долина Чартак"),
  },
  kashkadarya: {
    name: t("Kashkadarya", "Qashqadaryo", "Кашкадарья"),
    desc: t(
      "Ak-Saray ruins and Dorut Tilovat in Shahrisabz",
      "Shahrisabzdagi Oqsaroy qoldiqlari va Dorut Tilovat",
      "Руины Ак-Сарая и Дорут-Тиловат в Шахрисабзе",
    ),
  },
  surkhandarya: {
    name: t("Surkhandarya", "Surxondaryo", "Сурхандарья"),
    desc: t("Sultan Saodat complex and Boysun", "Sulton Saodat majmuasi va Boysun", "Комплекс Султан-Саадат и Байсун"),
  },
  jizzakh: {
    name: t("Jizzakh", "Jizzax", "Джизак"),
    desc: t("Zaamin National Park and Jizzakh station", "Zomin milliy tabiat bog‘i va Jizzax vokzali", "Зааминский нацпарк и вокзал Джизака"),
  },
  syrdarya: {
    name: t("Syrdarya", "Sirdaryo", "Сырдарья"),
    desc: t("The Syr Darya riverbank and Yogochli Sardoba", "Sirdaryo bo‘yi va Yog‘ochli sardoba", "Берега Сырдарьи и сардоба Ёгочли"),
  },
  navoi: {
    name: t("Navoi", "Navoiy", "Навои"),
    desc: t("Rabati Malik and the Nurata Chashma spring", "Raboti Malik va Nurota Chashmasi", "Рабати-Малик и источник Чашма в Нурате"),
  },
  karakalpakstan: {
    name: t("Karakalpakstan", "Qoraqalpog‘iston", "Каракалпакстан"),
    desc: t(
      "Savitsky Museum and the Moynaq ship graveyard",
      "Savitskiy muzeyi va Mo‘ynoq kemalar qabristoni",
      "Музей Савицкого и кладбище кораблей в Муйнаке",
    ),
  },
};
