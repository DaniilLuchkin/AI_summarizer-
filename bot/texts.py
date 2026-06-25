"""All user-facing strings in ru / en / uk, plus the `t()` lookup helper.

Code/identifiers stay in English; only the values here are shown to users.
Every handler resolves a per-user `lang` (see `resolve_lang`) and passes it to
`t(key, lang)`. Action button labels live here too — never hardcode them.
"""

from __future__ import annotations

SUPPORTED_LANGS = ("ru", "en", "uk")
DEFAULT_LANG = "ru"  # acceptance: unknown language_code -> Russian


def resolve_lang(language_code: str | None) -> str:
    """Map a Telegram language_code to one of our supported UI languages.

    ru -> ru, uk -> uk, en -> en, anything else -> Russian (the bot's primary
    audience). Only the language prefix matters (e.g. "en-US" -> "en").
    """
    code = (language_code or "").lower()
    if code.startswith("ru"):
        return "ru"
    if code.startswith("uk"):
        return "uk"
    if code.startswith("en"):
        return "en"
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
            "Команды:\n/reset — очистить пачку\n/start — показать справку"
        ),
        "reset_done": "🧹 Пачка очищена. Присылайте новые сообщения.",
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
        "action_selected": "🔹 {label}",
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
        "action_custom": "✍️ Свой запрос",
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
            "Commands:\n/reset — clear the batch\n/start — show this help"
        ),
        "reset_done": "🧹 Batch cleared. Send new messages.",
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
        "action_selected": "🔹 {label}",
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
        "action_custom": "✍️ Custom prompt",
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
            "Команди:\n/reset — очистити пачку\n/start — показати довідку"
        ),
        "reset_done": "🧹 Пачку очищено. Надсилайте нові повідомлення.",
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
        "action_selected": "🔹 {label}",
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
        "action_custom": "✍️ Свій запит",
    },
}
