# Research dependencies and provenance

**Surface Elo formulas and defaults** (K-factor with experience decay, shrinkage between overall and surface ratings) are adapted from Sam Coenen's `coenensam/tennis-match-predictor` at commit `f548d978e09b3ef1a0783a1d315ec1fce1b6f70f`. The upstream *software* license is MIT (Copyright © 2026 Sam Coenen; see https://github.com/coenensam/tennis-match-predictor/blob/main/LICENSE). Our day-batched replay, historical input parser, and independent calibration code are modifications/implementations in this project. Use the upstream project's LICENSE terms when incorporating substantial portions of that code.

**No third-party historical data is redistributed.** Historical workbook odds belong to their respective data owners; tennis-data.co.uk states copyright over its spreadsheet files. The Jeff Sackmann original match archive uses CC BY-NC-SA 4.0 when accessed from archives. Do not assume that a MIT software license confers data redistribution or commercialization rights.

Current project release is research-only, no sportsbook execution, live odds integration, or certified positive EV.
