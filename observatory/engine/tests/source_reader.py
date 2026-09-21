#!/usr/bin/env python3
""                                                                  

                                                                                
                                                                             
                                                                         
                  

                   

                                                                             
                                                                                   
                                      
                                                                               
                            
                                                                                
                                                                                 
                 

                                                                              
                                                                                
                                                                                

                                                                             
                                                                                  
                                           
   
from __future__ import annotations
import io
import tokenize


def code_only(src: str) -> str:
    ""                                                                    

                                                                            
                                                                   

                                                                         
                                                                            
                                                                               
                                                                                
                                                                                
                                                                      
       
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
                                                                            
                                                                             
        raise
    lines = src.splitlines(keepends=True)
    grid = [list(l) for l in lines]
    for tok in tokens:
        if tok.type not in (tokenize.COMMENT, tokenize.STRING, tokenize.FSTRING_START,
                            tokenize.FSTRING_MIDDLE, tokenize.FSTRING_END):
            continue
        (r1, c1), (r2, c2) = tok.start, tok.end
        for row in range(r1 - 1, min(r2, len(grid))):
            line = grid[row]
            start = c1 if row == r1 - 1 else 0
            end = c2 if row == r2 - 1 else len(line)
            for col in range(start, min(end, len(line))):
                if line[col] != "\n":
                    line[col] = " "
    return "".join("".join(l) for l in grid)


def appears_in_code(src: str, needle: str) -> bool:
    ""                                                                            
    return needle in code_only(src)


def code_lines(src: str, needle: str) -> list[int]:
    ""                                                                         
    hits = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        if needle in tok.line and tok.start[0] not in hits:
                                                                                
                                                                                 
            bare = tok.line.split("#", 1)[0]
            if needle in bare:
                hits.append(tok.start[0])
    return hits


def code_keeping_strings(src: str) -> str:
    ""                                                                         

                                                                                
                                                                     

                                                                  
                                                                       
                                                                              
                                                                     
                                                                             
                                                                               
                                                                         
                                                                        
                                                  

                                                                            
                                                                             
                                                                              
                                                                            
                                
       
    import re
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "tools"))
    import check_paths
    return re.sub(r"^\s*//.*$", "", check_paths.prose_removed(src), flags=re.M)
