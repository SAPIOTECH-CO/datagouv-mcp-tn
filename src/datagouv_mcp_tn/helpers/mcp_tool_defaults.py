from mcp.types import ToolAnnotations

# All tools hit the public data.gouv.tn API and never mutate anything:
# read-only, but results depend on the external service.
READ_ONLY_EXTERNAL_API_TOOL = ToolAnnotations(
    title=None,
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
