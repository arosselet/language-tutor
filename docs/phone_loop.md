# The Phone Loop — pushes out, replies back

The **phone module** (`config.modules.phone`) is optional. With it off, the daily
session and the podcast feed are the whole system. With it on, the tutor reaches the
learner between sessions and the learner can answer from the lock screen. This document
is the contract. Any receiver that honours it works, and Home Assistant is one worked
example.

```
tick ─▶ morning_knock / push_queue / reply lanes ─▶ POST PUSH_WEBHOOK_URL ─▶ phone
                                                                              │
phone ─▶ GitHub repository_dispatch ─▶ .github/workflows/tutor.yml ◀──────────┘
           knock-response: ack | reply (+ text, knock_id, intent)
           episode-rating: episode + verdict
```

## Out: the webhook (`publish.push_to_phone`)

Every push is one `POST` of JSON to the secret `PUSH_WEBHOOK_URL`:

```json
{
  "title": "<the tutor's name>",
  "text_content": "<the body, in the read form>",
  "knock_id": "<the knock's log timestamp, or empty>",
  "tag": "tutor-<knock_id>-<nanoseconds>",
  "audio_url": "<mp3 URL; only present on a voice dose>"
}
```

- **`knock_id` is correlation.** Send it back with a reply so the judge grades the reply
  against the knock it answers.
- **`tag` is identity, unique per message.** A receiver that replaces a notification
  with the same tag would otherwise let a second push silently eat the first.
- **`audio_url`** is also on the podcast feed. Dismissing a push never loses a dose.
- **Quiet hours** are enforced before the POST, from `config.rails`. A held push says so
  in the log, and its artifact waits on the feed.
- An unreachable receiver fails the run after three tries. A dropped push is never
  silent.

## Back: `repository_dispatch`

The phone POSTs to `https://api.github.com/repos/<owner>/<repo>/dispatches` with a
fine-grained token scoped to this repo only, with **Contents: read and write**:

| `event_type` | `client_payload` | What runs |
|---|---|---|
| `knock-response` | `{"response": "ack", "knock_id": "…"}` | `sync_state.py knock-response ack`: the knock landed. A tap never writes learning state |
| `knock-response` | `{"response": "reply", "text": "…", "knock_id": "…", "intent": "reply"}` | `knock_reply.py`: judged against that knock; the production axis can move |
| `knock-response` | `{"response": "reply", "text": "…", "intent": "message"}` | the **message lane**: the learner talking to the tutor, ungraded |
| `episode-rating` | `{"episode": "<feed title>", "verdict": "finished \| stopped early \| lost the thread"}` | `sync_state.py rate-episode`: a listen, from the feed's picker |

**Routing a reply** (`knock_reply.is_message`): a `knock_id` means a reply to that
knock. `intent: "reply"` means a reply to the last knock that fired. Anything else is a
**message**. Untagged text is treated as a message and logged loudly, unless it answers
the open ask, because grading a request corrupts the ledger. A Receptive Check answer
("missed 4, 9") is recognized before any of this and parsed by Python.

Give a receiver two buttons that send different intents, **Reply** and **Message**,
and the routing never has to guess.

## The default receiver: ntfy

[ntfy](https://ntfy.sh) needs no server of your own. Subscribe to a hard-to-guess topic
in the app, then set `PUSH_WEBHOOK_URL` to a templated publish URL so ntfy reads our
JSON. It supports Go templates over a JSON body; check its "message templating" docs for
your version:

```
https://ntfy.sh/<your-topic>?tpl=1&t={{.title}}&m={{.text_content}}
```

Percent-encode the braces (`%7B%7B.title%7D%7D`) if your shell or tooling mangles them.
Audio arrives through the podcast feed rather than as an attachment. Push-only
receivers like this one have no reply path of their own. Add one with any tool that can
POST the dispatch above, such as an iOS Shortcut, a Tasker task or a bookmarklet.

## Worked example: Home Assistant (push and reply)

This is the receiver the reference system ran for months. HA's companion app shows
actionable buttons and plays `audio_url` inline.

1. **Token.** Put the fine-grained PAT in HA `secrets.yaml` as the whole header value:
   `github_dispatch_auth: "Bearer github_pat_…"`. Never commit it.
2. **Inbound webhook.** Create an automation triggered by a webhook. Its id goes into
   `PUSH_WEBHOOK_URL` (`https://<ha>/api/webhook/<id>`). The action is a
   `notify.mobile_app_<phone>` call:
   ```yaml
   data:
     title: "{{ trigger.json.title }}"
     message: "{{ trigger.json.text_content }}"
     data:
       tag: "{{ trigger.json.tag }}"
       url: "{{ trigger.json.audio_url | default('') }}"
       actions:
         - action: "TUTOR_ACK_{{ trigger.json.knock_id }}"
           title: "Got it"
         - action: "TUTOR_REPLY_{{ trigger.json.knock_id }}"
           title: "Reply"
           behavior: textInput
         - action: "TUTOR_MESSAGE"
           title: "Message"
           behavior: textInput
   ```
3. **The dispatch.** Add a `rest_command` in `configuration.yaml`:
   ```yaml
   rest_command:
     tutor_dispatch:
       url: https://api.github.com/repos/<owner>/<repo>/dispatches
       method: POST
       headers:
         Authorization: !secret github_dispatch_auth
         Accept: application/vnd.github+json
       content_type: "application/json"
       payload: '{"event_type":"knock-response","client_payload":{{ client_payload | to_json }}}'
   ```
4. **The action handler.** Add an automation on `mobile_app_notification_action` that
   parses the action id and calls `rest_command.tutor_dispatch`:
   - `TUTOR_ACK_<id>` → `{"response":"ack","knock_id":"<id>"}`
   - `TUTOR_REPLY_<id>` → `{"response":"reply","text":"{{ trigger.event.data.reply_text }}","knock_id":"<id>","intent":"reply"}`
   - `TUTOR_MESSAGE` → `{"response":"reply","text":"…","intent":"message"}`

Keep webhook ids and tokens in HA secrets and GitHub secrets, never in tracked files.

## Wiring checklist (SETUP Phase 6, Wire)

1. Set the `PUSH_WEBHOOK_URL` secret in GitHub Actions, and in `.env` for local runs.
2. Set `"modules": {"phone": true}` in `config/tutor.json`.
3. Uncomment the cron in `.github/workflows/tutor.yml`. The rails decide when to
   actually knock, so the cron only has to be frequent enough to filter.
4. Run the workflow once with `force: true`. A push should land, and a reply should
   produce a judged push back.
