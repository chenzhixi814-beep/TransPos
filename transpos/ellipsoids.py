"""Reference ellipsoid definitions used for geodetic conversion."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Ellipsoid:
    name: str
    a: float      # semi-major axis (m)
    inv_f: float  # inverse flattening

    @property
    def f(self) -> float:
        return 1.0 / self.inv_f

    @property
    def b(self) -> float:
        return self.a * (1.0 - self.f)

    @property
    def e2(self) -> float:
        """First eccentricity squared."""
        return 2 * self.f - self.f ** 2


# Both frames share the same semi-major axis; the flattening differs only
# from the 9th significant digit onward, so the two ellipsoids are kept
# distinct here even though the practical effect on BLH is sub-millimetre.
WGS84 = Ellipsoid("WGS84", 6378137.0, 298.257223563)
CGCS2000 = Ellipsoid("CGCS2000", 6378137.0, 298.257222101)

ELLIPSOIDS = {"WGS84": WGS84, "CGCS2000": CGCS2000}
