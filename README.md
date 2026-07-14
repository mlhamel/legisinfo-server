# LEGISinfo ConnectRPC API Server

A standalone, high-performance web server built with **FastAPI** and **ConnectRPC** (using Protocol Buffers) to serve bill metadata and full texts scraped by [legisinfo-scraper](https://github.com/mlhamel/legisinfo-scraper).

---

## 🚀 Features

*   **FastAPI Engine:** Built on ASGI with fully asynchronous handlers.
*   **ConnectRPC / Protobuf Core:** Full type safety, schema-first design, and native support for three protocols on a single port:
    *   **Connect:** Lightweight JSON/HTTP protocol compatible with `curl` and standard HTTP clients.
    *   **gRPC:** High-performance, binary protocol for backend microservices.
    *   **gRPC-Web:** Browser-compatible protocol for frontend applications.
*   **Rich Querying:** Advanced filters (by status, sponsor, date range, chamber, etc.) and flexible sorting options.
*   **No Database Overhead:** Serves data directly from the scraped filesystem.
*   **Docker Containerized:** Multi-stage Docker build ready for container deployment.

---

## 🛠️ Getting Started

### Prerequisites

*   Python 3.11+
*   [uv](https://github.com/astral-sh/uv) (recommended) or `pip`
*   [buf](https://buf.build/) CLI

### 1. Installation

Set up the virtual environment and install packages in editable mode:

```bash
make install
```

### 2. Generate Code

Compile the Protobuf files inside `proto/` using `buf`:

```bash
make generate
```

This generates python stubs and connect service definitions under `src/legisinfo_server/gen/`.

### 3. Run Locally

Start the development server with hot reload:

```bash
make run LEGISINFO_DATA_PATH=../legisinfo
```

Your API is now running at `http://localhost:8000`. You can access the standard HTTP health check endpoint at `http://localhost:8000/health`.

---

## 🧪 Filtering & Sorting Capabilities

The server implements robust filtering and sorting options defined in the protobuf schema `ListBillsRequest`:

### Filters
*   `session` (string): Parliament & Session code (e.g. `45-1`).
*   `chamber` (Chamber enum): `CHAMBER_HOUSE` or `CHAMBER_SENATE`.
*   `sponsor` (string): Case-insensitive substring match of sponsor's name.
*   `sponsor_affiliation` (string): Filter by sponsor's title or affiliation.
*   `status` (string): Filter by the current status (e.g. `Royal Assent`).
*   `latest_activity` (string): Filter by the last event type.
*   `number` (string): Filter by bill number (e.g. `C-11`).
*   `date_after` / `date_before` (string): ISO-8601 strings (e.g., `2026-01-01`).
*   `search_query` (string): Performs a text search across bill titles, status, sponsor, and numbers.
*   `has_text` (bool): Filter by whether the bill text document has been scraped.
*   `committee_only` (bool): Filter for bills currently under consideration by a committee.

### Sorting
*   `sort_field` (SortField enum):
    *   `SORT_FIELD_LATEST_EVENT_DATE` (Default)
    *   `SORT_FIELD_NUMBER` (Sorted alphabetically and numerically, e.g. `C-2` before `C-10`)
    *   `SORT_FIELD_SPONSOR`
    *   `SORT_FIELD_STATUS`
    *   `SORT_FIELD_TITLE`
*   `sort_direction` (SortDirection enum):
    *   `SORT_DIRECTION_DESC` (Default for dates)
    *   `SORT_DIRECTION_ASC` (Default for text fields)

---

## 🐳 Docker Deployment

The server is packaged with a multi-stage Docker build that runs code generation automatically and outputs a minimal container image.

### Running with Docker Compose

Mount your scraped data folder and launch the container:

```bash
# Update the volume mapping in docker-compose.yml if your scraped data is elsewhere
make docker-up
```

The container listens on port `8000` and mounts the local scraped data folder into the container's `/data` volume.

---

## 📜 License

MIT License.
