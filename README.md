# Github-Issue-to-PDF-Generator

## Purpose
Generates PDF records of github issues

## Requirements
- $ pip install requests pdfkit markdown2 beautifulsoup4
- $ sudo apt-get install wkhtmltopdf

## Setup
- Set Github Token
  - $ export GITHUB_TOKEN=ghp_1234567...

## Set repo
- Adjust the "OWNER" and "REPO" in the configuration section of the script

## Run
- $ python GitHub-issues-to-pdf.py
