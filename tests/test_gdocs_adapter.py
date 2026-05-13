from activity_dashboard.adapters import gdocs as gdocs_adapter
from activity_dashboard.item import Bucket
from activity_dashboard.config import Settings, Credentials, JiraCredentials, Rules, NeedsAttentionThresholds, SubjectConfig


def _settings():
    return Settings(
        credentials=Credentials(
            github_token_file=None,
            jira=JiraCredentials(base_url="x", email_file=None, token_file=None),
            google_credentials_file=None, google_token_file=None,
        ),
        rules=Rules(window_days=7, needs_attention=NeedsAttentionThresholds()),
        subjects={},
    )


def _subject(doc_url="https://docs.google.com/document/d/abc123XYZ/edit"):
    return SubjectConfig(
        name="alice", display_name="Alice", canonical_email="a@c.com",
        launchpad_id="alice-lp", github_id="alice-gh",
        one_on_one_doc=doc_url,
    )


def _para(text, style="NORMAL_TEXT"):
    return {"paragraph": {
        "elements": [{"textRun": {"content": text + "\n"}}],
        "paragraphStyle": {"namedStyleType": style},
    }}


class FakeDocsAPI:
    def __init__(self, doc):
        self.doc = doc
        self.last_doc_id = None
    def documents(self):
        return self
    def get(self, documentId):
        self.last_doc_id = documentId
        return self
    def execute(self):
        return self.doc


def test_name_constant():
    assert gdocs_adapter.NAME == "gdocs"


def test_extract_doc_id_from_url():
    assert gdocs_adapter._extract_doc_id(
        "https://docs.google.com/document/d/abc123XYZ/edit"
    ) == "abc123XYZ"
    assert gdocs_adapter._extract_doc_id("abc123XYZ") == "abc123XYZ"


def test_fetch_action_items_under_for_next_week():
    doc = {"body": {"content": [
        _para("For next week", "HEADING_2"),
        _para("Talk to bob about widget"),
        _para("File launchpad bug for crash"),
        _para("Other section", "HEADING_2"),
        _para("ignored content"),
    ]}}
    client = FakeDocsAPI(doc)
    items = gdocs_adapter.fetch(_subject(), _settings(), _client=client)
    titles = [i.title for i in items]
    assert "Talk to bob about widget" in titles
    assert "File launchpad bug for crash" in titles
    assert "ignored content" not in titles


def test_fetch_action_items_under_carried_over():
    doc = {"body": {"content": [
        _para("Carried over from last week", "HEADING_2"),
        _para("Review the alpha doc"),
        _para("For next week", "HEADING_2"),
        _para("Schedule architecture sync"),
    ]}}
    client = FakeDocsAPI(doc)
    items = gdocs_adapter.fetch(_subject(), _settings(), _client=client)
    sections = {i.raw["section"] for i in items}
    assert "carried_over" in sections
    assert "for_next_week" in sections


def test_action_items_have_bucket_none_and_correct_kind():
    doc = {"body": {"content": [
        _para("For next week", "HEADING_2"),
        _para("do the thing"),
    ]}}
    client = FakeDocsAPI(doc)
    items = gdocs_adapter.fetch(_subject(), _settings(), _client=client)
    assert all(i.kind == "action_item" for i in items)
    assert all(i.bucket == Bucket.NONE for i in items)
    assert items[0].source == "gdocs"


def test_fetch_empty_when_no_matching_sections():
    doc = {"body": {"content": [
        _para("Topics to discuss", "HEADING_2"),
        _para("random note"),
    ]}}
    client = FakeDocsAPI(doc)
    items = gdocs_adapter.fetch(_subject(), _settings(), _client=client)
    assert items == []


def test_fetch_uses_subject_doc_id():
    doc = {"body": {"content": []}}
    client = FakeDocsAPI(doc)
    gdocs_adapter.fetch(_subject(), _settings(), _client=client)
    assert client.last_doc_id == "abc123XYZ"


def test_fetch_ignores_empty_paragraphs():
    doc = {"body": {"content": [
        _para("For next week", "HEADING_2"),
        _para(""),
        _para("   "),
        _para("real item"),
    ]}}
    client = FakeDocsAPI(doc)
    items = gdocs_adapter.fetch(_subject(), _settings(), _client=client)
    assert [i.title for i in items] == ["real item"]
