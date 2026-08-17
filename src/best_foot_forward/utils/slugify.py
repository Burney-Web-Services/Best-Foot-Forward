import re


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug (underscores, no leading/trailing).

    A *spaced* hyphen is a separator and collapses away, matching the directory
    convention already on disk ("Quality Assurance - Playwright" ->
    "Quality_Assurance_Playwright"). An *internal* hyphen is part of the token
    and is preserved ("aws-cdk" -> "aws-cdk").
    """
    text = re.sub(r'\s+-+\s+', ' ', text)
    return re.sub(r'_+', '_', re.sub(r'[^a-zA-Z0-9-]', '_', text)).strip('_')
