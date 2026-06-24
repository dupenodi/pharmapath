from app.ingestion.models import GeographyRecord

# Approximate geographic-center lat/lng per state, US Census region groupings.
# Real public data (not fabricated) -- precision is adequate for the haversine
# distance bands used by the matching engine's location score.
_STATES: list[tuple[str, str, float, float, str]] = [
    ("AL", "Alabama", 32.806671, -86.791130, "south"),
    ("AK", "Alaska", 61.370716, -152.404419, "west"),
    ("AZ", "Arizona", 33.729759, -111.431221, "west"),
    ("AR", "Arkansas", 34.969704, -92.373123, "south"),
    ("CA", "California", 36.116203, -119.681564, "west"),
    ("CO", "Colorado", 39.059811, -105.311104, "west"),
    ("CT", "Connecticut", 41.597782, -72.755371, "northeast"),
    ("DE", "Delaware", 39.318523, -75.507141, "northeast"),
    ("DC", "District of Columbia", 38.897438, -77.026817, "northeast"),
    ("FL", "Florida", 27.766279, -81.686783, "south"),
    ("GA", "Georgia", 33.040619, -83.643074, "south"),
    ("HI", "Hawaii", 21.094318, -157.498337, "west"),
    ("ID", "Idaho", 44.240459, -114.478828, "west"),
    ("IL", "Illinois", 40.349457, -88.986137, "midwest"),
    ("IN", "Indiana", 39.849426, -86.258278, "midwest"),
    ("IA", "Iowa", 42.011539, -93.210526, "midwest"),
    ("KS", "Kansas", 38.526600, -96.726486, "midwest"),
    ("KY", "Kentucky", 37.668140, -84.670067, "south"),
    ("LA", "Louisiana", 31.169546, -91.867805, "south"),
    ("ME", "Maine", 44.693947, -69.381927, "northeast"),
    ("MD", "Maryland", 39.063946, -76.802101, "northeast"),
    ("MA", "Massachusetts", 42.230171, -71.530106, "northeast"),
    ("MI", "Michigan", 43.326618, -84.536095, "midwest"),
    ("MN", "Minnesota", 45.694454, -93.900192, "midwest"),
    ("MS", "Mississippi", 32.741646, -89.678696, "south"),
    ("MO", "Missouri", 38.456085, -92.288368, "midwest"),
    ("MT", "Montana", 46.921925, -110.454353, "west"),
    ("NE", "Nebraska", 41.125370, -98.268082, "midwest"),
    ("NV", "Nevada", 38.313515, -117.055374, "west"),
    ("NH", "New Hampshire", 43.452492, -71.563896, "northeast"),
    ("NJ", "New Jersey", 40.298904, -74.521011, "northeast"),
    ("NM", "New Mexico", 34.840515, -106.248482, "west"),
    ("NY", "New York", 42.165726, -74.948051, "northeast"),
    ("NC", "North Carolina", 35.630066, -79.806419, "south"),
    ("ND", "North Dakota", 47.528912, -99.784012, "midwest"),
    ("OH", "Ohio", 40.388783, -82.764915, "midwest"),
    ("OK", "Oklahoma", 35.565342, -96.928917, "south"),
    ("OR", "Oregon", 44.572021, -122.070938, "west"),
    ("PA", "Pennsylvania", 40.590752, -77.209755, "northeast"),
    ("RI", "Rhode Island", 41.680893, -71.511780, "northeast"),
    ("SC", "South Carolina", 33.856892, -80.945007, "south"),
    ("SD", "South Dakota", 44.299782, -99.438828, "midwest"),
    ("TN", "Tennessee", 35.747845, -86.692345, "south"),
    ("TX", "Texas", 31.054487, -97.563461, "south"),
    ("UT", "Utah", 40.150032, -111.862434, "west"),
    ("VT", "Vermont", 44.045876, -72.710686, "northeast"),
    ("VA", "Virginia", 37.769337, -78.169968, "south"),
    ("WA", "Washington", 47.400902, -121.490494, "west"),
    ("WV", "West Virginia", 38.491226, -80.954453, "south"),
    ("WI", "Wisconsin", 44.268543, -89.616508, "midwest"),
    ("WY", "Wyoming", 42.755966, -107.302490, "west"),
]


def load_geography_records() -> list[GeographyRecord]:
    return [
        GeographyRecord(state_code=code, name=name, centroid_lat=lat, centroid_lng=lng, region=region)
        for code, name, lat, lng, region in _STATES
    ]
