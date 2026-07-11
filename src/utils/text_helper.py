from typing import List

def split_message(text: str, limit: int = 2000) -> List[str]:
    """
    Splits a text response into chunks of up to 2000 characters to fit Discord's limits.
    Avoids breaking mid-line if possible.
    """
    if len(text) <= limit:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk = ""

    for line in lines:
        if len(line) > limit:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            temp_line = line
            while len(temp_line) > limit:
                chunks.append(temp_line[:limit])
                temp_line = temp_line[limit:]
            current_chunk = temp_line + "\n"
        elif len(current_chunk) + len(line) + 1 > limit:
            chunks.append(current_chunk.strip())
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
