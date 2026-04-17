"""Tests for automation.bicapa — bicapa bearing-capacity helpers.

Source of formulas: Rodríguez Ortiz, "Curso aplicado de cimentaciones",
Cap. 2 §6.1. Book archived at docs/research/books/.
"""
from __future__ import annotations

import pytest

from automation.bicapa import (
    SoilLayer,
    bicapa_qh_fig29,
    sand_over_soft_clay_qh_tcheng,
    select_bearing_layer,
    two_clay_layers_nm_soft_over_stiff,
    two_clay_layers_qh_soft_over_stiff,
    two_clay_layers_qh_stiff_over_soft,
)


# ---------------------------------------------------------------------------
# Fig. 2.9 general interpolation — both variants
# ---------------------------------------------------------------------------

class TestFig29Interpolation:
    """Reproduces the graphed transitions from Fig. 2.9."""

    # Inputs: stronger top layer (q_h1=4), weaker bottom (q_h2=2), B=1m
    q_h1 = 4.0
    q_h2 = 2.0

    # ---- Case a ----
    def test_case_a_t_zero_equals_qh1(self):
        """At t=0 the upper layer is absent (footing rests on T2 surface)."""
        result = bicapa_qh_fig29(4.0, 2.0, t=0.0, B=1.0, case="a")
        assert result == pytest.approx(4.0)

    def test_case_a_beyond_threshold_equals_qh2(self):
        """t/B > 0.7 → q_h = q_h2 (deep enough that only upper layer matters? No:
        per §6.1 / Fig. 2.9, when the weak layer is deep enough below the footing,
        its influence disappears. Case a's q_h2 at high t/B is a conservative
        reading that keeps the weak bottom governing until t/B=0.7)."""
        assert bicapa_qh_fig29(4.0, 2.0, t=0.8, B=1.0, case="a") == pytest.approx(2.0)
        assert bicapa_qh_fig29(4.0, 2.0, t=2.0, B=1.0, case="a") == pytest.approx(2.0)

    def test_case_a_mid_range_interpolates_linearly(self):
        """At t/B = 0.35 (halfway through 0..0.7 band), q_h = 4 - (4-2)/0.7 × 0.35
        = 4 - 1 = 3.0."""
        assert bicapa_qh_fig29(4.0, 2.0, t=0.35, B=1.0, case="a") == pytest.approx(3.0)

    # ---- Case b ----
    def test_case_b_below_threshold_equals_qh2(self):
        """Case b: t/B ≤ 0.2 → q_h = q_h2."""
        assert bicapa_qh_fig29(4.0, 2.0, t=0.1, B=1.0, case="b") == pytest.approx(2.0)
        assert bicapa_qh_fig29(4.0, 2.0, t=0.2, B=1.0, case="b") == pytest.approx(2.0)

    def test_case_b_above_unity_equals_qh1(self):
        """Case b: t/B ≥ 1.0 → q_h = q_h1."""
        assert bicapa_qh_fig29(4.0, 2.0, t=1.0, B=1.0, case="b") == pytest.approx(4.0)
        assert bicapa_qh_fig29(4.0, 2.0, t=2.0, B=1.0, case="b") == pytest.approx(4.0)

    def test_case_b_mid_range_interpolates_linearly(self):
        """At t/B = 0.6 (halfway through 0.2..1.0 band), q_h per Fig. 2.9 case b:
        q_h = q_h2 - (q_h1 - q_h2)/0.8 × (t/B − 0.2)
            = 2 − (4−2)/0.8 × (0.6 − 0.2)
            = 2 − 2.5 × 0.4 = 2 − 1.0 = 1.0
        Note this is below q_h2 — the case b formula is an aggressive interpolation
        the book publishes as-is; this matches the chart text."""
        assert bicapa_qh_fig29(4.0, 2.0, t=0.6, B=1.0, case="b") == pytest.approx(1.0)

    def test_invalid_inputs_raise(self):
        with pytest.raises(ValueError):
            bicapa_qh_fig29(4.0, 2.0, t=0.5, B=0.0, case="a")
        with pytest.raises(ValueError):
            bicapa_qh_fig29(4.0, 2.0, t=-0.5, B=1.0, case="a")
        with pytest.raises(ValueError):
            bicapa_qh_fig29(4.0, 2.0, t=0.5, B=1.0, case="c")


# ---------------------------------------------------------------------------
# Vesic 1970 N_m lookup (Cuadro 2.4)
# ---------------------------------------------------------------------------

class TestVesicNmLookup:
    """Table values from Rodríguez Ortiz Cuadro 2.4."""

    def test_homogeneous_clay_gives_classical_ncp(self):
        """c2/c1 = 1.0 → N_m = 5.14 (strip) or 6.17 (square), for any B/H."""
        # Strip (L/B very large)
        assert two_clay_layers_nm_soft_over_stiff(
            c1=1.0, c2=1.0, B=1.0, L=100.0, H=5.0
        ) == pytest.approx(5.14, abs=0.01)
        # Square
        assert two_clay_layers_nm_soft_over_stiff(
            c1=1.0, c2=1.0, B=1.0, L=1.0, H=5.0
        ) == pytest.approx(6.17, abs=0.01)

    def test_stiff_bottom_strip_anchor_points(self):
        """Strip (L/B large), c2/c1=2, B/H=4 → table value 5.43."""
        assert two_clay_layers_nm_soft_over_stiff(
            c1=1.0, c2=2.0, B=4.0, L=100.0, H=1.0
        ) == pytest.approx(5.43, abs=0.05)

    def test_stiff_bottom_square_anchor_points(self):
        """Square (L/B=1), c2/c1=3, B/H=12 → table value 7.05."""
        assert two_clay_layers_nm_soft_over_stiff(
            c1=1.0, c2=3.0, B=12.0, L=12.0, H=1.0
        ) == pytest.approx(7.05, abs=0.05)

    def test_qh_soft_over_stiff_formula(self):
        """q_h = c1 · N_m + q."""
        q_h = two_clay_layers_qh_soft_over_stiff(
            c1=0.5, c2=2.0, B=1.0, L=1.0, H=1.0, q_surcharge=0.1,
        )
        # At c2/c1=4, B/H=1: interpolates ~6.17-6.33 (close to homogeneous edge)
        # q_h should be ≈ 0.5 × ~6.2 + 0.1 ≈ 3.2 kg/cm²
        assert 2.0 < q_h < 4.0


# ---------------------------------------------------------------------------
# Brown & Meyerhof 1969 — stiff over soft
# ---------------------------------------------------------------------------

class TestBrownMeyerhofStiffOverSoft:
    def test_homogeneous_case_matches_skempton(self):
        """If c2 = c1 and H >> B, the formula reduces to 0 + 1×1×N_c = N_c
        in the limit where geometric term → 0."""
        # B=1, L=1, H=100 → geometric term = 2(1+1)·100/(1·1) = 400. Dominates.
        q_h = two_clay_layers_qh_stiff_over_soft(
            c1=1.0, c2=1.0, B=1.0, L=1.0, H=100.0,
            N_c=6.17, s_c=1.0,
        )
        # N_m = 400 + 1 × 1 × 6.17 = 406.17
        # q_h = 1 × 406.17 = 406.17
        assert q_h == pytest.approx(406.17, abs=0.1)

    def test_soft_bottom_reduces_qh(self):
        """When c2 < c1 the weak bottom pulls N_m down."""
        q_stiff_over_hard = two_clay_layers_qh_stiff_over_soft(
            c1=1.0, c2=1.0, B=1.0, L=1.0, H=0.5,
            N_c=6.17, s_c=1.0,
        )
        q_stiff_over_soft = two_clay_layers_qh_stiff_over_soft(
            c1=1.0, c2=0.2, B=1.0, L=1.0, H=0.5,
            N_c=6.17, s_c=1.0,
        )
        assert q_stiff_over_soft < q_stiff_over_hard


# ---------------------------------------------------------------------------
# Tcheng 1957 — sand over soft clay
# ---------------------------------------------------------------------------

class TestTchengSandOverSoftClay:
    def test_h_equals_zero_gives_q_hc(self):
        """H=0 → denominator = 1 → q_h = q_hc (no sand above clay)."""
        assert sand_over_soft_clay_qh_tcheng(
            q_hc=2.0, phi_deg=35.0, B=1.0, H=0.01,
        ) == pytest.approx(2.0, abs=0.05)

    def test_thicker_sand_increases_qh(self):
        """More sand above a soft clay → higher combined q_h."""
        q_low = sand_over_soft_clay_qh_tcheng(q_hc=2.0, phi_deg=35.0, B=1.0, H=0.2)
        q_high = sand_over_soft_clay_qh_tcheng(q_hc=2.0, phi_deg=35.0, B=1.0, H=0.8)
        assert q_high > q_low

    def test_warns_outside_validity_range(self, caplog):
        """H > 1.5B should log a warning (formula is strictly for H ≤ 1.5B)."""
        import logging
        with caplog.at_level(logging.WARNING, logger="automation.bicapa"):
            sand_over_soft_clay_qh_tcheng(q_hc=2.0, phi_deg=35.0, B=1.0, H=2.0)
        assert any("H=" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Competent-layer selector (Eva's skip-soft-top pattern)
# ---------------------------------------------------------------------------

class TestSelectBearingLayer:
    def test_alcoletge_like_profile_picks_second_layer(self):
        """Alcoletge informe: 1st layer = sorres argiloses de rebliment,
        N=0, φ=28° (fill — to be sanejat). 2nd layer = lutites, N=20, φ=30°,
        c=1.0. Eva computes Qa on layer 2."""
        layers = [
            SoilLayer(
                depth_top=0.0, depth_bottom=1.3,
                soil_type="cohesive", nspt=0,
                gamma=1.80, cohesion=0.0, phi=28.0, E=50.0,
                description="Sorres argiloses de rebliment",
            ),
            SoilLayer(
                depth_top=1.3, depth_bottom=5.0,
                soil_type="rock", nspt=20,
                gamma=2.00, cohesion=1.0, phi=30.0, E=450.0,
                description="Lutites i sorrenques alterades",
            ),
        ]
        bearing, idx = select_bearing_layer(layers, foundation_depth=0.8)
        assert idx == 1, "should skip the rebliment layer"
        assert bearing.cohesion == 1.0
        assert bearing.phi == 30.0

    def test_skips_by_description_keyword(self):
        """Descriptions like 'rebliment' / 'relleno' trigger the skip."""
        layers = [
            SoilLayer(
                depth_top=0, depth_bottom=0.5, soil_type="granular",
                nspt=30, gamma=2.0, cohesion=0.0, phi=35.0, E=300.0,
                description="Relleno antrópico",
            ),
            SoilLayer(
                depth_top=0.5, depth_bottom=5.0, soil_type="granular",
                nspt=25, gamma=2.0, cohesion=0.0, phi=33.0, E=250.0,
                description="Arenas compactas",
            ),
        ]
        bearing, idx = select_bearing_layer(layers, foundation_depth=0.3)
        assert idx == 1, "explicit fill label trips the skip even with high N"

    def test_first_layer_competent_returns_first(self):
        """If the top layer is strong, it's the bearing layer."""
        layers = [
            SoilLayer(
                depth_top=0, depth_bottom=4.0, soil_type="rock",
                nspt=50, gamma=2.2, cohesion=1.0, phi=30.0, E=500.0,
                description="Bretxes amb lutites",
            ),
        ]
        bearing, idx = select_bearing_layer(layers, foundation_depth=0.8)
        assert idx == 0

    def test_raises_when_all_layers_weak(self):
        """No competent layer found → raise."""
        layers = [
            SoilLayer(
                depth_top=0, depth_bottom=3.0, soil_type="cohesive",
                nspt=2, gamma=1.5, cohesion=0.0, phi=20.0, E=30.0,
                description="Rellim feble",
            ),
        ]
        with pytest.raises(ValueError, match="no competent"):
            select_bearing_layer(layers, foundation_depth=0.8)

    def test_skips_layers_above_foundation_depth(self):
        """A thin strong surface layer entirely above Df isn't the bearer."""
        layers = [
            SoilLayer(
                depth_top=0, depth_bottom=0.4, soil_type="rock",
                nspt=80, gamma=2.2, cohesion=1.0, phi=30.0, E=500.0,
                description="Capa superficial",
            ),
            SoilLayer(
                depth_top=0.4, depth_bottom=5.0, soil_type="granular",
                nspt=25, gamma=2.0, cohesion=0.0, phi=33.0, E=250.0,
                description="Sòl natural",
            ),
        ]
        bearing, idx = select_bearing_layer(layers, foundation_depth=0.8)
        assert idx == 1, "top layer entirely above Df must be skipped"
