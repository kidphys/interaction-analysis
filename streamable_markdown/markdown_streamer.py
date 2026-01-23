class MarkdownStreamer:
    def __init__(self):
        self.buffer = ""
        self.in_code_block = False
        self.code_header_removed = False
        self.code_lang = ""
        self.latest_output = []

    def add(self, text: str):
        self.buffer += text
        self.latest_output = []
        self._process_buffer()

    def _process_buffer(self):
        while True:
            if not self.in_code_block:
                idx = self.buffer.find("```")

                if idx == -1:
                    partial_len = self._partial_backticks_at_end(self.buffer)
                    if partial_len > 0:
                        if len(self.buffer) > partial_len:
                            self.latest_output.append(self.buffer[:-partial_len])
                        self.buffer = self.buffer[-partial_len:]
                    else:
                        if self.buffer:
                            self.latest_output.append(self.buffer)
                            self.buffer = ""
                    return

                # emit normal text before code block
                if idx > 0:
                    self.latest_output.append(self.buffer[:idx])

                # enter code block
                self.buffer = self.buffer[idx + 3:]
                self.in_code_block = True
                self.code_header_removed = False
                self.code_lang = ""

            else:
                # parse language header (first line after ```)
                if not self.code_header_removed:
                    nl = self.buffer.find("\n")
                    if nl == -1:
                        return

                    self.code_lang = self.buffer[:nl].strip()
                    self.buffer = self.buffer[nl + 1:]
                    self.code_header_removed = True
                    continue

                # find end of code block
                idx = self.buffer.find("```")
                if idx == -1:
                    return

                code_content = self.buffer[:idx]

                self.latest_output.append({
                    "type": self.code_lang or "text",
                    "content": code_content
                })

                self.buffer = self.buffer[idx + 3:]
                self.in_code_block = False

    def _partial_backticks_at_end(self, s: str) -> int:
        if s.endswith("``"):
            return 2
        if s.endswith("`"):
            return 1
        return 0

    def get_markdowns(self):
        return self.latest_output
