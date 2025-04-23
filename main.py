"""
Medical Treatment Review System (Simplified)

A system that helps doctors review treatment plans using AI analysis,
while requiring explicit human confirmation for high-risk medical decisions.
"""

import os
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

from llama_index.llms.openai import OpenAI
from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.workflow import Context
from llama_index.core.workflow import (
    InputRequiredEvent,
    HumanResponseEvent
)

# Define risk levels for medical decisions
class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Define treatment categories
class TreatmentCategory(str, Enum):
    MEDICATION = "medication"
    PROCEDURE = "procedure"  
    THERAPY = "therapy"
    SURGERY = "surgery"
    LIFESTYLE = "lifestyle"

# Treatment model for schema compatibility
class TreatmentModel(BaseModel):
    treatment_id: str
    category: TreatmentCategory
    name: str
    description: str
    rationale: str
    risk_level: RiskLevel
    alternatives: List[str]
    interactions: List[str]
    approved: bool = False
    approved_by: Optional[str] = None
    approval_date: Optional[datetime] = None

# Patient model for schema compatibility
class PatientModel(BaseModel):
    patient_id: str
    name: str
    age: int
    conditions: List[str]
    allergies: List[str]
    medications: List[str]
    medical_history: str

# Initialize the LLM
def init_llm():
    """Initialize the LLM with appropriate parameters"""
    llm = OpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.environ.get("OPENAI_API_KEY")
    )
    return llm

# Function to generate mock treatment recommendations
def get_mock_treatments():
    """Generate mock treatment recommendations"""
    treatments = [
        {
            "treatment_id": "TRT-001",
            "category": "medication",
            "name": "Metformin 500mg",
            "description": "Oral medication taken twice daily",
            "rationale": "First-line treatment for Type 2 Diabetes with good efficacy and safety profile",
            "risk_level": "low",
            "alternatives": ["Lifestyle modifications", "Sulfonylureas"],
            "interactions": ["May interact with certain contrast dyes used in medical tests"],
            "approved": False,
            "approved_by": None,
            "approval_date": None
        },
        {
            "treatment_id": "TRT-002",
            "category": "procedure",
            "name": "Coronary Angioplasty",
            "description": "Minimally invasive procedure to widen narrowed coronary arteries",
            "rationale": "Patient has significant coronary artery blockage causing angina symptoms",
            "risk_level": "high",
            "alternatives": ["Medical management with anti-anginal medications", "Coronary artery bypass graft"],
            "interactions": ["Risk increases with current anticoagulant therapy"],
            "approved": False,
            "approved_by": None,
            "approval_date": None
        }
    ]
    return treatments

# Function to get mock patient data
def get_mock_patient():
    """Generate mock patient data"""
    patient = {
        "patient_id": "P12345",
        "name": "John Doe",
        "age": 67,
        "conditions": ["Type 2 Diabetes", "Coronary Artery Disease", "Hypertension"],
        "allergies": ["Penicillin", "Sulfa drugs"],
        "medications": ["Lisinopril", "Atorvastatin", "Aspirin"],
        "medical_history": "History of myocardial infarction 5 years ago. Appendectomy in 2010."
    }
    return patient

# Tool function to confirm high-risk treatments
async def confirm_treatment(ctx: Context, treatment_name: str, risk_level: str, patient_name: str, doctor_name: str) -> str:
    """Request human confirmation for a treatment"""
    
    confirmation_text = f"""
    MEDICAL TREATMENT CONFIRMATION REQUIRED
    
    Patient: {patient_name}
    
    RECOMMENDED TREATMENT:
    - Name: {treatment_name}
    - Risk Level: {risk_level.upper()}
    
    THIS TREATMENT REQUIRES EXPLICIT CONFIRMATION DUE TO ITS {risk_level.upper()} RISK LEVEL.
    """
    
    # Emit an event to the external stream to be captured
    ctx.write_event_to_stream(
        InputRequiredEvent(
            prefix=confirmation_text + f"\n\n{doctor_name}, do you confirm this treatment? (yes/no):",
            user_name=doctor_name,
        )
    )
    
    # Wait until we see a HumanResponseEvent
    response = await ctx.wait_for_event(
        HumanResponseEvent, requirements={"user_name": doctor_name}
    )
    
    # Act on the input from the event
    if response.response.strip().lower() == "yes":
        return f"Treatment {treatment_name} has been approved by {doctor_name}."
    else:
        return f"Treatment {treatment_name} has been rejected."

# Create the medical workflow
def create_workflow(llm):
    """Create the agent workflow for medical treatment review"""
    
    workflow = AgentWorkflow.from_tools_or_functions(
        [confirm_treatment],
        llm=llm,
        system_prompt="""
        You are a Medical Treatment Assistant AI.
        Your role is to review treatments and get doctor approval for high-risk treatments.
        If a treatment has "high" or "critical" risk level, you MUST use the confirm_treatment function.
        Low risk treatments can be approved automatically.
        """
    )
    
    return workflow

# Main function to run the medical review system
async def main():
    # Initialize LLM
    llm = init_llm()
    
    # Create workflow
    workflow = create_workflow(llm)
    
    # Get mock data
    treatments = get_mock_treatments()
    patient = get_mock_patient()
    doctor_name = "Dr. Smith"
    
    # Process each treatment
    for treatment in treatments:
        print(f"\nProcessing treatment: {treatment['name']}")
        print(f"Risk level: {treatment['risk_level']}")
        
        # For high-risk treatments, agent will use confirm_treatment
        # For low-risk treatments, agent will approve automatically
        user_msg = f"""Review this treatment for {patient['name']}:
                        - Treatment: {treatment['name']}
                        - Category: {treatment['category']}
                        - Description: {treatment['description']}
                        - Risk Level: {treatment['risk_level']}
                        - Alternatives: {', '.join(treatment['alternatives'])}

                        Please follow medical protocol for approval based on risk level.
                    """
        
        # Run the workflow
        handler = workflow.run(
            user_msg=user_msg,
            context_dict={
                "treatment_name": treatment['name'],
                "risk_level": treatment['risk_level'],
                "patient_name": patient['name'],
                "doctor_name": doctor_name
            }
        )
        
        # Process events from the agent
        async for event in handler.stream_events():
            # Handle InputRequiredEvent events (doctor confirmation)
            if isinstance(event, InputRequiredEvent):
                print("\n" + event.prefix)
                response = input()
                handler.ctx.send_event(
                    HumanResponseEvent(
                        response=response,
                        user_name=event.user_name,
                    )
                )
        
        # Get and print the response
        response = await handler
        print(f"\nResult: {response}")
        
        # Update treatment approval status based on response
        if "approved" in str(response).lower():
            treatment["approved"] = True
            treatment["approved_by"] = doctor_name
            treatment["approval_date"] = datetime.now().isoformat()
    
    # Generate treatment report
    print("\n===== TREATMENT PLAN SUMMARY =====")
    for treatment in treatments:
        status = "APPROVED" if treatment.get('approved', False) else "NOT APPROVED"
        print(f"- {treatment['name']}: {status}")
        if treatment.get('approved', False):
            print(f"  Approved by: {treatment.get('approved_by', 'Unknown')}")
            print(f"  Approval date: {treatment.get('approval_date', 'Unknown')}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
