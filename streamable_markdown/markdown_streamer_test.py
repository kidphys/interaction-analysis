from .markdown_streamer import MarkdownStreamer


def test_markdown_streamer():
    streamer = MarkdownStreamer()
    streamer.add("Hello, world!")
    assert streamer.get_markdowns() == ["Hello, world!"]


def test_markdown_streamer__yield_the_next_chunk_only():
    streamer = MarkdownStreamer()
    streamer.add("Hello, world!")
    streamer.add("world!")
    assert streamer.get_markdowns() == ["world!"]


def test_markdown_streamer__partial_code_block_yield_last_known_text():
    streamer = MarkdownStreamer()
    streamer.add("Hello, world!\n``")
    assert streamer.get_markdowns() == ["Hello, world!\n"]


def test_markdown_streamer__partial_code_block_yield_last_known_text_2():
    streamer = MarkdownStreamer()
    streamer.add("Hello, world!\n```python\nprint('Hello, world!')``")
    assert streamer.get_markdowns() == ["Hello, world!\n"]


def test_markdown_streamer__partial_code_block_yield_last_known_text_2():
    streamer = MarkdownStreamer()
    streamer.add("Hello, world!\n```python\nprint('Hello, world!')``")
    assert streamer.get_markdowns() == ["Hello, world!\n"]


def test_markdown_streamer__finish_code_block_yield_both():
    streamer = MarkdownStreamer()
    streamer.add("Hello, world!\n```python\nprint('Hello, world!')```")
    assert streamer.get_markdowns() == ["Hello, world!\n", {'type': 'python', 'content': "print('Hello, world!')"}]


def test_markdown_streamer__partially_add_finish_code_block_yield_code_block():
    streamer = MarkdownStreamer()
    streamer.add("Hello, world!\n```py")
    streamer.add("thon\nprint('Hello, world!')```")
    assert streamer.get_markdowns() == [{
      'type': 'python',
      'content': "print('Hello, world!')"
    }]