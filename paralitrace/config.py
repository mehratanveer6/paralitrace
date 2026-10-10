"""Static configuration: study region, receptor cities, model parameters."""
from dataclasses import dataclass, field
import os

# Study region (lat_min, lat_max, lon_min, lon_max): Punjab, Haryana, Delhi NCR.
BBOX = (27.8, 32.6, 73.8, 78.2)

# Wind grid resolution in degrees. 0.5 deg over BBOX = 10 x 9 = 90 points.
WIND_GRID_RES = 0.5


@dataclass(frozen=True)
class Receptor:
    id: str
    name: str
    lat: float
    lon: float
    population: int  # approx. Census 2011 urban figures; replace with WorldPop in v2


RECEPTORS = [
    Receptor("delhi", "Delhi", 28.6139, 77.2090, 16_300_000),
    Receptor("gurugram", "Gurugram", 28.4595, 77.0266, 880_000),
    Receptor("sonipat", "Sonipat", 28.9931, 77.0151, 280_000),
    Receptor("rohtak", "Rohtak", 28.8955, 76.6066, 370_000),
    Receptor("panipat", "Panipat", 29.3909, 76.9635, 290_000),
    Receptor("karnal", "Karnal", 29.6857, 76.9905, 290_000),
    Receptor("hisar", "Hisar", 29.1492, 75.7217, 300_000),
    Receptor("ambala", "Ambala", 30.3782, 76.7767, 200_000),
    Receptor("chandigarh", "Chandigarh", 30.7333, 76.7794, 1_030_000),
    Receptor("mohali", "Mohali", 30.7046, 76.7179, 170_000),
    Receptor("patiala", "Patiala", 30.3398, 76.3869, 450_000),
    Receptor("sangrur", "Sangrur", 30.2458, 75.8421, 90_000),
    Receptor("bathinda", "Bathinda", 30.2110, 74.9455, 290_000),
    Receptor("ludhiana", "Ludhiana", 30.9010, 75.8573, 1_610_000),
    Receptor("jalandhar", "Jalandhar", 31.3260, 75.5762, 870_000),
    Receptor("amritsar", "Amritsar", 31.6340, 74.8723, 1_180_000),
]
RECEPTOR_BY_ID = {r.id: r for r in RECEPTORS}

# District headquarters, used to name fire locations in words officials can act on.
PLACES = [
    ("Amritsar", 31.634, 74.872), ("Tarn Taran", 31.451, 74.927), ("Gurdaspur", 32.041, 75.405),
    ("Kapurthala", 31.380, 75.381), ("Jalandhar", 31.326, 75.576), ("Hoshiarpur", 31.532, 75.912),
    ("Nawanshahr", 31.125, 76.116), ("Ludhiana", 30.901, 75.857), ("Moga", 30.817, 75.169),
    ("Ferozepur", 30.925, 74.613), ("Fazilka", 30.403, 74.028), ("Faridkot", 30.677, 74.758),
    ("Sri Muktsar Sahib", 30.474, 74.516), ("Bathinda", 30.211, 74.946), ("Mansa", 29.999, 75.393),
    ("Sangrur", 30.246, 75.842), ("Barnala", 30.378, 75.547), ("Malerkotla", 30.531, 75.880),
    ("Patiala", 30.340, 76.387), ("Fatehgarh Sahib", 30.645, 76.390), ("Rupnagar", 30.966, 76.533),
    ("Mohali", 30.705, 76.718), ("Ambala", 30.378, 76.777), ("Yamunanagar", 30.129, 77.268),
    ("Kurukshetra", 29.969, 76.878), ("Kaithal", 29.802, 76.400), ("Karnal", 29.686, 76.991),
    ("Panipat", 29.391, 76.964), ("Sonipat", 28.993, 77.015), ("Jind", 29.316, 76.316),
    ("Fatehabad", 29.515, 75.455), ("Sirsa", 29.534, 75.029), ("Hisar", 29.149, 75.722),
    ("Bhiwani", 28.799, 76.134), ("Rohtak", 28.895, 76.607), ("Jhajjar", 28.607, 76.657),
    ("Delhi", 28.614, 77.209), ("Gurugram", 28.460, 77.027), ("Hanumangarh", 29.581, 74.329),
    ("Sri Ganganagar", 29.904, 73.877),
]


@dataclass(frozen=True)
class ModelParams:
    dt_seconds: int = 900                 # 15 min integration step
    horizon_hours: int = 48               # forecast length
    particles_per_cluster: int = 60
    eddy_diffusivity_m2s: float = 2000.0  # horizontal turbulent mixing (mesoscale)
    lifetime_hours: float = 48.0          # e-folding removal (deposition)
    release_hours: float = 6.0            # emissions spread over afternoon burn window
    persistence: float = 0.8              # fraction of today's clusters assumed to burn tomorrow
    receptor_radius_km: float = 20.0      # particles inside this radius count as exposure
    cluster_res_deg: float = 0.1          # fires grouped into ~10 km cells
    seed: int = 42


PARAMS = ModelParams()

# Risk bands on the smoke index (FRP-weighted particle mass per 1000 km^2, hourly mean).
# Placeholders until the 2025 backtest maps index -> observed PM2.5 increments.
RISK_BANDS = [(0.0, "low"), (20.0, "moderate"), (60.0, "high"), (150.0, "severe")]

OUTPUT_DIR = os.environ.get("PT_OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "..", "output"))


ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")


def load_env_file(path: str = ENV_FILE) -> None:
    """KEY=VALUE lines from .env into the environment. Real environment variables win; blanks are skipped."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.split(" #")[0].strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v


load_env_file()


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key) or default
