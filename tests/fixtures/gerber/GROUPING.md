# Gerber Sample Grouping

This file records the initial auto-grouping for fixture ZIPs.

- case_001_basic/input
  - Gerber_ST-LINK-V2-1_ST-LINK-V2-1_2026-02-22.zip
  - Test_deepseek.zip

- case_002_no_outline/input
  - Test_deepseek_no_outline.zip (derived from Test_deepseek.zip by removing GKO/outline entries)

- case_003_qfn/input
  - Test_MCU_PCB.zip
  - Test_Camera.zip

- case_004_zip_input/input
  - Test_mini_电吉他.zip

- case_005_large_board/input
  - Test_BIG_PCB.zip
  - Test_all_in_one.zip

Notes:

- Source ZIPs are kept in tests/fixtures/gerber root to avoid data loss.
- Current grouping is heuristic and can be adjusted after first pipeline runs.
