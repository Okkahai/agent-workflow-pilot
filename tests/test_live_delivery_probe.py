"""Controlled red probe: retain until the Coordinator observes failed GitHub CI."""


def test_live_delivery_probe_deliberate_failure():
    # Dedicated draft PR only; this intentional red state is not eligible delivery.
    assert False, "Deliberate live delivery probe failure; awaiting Coordinator observation"
