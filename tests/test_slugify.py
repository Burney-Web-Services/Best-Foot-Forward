from best_foot_forward.utils.slugify import slugify


def test_spaces_become_underscores():
    assert slugify("Senior Software Engineer") == "Senior_Software_Engineer"


def test_special_chars_replaced():
    assert slugify("Senior Software Engineer!") == "Senior_Software_Engineer"


def test_slashes_replaced():
    assert slugify("Reddit/Engineer") == "Reddit_Engineer"


def test_multiple_spaces_collapse():
    assert slugify("Hello   World") == "Hello_World"


def test_leading_trailing_stripped():
    assert slugify("!hello world!") == "hello_world"


def test_hyphens_preserved():
    assert slugify("aws-cdk") == "aws-cdk"


def test_spaced_hyphen_collapses():
    # A spaced hyphen is a separator, not part of a token. Matches the
    # directory convention already on disk for this role.
    assert slugify("Quality Assurance - Playwright") == "Quality_Assurance_Playwright"


def test_spaced_hyphen_does_not_affect_internal_hyphen():
    assert slugify("Deploy aws-cdk - Platform") == "Deploy_aws-cdk_Platform"


def test_empty_string():
    assert slugify("") == ""
