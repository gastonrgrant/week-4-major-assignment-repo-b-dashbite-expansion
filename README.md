# DashBite

## Project overview

This is Option 1. DashBite predicts whether a food-delivery order will be late. Each raw order has `order_id`, `timestamp`, `distance_km`, `prep_minutes`, `order_value`, and `was_late`.

Five programs run separately and do not import each other. They hand off only through files:

- The simulator writes order files.
- Preprocess drops invalid rows and writes feature files. It keeps `was_late`.
- Train fits a logistic regression on `distance_km` and `prep_minutes`, then publishes the next versioned checkpoint.
- Infer reads the newest checkpoint on disk and scores new feature files. It keeps scoring if training is not running.
- Model Pulse is a Streamlit page. It only reads files already on disk: how many orders arrived, what share were flagged late, and which fields failed cleaning.

The Makefile is the way to install, run, and test. In containers, the same five programs share one data volume. `DASHBITE_DATA_ROOT` is the only path setting.

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

## How the work was verified personally

I ran the smoke test above myself on 2026-09-28, in a terminal, separate from the tester chat.

## How the Tester checked the work

The tester's final gates were 43 passed from `make test` on the host and 43 passed from `make docker-test` on Python 3.11.16 inside `dashbite:local`. With `POLL_INTERVAL_SECONDS=60`, `docker compose stop -t 15 simulator` logged `simulator stopped` and the container exited 0. The Smoke test section is that separate run.

## Recommendations

The tester recommended four new tests. I accepted three: the health command exits 0 on a fresh heartbeat and 1 when the file is missing or older than 45 seconds in order to lock the signal Docker uses; peak hours stay on at 11, 13, 17, and 20 and off at 10, 14, 16, and 21 in order to make sure the correct hours were being labeled as peak; a batch of only on-time rows publishes no checkpoint. I rejected the messy-row test, because the test suite already covers messy data.

The builder recommended leaving the 45-second heartbeat rule as it is. I agreed. A 15-second poll stays inside that limit, so the cutoff did not need to follow the poll.

## Roles

The architect chat reviewed Stage 7 against the containers already in the repo and revised only that section. The plan now says Docker's `SIGTERM` reaches the worker because the entrypoint uses `exec setpriv`, and the smoke test proves `simulator stopped` and exit 0. One simulator stop covers preprocess, train, and infer. That chat did not change code.

The builder chat found the container stack already in place. It changed the entrypoint from `runuser` to `setpriv` so Docker's SIGTERM reaches the worker, which then finishes the current pass and exits. `make test` and `make docker-test` each passed 40 tests. That chat did not rerun the Stage 7 smoke after the fix.

The tester chat checked Stage 7 against the plan, ran the checks in **How the Tester checked the work**, and added the three tests from **Recommendations** as Stage 9.

The chats are committed as `docs/transcripts/architect.txt`, `docs/transcripts/builder.txt`, and `docs/transcripts/tester.txt`. The same files are also saved as `grg27_architect.txt`, `grg27_builder.txt`, and `grg27_tester.txt`
