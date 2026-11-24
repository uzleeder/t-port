import type { Metadata } from "next";
import { Icon } from "@/components/Icons";
import { PageBanner } from "@/components/PageBanner";
import { T } from "@/components/T";
import type { Tr } from "@/lib/i18n";

export const metadata: Metadata = { title: "Privacy" };

/*
 * What the pilot actually stores, as implemented (backend: accounts, sessions, saved journeys,
 * preferences, avatars, metadata-only AI and booking counters). A summary, not a legal policy.
 */
const POINTS: Tr[] = [
  {
    en: "Searching, exploring and asking T-AI work without an account.",
    uz: "Qidirish, joylarni ko‘rish va T-AI dan so‘rash uchun hisob kerak emas.",
    ru: "Поиск, просмотр мест и вопросы T-AI доступны без аккаунта.",
  },
  {
    en: "With an account, T-PORT keeps your email, the name and photo you choose, your saved journeys and your search preferences. Your name, email and photo are shown only to you.",
    uz: "Hisob ochsangiz, T-PORT elektron pochtangiz, siz tanlagan ism va rasm, saqlangan yo‘nalishlar va qidiruv sozlamalarini saqlaydi. Ism, pochta va rasm faqat sizga ko‘rinadi.",
    ru: "С аккаунтом T-PORT хранит ваш email, выбранные имя и фото, сохранённые маршруты и настройки поиска. Имя, email и фото видны только вам.",
  },
  {
    en: "Passwords are stored only as a salted hash, never as text.",
    uz: "Parollar faqat tuzlangan xesh ko‘rinishida saqlanadi, matn sifatida emas.",
    ru: "Пароли хранятся только в виде хеша с солью, а не текстом.",
  },
  {
    en: "What you type to T-AI is not stored; only counts and timings are kept to run the service.",
    uz: "T-AI ga yozganlaringiz saqlanmaydi; xizmat uchun faqat soni va vaqti qayd etiladi.",
    ru: "Текст запросов к T-AI не хранится; сохраняются только количество и время для работы сервиса.",
  },
  {
    en: "When you continue to a transport provider, T-PORT counts the hand-off per provider and day, never linked to you.",
    uz: "Tashuvchi saytiga o‘tganingizda T-PORT buni faqat tashuvchi va kun bo‘yicha sanaydi, siz bilan bog‘lamaydi.",
    ru: "При переходе к перевозчику T-PORT лишь считает переходы по перевозчику и дню, не связывая их с вами.",
  },
  {
    en: "You can delete your account at any time in Profile & Settings; this removes your photo, saved journeys and preferences.",
    uz: "Hisobingizni istalgan vaqtda «Profil va sozlamalar»da o‘chirishingiz mumkin; bunda rasm, saqlangan yo‘nalishlar va sozlamalar o‘chiriladi.",
    ru: "Удалить аккаунт можно в любой момент в «Профиле и настройках»; при этом удаляются фото, маршруты и настройки.",
  },
  {
    en: "Your theme, language and recent searches on this device stay in your browser.",
    uz: "Mavzu, til va so‘nggi qidiruvlar shu qurilmadagi brauzeringizda qoladi.",
    ru: "Тема, язык и недавние поиски хранятся в вашем браузере на этом устройстве.",
  },
];

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-5 px-3 py-4 sm:px-6 lg:px-0 lg:py-0">
      <PageBanner icon="shield" title="Privacy" subtitle="What T-PORT keeps about you during the pilot." />
      <ul className="space-y-3 rounded-3xl bg-surface p-5 shadow-soft sm:p-6">
        {POINTS.map((p) => (
          <li key={p.en} className="flex items-start gap-3 text-sm leading-relaxed">
            <Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-success" />
            <span>
              <T tr={p} />
            </span>
          </li>
        ))}
      </ul>
      <p className="px-1 text-xs text-muted">
        <T
          tr={{
            en: "This is a plain summary of how the pilot works, not a formal privacy policy.",
            uz: "Bu pilot qanday ishlashining qisqacha bayoni, rasmiy maxfiylik siyosati emas.",
            ru: "Это краткое описание работы пилота, а не официальная политика конфиденциальности.",
          }}
        />
      </p>
    </div>
  );
}
