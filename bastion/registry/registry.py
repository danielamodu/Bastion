import os
from google.cloud import firestore
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

# Initialize Firestore client
# Explicitly using project and default database
db = firestore.Client(project="bastion-505622", database="default")

def register_agent(agent_id: str, endpoint: str, capabilities: list) -> None:
    """
    Registers or updates an agent in the Firestore 'agents' collection.
    """
    doc_ref = db.collection('agents').document(agent_id)
    doc_ref.set({
        'endpoint': endpoint,
        'capabilities': capabilities,
        'status': 'active'
    }, merge=True)
    print(f"Successfully registered agent: {agent_id}")

def discover_agent(capability: str) -> dict:
    """
    Queries Firestore for an active agent matching the specified capability.
    Returns the first matching agent's record.
    """
    agents_ref = db.collection('agents')
    # Query for documents where the capabilities array contains the target capability
    # and the status is active.
    query = agents_ref.where(filter=firestore.FieldFilter('capabilities', 'array_contains', capability))\
                      .where(filter=firestore.FieldFilter('status', '==', 'active'))
    
    results = query.stream()
    
    for doc in results:
        data = doc.to_dict()
        data['agent_id'] = doc.id
        return data
        
    return None
