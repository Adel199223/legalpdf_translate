from .browser_esm_probe import run_browser_esm_json_probe


def test_fee_wording_is_explicit_retained_on_poll_and_reset_between_batches():
    result = run_browser_esm_json_probe(r'''
const { renderGmailFeeOptions, readGmailFeeOptions } = await import(__OPTIONS__);
const { buildGmailBatchFinalizeRequestPayload } = await import(__PAYLOADS__);
const nodes = {group:{dataset:{}}, recipient:{value:''}, include:{checked:true},
  declaration:{value:'old',defaultValue:'Proposed declaration'}, declarationField:{hidden:false}};
renderGmailFeeOptions(nodes,{ownerKey:'shadow:one:A',editable:true});
const initial = {...readGmailFeeOptions(nodes), hidden:nodes.declarationField.hidden};
nodes.recipient.value = 'À entidade <script>example</script>';
nodes.include.checked = true; nodes.declaration.value = 'Reviewed wording';
renderGmailFeeOptions(nodes,{ownerKey:'shadow:one:A',editable:true});
const current = buildGmailBatchFinalizeRequestPayload({...readGmailFeeOptions(nodes)});
renderGmailFeeOptions(nodes,{ownerKey:'shadow:one:A',editable:false});
const completed = {disabled:nodes.group.disabled, declarationDisabled:nodes.declaration.disabled};
renderGmailFeeOptions(nodes,{ownerKey:'shadow:one:B',editable:true});
const next = {...readGmailFeeOptions(nodes), declarationValue:nodes.declaration.value};
nodes.include.checked = true;
renderGmailFeeOptions(nodes,{ownerKey:'live:one:B',editable:true});
console.log(JSON.stringify({initial,current,completed,next,modeReset:!nodes.include.checked}));
''', {"__OPTIONS__": "gmail_fee_options.js", "__PAYLOADS__": "gmail_request_payloads.js"})
    assert result["initial"] == {"recipientBlock":"", "includeTranslatorDeclaration":False,
                                 "translatorDeclarationText":"", "hidden":True}
    assert result["current"]["recipient_block"] == "À entidade <script>example</script>"
    assert result["current"]["include_translator_declaration"] is True
    assert result["current"]["translator_declaration_text"] == "Reviewed wording"
    assert result["completed"] == {"disabled":True, "declarationDisabled":True}
    assert result["next"]["recipientBlock"] == ""
    assert result["next"]["includeTranslatorDeclaration"] is False
    assert result["next"]["declarationValue"] == "Proposed declaration"
    assert result["modeReset"] is True
