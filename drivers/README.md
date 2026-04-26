# drivers

Typed device boundaries for real and simulated hardware adapters.

- Owns: base driver contracts plus the device interfaces needed by the v1 single-wavelength vertical slice.
- Depends on: `contracts`, `platform`.
- Must not own cross-device orchestration or persistence.

The MIRcat public driver surface is single-wavelength only. It accepts
`ProbeSettings` for one target wavenumber and exposes no sweep, step-measure,
multispectral, wavelength-list, queued scan, or spectral mode API in v1.
