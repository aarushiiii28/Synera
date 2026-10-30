"""Indian cities the live map supports. Adding a city is one line; nothing else in the stack is tied to this list.

``state`` uses the names of the boundary file (frontend/public/data/india_states.geojson) and of the Track D grid panels.
``terrain`` selects the IMD heat-wave criteria (plains, coastal or hills).
"""
from __future__ import annotations

from typing import TypedDict


class City(TypedDict):
    id: str
    name: str
    state: str
    lat: float
    lon: float
    terrain: str


def _c(name: str, state: str, lat: float, lon: float, terrain: str = "plains") -> City:
    return {"id": name.lower().replace(" ", "-"), "name": name, "state": state, "lat": lat, "lon": lon, "terrain": terrain}


CITIES: list[City] = [
    _c("Delhi", "Delhi", 28.6139, 77.2090), _c("Mumbai", "Maharashtra", 19.0760, 72.8777, "coastal"),
    _c("Bengaluru", "Karnataka", 12.9716, 77.5946), _c("Chennai", "Tamil Nadu", 13.0827, 80.2707, "coastal"),
    _c("Kolkata", "West Bengal", 22.5726, 88.3639), _c("Hyderabad", "Telangana", 17.3850, 78.4867),
    _c("Amritsar", "Punjab", 31.6340, 74.8723), _c("Chandigarh", "Chandigarh", 30.7333, 76.7794),
    _c("Ludhiana", "Punjab", 30.9010, 75.8573), _c("Jalandhar", "Punjab", 31.3260, 75.5762),
    _c("Jaipur", "Rajasthan", 26.9124, 75.7873), _c("Jodhpur", "Rajasthan", 26.2389, 73.0243),
    _c("Lucknow", "Uttar Pradesh", 26.8467, 80.9462), _c("Kanpur", "Uttar Pradesh", 26.4499, 80.3319),
    _c("Varanasi", "Uttar Pradesh", 25.3176, 82.9739), _c("Agra", "Uttar Pradesh", 27.1767, 78.0081),
    _c("Noida", "Uttar Pradesh", 28.5355, 77.3910), _c("Gurugram", "Haryana", 28.4595, 77.0266),
    _c("Faridabad", "Haryana", 28.4089, 77.3178), _c("Pune", "Maharashtra", 18.5204, 73.8567),
    _c("Nagpur", "Maharashtra", 21.1458, 79.0882), _c("Ahmedabad", "Gujarat", 23.0225, 72.5714),
    _c("Surat", "Gujarat", 21.1702, 72.8311, "coastal"), _c("Bhopal", "Madhya Pradesh", 23.2599, 77.4126),
    _c("Indore", "Madhya Pradesh", 22.7196, 75.8577), _c("Patna", "Bihar", 25.5941, 85.1376),
    _c("Ranchi", "Jharkhand", 23.3441, 85.3096), _c("Raipur", "Chhattisgarh", 21.2514, 81.6296),
    _c("Bhubaneswar", "Odisha", 20.2961, 85.8245, "coastal"), _c("Guwahati", "Assam", 26.1445, 91.7362),
    _c("Srinagar", "Jammu and Kashmir", 34.0837, 74.7973, "hills"), _c("Jammu", "Jammu and Kashmir", 32.7266, 74.8570),
    _c("Leh", "Ladakh", 34.1526, 77.5771, "hills"), _c("Shimla", "Himachal Pradesh", 31.1048, 77.1734, "hills"),
    _c("Dehradun", "Uttarakhand", 30.3165, 78.0322), _c("Gangtok", "Sikkim", 27.3389, 88.6065, "hills"),
    _c("Shillong", "Meghalaya", 25.5788, 91.8933, "hills"), _c("Imphal", "Manipur", 24.8170, 93.9368),
    _c("Aizawl", "Mizoram", 23.7271, 92.7176, "hills"), _c("Kohima", "Nagaland", 25.6751, 94.1086, "hills"),
    _c("Agartala", "Tripura", 23.8315, 91.2868), _c("Itanagar", "Arunachal Pradesh", 27.0844, 93.6053, "hills"),
    _c("Panaji", "Goa", 15.4909, 73.8278, "coastal"), _c("Puducherry", "Puducherry", 11.9416, 79.8083, "coastal"),
    _c("Visakhapatnam", "Andhra Pradesh", 17.6868, 83.2185, "coastal"), _c("Vijayawada", "Andhra Pradesh", 16.5062, 80.6480),
    _c("Kochi", "Kerala", 9.9312, 76.2673, "coastal"), _c("Thiruvananthapuram", "Kerala", 8.5241, 76.9366, "coastal"),
    _c("Coimbatore", "Tamil Nadu", 11.0168, 76.9558), _c("Madurai", "Tamil Nadu", 9.9252, 78.1198),
    _c("Mysuru", "Karnataka", 12.2958, 76.6394), _c("Port Blair", "Andaman and Nicobar Islands", 11.6234, 92.7265, "coastal"),
]

BY_ID: dict[str, City] = {c["id"]: c for c in CITIES}
