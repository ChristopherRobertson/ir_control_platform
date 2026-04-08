# data-pipeline

Session creation, artifact registration, and replay boundaries.

- Owns: session writer, artifact registry, and reopen/replay protocols.
- Depends on: `contracts`.
- Must remain the authoritative persistence boundary.
