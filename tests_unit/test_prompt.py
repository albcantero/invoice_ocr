from lib.llm.prompt import MOLD, build_messages


def test_mold_has_expected_keys():
    assert set(MOLD.keys()) == {
        "vendor_name", "vendor_vat", "invoice_date", "invoice_ref",
        "due_date", "currency", "lines", "amount_untaxed", "amount_tax",
        "amount_total",
    }


def test_build_messages_includes_text_and_mold():
    msgs = build_messages("FACTURA X")
    assert msgs[0]["role"] == "system"
    assert "vendor_vat" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"
    assert "FACTURA X" in msgs[1]["content"]
