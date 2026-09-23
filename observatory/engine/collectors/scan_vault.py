import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import atomic
import paths
import json, re, sys
from pathlib import Path
V = paths.VAULT
KNOWN: set[str] = set()
REPO_RX = re.compile(r"github\.com[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?=[\s)\]\"'`,]|$)")
DATA_RX = re.compile(r"(?:~/)?DATA/([A-Za-z0-9_.-]+)")


def opening(text: str) -> str:
    ""                                                                           

                                                                                                   
                                                                                 
                                                                                  
                                                                                             
                                                                                  
                                                                                
                                          
       
    body = text
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end >= 0:
            body = body[end + 4:]
    cut = body.find("\n## ")
    return body if cut < 0 else body[:cut]
BB_RX   = re.compile(r"bitbucket\.org[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?=[\s)\]\"'`,]|$)")
def split_front_matter(text):
    if not text.startswith("---"): return {}, text
    end = text.find("\n---", 3)
    if end < 0: return {}, text
    return parse_fm(text[3:end]), text[end+4:]
def parse_fm(block):
    fm, key, buf = {}, None, []
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            if key: fm[key] = " ".join(buf).strip()
            key, val = m.group(1), m.group(2).strip()
            buf = [] if val in (">-", ">", "|", "|-", "") else [val]
        elif key and line.startswith((" ", "\t")):
            buf.append(line.strip())
        elif key:
            fm[key] = " ".join(buf).strip(); key, buf = None, []
    if key: fm[key] = " ".join(buf).strip()
    return fm
def clean(s):
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", lambda m: m.group(1).split("/")[-1], s)
    return re.sub(r"\s+", " ", re.sub(r"[*`]", "", s)).strip()
def summary(text):
    fm, body = split_front_matter(text)
    if fm.get("summary"): return clean(fm["summary"])[:400]
    out = []
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "- ", "* ", "|", "> ", "```", "!")):
            if out: break
            continue
        out.append(s)
        if len(" ".join(out)) > 300: break
    return clean(" ".join(out))[:400]

def scan() -> list[dict]:
    ""                                                                         

                                                                              
                                                                       
                                                                                 
                                                                             
                                                                               
                        
       
    global KNOWN
    KNOWN = {d["name"] for d in json.loads((paths.REGISTRY / "domains.json").read_text())["domains"]}
    rows=[]
    for d in sorted((V/"projects").iterdir()):
        if not d.is_dir(): continue
        notes=sorted(d.rglob("*.md"))
        # A directory with no notes is not a project. Deleting a folder's last note
        # leaves the empty subdirectories behind, and those kept the project alive in
        # the registry with `vault_notes: 0` — a project that exists because a
        # filesystem entry does.
        if not notes:
            continue
        blob="\n".join(p.read_text(encoding="utf-8",errors="replace") for p in notes)
        ov = d/f"{d.name}.md"
        rows.append({
            "folder": d.name,
            "overview": str(ov.relative_to(V)) if ov.exists() else "",
            # The newest write anywhere in the project's notes — the freshness
            # the wiki can claim. A note that predates weeks of activity is a
            # narrative that stopped describing its subject, and until this
            # date existed nothing could measure that.
            "notes_updated_on": __import__("datetime").datetime.fromtimestamp(
                max(n.stat().st_mtime for n in notes),
                __import__("datetime").timezone.utc).strftime("%Y-%m-%d"),
            "note_count": len(notes),
            "summary": summary(ov.read_text(encoding="utf-8",errors="replace")) if ov.exists() else "",
            "domains": sorted({x for x in KNOWN if re.search(r"(?<![\w.-])"+re.escape(x)+r"(?![\w-])", blob)}),
            "github": sorted({f"{a}/{b}" for a,b in REPO_RX.findall(blob)}),
            "bitbucket": sorted({f"{a}/{b}" for a,b in BB_RX.findall(blob)}),
            # From the OVERVIEW's opening only — see opening().
            "datapaths": sorted(set(DATA_RX.findall(
                opening(ov.read_text(encoding="utf-8", errors="replace")) if ov.exists() else ""))),
        })
    return rows


if __name__ == "__main__":
    import configuration
    if not configuration.enabled("wiki"):
        print("wiki: not configured (integration disabled)")
        raise SystemExit(0)
    rows = scan()
    atomic.write_json(sys.argv[1], rows)
    print(f"{len(rows)} vault project folders; with overview: "
          f"{sum(1 for r in rows if r['overview'])}; naming a domain: "
          f"{sum(1 for r in rows if r['domains'])}")
