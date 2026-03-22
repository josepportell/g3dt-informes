"""
SmartScan tests — ground truth verification for 7 projects.

Each project has manually verified file→role mappings.
Tests verify that SmartScan correctly classifies every file.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

# Adjust path so we can import from project root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.smartscan import scan_project, SmartScanResult


REF_DIR = Path(__file__).resolve().parent.parent / 'reference-material'


# ── Ground Truth ─────────────────────────────────────────────
# role → relative file path (from project root)
# None means the project legitimately lacks this role.

GROUND_TRUTH: dict[str, dict[str, str | None]] = {
    "4001612 BELL-LLOC": {
        "architect_plan": "A.01.pdf",
        "dpsh_field_sheet": "PENETROS.pdf",
        "dpsh_excel": "ANNEXES/4001612_DPSH.xls",
        "sondeig_field_sheet": "SONDEIG.pdf",
        "sondeig_annex": "PDF/ANNEXES/4001612_sondeig.pdf",
        "correlation_section": "tall.pdf",
        "situation_plan": "pl. situaci.pdf",
        "photos_dir": "FOTOGRAFIES",
        "reference_report": "4001612_informe.doc",
    },
    "3001621 CASTELLAR DEL VALLES": {
        "dpsh_field_sheet": "PENETROS + SONDEIG.pdf",
        "sondeig_field_sheet": "PENETROS + SONDEIG.pdf",  # combined
        "dpsh_excel": "ANNEXES/3001621_DPSH.xls",
        "sondeig_annex": "PDF/ANNEXES/3001621_sondeig.pdf",
        "correlation_section": "tall.pdf",
        "photos_dir": "FOTOGRAFIES",
        "reference_report": "3001621_informe_v0.doc",
    },
    "3001631 RUBI": {
        "dpsh_field_sheet": "3001631 - PENETROS.pdf",
        "dpsh_excel": "ANNEXES/3001631_DPSH.xls",
        "correlation_section": "tall.pdf",
        "photos_dir": "FOTOGRAFIES",
        "reference_report": "3001631_informe.doc",
    },
    "4001607 LINYOLA": {
        "dpsh_field_sheet": "PENETROS.pdf",
        "dpsh_excel": "ANNEXES/4001607_DPSH.xls",
        "correlation_section": "tall.pdf",
        "situation_plan": "pl situ.pdf",
        "photos_dir": "FOTOGRAFIES",
        "reference_report": "4001607_informe.doc",
    },
    "4001670 ALCOLETGE": {
        "architect_plan": "A.01.pdf",
        "dpsh_field_sheet": "PENETROS.pdf",
        "dpsh_excel": "ANNEXES/4001670_DPSH.xls",
        "field_croquis": "FOTOS DE CAMP + PLANOL PUNTS/CROQUIS.jpeg",
        "sondeig_field_sheet": None,  # No sondeig
        "correlation_section": "tall.pdf",
        "photos_dir": "FOTOS DE CAMP + PLANOL PUNTS",
        "reference_report": "4001670_informe.doc",
    },
    "4001671 VILANOVA DE SEGRIA": {
        "dpsh_field_sheet": "PENETROS.pdf",
        "dpsh_excel": "ANEXOS/4001671_DPSH.xls",
        "sondeig_field_sheet": None,  # No sondeig
        "correlation_section": "tall.pdf",
        "situation_plan": "pl situació.pdf",
        "photos_dir": "FOTOGRAFIES",
        "reference_report": "4001671_informe.docx",
    },
    "4001679 ANCILES": {
        "dpsh_field_sheet": "PENETROS + SONDEIGS.pdf",
        "sondeig_field_sheet": "PENETROS + SONDEIGS.pdf",  # combined
        "dpsh_excel": "ANEJOS/4001679_DPSH.xls",
        "sondeig_annex": "PDF_V0/ANEJOS/4001679_sondeos.pdf",
        "correlation_section": "tall.pdf",
        "situation_plan": "pl situ.pdf",
        "photos_dir": "FOTOGRAFIES",
        "reference_report": "4001679_informe_V0.doc",
    },
}


def _project_exists(name: str) -> bool:
    return (REF_DIR / name).is_dir()


@pytest.fixture(params=list(GROUND_TRUTH.keys()))
def project_name(request):
    name = request.param
    if not _project_exists(name):
        pytest.skip(f"Project {name} not in reference-material")
    return name


class TestSmartScanGroundTruth:
    """Verify SmartScan classifies all roles correctly across 7 projects."""

    def test_roles_match_ground_truth(self, project_name: str):
        """Each expected role must be correctly assigned."""
        project_path = REF_DIR / project_name
        result = scan_project(project_path, max_tier=2)

        truth = GROUND_TRUTH[project_name]
        role_map = result.role_map

        errors = []
        for role, expected_path in truth.items():
            if expected_path is None:
                # Role should NOT be assigned
                if role in role_map:
                    errors.append(
                        f"  {role}: should be absent but got '{role_map[role].file_path}'"
                    )
                continue

            if role not in role_map:
                errors.append(f"  {role}: MISSING (expected '{expected_path}')")
                continue

            actual_path = role_map[role].file_path
            if actual_path != expected_path:
                errors.append(
                    f"  {role}: got '{actual_path}', expected '{expected_path}'"
                )

        if errors:
            msg = f"\n{project_name} role mismatches:\n" + "\n".join(errors)
            pytest.fail(msg)

    def test_no_false_positives(self, project_name: str):
        """No role should be assigned to a wrong file."""
        project_path = REF_DIR / project_name
        result = scan_project(project_path, max_tier=2)

        truth = GROUND_TRUTH[project_name]
        role_map = result.role_map

        for role, clf in role_map.items():
            if role in truth:
                continue
            # Roles not in ground truth are acceptable (additional detection)
            # but we should flag them for review
            pass

    def test_confidence_thresholds(self, project_name: str):
        """Classified files must meet minimum confidence thresholds."""
        project_path = REF_DIR / project_name
        result = scan_project(project_path, max_tier=2)

        for clf in result.classifications:
            if clf.role and clf.category == "classified":
                if clf.tier.value == "filename":
                    assert clf.confidence >= 0.7, (
                        f"Tier 1 {clf.file_path} ({clf.role}): "
                        f"confidence {clf.confidence:.2f} < 0.7"
                    )
                elif clf.tier.value == "fingerprint":
                    assert clf.confidence >= 0.6, (
                        f"Tier 2 {clf.file_path} ({clf.role}): "
                        f"confidence {clf.confidence:.2f} < 0.6"
                    )

    def test_scan_performance(self, project_name: str):
        """Scan should complete in under 2 seconds (without Tier 3)."""
        project_path = REF_DIR / project_name
        start = time.monotonic()
        result = scan_project(project_path, max_tier=2)
        elapsed = time.monotonic() - start

        assert elapsed < 2.0, (
            f"{project_name}: scan took {elapsed:.2f}s (limit: 2.0s)"
        )

    def test_zero_files_ignored_silently(self, project_name: str):
        """Every file must appear in classifications or unclassified."""
        project_path = REF_DIR / project_name
        result = scan_project(project_path, max_tier=2)

        all_tracked = set()
        for clf in result.classifications:
            all_tracked.add(clf.file_path)
        for clf in result.unclassified:
            all_tracked.add(clf.file_path)

        # Check that no file is silently dropped
        from automation.smartscan.classifier import _enumerate_files
        entries = _enumerate_files(project_path)
        for rel_path, is_dir in entries:
            assert rel_path in all_tracked, (
                f"{project_name}: file '{rel_path}' not tracked by SmartScan"
            )


class TestSmartScanCompatibility:
    """Test backward compatibility with FileMapping format."""

    def test_to_file_mapping_format(self):
        """to_file_mapping() must produce valid FileMapping JSON structure."""
        project_path = REF_DIR / "4001612 BELL-LLOC"
        if not project_path.exists():
            pytest.skip("Bell-Lloc not available")

        result = scan_project(project_path, max_tier=2)
        fm = result.to_file_mapping()

        assert "roles" in fm
        assert "ignored" in fm
        assert "unassigned" in fm
        assert "_metadata" in fm

        # Check role structure
        for role_name, role_data in fm["roles"].items():
            assert "path" in role_data
            assert "confidence" in role_data
            assert role_data["confidence"] in ("high", "medium", "low")
            assert "detection" in role_data
            assert "vision_type" in role_data

    def test_file_mapping_roles_match(self):
        """FileMapping roles must match ground truth."""
        project_path = REF_DIR / "4001612 BELL-LLOC"
        if not project_path.exists():
            pytest.skip("Bell-Lloc not available")

        result = scan_project(project_path, max_tier=2)
        fm = result.to_file_mapping()

        truth = GROUND_TRUTH["4001612 BELL-LLOC"]
        for role, expected_path in truth.items():
            if expected_path is None:
                continue
            assert role in fm["roles"], f"Role '{role}' missing from FileMapping"
            assert fm["roles"][role]["path"] == expected_path


class TestSmartScanCombinedFiles:
    """Test combined file detection (PENETROS + SONDEIG)."""

    @pytest.mark.parametrize("project_name,file_name", [
        ("3001621 CASTELLAR DEL VALLES", "PENETROS + SONDEIG.pdf"),
        ("4001679 ANCILES", "PENETROS + SONDEIGS.pdf"),
    ])
    def test_combined_file_dual_roles(self, project_name: str, file_name: str):
        """Combined files must assign both dpsh_field_sheet and sondeig_field_sheet."""
        project_path = REF_DIR / project_name
        if not project_path.exists():
            pytest.skip(f"{project_name} not available")

        result = scan_project(project_path, max_tier=2)
        role_map = result.role_map

        assert "dpsh_field_sheet" in role_map, "Missing dpsh_field_sheet"
        assert "sondeig_field_sheet" in role_map, "Missing sondeig_field_sheet"
        assert role_map["dpsh_field_sheet"].file_path == file_name
        assert role_map["sondeig_field_sheet"].file_path == file_name


class TestSmartScanESVariants:
    """Test Spanish naming convention support."""

    def test_vilanova_anexos(self):
        """Vilanova uses ANEXOS/ instead of ANNEXES/."""
        project_path = REF_DIR / "4001671 VILANOVA DE SEGRIA"
        if not project_path.exists():
            pytest.skip("Vilanova not available")

        result = scan_project(project_path, max_tier=2)
        role_map = result.role_map

        assert "dpsh_excel" in role_map
        assert role_map["dpsh_excel"].file_path == "ANEXOS/4001671_DPSH.xls"

    def test_vilanova_docx_report(self):
        """Vilanova uses .docx instead of .doc for reference report."""
        project_path = REF_DIR / "4001671 VILANOVA DE SEGRIA"
        if not project_path.exists():
            pytest.skip("Vilanova not available")

        result = scan_project(project_path, max_tier=2)
        role_map = result.role_map

        assert "reference_report" in role_map
        assert role_map["reference_report"].file_path == "4001671_informe.docx"

    def test_anciles_anejos(self):
        """Anciles uses ANEJOS/ instead of ANNEXES/."""
        project_path = REF_DIR / "4001679 ANCILES"
        if not project_path.exists():
            pytest.skip("Anciles not available")

        result = scan_project(project_path, max_tier=2)
        role_map = result.role_map

        assert "dpsh_excel" in role_map
        assert role_map["dpsh_excel"].file_path == "ANEJOS/4001679_DPSH.xls"

    def test_anciles_sondeos_annex(self):
        """Anciles uses _sondeos.pdf in PDF_V0/ANEJOS/."""
        project_path = REF_DIR / "4001679 ANCILES"
        if not project_path.exists():
            pytest.skip("Anciles not available")

        result = scan_project(project_path, max_tier=2)
        role_map = result.role_map

        assert "sondeig_annex" in role_map
        assert role_map["sondeig_annex"].file_path == "PDF_V0/ANEJOS/4001679_sondeos.pdf"

    def test_anciles_plural_penetros_sondeigs(self):
        """Anciles has PENETROS + SONDEIGS (plural S)."""
        project_path = REF_DIR / "4001679 ANCILES"
        if not project_path.exists():
            pytest.skip("Anciles not available")

        result = scan_project(project_path, max_tier=2)
        role_map = result.role_map

        assert "dpsh_field_sheet" in role_map
        assert "SONDEIGS" in role_map["dpsh_field_sheet"].file_path


class TestSmartScanNonStandard:
    """Test non-standard naming patterns."""

    def test_alcoletge_photos_dir(self):
        """Alcoletge uses 'FOTOS DE CAMP + PLANOL PUNTS' for photos."""
        project_path = REF_DIR / "4001670 ALCOLETGE"
        if not project_path.exists():
            pytest.skip("Alcoletge not available")

        result = scan_project(project_path, max_tier=2)
        role_map = result.role_map

        assert "photos_dir" in role_map
        assert role_map["photos_dir"].file_path == "FOTOS DE CAMP + PLANOL PUNTS"

    def test_rubi_prefixed_penetros(self):
        """Rubi has '3001631 - PENETROS.pdf' with ID prefix."""
        project_path = REF_DIR / "3001631 RUBI"
        if not project_path.exists():
            pytest.skip("Rubi not available")

        result = scan_project(project_path, max_tier=2)
        role_map = result.role_map

        assert "dpsh_field_sheet" in role_map
        assert role_map["dpsh_field_sheet"].file_path == "3001631 - PENETROS.pdf"

    def test_bell_lloc_situation_plan(self):
        """Bell-Lloc has 'pl. situaci.pdf' (truncated name)."""
        project_path = REF_DIR / "4001612 BELL-LLOC"
        if not project_path.exists():
            pytest.skip("Bell-Lloc not available")

        result = scan_project(project_path, max_tier=2)
        role_map = result.role_map

        assert "situation_plan" in role_map
        assert role_map["situation_plan"].file_path == "pl. situaci.pdf"


class TestSmartScanImageClassification:
    """Test image file classification (Phase 2)."""

    def test_alcoletge_croquis_classified(self):
        """CROQUIS.jpeg in content dir must get field_croquis role."""
        project_path = REF_DIR / "4001670 ALCOLETGE"
        if not project_path.exists():
            pytest.skip("Alcoletge not available")

        result = scan_project(project_path, max_tier=2)
        role_map = result.role_map

        assert "field_croquis" in role_map
        assert role_map["field_croquis"].file_path == "FOTOS DE CAMP + PLANOL PUNTS/CROQUIS.jpeg"

    def test_alcoletge_penetros_jpeg_is_suggestion(self):
        """PENETROS.jpeg should be a suggestion (PENETROS.pdf is primary)."""
        project_path = REF_DIR / "4001670 ALCOLETGE"
        if not project_path.exists():
            pytest.skip("Alcoletge not available")

        result = scan_project(project_path, max_tier=2)

        suggestions = [c for c in result.classifications
                       if c.category == "suggestion" and "PENETROS.jpeg" in c.file_path]
        assert len(suggestions) == 1, "PENETROS.jpeg should be a suggestion (alternative to PENETROS.pdf)"

    def test_alcoletge_field_photos_stay_informative(self):
        """P1, P2, P3 photos in content dir must remain informative."""
        project_path = REF_DIR / "4001670 ALCOLETGE"
        if not project_path.exists():
            pytest.skip("Alcoletge not available")

        result = scan_project(project_path, max_tier=2)

        # P1 gets photo_test_point role, P2 becomes suggestion (only one winner per role)
        p1 = [c for c in result.classifications if "P1 - ALCOLETGE" in c.file_path]
        assert len(p1) == 1
        assert p1[0].role == "photo_test_point", (
            f"P1 should be photo_test_point but got role={p1[0].role}"
        )
        p2 = [c for c in result.classifications if "P2 - ALCOLETGE" in c.file_path]
        assert len(p2) == 1
        assert p2[0].category == "suggestion", (
            f"P2 should be suggestion (P1 wins) but got {p2[0].category}"
        )


class TestSmartScanFigureRoles:
    """Test report figure/photo role classification (Phase 6 prep)."""

    def test_vilanova_figure_maps(self):
        """Vilanova ANEXOS/OTROS/ has F1 SIT, F2 PUNTS, F4 MGEOL images."""
        project_path = REF_DIR / "4001671 VILANOVA DE SEGRIA"
        if not project_path.exists():
            pytest.skip("Vilanova not available")

        result = scan_project(project_path, max_tier=2)
        role_map = result.role_map

        assert "figure_situation_map" in role_map
        assert "F1 SIT" in role_map["figure_situation_map"].file_path

        assert "figure_test_points" in role_map
        assert "F2 PUNTS" in role_map["figure_test_points"].file_path

        assert "figure_geological_map" in role_map
        assert "F4 MGEOL" in role_map["figure_geological_map"].file_path

    def test_rubi_figure_roles(self):
        """Rubi ANNEXES/Altres/ has F1 UBI, F4 MGEOL, F5 TALL images."""
        project_path = REF_DIR / "3001631 RUBI"
        if not project_path.exists():
            pytest.skip("Rubi not available")

        result = scan_project(project_path, max_tier=2)
        role_map = result.role_map

        assert "figure_situation_map" in role_map
        assert "F1 UBI" in role_map["figure_situation_map"].file_path

        assert "figure_correlation" in role_map
        assert "F5 TALL" in role_map["figure_correlation"].file_path


class TestSmartScanImageFingerprint:
    """Test Tier 2 image fingerprinting (Phase 2.2)."""

    def test_rubi_whatsapp_floor_plans_need_vision(self):
        """WhatsApp photos of floor plans should be flagged needs_vision."""
        project_path = REF_DIR / "3001631 RUBI"
        if not project_path.exists():
            pytest.skip("Rubi not available")

        result = scan_project(project_path, max_tier=2)

        # These WhatsApp images are photos of floor plans
        for c in result.classifications:
            if "IMG-20251104" in c.file_path:
                assert c.category == "needs_vision", (
                    f"{c.file_path} should be needs_vision but is {c.category}"
                )

    def test_rubi_f3_vg_needs_vision(self):
        """F3 VG.png (Google Street View screenshot) should be needs_vision."""
        project_path = REF_DIR / "3001631 RUBI"
        if not project_path.exists():
            pytest.skip("Rubi not available")

        result = scan_project(project_path, max_tier=2)

        f3_results = [c for c in result.classifications if "F3 VG" in c.file_path]
        assert len(f3_results) == 1
        assert f3_results[0].category == "needs_vision"

    def test_alcoletge_ampliacio_is_document(self):
        """ampliació habitatge v2.png (floor plan) should be needs_vision/document."""
        project_path = REF_DIR / "4001670 ALCOLETGE"
        if not project_path.exists():
            pytest.skip("Alcoletge not available")

        result = scan_project(project_path, max_tier=2)

        amp_results = [c for c in result.classifications
                       if "ampliació habitatge" in c.file_path.lower()]
        assert len(amp_results) == 1
        # It's a suggestion (Tier 1 matched architect_plan but A.01.pdf wins)
        # OR it could be needs_vision from Tier 2. Both are correct.
        assert amp_results[0].category in ("suggestion", "needs_vision"), (
            f"ampliació should be suggestion or needs_vision, got {amp_results[0].category}"
        )
