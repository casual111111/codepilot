from codepilot.tools.patch import extract_changed_files


def test_extract_changed_files_from_unified_diff():
    diff = """diff --git a/a.txt b/a.txt
--- a/a.txt
+++ b/a.txt
@@ -1 +1 @@
-old
+new
diff --git a/deleted.txt b/deleted.txt
--- a/deleted.txt
+++ /dev/null
"""

    assert extract_changed_files(diff) == ["a.txt"]
