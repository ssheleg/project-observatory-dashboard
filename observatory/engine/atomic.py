#!/usr/bin/env python3
""                                      

                                                                               
                                                                                
                                                                               
                                                                              
                                                                                
                                              

                                                                               
                                                                             
                                                                              
                                                                                
                                                                             

                                                                                
                                                            

                                                                                     
                                                                                  
   
from __future__ import annotations
import errno, json, os, pathlib, shutil, tempfile
from typing import Any


def write_json(path: str | os.PathLike, data: Any, *, indent: int = 1,
               ensure_ascii: bool = False) -> pathlib.Path:
    ""                                                                     

                                                                           
                                                                                 
                                                                             
    dest = pathlib.Path(path)
                                                                           
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
                                                                            
                                                                            
                                                                               
                                                                            
                                                                       
                                                                             
                                                            
            fh.write("\n")
            fh.flush()
                                                                           
                                                                               
                                                                             
            os.fsync(fh.fileno())
        os.replace(tmp, dest)
        return dest
    except BaseException as exc:
                                                                              
                                                                        
        try:
            os.unlink(tmp)
        except OSError:
            pass
                                                                               
                                                                       
                                                                                  
                                                                               
                                                                              
                                                                             
                                                                             
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
                                                                            
                                                                              
                                                                         
    write_json(dest, out, **kw)
    return dest, not carried
