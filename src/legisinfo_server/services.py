import os
import sys

# Add gen directory to python path to resolve proto.* imports
sys.path.append(os.path.join(os.path.dirname(__file__), "gen"))

from connectrpc.code import Code
from connectrpc.errors import ConnectError
from connectrpc.request import RequestContext

from proto.legisinfo.v1 import legisinfo_connect, legisinfo_pb2


class LegisinfoServiceImpl(legisinfo_connect.LegisinfoService):
    def __init__(self, reader):
        self.reader = reader

    async def list_sessions(
        self, _request: legisinfo_pb2.ListSessionsRequest, _ctx: RequestContext
    ) -> legisinfo_pb2.ListSessionsResponse:
        sessions = self.reader.get_sessions()
        return legisinfo_pb2.ListSessionsResponse(sessions=sessions)

    async def list_bills(
        self, request: legisinfo_pb2.ListBillsRequest, _ctx: RequestContext
    ) -> legisinfo_pb2.ListBillsResponse:
        session = "45-1"
        filters_dict = {}

        if request.filters:
            if request.filters.session:
                session = request.filters.session

            # Map Chamber Enum to string for reader
            chamber_str = legisinfo_pb2.Chamber.Name(request.filters.chamber)

            filters_dict = {
                "chamber": chamber_str,
                "sponsor": request.filters.sponsor,
                "sponsor_affiliation": request.filters.sponsor_affiliation,
                "status": request.filters.status,
                "latest_activity": request.filters.latest_activity,
                "number": request.filters.number,
                "date_after": request.filters.date_after,
                "date_before": request.filters.date_before,
                "search_query": request.filters.search_query,
                "has_text": request.filters.has_text,
                "committee_only": request.filters.committee_only,
            }

        # Convert sort enums to names
        sort_field_str = legisinfo_pb2.SortField.Name(request.sort_field)
        sort_direction_str = legisinfo_pb2.SortDirection.Name(request.sort_direction)

        all_bills = self.reader.get_bills(
            session=session, filters=filters_dict, sort_field=sort_field_str, sort_direction=sort_direction_str
        )

        total_count = len(all_bills)

        # Slice for offset and limit
        offset = request.offset if request.offset >= 0 else 0
        limit = request.limit if request.limit > 0 else total_count

        sliced_bills = all_bills[offset : offset + limit]

        pb_bills = []
        for b in sliced_bills:
            pb_bills.append(
                legisinfo_pb2.BillSummary(
                    number=b["number"],
                    session=b["session"],
                    title_en=b["title_en"],
                    title_fr=b["title_fr"],
                    sponsor_name=b["sponsor_name"],
                    status=b["status"],
                    latest_event_date=b["latest_event_date"],
                )
            )

        return legisinfo_pb2.ListBillsResponse(bills=pb_bills, total_count=total_count)

    async def get_bill(
        self, request: legisinfo_pb2.GetBillRequest, _ctx: RequestContext
    ) -> legisinfo_pb2.GetBillResponse:
        bill = self.reader.get_bill_detail(request.session, request.bill_number)
        if not bill:
            raise ConnectError(Code.NOT_FOUND, f"Bill {request.bill_number} not found in session {request.session}")

        pb_stages = [
            legisinfo_pb2.BillStage(slug=s["slug"], name=s["name"], date=s["date"], source_type=s["source_type"])
            for s in bill["stages"]
        ]

        return legisinfo_pb2.GetBillResponse(
            bill=legisinfo_pb2.BillDetail(
                number=bill["number"],
                session=bill["session"],
                title_en=bill["title_en"],
                title_fr=bill["title_fr"],
                sponsor_name=bill["sponsor_name"],
                sponsor_email=bill["sponsor_email"],
                status=bill["status"],
                latest_event_date=bill["latest_event_date"],
                stages=pb_stages,
            )
        )

    async def get_bill_text(
        self, request: legisinfo_pb2.GetBillTextRequest, _ctx: RequestContext
    ) -> legisinfo_pb2.GetBillTextResponse:
        as_markdown = request.format != legisinfo_pb2.GetBillTextRequest.Format.FORMAT_XML

        content, format_str = self.reader.get_bill_text(
            session=request.session,
            bill_number=request.bill_number,
            stage_slug=request.stage_slug,
            as_markdown=as_markdown,
        )

        if format_str == "NONE":
            raise ConnectError(
                Code.NOT_FOUND,
                f"Bill text not found for {request.bill_number} (stage: {request.stage_slug or 'latest'})",
            )

        return legisinfo_pb2.GetBillTextResponse(
            bill_number=request.bill_number,
            session=request.session,
            stage_slug=request.stage_slug or "latest",
            content=content,
            format=format_str,
        )
