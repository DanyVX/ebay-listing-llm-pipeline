# Development environment discovery (2026-10-10)

Observed isolated authoring sandbox (not the user's PC):

| Check | Value |
|---|---|
| OS / shell | Linux x86_64 / bash |
| Python | 3.13.5 |
| uv / pip | uv 0.10.0 / pip 25.1.1 |
| GPU / CUDA | None detected |
| RAM | 5.8 GiB |
| Free disk | ~30 GB |
| Internet | DNS not available from execution container |
| Docker | Not installed |
| ffmpeg | /usr/bin/ffmpeg |
| Git identity | Not set in sandbox (GitHub connector attributed to account) |

Default tests and CLI must work without GPU and without network after dependency installation. Large model runs are deferred; Colab/Kaggle/cloud GPU setup will be documented only if a later milestone needs it. Benchmark metadata must always be captured at execution time, not copied from this file.
