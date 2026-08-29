# D&D v15 — Google Drive import repair

## Fixed
- Google Drive sync no longer trusts the local import registry as proof that a beat exists in D&D.
- Old records that were marked as processed but were never actually imported are retried.
- Existing beats are matched by Google Drive file ID and repaired in place.
- BPM/key are parsed from formats such as `140Bpm Bmin`, `147bpm Fmaj`, `150 BPM F#min`.
- Producer aliases are parsed from filenames, including:
  - `SLV`, `@prod_slv`, `@quikinnnslv`, `@slv1`
  - `@deplugboy`, `DE PLUG`
  - `@daddykar_official`, `DADDY KAR`
- Producer handles are removed from the visible beat title.
- Existing imported beats can be updated from their Drive filename during sync.
- Sync dialog now reports Imported / Updated / Skipped / Failed separately.

## Expected result
For a folder containing 121 audio files, the next manual Sync should no longer report `Imported: 0 / Skipped: 121` just because an old registry entry exists. Existing records are repaired, and genuinely missing files are imported.
