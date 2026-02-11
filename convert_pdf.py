#!/usr/bin/env python3
"""Convert PLAN.md to PDF with proper Unicode box-drawing support."""

import markdown
from weasyprint import HTML

with open("PLAN.md", "r") as f:
    md_content = f.read()

html_body = markdown.markdown(
    md_content,
    extensions=["tables", "fenced_code"],
)

html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 2cm;
  }}
  body {{
    font-family: "DejaVu Sans", "Noto Sans", "Liberation Sans", sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #1a1a1a;
  }}
  h1 {{
    font-size: 22pt;
    border-bottom: 2px solid #333;
    padding-bottom: 8px;
    margin-top: 0;
  }}
  h2 {{
    font-size: 16pt;
    border-bottom: 1px solid #999;
    padding-bottom: 4px;
    margin-top: 24pt;
  }}
  h3 {{
    font-size: 13pt;
    margin-top: 18pt;
  }}
  h4 {{
    font-size: 11pt;
    margin-top: 14pt;
  }}
  pre {{
    background-color: #f5f5f5;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 12px;
    font-size: 7pt;
    line-height: 1.3;
    overflow-x: auto;
    white-space: pre;
  }}
  code {{
    font-family: "DejaVu Sans Mono", "Noto Sans Mono", "Liberation Mono", "Courier New", monospace;
  }}
  pre code {{
    font-family: "DejaVu Sans Mono", "Noto Sans Mono", "Liberation Mono", "Courier New", monospace;
    font-size: 7pt;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 10pt;
  }}
  th, td {{
    border: 1px solid #ccc;
    padding: 6px 10px;
    text-align: left;
  }}
  th {{
    background-color: #f0f0f0;
    font-weight: bold;
  }}
  tr:nth-child(even) {{
    background-color: #fafafa;
  }}
  hr {{
    border: none;
    border-top: 1px solid #ccc;
    margin: 20px 0;
  }}
  ul, ol {{
    margin: 8px 0;
  }}
  li {{
    margin: 4px 0;
  }}
  strong {{
    color: #111;
  }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

HTML(string=html_doc).write_pdf("PLAN.pdf")
print("PLAN.pdf generated successfully.")
