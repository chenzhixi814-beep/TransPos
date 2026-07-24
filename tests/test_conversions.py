import math
import unittest

from transpos.conversions import (
    HelmertParams,
    blh_to_xyz,
    ecef_to_enu_matrix,
    helmert_forward,
    helmert_inverse,
    velocity_ecef_to_enu,
    velocity_enu_to_ecef,
    xyz_to_blh,
)
from transpos.ellipsoids import CGCS2000, WGS84


class TestBlhXyzRoundTrip(unittest.TestCase):
    POINTS = [
        (39.9, 116.4, 50.0),     # Beijing, mid-latitude
        (-33.9, 151.2, 100.0),   # Sydney, southern hemisphere
        (0.0, 0.0, 0.0),         # equator / prime meridian
        (0.0, 180.0, 0.0),       # equator / anti-meridian
        (89.9999, 45.0, 200.0),  # near the north pole
        (-89.9999, 45.0, -20.0),  # near the south pole
    ]

    def test_round_trip_wgs84(self):
        for lat, lon, h in self.POINTS:
            x, y, z = blh_to_xyz(lat, lon, h, WGS84)
            lat2, lon2, h2 = xyz_to_blh(x, y, z, WGS84)
            self.assertAlmostEqual(lat, lat2, places=8)
            self.assertAlmostEqual(lon, lon2, places=8)
            self.assertAlmostEqual(h, h2, places=6)

    def test_round_trip_cgcs2000(self):
        for lat, lon, h in self.POINTS:
            x, y, z = blh_to_xyz(lat, lon, h, CGCS2000)
            lat2, lon2, h2 = xyz_to_blh(x, y, z, CGCS2000)
            self.assertAlmostEqual(lat, lat2, places=8)
            self.assertAlmostEqual(lon, lon2, places=8)
            self.assertAlmostEqual(h, h2, places=6)

    def test_equator_prime_meridian(self):
        x, y, z = blh_to_xyz(0.0, 0.0, 0.0, WGS84)
        self.assertAlmostEqual(x, WGS84.a, places=6)
        self.assertAlmostEqual(y, 0.0, places=6)
        self.assertAlmostEqual(z, 0.0, places=6)

    def test_north_pole(self):
        x, y, z = blh_to_xyz(90.0, 0.0, 0.0, WGS84)
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(y, 0.0, places=6)
        self.assertAlmostEqual(z, WGS84.b, places=6)

    def test_pole_inverse_matches_forward(self):
        lat, lon, h = xyz_to_blh(0.0, 0.0, WGS84.b + 10.0, WGS84)
        self.assertAlmostEqual(lat, 90.0, places=6)
        self.assertAlmostEqual(h, 10.0, places=6)


class TestHelmert(unittest.TestCase):
    def test_zero_params_is_identity(self):
        p = HelmertParams()
        pt = (-2179732.234, 4385493.12, 4078894.55)
        out = helmert_forward(*pt, p)
        for a, b in zip(pt, out):
            self.assertAlmostEqual(a, b, places=9)

    def test_forward_inverse_round_trip(self):
        p = HelmertParams(dx=0.03, dy=-0.02, dz=0.01, rx=0.002, ry=-0.001, rz=0.0005, ds=0.01)
        pt = (-2179732.234, 4385493.12, 4078894.55)
        forward = helmert_forward(*pt, p)
        back = helmert_inverse(*forward, p)
        for a, b in zip(pt, back):
            self.assertAlmostEqual(a, b, places=6)


class TestVelocity(unittest.TestCase):
    def test_enu_matrix_is_orthonormal(self):
        r = ecef_to_enu_matrix(35.0, 120.0)
        # rows should be unit length and mutually orthogonal
        for i in range(3):
            norm = math.sqrt(sum(v * v for v in r[i]))
            self.assertAlmostEqual(norm, 1.0, places=9)
        for i in range(3):
            for j in range(i + 1, 3):
                dot = sum(r[i][k] * r[j][k] for k in range(3))
                self.assertAlmostEqual(dot, 0.0, places=9)

    def test_ecef_enu_round_trip(self):
        lat, lon = 22.5, 114.0
        vx, vy, vz = 1.5, -2.3, 0.7
        ve, vn, vu = velocity_ecef_to_enu(vx, vy, vz, lat, lon)
        vx2, vy2, vz2 = velocity_enu_to_ecef(ve, vn, vu, lat, lon)
        self.assertAlmostEqual(vx, vx2, places=9)
        self.assertAlmostEqual(vy, vy2, places=9)
        self.assertAlmostEqual(vz, vz2, places=9)

    def test_up_at_equator_prime_meridian_is_x_axis(self):
        # At (0, 0), local Up should align with the ECEF X axis.
        ve, vn, vu = velocity_ecef_to_enu(1.0, 0.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(ve, 0.0, places=9)
        self.assertAlmostEqual(vn, 0.0, places=9)
        self.assertAlmostEqual(vu, 1.0, places=9)


if __name__ == "__main__":
    unittest.main()
