"""Document reading with Azure Document Intelligence (prebuilt read model), for digital and scanned PDFs."""
import json
import time
import urllib.request
from pathlib import Path

from . import config

API_VERSION = "2024-11-30"
READER = "azure-document-intelligence/prebuilt-read"


def read_pages(path):
    """Return the text of each page of a PDF."""
    endpoint = config.setting("AZURE_AI_ENDPOINT").rstrip("/")
    headers = {"Ocp-Apim-Subscription-Key": config.setting("AZURE_AI_KEY")}
    url = f"{endpoint}/documentintelligence/documentModels/prebuilt-read:analyze?api-version={API_VERSION}"
    request = urllib.request.Request(
        url, data=Path(path).read_bytes(), headers={**headers, "Content-Type": "application/pdf"}, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        operation = response.headers["Operation-Location"]

    for _ in range(120):
        with urllib.request.urlopen(urllib.request.Request(operation, headers=headers), timeout=60) as response:
            result = json.load(response)
        if result["status"] == "succeeded":
            return ["\n".join(line["content"] for line in page.get("lines", []))
                    for page in result["analyzeResult"]["pages"]]
        if result["status"] == "failed":
            raise RuntimeError(f"OCR failed for {path}: {result.get('error')}")
        time.sleep(2)
    raise TimeoutError(f"OCR timed out for {path}")
