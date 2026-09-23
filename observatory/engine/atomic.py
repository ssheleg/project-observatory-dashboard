#!/usr/bin/env python3
""                                      

                                                                               
                                                                                
                                                                               
                                                                              
                                                                                
                                              

                                                                               
                                                                             
                                                                              
                                                                                
                                                                             

                                                                                
                                                            

                                                                                     
                                                                                  
   
from __future__ import annotations
import errno, json, os, pathlib, shutil, tempfile
from typing import Any


def write_json(path: str | os.PathLike, data: Any, *, indent: int = 1,
               ensure_ascii: bool = False) -> pathlib.Path:
    """Serialise first, replace second. The destination is never truncated.

    The temp file is created in the SAME directory, because `os.replace` is
    atomic only within one filesystem — a temp in `/tmp` would make this a copy
    across devices and reintroduce the partial write it exists to prevent."""
    dest = pathlib.Path(path)
    # Refuse future registry versions and retain optional extension fields.
    import configuration
    import paths
    if dest.parent.resolve() == paths.REGISTRY.resolve() and dest.suffix == ".json":
        configuration.validate_registry_document(dest, data)
        if dest.exists():
            old = configuration.read_json(dest)
            configuration.validate_registry_document(dest, old)
            data = {**old, **data}
    if any(p.is_symlink() for p in (dest, *dest.parents)):
        raise ValueError("Output path must not contain symbolic links")
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=indent, ensure_ascii=ensure_ascii)
            # A TRAILING NEWLINE, because these files are read in diffs. The
            # registry emit used to append one and this function did not, so
            # routing the emit through here rewrote the last line of
            # six tracked documents with `\ No newline at end of file` — a
            # whole-file churn in the operator's diff for a byte nobody
            # intended to change. Every writer in the repository goes through
            # this function, so the convention belongs here.
            fh.write("\n")
            fh.flush()
            # The rename is atomic; the CONTENT reaching the platter is not
            # implied by it. On a machine that has already lost a database to a
            # write it could not finish, that distinction is the whole point.
            os.fsync(fh.fileno())
        os.replace(tmp, dest)
        return dest
    except BaseException as exc:
        # Including KeyboardInterrupt and SystemExit: a half-written temp file
        # left in a scanned directory is litter the next run would glob.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        # A FULL DISK, NAMED. On 2026-09-07 at 06:39 the volume filled and four
        # collectors died here in the same tick, each with a five-frame
        # traceback ending in `[Errno 28] No space left on device` — so the tick
        # reported four failed steps and the log held four stack traces for ONE
        # cause. The failure is correct and stays; what was wrong was that the
        # cheapest fact to state was the hardest one to find. Raising it as a
        # sentence means every caller of this function inherits the sentence.
        if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
            free = shutil.disk_usage(dest.parent).free
            raise OSError(
                errno.ENOSPC,
                f"no space left on the volume holding {dest} — {free // (1024*1024)} MiB "
                f"free. Nothing was written and the destination is intact; every "
                f"writer in this repository fails the same way until space is "
                f"freed.") from exc
        raise


def write_text(path: str | os.PathLike, text: str) -> pathlib.Path:
    ""                                                          

                                                                               
                                                                         
                                                                              
                                                     
                                                                          
                                                                                 
                                                                                
                                                                          
                                                                            
                         

                                                                             
                                                                              
                                                       

                                                                               
                                                                                 
                                                                                 
                                                                   
               
       
    dest = pathlib.Path(path)
    if any(p.is_symlink() for p in (dest, *dest.parents)):
        raise ValueError("Output path must not contain symbolic links")
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, dest)
        return dest
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_json_carrying(path: str | os.PathLike, doc: dict, *,
                        stamps: tuple[str, ...], now: str, **kw) -> tuple[pathlib.Path, bool]:
    ""                                                                    

                            

                                                                            
                                                                            
                                                                                
                                                                               
                                                                             
                                                                               
                               

                                                                                
                                                                                 
                                                                                
                                                                           
                                                           
       
    dest = pathlib.Path(path)
    body = {k: v for k, v in doc.items() if k not in stamps}
    carried: dict[str, Any] = {}
    if dest.is_file():
        try:
            old = json.loads(dest.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            old = None
        if isinstance(old, dict):
            old_stamps = {k: old.pop(k, None) for k in stamps}
            if old == body:
                carried = {k: v for k, v in old_stamps.items() if v is not None}
    out = dict(doc)
    for k in stamps:
        out[k] = carried.get(k, now)
    # The key ORDER is preserved from `doc`, because these files are read by
    # people in a diff: a stamp that jumps to the end of the object on the run
    # that carries it forward would show as a move of every line between.
    write_json(dest, out, **kw)
    return dest, not carried
