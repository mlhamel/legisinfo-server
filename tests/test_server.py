import os
import tempfile
import shutil
import unittest
from fastapi.testclient import TestClient

# Mock environment variable before importing main app
tmp_data_dir = tempfile.mkdtemp()
os.environ["LEGISINFO_DATA_PATH"] = tmp_data_dir

from legisinfo_server.main import app

class TestLegisinfoServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = tmp_data_dir
        cls.client = TestClient(app)
        
        # Create mock data structure:
        # - Session 45-1
        #   - bills
        #     - C-11 (House bill, sponsor: Khanna, status: Royal Assent)
        #     - S-2 (Senate bill, sponsor: Gold, status: Committee)
        
        # 1. Bill C-11
        c11_path = os.path.join(cls.data_dir, "45-1", "bills", "C-11")
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
        s2_path = os.path.join(cls.data_dir, "45-1", "bills", "S-2")
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

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.data_dir)

    def test_http_endpoints(self):
        # Health check
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")
        self.assertEqual(res.json()["available_sessions_count"], 1)
        
        # Root welcome
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Welcome", res.json()["message"])

    def test_list_sessions(self):
        res = self.client.post("/legisinfo.v1.LegisinfoService/ListSessions", json={})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"sessions": ["45-1"]})

    def test_list_bills_all(self):
        res = self.client.post("/legisinfo.v1.LegisinfoService/ListBills", json={})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["totalCount"], 2)
        
        # Sorted by latest event date descending by default: S-2 (June 20), C-11 (May 10)
        self.assertEqual(data["bills"][0]["number"], "S-2")
        self.assertEqual(data["bills"][1]["number"], "C-11")

    def test_list_bills_filter_chamber(self):
        # Filter House
        res = self.client.post("/legisinfo.v1.LegisinfoService/ListBills", json={
            "filters": {
                "chamber": "CHAMBER_HOUSE"
            }
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["totalCount"], 1)
        self.assertEqual(data["bills"][0]["number"], "C-11")
        
        # Filter Senate
        res = self.client.post("/legisinfo.v1.LegisinfoService/ListBills", json={
            "filters": {
                "chamber": "CHAMBER_SENATE"
            }
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["totalCount"], 1)
        self.assertEqual(data["bills"][0]["number"], "S-2")

    def test_list_bills_filter_sponsor(self):
        res = self.client.post("/legisinfo.v1.LegisinfoService/ListBills", json={
            "filters": {
                "sponsor": "Khanna"
            }
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["totalCount"], 1)
        self.assertEqual(data["bills"][0]["number"], "C-11")

    def test_list_bills_filter_status(self):
        res = self.client.post("/legisinfo.v1.LegisinfoService/ListBills", json={
            "filters": {
                "status": "Assent"
            }
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["totalCount"], 1)
        self.assertEqual(data["bills"][0]["number"], "C-11")

    def test_list_bills_filter_search(self):
        # Search match safety
        res = self.client.post("/legisinfo.v1.LegisinfoService/ListBills", json={
            "filters": {
                "searchQuery": "Safety"
            }
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["totalCount"], 1)
        self.assertEqual(data["bills"][0]["number"], "S-2")

    def test_list_bills_sorting(self):
        # Sort by number ascending
        res = self.client.post("/legisinfo.v1.LegisinfoService/ListBills", json={
            "sortField": "SORT_FIELD_NUMBER",
            "sortDirection": "SORT_DIRECTION_ASC"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["bills"][0]["number"], "C-11")
        self.assertEqual(data["bills"][1]["number"], "S-2")

    def test_get_bill_detail(self):
        res = self.client.post("/legisinfo.v1.LegisinfoService/GetBill", json={
            "session": "45-1",
            "billNumber": "C-11"
        })
        self.assertEqual(res.status_code, 200)
        bill = res.json()["bill"]
        self.assertEqual(bill["number"], "C-11")
        self.assertEqual(bill["sponsorName"], "Conservative MP Arpan Khanna")
        self.assertEqual(len(bill["stages"]), 2)
        self.assertEqual(bill["stages"][0]["slug"], "first-reading")

    def test_get_bill_detail_not_found(self):
        res = self.client.post("/legisinfo.v1.LegisinfoService/GetBill", json={
            "session": "45-1",
            "billNumber": "C-99"
        })
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.json()["message"])

    def test_get_bill_text(self):
        res = self.client.post("/legisinfo.v1.LegisinfoService/GetBillText", json={
            "session": "45-1",
            "billNumber": "C-11",
            "format": "FORMAT_MARKDOWN"
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("Broadcast Act", res.json()["content"])

    def test_get_bill_text_stage(self):
        res = self.client.post("/legisinfo.v1.LegisinfoService/GetBillText", json={
            "session": "45-1",
            "billNumber": "C-11",
            "stageSlug": "first-reading",
            "format": "FORMAT_MARKDOWN"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["content"], "# First Reading text")

    def test_openapi_schema(self):
        res = self.client.get("/openapi.json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("/legisinfo.v1.LegisinfoService/ListSessions", data["paths"])
        self.assertIn("/legisinfo.v1.LegisinfoService/ListBills", data["paths"])
        self.assertIn("ListBillsRequest", data["components"]["schemas"])
