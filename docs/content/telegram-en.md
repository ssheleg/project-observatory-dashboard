You kept your API key out of Git. Did you keep it out of your Claude Code history?

A diagnostic command prints a credential. The result can remain in a session record. An optional memory plugin can retain it after the task is finished.

Your app still works. Nothing about that tells you where the key was copied.

In our local setup, a cleanup pass recorded 202 value-replacement events: 66 in claude-mem SQLite and 136 in Chroma SQLite. These were retained local copies, not 202 unique keys or proof of theft.

I built Project Observatory to inspect selected artifacts for known credential values without repeating those values in the findings. The full engine is now open source; your keys and project data stay in your own workspace.

I wrote up how copies can accumulate, what we actually found, and what to check before sharing another transcript:
https://observatory.sshlg.me/field-notes/
