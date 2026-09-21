#!/usr/bin/env python3
""                                                                        

                                                                              
                                                                          
                                                                                   
                                                                       
                             

                                                                          
                                                                        
                                                                             
                                                                                
                                                                 

                                                                                 
                                                        
                                                                             
                                                                           
                                                                       
                               
                                                      
                                                                             
                                      
                                                              
                                                                

                                                                 
                                                                               
                                                                         
                                                                               
                                     

                                                                                 
                                                                                 
                                                                            
                                                                                
                                                                             
   
from __future__ import annotations
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths                                                                      


def has_store() -> bool:
    ""                                                                     

                                                                           
                                                                               
                                                                               
                                                                            
                                                  
       
    try:
        return paths.DB.is_file() and paths.DB.stat().st_size > 0
    except OSError:
        return False


def has_receipt(name: str) -> bool:
    ""                                                                 
    try:
        return (paths.SCRATCH / name).is_file()
    except OSError:
        return False


def needs(what: str, present: bool, covered: str) -> bool:
    ""                                                                          

                                                                           
                                                                                
                                                  
       
    if present:
        return True
    print(f"  NOTE  {what} is not on this machine, so the assertions below were "
          f"not made [covered: {covered}]")
    return False
