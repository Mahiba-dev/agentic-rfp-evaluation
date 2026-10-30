# Agentic RFP Evaluation

## Choosing an LLM

Run the Streamlit app with `streamlit run app.py`. In the **LLM settings** sidebar,
choose a provider, enter its API key, and type the model identifier supported by
that provider. For an OpenAI-compatible service, also enter its base URL (usually
including `/v1`).

The API key is used for the current Streamlit session and is not included in
saved evaluation results. Alternatively, leave the key field blank and configure
`LLM_API_KEY` (or `OPENAI_API_KEY`) in the environment. The optional
`LLM_BASE_URL` environment variable can supply a compatible endpoint.