"""
Web server for browsing and downloading S3 bucket contents.

Run this on the EC2 instance to serve files via http://kgx-storage.rtx.ai
"""

import boto3
import json
from flask import Flask, render_template_string, request, redirect, send_from_directory
from botocore.exceptions import ClientError
from pathlib import Path

app = Flask(__name__)
BUCKET_NAME = "translator-ingests"
S3_CLIENT = boto3.client("s3")
PUBLIC_DIR = Path(__file__).parent / "public"


def format_size(size_bytes):
    """Format bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_folder_stats(prefix):
    """Get total size and file count for a folder."""
    paginator = S3_CLIENT.get_paginator("list_objects_v2")
    total_size = 0
    file_count = 0
    latest_modified = None

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        for obj in page.get("Contents", []):
            total_size += obj.get("Size", 0)
            file_count += 1
            if latest_modified is None or obj["LastModified"] > latest_modified:
                latest_modified = obj["LastModified"]

    return {
        "size": total_size,
        "size_display": format_size(total_size),
        "file_count": file_count,
        "modified": latest_modified.strftime("%Y-%m-%d %H:%M") if latest_modified else "-"
    }


def list_directory(prefix=""):
    """List contents of a directory (prefix) in S3."""
    folders = []
    files = []

    paginator = S3_CLIENT.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix, Delimiter="/"):
        # Get folders
        for prefix_obj in page.get("CommonPrefixes", []):
            folder_path = prefix_obj["Prefix"]
            folder_name = folder_path[len(prefix):].rstrip("/")
            stats = get_folder_stats(folder_path)
            folders.append({
                "name": folder_name,
                "path": folder_path,
                "size": stats["size"],
                "size_display": stats["size_display"],
                "file_count": stats["file_count"],
                "modified": stats["modified"]
            })

        # Get files
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key == prefix:
                continue
            file_name = key[len(prefix):]
            if "/" not in file_name:
                files.append({
                    "name": file_name,
                    "path": key,
                    "size": obj["Size"],
                    "size_display": format_size(obj["Size"]),
                    "modified": obj["LastModified"].strftime("%Y-%m-%d %H:%M")
                })

    # Sort alphabetically
    folders.sort(key=lambda x: x["name"].lower())
    files.sort(key=lambda x: x["name"].lower())

    return folders, files


def get_presigned_url(s3_key, expiration=3600):
    """Generate a presigned URL for downloading a file."""
    try:
        params = {"Bucket": BUCKET_NAME, "Key": s3_key}
        return S3_CLIENT.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expiration
        )
    except ClientError:
        return None


def get_parent_path(path):
    """Get parent directory path."""
    if not path or path == "/":
        return ""
    path = path.rstrip("/")
    if "/" in path:
        return path.rsplit("/", 1)[0] + "/"
    return ""


def get_breadcrumbs(path):
    """Generate breadcrumb navigation."""
    if not path:
        return []

    parts = path.rstrip("/").split("/")
    breadcrumbs = []
    current = ""

    for part in parts:
        current += part + "/"
        breadcrumbs.append({
            "name": part,
            "path": current
        })

    return breadcrumbs


def browse_directory(path):
    """Shared function to browse a directory path."""
    # Ensure path ends with / for directories
    if path and not path.endswith("/"):
        path += "/"
    
    try:
        folders, files = list_directory(path)
        parent = get_parent_path(path) if path else None
        breadcrumbs = get_breadcrumbs(path)

        # Calculate totals
        total_size = sum(f["size"] for f in folders) + sum(f["size"] for f in files)
        total_files = sum(f["file_count"] for f in folders) + len(files)

        return render_template_string(
            HTML_TEMPLATE,
            path=path,
            parent=parent,
            breadcrumbs=breadcrumbs,
            folders=folders,
            files=files,
            bucket=BUCKET_NAME,
            total_size=format_size(total_size),
            total_files=total_files,
            folder_count=len(folders),
            file_count=len(files)
        )
    except ClientError as e:
        return f"Error: {e}", 500


@app.route("/")
def index():
    """Browse root directory or handle legacy query parameter."""
    # Support legacy ?path= query parameter for backward compatibility
    path = request.args.get("path", "")
    
    # Redirect legacy query parameter URLs to clean URLs
    if path:
        # Ensure path ends with / for directory browsing
        clean_path = path if path.endswith("/") else path + "/"
        return redirect(f"/{clean_path}", code=301)
    
    return browse_directory("")


@app.route("/view/<path:s3_key>")
def view_json(s3_key):
    """View JSON file with syntax highlighting."""
    if not s3_key.lower().endswith('.json'):
        # Non-JSON files go directly to download
        return redirect(f"/download/{s3_key}")

    try:
        # Fetch JSON content from S3
        response = S3_CLIENT.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        json_content = response['Body'].read().decode('utf-8')

        # Parse and pretty-print JSON
        try:
            parsed_json = json.loads(json_content)
            formatted_json = json.dumps(parsed_json, indent=2)
        except json.JSONDecodeError:
            formatted_json = json_content

        # Get file metadata
        file_name = s3_key.split('/')[-1]
        file_size = format_size(response['ContentLength'])
        last_modified = response['LastModified'].strftime("%Y-%m-%d %H:%M:%S")

        # Get download URL
        download_url = get_presigned_url(s3_key)

        # Get parent path for back button
        parent_path = '/'.join(s3_key.split('/')[:-1])
        if parent_path:
            parent_path += '/'

        return render_template_string(
            JSON_VIEWER_TEMPLATE,
            file_name=file_name,
            file_size=file_size,
            last_modified=last_modified,
            json_content=formatted_json,
            download_url=download_url,
            parent_path=parent_path,
            s3_key=s3_key
        )
    except ClientError as e:
        return f"Error loading file: {e}", 500


@app.route("/download/<path:s3_key>")
def download(s3_key):
    """Redirect to presigned download URL."""
    url = get_presigned_url(s3_key)
    if url:
        return redirect(url)
    return "Error generating download URL", 500


@app.route("/docs")
def docs():
    """Documentation page for file access."""
    return render_template_string(DOCS_TEMPLATE, bucket=BUCKET_NAME)


@app.route("/public/<path:filename>")
def serve_public(filename):
    """Serve static files from public directory."""
    return send_from_directory(PUBLIC_DIR, filename)


@app.route("/<path:folder_path>")
def browse_path(folder_path):
    """Browse directory using clean URL path (e.g., /releases/alliance/latest/).
    
    This catch-all route must come AFTER specific routes like /view/, /download/, /docs/, /public/
    to ensure those routes are matched first. Flask matches routes in order of definition.
    
    Note: Paths starting with 'view', 'download', 'docs', or 'public' should not reach here
    unless they have trailing slashes (which would be incorrect usage).
    """
    # Safety check: don't handle paths that should be specific routes
    if folder_path.rstrip("/") in ("view", "download", "docs", "public"):
        return "Not found", 404
    
    # Ensure path ends with / for directories
    if not folder_path.endswith("/"):
        folder_path += "/"
    
    return browse_directory(folder_path)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ path or '/' }} - Translator Ingests</title>
    <style>
        :root {
            --bg: #f4f4f6;
            --surface: #ffffff;
            --surface-hover: #f8f8fa;
            --border: #d4d4d8;
            --text: #1e1e2e;
            --text-dim: #71717a;
            --accent: #7c3aed;
            --accent-hover: #6d28d9;
            --primary: #5b4b8a;
            --primary-dark: #4a3a7a;
            --folder: #7c3aed;
            --file: #71717a;
        }
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }
        .header {
            background: var(--primary);
            border-bottom: 2px solid var(--primary-dark);
            padding: 16px 24px;
        }
        .header-content {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header h1 {
            font-size: 1.1em;
            font-weight: 600;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
            color: #ffffff;
        }
        .header .path {
            font-size: 0.85em;
            color: rgba(255, 255, 255, 0.7);
        }
        .header .path a {
            color: rgba(255, 255, 255, 0.9);
            text-decoration: none;
        }
        .header .path a:hover {
            color: #ffffff;
            text-decoration: underline;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px 24px;
        }
        .toolbar {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 16px;
        }
        .back-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: var(--surface);
            color: var(--text);
            padding: 8px 14px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 0.85em;
            border: 1px solid var(--border);
            transition: all 0.15s;
        }
        .back-btn:hover {
            background: var(--accent);
            color: #ffffff;
            border-color: var(--accent);
        }
        .stats-bar {
            display: flex;
            gap: 24px;
            font-size: 0.8em;
            color: var(--text-dim);
            margin-left: auto;
        }
        .stats-bar span {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .tree {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }
        .tree-header {
            display: grid;
            grid-template-columns: 1fr 100px 140px 140px;
            padding: 12px 16px;
            background: #fafafb;
            border-bottom: 2px solid var(--border);
            font-size: 0.75em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-dim);
        }
        .tree-item {
            display: grid;
            grid-template-columns: 1fr 100px 140px 140px;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            text-decoration: none;
            color: inherit;
            transition: background 0.1s;
        }
        .tree-item:last-child {
            border-bottom: none;
        }
        .tree-item:hover {
            background: var(--surface-hover);
        }
        .tree-name {
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 500;
        }
        .tree-icon {
            font-size: 1.1em;
            width: 20px;
            text-align: center;
        }
        .tree-icon.folder { color: var(--folder); }
        .tree-icon.file { color: var(--file); }
        .tree-size, .tree-count, .tree-date {
            font-size: 0.85em;
            color: var(--text-dim);
            display: flex;
            align-items: center;
        }
        .tree-count {
            font-size: 0.8em;
        }
        .empty {
            padding: 60px 20px;
            text-align: center;
            color: var(--text-dim);
        }
        .empty-icon {
            font-size: 3em;
            margin-bottom: 16px;
            opacity: 0.5;
        }
        .section-label {
            padding: 8px 16px;
            font-size: 0.7em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--accent);
            background: #f8f8fa;
            border-bottom: 1px solid var(--border);
        }
        footer {
            background: var(--surface);
            border-top: 1px solid var(--border);
            margin-top: 60px;
            padding: 20px;
        }
        .footer-content {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            gap: 32px;
        }
        .footer-banner {
            flex-shrink: 0;
        }
        .footer-banner img {
            max-width: 300px;
            height: auto;
        }
        .footer-info {
            flex: 1;
            color: var(--text-dim);
            font-size: 0.75em;
            line-height: 1.6;
            text-align: left;
        }
        .footer-info h3 {
            color: var(--text);
            font-size: 1em;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .footer-info p {
            margin: 6px 0;
        }
        .footer-links {
            margin-top: 8px;
        }
        .footer-links a {
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
        }
        .footer-links a:hover {
            text-decoration: underline;
        }
        @media (max-width: 768px) {
            .tree-header, .tree-item {
                grid-template-columns: 1fr 80px;
            }
            .tree-count, .tree-date {
                display: none;
            }
            .footer-content {
                flex-direction: column;
                text-align: center;
            }
            .footer-info {
                text-align: center;
            }
            .footer-banner img {
                max-width: 200px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h1>KGX STORAGE</h1>
                    <div class="path">
                        <a href="/">s3://{{ bucket }}</a>{% for crumb in breadcrumbs %}/<a href="/{{ crumb.path }}">{{ crumb.name }}</a>{% endfor %}
                    </div>
                </div>
                <div>
                    <a href="/docs" style="color: rgba(255, 255, 255, 0.9); text-decoration: none; font-size: 0.85em; padding: 6px 16px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 4px; transition: all 0.15s;">
                        Documentation
                    </a>
                </div>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="toolbar">
            {% if parent is not none %}
            <a href="/{{ parent }}" class="back-btn">
                <span>&#8592;</span> Back
            </a>
            {% endif %}
            <div class="stats-bar">
                <span>{{ folder_count }} folders</span>
                <span>{{ file_count }} files</span>
                <span>{{ total_size }} total</span>
            </div>
        </div>

        <div class="tree">
            <div class="tree-header">
                <span>Name</span>
                <span>Size</span>
                <span>Items</span>
                <span>Modified</span>
            </div>

            {% if not folders and not files %}
            <div class="empty">
                <div class="empty-icon">&#128193;</div>
                <p>This folder is empty</p>
            </div>
            {% endif %}

            {% if folders %}
            <div class="section-label">Folders</div>
            {% for folder in folders %}
            <a href="/{{ folder.path }}" class="tree-item">
                <span class="tree-name">
                    <span class="tree-icon folder">&#128193;</span>
                    {{ folder.name }}
                </span>
                <span class="tree-size">{{ folder.size_display }}</span>
                <span class="tree-count">{{ folder.file_count }} files</span>
                <span class="tree-date">{{ folder.modified }}</span>
            </a>
            {% endfor %}
            {% endif %}

            {% if files %}
            <div class="section-label">Files</div>
            {% for file in files %}
            <a href="{% if file.name.lower().endswith('.json') %}/view/{{ file.path }}{% else %}/download/{{ file.path }}{% endif %}" class="tree-item">
                <span class="tree-name">
                    <span class="tree-icon file">&#128196;</span>
                    {{ file.name }}
                </span>
                <span class="tree-size">{{ file.size_display }}</span>
                <span class="tree-count">-</span>
                <span class="tree-date">{{ file.modified }}</span>
            </a>
            {% endfor %}
            {% endif %}
        </div>
    </div>

    <footer>
        <div class="footer-content">
            <div class="footer-banner">
                <img src="/public/ncats-banner.png" alt="NCATS Translator">
            </div>
            <div class="footer-info">
                <h3>KGX Storage Component</h3>
                <p>This interface provides access to KGX (Knowledge Graph Exchange) format outputs stored in the S3 bucket for the NCATS Biomedical Data Translator project. Browse and download knowledge graph data files including nodes, edges, and metadata from various biomedical data sources processed through the Translator Ingests pipeline.</p>
                <div class="footer-links">
                    <a href="/docs">File Access Documentation</a> • 
                    <a href="https://github.com/NCATSTranslator/translator-ingests" target="_blank">View Source Code on GitHub</a>
                </div>
            </div>
        </div>
    </footer>
</body>
</html>
"""


JSON_VIEWER_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ file_name }} - Translator Ingests</title>
    <style>
        :root {
            --bg: #f4f4f6;
            --surface: #ffffff;
            --surface-hover: #f8f8fa;
            --border: #d4d4d8;
            --text: #1e1e2e;
            --text-dim: #71717a;
            --accent: #7c3aed;
            --accent-hover: #6d28d9;
            --primary: #5b4b8a;
            --primary-dark: #4a3a7a;
        }
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }
        .header {
            background: var(--primary);
            border-bottom: 2px solid var(--primary-dark);
            padding: 16px 24px;
        }
        .header-content {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header h1 {
            font-size: 1.1em;
            font-weight: 600;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
            color: #ffffff;
        }
        .header .path {
            font-size: 0.85em;
            color: rgba(255, 255, 255, 0.7);
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px 24px;
        }
        .toolbar {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: var(--surface);
            color: var(--text);
            padding: 8px 16px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 0.85em;
            border: 1px solid var(--border);
            transition: all 0.15s;
            cursor: pointer;
        }
        .btn:hover {
            background: var(--accent);
            color: #ffffff;
            border-color: var(--accent);
        }
        .btn-primary {
            background: var(--accent);
            color: #ffffff;
            border-color: var(--accent);
        }
        .btn-primary:hover {
            background: var(--accent-hover);
            border-color: var(--accent-hover);
        }
        .file-info {
            display: flex;
            gap: 24px;
            font-size: 0.8em;
            color: var(--text-dim);
            margin-left: auto;
        }
        .file-info span {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .viewer-container {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }
        .viewer-header {
            padding: 12px 16px;
            background: #fafafb;
            border-bottom: 2px solid var(--border);
            font-size: 0.85em;
            font-weight: 600;
            color: var(--text);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .copy-btn {
            padding: 4px 12px;
            font-size: 0.9em;
            background: var(--surface);
        }
        .json-content {
            padding: 20px;
            overflow-x: auto;
            max-height: calc(100vh - 280px);
            overflow-y: auto;
        }
        pre {
            margin: 0;
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
            font-size: 0.85em;
            line-height: 1.5;
        }
        code {
            display: block;
        }
        /* JSON Syntax Highlighting */
        .json-key { color: #0451a5; font-weight: 500; }
        .json-string { color: #a31515; }
        .json-number { color: #098658; }
        .json-boolean { color: #0000ff; font-weight: 600; }
        .json-null { color: #0000ff; font-weight: 600; }
        .json-punctuation { color: #000000; }
        @media (max-width: 768px) {
            .file-info {
                width: 100%;
                margin-left: 0;
                margin-top: 8px;
            }
            .json-content {
                font-size: 0.75em;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h1>KGX STORAGE</h1>
                    <div class="path">{{ file_name }}</div>
                </div>
                <div>
                    <a href="/docs" style="color: rgba(255, 255, 255, 0.9); text-decoration: none; font-size: 0.85em; padding: 6px 16px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 4px; transition: all 0.15s;">
                        Documentation
                    </a>
                </div>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="toolbar">
            <a href="/{{ parent_path }}" class="btn">
                <span>&#8592;</span> Back to Folder
            </a>
            <a href="{{ download_url }}" class="btn btn-primary" download>
                <span>&#8595;</span> Download File
            </a>
            <div class="file-info">
                <span><strong>Size:</strong> {{ file_size }}</span>
                <span><strong>Modified:</strong> {{ last_modified }}</span>
            </div>
        </div>

        <div class="viewer-container">
            <div class="viewer-header">
                <span>JSON Content</span>
            </div>
            <div class="json-content">
                <pre><code id="json-code">{{ json_content }}</code></pre>
            </div>
        </div>
    </div>

    <script>
        // Syntax highlighting
        function highlightJSON() {
            const codeElement = document.getElementById('json-code');
            let text = codeElement.textContent;

            // Escape HTML
            text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

            // Highlight different JSON elements
            text = text.replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:');
            text = text.replace(/: "([^"]*)"/g, ': <span class="json-string">"$1"</span>');
            text = text.replace(/: (-?\d+\.?\d*)/g, ': <span class="json-number">$1</span>');
            text = text.replace(/: (true|false)/g, ': <span class="json-boolean">$1</span>');
            text = text.replace(/: (null)/g, ': <span class="json-null">$1</span>');

            codeElement.innerHTML = text;
        }

        // Copy to clipboard
        function copyToClipboard() {
            const code = document.getElementById('json-code').textContent;
            navigator.clipboard.writeText(code).then(() => {
                const icon = document.getElementById('copy-icon');
                const btn = icon.parentElement;
                const originalText = btn.innerHTML;
                btn.innerHTML = '<span>&#10003;</span> Copied!';
                btn.style.background = '#10b981';
                btn.style.color = '#ffffff';
                btn.style.borderColor = '#10b981';
                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.style.background = '';
                    btn.style.color = '';
                    btn.style.borderColor = '';
                }, 2000);
            }).catch(err => {
                alert('Failed to copy to clipboard');
            });
        }

        // Apply syntax highlighting on load
        highlightJSON();
    </script>
</body>
</html>
"""


DOCS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download Files - KGX Storage</title>
    <style>
        :root {
            --bg: #f4f4f6;
            --surface: #ffffff;
            --text: #1e1e2e;
            --text-dim: #71717a;
            --accent: #7c3aed;
            --primary: #5b4b8a;
        }
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }
        .header {
            background: var(--primary);
            padding: 16px 24px;
        }
        .header-content {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 1.1em;
            font-weight: 600;
            letter-spacing: 0.5px;
            color: #ffffff;
        }
        .header-nav a {
            color: rgba(255, 255, 255, 0.9);
            text-decoration: none;
            font-size: 0.85em;
            padding: 6px 12px;
            transition: all 0.15s;
        }
        .header-nav a:hover {
            color: #ffffff;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 24px;
        }
        h2 {
            font-size: 1.4em;
            font-weight: 600;
            margin: 40px 0 20px 0;
            color: var(--primary);
        }
        .intro {
            font-size: 1em;
            color: var(--text-dim);
            margin-bottom: 40px;
        }
        .cmd-block {
            background: #2d2d2d;
            color: #e5e7eb;
            padding: 16px 20px;
            margin: 12px 0;
            font-size: 0.9em;
            cursor: pointer;
            transition: all 0.2s;
            position: relative;
        }
        .cmd-block:hover {
            background: #3a3a3a;
        }
        .cmd-block::after {
            content: 'click to copy';
            position: absolute;
            right: 20px;
            top: 16px;
            font-size: 0.75em;
            color: var(--accent);
            opacity: 0;
            transition: opacity 0.2s;
        }
        .cmd-block:hover::after {
            opacity: 1;
        }
        .cmd-block.copied::after {
            content: 'copied!';
            color: #10b981;
            opacity: 1;
        }
        .cmd-label {
            font-size: 0.8em;
            color: var(--accent);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin: 20px 0 8px 0;
            font-weight: 500;
        }
        .note {
            font-size: 0.85em;
            color: var(--text-dim);
            margin: 8px 0 20px 0;
            font-style: italic;
        }
        .path {
            color: var(--accent);
            font-family: monospace;
            font-size: 0.9em;
            display: block;
            margin: 8px 0;
        }
        @media (max-width: 768px) {
            .header-content {
                flex-direction: column;
                align-items: flex-start;
                gap: 12px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <h1>KGX STORAGE</h1>
            <div class="header-nav">
                <a href="/">Browse Files</a>
            </div>
        </div>
    </div>

    <div class="container">
        <p class="intro">Download knowledge graph files via HTTPS or S3. Both methods are publicly accessible without authentication.</p>

        <h2>HTTPS Download</h2>
        
        <div class="cmd-label">Single File</div>
        <div class="cmd-block" onclick="copy(this)">curl -O "https://kgx-storage.rtx.ai/download/releases/go_cam/latest/go_cam.tar.zst"</div>
        <p class="note">Replace go_cam with your source name</p>
        
        <div class="cmd-label">Specific Version</div>
        <div class="cmd-block" onclick="copy(this)">curl -O "https://kgx-storage.rtx.ai/download/data/ctd/November_2025/1.0/normalization_2025sep1/merged_nodes.jsonl"</div>
        
        <div class="cmd-label">With wget</div>
        <div class="cmd-block" onclick="copy(this)">wget "https://kgx-storage.rtx.ai/download/releases/alliance/latest/alliance.tar.zst"</div>

        <h2>S3 Download</h2>
        <p class="note">Requires AWS CLI installed locally</p>
        
        <div class="cmd-label">Install AWS CLI</div>
        <div class="cmd-block" onclick="copy(this)">brew install awscli</div>
        <p class="note">macOS</p>
        <div class="cmd-block" onclick="copy(this)">sudo apt install awscli</div>
        <p class="note">Ubuntu/Debian</p>
        
        <div class="cmd-label">Single File</div>
        <div class="cmd-block" onclick="copy(this)">aws s3 cp s3://{{ bucket }}/releases/go_cam/latest/go_cam.tar.zst . --no-sign-request</div>
        <p class="note">No AWS credentials required with --no-sign-request</p>
        
        <div class="cmd-label">Entire Directory (Recursively)</div>
        <div class="cmd-block" onclick="copy(this)">aws s3 sync s3://{{ bucket }}/releases/alliance/latest/ ./alliance/ --no-sign-request</div>
        <p class="note">Downloads all files in directory</p>
        
        <div class="cmd-label">List Available Files</div>
        <div class="cmd-block" onclick="copy(this)">aws s3 ls s3://{{ bucket }}/releases/ --no-sign-request</div>

        <h2>Common Paths</h2>
        
        <div class="cmd-label">Latest Release</div>
        <span class="path">releases/{source}/latest/{source}.tar.zst</span>
        
        <div class="cmd-label">Merged Files</div>
        <span class="path">data/{source}/{version}/{transform}/normalization_{norm}/merged_nodes.jsonl</span>
        <span class="path">data/{source}/{version}/{transform}/normalization_{norm}/merged_edges.jsonl</span>
        
        <div class="cmd-label">Metadata</div>
        <span class="path">data/{source}/latest-build.json</span>
        <span class="path">releases/{source}/latest/graph-metadata.json</span>

        <h2>Extract Archives</h2>
        
        <div class="cmd-label">Install zstd</div>
        <div class="cmd-block" onclick="copy(this)">brew install zstd</div>
        <p class="note">macOS</p>
        <div class="cmd-block" onclick="copy(this)">sudo apt install zstd</div>
        <p class="note">Ubuntu/Debian</p>
        
        <div class="cmd-label">Extract .tar.zst</div>
        <div class="cmd-block" onclick="copy(this)">tar --use-compress-program=zstd -xvf go_cam.tar.zst</div>
    </div>

    <script>
        function copy(el) {
            navigator.clipboard.writeText(el.textContent.trim()).then(() => {
                el.classList.add('copied');
                setTimeout(() => el.classList.remove('copied'), 2000);
            });
        }
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
