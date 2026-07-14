import os
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient

# Mock environment variable before importing main app
tmp_data_dir = tempfile.mkdtemp()
os.environ["LEGISINFO_DATA_PATH"] = tmp_data_dir

from legisinfo_server.main import app  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def setup_mock_data():
    data_dir = tmp_data_dir

    # Create mock data structure:
    # - Session 45-1
    #   - bills
    #     - C-11 (House bill, sponsor: Khanna, status: Royal Assent)
    #     - S-2 (Senate bill, sponsor: Gold, status: Committee)

    # 1. Bill C-11
    c11_path = os.path.join(data_dir, "45-1", "bills", "C-11")
    os.makedirs(os.path.join(c11_path, "stages"), exist_ok=True)

    metadata_c11 = """<Bill>
        <NumberCode>C-11</NumberCode>
        <LongTitleEn>An Act to amend the Broadcast Act</LongTitleEn>
        <LongTitleFr>Loi modifiant la Loi sur la radiodiffusion</LongTitleFr>
        <StatusNameEn>Royal Assent Received</StatusNameEn>
        <LatestBillEventTypeName>Royal Assent</LatestBillEventTypeName>
        <LatestBillEventDateTime>2026-05-10T12:00:00</LatestBillEventDateTime>
        <SponsorPersonName>Arpan Khanna</SponsorPersonName>
        <SponsorAffiliationTitleEn>Conservative MP</SponsorAffiliationTitleEn>
        <HouseBillStages>
            <HouseBillStage>
                <BillStageNameEn>First Reading</BillStageNameEn>
                <StateNameEn>Completed</StateNameEn>
                <LastStageEventStartDateTime>2026-01-15T10:00:00</LastStageEventStartDateTime>
            </HouseBillStage>
            <HouseBillStage>
                <BillStageNameEn>Royal Assent</BillStageNameEn>
                <StateNameEn>Completed</StateNameEn>
                <LastStageEventStartDateTime>2026-05-10T12:00:00</LastStageEventStartDateTime>
            </HouseBillStage>
        </HouseBillStages>
    </Bill>"""
    with open(os.path.join(c11_path, "metadata.xml"), "w", encoding="utf-8") as f:
        f.write(metadata_c11)

    with open(os.path.join(c11_path, "bill_text.md"), "w", encoding="utf-8") as f:
        f.write("# Broadcast Act Amendments\nThis is the text.")

    with open(os.path.join(c11_path, "stages", "first-reading.md"), "w", encoding="utf-8") as f:
        f.write("# First Reading text")

    # 2. Bill S-2
    s2_path = os.path.join(data_dir, "45-1", "bills", "S-2")
    os.makedirs(os.path.join(s2_path, "stages"), exist_ok=True)

    metadata_s2 = """<Bill>
        <NumberCode>S-2</NumberCode>
        <LongTitleEn>An Act to amend the Safety Board Act</LongTitleEn>
        <StatusNameEn>At consideration in committee in the Senate</StatusNameEn>
        <LatestBillEventTypeName>Committee Stage</LatestBillEventTypeName>
        <LatestBillEventDateTime>2026-06-20T10:00:00</LatestBillEventDateTime>
        <SponsorPersonName>Senator Gold</SponsorPersonName>
        <SenateBillStages>
            <SenateBillStage>
                <BillStageNameEn>First Reading</BillStageNameEn>
                <StateNameEn>Completed</StateNameEn>
                <LastStageEventStartDateTime>2026-06-01T14:00:00</LastStageEventStartDateTime>
            </SenateBillStage>
        </SenateBillStages>
    </Bill>"""
    with open(os.path.join(s2_path, "metadata.xml"), "w", encoding="utf-8") as f:
        f.write(metadata_s2)

    yield

    shutil.rmtree(data_dir)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_http_endpoints(client):
    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"
    assert res.json()["available_sessions_count"] == 1

    # Root welcome
    res = client.get("/")
    assert res.status_code == 200
    assert "Welcome" in res.json()["message"]


def test_list_sessions(client):
    res = client.post("/legisinfo.v1.LegisinfoService/ListSessions", json={})
    assert res.status_code == 200
    assert res.json() == {"sessions": ["45-1"]}


def test_list_bills_all(client):
    res = client.post("/legisinfo.v1.LegisinfoService/ListBills", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["totalCount"] == 2

    # Sorted by latest event date descending by default: S-2 (June 20), C-11 (May 10)
    assert data["bills"][0]["number"] == "S-2"
    assert data["bills"][1]["number"] == "C-11"


def test_list_bills_filter_chamber(client):
    # Filter House
    res = client.post("/legisinfo.v1.LegisinfoService/ListBills", json={"filters": {"chamber": "CHAMBER_HOUSE"}})
    assert res.status_code == 200
    data = res.json()
    assert data["totalCount"] == 1
    assert data["bills"][0]["number"] == "C-11"

    # Filter Senate
    res = client.post("/legisinfo.v1.LegisinfoService/ListBills", json={"filters": {"chamber": "CHAMBER_SENATE"}})
    assert res.status_code == 200
    data = res.json()
    assert data["totalCount"] == 1
    assert data["bills"][0]["number"] == "S-2"


def test_list_bills_filter_sponsor(client):
    res = client.post("/legisinfo.v1.LegisinfoService/ListBills", json={"filters": {"sponsor": "Khanna"}})
    assert res.status_code == 200
    data = res.json()
    assert data["totalCount"] == 1
    assert data["bills"][0]["number"] == "C-11"


def test_list_bills_filter_status(client):
    res = client.post("/legisinfo.v1.LegisinfoService/ListBills", json={"filters": {"status": "Assent"}})
    assert res.status_code == 200
    data = res.json()
    assert data["totalCount"] == 1
    assert data["bills"][0]["number"] == "C-11"


def test_list_bills_filter_search(client):
    res = client.post("/legisinfo.v1.LegisinfoService/ListBills", json={"filters": {"searchQuery": "Safety"}})
    assert res.status_code == 200
    data = res.json()
    assert data["totalCount"] == 1
    assert data["bills"][0]["number"] == "S-2"


def test_list_bills_sorting(client):
    res = client.post(
        "/legisinfo.v1.LegisinfoService/ListBills",
        json={"sortField": "SORT_FIELD_NUMBER", "sortDirection": "SORT_DIRECTION_ASC"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["bills"][0]["number"] == "C-11"
    assert data["bills"][1]["number"] == "S-2"


def test_get_bill_detail(client):
    res = client.post("/legisinfo.v1.LegisinfoService/GetBill", json={"session": "45-1", "billNumber": "C-11"})
    assert res.status_code == 200
    bill = res.json()["bill"]
    assert bill["number"] == "C-11"
    assert bill["sponsorName"] == "Conservative MP Arpan Khanna"
    assert len(bill["stages"]) == 2
    assert bill["stages"][0]["slug"] == "first-reading"


def test_get_bill_detail_not_found(client):
    res = client.post("/legisinfo.v1.LegisinfoService/GetBill", json={"session": "45-1", "billNumber": "C-99"})
    assert res.status_code == 404
    assert "not found" in res.json()["message"]


def test_get_bill_text(client):
    res = client.post(
        "/legisinfo.v1.LegisinfoService/GetBillText",
        json={"session": "45-1", "billNumber": "C-11", "format": "FORMAT_MARKDOWN"},
    )
    assert res.status_code == 200
    assert "Broadcast Act" in res.json()["content"]


def test_get_bill_text_stage(client):
    res = client.post(
        "/legisinfo.v1.LegisinfoService/GetBillText",
        json={"session": "45-1", "billNumber": "C-11", "stageSlug": "first-reading", "format": "FORMAT_MARKDOWN"},
    )
    assert res.status_code == 200
    assert res.json()["content"] == "# First Reading text"


def test_openapi_schema(client):
    res = client.get("/openapi.json")
    assert res.status_code == 200
    data = res.json()
    assert "/legisinfo.v1.LegisinfoService/ListSessions" in data["paths"]
    assert "/legisinfo.v1.LegisinfoService/ListBills" in data["paths"]
    assert "ListBillsRequest" in data["components"]["schemas"]
