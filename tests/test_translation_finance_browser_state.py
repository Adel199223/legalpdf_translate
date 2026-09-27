from .browser_esm_probe import run_browser_esm_json_probe


def test_decimal_browser_preview_matches_fees_and_preserves_manual_history():
    result = run_browser_esm_json_probe(
        r"""
const { translationFeeEur, updateTranslationFinance } = await import(__MODULE_URL__);
const nodes = { mode: {value:'auto'}, words:{value:'1132'}, rate:{value:'0.08'},
  total:{value:'90.56'}, profit:{value:''}, note:{textContent:''} };
updateTranslationFinance(nodes);
nodes.words.value = '1138'; updateTranslationFinance(nodes);
const correctedWords = nodes.total.value;
nodes.rate.value = '0.027'; updateTranslationFinance(nodes);
const correctedRate = nodes.total.value;
nodes.mode.value = 'manual'; nodes.total.value = '71.23'; nodes.profit.value='90.4';
nodes.words.value='1501'; updateTranslationFinance(nodes);
const manual = { total:nodes.total.value, readonly:nodes.total.readOnly, profit:nodes.profit.value, note:nodes.note.textContent };
nodes.mode.value = 'auto'; updateTranslationFinance(nodes);
console.log(JSON.stringify({ correctedWords, correctedRate, manual, restored:nodes.total.value,
  cents:translationFeeEur(15,'.027'), comma:translationFeeEur(5,'0,027'),
  scientific:translationFeeEur(100,'2.7e-2'), zero:translationFeeEur(0,0),
  invalid:[translationFeeEur(-1,'.027'),translationFeeEur('1.2','.027'),translationFeeEur(2,'NaN'),translationFeeEur(2,'-1')] }));
""",
        {"__MODULE_URL__": "translation_finance.js"},
    )
    assert result["correctedWords"] == "91.04"
    assert result["correctedRate"] == "30.73"
    assert result["manual"]["total"] == "71.23"
    assert result["manual"]["readonly"] is False
    assert result["manual"]["profit"] == "90.4"
    assert "Historical" in result["manual"]["note"]
    assert result["restored"] == "40.53"
    assert (result["cents"], result["comma"], result["scientific"], result["zero"]) == ("0.41", "0.14", "2.70", "0.00")
    assert result["invalid"] == [None] * 4
