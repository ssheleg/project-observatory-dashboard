#!/usr/bin/env python3
""                                                                               

                                                                     
                                                                             
                                                                                
                                                                             
                                                                              

                                                                           
                                                                      
                                                                           
                                                                             
                                                                                 
               

                                                                                
                                                                               
                                                                             
                                                                             
                                                                            
                                          

                                                                                
                                                                            
                                    
   
from __future__ import annotations


def plural(n: int) -> str:
    return "repository" if n == 1 else "repositories"


def empty_would_lose(label: str, previous_count: int, new_count: int,
                     remedy: str) -> str | None:
    ""                                                                   

                                                                              
                                                                                  
                                                                            
                                                                                
                                         
       
    if new_count or previous_count <= 0:
        return None
    return (f"the listing for {label} succeeded and returned NOTHING while the "
            f"previous one held {previous_count} {plural(previous_count)}. "
            f"Keeping the previous answer: a credential that lost access to an "
            f"organisation looks exactly like this from here, and an answer that "
            f"is older is worth more than one that is wrong. {remedy}")
