# D&D v26 — Producer Alias & Filename Parser Update

## Producer aliases

The importer and producer resolver now treat these as the same producer:

### SLV
- `@prod.slv`
- `@prod_slv`
- `@quikinnnslv`
- `slv`
- `SLV`
- `@slv`

### DE PLUG
- `de plug`
- `de plugg`
- `@deplugboy`
- `@de_plug`
- `@deplug`
- `deplug`

### DADDY KAR
- `daddy kar`
- `daddykar`
- `@daddykar`
- `@daddykar_official`

## Filename parsing

When BPM/key are recognized, they are removed from the suggested beat title while the BPM/key fields are populated and remain editable.

Known producer credit blocks are also removed from the suggested title. Examples:

`SLV & DE PLUG - HIT (143Bpm Cmin).mp3` → `HIT`, BPM `143`, Key `C minor`

`@prod.slv @deplugboy - MANSION (146Bpm Emin).mp3` → `MANSION`, BPM `146`, Key `E minor`

## Account display

The backend identity can remain `slv1` for compatibility, but all user-facing producer labels now display as **SLV**. Beat producer fields also show the canonical label.
