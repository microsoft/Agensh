- **shared context board** — an append-only log of short, verified notes from every agent.
  You do not fetch it: it is rendered into your prompt each turn under
  `==== SHARED CONTEXT ====`. Read it before acting, and publish with `board_write` the moment
                              you establish
  something — `FACT` / `OBSERVED` for what you confirmed, `FAIL` for a hypothesis you
  falsified (the highest-value entry: it stops peers spending budget on it), `PATCH_SUMMARY`
  as `files= | idea= | evidence=` when you fix something, and `CLAIM` while you are working
  so peers pick a different angle. Entries are capped (100 chars, 300 for `PATCH_SUMMARY`);
  put the long version in `detail` and peers `board_unfold` it. Do not re-derive a peer's
  `FACT`, and do not retry something recorded as `FAIL`.