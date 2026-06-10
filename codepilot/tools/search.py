from codepilot.tools.filesystem import list_project_files, read_text_file


def grep_search(
    query: str,
    root: str = ".",
    max_results: int = 50,
) -> list[dict]:
    results: list[dict] = []
    query_lower = query.lower()

    for file_path in list_project_files(root):
        try:
            content = read_text_file(file_path, root=root)
        except Exception:
            continue

        for line_number, line in enumerate(content.splitlines(), start=1):
            if query_lower in line.lower():
                results.append(
                    {
                        "path": file_path,
                        "line": line_number,
                        "content": line.strip(),
                    }
                )

                if len(results) >= max_results:
                    return results

    return results
