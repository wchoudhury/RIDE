
import json
from typing import Callable, Any
from dataclasses import asdict

try:
    import fastdds
    HAS_FASTDDS = True
except ImportError:
    HAS_FASTDDS = False
    print("FastDDS not available")


class DDSInterface:
    """publishing and subscribing"""
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.participant = None
        self.publishers = {}
        self.subscribers = {}
        
        if HAS_FASTDDS:
            factory = fastdds.DomainParticipantFactory.get_instance()
            qos = fastdds.DomainParticipantQos()
            self.participant = factory.create_participant(domain_id, qos)
            print(f"[DDS] Connected to domain {domain_id}")
        else:
            print(f"[TEST MODE] Domain {domain_id}")
    
    def publish(self, topic: str, message: Any):
    
        if HAS_FASTDDS and self.participant:
            
            print(f"[DDS] Publishing to {topic}")
        else:
            
            try:
                data = asdict(message)
                print(f"[{topic}] {json.dumps(data, indent=2)}")
            except:
                print(f"[{topic}] {message}")
    
    def subscribe(self, topic: str, callback: Callable):
       
        self.subscribers[topic] = callback
        
        if HAS_FASTDDS and self.participant:
            
            print(f"[DDS] Subscribed to {topic}")
        else:
            print(f"[TEST MODE] Subscribed to {topic}")
    
    def close(self):
        
        if HAS_FASTDDS and self.participant:
            factory = fastdds.DomainParticipantFactory.get_instance()
            factory.delete_participant(self.participant)
            print("[DDS] Closed")
