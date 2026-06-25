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
    """One registered drug establishment (DECRS drls_reg export)."""

    fei_number: str
    firm_name: str
    canonical_name: str
    address: str
    city: str
    state: str  # US 2-letter code, "" if foreign/unknown
    country: str  # 3-letter code (USA, IND, ...)
    is_foreign: bool
    operations: list[str]  # MANUFACTURE, API MANUFACTURE, REPACK, RELABEL, ...
    is_manufacturer: bool  # performs (API) MANUFACTURE
    is_repackager: bool  # performs REPACK/RELABEL but not MANUFACTURE
    expiration_date: str | None
    registrant_name: str | None


class DistributorRecord(BaseModel):
    """One licensed wholesale distributor / 3PL, aggregated across the DSCSA
    per-state reporting exports (one entity, all the states it's licensed in)."""

    license_number: str  # a representative license number
    name: str
    canonical_name: str
    distributor_type: str  # "wholesale_distributor" | "third_party_logistics"
    home_state: str
    city: str
    states_licensed: list[str]
    national_coverage: bool
    license_count: int  # how many state licenses back this entity


class GeographyRecord(BaseModel):
    """One US state/territory node."""

    state_code: str
    name: str
    centroid_lat: float
    centroid_lng: float
    region: str
