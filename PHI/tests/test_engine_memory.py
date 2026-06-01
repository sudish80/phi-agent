import os
import tempfile
import pytest
from backend.orchestrator.engine.memory.store import MemoryStore, WikiStore, MemoryEntry, WikiPage


class TestMemoryStore:
    @pytest.fixture
    def store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ms = MemoryStore(store_dir=tmpdir)
            yield ms

    def test_save_and_get(self, store):
        store.save("key1", "hello world", source="test", tags=["greeting"])
        entry = store.get("key1")
        assert entry is not None
        assert entry.key == "key1"
        assert entry.content == "hello world"
        assert entry.source == "test"
        assert entry.tags == ["greeting"]

    def test_get_nonexistent(self, store):
        assert store.get("nope") is None

    def test_search_by_content(self, store):
        store.save("doc1", "the quick brown fox")
        store.save("doc2", "jumps over the lazy dog")
        results = store.search("fox")
        assert len(results) == 1
        assert results[0].key == "doc1"

    def test_search_by_key(self, store):
        store.save("important_note", "content here")
        results = store.search("IMPORTANT")
        assert len(results) == 1

    def test_search_returns_empty_for_no_match(self, store):
        store.save("a", "hello")
        assert store.search("zzzzz") == []

    def test_delete_existing(self, store):
        store.save("del_me", "to be deleted")
        assert store.delete("del_me") is True
        assert store.get("del_me") is None

    def test_delete_nonexistent(self, store):
        assert store.delete("ghost") is False

    def test_list_all(self, store):
        store.save("a", "first")
        store.save("b", "second")
        entries = store.list_all()
        assert len(entries) == 2

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ms1 = MemoryStore(store_dir=tmpdir)
            ms1.save("persist_key", "persisted content")
            del ms1
            ms2 = MemoryStore(store_dir=tmpdir)
            entry = ms2.get("persist_key")
            assert entry is not None
            assert entry.content == "persisted content"

    def test_sync_from_transcript(self, store):
        transcript = [
            {"role": "user", "content": "short"},
            {"role": "assistant", "content": "a" * 100},
        ]
        count = store.sync_from_transcript(transcript, "sess_1")
        assert count == 1

    def test_sync_from_transcript_short_skipped(self, store):
        transcript = [{"role": "user", "content": "hi"}]
        count = store.sync_from_transcript(transcript, "sess_2")
        assert count == 0

    def test_append_updates_existing(self, store):
        store.save("key", "original")
        store.save("key", "updated")
        entry = store.get("key")
        assert entry.content == "updated"


class TestWikiStore:
    @pytest.fixture
    def wiki(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = WikiStore(store_dir=tmpdir)
            yield ws

    def test_create_and_get(self, wiki):
        wiki.save("Test Page", "Hello Wiki")
        page = wiki.get("Test Page")
        assert page is not None
        assert page.title == "Test Page"
        assert page.content == "Hello Wiki"

    def test_get_nonexistent(self, wiki):
        assert wiki.get("NoPage") is None

    def test_search_finds_page(self, wiki):
        wiki.save("Python Guide", "Learn Python programming")
        results = wiki.search("Python")
        assert len(results) == 1
        assert results[0].title == "Python Guide"

    def test_search_no_match(self, wiki):
        wiki.save("OnlyOne", "content")
        assert wiki.search("zzzzz") == []

    def test_list_titles(self, wiki):
        wiki.save("Page A", "a")
        wiki.save("Page B", "b")
        titles = wiki.list_titles()
        assert "Page A" in titles
        assert "Page B" in titles

    def test_save_with_tags(self, wiki):
        wiki.save("Tagged", "content here", tags=["python", "tutorial"])
        page = wiki.get("Tagged")
        assert "python" in page.tags
        assert "tutorial" in page.tags

    def test_tags_parsed_from_frontmatter(self, wiki):
        wiki.save("TagsTest", "body", tags=["alpha", "beta"])
        page = wiki.get("TagsTest")
        assert page.tags == ["alpha", "beta"]
        assert page.content == "body"

    def test_file_path_safe_title(self, wiki):
        wiki.save("Path/With/Slashes", "content")
        page = wiki.get("Path/With/Slashes")
        assert page is not None
        assert page.content == "content"
