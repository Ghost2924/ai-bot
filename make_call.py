import os
import sys
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(current_dir, '.env'))

from twilio.rest import Client
from scenarios import SCENARIOS

def main():
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")
    to_number = os.getenv("TO_PHONE_NUMBER", "+18054398008")
    PUBLIC_URL = os.getenv("PUBLIC_URL")
    
    # Validation checks
    missing_vars = []
    if not account_sid:
         missing_vars.append("TWILIO_ACCOUNT_SID")
    if not auth_token:
         missing_vars.append("TWILIO_AUTH_TOKEN")
    if not from_number:
         missing_vars.append("TWILIO_PHONE_NUMBER")
    if not PUBLIC_URL:
         missing_vars.append("PUBLIC_URL")
         
    if missing_vars:
         print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
         print("Please create a '.env' file based on '.env.example' and configure these values.")
         sys.exit(1)
         
    # Handle Scenario Selection
    selected_scenario_id = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in SCENARIOS:
            selected_scenario_id = arg
            print(f"Using command-line scenario: '{selected_scenario_id}'")
        else:
            print(f"Scenario ID '{arg}' not found. Falling back to selection menu.")
            
    if not selected_scenario_id:
        list_scenarios = list(SCENARIOS.keys())
        print("\nAvailable Patient Scenarios:")
        for idx, key in enumerate(list_scenarios, 1):
            name = SCENARIOS[key]["name"]
            desc = SCENARIOS[key]["description"]
            print(f"  [{idx}] {name}\n      ({desc})")
            
        try:
            choice = input("\nSelect a scenario (number or ID, default [1] - Default Receptionist): ").strip()
            if not choice:
                selected_scenario_id = "default_receptionist"
            elif choice.isdigit():
                val = int(choice)
                if 1 <= val <= len(list_scenarios):
                    selected_scenario_id = list_scenarios[val - 1]
                else:
                    print(f"Invalid option. Defaulting to 'default_receptionist'.")
                    selected_scenario_id = "default_receptionist"
            elif choice in SCENARIOS:
                selected_scenario_id = choice
            else:
                print(f"Invalid selection. Defaulting to 'default_receptionist'.")
                selected_scenario_id = "default_receptionist"
        except (KeyboardInterrupt, SystemExit):
            print("\nCall initiation cancelled.")
            sys.exit(0)
            
    scenario_details = SCENARIOS[selected_scenario_id]
    print(f"\nTriggering call with Scenario: {scenario_details['name']}")
    print(f"Description: {scenario_details['description']}")
         
    # Build the TwiML URL
    twiml_url = f"https://{os.getenv('PUBLIC_URL')}/incoming-call?scenario_id={selected_scenario_id}"
    
    print(f"\nInitializing Twilio Client...")
    try:
        client = Client(account_sid, auth_token)
        
        print(f"Initiating outbound call:")
        print(f"  From (Twilio): {from_number}")
        print(f"  To (Clinic):   {to_number}")
        print(f"  TwiML URL:     {twiml_url}")
        
        call = client.calls.create(
            to=to_number,
            from_=from_number,
            url=twiml_url
        )
        
        print("\n[SUCCESS] Outbound call triggered successfully!")
        print(f"  Call SID: {call.sid}")
        print(f"  Status:   {call.status}")
        print(f"  Scenario: {selected_scenario_id}")
        print("\nMake sure your FastAPI server is running and ngrok is tunneling to your local port.")
        
    except Exception as e:
        print(f"\n[ERROR] Failed to trigger outbound call via Twilio:")
        print(f"  {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

