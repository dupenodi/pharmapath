import csv
from pathlib import Path

from app.core.config import settings
from app.ingestion.models import OrangeBookProduct

PRODUCTS_FILENAME = "products.txt"


def products_file_path() -> Path:
    return settings.raw_data_dir / "orange_book" / PRODUCTS_FILENAME


def parse_products_file(path: Path) -> list[OrangeBookProduct]:
    """Parses the Orange Book products.txt (tilde-delimited, header row included)."""
    with path.open(encoding="latin-1", newline="") as f:
        reader = csv.DictReader(f, delimiter="~")
        return [
            OrangeBookProduct(
                ingredient=row["Ingredient"],
                df_route=row["DF;Route"],
                trade_name=row["Trade_Name"],
                applicant=row["Applicant"],
                strength=row["Strength"],
                appl_type=row["Appl_Type"],
                appl_no=row["Appl_No"],
                product_no=row["Product_No"],
                te_code=row.get("TE_Code") or None,
                approval_date=row.get("Approval_Date") or None,
                type=row["Type"],
                applicant_full_name=row["Applicant_Full_Name"],
            )
            for row in reader
        ]


def load_orange_book_products() -> list[OrangeBookProduct]:
    path = products_file_path()
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. See data/raw/MANUAL_DOWNLOADS.md for how to fetch it."
        )
    return parse_products_file(path)
