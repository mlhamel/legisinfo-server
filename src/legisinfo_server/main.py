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

    import google.protobuf.descriptor

    def descriptor_to_openapi(descriptor, schemas_dict):
        schema_name = descriptor.name
        if schema_name in schemas_dict:
            return {"$ref": f"#/components/schemas/{schema_name}"}
        properties = {}
        schema = {"type": "object", "properties": properties}
        schemas_dict[schema_name] = schema
        for field in descriptor.fields:
            json_name = field.json_name or field.name
            if field.is_repeated:
                field_schema = {"type": "array", "items": get_field_type_schema(field, schemas_dict)}
            else:
                field_schema = get_field_type_schema(field, schemas_dict)
            properties[json_name] = field_schema
        return {"$ref": f"#/components/schemas/{schema_name}"}

    def get_field_type_schema(field, schemas_dict):
        fd = google.protobuf.descriptor.FieldDescriptor
        if field.type == fd.TYPE_DOUBLE or field.type == fd.TYPE_FLOAT:
            return {"type": "number"}
        if field.type in (fd.TYPE_INT64, fd.TYPE_UINT64, fd.TYPE_INT32, fd.TYPE_UINT32, fd.TYPE_SINT32, fd.TYPE_SINT64):
            return {"type": "integer"}
        if field.type == fd.TYPE_BOOL:
            return {"type": "boolean"}
        if field.type == fd.TYPE_STRING:
            return {"type": "string"}
        if field.type == fd.TYPE_BYTES:
            return {"type": "string", "format": "binary"}
        if field.type == fd.TYPE_ENUM:
            enum_name = field.enum_type.name
            if enum_name not in schemas_dict:
                schemas_dict[enum_name] = {
                    "type": "string",
                    "enum": [value.name for value in field.enum_type.values],
                }
            return {"$ref": f"#/components/schemas/{enum_name}"}
        if field.type == fd.TYPE_MESSAGE:
            return descriptor_to_openapi(field.message_type, schemas_dict)
        return {"type": "string"}

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

    schemas_dict = openapi_schema["components"]["schemas"]

    try:
        endpoints = connect_app._endpoints(connect_app._service)
        for path, endpoint in endpoints.items():
            method_info = endpoint.method
            in_ref = descriptor_to_openapi(method_info.input.DESCRIPTOR, schemas_dict)
            out_ref = descriptor_to_openapi(method_info.output.DESCRIPTOR, schemas_dict)

            openapi_schema["paths"][path] = {
                "post": {
                    "tags": [method_info.service_name],
                    "summary": method_info.name,
                    "operationId": method_info.name,
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": in_ref}},
                    },
                    "responses": {
                        "200": {
                            "description": "Successful Response",
                            "content": {"application/json": {"schema": out_ref}},
                        }
                    },
                }
            }
    except Exception as e:
        print(f"Failed to dynamically generate ConnectRPC OpenAPI schema: {e}")  # noqa: T201

    app.openapi_schema = openapi_schema
    return openapi_schema


app.openapi = custom_openapi
