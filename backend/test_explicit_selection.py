"""
Test explicit product selection logic
"""
import asyncio
from app.models.conversation import ConversationState, MasterParameters

async def test():
    """Test what's in master_parameters"""

    # Simulate what should be in master_parameters after LLM extraction
    master_params = MasterParameters(
        welding_process=None,
        current_amps=None,
        voltage=None,
        material=None,
        thickness_mm=None,
        application=None,
        environment=None,
        duty_cycle=None,
        power_watts=None
    )

    # Create conversation state
    state = ConversationState()

    # Update with explicit product name
    params_dict = master_params.dict()
    params_dict['explicit_product_name'] = 'Aristo 500ix'

    print("Master parameters dict:", params_dict)
    print("Has explicit_product_name:", 'explicit_product_name' in params_dict)
    print("Value:", params_dict.get('explicit_product_name'))

    # Update state
    state.update_master_parameters(params_dict)

    # Check what's in state
    print("\nAfter update:")
    print("State master_parameters dict:", state.master_parameters.dict())
    print("Has explicit_product_name:", 'explicit_product_name' in state.master_parameters.dict())

if __name__ == "__main__":
    asyncio.run(test())
