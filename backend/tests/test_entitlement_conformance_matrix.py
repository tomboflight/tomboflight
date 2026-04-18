import unittest

from app.core.entitlement_conformance_matrix import (
    get_entitlement_conformance_matrix,
    validate_entitlement_conformance_matrix,
)
from app.core.package_catalog import get_package_catalog


class EntitlementConformanceMatrixTests(unittest.TestCase):
    def test_matrix_covers_all_catalog_packages(self):
        matrix = get_entitlement_conformance_matrix()
        catalog = get_package_catalog()

        covered = set()
        for lane in ("portrait", "household", "network", "organization"):
            lane_packages = matrix["lanes"][lane]["packages"]
            covered.update(lane_packages.keys())

        self.assertEqual(set(catalog.keys()), covered)

    def test_matrix_has_complete_hard_limits(self):
        matrix = get_entitlement_conformance_matrix()
        required_limit_keys = {
            "max_uploads",
            "max_storage_gb",
            "max_members",
            "max_households",
            "max_org_nodes",
            "max_zoom_layers",
        }

        for lane in matrix["lanes"].values():
            for package in lane["packages"].values():
                limits = package["hard_limits"]
                self.assertEqual(required_limit_keys, set(limits.keys()))

    def test_matrix_self_validation_passes(self):
        matrix = get_entitlement_conformance_matrix()
        errors = validate_entitlement_conformance_matrix(matrix)
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
