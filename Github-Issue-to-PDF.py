#!/usr/bin/env python3

"""
Fetches all GitHub issues (including comments) from a repository via the GitHub REST API,
and exports each to a PDF file using pdfkit + wkhtmltopdf.

Images are inlined (converted to base64) so that private or otherwise unreachable
image URLs show up properly in the PDF (instead of the broken-image icon).
"""

import os
import sys
import base64
import requests
import pdfkit
import markdown2
from bs4 import BeautifulSoup
from datetime import datetime

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------
OWNER = "UAX-Technologies"   # e.g. "octocat"
REPO = "DeckRC"             # e.g. "Hello-World"
STATE = "all"               # "open", "closed", or "all"
OUTPUT_DIR = f"Exported_PDFs/{OWNER}-{REPO}"

# If the repo is private or you want higher rate limits, set a GitHub token.
# We'll read from an environment variable by default.
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", None)

# If you want custom HTML styling, embed it here:
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Issue #{issue_number} - {issue_title}</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 20px;
      line-height: 1.4;
    }}
    pre, code {{
      background: #f5f5f5;
      padding: 5px;
      font-family: monospace;
      white-space: pre-wrap;
      word-wrap: break-word;
    }}
    h1, h2, h3 {{
      margin-top: 1em;
    }}
    .metadata, .comments {{
      margin: 1em 0;
    }}
    .comment {{
      border-top: 1px solid #ccc;
      padding-top: 1em;
      margin-top: 1em;
    }}
    .comment:first-child {{
      border-top: none;
      margin-top: 0;
      padding-top: 0;
    }}
  </style>
</head>
<body>
  <h1>Issue #{issue_number}: {issue_title}</h1>
  
  <div class="metadata">
    <p><strong>State:</strong> {issue_state}</p>
    <p><strong>Created at:</strong> {issue_created_at}</p>
    <p><strong>Author:</strong> {issue_author}</p>
    <p><strong>Locked:</strong> {locked}</p>
    {milestone_html}
    {labels_html}
    {assignees_html}
  </div>
  
  <hr/>
  <div class="issue-body">
    {issue_body_html}
  </div>

  <hr/>
  <div class="comments">
    <h2>Comments ({comments_count})</h2>
    {comments_html}
  </div>
</body>
</html>
"""

# -------------------------------------------------------------------
# MAIN SCRIPT
# -------------------------------------------------------------------

def session_with_auth(token=None):
    """Create a requests Session, optionally with a Bearer token for private repos."""
    s = requests.Session()
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s

def fetch_issues(owner, repo, state="all", token=None):
    """
    Generator: yields issue objects from the GitHub API (all pages).
    Skips Pull Requests. (PRs have a 'pull_request' key.)
    """
    sess = session_with_auth(token)
    page = 1
    per_page = 100
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = {
            "state": state,
            "page": page,
            "per_page": per_page
        }
        print(f"Fetching issues page {page}...")

        resp = sess.get(url, params=params)
        if resp.status_code != 200:
            print(f"Error: {resp.status_code} {resp.text}")
            sys.exit(1)

        data = resp.json()
        if not isinstance(data, list) or len(data) == 0:
            break  # no more issues

        for issue in data:
            if "pull_request" in issue:
                # This is a Pull Request, skip if you only want issues
                continue
            yield issue

        page += 1

def fetch_comments_for_issue(issue, token=None):
    """Return a list of comment objects for a single issue (handle pagination)."""
    sess = session_with_auth(token)
    url = issue["comments_url"]  # "https://api.github.com/repos/owner/repo/issues/123/comments"

    comments = []
    page = 1
    per_page = 100
    while True:
        params = {"page": page, "per_page": per_page}
        resp = sess.get(url, params=params)
        if resp.status_code != 200:
            print(f"Error fetching comments for issue #{issue['number']}: {resp.status_code}")
            break
        page_data = resp.json()
        if not page_data:
            break
        comments.extend(page_data)
        page += 1

    return comments

def markdown_to_html(md_text):
    """Convert Markdown to HTML with markdown2 (fenced-code-blocks, etc.)."""
    return markdown2.markdown(md_text or "", extras=["fenced-code-blocks", "tables", "strike"])

def inline_images_in_html(html, token=None):
    """
    Parse the given HTML for <img> tags. For each:
      1) Fetch the image with an authenticated session (if token is provided).
      2) Convert to base64 data URL.
      3) Replace the 'src' with the data URL.
    Returns a modified HTML string.
    """
    sess = session_with_auth(token)
    soup = BeautifulSoup(html, "html.parser")

    for img in soup.find_all("img"):
        src = img.get("src", "")
        # If src is a valid URL (starts with http), try to inline it
        if src.lower().startswith("http"):
            try:
                # Fetch image
                r = sess.get(src)
                if r.status_code == 200:
                    content_type = r.headers.get("Content-Type", "image/png")
                    # Convert to base64
                    b64_data = base64.b64encode(r.content).decode("utf-8")
                    data_url = f"data:{content_type};base64,{b64_data}"
                    # Replace src
                    img["src"] = data_url
                else:
                    # If fetch fails, we leave the original src
                    print(f"Warning: Could not fetch image ({src}), status={r.status_code}")
            except Exception as e:
                print(f"Warning: Exception while inlining image ({src}): {e}")

    return str(soup)

def create_issue_pdf(issue, comments, token=None):
    """
    Build final HTML (issue + comments), inline images, and export to a PDF.
    """
    issue_number = issue["number"]
    issue_title = issue.get("title", f"Issue {issue_number}")
    issue_state = issue.get("state", "unknown").upper()
    issue_created_at = issue.get("created_at", "")
    locked = issue.get("locked", False)
    locked_str = "Yes" if locked else "No"

    # Author
    user = issue.get("user")
    issue_author = user["login"] if user else "unknown"

    # Labels
    labels_data = issue.get("labels", [])
    if labels_data:
        labels_html = "<p><strong>Labels:</strong> " + ", ".join(
            f"{lbl['name']}" for lbl in labels_data
        ) + "</p>"
    else:
        labels_html = "<p><strong>Labels:</strong> None</p>"

    # Assignees
    assignees_data = issue.get("assignees", [])
    if assignees_data:
        assignees_html = "<p><strong>Assignees:</strong> " + ", ".join(
            a["login"] for a in assignees_data
        ) + "</p>"
    else:
        assignees_html = "<p><strong>Assignees:</strong> None</p>"

    # Milestone
    milestone = issue.get("milestone")
    if milestone:
        milestone_html = f"<p><strong>Milestone:</strong> {milestone['title']}</p>"
    else:
        milestone_html = "<p><strong>Milestone:</strong> None</p>"

    # Convert issue body to HTML
    issue_body_md = issue.get("body", "")
    issue_body_html = markdown_to_html(issue_body_md)

    # Convert each comment to HTML
    comments_html_parts = []
    for cm in comments:
        cm_user = cm["user"]["login"] if cm.get("user") else "unknown"
        cm_created_at = cm.get("created_at", "")
        cm_body_md = cm.get("body", "")
        cm_body_html = markdown_to_html(cm_body_md)
        snippet = f"""
        <div class="comment">
          <p><strong>{cm_user}</strong> commented on {cm_created_at}</p>
          <div>{cm_body_html}</div>
        </div>
        """
        comments_html_parts.append(snippet)

    comments_count = len(comments)
    comments_html = "\n".join(comments_html_parts)

    # Merge into the master template
    full_html = HTML_TEMPLATE.format(
        issue_number=issue_number,
        issue_title=issue_title,
        issue_state=issue_state,
        issue_created_at=issue_created_at,
        issue_author=issue_author,
        locked=locked_str,
        milestone_html=milestone_html,
        labels_html=labels_html,
        assignees_html=assignees_html,
        issue_body_html=issue_body_html,
        comments_count=comments_count,
        comments_html=comments_html
    )

    # Inline images so they're guaranteed to render (especially for private repos)
    inlined_html = inline_images_in_html(full_html, token=token)

    # Ensure output dir
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf_path = os.path.join(OUTPUT_DIR, f"issue_{issue_number}.pdf")

    print(f"  -> Creating PDF: Issue #{issue_number} -> {pdf_path}")
    try:
        pdfkit.from_string(inlined_html, pdf_path, options={"dpi": "300"})
    except Exception as ex:
        log_error(f"Issue #{issue_number} - PDF generation error: {ex}")

def log_error(msg):
    """Append an error message to error_log.txt in the output dir."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, "error_log.txt")
    with open(log_path, "a", encoding="utf-8") as f:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{now_str}] {msg}\n")

def main():
    print(f"Exporting '{OWNER}/{REPO}' issues (state={STATE}) to PDF with inlined images...")

    total_issues = 0
    # Loop over all issues
    for issue_data in fetch_issues(OWNER, REPO, STATE, GITHUB_TOKEN):
        issue_num = issue_data["number"]
        print(f"\nProcessing Issue #{issue_num}...")

        # Fetch all comments for this issue
        comments = fetch_comments_for_issue(issue_data, GITHUB_TOKEN)

        # Generate PDF (inline images)
        create_issue_pdf(issue_data, comments, token=GITHUB_TOKEN)
        total_issues += 1

    print(f"\nDone! Exported {total_issues} issues to PDF in '{OUTPUT_DIR}'.")

if __name__ == "__main__":
    main()
