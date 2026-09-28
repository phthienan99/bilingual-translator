# Historical development note — guard diagnostic update (superseded)

New candidate image: bilingual-translator:parakeet-guard-candidate, running at http://localhost:8005. The previous 8004 app and its history remain unchanged.

Changes: recognizable event clock phrases (including “three fifteen” and “3.15”) are normalized to 3:15 only for translation input. Prices/ordinary decimals are not changed. Empty or rejected final recognition now discards provisional text rather than preserving it as unconfirmed. This can remove real speech when final recognition fails; it deliberately avoids treating unsupported text as confirmed.

21 unit tests passed. Actual model probes of 3:15/3:50, 9:05/9:45 and 12:40/12:14 retained the times in Chinese translation. Source speech is never replaced with a reference answer.

The supplied 39.96-second recording was replayed through the old version. Its six main test sentences were retained; the screenshot's extra Final phrases did not reproduce. Isolated audio cropping can change recognition (one cropped word tail became “Grace”). Therefore spontaneous extra Final captions are NOT fixed or explained. A neural VAD probe was evaluated but NOT added: it also detected speech in some low-energy spans. Do not claim silence safety from these tests. Broader live/noise/quiet-speech validation remains necessary.

Earlier exported Docker TARs and handoff ZIPs predate this update. The current source is in bilingual-translator and guard-candidate-source.zip. No private recordings are included.

> **Status:** Historical development notes retained for traceability. They describe earlier candidate/diagnostic states and are **not** the current submission instructions or release status. Use `README.md`, `SETUP.md`, `PEER_TRIAL.md`, `CONTRIBUTIONS.md`, and the published `v72-web` release as the current record.
