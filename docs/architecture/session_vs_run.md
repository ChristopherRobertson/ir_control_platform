# Session Vs Run

## Session
A session is the user-defined experimental context created before acquisition and capable of containing multiple runs.

Required session fields:

- experiment type, fixed in v1 to generic single-wavelength pump-probe
- session name or session ID
- operator
- sample ID or sample name
- sample notes
- experiment notes
- created timestamp
- updated timestamp

Wavelength is not a session field.

Timescale is not a session field.

## Run
A run is one acquisition executed inside a session using a specific immutable settings snapshot.

Required run fields:

- run name or run number
- run notes
- session foreign key or reference
- exact configuration snapshot used for the run
- timescale regime
- probe settings
- pump settings
- lock-in settings
- raw data
- processed data
- start timestamp
- end timestamp
- completion status
- fault/error state if aborted or failed

The run settings snapshot is frozen when Run starts. Later edits to session metadata do not mutate the snapshot used for an acquisition.

## Persistence
The data-pipeline owns session and run persistence. UI state is never the authoritative store of session truth, run truth, raw data, processed data, or exports.
