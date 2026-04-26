# GraceKelly Windows Autostart

This folder contains the Windows Task Scheduler artefacts for starting GraceKelly V2 on `127.0.0.1:8011` when the Windows user logs on.

The task runs `D:\GraceKelly\scripts\win-autostart\gracekelly_uvicorn.bat`. The batch file changes to `D:\GraceKelly`, creates `%LOCALAPPDATA%\GraceKelly\` when needed, loads the execution profile, and starts:

```bat
.\.venv\Scripts\python.exe -m uvicorn gracekelly.main:create_app --factory --host 127.0.0.1 --port 8011
```

## Install

1. Open this folder in File Explorer:

   ```bat
   D:\GraceKelly\scripts\win-autostart
   ```

2. Right-click `install_autostart.bat` and choose `Run as administrator`.

3. The installer imports `gracekelly_autostart.xml` as the scheduled task `GraceKelly Autostart`.

The XML ships with placeholder `DOMAIN\USERNAME` and uses `InteractiveToken` (so the import does not ask for the user's password). Before installing, replace **all three** `DOMAIN\USERNAME` occurrences in `gracekelly_autostart.xml` with the value of `whoami` from PowerShell (e.g. `mymachine\myuser`).

Do not run `install_autostart.bat` from this batch process. Installation is an explicit user action because it needs Administrator elevation.

## Execution Profile

Default profile is `dry-run`.

Use `set_profile.bat` to switch profiles without editing `gracekelly_uvicorn.bat`:

```bat
set_profile.bat dry-run
set_profile.bat api-only
set_profile.bat hybrid
```

The helper writes:

```bat
%LOCALAPPDATA%\GraceKelly\profile.env
```

with one line:

```bat
GRACEKELLY_EXECUTION_PROFILE=<value>
```

Restart the scheduled task after changing the profile:

```bat
schtasks /End /TN "GraceKelly Autostart"
schtasks /Run /TN "GraceKelly Autostart"
```

If the task is not running yet, `/End` may report that there is no running instance. In that case, run only `/Run` or log out and log back in.

## Logs

Uvicorn output is appended to:

```bat
%LOCALAPPDATA%\GraceKelly\uvicorn.log
```

Open it with:

```bat
notepad "%LOCALAPPDATA%\GraceKelly\uvicorn.log"
```

## Status

Query the scheduled task:

```bat
schtasks /Query /TN "GraceKelly Autostart" /V /FO LIST
```

Start it manually:

```bat
schtasks /Run /TN "GraceKelly Autostart"
```

Stop it manually:

```bat
schtasks /End /TN "GraceKelly Autostart"
```

## Uninstall

Right-click `uninstall_autostart.bat` and choose `Run as administrator`.

The script runs:

```bat
schtasks /Delete /TN "GraceKelly Autostart" /F
```

## Troubleshooting

### `:8011` already in use

Check the process using the port:

```bat
netstat -ano | findstr :8011
```

If it is an old GraceKelly or uvicorn process, stop the scheduled task:

```bat
schtasks /End /TN "GraceKelly Autostart"
```

Then close the stale process from Task Manager or with `taskkill /PID <pid> /F` after confirming the PID belongs to GraceKelly.

### `python` not in PATH

The task does not use `python` from PATH. It runs:

```bat
D:\GraceKelly\.venv\Scripts\python.exe
```

If startup fails, check that this file exists and that the project virtual environment has the required dependencies installed.

### Task exists but GraceKelly is not responding

Check the task status:

```bat
schtasks /Query /TN "GraceKelly Autostart" /V /FO LIST
```

Then check the log:

```bat
notepad "%LOCALAPPDATA%\GraceKelly\uvicorn.log"
```

You can also run `gracekelly_uvicorn.bat` from a normal Command Prompt to see whether the same startup failure appears in the log.

### Access denied during install or uninstall

Run `install_autostart.bat` or `uninstall_autostart.bat` as Administrator. The runtime directory `%LOCALAPPDATA%\GraceKelly\` is created under the logged-in user's profile and should not need explicit ACL changes.

## Selectors weekly recon (optional)

A second scheduled task captures the live Perplexity DOM and compares it against a stored baseline once a week, so UI drift is detected before it breaks an actual run.

The task runs `gracekelly-recon-weekly` (entry point installed by `pip install -e .[browser]`). Schedule: every **Friday 03:00** local time. Execution time limit: 15 minutes.

### Install

Right-click `install_recon_cron.bat` and choose `Run as administrator`. The script substitutes `%USERDOMAIN%\%USERNAME%` into a rendered copy of `recon-task.xml` and registers it as `GraceKelly Selectors Recon`.

### Uninstall

Right-click `uninstall_recon_cron.bat` and choose `Run as administrator`. The task is removed via `schtasks /Delete`.

### What recon writes

| Artefact | Path | Meaning |
|---|---|---|
| Latest snapshot | `D:\GraceKelly\.workflow\state\perplexity-selectors-latest.json` | Last capture, always overwritten |
| Baseline | `D:\GraceKelly\.workflow\state\perplexity-selectors-baseline.json` | Reference for diff. Created on first run. |
| Drift flag | `D:\GraceKelly\.workflow\state\perplexity-selectors-drift.flag` | Present iff drift was detected on the most recent run |
| Drift log | `D:\GraceKelly\logs\recon-drift.jsonl` | One line per drifted run, JSON `{ts, added, removed, changed}` |

### Acknowledging drift

When the flag is present:

1. Inspect `recon-drift.jsonl` for the structural diff.
2. Decide whether the drift is benign (a new model added, a button renamed) or breaking (a selector path no longer resolves).
3. If breaking — fix the selector module and rerun integration tests.
4. To accept the new state as the baseline:

   ```bat
   copy /Y "D:\GraceKelly\.workflow\state\perplexity-selectors-latest.json" ^
       "D:\GraceKelly\.workflow\state\perplexity-selectors-baseline.json"
   del "D:\GraceKelly\.workflow\state\perplexity-selectors-drift.flag"
   ```

The next scheduled run will exit 0 again until the next drift.

### Manual run

```bat
.\.venv\Scripts\gracekelly-recon-weekly.exe
```

Exits 0 when no drift, 1 when drift is detected, 2 on argument errors.
