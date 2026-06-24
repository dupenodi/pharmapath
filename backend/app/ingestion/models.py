from pydantic import BaseModel


class NdcRecord(BaseModel):
    """One normalized record from the openFDA NDC bulk directory.

    Source: https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip
    """

    product_id: str
    product_ndc: str
    generic_name: str
    brand_name: str | None
    dosage_form: str | None
    route: list[str]
    labeler_name: str
    substance_name: list[str]
    application_number: str | None
    product_type: str | None
    marketing_category: str | None
    finished: bool
    listing_expiration_date: str | None
    active_ingredient_strengths: list[str]


class OrangeBookProduct(BaseModel):
    """One row from the Orange Book product.txt (tilde-delimited)."""

    ingredient: str
    df_route: str
    trade_name: str
    applicant: str
    strength: str
    appl_type: str
    appl_no: str
    product_no: str
    te_code: str | None
    approval_date: str | None
    type: str
    applicant_full_name: str


class FacilityRecord(BaseModel):
    """One registered drug manufacturing facility (DECRS)."""

    fei_number: str
    firm_name: str
    address: str
    city: str
    state: str
    zip_code: str
    country: str
    registration_status: str
    facility_types: list[str]


class DistributorRecord(BaseModel):
    """One licensed wholesale distributor / 3PL (DSCSA annual reporting)."""

    license_number: str
    name: str
    distributor_type: str  # "wholesale_distributor" | "third_party_logistics"
    home_state: str
    city: str
    states_licensed: list[str]
    national_coverage: bool
