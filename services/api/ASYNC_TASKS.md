# Async tasks with Celery and Redis (DEV-55)

Heavy work no longer runs inside the API request. The API enqueues a task and answers at once
with a `task_id`. A separate worker process does the work.

```
Client -> API (producer) -> Redis (broker) -> Worker (consumer) -> result stored in Redis
```

## Run it

```
docker compose up --build
```

| Service | What it does | Port |
|---|---|---|
| `backend` | FastAPI. Only enqueues tasks and reports their status. | 8000 |
| `worker` | Celery worker, its own container and process. Listens to `default` and `dlq`. | none |
| `redis` | Broker and result backend. | 6379 |
| `flower` | Monitoring page for the queue. | 5555 |

## Endpoints

- `POST /telemetry/report` returns `202 Accepted` with `{"task_id": ..., "status": "pending"}`.
  Optional body: `{"start_date": ..., "end_date": ...}`. The old `GET /telemetry/report` still works.
- `GET /tasks/{task_id}` returns `status` (`pending`, `started`, `success`, `failure`), plus `result` or `error`.
- `GET /tasks/dlq/records` lists the tasks that failed 3 times.

## Reliability rules

- **Light messages.** The task message holds two ISO date strings. The worker loads the data itself.
- **ACK after success.** `task_acks_late=True`: if a worker dies mid-task, the message returns to the queue.
- **Timeouts.** Soft limit 60 s, hard limit 90 s on every task.
- **Retries and DLQ.** A failing task runs 3 times (waits of 2 s, then 4 s). After the third failure it is
  recorded with `task_id`, attempt number and error message in the `dlq` queue (visible in Flower)
  and in the Redis list `dlq:records`.

## Demo a failure

Set `ALLOW_TASK_FAILURE_DEMO=1` in the root `.env`, restart the backend, then:

```
curl -X POST localhost:8000/telemetry/report -H "Content-Type: application/json" -d '{"simulate_failure": true}'
docker compose logs worker --tail 30
curl localhost:8000/tasks/dlq/records
```

Without that variable the flag is rejected with `403`.

## Tests

```
cd services/api && uv run pytest tests/test_tasks.py -q
```

The tests run Celery eagerly and fake Redis, so no containers are needed.
