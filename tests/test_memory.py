"""
Tests for the memory hierarchy (HotMemory, WarmMemory, ColdMemory).
"""
from core.memory.hierarchy import ColdMemory, HotMemory, MemoryEntry, WarmMemory


def test_hot_memory_fifo_eviction():
    mem = HotMemory(max_tokens=10, avg_chars_per_token=1)  # 10 char budget
    for i in range(20):
        mem.add(MemoryEntry(text=f"{i}-item"))  # 6 chars each
    # Should have evicted early entries — context should be small
    context = mem.get_context()
    total_chars = sum(len(c) for c in context)
    assert total_chars <= 10 * 4 + 10  # some slack for rounding


def test_warm_memory_retrieval_returns_results():
    mem = WarmMemory(top_k=2)
    mem.index(MemoryEntry(text="circuit breaker pattern"))
    mem.index(MemoryEntry(text="saga pattern for distributed transactions"))
    mem.index(MemoryEntry(text="star topology hub"))
    results = mem.retrieve("circuit breaker")
    assert len(results) > 0


def test_cold_memory_write_and_read():
    mem = ColdMemory()
    entry = MemoryEntry(text="bounded context definition", metadata={"tags": ["ddd"]})
    mem.write("bc:orders", entry)
    retrieved = mem.read("bc:orders")
    assert retrieved is not None
    assert retrieved.text == "bounded context definition"


def test_cold_memory_search_by_tag():
    mem = ColdMemory()
    mem.write("k1", MemoryEntry(text="entry1", metadata={"tags": ["ddd", "arch"]}))
    mem.write("k2", MemoryEntry(text="entry2", metadata={"tags": ["cicd"]}))
    result = mem.search_by_tag("ddd")
    assert len(result) == 1
    assert result[0].text == "entry1"
