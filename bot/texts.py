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
            "👋 Привет! Я собираю пачку сообщений и превращаю её в текст, "
            "с которым можно работать через LLM.\n\n"
            "1️⃣ Перешлите или отправьте несколько сообщений подряд — текст, "
            "голосовые, кружочки, видео, аудио, документы или фото.\n"
            "2️⃣ Я подожду пару секунд, расшифрую медиа, распознаю текст с картинок "
            "и соберу всё в один документ с именами отправителей.\n"
            "3️⃣ Выберите действие на клавиатуре или нажмите «✍️ Свой запрос».\n"
            "4️⃣ К своему запросу можно приложить контекст — файл или ссылку.\n\n"
            "Команды:\n/reset — очистить пачку\n/pro — перейти на Pro\n"
            "🔒 /privacy — как мы обращаемся с данными"
        ),
        "reset_done": "🧹 Пачка очищена. Присылайте новые сообщения.",
        "help": (
            "ℹ️ Как это работает:\n"
            "• Перешлите или отправьте несколько сообщений подряд (текст, голосовые, "
            "кружочки, видео, аудио, документы, фото).\n"
            "• Я расшифрую медиа, распознаю текст с картинок и соберу всё в один "
            "документ с именами отправителей.\n"
            "• Выберите действие на клавиатуре — оно появится как команда, к которой "
            "можно добавить контекст (текст, файл или ссылку), затем «▶️ Запустить».\n"
            "• Или просто напишите свой запрос текстом — он выполнится по текущей пачке.\n\n"
            "Команды: /start, /reset, /help, /lang, /pro, /plans, /usage\n"
            "/setkey, /removekey — свой ключ OpenRouter · /prompts — сохранённые запросы\n"
            "/invite — пригласить друзей · /privacy, /forgetme — данные"
        ),
        "lang_choose": "Выбери язык интерфейса:",
        "lang_set": "✅ Язык интерфейса — русский.",
        "finalizing": "🛠 Обрабатываю пачку (расшифровка, распознавание)…",
        "empty_batch": "Пачка пустая — нечего обрабатывать.",
        "batch_ready": "✅ Пачка готова. Что сделать?",
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
        "custom_prompt_empty": "Не вижу инструкции. Напишите, что нужно сделать с пачкой.",
        "custom_add_context_q": "Добавить контекст к запросу (файл или ссылку)?",
        "btn_attach": "📎 Прикрепить файл / ссылку",
        "btn_send": "▶️ Отправить",
        "custom_send_context": "Пришлите файл (.pdf/.docx/.txt/.md) или сообщение со ссылкой.",
        "context_added_file": "📎 Контекст из файла «{name}» добавлен.",
        "context_added_link": "🔗 Контекст по ссылке добавлен.",
        "context_file_failed": "⚠️ Не удалось прочитать файл «{name}»: {error}",
        "context_link_failed": "⚠️ Не удалось загрузить ссылку {url}: {error}",
        "context_none_found": "Не нашёл ни файла, ни ссылки — выполняю запрос без контекста.",
        "followup_hint": "Можно выбрать ещё одно действие для этой же пачки 👇",
        "long_result_heads_up": "📄 Ответ длинный — прислал его файлом.",
        "not_allowed": "⛔ Извините, у вас нет доступа к этому боту.",
        "llm_error": "😕 Не получилось получить ответ от модели. Попробуйте позже.",
        "generic_error": "😕 Что-то пошло не так. Попробуйте ещё раз.",
        "rate_limit_batches": (
            "🚦 Лимит пачек исчерпан ({limit} в час). Попробуйте через ~{minutes} мин."
        ),
        "rate_limit_llm": (
            "🚦 Лимит запросов к модели исчерпан ({limit} в сутки). "
            "Попробуйте через ~{hours} ч."
        ),
        "building_presentation": "📊 Собираю презентацию…",
        "building_pdf": "📄 Собираю PDF…",
        "building_image": "🎨 Генерирую изображение…",
        "presentation_caption": "📊 Презентация готова.",
        "pdf_caption": "📄 Документ готов.",
        "presentation_failed": "😕 Не удалось собрать презентацию.",
        "pdf_failed": "😕 Не удалось собрать PDF.",
        "image_failed": "😕 Не удалось сгенерировать изображение.",
        # Action button labels
        "action_summary": "📝 Краткое содержание",
        "action_structure": "📋 Структурировать",
        "action_reply": "💬 Черновик ответа",
        "action_email": "✉️ Follow-up письмо",
        "action_items": "✅ Задачи и решения",
        "action_translate": "🌐 Перевести (EN)",
        "action_presentation": "📊 Презентация",
        "action_pdf": "📄 PDF",
        "action_image": "🎨 Картинка",
        "action_custom": "✍️ Или просто напишите свой запрос ⬇️",
        # --- Monetization / account ---
        "paywall_image": "🎨 Генерация изображений доступна на Pro.",
        "paywall_pptx": "📊 Презентации доступны на Pro.",
        "paywall_generic": "Эта функция недоступна на текущем тарифе.",
        "limit_audio": "Достигнут дневной лимит расшифровки аудио.",
        "limit_photo": "Достигнут дневной лимит анализа фото.",
        "limit_llm": "🚦 Достигнут дневной лимит запросов к модели.",
        "item_not_transcribed": "не расшифровано: достигнут дневной лимит",
        "item_not_ocr": "не распознано: достигнут дневной лимит",
        "upgrade_hint": "ℹ️ Часть элементов пропущена из-за лимитов. Больше — на Pro: /pro",
        "pro_benefits": (
            "⭐ Forwardly Pro\n\n• Генерация изображений 🎨 и презентаций 📊\n"
            "• Большие дневные лимиты аудио/фото/запросов\n"
            "• Более мощная модель и больший контекст\n\n"
            "Цена: {stars}⭐ или {usdt} USDT за 30 дней."
        ),
        "btn_pay_stars": "⭐ Оплатить Stars",
        "btn_pay_crypto": "💎 Оплатить криптой",
        "btn_paid_check": "✅ Я оплатил — проверить",
        "payment_success": "🎉 Pro активирован! Спасибо за поддержку.",
        "payment_held": "⏳ Платёж получен, но требует проверки. Мы скоро всё подтвердим.",
        "crypto_not_paid": "Платёж пока не виден. Если вы только что оплатили — подождите минуту и нажмите ещё раз.",
        "usage_report": (
            "📊 Тариф: {plan}\n\nОсталось сегодня:\n• 🎙 Аудио: {audio_min} мин\n"
            "• 🖼 Анализ фото: {photos}\n• 💬 Текстовые действия: {llm}\n"
            "• 🎨 Изображения: {images}\n• 📊 Презентации: {pptx}\n\n"
            "🎁 Бонус при регистрации: {bonus_audio_min} мин аудио, {bonus_photos} фото\n\n"
            "👥 Приглашайте друзей — бонус обоим:\n{invite}"
        ),
        "plan_pro": "Pro (до {date})",
        "plan_free": "Free",
        "byo_active": "Свой ключ (без лимитов)",
        "invite_text": (
            "👥 Ваша реферальная ссылка:\n{link}\n\nЗа каждого нового пользователя "
            "вы оба получаете +{audio_min} мин аудио и +{photos} фото."
        ),
        "key_saved": "🔑 Ключ сохранён. Теперь запросы идут через ваш ключ OpenRouter без лимитов.",
        "key_removed": "🔑 Ключ удалён. Снова действуют обычные лимиты.",
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
        "see_plans_hint": "Подробнее — /plans",
        "plans_header": "💎 Тарифы и цены",
        "plans_free_block": (
            "🆓 Free\n"
            "• Бонус при регистрации: {signup_audio_min} мин расшифровки + "
            "{signup_photos} анализов фото (разово)\n"
            "• В день: {daily_audio_min} мин аудио, {daily_photos} фото, "
            "{daily_llm} текстовых действий\n"
            "• Краткое содержание, структура, ответы, follow-up письма, задачи, перевод, PDF\n"
            "• До {saved_prompts} сохранённых промптов\n"
            "❌ Без генерации изображений · ❌ Без презентаций"
        ),
        "plans_pro_block": (
            "⭐ Pro\n"
            "• Всё из Free и большие дневные лимиты: {pro_audio_min} мин аудио, "
            "{pro_photos} фото, {pro_llm} текстовых действий\n"
            "✅ Генерация изображений (до {pro_images}/день) · "
            "✅ Презентации (до {pro_pptx}/день)\n"
            "• Премиум-модель ({pro_model}), больший контекст ({pro_context} симв.)\n"
            "• Безлимит сохранённых промптов"
        ),
        "plans_byo_line": (
            "🔑 Свой ключ: /setkey с вашим ключом OpenRouter → без лимитов, "
            "все функции (вы платите за свой API)."
        ),
        "plans_price_line": "💳 Цена: {stars} ⭐ / мес или {usdt} USDT / мес.",
        "plans_pro_active": "✅ У вас Pro — действует до {date}.",
    },
    # ================================================================= EN ===
    "en": {
        "welcome": (
            "👋 Hi! I collect a batch of messages and turn it into text you can "
            "work on with an LLM.\n\n"
            "1️⃣ Forward or send several messages in a row — text, voice, video "
            "notes, videos, audio, documents or photos.\n"
            "2️⃣ I'll wait a couple of seconds, transcribe media, OCR images and "
            "assemble one document labeled with sender names.\n"
            "3️⃣ Pick an action on the keyboard or tap “✍️ Custom prompt”.\n"
            "4️⃣ You can attach context to a custom prompt — a file or a link.\n\n"
            "Commands:\n/reset — clear the batch\n/pro — upgrade to Pro\n"
            "🔒 /privacy — how we handle your data"
        ),
        "reset_done": "🧹 Batch cleared. Send new messages.",
        "help": (
            "ℹ️ How it works:\n"
            "• Forward or send several messages in a row (text, voice, video notes, "
            "videos, audio, documents, photos).\n"
            "• I transcribe media, OCR images and assemble one document labeled with "
            "sender names.\n"
            "• Pick an action — it appears as a command you can extend with context "
            "(text, file, or link), then “▶️ Run”.\n"
            "• Or just type your prompt — it runs against the current batch.\n\n"
            "Commands: /start, /reset, /help, /lang, /pro, /plans, /usage\n"
            "/setkey, /removekey — your OpenRouter key · /prompts — saved prompts\n"
            "/invite — refer friends · /privacy, /forgetme — your data"
        ),
        "lang_choose": "Choose interface language:",
        "lang_set": "✅ Language set to English.",
        "finalizing": "🛠 Processing the batch (transcription, OCR)…",
        "empty_batch": "The batch is empty — nothing to process.",
        "batch_ready": "✅ Batch ready. What should I do?",
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
        "custom_prompt_empty": "I don't see an instruction. Tell me what to do with the batch.",
        "custom_add_context_q": "Add context to your prompt (a file or a link)?",
        "btn_attach": "📎 Attach file / link",
        "btn_send": "▶️ Send",
        "custom_send_context": "Send a file (.pdf/.docx/.txt/.md) or a message with a link.",
        "context_added_file": "📎 Context from file “{name}” added.",
        "context_added_link": "🔗 Context from the link added.",
        "context_file_failed": "⚠️ Couldn't read file “{name}”: {error}",
        "context_link_failed": "⚠️ Couldn't fetch link {url}: {error}",
        "context_none_found": "No file or link found — running the prompt without context.",
        "followup_hint": "You can run another action on the same batch 👇",
        "long_result_heads_up": "📄 The answer is long — sent it as a file.",
        "not_allowed": "⛔ Sorry, you don't have access to this bot.",
        "llm_error": "😕 Couldn't get a response from the model. Try again later.",
        "generic_error": "😕 Something went wrong. Please try again.",
        "rate_limit_batches": (
            "🚦 Batch limit reached ({limit}/hour). Try again in ~{minutes} min."
        ),
        "rate_limit_llm": (
            "🚦 Model request limit reached ({limit}/day). Try again in ~{hours} h."
        ),
        "building_presentation": "📊 Building the presentation…",
        "building_pdf": "📄 Building the PDF…",
        "building_image": "🎨 Generating the image…",
        "presentation_caption": "📊 Presentation ready.",
        "pdf_caption": "📄 Document ready.",
        "presentation_failed": "😕 Couldn't build the presentation.",
        "pdf_failed": "😕 Couldn't build the PDF.",
        "image_failed": "😕 Couldn't generate the image.",
        "action_summary": "📝 Summary",
        "action_structure": "📋 Structure",
        "action_reply": "💬 Draft reply",
        "action_email": "✉️ Follow-up email",
        "action_items": "✅ Action items",
        "action_translate": "🌐 Translate (EN)",
        "action_presentation": "📊 Presentation",
        "action_pdf": "📄 PDF",
        "action_image": "🎨 Image",
        "action_custom": "✍️ Or just type your prompt ⬇️",
        # --- Monetization / account ---
        "paywall_image": "🎨 Image generation is a Pro feature.",
        "paywall_pptx": "📊 Presentations are a Pro feature.",
        "paywall_generic": "This feature isn't available on your plan.",
        "limit_audio": "Daily audio transcription limit reached.",
        "limit_photo": "Daily photo analysis limit reached.",
        "limit_llm": "🚦 Daily model-request limit reached.",
        "item_not_transcribed": "not transcribed: daily limit reached",
        "item_not_ocr": "not analyzed: daily limit reached",
        "upgrade_hint": "ℹ️ Some items were skipped due to limits. Get more with Pro: /pro",
        "pro_benefits": (
            "⭐ Forwardly Pro\n\n• Image 🎨 and presentation 📊 generation\n"
            "• Much higher daily audio/photo/request limits\n"
            "• A stronger model and a larger context\n\n"
            "Price: {stars}⭐ or {usdt} USDT for 30 days."
        ),
        "btn_pay_stars": "⭐ Pay with Stars",
        "btn_pay_crypto": "💎 Pay with crypto",
        "btn_paid_check": "✅ I've paid — check",
        "payment_success": "🎉 Pro is active! Thanks for the support.",
        "payment_held": "⏳ Payment received but needs a quick review. We'll confirm shortly.",
        "crypto_not_paid": "Payment not visible yet. If you just paid, wait a minute and tap again.",
        "usage_report": (
            "📊 Plan: {plan}\n\nRemaining today:\n• 🎙 Audio: {audio_min} min\n"
            "• 🖼 Photo analyses: {photos}\n• 💬 Text actions: {llm}\n"
            "• 🎨 Images: {images}\n• 📊 Presentations: {pptx}\n\n"
            "🎁 Signup bonus: {bonus_audio_min} min audio, {bonus_photos} photos\n\n"
            "👥 Invite friends — both get a bonus:\n{invite}"
        ),
        "plan_pro": "Pro (until {date})",
        "plan_free": "Free",
        "byo_active": "Your own key (no limits)",
        "invite_text": (
            "👥 Your referral link:\n{link}\n\nFor every new user, you both get "
            "+{audio_min} min audio and +{photos} photos."
        ),
        "key_saved": "🔑 Key saved. Your requests now use your own OpenRouter key with no limits.",
        "key_removed": "🔑 Key removed. Standard limits apply again.",
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
        "see_plans_hint": "See /plans for details.",
        "plans_header": "💎 Plans & pricing",
        "plans_free_block": (
            "🆓 Free\n"
            "• Signup bonus: {signup_audio_min} min transcription + "
            "{signup_photos} photo analyses (one-time)\n"
            "• Daily: {daily_audio_min} min audio, {daily_photos} photos, "
            "{daily_llm} text actions\n"
            "• Summaries, structure, replies, follow-up emails, action items, translation, PDF\n"
            "• Up to {saved_prompts} saved prompts\n"
            "❌ No image generation · ❌ No presentations"
        ),
        "plans_pro_block": (
            "⭐ Pro\n"
            "• Everything in Free, with higher daily caps: {pro_audio_min} min audio, "
            "{pro_photos} photos, {pro_llm} text actions\n"
            "✅ Image generation (up to {pro_images}/day) · "
            "✅ Presentations (up to {pro_pptx}/day)\n"
            "• Premium model ({pro_model}), larger context ({pro_context} chars)\n"
            "• Unlimited saved prompts"
        ),
        "plans_byo_line": (
            "🔑 Bring your own key: /setkey with your OpenRouter key → no limits, "
            "all features (you pay your API usage)."
        ),
        "plans_price_line": "💳 Price: {stars} ⭐ / month or {usdt} USDT / month.",
        "plans_pro_active": "✅ You're on Pro — valid until {date}.",
    },
    # ================================================================= UK ===
    "uk": {
        "welcome": (
            "👋 Привіт! Я збираю пачку повідомлень і перетворюю її на текст, "
            "з яким можна працювати через LLM.\n\n"
            "1️⃣ Перешліть або надішліть кілька повідомлень поспіль — текст, "
            "голосові, кружечки, відео, аудіо, документи чи фото.\n"
            "2️⃣ Я зачекаю кілька секунд, розшифрую медіа, розпізнаю текст з "
            "зображень і зберу все в один документ з іменами відправників.\n"
            "3️⃣ Оберіть дію на клавіатурі або натисніть «✍️ Свій запит».\n"
            "4️⃣ До свого запиту можна додати контекст — файл або посилання.\n\n"
            "Команди:\n/reset — очистити пачку\n/pro — перейти на Pro\n"
            "🔒 /privacy — як ми обробляємо дані"
        ),
        "reset_done": "🧹 Пачку очищено. Надсилайте нові повідомлення.",
        "help": (
            "ℹ️ Як це працює:\n"
            "• Перешліть або надішліть кілька повідомлень поспіль (текст, голосові, "
            "кружечки, відео, аудіо, документи, фото).\n"
            "• Я розшифрую медіа, розпізнаю текст із зображень і зберу все в один "
            "документ з іменами відправників.\n"
            "• Оберіть дію на клавіатурі — вона з'явиться як команда, до якої можна "
            "додати контекст (текст, файл або посилання), потім «▶️ Запустити».\n"
            "• Або просто напишіть свій запит текстом — він виконається за поточною пачкою.\n\n"
            "Команди: /start, /reset, /help, /lang, /pro, /plans, /usage\n"
            "/setkey, /removekey — свій ключ OpenRouter · /prompts — збережені запити\n"
            "/invite — запросити друзів · /privacy, /forgetme — дані"
        ),
        "lang_choose": "Обери мову інтерфейсу:",
        "lang_set": "✅ Мова інтерфейсу — українська.",
        "finalizing": "🛠 Обробляю пачку (розшифрування, розпізнавання)…",
        "empty_batch": "Пачка порожня — немає що обробляти.",
        "batch_ready": "✅ Пачка готова. Що зробити?",
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
        "custom_prompt_empty": "Не бачу інструкції. Напишіть, що зробити з пачкою.",
        "custom_add_context_q": "Додати контекст до запиту (файл або посилання)?",
        "btn_attach": "📎 Прикріпити файл / посилання",
        "btn_send": "▶️ Надіслати",
        "custom_send_context": "Надішліть файл (.pdf/.docx/.txt/.md) або повідомлення з посиланням.",
        "context_added_file": "📎 Контекст із файлу «{name}» додано.",
        "context_added_link": "🔗 Контекст за посиланням додано.",
        "context_file_failed": "⚠️ Не вдалося прочитати файл «{name}»: {error}",
        "context_link_failed": "⚠️ Не вдалося завантажити посилання {url}: {error}",
        "context_none_found": "Не знайшов ні файлу, ні посилання — виконую запит без контексту.",
        "followup_hint": "Можна обрати ще одну дію для цієї ж пачки 👇",
        "long_result_heads_up": "📄 Відповідь довга — надіслав її файлом.",
        "not_allowed": "⛔ Вибачте, у вас немає доступу до цього бота.",
        "llm_error": "😕 Не вдалося отримати відповідь від моделі. Спробуйте пізніше.",
        "generic_error": "😕 Щось пішло не так. Спробуйте ще раз.",
        "rate_limit_batches": (
            "🚦 Ліміт пачок вичерпано ({limit} на годину). Спробуйте за ~{minutes} хв."
        ),
        "rate_limit_llm": (
            "🚦 Ліміт запитів до моделі вичерпано ({limit} на добу). "
            "Спробуйте за ~{hours} год."
        ),
        "building_presentation": "📊 Збираю презентацію…",
        "building_pdf": "📄 Збираю PDF…",
        "building_image": "🎨 Генерую зображення…",
        "presentation_caption": "📊 Презентація готова.",
        "pdf_caption": "📄 Документ готовий.",
        "presentation_failed": "😕 Не вдалося зібрати презентацію.",
        "pdf_failed": "😕 Не вдалося зібрати PDF.",
        "image_failed": "😕 Не вдалося згенерувати зображення.",
        "action_summary": "📝 Короткий зміст",
        "action_structure": "📋 Структурувати",
        "action_reply": "💬 Чернетка відповіді",
        "action_email": "✉️ Follow-up лист",
        "action_items": "✅ Завдання і рішення",
        "action_translate": "🌐 Перекласти (EN)",
        "action_presentation": "📊 Презентація",
        "action_pdf": "📄 PDF",
        "action_image": "🎨 Зображення",
        "action_custom": "✍️ Або просто напишіть свій запит ⬇️",
        # --- Monetization / account ---
        "paywall_image": "🎨 Генерація зображень доступна на Pro.",
        "paywall_pptx": "📊 Презентації доступні на Pro.",
        "paywall_generic": "Ця функція недоступна на поточному тарифі.",
        "limit_audio": "Досягнуто денного ліміту розшифрування аудіо.",
        "limit_photo": "Досягнуто денного ліміту аналізу фото.",
        "limit_llm": "🚦 Досягнуто денного ліміту запитів до моделі.",
        "item_not_transcribed": "не розшифровано: досягнуто денного ліміту",
        "item_not_ocr": "не розпізнано: досягнуто денного ліміту",
        "upgrade_hint": "ℹ️ Частину елементів пропущено через ліміти. Більше — на Pro: /pro",
        "pro_benefits": (
            "⭐ Forwardly Pro\n\n• Генерація зображень 🎨 та презентацій 📊\n"
            "• Значно більші денні ліміти аудіо/фото/запитів\n"
            "• Потужніша модель і більший контекст\n\n"
            "Ціна: {stars}⭐ або {usdt} USDT за 30 днів."
        ),
        "btn_pay_stars": "⭐ Сплатити Stars",
        "btn_pay_crypto": "💎 Сплатити криптою",
        "btn_paid_check": "✅ Я сплатив — перевірити",
        "payment_success": "🎉 Pro активовано! Дякуємо за підтримку.",
        "payment_held": "⏳ Платіж отримано, але потрібна перевірка. Скоро підтвердимо.",
        "crypto_not_paid": "Платіж поки не видно. Якщо ви щойно сплатили — зачекайте хвилину й натисніть ще раз.",
        "usage_report": (
            "📊 Тариф: {plan}\n\nЗалишилось сьогодні:\n• 🎙 Аудіо: {audio_min} хв\n"
            "• 🖼 Аналіз фото: {photos}\n• 💬 Текстові дії: {llm}\n"
            "• 🎨 Зображення: {images}\n• 📊 Презентації: {pptx}\n\n"
            "🎁 Бонус за реєстрацію: {bonus_audio_min} хв аудіо, {bonus_photos} фото\n\n"
            "👥 Запрошуйте друзів — бонус обом:\n{invite}"
        ),
        "plan_pro": "Pro (до {date})",
        "plan_free": "Free",
        "byo_active": "Власний ключ (без лімітів)",
        "invite_text": (
            "👥 Ваше реферальне посилання:\n{link}\n\nЗа кожного нового користувача "
            "ви обидва отримуєте +{audio_min} хв аудіо та +{photos} фото."
        ),
        "key_saved": "🔑 Ключ збережено. Тепер запити йдуть через ваш ключ OpenRouter без лімітів.",
        "key_removed": "🔑 Ключ видалено. Знову діють звичайні ліміти.",
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
        "see_plans_hint": "Деталі — /plans",
        "plans_header": "💎 Тарифи та ціни",
        "plans_free_block": (
            "🆓 Free\n"
            "• Бонус за реєстрацію: {signup_audio_min} хв розшифрування + "
            "{signup_photos} аналізів фото (одноразово)\n"
            "• Щодня: {daily_audio_min} хв аудіо, {daily_photos} фото, "
            "{daily_llm} текстових дій\n"
            "• Короткий зміст, структура, відповіді, follow-up листи, завдання, переклад, PDF\n"
            "• До {saved_prompts} збережених промптів\n"
            "❌ Без генерації зображень · ❌ Без презентацій"
        ),
        "plans_pro_block": (
            "⭐ Pro\n"
            "• Усе з Free і більші денні ліміти: {pro_audio_min} хв аудіо, "
            "{pro_photos} фото, {pro_llm} текстових дій\n"
            "✅ Генерація зображень (до {pro_images}/день) · "
            "✅ Презентації (до {pro_pptx}/день)\n"
            "• Преміум-модель ({pro_model}), більший контекст ({pro_context} симв.)\n"
            "• Безліміт збережених промптів"
        ),
        "plans_byo_line": (
            "🔑 Власний ключ: /setkey з вашим ключем OpenRouter → без лімітів, "
            "усі функції (ви платите за свій API)."
        ),
        "plans_price_line": "💳 Ціна: {stars} ⭐ / міс або {usdt} USDT / міс.",
        "plans_pro_active": "✅ У вас Pro — діє до {date}.",
    },
}
