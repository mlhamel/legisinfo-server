import os
import sys

from connectrpc.compat import google_protobuf_codecs
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Mount

# Add gen directory to python path to resolve proto.* imports
sys.path.append(os.path.join(os.path.dirname(__file__), "gen"))

from legisinfo_server.pkg.openapi.services import GenerateOpenAPISchemaService
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

    service = GenerateOpenAPISchemaService(app, connect_app)
    coro = service.perform()
    try:
        # Since perform is CPU-bound (no awaits on I/O), we can run the coroutine
        # synchronously on this thread by calling coro.send(None)
        coro.send(None)
    except StopIteration as e:
        app.openapi_schema = e.value
        return e.value

    # Fallback to asyncio.run if it yields control unexpectedly
    import asyncio

    try:
        asyncio.get_running_loop()
        return app.openapi_schema
    except RuntimeError:
        res = asyncio.run(coro)
        app.openapi_schema = res
        return res


app.openapi = custom_openapi
