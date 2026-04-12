from core.prompting import PromptLibrary


def test_prompt_library_registers_and_promotes_candidate(tmp_path):
    library = PromptLibrary(tmp_path)
    default_text = "Base prompt"

    resolved_text, variant_id = library.resolve("chat.system", default_text)
    assert resolved_text == default_text
    assert variant_id == "default"

    candidate = library.register_candidate("chat.system", default_text, "Improved prompt", notes="candidate")
    library.record_outcome("chat.system", default_text, candidate.id, 0.92, True)

    resolved_text, variant_id = library.resolve("chat.system", default_text)
    assert resolved_text == "Improved prompt"
    assert variant_id == candidate.id
