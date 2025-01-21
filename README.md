# Github-Issue-to-PDF-Generator

## Purpose
Generates PDF records of github issues

## Requirements
- $ pip install requests pdfkit markdown2 beautifulsoup4
- $ sudo apt-get install wkhtmltopdf

## Setup
- Create a [Github personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) (fine grained access token recommended)
   - Enable access to issues
   - If you have an organization you may need to [enable access](https://docs.github.com/en/organizations/managing-programmatic-access-to-your-organization/setting-a-personal-access-token-policy-for-your-organization).
- Set Github Token in your terminal environment
  - $ export GITHUB_TOKEN="ghp_1234567..."

## Set repo
- Edit the "OWNER" and "REPO" in the configuration section of the script
   - Save the changes

## Run
- $ python Github-Issue-to-PDF.py
