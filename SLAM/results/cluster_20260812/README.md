# Cluster result subset — 2026-08-12

This directory contains a small, reviewable subset of the verified `SERVER-113` run. Large raw GPUWattch logs, HotSpot traces, generated process directories and third-party binaries are intentionally excluded.

## Execution

- Static TriFold-3D v2, full SLAM aggregate, two rounds: both returned status 0.
- Cycle counts: 36,051,220 and 36,017,916; relative difference 0.092465%.
- Detailed 3D thermal trace: 4,365 rows.
- Average package power: 57.7747995 W.
- Raw trace peak: 732.990248 W. This is retained for traceability but is not a credible target-chip peak because the run used an approximate GTX480 GPUWattch XML.
- Steady maximum: 72.71 °C at `t2_gpu_control`.
- Transient maximum: 84.05 °C at `t2_gpu_control`.
- Last transient row maximum: 73.73 °C at `t0_hbm_system`.

`bench.txt` is the message-event input to PopNet and `delayInfo.txt` is the resulting delay table. `model_assumptions.json` explicitly separates measured inputs from engineering assumptions.
