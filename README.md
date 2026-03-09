# Precision Manufacturing Invoice Automations

A portfolio of three real-world automations built for Precision Manufacturing’s Finance team.

## 🚀 What’s Included

### 1. PDF Invoice Processor (Local Script)
**Folder:** `automations/invoice-processor/`

- Processes a folder of PDF invoices.
- Extracts invoice number, vendor, date, amount.
- Sends records to Airtable.

### 2. Google Drive Invoice Automation
**Folder:** `automations/drive-automation/`

- Watches a Google Drive folder for new PDFs.
- Automatically runs the invoice processor.
- Archives processed files.

### 3. Invoice Upload Web App
**Folder:** `automations/invoice-webapp/`  
**Live URL:** `https://YOUR-VERCEL-URL.vercel.app`  
**Web app repo:** `https://github.com/dougl7573/invoice-upload-webapp`

- Finance can upload a single PDF in the browser.
- Shows extracted data for review.
- Saves to Airtable with one click.

## 🧰 Tech Stack

- Python (scripts and backend)
- Flask (web app backend)
- Airtable API
- Google Drive API
- Vercel (web app hosting)
- Git & GitHub (version control and portfolio)

## 📦 How to Use This Repo

1. Clone:

   ```bash
   git clone https://github.com/dougl7573/precision-manufacturing-automations.git
   cd precision-manufacturing-automations
