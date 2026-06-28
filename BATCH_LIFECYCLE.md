# Batch lifecycle

How Forwardly AI groups incoming messages into a "batch" and when that batch is
replaced. This is the canonical reference for the rules implemented in
`bot/handlers/collect.py` and `bot/services/batch.py`.

## What a batch is

A **batch** is the set of forwarded/sent messages the bot assembles into one
labeled document, which your actions (Summary, Reply, Custom prompt, …) then run
against. A chat has at most one batch at a time. Batch state is in memory only
(`ChatState`): the pending messages, the finalized item texts, retained photo
bytes, the debounce timer, and a `replaced_previous` flag.

A batch moves through two phases:

- **Collecting** — messages are arriving; each one resets the debounce timer
  (`DEBOUNCE_SECONDS`). `has_active_batch` is still `False`.
- **Finalized** — the user went quiet, the batch was processed (media
  transcribed, photos OCR'd) and the actions keyboard was shown.
  `has_active_batch` is `True` (there are finalized `item_texts`).

## Canonical rules

1. **Forwarded or directly-sent messages/media start or extend a batch.** While
   they keep arriving they are appended to the *collecting* batch and the
   debounce timer is reset. When the flow stops, the batch is finalized and the
   actions keyboard is shown.
2. **Plain typed text is a custom prompt** against the already-finalized batch.
   It does **not** start a new batch.
3. **Forwarded/media after a batch is already finalized starts a NEW batch** and
   replaces the previous one. The old assembled context, retained photos, last
   custom prompt, and any pending timer are dropped, and the user is told a new
   batch started (`new_batch_started`, shown once, just before `batch_ready`).
4. **`/reset`** clears the current batch and session state manually (keeps the
   chosen language). `/start` does the same and re-greets.

## Edge cases (and how they are handled)

| Situation | Behavior |
|---|---|
| New forward arrives **while still collecting** (before finalize) | Joins the current batch (rule 1). `has_active_batch` is `False`, so no replacement. |
| New forward arrives **after finalize / after an answer** | Starts a fresh batch; the old context + retained photos are discarded (rule 3). Shows the "new batch started" notice. |
| Mixed message | If it carries forwarded/media content it counts as batch input (rule 1/3). If it is plain text with no media and a finalized batch exists, it is a custom prompt (rule 2). |
| Plain text while a batch is still collecting | Joins the batch as a text item (there is no finalized batch yet to prompt against). |
| Follow-up custom prompts | Keep working on the same finalized batch until a new batch starts or `/reset`. No re-transcription, no extra batch. |
| Replacement happens | `start_new_batch` cancels the old debounce task and clears `item_texts`, `pending`, `photos`, `dropped`, `limit_notified`, and `last_custom_prompt` — no leftovers, no double processing. |

## The "new batch started" notice

`replaced_previous` is set when a finalized batch is replaced (rule 3). It is
captured and cleared exactly once at finalize, so the notice fires a single time
and never leaks into a later finalize. It is **not** shown for the first batch in
a session or while a batch is still collecting — only when an existing finalized
batch is actually replaced.

What triggers a new batch (forwarded messages / sent media) vs. a custom prompt
(plain text) is detected in `collect.is_new_batch_trigger` / `_is_plain_text` and
is unchanged by this document.
