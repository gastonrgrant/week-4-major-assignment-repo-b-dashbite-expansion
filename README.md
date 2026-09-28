# DashBite

Option 1. DashBite predicts whether a food-delivery order will be late. The simulator writes raw orders, preprocess cleans them, train publishes a versioned checkpoint, and infer scores new rows from the newest checkpoint on disk. Model Pulse is a Streamlit page that only reads those files.

Stages do not import each other. They hand off through folders under the data root. The Makefile is the way to install, run, and test.

## Install

```bash
make install
```

That creates `.venv` and installs the project with its dev extra.

## Run

Containers:

```bash
make docker-up
```

Dashboard: http://127.0.0.1:8501

`make docker-up` builds one image and starts `simulator`, `preprocess`, `train`, `infer`, and `dashboard`. They share a named volume mounted at `/data`. Compose sets `DASHBITE_DATA_ROOT=/data`. Defaults are `POLL_INTERVAL_SECONDS=15` and `TRAIN_EVERY_N_EVENTS=2000`. Override either in the environment before `make docker-up`. Stop with `make docker-down`. That removes the containers and keeps the volume.

The image starts as root only long enough to create `/data` and give it to the `dashbite` user. The service command then replaces that process, so Docker's SIGTERM reaches the worker. The worker finishes its current pass and exits. Each pass touches a heartbeat file; Compose marks the service unhealthy when that file is stale. The dashboard health check calls Streamlit's `/_stcore/health`.

Same pipeline without Docker:

```bash
make run
```

Model Pulse: http://localhost:8501. Stop with `make stop`.

## Test

```bash
make test
make docker-test
```

`make test` is the local pytest gate. `make docker-test` runs the same suite in the image and does not start the long-running services. The image used by `make docker-test` is the one from the last build; `make docker-up` rebuilds it.

## Smoke test

Checked on 2026-09-28 from the DashBite folder.

`make install` finished with `Successfully installed dashbite-0.1.0`.

`make docker-up` built `dashbite:local` and started `simulator`, `preprocess`, `train`, `infer`, and `dashboard`. `docker compose ps` showed all five healthy. The dashboard was published at `0.0.0.0:8501`.

`curl -fsS http://127.0.0.1:8501/_stcore/health` printed `ok`.

The simulator log recorded `new orders arrived: 50 rows` for:

- `orders-20260928T192757-8253184c.csv`
- `orders-20260928T192812-edc0b91c.csv`

`/data/raw` listed those files. `/data/features` listed the cleaned copy of `orders-20260928T192757-8253184c.csv`.

`make docker-down` removed all five containers. `docker compose ps` showed nothing running. The volume `dashbite_dashbite-data` was still present.

## How the work was checked

The tester's final gates were 43 passed from `make test` on the host and 43 passed from `make docker-test` on Python 3.11.16 inside `dashbite:local`. With `POLL_INTERVAL_SECONDS=60`, `docker compose stop -t 15 simulator` logged `simulator stopped` and the container exited 0. The smoke test section above is a separate run from the DashBite folder.

## Recommendations

Accepted: keep `DASHBITE_DATA_ROOT` as the only path setting and mount the named volume at `/data`. Compose points the existing variable at the volume.

Rejected: replace the file handoff with a queue or a database. The stages still meet only through files on the shared volume.

Rejected: leave `runuser` in front of the service command. It receives Docker's SIGTERM and kills the session before the worker finishes the current pass. The entrypoint uses `setpriv` so the worker is the process that handles the signal.

## Roles

The architect chat confirmed Stage 7 was already in `docs/plan.md` and did not add a second copy or implement the containers. In that same chat it appended Stage 8 and implemented the training cursor and full refit. That stage's smoke published `late_v021.joblib`.

The builder chat found the container stack already in place. It changed the entrypoint from `runuser` to `setpriv` so Docker's SIGTERM reaches the worker, which then finishes the current pass and exits. `make test` and `make docker-test` each passed 40 tests. That chat did not rerun the Stage 7 smoke after the fix.

The tester chat checked Stage 7 against the plan. `make docker-up` started all five services healthy, the dashboard health URL printed `ok`, and the simulator log showed a new order file. With a 60-second poll, `docker compose stop -t 15 simulator` logged `simulator stopped` and exited 0. The tester then added three tests as Stage 9. The final gates were 43 passed on the host and 43 passed in the container.

The chats are committed as `docs/transcripts/architect.txt`, `docs/transcripts/builder.txt`, and `docs/transcripts/tester.txt`. The same files are also saved as `grg27_architect.txt`, `grg27_builder.txt`, and `grg27_tester.txt`. Upload those three chats to Canvas separately.
