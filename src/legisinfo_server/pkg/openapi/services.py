import logging
from typing import Any

import google.protobuf.descriptor
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from legisinfo_server.pkg.base import BaseService


class GenerateOpenAPISchemaService(BaseService[dict[str, Any]]):
    def __init__(self, app: FastAPI, connect_app: Any):
        self.app = app
        self.connect_app = connect_app

    async def perform(self) -> dict[str, Any]:
        openapi_schema = get_openapi(
            title=self.app.title,
            version=self.app.version,
            description=self.app.description,
            routes=self.app.routes,
        )

        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
        if "schemas" not in openapi_schema["components"]:
            openapi_schema["components"]["schemas"] = {}

        schemas_dict = openapi_schema["components"]["schemas"]

        try:
            endpoints = self.connect_app._endpoints(self.connect_app._service)
            for path, endpoint in endpoints.items():
                method_info = endpoint.method
                in_ref = self._descriptor_to_openapi(method_info.input.DESCRIPTOR, schemas_dict)
                out_ref = self._descriptor_to_openapi(method_info.output.DESCRIPTOR, schemas_dict)

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
            logging.getLogger("uvicorn.error").error(f"Failed to dynamically generate ConnectRPC OpenAPI schema: {e}")

        return openapi_schema

    def _descriptor_to_openapi(self, descriptor: Any, schemas_dict: dict[str, Any]) -> dict[str, Any]:
        schema_name = descriptor.name
        if schema_name in schemas_dict:
            return {"$ref": f"#/components/schemas/{schema_name}"}
        properties = {}
        schema = {"type": "object", "properties": properties}
        schemas_dict[schema_name] = schema
        for field in descriptor.fields:
            json_name = field.json_name or field.name
            if field.is_repeated:
                field_schema = {"type": "array", "items": self._get_field_type_schema(field, schemas_dict)}
            else:
                field_schema = self._get_field_type_schema(field, schemas_dict)
            properties[json_name] = field_schema
        return {"$ref": f"#/components/schemas/{schema_name}"}

    def _get_field_type_schema(self, field: Any, schemas_dict: dict[str, Any]) -> dict[str, Any]:
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
            return self._descriptor_to_openapi(field.message_type, schemas_dict)
        return {"type": "string"}
