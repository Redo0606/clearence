#!/usr/bin/env python3
"""
Fetch content from all links in the Enterprise CRM Self-Help Guide PDF.
Outputs a JSON file with url, title, and content (string) for each link - ready for RAG/embedding/ingestion.

Usage: python fetch_link_contents.py [--output FILE]
"""

import argparse
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

# Base URL for UMN relative paths
UMN_BASE = "https://it.umn.edu"

# Link definitions: (title, url) - truncated Salesforce URLs completed with &language=en_US
LINKS = [
    ("Understand Privacy Settings", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-understand-privacy"),
    ("Understand Sharing", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-understand-sharing"),
    ("Log in for the First Time", "https://help.salesforce.com/apex/HTViewHelpDoc?id=basics_intro_logging_in.htm&language=en_US"),
    ("Troubleshoot Login Issues", "https://help.salesforce.com/HTViewHelpDoc?id=getstart_login.htm&language=en_US"),
    ("Navigate Salesforce Tabs", "https://help.salesforce.com/articleView?id=user_alltabs.htm&type=5"),
    ("Tips for New Users", "https://help.salesforce.com/articleView?id=basics_intro_tips_new_users.htm&type=5"),
    ("Use the Global Search Bar", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-use-global-search-bar"),
    ("Find Your Personal Settings", "https://help.salesforce.com/apex/HTViewHelpDoc?id=basics_nav_personal_settings.htm&language=en_US"),
    ("Martin - Our Full Sandbox Environment", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-access-martin-our-full"),
    ("Customize Your Pages", "https://help.salesforce.com/HTViewHelpDoc?id=user_userdisplay_pages.htm&language=en_US"),
    ("Customize Your Tabs", "https://help.salesforce.com/HTViewHelpDoc?id=user_userdisplay_tabs.htm&language=en_US"),
    ("Create Views", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-create-views"),
    ("Merge Fields Overview", "https://help.salesforce.com/apex/HTViewHelpDoc?id=valid_merge_fields.htm&language=en_US"),
    ("Considerations for Using Merge Fields in Email Templates", "https://help.salesforce.com/HTViewHelpDoc?id=merge_fields_email_templates.htm&language=en_US"),
    ("Create HTML Email Templates", "https://help.salesforce.com/HTViewHelpDoc?id=creating_html_email_templates.htm&language=en_US"),
    ("Create Text Email Templates", "https://help.salesforce.com/HTViewHelpDoc?id=creating_text_email_templates.htm&language=en_US"),
    ("Create Custom HTML Email Templates", "https://help.salesforce.com/HTViewHelpDoc?id=creating_custom_html_email_templates.htm&language=en_US"),
    ("Manage Email Templates", "https://help.salesforce.com/HTViewHelpDoc?id=admin_emailtemplates.htm&language=en_US"),
    ("Set Up Your Chatter Profile", "https://help.salesforce.com/apex/HTViewHelpDoc?id=basics_intro_setting_up_chatter.htm&language=en_US"),
    ("Post Visibility", "https://help.salesforce.com/apex/HTViewHelpDoc?id=collab_post_visibility.htm&language=en_US"),
    ("Replying to Chatter Email Notifications", "https://help.salesforce.com/apex/HTViewHelpDoc?id=collab_email_reply.htm&language=en_US"),
    ("@Mention People and Groups in Posts and Comments", "https://help.salesforce.com/apex/HTViewHelpDoc?id=collab_add_mentioning_people.htm&language=en_US"),
    ("Follow Records", "https://help.salesforce.com/HTViewHelpDoc?id=collab_following_records.htm&language=en_US"),
    ("Viewing Record Feeds", "https://help.salesforce.com/apex/HTViewHelpDoc?id=collab_viewing_record_updates.htm&language=en_US"),
    ("Chatter Groups", "https://help.salesforce.com/apex/HTViewHelpDoc?id=collab_group_about.htm&language=en_US"),
    ("Tutorials for Cirrus Insight", "https://www.cirrusinsight.com/tutorials"),
    ("Create an Internal Support Case", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-create-internal-support"),
    ("Verify a Case in Martin", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-verify-case-in-martin"),
    ("Verify a Case in Production", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-verify-case-in-production"),
    ("Create a Task", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-create-task"),
    ("Create an Event", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-create-event"),
    ("Add a Google Doc", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-add-google-doc"),
    ("Add a Note", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-add-note"),
    ("Add an Attachment", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-add-attachment"),
    ("Log a Call", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-log-call"),
    ("Send an Email", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-send-email"),
    ("Manually Create a Contact record", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-manually-create-contact"),
    ("Manually Create an Organization Record", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-manually-create-0"),
    ("Bios Record Types", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-bios-record-types"),
    ("Create Bios", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-create-bios"),
    ("Reserved Contact Data", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-reserved-contact-data"),
    ("Manually Create Reserved Contact Data", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-manually-create-reserved"),
    ("Reserved Organization Data", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-reserved-organization"),
    ("Manually Create Reserved Organization Data", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-manually-create-reserved-0"),
    ("Manually Create a New Lead", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-manually-create-new-lead"),
    ("Use Find Duplicates on Leads", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-use-find-duplicates-leads"),
    ("Convert Leads", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-convert-leads"),
    ("Manually Create an Opportunity", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-manually-create"),
    ("Manage Opportunities", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-manage-opportunities"),
    ("Manually Create Tags", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-manually-create-tags"),
    ("Add New Tag Assignments", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-add-new-tag-assignments"),
    ("Manually Create a New Interested Party record", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-manually-create-new"),
    ("Add Interested Party Assignments, Users, and Change record Owners", f"{UMN_BASE}/services-technologies/how-tos/enterprise-crm-add-interested-party"),
    ("Choose a Report Type", "https://help.salesforce.com/HTViewHelpDoc?id=reports_builder_selecting_a_report_type.htm&language=en_US"),
    ("Choose a Report Format", "https://help.salesforce.com/HTViewHelpDoc?id=reports_changing_format.htm&language=en_US"),
    ("Create a Report", "https://help.salesforce.com/HTViewHelpDoc?id=reports_builder_create.htm&language=en_US"),
    ("Using the Drag and Drop Report Builder", "https://help.salesforce.com/s/articleView?id=sf.reports_builder_impl_guide.htm&language=en_US"),
    ("Customizing Reports", "https://help.salesforce.com/HTViewHelpDoc?id=reports_builder_what_is.htm&language=en_US"),
    ("Report Fields", "https://help.salesforce.com/HTViewHelpDoc?id=reports_builder_fields.htm&language=en_US"),
    ("Group Your Report Data", "https://help.salesforce.com/HTViewHelpDoc?id=reports_builder_fields_groupings.htm&language=en_US"),
    ("Keep Working While Your Report Preview Loads", "https://help.salesforce.com/HTViewHelpDoc?id=reports_builder_asych.htm&language=en_US"),
    ("Summarize Your Report Data", "https://help.salesforce.com/HTViewHelpDoc?id=reports_builder_fields_summaries.htm&language=en_US"),
    ("Work with Formulas in Report Builder", "https://help.salesforce.com/HTViewHelpDoc?id=reports_builder_fields_formulas.htm&language=en_US"),
    ("Filter Report Data", "https://help.salesforce.com/HTViewHelpDoc?id=reports_builder_filtering.htm&language=en_US"),
    ("Getting the Most out of Filter Logic", "https://help.salesforce.com/HTViewHelpDoc?id=working_with_advanced_filter_conditions_in_reports_and_list_views.htm&language=en_US"),
    ("Filter Operators", "https://help.salesforce.com/HTViewHelpDoc?id=filter_operators.htm&language=en_US"),
    ("Example: Report on Related Objects with Cross Filters", "https://help.salesforce.com/HTViewHelpDoc?id=reports_cross_filters.htm&language=en_US"),
    ("Create a Salesforce Classic Dashboard", "https://help.salesforce.com/HTViewHelpDoc?id=dashboards_create.htm&language=en_US"),
    ("Save Your Report", "https://help.salesforce.com/HTViewHelpDoc?id=reports_saving.htm&language=en_US"),
    ("Subscribe to Get Report Notifications", "https://help.salesforce.com/htviewhelpdoc?id=reports_notifications_home.htm&siteLang=en_US"),
]


def extract_text(html: str, url: str) -> str:
    """Extract readable text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _is_429(exc: BaseException) -> bool:
    return isinstance(exc, requests.HTTPError) and getattr(exc, "response", None) and exc.response.status_code == 429


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception(_is_429),
)
def _fetch_url(url: str, timeout: int = 15) -> requests.Response:
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return resp


def fetch_content(title: str, url: str, timeout: int = 15) -> dict:
    """Fetch URL and return {url, title, content}. Skip fetch for JS-heavy Salesforce Help."""
    result = {"url": url, "title": title, "content": ""}
    # Salesforce Help loads content via JavaScript - skip fetch, store reference
    if "help.salesforce.com" in url or "salesforce.com/help" in url:
        result["content"] = (
            f"Salesforce Help: {title}. "
            f"This documentation page loads content dynamically via JavaScript. "
            f"Visit {url} for the full article."
        )
        result["content_type"] = "html"
        result["content_source"] = "reference"
        return result
    try:
        resp = _fetch_url(url, timeout)
        if "application/pdf" in resp.headers.get("Content-Type", ""):
            result["content"] = f"[PDF document - {len(resp.content)} bytes]"
            result["content_type"] = "pdf"
        else:
            result["content"] = extract_text(resp.text, url)
            result["content_type"] = "html"
        result["content_source"] = "fetched"
    except Exception as e:
        result["content"] = ""
        result["error"] = str(e)
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch link contents for ingestion")
    parser.add_argument("--output", "-o", type=Path, default=Path("documents/useful_links_content.json"))
    parser.add_argument("--delay", type=float, default=1.2, help="Delay between fetches (seconds)")
    parser.add_argument("--no-fix", action="store_true", help="Skip running fix_link_content.py after fetch")
    parser.add_argument("--retry-missing", action="store_true", help="Only fetch URLs that failed (empty content) in existing output")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Build cache of existing content by URL (for --retry-missing)
    existing_by_url: dict[str, dict] = {}
    if args.retry_missing and args.output.exists():
        try:
            with open(args.output, encoding="utf-8") as f:
                for rec in json.load(f):
                    existing_by_url[rec["url"]] = rec
            print(f"Loaded {len(existing_by_url)} existing records, will retry only failed URLs\n")
        except (json.JSONDecodeError, KeyError):
            pass

    records = []
    for i, (title, url) in enumerate(LINKS):
        skip_fetch = "help.salesforce.com" in url or "salesforce.com/help" in url
        if args.retry_missing and url in existing_by_url:
            existing = existing_by_url[url]
            # Reuse if we have content; otherwise refetch
            if existing.get("content") and not existing.get("error"):
                records.append(existing)
                print(f"[{i+1}/{len(LINKS)}] {title[:50]}... (cached)")
                continue
        label = "(skip)" if skip_fetch else ""
        print(f"[{i+1}/{len(LINKS)}] {title[:50]}... {label}")
        rec = fetch_content(title, url)
        records.append(rec)
        if rec.get("content"):
            preview = rec["content"][:80].replace("\n", " ")
            print(f"       -> {preview}...")
        elif rec.get("error"):
            print(f"       -> Error: {rec['error']}")
        if not skip_fetch:
            time.sleep(args.delay)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {len(records)} records to {args.output}")

    if not args.no_fix and args.output.name == "useful_links_content.json":
        import subprocess
        fix_script = Path(__file__).parent / "fix_link_content.py"
        if fix_script.exists():
            subprocess.run(
                [__import__("sys").executable, str(fix_script)],
                check=True,
                cwd=args.output.resolve().parent.parent,
            )
            print("Ran fix_link_content.py")


if __name__ == "__main__":
    main()
