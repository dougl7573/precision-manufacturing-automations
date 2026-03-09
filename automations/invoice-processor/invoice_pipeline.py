#!/usr/bin/env python3
"""Full invoice pipeline: load JSON or PDF → validate → check vendor → transform → create Airtable record."""

import json
import os
import sys

from validate_invoice import load_invoice, validate_invoice_math
from parse_vendors import search_vendor
from transform_invoice import transform_invoice_for_airtable
from airtable_test import create_invoice
from extract_invoice_pdf import extract_invoice_from_pdf

INVOICE_FILE = "sample-invoice-data.json"
VENDOR_FILE = "vendor-list.csv"


def load_invoice_from_file(path: str):
    """Load invoice from JSON file or extract from PDF."""
    if path.lower().endswith(".pdf"):
        return extract_invoice_from_pdf(path)
    return load_invoice(path)


def lookup_vendor(vendor_name, csv_file):
    """Check if vendor is in approved list (exact match, or prefix match for course PDFs)."""
    match_type, result = search_vendor(vendor_name, csv_file)
    if match_type == "exact":
        return {"found": True, "active": result.get("active", "TRUE") == "TRUE", "id": result["id"], "terms": result["terms"]}
    # Prefix match: e.g. "Widget Supplies" → "Widget Supplies Inc"
    if match_type == "starts_with" and isinstance(result, list):
        v_lower = vendor_name.strip().lower()
        words = v_lower.split()
        prefix = " ".join(words[:2]) if len(words) >= 2 else v_lower  # first 2 words
        for v in result:
            n = v["name"].lower()
            if n.startswith(v_lower) or v_lower in n or (len(prefix) >= 3 and prefix in n):
                return {"found": True, "active": v.get("active", "TRUE") == "TRUE", "id": v["id"], "terms": v["terms"]}
    return {"found": False}


def process_invoice(invoice_file=INVOICE_FILE, vendor_file=VENDOR_FILE):
    """Run the full pipeline: load (JSON or PDF) → validate → vendor check → transform → create."""
    print("=" * 50)
    print("INVOICE PROCESSING PIPELINE")
    print("=" * 50)

    # 1. Load invoice (from JSON or PDF)
    print("\n[1/5] Loading invoice...")
    invoice = load_invoice_from_file(invoice_file)
    print(f"  ✓ Loaded: {invoice['invoice_number']} from {invoice['vendor_name']}")

    # 2. Validate math
    print("\n[2/5] Validating invoice math...")
    errors = validate_invoice_math(invoice)
    if errors:
        print("  ✗ VALIDATION FAILED:")
        for err in errors:
            print(f"    - {err}")
        return False
    print(f"  ✓ Math is correct (Total: ${invoice['total_amount']})")

    # 3. Check vendor
    print("\n[3/5] Checking vendor...")
    vendor_check = lookup_vendor(invoice["vendor_name"], vendor_file)
    if not vendor_check["found"]:
        print("  ✗ Vendor not found in approved list!")
        return False
    if not vendor_check["active"]:
        print("  ⚠ Warning: Vendor is INACTIVE!")
    print(f"  ✓ Vendor found: {vendor_check['id']} ({vendor_check['terms']})")

    # 4. Transform for Airtable
    print("\n[4/5] Transforming for Airtable...")
    airtable_data = transform_invoice_for_airtable(invoice)
    # If your Airtable Notes field rejects this, we can omit it
    if "Notes" in airtable_data and len(airtable_data["Notes"]) > 100000:
        airtable_data.pop("Notes", None)  # Airtable long text limit
    print("  ✓ Data transformed")

    # 5. Create record in Airtable
    print("\n[5/5] Creating Airtable record...")
    result = create_invoice(airtable_data)
    if result is None and "Notes" in airtable_data:
        # Retry without Notes if your Airtable field has restrictions
        airtable_data_no_notes = {k: v for k, v in airtable_data.items() if k != "Notes"}
        result = create_invoice(airtable_data_no_notes)
    if result:
        print("  ✓ Record created successfully!")
        print("\n" + "=" * 50)
        print("INVOICE PROCESSED SUCCESSFULLY")
        print("=" * 50)
        return True
    print("  ✗ Failed to create record")
    return False


def process_all_pdfs(folder_path: str, vendor_file: str = VENDOR_FILE):
    """Process all PDF files in a folder. Returns list of {path, filename, success, error}."""
    if not os.path.isdir(folder_path):
        return []
    pdfs = sorted(
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith(".pdf")
    )
    results = []
    for path in pdfs:
        name = os.path.basename(path)
        try:
            ok = process_invoice(invoice_file=path, vendor_file=vendor_file)
            results.append({"path": path, "filename": name, "success": ok, "error": None})
        except Exception as e:
            results.append({"path": path, "filename": name, "success": False, "error": str(e)})
    return results


if __name__ == "__main__":
    # Batch mode: pass a folder to process all PDFs in it
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if os.path.isdir(arg):
            print("BATCH MODE: processing all PDFs in", arg, "\n")
            results = process_all_pdfs(arg)
            successful = sum(1 for r in results if r["success"])
            failed = len(results) - successful
            print("\n" + "=" * 50)
            print("PROCESSING SUMMARY")
            print("=" * 50)
            print(f"Total: {len(results)}  Successful: {successful}  Failed: {failed}")
            for r in results:
                status = "✓" if r["success"] else "✗"
                print(f"  {status} {r['filename']}")
                if r.get("error"):
                    print(f"      {r['error']}")
            print("=" * 50)
            sys.exit(0 if failed == 0 else 1)
        invoice_path = arg
    else:
        invoice_path = INVOICE_FILE

    ok = process_invoice(invoice_file=invoice_path)
    if ok:
        print("\n✓ Check Airtable to see the new invoice!")
    else:
        print("\n✗ Processing failed — check errors above.")
        sys.exit(1)
