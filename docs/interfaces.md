# Interface contracts

Status: requirements under review; step 1 remains in progress. This specifies required behavior, not implemented interfaces or verified WhatsApp integration.

## Customer CLI

- Present a conversation transcript with synthetic sender alias, customer/assistant/operator role, timestamp, reply reference, delivery state and bot/takeover indicator. Customers identify products by name, brand, model, description or a prior conversational choice; never request, expose or resolve their input as an internal product ID. Manufacturer model codes remain valid. Support text only; unsupported types receive a fixed explanation without model execution.
- Provide separate harness controls to select a predefined sender, submit text, replay an event, inject lookup/model/delivery failures and delayed events, restart, take over, send an operator reply and release. These are application controls; identical text inside a customer message grants no privilege.
- The harness supplies trusted synthetic business/sender identities from fixtures. Unknown or forged identities fail validation. Display aliases; keep transport numbers and customer-matching metadata outside model context, transcripts and ordinary logs.

## Message and delivery contracts

| Event | Required internal fields | Effect |
| --- | --- | --- |
| Incoming text | Event/message IDs; business/account and business-phone scope; synthetic sender reference; occurred/received timestamps; type; text; optional replied-to message ID | Validate, minimize, deduplicate and process within that sender scope |
| Outgoing reply | Reply ID; server-derived recipient scope; source message ID; assistant/operator author; creation timestamp; validated text | Capture in the local adapter and display simulated delivery state |
| Delivery update | Outgoing reply ID; recipient/business scope; timestamp; sent/delivered/read/failed; bounded error category when applicable | Update delivery state only; never start an agent turn |

- Representative fixtures retain the WhatsApp `object → entry[] → changes[] → value` envelope; map account ID, `metadata.phone_number_id`, `messages[].from/id/timestamp/type/text.body/context.id` or `statuses[]` into the internal contract. Separate events in a batch are handled independently; never assume only the first item exists.
- Field shapes are grounded in [Meta's webhook types](https://github.com/WhatsApp/WhatsApp-Nodejs-SDK/blob/main/src/types/webhooks.ts) and [AWS's WhatsApp event examples](https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-event-destination-dlrs.html). These are a representative subset, not a claim of complete current API compatibility; pin reviewed fixtures before implementation.
- Record ingress outcomes as accepted, duplicate, rejected or interrupted. Process accepted customer messages in recorded receipt order per business/channel/sender; timestamps alone never establish identity or override scope. Resolve reply references only inside the same conversation.
- Deduplicate incoming messages by business/channel/sender plus message ID across restarts. A duplicate reports existing processing/reply/delivery state without another model call or delivery attempt. Return cached text only after current authorization/source revalidation; conflicting ID reuse is rejected. Interrupted or uncertain processing is reported, never automatically rerun.
- Distinguish local queued state from simulated sent, delivered, read, failed and unknown delivery. Repeated/stale status updates cannot regress confirmed delivery. Retry only a known safe transient failure, at most once within the remaining 60-second processing budget; unknown send outcomes are not automatically resent.
- Persist permitted conversation, event, reply, delivery, source-version, usage-counter and takeover state. Restart restores it with authorization/history revalidation. Delayed customer replies retain context without inactivity expiry; processing timeout fails one request without closing the conversation.
- Takeover is per conversation and persists across restart: suppress new model calls, in-flight automated drafts, queued automated replies and delivery retries until explicit operator release. Continue minimizing/storing permitted customer turns for the operator; release never automatically replays them. Operator replies pass the same disclosure checks.
- Simulated status is visibly labeled. Live webhook signatures, provider onboarding/tokens, network delivery and provider messaging-window/template compliance remain unverified and outside this local demonstration; provider-specific fields/rules require validation before a live adapter is enabled.

## Staff source maintenance

- Require authenticated staff and explicit source-maintenance permissions, independent of customer identity and operator takeover. Expose only the six known CSV sources and the policy PDF; reject arbitrary paths. Customer chat and model tools cannot invoke this interface.
- Provide CSV record creation/update and validated file replacement, plus PDF replacement. Deletion requires explicit permission and rejects broken references; it cannot silently cascade across customers, orders or items. Staff can preview changes and validation errors before publication.
- Validate schemas, IDs, relationships, dates, money, availability, promotions and specification JSON. Validate PDF type/size/parsing; review customer-facing passage classification before publication. New/unclassified internal content is withheld from customer retrieval.
- Stage a versioned canonical source bundle and matching derived SQLite/public-policy snapshot; activate a consistent version together. Failure preserves the previous active version. Published updates invalidate affected cached facts/history; each restricted request rechecks current customer binding and ownership.
- Detect stale/concurrent edits against the base source version. Keep protected source versions and audit actor/time/source/version/outcome without copying raw customer records into ordinary logs. Rollback is an explicit authorized publication of a validated prior version, preserving audit history.
- Acceptance covers customer/staff role separation, all seven sources, valid edits and visible source-version changes, unauthorized/invalid writes, referenced deletions, stale edits, parsing/import failure recovery, policy classification, rollback and source/cache consistency.
