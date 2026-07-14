[![Test](https://github.com/yuukis/yamanashi-event-feed/actions/workflows/test.yml/badge.svg?branch=main&event=push)](https://github.com/yuukis/yamanashi-event-feed/actions/workflows/test.yml)
[![DockerHub](https://github.com/yuukis/yamanashi-event-feed/actions/workflows/dockerhub.yml/badge.svg?branch=main&event=push)](https://github.com/yuukis/yamanashi-event-feed/actions/workflows/dockerhub.yml)
[![DeployToAWS](https://github.com/yuukis/yamanashi-event-feed/actions/workflows/aws-deploy.yml/badge.svg?branch=main&event=push)](https://github.com/yuukis/yamanashi-event-feed/actions/workflows/aws-deploy.yml)

# Yamanashi Event Feed

<!-- ABOUT THE PROJECT -->
## About The Project

This is a small, independent service that republishes recent Yamanashi
tech-event data as an RSS 2.0 feed, so feed readers and Slack/Discord
link-unfurling/RSS integrations can notice new and updated events.

It is part of the [Yamanashi Developer Hub](https://hub.yamanashi.dev)
ecosystem, but ships as its own service rather than a feature of
[yamanashi-event-api](https://github.com/yuukis/yamanashi-event-api):

- Data source: `GET https://api.event.yamanashi.dev/events` (yamanashi-event-api).
  This service only reads from it and never modifies it.
- Every `<item><link>` points at the event's own primary source URL
  (e.g. its connpass page), never at the hub itself — the hub ecosystem's
  policy is to always send traffic to the primary source.
- Items are sorted by `updated_at` descending (not by event date), because
  the point of this feed is "what's new or changed", not "what's upcoming".

This feed is available at the following URL:

https://feed.event.yamanashi.dev/feed.xml

### Tech stack & deployment

Built with Python/FastAPI and deployed as an AWS Lambda function via
AWS SAM + Docker, mirroring `yamanashi-event-api`'s stack so the same
maintainer can operate both services with one set of tooling. This is a
deliberate choice, not a requirement of the RSS format itself — a lighter
deploy target (e.g. Cloudflare Workers, Render) would also work fine, but
consistency with the sibling repo was prioritized instead.

<!-- GETTING STARTED -->
## Getting Started

### Prerequisites

* Python 3.10 or later

### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/yuukis/yamanashi-event-feed.git
   ```
2. Install Python packages
   ```sh
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and adjust as needed
   ```ini
   UPSTREAM_API_URL=https://api.event.yamanashi.dev
   HUB_BASE_URL=https://hub.yamanashi.dev
   MAX_ITEMS=30
   CACHE_TTL_SECONDS=300
   ```
4. Run the app
   ```sh
   uvicorn app.main:app --reload
   ```
5. Access http://localhost:8000/feed.xml

### Docker Compose Installation

1. Clone the repo
   ```sh
   git clone https://github.com/yuukis/yamanashi-event-feed.git
   ```
2. Build and run the Docker services
   ```sh
   docker-compose up --build
   ```
3. Access http://localhost:8000/feed.xml

<!-- USAGE EXAMPLES -->
## Usage

### `GET /feed.xml` (also served at `GET /`)

Returns an RSS 2.0 document (`Content-Type: application/rss+xml; charset=utf-8`)
listing the most recently updated events, newest first, capped at
`MAX_ITEMS` (default 30).

- `<title>`: the event's title, with `(group_name)` appended when the
  event has an associated community.
- `<link>`: the event's own `event_url` (primary source), never the hub.
- `<guid isPermaLink="false">`: the event's `uid`.
- `<pubDate>`: the event's `updated_at`.
- `<description>`: `description`, falling back to `catch`, falling back
  to empty. HTML in `description` is entity-escaped, not wrapped in CDATA.
- `<category>`: one per keyword, if any.

Supports conditional GET (`If-Modified-Since` / `Last-Modified` / `304`)
so feed readers can poll cheaply.

Upstream responses are cached in-memory for `CACHE_TTL_SECONDS` (default
300s) to avoid hammering `yamanashi-event-api` on every request.

### `GET /{group_key}/feed.xml`

Same item shape as `GET /feed.xml`, scoped to a single community group.

- Channel `<title>`/`<link>`/`<description>` come from the upstream
  `GET /groups/{group_key}` (`yamanashi-event-api`), falling back to a
  generated description when the group has none set.
- Items come from `GET /groups/{group_key}/events`, covering the group's
  full history (not just the ~90-day window `/feed.xml` uses), sorted by
  `updated_at` descending and capped at `MAX_ITEMS`, same as `/feed.xml`.
- Returns `404` if `group_key` doesn't match a known group.

Also supports conditional GET, and is cached in-memory per `group_key`
the same way as `/feed.xml`.

### Environment variables

| Name                 | Default                             | Description                                   |
|----------------------|--------------------------------------|------------------------------------------------|
| `UPSTREAM_API_URL`   | `https://api.event.yamanashi.dev`    | Base URL of the upstream event API            |
| `HUB_BASE_URL`       | `https://hub.yamanashi.dev`          | Base URL used for the feed's channel `<link>`  |
| `MAX_ITEMS`          | `30`                                  | Max number of items in the feed               |
| `CACHE_TTL_SECONDS`  | `300`                                 | In-memory cache TTL for upstream responses    |

<!-- TESTING -->
## Testing

```sh
pytest
```

<!-- DEPLOYMENT -->
## Deployment

Deployed as an AWS Lambda function behind API Gateway via AWS SAM
(`template.yml`), matching `yamanashi-event-api`'s deployment approach:

```sh
sam build
sam deploy --guided
```

The `feed.event.yamanashi.dev` DNS record and the `Test`/`DockerHub`/
`DeployToAWS` GitHub Actions workflows follow the same pattern as
`yamanashi-event-api` (they no-op if the required secrets aren't
configured on the repo).

<!-- LICENSE -->
## License

Distributed under the Apache License 2.0. See `LICENSE` for more information.
