from typing import Any

import pytest
from fastapi import FastAPI

from legisinfo_server.pkg.openapi.services import GenerateOpenAPISchemaService


class MockMethodInfo:
    def __init__(self, name: str, service_name: str, input_class: Any, output_class: Any):
        self.name = name
        self.service_name = service_name
        self.input = input_class
        self.output = output_class


class MockEndpoint:
    def __init__(self, name: str, service_name: str, input_class: Any, output_class: Any):
        self.method = MockMethodInfo(name, service_name, input_class, output_class)


class MockConnectApp:
    def __init__(self, endpoints: dict[str, Any]):
        self._endpoints = lambda _svc: endpoints
        self._service = object()


@pytest.mark.anyio
async def test_generate_openapi_schema_service():
    from proto.legisinfo.v1 import legisinfo_pb2

    app = FastAPI(title="Test App", version="1.2.3")

    mock_endpoints = {
        "/test.v1.Service/ListSessions": MockEndpoint(
            name="ListSessions",
            service_name="test.v1.Service",
            input_class=legisinfo_pb2.ListSessionsRequest,
            output_class=legisinfo_pb2.ListSessionsResponse,
        )
    }
    connect_app = MockConnectApp(mock_endpoints)

    service = GenerateOpenAPISchemaService(app, connect_app)
    schema = await service.perform()

    assert schema["info"]["title"] == "Test App"
    assert schema["info"]["version"] == "1.2.3"
    assert "/test.v1.Service/ListSessions" in schema["paths"]
    assert "ListSessionsRequest" in schema["components"]["schemas"]
