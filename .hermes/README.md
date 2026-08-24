# Hermes staging layout

The live system must use two independent Hermes homes. The repository copies
are under `.hermes/profiles/cti-analyst` and `.hermes/profiles/cti-maintainer`
so they can be reviewed and versioned before a human installs them.

The old top-level `.hermes/prompts`, `.hermes/skills`, `.hermes/memories`, and
`.hermes/cron` entries are legacy/default staging assets. They are not a
coordination channel and must not be used for scheduled production jobs after
the two profiles are installed. Profile-local assets are authoritative for
scheduled work.

No `.env`, session, log, gateway, or audit runtime state containing secrets may
be committed. Only the checked-in `.env.example` files and empty state
placeholders belong here.
