import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.ingestion.models import OrangeBookProduct

PRODUCTS_FILENAME = "products.txt"

csv.field_size_limit(10**7)

# NDC application_number looks like "ANDA211106" / "NDA021436" / "BLA125085";
# Orange Book stores Appl_Type ("A"/"N"/"B") + Appl_No ("211106") separately.
_APPL_RE = re.compile(r"^(ANDA|NDA|BLA)0*(\d+)$", re.IGNORECASE)
_TYPE_TO_LETTER = {"ANDA": "A", "NDA": "N", "BLA": "B"}


def application_key(appl_type: str, appl_no: str) -> str:
    """Canonical join key from an Orange Book row, e.g. ('A', '00211106') -> 'A211106'."""
    return f"{appl_type.strip().upper()}{appl_no.strip().lstrip('0')}"


def ndc_application_key(application_number: str | None) -> str | None:
    """Canonical join key from an NDC application_number, or None if not applicable."""
    if not application_number:
        return None
    m = _APPL_RE.match(application_number.strip())
    if not m:
        return None
    return f"{_TYPE_TO_LETTER[m.group(1).upper()]}{m.group(2).lstrip('0')}"


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
            f"{path} not found. See data/MANUAL_DOWNLOADS.md for how to fetch it."
        )
    return parse_products_file(path)


def _te_group(product: OrangeBookProduct) -> str | None:
    """A key shared by therapeutically-equivalent products (substitutable).

    Same active ingredient + dosage form/route + TE class (the letter, e.g. "AB")
    means the products are rated interchangeable.
    """
    if not product.te_code:
        return None
    ingredient = product.ingredient.strip().upper()
    return f"{ingredient}|{product.df_route.strip().upper()}|{product.te_code.strip()}"


@dataclass
class OrangeBookEntry:
    """Aggregated Orange Book facts for one FDA application, keyed by application_key."""

    te_codes: set[str] = field(default_factory=set)
    te_groups: set[str] = field(default_factory=set)
    is_rld: bool = False  # reference listed drug (the brand alternatives reference)
    rx_otc: str = ""  # RX / OTC / DISCN


def build_orange_book_index(products: list[OrangeBookProduct]) -> dict[str, OrangeBookEntry]:
    """Index Orange Book products by application_key for joining to NDC drugs."""
    index: dict[str, OrangeBookEntry] = {}
    for p in products:
        key = application_key(p.appl_type, p.appl_no)
        entry = index.setdefault(key, OrangeBookEntry())
        if p.te_code:
            entry.te_codes.add(p.te_code.strip())
        group = _te_group(p)
        if group:
            entry.te_groups.add(group)
        if (p.type or "").strip().upper() and not entry.rx_otc:
            entry.rx_otc = p.type.strip().upper()
        # RLD column isn't on the model; treat presence of an NDA (originator) as a hint.
    return index


def load_orange_book_index() -> dict[str, OrangeBookEntry]:
    return build_orange_book_index(load_orange_book_products())
