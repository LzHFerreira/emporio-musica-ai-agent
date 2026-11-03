# Reviewed Meta text fixtures, target v24.0

These synthetic fixtures were independently reviewed on 2026-11-02 before client/mock implementation. Tests now exercise shared webhook, worker and Meta-client boundaries. They are not captured customer traffic, complete Meta schemas or live compatibility evidence. The chosen `META_API_VERSION=v24.0` is a local target; current-version status was not verified.

| Fixture | Contract exercised |
| --- | --- |
| [incoming-text.json](incoming-text.json) | Signed raw-body webhook; acknowledge HTTP 200 empty body only after durable acceptance; one job, no answer in HTTP response. |
| [outgoing-request.json](outgoing-request.json) | Versioned text send, bearer token, scoped recipient and optional reply context. |
| [acceptance-response.json](acceptance-response.json) | HTTP 200 provider message ID is acceptance only, not delivery. |
| [delivery-callback.json](delivery-callback.json) | Separate signed status webhook; scoped status persistence, no agent job. |

## Provenance

The [Meta Postman text endpoint](https://www.postman.com/meta/whatsapp-business-platform/request/8gvd47s/send-text-message) informed request shape. [Meta message types](https://github.com/WhatsApp/WhatsApp-Nodejs-SDK/blob/main/src/types/messages.ts) and [webhook types](https://github.com/WhatsApp/WhatsApp-Nodejs-SDK/blob/main/src/types/webhooks.ts) informed envelopes. The SDK is archived and has inconsistent `phoneNumberId`/metadata declarations; fixtures use `metadata.phone_number_id`. [AWS status examples](https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-event-destination-dlrs.html) independently corroborated status IDs and metadata. The [archived verification reference](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/) informed challenge/raw-body signature handling; it is not a dependency. Current Meta reference fetches were unavailable or rate-limited during review.

Optional provider fields may be absent and are ignored; do not forward them into model context. Local HTTP outcomes, error codes and mutation requirements are project contracts; they do not claim Meta emits each mock error. Full batch, callback, retry and scope behavior is in [interface contracts](../../interfaces.md#webhook-ingress) and actual coverage in [validation](../../validation.md).

## Fixture SHA-256

Any fixture change requires independent review and a matching digest update. Hashes pin the exact bytes:

- `incoming-text.json`: `076c3bace88c50ccdafae57667c261235c78e33d0a4da37820217cc691d0ddf9`
- `outgoing-request.json`: `a4b9790b5e2107c980b42bef48865c7e8c802c762aed3666b9a8c01d2b2d8ccc`
- `acceptance-response.json`: `c93dbb4846bd1d7384d8d3e33924fea8b271447bd9622ee76fc5289e6c33d169`
- `delivery-callback.json`: `71788c91483c5cdcbafb690f8f87364cd698acc29dcc984d67568d497cf152cb`
