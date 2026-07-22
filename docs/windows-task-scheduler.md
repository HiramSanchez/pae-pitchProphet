# Windows Task Scheduler

Create a task that runs whether the user is logged in or not and uses the
repository root as **Start in**. Configure the program and arguments with
absolute paths, for example:

```text
Program: C:\path\to\PitchProphet\.venv\Scripts\python.exe
Arguments: -m scripts.run_automated_update --source-file C:\data\matches.json --source-name scheduled-file --max-attempts 3 --retry-delay 10 --log-file C:\logs\pitchprophet.jsonl
Start in: C:\path\to\PitchProphet
```

Recommended settings:

- run on a fixed schedule after the expected source update;
- do not start a second instance while one is running;
- retry the task only after the command itself has exhausted its retries;
- treat exit code `0` as success and `1` as failure;
- run under an account that can read the source and write the database/log;
- never place credentials in command-line arguments or log paths.

Each internal attempt creates its own `update_runs` audit row when the schema
is available. Functional changes are transactional and safe to retry. Review
both the JSON log lines and `update_runs` when the command returns `1`.
