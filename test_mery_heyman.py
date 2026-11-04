"""Tests du module Méry–Heyman.

Référence : Milankovitch (1907) — épaisseur minimale d'une arcade
semi-circulaire sous poids propre, joints radiaux :
    t/R = 0.10748, articulation d'intrados à 54.484 deg de la clé.
"""
import math
import unittest

from mery_heyman import Vault, VaultAnalysis


def semicircular(t_ratio: float, n: int = 200) -> VaultAnalysis:
    return VaultAnalysis(Vault(2.0, 1.0, t_ratio, 22.0, n))


class TestSemicircularArch(unittest.TestCase):
    def test_geometry(self) -> None:
        a = semicircular(0.2)
        self.assertAlmostEqual(a.geo.R, 1.0)
        self.assertAlmostEqual(a.geo.alpha, math.pi / 2)

    def test_milankovitch_min_thickness(self) -> None:
        a = semicircular(0.108)
        t_min = a.min_thickness(0.05, 0.2)
        self.assertAlmostEqual(t_min.thickness, 0.10748, delta=2e-4)

    def test_stability_threshold(self) -> None:
        self.assertFalse(semicircular(0.1070).is_stable())
        self.assertTrue(semicircular(0.1080).is_stable())

    def test_hinge_location_at_limit(self) -> None:
        a = semicircular(0.10748)
        H_min, _, e_min, _ = a.thrust_bounds()
        hinges = a.hinges(H_min, e_min)
        intrados = [ang for ang, face in hinges if face == "intrados"]
        self.assertTrue(any(abs(ang - 54.484) < 0.5 for ang in intrados),
                        msg=f"articulations: {hinges}")

    def test_thrust_bounds_ordering(self) -> None:
        a = semicircular(0.2)
        H_min, H_max, e_min, e_max = a.thrust_bounds()
        self.assertLess(H_min, H_max)
        self.assertGreater(H_min, 0.0)
        self.assertAlmostEqual(e_min, a.vault.thickness / 2.0, places=6)
        self.assertLessEqual(abs(e_max), a.vault.thickness / 2 + 1e-9)

    def test_feasible_line_within_ring(self) -> None:
        a = semicircular(0.2)
        H_min, H_max, e_min, e_max = a.thrust_bounds()
        for H, e in ((H_min, e_min), (H_max, e_max)):
            for j in range(a.geo.n + 1):
                d = a.thrust_offset(H, e, j)
                self.assertLessEqual(abs(d), a.vault.thickness / 2 + 1e-9)

    def test_unstable_vault_raises(self) -> None:
        a = semicircular(0.05)
        with self.assertRaises(ValueError):
            a.thrust_bounds()

    def test_surbased_arch(self) -> None:
        a = VaultAnalysis(Vault(8.0, 2.0, 0.5, 22.0, 100))
        H_min, H_max, e_min, e_max = a.thrust_bounds()
        self.assertLess(H_min, H_max)
        self.assertAlmostEqual(a.geo.R, 5.0)
        self.assertAlmostEqual(math.degrees(a.geo.alpha), 53.130, delta=1e-3)


if __name__ == "__main__":
    unittest.main()
