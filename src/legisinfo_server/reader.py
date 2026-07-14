import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

class LegisinfoReader:
    def __init__(self, data_repo_path: str):
        self.data_repo_path = data_repo_path

    def get_sessions(self) -> List[str]:
        """List all parliament sessions available in the data repository."""
        if not os.path.exists(self.data_repo_path):
            return []
        
        sessions = []
        for name in os.listdir(self.data_repo_path):
            if os.path.isdir(os.path.join(self.data_repo_path, name)):
                # Match e.g. "45-1", "36-1"
                if re.match(r"^\d+-\d+$", name):
                    sessions.append(name)
        
        # Sort sessions descending (e.g. 45-1, 44-2, 44-1...)
        def session_key(s: str) -> Tuple[int, int]:
            parts = s.split("-")
            return int(parts[0]), int(parts[1])
            
        sessions.sort(key=session_key, reverse=True)
        return sessions

    def _parse_metadata(self, metadata_path: str) -> Optional[Dict[str, Any]]:
        """Parse metadata.xml for a bill and return a structured dictionary."""
        if not os.path.exists(metadata_path):
            return None
        
        try:
            tree = ET.parse(metadata_path)
            root = tree.getroot()
            
            number = root.findtext("NumberCode") or ""
            # Fallback to file's parent folder name if NumberCode is missing
            if not number:
                number = os.path.basename(os.path.dirname(metadata_path))
                
            title_en = root.findtext("LongTitleEn") or root.findtext("ShortTitleEn") or ""
            title_fr = root.findtext("LongTitleFr") or root.findtext("ShortTitleFr") or ""
            
            sponsor_name = root.findtext(".//SponsorPersonName") or ""
            sp_title = root.findtext(".//SponsorAffiliationTitleEn") or ""
            sponsor_affiliation = sp_title or root.findtext(".//SponsorAffiliationRoleEn") or ""
            
            if sponsor_name and sp_title:
                sponsor_display = f"{sp_title} {sponsor_name}"
            else:
                sponsor_display = sponsor_name or "Parliament of Canada"
                
            sponsor_email = ""
            if sponsor_name:
                cleaned_name = re.sub(r"[^a-zA-Z\s.-]", "", sponsor_name).strip()
                cleaned_name = re.sub(r"\s+", ".", cleaned_name).lower()
                sponsor_email = f"{cleaned_name}@parl.gc.ca"
            
            status = root.findtext("StatusNameEn") or ""
            latest_activity = root.findtext("LatestBillEventTypeName") or ""
            
            latest_event_date_str = root.findtext("LatestBillEventDateTime") or ""
            
            # Parse stages
            stages = []
            # Extract House and Senate stages
            for stages_parent in ("HouseBillStages", "SenateBillStages"):
                for stage_node in root.findall(f".//{stages_parent}/*"):
                    stage_name = stage_node.findtext("BillStageNameEn")
                    stage_status = stage_node.findtext("StateNameEn")
                    stage_date = stage_node.findtext("LastStageEventStartDateTime")
                    
                    if stage_name and stage_status == "Completed" and stage_date:
                        # Clean date
                        if stage_date.startswith("0001-01-01"):
                            continue
                            
                        # Generate slug
                        slug = stage_name.lower().replace(" ", "-").replace("stage", "").strip("-")
                        # Normalize slugs
                        if "first" in slug:
                            slug = "first-reading"
                        elif "second" in slug:
                            slug = "second-reading"
                        elif "third" in slug:
                            slug = "third-reading"
                        elif "committee" in slug:
                            slug = "committee"
                        elif "royal" in slug or "assent" in slug:
                            slug = "royal-assent"
                            
                        stages.append({
                            "slug": slug,
                            "name": stage_name,
                            "date": stage_date,
                            "source_type": "XML"
                        })
                        
            # Sort stages chronologically based on date
            def parse_date(d):
                try:
                    return datetime.fromisoformat(d)
                except Exception:
                    return datetime.min
            stages.sort(key=lambda s: parse_date(s["date"]))
            
            return {
                "number": number,
                "title_en": title_en,
                "title_fr": title_fr,
                "sponsor_name": sponsor_display,
                "sponsor_affiliation": sponsor_affiliation,
                "sponsor_email": sponsor_email,
                "status": status,
                "latest_activity": latest_activity,
                "latest_event_date": latest_event_date_str,
                "stages": stages
            }
        except Exception:
            return None

    def get_bills(
        self,
        session: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_field: str = "SORT_FIELD_UNSPECIFIED",
        sort_direction: str = "SORT_DIRECTION_UNSPECIFIED"
    ) -> List[Dict[str, Any]]:
        """Retrieve and filter bills in a session."""
        bills_dir = os.path.join(self.data_repo_path, session, "bills")
        if not os.path.exists(bills_dir):
            return []
            
        bills = []
        for bill_number in os.listdir(bills_dir):
            bill_path = os.path.join(bills_dir, bill_number)
            if not os.path.isdir(bill_path):
                continue
                
            metadata_path = os.path.join(bill_path, "metadata.xml")
            bill_data = self._parse_metadata(metadata_path)
            if bill_data:
                bill_data["session"] = session
                bill_data["has_text"] = os.path.exists(os.path.join(bill_path, "bill_text.md"))
                bills.append(bill_data)
                
        # Apply filters
        if filters:
            filtered_bills = []
            for b in bills:
                # 1. Chamber filter
                chamber_filter = filters.get("chamber")
                if chamber_filter and chamber_filter != "CHAMBER_UNSPECIFIED":
                    prefix = b["number"].upper()
                    is_house = prefix.startswith("C-")
                    is_senate = prefix.startswith("S-")
                    if chamber_filter == "CHAMBER_HOUSE" and not is_house:
                        continue
                    if chamber_filter == "CHAMBER_SENATE" and not is_senate:
                        continue

                # 2. Sponsor substring
                sponsor_f = filters.get("sponsor")
                if sponsor_f and sponsor_f.lower() not in b["sponsor_name"].lower():
                    continue

                # 3. Sponsor affiliation
                aff_f = filters.get("sponsor_affiliation")
                if aff_f and aff_f.lower() not in b["sponsor_affiliation"].lower():
                    continue

                # 4. Status
                status_f = filters.get("status")
                if status_f and status_f.lower() not in b["status"].lower():
                    continue

                # 5. Latest Activity
                act_f = filters.get("latest_activity")
                if act_f and act_f.lower() not in b["latest_activity"].lower():
                    continue

                # 6. Bill Number Match
                num_f = filters.get("number")
                if num_f and num_f.lower() not in b["number"].lower():
                    continue

                # 7. Date comparisons
                def to_datetime(ds):
                    if not ds or ds.startswith("0001-01-01"):
                        return None
                    try:
                        return datetime.fromisoformat(ds.split(".")[0])
                    except Exception:
                        try:
                            return datetime.strptime(ds, "%Y-%m-%d")
                        except Exception:
                            return None

                latest_dt = to_datetime(b["latest_event_date"])
                
                after_f = filters.get("date_after")
                if after_f:
                    after_dt = to_datetime(after_f)
                    if after_dt and (not latest_dt or latest_dt < after_dt):
                        continue

                before_f = filters.get("date_before")
                if before_f:
                    before_dt = to_datetime(before_f)
                    if before_dt and (not latest_dt or latest_dt > before_dt):
                        continue

                # 8. Search query (searches title, sponsor, number, status)
                query_f = filters.get("search_query")
                if query_f:
                    query = query_f.lower()
                    matches = (
                        query in b["number"].lower() or
                        query in b["title_en"].lower() or
                        query in b["title_fr"].lower() or
                        query in b["sponsor_name"].lower() or
                        query in b["status"].lower()
                    )
                    if not matches:
                        continue

                # 9. Has Text
                if filters.get("has_text") and not b["has_text"]:
                    continue

                # 10. Committee Only
                if filters.get("committee_only") and "committee" not in b["status"].lower() and "committee" not in b["latest_activity"].lower():
                    continue

                filtered_bills.append(b)
            bills = filtered_bills

        # Apply sorting
        # Determine sorting field
        def sort_key_fn(b: Dict[str, Any]):
            if sort_field == "SORT_FIELD_NUMBER":
                # Parse bill number to sort C-11 before C-100
                match = re.match(r"^([C|S])-(\d+)", b["number"])
                if match:
                    return match.group(1), int(match.group(2))
                return b["number"], 0
            elif sort_field == "SORT_FIELD_SPONSOR":
                return b["sponsor_name"].lower()
            elif sort_field == "SORT_FIELD_STATUS":
                return b["status"].lower()
            elif sort_field == "SORT_FIELD_TITLE":
                return b["title_en"].lower() or b["title_fr"].lower()
            else: # SORT_FIELD_LATEST_EVENT_DATE or SORT_FIELD_UNSPECIFIED
                # Sort by date
                ds = b["latest_event_date"]
                if not ds or ds.startswith("0001-01-01"):
                    return datetime.min
                try:
                    return datetime.fromisoformat(ds)
                except Exception:
                    return datetime.min

        # Sort direction default
        # If unspecified, DESC for date, ASC for others
        is_desc = True
        if sort_direction == "SORT_DIRECTION_ASC":
            is_desc = False
        elif sort_direction == "SORT_DIRECTION_DESC":
            is_desc = True
        else:
            if sort_field in ("SORT_FIELD_NUMBER", "SORT_FIELD_SPONSOR", "SORT_FIELD_STATUS", "SORT_FIELD_TITLE"):
                is_desc = False
            else:
                is_desc = True

        bills.sort(key=sort_key_fn, reverse=is_desc)
        return bills

    def get_bill_detail(self, session: str, bill_number: str) -> Optional[Dict[str, Any]]:
        """Get full details of a bill including its stages."""
        metadata_path = os.path.join(self.data_repo_path, session, "bills", bill_number, "metadata.xml")
        bill_data = self._parse_metadata(metadata_path)
        if bill_data:
            bill_data["session"] = session
            # Check if actual stages has text file in stages/ folder
            stages_dir = os.path.join(self.data_repo_path, session, "bills", bill_number, "stages")
            if os.path.exists(stages_dir):
                for s in bill_data["stages"]:
                    slug = s["slug"]
                    if os.path.exists(os.path.join(stages_dir, f"{slug}.xml")):
                        s["source_type"] = "XML"
                    elif os.path.exists(os.path.join(stages_dir, f"{slug}.md")):
                        s["source_type"] = "HTML Fallback"
            return bill_data
        return None

    def get_bill_text(self, session: str, bill_number: str, stage_slug: str = "", as_markdown: bool = True) -> Tuple[str, str]:
        """Retrieve bill text content. Returns (content, format)."""
        bill_dir = os.path.join(self.data_repo_path, session, "bills", bill_number)
        
        # Determine filepath based on stage_slug
        if stage_slug:
            ext = "md" if as_markdown else "xml"
            path = os.path.join(bill_dir, "stages", f"{stage_slug}.{ext}")
            # Fallback to XML if md requested but not found, or vice-versa
            if not os.path.exists(path):
                alt_ext = "xml" if as_markdown else "md"
                alt_path = os.path.join(bill_dir, "stages", f"{stage_slug}.{alt_ext}")
                if os.path.exists(alt_path):
                    path = alt_path
                    as_markdown = (alt_ext == "md")
        else:
            # Latest bill text
            ext = "md" if as_markdown else "xml"
            path = os.path.join(bill_dir, f"bill_text.{ext}")
            if not os.path.exists(path):
                alt_ext = "xml" if as_markdown else "md"
                alt_path = os.path.join(bill_dir, f"bill_text.{alt_ext}")
                if os.path.exists(alt_path):
                    path = alt_path
                    as_markdown = (alt_ext == "md")

        if not os.path.exists(path):
            return "", "NONE"

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            format_str = "MARKDOWN" if as_markdown else "XML"
            return content, format_str
        except Exception:
            return "", "NONE"
