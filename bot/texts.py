"""All user-facing strings in ru / en / uk, plus the `t()` lookup helper.

Code/identifiers stay in English; only the values here are shown to users.
Every handler resolves a per-user `lang` (see `resolve_lang`) and passes it to
`t(key, lang)`. Action button labels live here too — never hardcode them.
"""

from __future__ import annotations

SUPPORTED_LANGS = ("ru", "en", "uk")
DEFAULT_LANG = "en"  # English is the default for any non-ru/uk language_code


def resolve_lang(language_code: str | None) -> str:
    """Map a Telegram language_code to one of our supported UI languages.

    ru -> ru, uk -> uk, everything else -> English (the default). Only the
    language prefix matters (e.g. "en-US" -> "en", "de" -> "en").
    """
    code = (language_code or "").lower()
    if code.startswith("ru"):
        return "ru"
    if code.startswith("uk"):
        return "uk"
    return DEFAULT_LANG


def t(key: str, lang: str) -> str:
    """Look up a UI string. Falls back to English, then to the raw key."""
    return TEXTS.get(lang, TEXTS["en"]).get(key, TEXTS["en"].get(key, key))


# Technical, language-independent labels for the "kind" part of an item, e.g.
# "[1] Иван (voice → transcript): …". Kept in English on purpose.
KIND_TEXT = "text"
KIND_VOICE = "voice → transcript"
KIND_VIDEO_NOTE = "video_note → transcript"
KIND_VIDEO = "video → transcript"
KIND_AUDIO = "audio → transcript"
KIND_PHOTO = "photo → ocr"
KIND_DOCUMENT = "document → text"

RESULT_FILENAME = "result.md"


TEXTS: dict[str, dict[str, str]] = {
    # ================================================================= RU ===
    "ru": {
        "welcome": (
            "👋 Привет! Я превращаю пересланные сообщения в готовый результат.\n\n"
            "1️⃣ Перешлите или отправьте подряд несколько сообщений — текст, голосовые, "
            "кружочки, видео, аудио, документы, фото. Медиа расшифрую, текст с фото распознаю.\n"
            "2️⃣ Выберите действие на клавиатуре — или просто напишите свой запрос текстом.\n"
            "3️⃣ Перед запуском можно добавить контекст: текст, файл или ссылку.\n\n"
            "Ответ приходит на языке исходных сообщений.\n"
            "/help — подробнее · /plans — тарифы"
        ),
        "reset_done": "🧹 Пачка очищена. Присылайте новые сообщения.",
        "help": (
            "ℹ️ Как это работает\n"
            "Перешлите несколько сообщений (текст, голосовые, кружочки, видео, аудио, "
            "документы, фото). Я расшифрую медиа, распознаю текст с фото и соберу всё в "
            "один документ с именами отправителей.\n"
            "Дальше выберите действие на клавиатуре или просто напишите свой запрос. "
            "К любому действию можно добавить контекст (текст, файл или ссылку) или нажать "
            "«▶️ Запустить» без него.\n"
            "Файлы — до 20 МБ, длинное аудио делю автоматически, длинный ответ разбиваю "
            "на несколько сообщений. Ответ — на языке исходных сообщений.\n"
            "Как работают пачки: пересланные или отправленные сообщения собираются в одну "
            "пачку; выберите действие или напишите запрос — он применится к ней. Пересылка "
            "новых сообщений после ответа начинает новую пачку (старая очищается); "
            "/reset очищает её вручную.\n\n"
            "Команды\n"
            "• Основные: /start, /reset, /help, /lang\n"
            "• Тариф и лимиты: /plans, /pro, /usage\n"
            "• Свой ключ и модели: /setkey, /removekey, /models\n"
            "• Запросы: /prompts (сохранённые)\n"
            "• Друзья и данные: /invite, /privacy, /forgetme\n"
            "• В группах: /summary, /ask, /actions, /clear"
        ),
        "lang_choose": "Выбери язык интерфейса:",
        "lang_set": "✅ Язык интерфейса — русский.",
        "finalizing": "🛠 Обрабатываю пачку (расшифровка, распознавание)…",
        "empty_batch": "Пачка пустая — нечего обрабатывать.",
        "batch_ready": "✅ Пачка готова. Выберите действие — или просто напишите свой запрос.",
        "new_batch_started": "🔄 Начал новую пачку — предыдущая очищена.",
        "batch_limit_reached": (
            "⚠️ Достигнут лимит в {limit} сообщений на пачку. "
            "Лишние сообщения проигнорированы."
        ),
        "context_truncated": (
            "ℹ️ Контекст был слишком большим — самые старые сообщения обрезаны "
            "перед отправкой в модель."
        ),
        "label_you": "Ты",
        "skipped_too_large": (
            "⚠️ Элемент [{index}] ({kind}) пропущен: файл больше 20 МБ, "
            "Telegram не отдаёт такие боту."
        ),
        "skipped_no_audio": "⚠️ Элемент [{index}] (видео) без звука — расшифровка пропущена.",
        "skipped_error": "⚠️ Элемент [{index}] ({kind}) не удалось обработать: {error}",
        "unsupported_document": "⚠️ Элемент [{index}]: формат документа не поддерживается.",
        "no_active_batch": "Сейчас нет активной пачки. Пришлите сообщения, и я соберу новую.",
        "thinking": "🤔 Думаю…",
        "action_context_hint": (
            "Добавьте контекст (текст, файл или ссылку) и отправьте — "
            "или нажмите ▶️ Запустить."
        ),
        "btn_run": "▶️ Запустить",
        "custom_prompt_ask": (
            "✍️ Напишите свою инструкцию (например: «составь ответ» или «сделай "
            "из этого промпт для другой нейросети»)."
        ),
        "context_added_file": "📎 Контекст из файла «{name}» добавлен.",
        "context_added_link": "🔗 Контекст по ссылке добавлен.",
        "context_file_failed": "⚠️ Не удалось прочитать файл «{name}»: {error}",
        "context_link_failed": "⚠️ Не удалось загрузить ссылку {url}: {error}",
        "followup_hint": "Можно выбрать ещё одно действие для этой же пачки 👇",
        "result_file_caption": "📄 Готово — ответ в файле.",
        "not_allowed": "⛔ Извините, у вас нет доступа к этому боту.",
        "llm_error": "😕 Не получилось получить ответ от модели. Попробуйте позже.",
        "generic_error": "😕 Что-то пошло не так. Попробуйте ещё раз.",
        "rate_limit_batches": (
            "🚦 Лимит пачек исчерпан ({limit} в час). Попробуйте через ~{minutes} мин."
        ),
        "building_presentation": "📊 Собираю презентацию…",
        "deck_polishing": "✨ Полирую презентацию…",
        "building_pdf": "📄 Собираю PDF…",
        "building_image": "🎨 Генерирую изображение…",
        "presentation_caption": "📊 Презентация готова.",
        "pdf_caption": "📄 Документ готов.",
        "presentation_failed": "😕 Не удалось собрать презентацию.",
        "pdf_failed": "😕 Не удалось собрать PDF.",
        "image_failed": "😕 Не удалось сгенерировать изображение.",
        # Action button labels (kept short so they don't truncate on phones)
        "action_summary": "📝 Кратко",
        "action_structure": "📋 Структура",
        "action_reply": "💬 Ответ",
        "action_email": "✉️ Письмо",
        "action_items": "✅ Задачи",
        "action_translate": "🌐 Перевод EN",
        "action_presentation": "📊 Презентация",
        "action_pdf": "📄 PDF",
        "action_image": "🎨 Картинка",
        "action_custom": "✍️ Или просто напишите запрос ⬇️",
        # --- Monetization / account ---
        "paywall_generic": "Эта функция недоступна на текущем тарифе.",
        "btn_pay_stars": "⭐ Оплатить Stars",
        "payment_success": "🎉 Pro активирован! Спасибо за поддержку.",
        "payment_held": "⏳ Платёж получен, но требует проверки. Мы скоро всё подтвердим.",
        "invite_text": (
            "👥 Ваша реферальная ссылка:\n{link}\n\nЗа каждого нового пользователя "
            "вы оба получаете +{credits} кредитов."
        ),
        "key_saved": "🔑 Ключ сохранён. Запросы идут через ваш ключ OpenRouter — кредиты не списываются.",
        "key_removed": "🔑 Ключ удалён. Вы снова на кредитной системе.",
        "key_invalid": "⚠️ Не получилось проверить ключ. Использование: /setkey <ваш ключ OpenRouter>",
        "prompt_saved": "💾 Промпт сохранён. Смотрите /prompts.",
        "prompts_empty": "У вас пока нет сохранённых промптов. Запустите свой запрос и нажмите «Сохранить».",
        "prompts_pick": "Ваши сохранённые промпты:",
        "prompts_limit": "На бесплатном тарифе можно хранить до {limit} промптов. Pro — без ограничений: /pro",
        "btn_save_prompt": "💾 Сохранить промпт",
        "privacy_text": (
            "🔒 Приватность\n\nПересланный контент обрабатывается временно — только чтобы "
            "выполнить ваше действие. Производный текст (расшифровки/распознавание) кэшируется "
            "по непрозрачному файловому id Telegram, чтобы не платить дважды, и не содержит "
            "идентификаторов аккаунта. Мы ничего не продаём. Удалить свои данные: /forgetme"
        ),
        "forgetme_confirm": "Удалить все ваши данные (тариф, лимиты, промпты, платежи)? Это необратимо.",
        "forgetme_done": "🗑 Готово. Все ваши данные удалены.",
        # --- Plans / upgrade ---
        "btn_upgrade": "⭐ Перейти на Pro",
        "plans_header": "💎 Тарифы и цены",
        "plans_free_block": (
            "🆓 Free\n"
            "• {signup} кредитов для старта (разовый бонус)\n"
            "• {daily} бесплатных кредитов каждый день (не накапливаются)\n"
            "• Оплата по факту: текст ~0.1–0.2 кредита/действие · аудио 1 кредит/минута · "
            "фото 0.5 кредита/фото"
        ),
        "plans_pro_block": (
            "⭐ Pro — {stars} ⭐ / мес\n"
            "• {pro_credits} кредитов каждый месяц — в 2× больше, чем вы платите ⭐\n"
            "• −{discount}% на пакеты кредитов\n"
            "• Премиум-модель, больший контекст, в группах /ask и /actions, безлимит промптов"
        ),
        "plans_byo_line": (
            "🔑 Свой ключ — без подписки и кредитов: через /setkey вы платите напрямую "
            "за свой API OpenRouter."
        ),
        "plans_pro_active": "✅ У вас Pro — действует до {date}.",
        "usage_pro_active": "✅ У вас Pro — действует до {date}.",
        "usage_byo_active": "🔑 Свой ключ активен — кредиты не списываются.",
        # --- Credits ---
        "balance_line": "💳 Кредиты: {persistent} (+{daily} бесплатных сегодня)",
        "daily_floor_note": "🎁 Каждый день вам также начисляется {daily} бесплатных кредитов.",
        "usage_invite": "👥 Зовите друзей — кредиты получаете оба:\n{invite}",
        "credits_low": (
            "💳 Кредиты закончились. Купите пакет или оформите Pro — это ежемесячные "
            "кредиты и −30% на пакеты."
        ),
        "item_skipped_no_credits": "пропущено: нет кредитов",
        "feature_unavailable": "Эта функция сейчас недоступна.",
        "btn_buy_credits": "💳 Купить кредиты",
        "buy_credits_header": "Выберите пакет кредитов (1 ⭐ = 1 кредит):",
        "pack_label": "{credits} кредитов — {stars} ⭐",
        "pack_invoice_title": "{credits} кредитов",
        "pack_invoice_desc": "Пополнение на {credits} кредитов Forwardly.",
        "credits_added": "🎉 Начислено {credits} кредитов. Пользуйтесь!",
        "pro_value_math": (
            "⭐ Forwardly Pro — {stars} ⭐ / мес\n\n"
            "Покупка кредитов: 1 ⭐ = 1 кредит (то есть {stars} ⭐ → {stars} кредитов).\n"
            "Pro: {stars} ⭐ → {pro_credits} кредитов — в 2× выгоднее — плюс −{discount}% на "
            "пакеты кредитов, премиум-модель, больший контекст, вопросы в группах и "
            "безлимит сохранённых промптов."
        ),
        # --- Group mode ---
        "group_intro": (
            "👋 Привет! Я умею делать сводку группового чата.\n\n"
            "• /summary [N] — кратко о последних N сообщениях\n"
            "• /ask <вопрос> и /actions — функции Pro\n"
            "• /clear — админы очищают мой буфер\n\n"
            "🔒 Я храню только короткий буфер последних сообщений в памяти "
            "(ограниченный, с авто-истечением) — ничего про эту группу не сохраняется. "
            "Я вижу только сообщения, отправленные *после* того, как я вошёл "
            "(режим приватности должен быть выключен)."
        ),
        "group_summary_empty": (
            "Пока нечего обобщать — я вижу только сообщения после моего входа. "
            "Убедитесь, что режим приватности выключен (BotFather → /setprivacy → "
            "Disable), и добавьте меня заново."
        ),
        "group_cooldown": "⏳ Чуть помедленнее — я только что делал сводку. Попробуйте через несколько секунд.",
        "group_admins_only": "Очистить буфер могут только администраторы группы.",
        "group_cleared": "🧹 Буфер очищен.",
        "group_ask_usage": "Использование: /ask <ваш вопрос по недавнему треду>",
        # --- Per-task model selection (BYO) ---
        "models_byo_only": (
            "🔧 Выбор модели для каждой задачи — функция для тех, кто использует свой "
            "ключ. Добавьте ключ OpenRouter через /setkey, затем /models позволит "
            "выбрать модель для каждой задачи."
        ),
        "models_header": (
            "🔧 Ваши модели (по задачам). Нажмите «Изменить», чтобы выбрать из списка "
            "или ввести свой slug."
        ),
        "models_slot_text": "Текст",
        "models_slot_vision": "Зрение",
        "models_slot_transcribe": "Расшифровка",
        "models_slot_image": "Изображение",
        "btn_change": "Изменить",
        "btn_custom_slug": "✏️ Ввести свой slug",
        "btn_reset_slot": "↺ Сбросить к умолчанию",
        "btn_reset_all": "↺ Сбросить всё к умолчаниям",
        "models_pick_prompt": "Выберите модель для: {slot}",
        "models_ask_slug": "Пришлите slug модели (например, openai/gpt-4o-mini):",
        "models_set": "✅ Модель установлена: {slug}.",
        "models_invalid": "⚠️ Не нашёл такую модель в каталоге OpenRouter. Проверьте slug и попробуйте снова.",
        "models_modality_warn": "⚠️ Внимание: модель может не поддерживать вход/выход для этой задачи — всё равно сохранено.",
        "models_reset_done": "↺ Возвращена модель по умолчанию для этой задачи.",
        "models_reset_all_done": "↺ Все слоты сброшены к умолчаниям.",
        # --- Moved out of handlers / contextual hints ---
        "invoice_title": "Forwardly Pro",
        "invoice_description": "Forwardly Pro на 30 дней: ежемесячные кредиты, скидка на пакеты, премиум-модель, больший контекст.",
        "presentation_context_hint": (
            "📊 Можно приложить свой шаблон .pptx/.potx и/или добавить текст, файл или "
            "ссылку, затем отправьте — или нажмите ▶️ Запустить."
        ),
        "save_prompt_offer": "💾 Сохранить этот запрос, чтобы запускать его повторно?",
        "btn_confirm_delete": "✅ Да, удалить",
        "btn_cancel": "✖️ Отмена",
        "forgetme_cancelled": "Отменено — данные не тронуты.",
        "models_default": "по умолчанию",
    },
    # ================================================================= EN ===
    "en": {
        "welcome": (
            "👋 Hi! I turn forwarded messages into a finished result.\n\n"
            "1️⃣ Forward or send several messages in a row — text, voice, video notes, "
            "videos, audio, documents, photos. I transcribe media and read text from photos.\n"
            "2️⃣ Pick an action on the keyboard — or just type your prompt.\n"
            "3️⃣ Before running, you can add context: text, a file, or a link.\n\n"
            "The answer comes back in the language of your messages.\n"
            "/help — details · /plans — pricing"
        ),
        "reset_done": "🧹 Batch cleared. Send new messages.",
        "help": (
            "ℹ️ How it works\n"
            "Forward several messages (text, voice, video notes, videos, audio, "
            "documents, photos). I transcribe media, read text from photos, and assemble "
            "one document labeled with sender names.\n"
            "Then pick an action on the keyboard or just type your prompt. You can add "
            "context (text, a file, or a link) to any action, or tap “▶️ Run” without it.\n"
            "Files up to 20 MB, long audio is split automatically, long answers are split "
            "into several messages. The answer is in the language of your messages.\n"
            "How batches work: forwarded or sent messages collect into one batch; pick an "
            "action or type a prompt to run it on that batch. Forwarding new messages after "
            "an answer starts a fresh batch (the old one is cleared); /reset clears it.\n\n"
            "Commands\n"
            "• Everyday: /start, /reset, /help, /lang\n"
            "• Plan & limits: /plans, /pro, /usage\n"
            "• Your key & models: /setkey, /removekey, /models\n"
            "• Prompts: /prompts (saved)\n"
            "• Friends & data: /invite, /privacy, /forgetme\n"
            "• In groups: /summary, /ask, /actions, /clear"
        ),
        "lang_choose": "Choose interface language:",
        "lang_set": "✅ Language set to English.",
        "finalizing": "🛠 Processing the batch (transcription, OCR)…",
        "empty_batch": "The batch is empty — nothing to process.",
        "batch_ready": "✅ Batch ready. Pick an action — or just type your prompt.",
        "new_batch_started": "🔄 Started a new batch — the previous one was cleared.",
        "batch_limit_reached": (
            "⚠️ Reached the limit of {limit} messages per batch. Extra messages ignored."
        ),
        "context_truncated": (
            "ℹ️ The context was too large — the oldest messages were truncated "
            "before sending to the model."
        ),
        "label_you": "You",
        "skipped_too_large": (
            "⚠️ Item [{index}] ({kind}) skipped: file larger than 20 MB, "
            "Telegram won't hand it to the bot."
        ),
        "skipped_no_audio": "⚠️ Item [{index}] (video) has no audio — transcription skipped.",
        "skipped_error": "⚠️ Item [{index}] ({kind}) could not be processed: {error}",
        "unsupported_document": "⚠️ Item [{index}]: unsupported document format.",
        "no_active_batch": "There's no active batch. Send some messages and I'll build one.",
        "thinking": "🤔 Thinking…",
        "action_context_hint": (
            "Add context (text, file, or link), then send — or tap ▶️ Run."
        ),
        "btn_run": "▶️ Run",
        "custom_prompt_ask": (
            "✍️ Type your instruction (e.g. “draft a reply” or “turn this into a "
            "prompt for another LLM”)."
        ),
        "context_added_file": "📎 Context from file “{name}” added.",
        "context_added_link": "🔗 Context from the link added.",
        "context_file_failed": "⚠️ Couldn't read file “{name}”: {error}",
        "context_link_failed": "⚠️ Couldn't fetch link {url}: {error}",
        "followup_hint": "You can run another action on the same batch 👇",
        "result_file_caption": "📄 Done — your answer is in the file.",
        "not_allowed": "⛔ Sorry, you don't have access to this bot.",
        "llm_error": "😕 Couldn't get a response from the model. Try again later.",
        "generic_error": "😕 Something went wrong. Please try again.",
        "rate_limit_batches": (
            "🚦 Batch limit reached ({limit}/hour). Try again in ~{minutes} min."
        ),
        "building_presentation": "📊 Building the presentation…",
        "deck_polishing": "✨ Polishing your deck…",
        "building_pdf": "📄 Building the PDF…",
        "building_image": "🎨 Generating the image…",
        "presentation_caption": "📊 Presentation ready.",
        "pdf_caption": "📄 Document ready.",
        "presentation_failed": "😕 Couldn't build the presentation.",
        "pdf_failed": "😕 Couldn't build the PDF.",
        "image_failed": "😕 Couldn't generate the image.",
        "action_summary": "📝 Summary",
        "action_structure": "📋 Structure",
        "action_reply": "💬 Reply",
        "action_email": "✉️ Follow-up",
        "action_items": "✅ Action items",
        "action_translate": "🌐 Translate EN",
        "action_presentation": "📊 Presentation",
        "action_pdf": "📄 PDF",
        "action_image": "🎨 Image",
        "action_custom": "✍️ Or just type your prompt ⬇️",
        # --- Monetization / account ---
        "paywall_generic": "This feature isn't available on your plan.",
        "btn_pay_stars": "⭐ Pay with Stars",
        "payment_success": "🎉 Pro is active! Thanks for the support.",
        "payment_held": "⏳ Payment received but needs a quick review. We'll confirm shortly.",
        "invite_text": (
            "👥 Your referral link:\n{link}\n\nFor every new user, you both get "
            "+{credits} credits."
        ),
        "key_saved": "🔑 Key saved. Your requests now use your own OpenRouter key — no credits charged.",
        "key_removed": "🔑 Key removed. You're back on the credit system.",
        "key_invalid": "⚠️ Couldn't validate the key. Usage: /setkey <your OpenRouter key>",
        "prompt_saved": "💾 Prompt saved. See /prompts.",
        "prompts_empty": "You have no saved prompts yet. Run a custom prompt and tap Save.",
        "prompts_pick": "Your saved prompts:",
        "prompts_limit": "Free plan stores up to {limit} prompts. Pro is unlimited: /pro",
        "btn_save_prompt": "💾 Save prompt",
        "privacy_text": (
            "🔒 Privacy\n\nForwarded content is processed transiently — only to perform the "
            "action you asked for. Derived text (transcripts/OCR) is cached by Telegram's opaque "
            "file id to avoid re-billing and contains no account identifiers. Nothing is sold. "
            "Delete your data: /forgetme"
        ),
        "forgetme_confirm": "Delete all your data (plan, limits, saved prompts, payments)? This can't be undone.",
        "forgetme_done": "🗑 Done. All your data has been deleted.",
        # --- Plans / upgrade ---
        "btn_upgrade": "⭐ Upgrade to Pro",
        "plans_header": "💎 Plans & pricing",
        "plans_free_block": (
            "🆓 Free\n"
            "• {signup} credits to start (one-time bonus)\n"
            "• {daily} free credits every day (use it or lose it — they don't carry over)\n"
            "• Pay by usage: text ~0.1–0.2 credits/action · audio 1 credit/minute · "
            "photo 0.5 credits/photo"
        ),
        "plans_pro_block": (
            "⭐ Pro — {stars} ⭐ / month\n"
            "• {pro_credits} credits every month — 2× the Stars you pay\n"
            "• {discount}% off extra credit packs\n"
            "• Premium model, bigger context, group /ask & /actions, unlimited saved prompts"
        ),
        "plans_byo_line": (
            "🔑 Your own key — no subscription, no credits: use /setkey and pay your own "
            "OpenRouter API directly."
        ),
        "plans_pro_active": "✅ You're on Pro — valid until {date}.",
        "usage_pro_active": "✅ You're on Pro — valid until {date}.",
        "usage_byo_active": "🔑 Own key active — no credits charged.",
        # --- Credits ---
        "balance_line": "💳 Credits: {persistent} (+{daily} free today)",
        "daily_floor_note": "🎁 You also get {daily} free credits every day.",
        "usage_invite": "👥 Invite friends — you both get credits:\n{invite}",
        "credits_low": (
            "💳 You're out of credits. Buy a credit pack, or go Pro for monthly "
            "credits and 30% off packs."
        ),
        "item_skipped_no_credits": "skipped: out of credits",
        "feature_unavailable": "That feature is currently unavailable.",
        "btn_buy_credits": "💳 Buy credits",
        "buy_credits_header": "Choose a credit pack (1 ⭐ = 1 credit):",
        "pack_label": "{credits} credits — {stars} ⭐",
        "pack_invoice_title": "{credits} credits",
        "pack_invoice_desc": "Top up {credits} Forwardly credits.",
        "credits_added": "🎉 Added {credits} credits. Enjoy!",
        "pro_value_math": (
            "⭐ Forwardly Pro — {stars} ⭐ / month\n\n"
            "Buy credits: 1 ⭐ = 1 credit (so {stars} ⭐ → {stars} credits).\n"
            "Pro: {stars} ⭐ → {pro_credits} credits — 2× the value — plus {discount}% off "
            "extra credit packs, a premium model, bigger context, group Q&A, and "
            "unlimited saved prompts."
        ),
        # --- Group mode ---
        "group_intro": (
            "👋 Hi! I can recap your group chat.\n\n"
            "• /summary [N] — summarize the last N messages\n"
            "• /ask <question> and /actions — Pro features\n"
            "• /clear — admins wipe my buffer\n\n"
            "🔒 I keep only a short, in-memory buffer of recent messages (capped, "
            "auto-expiring) — nothing about this group is stored. I can only see "
            "messages sent *after* I joined (privacy mode must be off)."
        ),
        "group_summary_empty": (
            "Nothing buffered yet — I only see messages sent after I joined. Make "
            "sure my privacy mode is disabled (BotFather → /setprivacy → Disable), "
            "then re-add me."
        ),
        "group_cooldown": "⏳ Slow down a moment — I just summarized. Try again in a few seconds.",
        "group_admins_only": "Only group admins can clear my buffer.",
        "group_cleared": "🧹 Buffer cleared.",
        "group_ask_usage": "Usage: /ask <your question about the recent thread>",
        # --- Per-task model selection (BYO) ---
        "models_byo_only": (
            "🔧 Per-task model selection is a power-user feature for bring-your-own-key "
            "users. Add your OpenRouter key with /setkey, then /models lets you pick a "
            "model for each task."
        ),
        "models_header": (
            "🔧 Your models (per task). Tap Change to pick from a live shortlist or "
            "enter a custom slug."
        ),
        "models_slot_text": "Text",
        "models_slot_vision": "Vision",
        "models_slot_transcribe": "Transcription",
        "models_slot_image": "Image",
        "btn_change": "Change",
        "btn_custom_slug": "✏️ Enter custom slug",
        "btn_reset_slot": "↺ Reset to default",
        "btn_reset_all": "↺ Reset all to defaults",
        "models_pick_prompt": "Pick a model for {slot}:",
        "models_ask_slug": "Send the model slug (e.g. openai/gpt-4o-mini):",
        "models_set": "✅ Model set to {slug}.",
        "models_invalid": "⚠️ I couldn't find that model in the OpenRouter catalog. Check the slug and try again.",
        "models_modality_warn": "⚠️ Heads up: that model may not support this task's input/output — set anyway.",
        "models_reset_done": "↺ Reset to the default model for this task.",
        "models_reset_all_done": "↺ All slots reset to defaults.",
        # --- Moved out of handlers / contextual hints ---
        "invoice_title": "Forwardly Pro",
        "invoice_description": "Forwardly Pro for 30 days: monthly credits, discounted credit packs, premium model, bigger context.",
        "presentation_context_hint": (
            "📊 You can attach your own .pptx/.potx template and/or add text, a file, or "
            "a link, then send — or tap ▶️ Run."
        ),
        "save_prompt_offer": "💾 Save this prompt to run it again later?",
        "btn_confirm_delete": "✅ Yes, delete",
        "btn_cancel": "✖️ Cancel",
        "forgetme_cancelled": "Cancelled — your data is untouched.",
        "models_default": "default",
    },
    # ================================================================= UK ===
    "uk": {
        "welcome": (
            "👋 Привіт! Я перетворюю переслані повідомлення на готовий результат.\n\n"
            "1️⃣ Перешліть або надішліть поспіль кілька повідомлень — текст, голосові, "
            "кружечки, відео, аудіо, документи, фото. Медіа розшифрую, текст із фото розпізнаю.\n"
            "2️⃣ Оберіть дію на клавіатурі — або просто напишіть свій запит текстом.\n"
            "3️⃣ Перед запуском можна додати контекст: текст, файл або посилання.\n\n"
            "Відповідь приходить мовою вихідних повідомлень.\n"
            "/help — докладніше · /plans — тарифи"
        ),
        "reset_done": "🧹 Пачку очищено. Надсилайте нові повідомлення.",
        "help": (
            "ℹ️ Як це працює\n"
            "Перешліть кілька повідомлень (текст, голосові, кружечки, відео, аудіо, "
            "документи, фото). Я розшифрую медіа, розпізнаю текст із фото й зберу все в "
            "один документ з іменами відправників.\n"
            "Далі оберіть дію на клавіатурі або просто напишіть свій запит. До будь-якої "
            "дії можна додати контекст (текст, файл або посилання) чи натиснути "
            "«▶️ Запустити» без нього.\n"
            "Файли — до 20 МБ, довге аудіо ділю автоматично, довгу відповідь розбиваю "
            "на кілька повідомлень. Відповідь — мовою вихідних повідомлень.\n"
            "Як працюють пачки: переслані або надіслані повідомлення збираються в одну "
            "пачку; оберіть дію або напишіть запит — він застосується до неї. Пересилання "
            "нових повідомлень після відповіді починає нову пачку (стара очищається); "
            "/reset очищає її вручну.\n\n"
            "Команди\n"
            "• Основні: /start, /reset, /help, /lang\n"
            "• Тариф і ліміти: /plans, /pro, /usage\n"
            "• Свій ключ і моделі: /setkey, /removekey, /models\n"
            "• Запити: /prompts (збережені)\n"
            "• Друзі та дані: /invite, /privacy, /forgetme\n"
            "• У групах: /summary, /ask, /actions, /clear"
        ),
        "lang_choose": "Обери мову інтерфейсу:",
        "lang_set": "✅ Мова інтерфейсу — українська.",
        "finalizing": "🛠 Обробляю пачку (розшифрування, розпізнавання)…",
        "empty_batch": "Пачка порожня — немає що обробляти.",
        "batch_ready": "✅ Пачка готова. Оберіть дію — або просто напишіть свій запит.",
        "new_batch_started": "🔄 Почав нову пачку — попередню очищено.",
        "batch_limit_reached": (
            "⚠️ Досягнуто ліміту в {limit} повідомлень на пачку. "
            "Зайві повідомлення проігноровано."
        ),
        "context_truncated": (
            "ℹ️ Контекст був завеликий — найстаріші повідомлення обрізано перед "
            "надсиланням у модель."
        ),
        "label_you": "Ти",
        "skipped_too_large": (
            "⚠️ Елемент [{index}] ({kind}) пропущено: файл більший за 20 МБ, "
            "Telegram не віддає такі боту."
        ),
        "skipped_no_audio": "⚠️ Елемент [{index}] (відео) без звуку — розшифрування пропущено.",
        "skipped_error": "⚠️ Елемент [{index}] ({kind}) не вдалося обробити: {error}",
        "unsupported_document": "⚠️ Елемент [{index}]: формат документа не підтримується.",
        "no_active_batch": "Зараз немає активної пачки. Надішліть повідомлення, і я зберу нову.",
        "thinking": "🤔 Думаю…",
        "action_context_hint": (
            "Додайте контекст (текст, файл або посилання) і надішліть — "
            "або натисніть ▶️ Запустити."
        ),
        "btn_run": "▶️ Запустити",
        "custom_prompt_ask": (
            "✍️ Напишіть свою інструкцію (наприклад: «склади відповідь» або «зроби "
            "з цього промпт для іншої нейромережі»)."
        ),
        "context_added_file": "📎 Контекст із файлу «{name}» додано.",
        "context_added_link": "🔗 Контекст за посиланням додано.",
        "context_file_failed": "⚠️ Не вдалося прочитати файл «{name}»: {error}",
        "context_link_failed": "⚠️ Не вдалося завантажити посилання {url}: {error}",
        "followup_hint": "Можна обрати ще одну дію для цієї ж пачки 👇",
        "result_file_caption": "📄 Готово — відповідь у файлі.",
        "not_allowed": "⛔ Вибачте, у вас немає доступу до цього бота.",
        "llm_error": "😕 Не вдалося отримати відповідь від моделі. Спробуйте пізніше.",
        "generic_error": "😕 Щось пішло не так. Спробуйте ще раз.",
        "rate_limit_batches": (
            "🚦 Ліміт пачок вичерпано ({limit} на годину). Спробуйте за ~{minutes} хв."
        ),
        "building_presentation": "📊 Збираю презентацію…",
        "deck_polishing": "✨ Полірую презентацію…",
        "building_pdf": "📄 Збираю PDF…",
        "building_image": "🎨 Генерую зображення…",
        "presentation_caption": "📊 Презентація готова.",
        "pdf_caption": "📄 Документ готовий.",
        "presentation_failed": "😕 Не вдалося зібрати презентацію.",
        "pdf_failed": "😕 Не вдалося зібрати PDF.",
        "image_failed": "😕 Не вдалося згенерувати зображення.",
        "action_summary": "📝 Стисло",
        "action_structure": "📋 Структура",
        "action_reply": "💬 Відповідь",
        "action_email": "✉️ Лист",
        "action_items": "✅ Завдання",
        "action_translate": "🌐 Переклад EN",
        "action_presentation": "📊 Презентація",
        "action_pdf": "📄 PDF",
        "action_image": "🎨 Зображення",
        "action_custom": "✍️ Або просто напишіть запит ⬇️",
        # --- Monetization / account ---
        "paywall_generic": "Ця функція недоступна на поточному тарифі.",
        "btn_pay_stars": "⭐ Сплатити Stars",
        "payment_success": "🎉 Pro активовано! Дякуємо за підтримку.",
        "payment_held": "⏳ Платіж отримано, але потрібна перевірка. Скоро підтвердимо.",
        "invite_text": (
            "👥 Ваше реферальне посилання:\n{link}\n\nЗа кожного нового користувача "
            "ви обидва отримуєте +{credits} кредитів."
        ),
        "key_saved": "🔑 Ключ збережено. Запити йдуть через ваш ключ OpenRouter — кредити не списуються.",
        "key_removed": "🔑 Ключ видалено. Ви знову на кредитній системі.",
        "key_invalid": "⚠️ Не вдалося перевірити ключ. Використання: /setkey <ваш ключ OpenRouter>",
        "prompt_saved": "💾 Промпт збережено. Дивіться /prompts.",
        "prompts_empty": "У вас поки немає збережених промптів. Запустіть свій запит і натисніть «Зберегти».",
        "prompts_pick": "Ваші збережені промпти:",
        "prompts_limit": "На безкоштовному тарифі можна зберігати до {limit} промптів. Pro — без обмежень: /pro",
        "btn_save_prompt": "💾 Зберегти промпт",
        "privacy_text": (
            "🔒 Приватність\n\nПереслан контент обробляється тимчасово — лише щоб виконати вашу "
            "дію. Похідний текст (розшифрування/розпізнавання) кешується за непрозорим файловим "
            "id Telegram, щоб не платити двічі, і не містить ідентифікаторів акаунта. Ми нічого "
            "не продаємо. Видалити дані: /forgetme"
        ),
        "forgetme_confirm": "Видалити всі ваші дані (тариф, ліміти, промпти, платежі)? Це незворотно.",
        "forgetme_done": "🗑 Готово. Усі ваші дані видалено.",
        # --- Plans / upgrade ---
        "btn_upgrade": "⭐ Перейти на Pro",
        "plans_header": "💎 Тарифи та ціни",
        "plans_free_block": (
            "🆓 Free\n"
            "• {signup} кредитів для старту (одноразовий бонус)\n"
            "• {daily} безкоштовних кредитів щодня (не накопичуються)\n"
            "• Оплата за фактом: текст ~0.1–0.2 кредита/дія · аудіо 1 кредит/хвилина · "
            "фото 0.5 кредита/фото"
        ),
        "plans_pro_block": (
            "⭐ Pro — {stars} ⭐ / міс\n"
            "• {pro_credits} кредитів щомісяця — у 2× більше, ніж ви платите ⭐\n"
            "• −{discount}% на пакети кредитів\n"
            "• Преміум-модель, більший контекст, у групах /ask і /actions, безліміт промптів"
        ),
        "plans_byo_line": (
            "🔑 Власний ключ — без підписки та кредитів: через /setkey ви платите "
            "напряму за свій API OpenRouter."
        ),
        "plans_pro_active": "✅ У вас Pro — діє до {date}.",
        "usage_pro_active": "✅ У вас Pro — діє до {date}.",
        "usage_byo_active": "🔑 Власний ключ активний — кредити не списуються.",
        # --- Credits ---
        "balance_line": "💳 Кредити: {persistent} (+{daily} безкоштовних сьогодні)",
        "daily_floor_note": "🎁 Щодня вам також нараховується {daily} безкоштовних кредитів.",
        "usage_invite": "👥 Запрошуйте друзів — кредити отримуєте обидва:\n{invite}",
        "credits_low": (
            "💳 Кредити закінчилися. Купіть пакет або оформіть Pro — це щомісячні "
            "кредити та −30% на пакети."
        ),
        "item_skipped_no_credits": "пропущено: немає кредитів",
        "feature_unavailable": "Ця функція зараз недоступна.",
        "btn_buy_credits": "💳 Купити кредити",
        "buy_credits_header": "Оберіть пакет кредитів (1 ⭐ = 1 кредит):",
        "pack_label": "{credits} кредитів — {stars} ⭐",
        "pack_invoice_title": "{credits} кредитів",
        "pack_invoice_desc": "Поповнення на {credits} кредитів Forwardly.",
        "credits_added": "🎉 Нараховано {credits} кредитів. Користуйтеся!",
        "pro_value_math": (
            "⭐ Forwardly Pro — {stars} ⭐ / міс\n\n"
            "Купівля кредитів: 1 ⭐ = 1 кредит (тобто {stars} ⭐ → {stars} кредитів).\n"
            "Pro: {stars} ⭐ → {pro_credits} кредитів — у 2× вигідніше — плюс −{discount}% на "
            "пакети кредитів, преміум-модель, більший контекст, питання в групах і "
            "безліміт збережених промптів."
        ),
        # --- Group mode ---
        "group_intro": (
            "👋 Привіт! Я вмію робити зведення групового чату.\n\n"
            "• /summary [N] — стисло про останні N повідомлень\n"
            "• /ask <питання> та /actions — функції Pro\n"
            "• /clear — адміни очищають мій буфер\n\n"
            "🔒 Я зберігаю лише короткий буфер останніх повідомлень у пам'яті "
            "(обмежений, з авто-завершенням) — нічого про цю групу не зберігається. "
            "Я бачу лише повідомлення, надіслані *після* мого входу "
            "(режим приватності має бути вимкнений)."
        ),
        "group_summary_empty": (
            "Поки нічого узагальнювати — я бачу лише повідомлення після мого входу. "
            "Переконайтеся, що режим приватності вимкнено (BotFather → /setprivacy → "
            "Disable), і додайте мене знову."
        ),
        "group_cooldown": "⏳ Трохи повільніше — я щойно робив зведення. Спробуйте за кілька секунд.",
        "group_admins_only": "Очистити буфер можуть лише адміністратори групи.",
        "group_cleared": "🧹 Буфер очищено.",
        "group_ask_usage": "Використання: /ask <ваше питання щодо нещодавнього треду>",
        # --- Per-task model selection (BYO) ---
        "models_byo_only": (
            "🔧 Вибір моделі для кожної задачі — функція для тих, хто використовує "
            "власний ключ. Додайте ключ OpenRouter через /setkey, потім /models "
            "дозволить обрати модель для кожної задачі."
        ),
        "models_header": (
            "🔧 Ваші моделі (за задачами). Натисніть «Змінити», щоб обрати зі списку "
            "або ввести власний slug."
        ),
        "models_slot_text": "Текст",
        "models_slot_vision": "Зір",
        "models_slot_transcribe": "Розшифрування",
        "models_slot_image": "Зображення",
        "btn_change": "Змінити",
        "btn_custom_slug": "✏️ Ввести власний slug",
        "btn_reset_slot": "↺ Скинути до типового",
        "btn_reset_all": "↺ Скинути все до типового",
        "models_pick_prompt": "Оберіть модель для: {slot}",
        "models_ask_slug": "Надішліть slug моделі (наприклад, openai/gpt-4o-mini):",
        "models_set": "✅ Модель встановлено: {slug}.",
        "models_invalid": "⚠️ Не знайшов таку модель у каталозі OpenRouter. Перевірте slug і спробуйте ще раз.",
        "models_modality_warn": "⚠️ Увага: модель може не підтримувати вхід/вихід для цієї задачі — все одно збережено.",
        "models_reset_done": "↺ Повернено типову модель для цієї задачі.",
        "models_reset_all_done": "↺ Усі слоти скинуто до типових.",
        # --- Moved out of handlers / contextual hints ---
        "invoice_title": "Forwardly Pro",
        "invoice_description": "Forwardly Pro на 30 днів: щомісячні кредити, знижка на пакети, преміум-модель, більший контекст.",
        "presentation_context_hint": (
            "📊 Можна додати свій шаблон .pptx/.potx та/або текст, файл чи посилання, "
            "потім надішліть — або натисніть ▶️ Запустити."
        ),
        "save_prompt_offer": "💾 Зберегти цей запит, щоб запускати його повторно?",
        "btn_confirm_delete": "✅ Так, видалити",
        "btn_cancel": "✖️ Скасувати",
        "forgetme_cancelled": "Скасовано — дані не змінено.",
        "models_default": "типова",
    },
}
