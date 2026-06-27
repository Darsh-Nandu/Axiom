from axiom.llm.llm_provider import Model

llm = Model.set(provider_name="groq")
res = llm.invoke(["Hi"])
print(res.content)