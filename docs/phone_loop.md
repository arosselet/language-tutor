# The Phone Loop — wiring knocks to your lock screen (and replies back)

The knock system (`morning_knock.py`, `push_queue.py`) delivers via **one
generic webhook**: it POSTs JSON to `PUSH_WEBHOOK_URL` —

```json
{"title": "<tutor name>", "text_content": "<the dose>", "audio_url": "<mp3 url, only for audio doses>"}
```

— and the reply path comes back via a **GitHub `repository_dispatch`** event
(`knock-response`) that `.github/workflows/log-knock-response.yml` turns into
either a tap log or a judged rep. Any notification system that can receive a
webhook and POST to the GitHub API works. This doc gives the reference
implementation used by the Tamil system: **Home Assistant + the iOS/Android
companion app**, which gets you actionable buttons and an inline audio player.

```
knock push ─▶ phone notification ─┬▶ tap "Got it 👍"          ─▶ event TUTOR_ACK
                                  └▶ "Reply ✍️" + typed text   ─▶ event TUTOR_REPLY (reply_text)
                                        │
               mobile_app_notification_action
                                        │
               rest_command → GitHub dispatches API
                                        │
               repository_dispatch: knock-response ─▶ log-knock-response.yml
                                        │
               ack   → sync_state.py knock-response ack   (knock marked landed)
               reply → knock_reply.py "<text>"            (judged; production axis moves;
                                                           recast + scoreboard pushed back)
```

A tap is a **landed** signal only — it never writes learning state. The
**reply** is a real rep: judged against what the knock asked for; text the
knock revealed caps at *hinted* (only unaided production fires cold).

## Alternatives to Home Assistant

- **ntfy.sh** — simplest push-only path: a tiny relay (or ntfy's JSON publish)
  that maps `text_content` → message and `audio_url` → attachment. You lose
  the reply button; replies can still flow through the iOS Shortcut in §7.
- **Pushover / Pushcut / Tasker** — same shape: receive webhook, show
  notification; wire any "reply" affordance to the dispatches API below.

Set `PUSH_WEBHOOK_URL` (local `.env` + GitHub Actions secret) to whatever
endpoint you build.

## Home Assistant reference implementation

> **Secrets note:** if your repo is public, real webhook IDs and tokens never
> go in tracked files — keep them in HA's `secrets.yaml` and in GitHub secrets.

### 1. GitHub fine-grained PAT (for the reply path)

github.com → Settings → Developer settings → Fine-grained tokens: access to
**your tutor repo only**, permission **Contents: Read and write** (the only one
needed by the dispatches endpoint). Store in HA `secrets.yaml` as the whole
header value:

```yaml
github_dispatch_auth: "Bearer github_pat_xxxxxxxxxxxxxxxx"
```

### 2. `configuration.yaml` — the REST commands

```yaml
rest_command:
  tutor_knock_response:
    url: https://api.github.com/repos/<you>/<your-tutor-repo>/dispatches
    method: POST
    headers:
      Authorization: !secret github_dispatch_auth
      Accept: application/vnd.github+json
      X-GitHub-Api-Version: "2022-11-28"
    content_type: "application/json"
    payload: '{"event_type":"knock-response","client_payload":{"response":"{{ response }}"}}'
  tutor_knock_reply:
    url: https://api.github.com/repos/<you>/<your-tutor-repo>/dispatches
    method: POST
    headers:
      Authorization: !secret github_dispatch_auth
      Accept: application/vnd.github+json
      X-GitHub-Api-Version: "2022-11-28"
    content_type: "application/json"
    # tojson quotes AND escapes the typed text, so quotes/emoji can't break the JSON
    payload: '{"event_type":"knock-response","client_payload":{"response":"reply","text":{{ text | tojson }}}}'
```

A successful dispatch returns HTTP **204**.

### 3. The notification automation (edit in YAML mode, not the visual editor)

Three hard-won details: call notify with **`service:`** (the `action:` alias
collides with the button's `action:` key), **quote** the button action values,
and make audio **conditional** — text doses carry no `audio_url`, and an
unconditional attachment renders a broken file.

```yaml
alias: Tutor knock → phone
triggers:
  - trigger: webhook
    allowed_methods: [POST, PUT]
    local_only: false            # GitHub runners are remote; the webhook_id is the secret
    webhook_id: "<YOUR_WEBHOOK_ID>"
conditions: []
actions:
  - if:
      - condition: template
        # must render a literal boolean — "is defined and x" yields the STRING x
        value_template: "{{ trigger.json.audio_url | default('') | length > 0 }}"
    then:
      - service: notify.mobile_app_<your_device>
        data:
          title: "{{ trigger.json.title | default('Tutor', true) }}"
          message: "{{ trigger.json.text_content }}"
          data:
            tag: tutor-knock             # self-replacing — one knock at a time
            url: "{{ trigger.json.audio_url }}"
            attachment:
              url: "{{ trigger.json.audio_url }}"
              content-type: mp3          # file EXTENSION, not MIME — audio/mpeg errors on iOS
            actions:
              - action: "TUTOR_REPLY"
                title: "Reply ✍️"
                behavior: textInput
              - action: "TUTOR_ACK"
                title: "Got it 👍"
    else:
      - service: notify.mobile_app_<your_device>
        data:
          title: "{{ trigger.json.title | default('Tutor', true) }}"
          message: "{{ trigger.json.text_content }}"
          data:
            tag: tutor-knock
            actions:
              - action: "TUTOR_REPLY"
                title: "Reply ✍️"
                behavior: textInput
              - action: "TUTOR_ACK"
                title: "Got it 👍"
mode: single
```

`PUSH_WEBHOOK_URL` = `https://<your-ha-instance>/api/webhook/<YOUR_WEBHOOK_ID>`.

### 4. Tap-handler automations

```yaml
alias: "Knock — handle ack tap"
triggers:
  - trigger: event
    event_type: mobile_app_notification_action
    event_data: {action: TUTOR_ACK}
actions:
  - action: rest_command.tutor_knock_response
    data: {response: ack}
mode: single
```

```yaml
alias: "Knock — handle typed reply"
triggers:
  - trigger: event
    event_type: mobile_app_notification_action
    event_data: {action: TUTOR_REPLY}
actions:
  - action: rest_command.tutor_knock_reply
    data:
      text: "{{ trigger.event.data.reply_text }}"
mode: single
```

### 5. Test before trusting it live

```bash
# reply path end-to-end (terminal — never paste the PAT into a chat)
curl -X POST https://api.github.com/repos/<you>/<repo>/dispatches \
  -H "Authorization: Bearer github_pat_xxx" \
  -H "Accept: application/vnd.github+json" \
  -d '{"event_type":"knock-response","client_payload":{"response":"reply","text":"<a line in the language>"}}'
```

Expect 204, a **Log Knock Response** workflow run through the judge step, a
`Knock reply: …` commit, and a push-back notification with the recast +
scoreboard. Then fire a real knock: Actions → **Tutor Knock** → Run workflow →
`force: true`.

### 6. Gotchas (all field-tested)

- **iOS action buttons are hidden** until you long-press / pull down the notification.
- **Dictation into the reply field is a better rep than typing** — real life needs your mouth.
- **Audio attachments cap at 5 MB** on the iOS companion app.
- **Pre-warm matters:** `push_to_phone()` GETs the audio URL before notifying —
  a cold CDN path can be slower than iOS's attachment fetch window.
- **Template conditions must render literal booleans** (`| default('') | length > 0`).
- **`!secret` is read at platform load** — reload REST commands after changing `secrets.yaml`.

### 7. Home-screen "Tell the tutor" button (iOS Shortcut → same pipeline)

A standalone Shortcut that opens the reply channel without a live notification:
**Ask for Input** (text) → **Get Contents of URL** (POST to the dispatches API,
headers as above, body: `event_type` = `knock-response`, `client_payload` =
Dictionary {`response`: `reply`, `text`: Provided Input}). The one gotcha: in
the Shortcuts JSON editor, nesting only happens when a field's *type* is
explicitly Dictionary.
