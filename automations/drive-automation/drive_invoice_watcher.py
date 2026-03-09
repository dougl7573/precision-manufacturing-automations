#!/usr/bin/env python3
"""
Drive Invoice Watcher (Lesson 2.3).
Watches a Google Drive folder for new PDF invoices, processes them with the
Lesson 2.2 pipeline, and moves them to a "Processed" folder.
"""

import argparse
import io
import logging
import os
import sys
import tempfile
import time

# Load config and ensure pipeline is importable
import config

if not os.path.isdir(config.PIPELINE_DIR):
    raise SystemExit(f"Pipeline directory not found: {config.PIPELINE_DIR}")

sys.path.insert(0, os.path.abspath(config.PIPELINE_DIR))

# Google Drive API
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_PATH = os.path.join(config.SCRIPT_DIR, "credentials.json")
TOKEN_PATH = os.path.join(config.SCRIPT_DIR, "token.json")


def setup_logging():
    """Configure logging to file and console."""
    log_path = os.path.join(config.SCRIPT_DIR, config.LOG_FILE)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


logger = setup_logging()


def authenticate_drive():
    """Authenticate with Google Drive; create token.json on first run."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"Put OAuth credentials in {CREDENTIALS_PATH} (Google Cloud Console → OAuth client → Desktop app)"
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


def list_pdfs_in_folder(service, folder_id):
    """List PDF files in the given Drive folder."""
    if not folder_id:
        return []
    q = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
    results = (
        service.files()
        .list(q=q, spaces="drive", fields="files(id, name)", orderBy="createdTime")
        .execute()
    )
    return results.get("files", [])


def download_file(service, file_id, destination_path):
    """Download a Drive file by ID to a local path."""
    request = service.files().get_media(fileId=file_id)
    with io.FileIO(destination_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return True


def move_file_to_folder(service, file_id, new_folder_id):
    """Move a Drive file to another folder."""
    file_meta = service.files().get(fileId=file_id, fields="parents").execute()
    previous_parents = ",".join(file_meta.get("parents", []))
    service.files().update(
        fileId=file_id,
        addParents=new_folder_id,
        removeParents=previous_parents,
    ).execute()
    return True


def process_invoice_pdf(pdf_path):
    """Run the Lesson 2.2 pipeline on a PDF. Returns True if successful."""
    import invoice_pipeline
    return invoice_pipeline.process_invoice(
        invoice_file=pdf_path,
        vendor_file=config.VENDOR_LIST_PATH,
    )


def run_once(service):
    """Check folder once: download each PDF, process, move if success."""
    if not config.TO_PROCESS_FOLDER_ID or not config.PROCESSED_FOLDER_ID:
        logger.warning("TO_PROCESS_FOLDER_ID or PROCESSED_FOLDER_ID not set in config. Set them in config.py or env.")
        return

    files = list_pdfs_in_folder(service, config.TO_PROCESS_FOLDER_ID)
    if not files:
        logger.info("No new PDFs in folder.")
        return

    logger.info("Found %d PDF(s) to process.", len(files))

    with tempfile.TemporaryDirectory() as tmpdir:
        for f in files:
            file_id, name = f["id"], f["name"]
            path = os.path.join(tmpdir, name)
            try:
                logger.info("Downloading: %s", name)
                download_file(service, file_id, path)
            except Exception as e:
                logger.error("Download failed for %s: %s", name, e)
                continue

            try:
                success = process_invoice_pdf(path)
                if success:
                    logger.info("Processing succeeded. Moving to Processed: %s", name)
                    move_file_to_folder(service, file_id, config.PROCESSED_FOLDER_ID)
                else:
                    logger.warning("Processing failed; leaving file in To Process: %s", name)
            except Exception as e:
                logger.exception("Error processing %s: %s", name, e)


def main():
    parser = argparse.ArgumentParser(description="Watch Drive folder and process invoice PDFs.")
    parser.add_argument("--once", action="store_true", help="Run once and exit; otherwise run every %s seconds." % config.CHECK_INTERVAL_SECONDS, default=False)
    args = parser.parse_args()

    logger.info("Drive Invoice Watcher starting.")
    service = authenticate_drive()

    if args.once:
        run_once(service)
        logger.info("Done (--once).")
        return

    while True:
        run_once(service)
        logger.info("Waiting %s seconds before next check.", config.CHECK_INTERVAL_SECONDS)
        time.sleep(config.CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
