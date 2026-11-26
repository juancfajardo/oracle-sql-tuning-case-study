| Case | Before | After | Speed-up | Logical reads (before -> after) | Same result |
|---|---:|---:|---:|---:|:---:|
| Monthly sales report (per report) | 286 ms | 25 ms | 12x | 11,014 -> 937 | yes |
| Customer order lookup (API call) (per lookup) | 78 ms | 0.31 ms | 254x | 11,014 -> 27 | yes |
| Bulk price upload (per file) | 1 min 26 s | 91 ms | 940x | 32,913,638 -> 38,556 | yes |

Double submission test (two sessions load the same file at the same time):

| Version | Duplicate product/date keys | Rows in price list |
|---|---:|---:|
| Before | 7 | 209,095 |
| After | 0 | 209,088 |

Environment: Oracle AI Database 26ai Free Release 23.26.4.0.0; python-oracledb 26.2.0 (thin), Python 3.12.16; GitHub Actions ubuntu-latest runner, Oracle Database Free in a service container.
Data: 100,000 customers, 2,000,000 orders, 200,000 prices, 20,000-line upload file.
Method: median of repeated runs after one warm-up run (warm buffer cache); logical reads from V$MYSTAT 'session logical reads'. Generated 2026-11-26T06:51:31+00:00.
