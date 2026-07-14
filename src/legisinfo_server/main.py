import os
import sys

from connectrpc.compat import google_protobuf_codecs
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.routing import Mount

# Add gen directory to python path to resolve proto.* imports
sys.path.append(os.path.join(os.path.dirname(__file__), "gen"))

from legisinfo_server.reader import LegisinfoReader
from legisinfo_server.services import LegisinfoServiceImpl
from proto.legisinfo.v1.legisinfo_connect import LegisinfoServiceASGIApplication

# 1. Load configuration from environment variables
DATA_PATH = os.environ.get("LEGISINFO_DATA_PATH", "/data")

# 2. Initialize data reader and RPC servicer
reader = LegisinfoReader(DATA_PATH)
servicer = LegisinfoServiceImpl(reader)


# 3. Create ConnectRPC ASGI app wrapper
connect_app = LegisinfoServiceASGIApplication(servicer, codecs=google_protobuf_codecs())

# 4. Instantiate FastAPI
app = FastAPI(
    title="LEGISinfo ConnectRPC API Server",
    description="ConnectRPC (protobuf) API for querying parliament bills and stages texts.",
    version="0.1.0",
)

# 5. Enable CORS for web browser clients (crucial for gRPC-Web and Connect protocols)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 6. Mount ConnectRPC service endpoints
app.routes.append(Mount(connect_app.path, app=connect_app))


# 7. Add standard health checking routes
@app.get("/", tags=["system"])
def root():
    return {
        "message": "Welcome to LEGISinfo API Server",
        "data_path": DATA_PATH,
        "connect_endpoints": f"{connect_app.path}*",
    }


@app.get("/health", tags=["system"])
def health():
    # Basic check to see if the data directory exists
    dir_exists = os.path.exists(DATA_PATH)
    sessions = reader.get_sessions() if dir_exists else []
    return {
        "status": "healthy" if dir_exists else "degraded",
        "data_directory_configured": dir_exists,
        "available_sessions_count": len(sessions),
    }


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "schemas" not in openapi_schema["components"]:
        openapi_schema["components"]["schemas"] = {}

    schemas = {
        "ListSessionsRequest": {
            "type": "object",
            "properties": {},
            "description": "Empty request body to list available sessions.",
        },
        "ListSessionsResponse": {
            "type": "object",
            "properties": {
                "sessions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of session identifiers (e.g. '45-1').",
                }
            },
        },
        "Chamber": {
            "type": "string",
            "enum": ["CHAMBER_UNSPECIFIED", "CHAMBER_HOUSE", "CHAMBER_SENATE"],
            "description": "Parliamentary chamber filter.",
        },
        "BillFilters": {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "Session code (e.g. '45-1')."},
                "chamber": {"$ref": "#/components/schemas/Chamber"},
                "sponsor": {"type": "string", "description": "Sponsor name search substring."},
                "sponsorAffiliation": {"type": "string", "description": "Sponsor title or party."},
                "status": {"type": "string", "description": "Bill status filter."},
                "latestActivity": {"type": "string", "description": "Latest stage activity filter."},
                "number": {"type": "string", "description": "Bill number filter (e.g. 'C-11')."},
                "dateAfter": {
                    "type": "string",
                    "format": "date",
                    "description": "Filter bills updated after this date.",
                },
                "dateBefore": {
                    "type": "string",
                    "format": "date",
                    "description": "Filter bills updated before this date.",
                },
                "searchQuery": {"type": "string", "description": "Full-text search query across fields."},
                "hasText": {"type": "boolean", "description": "Filter by whether bill text is scraped."},
                "committeeOnly": {"type": "boolean", "description": "Filter for bills in committee stage."},
            },
        },
        "SortField": {
            "type": "string",
            "enum": [
                "SORT_FIELD_UNSPECIFIED",
                "SORT_FIELD_LATEST_EVENT_DATE",
                "SORT_FIELD_NUMBER",
                "SORT_FIELD_SPONSOR",
                "SORT_FIELD_STATUS",
                "SORT_FIELD_TITLE",
            ],
        },
        "SortDirection": {
            "type": "string",
            "enum": ["SORT_DIRECTION_UNSPECIFIED", "SORT_DIRECTION_DESC", "SORT_DIRECTION_ASC"],
        },
        "ListBillsRequest": {
            "type": "object",
            "properties": {
                "filters": {"$ref": "#/components/schemas/BillFilters"},
                "sortField": {"$ref": "#/components/schemas/SortField"},
                "sortDirection": {"$ref": "#/components/schemas/SortDirection"},
                "limit": {"type": "integer", "default": 20, "description": "Max number of bills to return."},
                "offset": {"type": "integer", "default": 0, "description": "Offset index for pagination."},
            },
        },
        "BillSummary": {
            "type": "object",
            "properties": {
                "number": {"type": "string"},
                "session": {"type": "string"},
                "titleEn": {"type": "string"},
                "titleFr": {"type": "string"},
                "sponsorName": {"type": "string"},
                "status": {"type": "string"},
                "latestEventDate": {"type": "string", "format": "date-time"},
            },
        },
        "ListBillsResponse": {
            "type": "object",
            "properties": {
                "bills": {"type": "array", "items": {"$ref": "#/components/schemas/BillSummary"}},
                "totalCount": {"type": "integer"},
            },
        },
        "GetBillRequest": {
            "type": "object",
            "required": ["session", "billNumber"],
            "properties": {
                "session": {"type": "string", "description": "Session code (e.g. '45-1')."},
                "billNumber": {"type": "string", "description": "Bill number (e.g. 'C-11')."},
            },
        },
        "BillStage": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "name": {"type": "string"},
                "date": {"type": "string", "format": "date-time"},
                "sourceType": {"type": "string"},
            },
        },
        "BillDetail": {
            "type": "object",
            "properties": {
                "number": {"type": "string"},
                "session": {"type": "string"},
                "titleEn": {"type": "string"},
                "titleFr": {"type": "string"},
                "sponsorName": {"type": "string"},
                "sponsorEmail": {"type": "string"},
                "status": {"type": "string"},
                "latestEventDate": {"type": "string", "format": "date-time"},
                "stages": {"type": "array", "items": {"$ref": "#/components/schemas/BillStage"}},
            },
        },
        "GetBillResponse": {"type": "object", "properties": {"bill": {"$ref": "#/components/schemas/BillDetail"}}},
        "GetBillTextRequestFormat": {"type": "string", "enum": ["FORMAT_UNSPECIFIED", "FORMAT_XML", "FORMAT_MARKDOWN"]},
        "GetBillTextRequest": {
            "type": "object",
            "required": ["session", "billNumber"],
            "properties": {
                "session": {"type": "string"},
                "billNumber": {"type": "string"},
                "stageSlug": {"type": "string", "description": "Specific stage slug (optional, defaults to latest)."},
                "format": {"$ref": "#/components/schemas/GetBillTextRequestFormat"},
            },
        },
        "GetBillTextResponse": {
            "type": "object",
            "properties": {
                "billNumber": {"type": "string"},
                "session": {"type": "string"},
                "stageSlug": {"type": "string"},
                "content": {"type": "string"},
                "format": {"type": "string"},
            },
        },
    }

    openapi_schema["components"]["schemas"].update(schemas)

    paths = {
        "/legisinfo.v1.LegisinfoService/ListSessions": {
            "post": {
                "tags": ["LegisinfoService (ConnectRPC)"],
                "summary": "List available scraped sessions",
                "operationId": "ListSessions",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ListSessionsRequest"}}},
                },
                "responses": {
                    "200": {
                        "description": "Success response",
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/ListSessionsResponse"}}
                        },
                    }
                },
            }
        },
        "/legisinfo.v1.LegisinfoService/ListBills": {
            "post": {
                "tags": ["LegisinfoService (ConnectRPC)"],
                "summary": "List and filter bills",
                "operationId": "ListBills",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ListBillsRequest"}}},
                },
                "responses": {
                    "200": {
                        "description": "Success response",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ListBillsResponse"}}},
                    }
                },
            }
        },
        "/legisinfo.v1.LegisinfoService/GetBill": {
            "post": {
                "tags": ["LegisinfoService (ConnectRPC)"],
                "summary": "Get detailed information for a specific bill",
                "operationId": "GetBill",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/GetBillRequest"}}},
                },
                "responses": {
                    "200": {
                        "description": "Success response",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/GetBillResponse"}}},
                    }
                },
            }
        },
        "/legisinfo.v1.LegisinfoService/GetBillText": {
            "post": {
                "tags": ["LegisinfoService (ConnectRPC)"],
                "summary": "Get the text content of a bill stage",
                "operationId": "GetBillText",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/GetBillTextRequest"}}},
                },
                "responses": {
                    "200": {
                        "description": "Success response",
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/GetBillTextResponse"}}
                        },
                    }
                },
            }
        },
    }

    openapi_schema["paths"].update(paths)
    app.openapi_schema = openapi_schema
    return openapi_schema


app.openapi = custom_openapi
