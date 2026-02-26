import os


def split_text_file(input_filename, output_filename, max_chars=2000, prefix="!multi\n"):
    # Calculate the effective limit (2000 - length of the prefix)
    # We want the prefix + content to be <= 2000
    effective_limit = max_chars - len(prefix)

    if not os.path.exists(input_filename):
        print(f"Error: {input_filename} not found.")
        return

    with open(input_filename, "r", encoding="utf-8") as f:
        text = f.read()

    lines = text.splitlines()
    chunks = []
    current_chunk_lines = []
    current_length = 0

    for line in lines:
        # +1 accounts for the newline character that will be added by join()
        line_length = len(line) + 1

        # Check if adding this line exceeds the effective limit
        if current_length + line_length > effective_limit:
            # Save the current set of lines as a chunk (prefixed with !multi)
            if current_chunk_lines:
                chunks.append(prefix + "\n".join(current_chunk_lines))

            # Start a new chunk with the current line
            current_chunk_lines = [line]
            current_length = line_length
        else:
            current_chunk_lines.append(line)
            current_length += line_length

    # Add the final chunk
    if current_chunk_lines:
        chunks.append(prefix + "\n".join(current_chunk_lines))

    # Write the chunks to the output file
    with open(output_filename, "w", encoding="utf-8") as f:
        # We separate chunks with an extra newline for readability in the output file
        f.write("\n\n".join(chunks))

    print(f"Done! Split into {len(chunks)} chunks.")
    print(f"Output saved to: {output_filename}")


# --- Execution ---
if __name__ == "__main__":
    # Change these filenames as needed
    IN_FILE = "script.txt"
    OUT_FILE = "output_chunks.txt"

    split_text_file(IN_FILE, OUT_FILE)
