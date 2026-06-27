from axiom.llm.llm_provider import Model

def test_model_set_groq():
    llm = Model.set(provider_name="groq")
    assert llm is not None