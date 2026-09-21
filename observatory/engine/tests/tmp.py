#!/usr/bin/env python3
""                                                             

                                                                              
                                                                    
                                                                                
                                                                              
                                      

                                                                                
                                                                               
                                                                                 
                                                                              
                                         

                                                                           
                                                                              
                                                                             
                                                                                 
                                                                                   
                                                                                 
                                    

                                                                               
                                                                           
                                                        
   
from __future__ import annotations
import atexit
import shutil
import tempfile


def mkdtemp(prefix: str = "observatory-") -> str:
    ""                                                                     
    path = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, path, ignore_errors=True)
    return path
