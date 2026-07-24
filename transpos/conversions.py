"""Core geodetic conversion routines.

Covers three conversions:

1. Geodetic (B, L, H) <-> ECEF (X, Y, Z), for a given reference ellipsoid.
2. 7-parameter Helmert (Bursa-Wolf) datum transform, used to relate the
   WGS84 and CGCS2000 frames.
3. ECEF <-> local ENU (East, North, Up) velocity transform at a given
   geodetic position.
"""

import math

from .ellipsoids import Ellipsoid


def blh_to_xyz(lat_deg: float, lon_deg: float, h: float, ellip: Ellipsoid):
    """Geodetic (lat, lon in degrees; ellipsoidal height in metres) -> ECEF X, Y, Z."""
    b = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    a, e2 = ellip.a, ellip.e2
    n = a / math.sqrt(1 - e2 * math.sin(b) ** 2)
    x = (n + h) * math.cos(b) * math.cos(lon)
    y = (n + h) * math.cos(b) * math.sin(lon)
    z = (n * (1 - e2) + h) * math.sin(b)
    return x, y, z


def xyz_to_blh(x: float, y: float, z: float, ellip: Ellipsoid,
               tol: float = 1e-12, max_iter: int = 50):
    """ECEF X, Y, Z (metres) -> geodetic lat, lon (degrees), ellipsoidal height (metres).

    There is no closed-form inverse, so this iterates (Bowring-style) until
    the latitude estimate stops changing. Converges in a handful of steps
    for any point outside the immediate vicinity of the Earth's centre.
    """
    a, e2 = ellip.a, ellip.e2
    lon = math.atan2(y, x)
    p = math.hypot(x, y)

    if p < 1e-9:  # on the polar axis: longitude and the p-based formula are undefined
        b = math.copysign(math.pi / 2, z) if z else 0.0
        n = a / math.sqrt(1 - e2 * math.sin(b) ** 2)
        h = abs(z) - n * (1 - e2)
        return math.degrees(b), math.degrees(lon), h

    b = math.atan2(z, p * (1 - e2))
    for _ in range(max_iter):
        n = a / math.sqrt(1 - e2 * math.sin(b) ** 2)
        # h = p/cos(b) - n is unstable near the poles (division by ~0);
        # this equivalent form only uses cos/sin directly and stays stable
        # everywhere, including near the poles.
        h = p * math.cos(b) + z * math.sin(b) - a * math.sqrt(1 - e2 * math.sin(b) ** 2)
        b_next = math.atan2(z, p * (1 - e2 * n / (n + h)))
        if abs(b_next - b) < tol:
            b = b_next
            break
        b = b_next

    n = a / math.sqrt(1 - e2 * math.sin(b) ** 2)
    h = p * math.cos(b) + z * math.sin(b) - a * math.sqrt(1 - e2 * math.sin(b) ** 2)
    return math.degrees(b), math.degrees(lon), h


class HelmertParams:
    """7-parameter Bursa-Wolf datum transform parameters.

    dx, dy, dz : translations, metres
    rx, ry, rz : small rotations, arcseconds
    ds         : scale difference, ppm

    Default is all-zero: WGS84 and CGCS2000 are both ITRF-aligned frames and
    are treated as coincident at ordinary surveying/mapping accuracy (real
    differences are at the centimetre level or below, and no single public
    Bursa-Wolf parameter set is published because the frames are defined to
    coincide). Only override these fields if you have been issued
    region-specific transformation parameters and need sub-centimetre
    consistency.
    """

    def __init__(self, dx=0.0, dy=0.0, dz=0.0, rx=0.0, ry=0.0, rz=0.0, ds=0.0):
        self.dx, self.dy, self.dz = dx, dy, dz
        self.rx, self.ry, self.rz = rx, ry, rz
        self.ds = ds


def _helmert_apply(x, y, z, dx, dy, dz, rx, ry, rz, ds):
    rx = math.radians(rx / 3600.0)
    ry = math.radians(ry / 3600.0)
    rz = math.radians(rz / 3600.0)
    s = ds * 1e-6
    out_x = (1 + s) * x - rz * y + ry * z + dx
    out_y = rz * x + (1 + s) * y - rx * z + dy
    out_z = -ry * x + rx * y + (1 + s) * z + dz
    return out_x, out_y, out_z


def helmert_forward(x, y, z, p: HelmertParams):
    """Apply the transform in its defined direction (e.g. WGS84 -> CGCS2000)."""
    return _helmert_apply(x, y, z, p.dx, p.dy, p.dz, p.rx, p.ry, p.rz, p.ds)


def helmert_inverse(x, y, z, p: HelmertParams):
    """Apply the reverse transform.

    Negating all seven parameters is only exact to first order, but since
    rotations are arcsecond-scale and the scale term is ppm-scale, the
    linearisation error is negligible (sub-millimetre) for this use case.
    """
    return _helmert_apply(x, y, z, -p.dx, -p.dy, -p.dz, -p.rx, -p.ry, -p.rz, -p.ds)


def ecef_to_enu_matrix(lat_deg: float, lon_deg: float):
    """Rotation matrix taking an ECEF vector to local East-North-Up components."""
    b = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_b, cos_b = math.sin(b), math.cos(b)
    sin_l, cos_l = math.sin(lon), math.cos(lon)
    return (
        (-sin_l, cos_l, 0.0),
        (-sin_b * cos_l, -sin_b * sin_l, cos_b),
        (cos_b * cos_l, cos_b * sin_l, sin_b),
    )


def _mat_vec(r, v):
    return tuple(sum(r[i][j] * v[j] for j in range(3)) for i in range(3))


def _mat_transpose(r):
    return tuple(tuple(r[j][i] for j in range(3)) for i in range(3))


def velocity_ecef_to_enu(vx: float, vy: float, vz: float, lat_deg: float, lon_deg: float):
    """ECEF velocity -> local East, North, Up velocity at the given geodetic position.

    Only the rotation at the given instant is applied; this is the standard
    GNSS convention and ignores the (second-order) rate of change of the
    local frame's own orientation as the point moves.
    """
    r = ecef_to_enu_matrix(lat_deg, lon_deg)
    return _mat_vec(r, (vx, vy, vz))


def velocity_enu_to_ecef(ve: float, vn: float, vu: float, lat_deg: float, lon_deg: float):
    """Local East, North, Up velocity -> ECEF velocity at the given geodetic position."""
    r = _mat_transpose(ecef_to_enu_matrix(lat_deg, lon_deg))
    return _mat_vec(r, (ve, vn, vu))
