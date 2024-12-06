from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from openai import OpenAI
from dotenv import load_dotenv
import os
from email.mime.text import MIMEText
import base64

# Load environment variables from .env file
load_dotenv()

# Store processed thread IDs to avoid duplicate responses
processed_threads = set()

# Define the assistant persona and behavior
SYSTEM_MESSAGE = """
You are a helpful and friendly assistant for an e-commerce clothing brand called Shameless Collective. 
Your tone is warm, empathetic, and professional. 
Please structure your response as:
    - "subject": The subject line for the email.
    - "body": The email body text.

You respond to customer inquiries in a complete email format with:
1. A polite and appropriate subject line.
2. A greeting that addresses the customer warmly and if the mood is good, a bit informal (e.g., "Dear Customer" or "Hi there").
3. A clear and structured response in the email body, based on the customer's query.
4. A closing message that thanks the customer for supporting the brand and encourages further communication.
5. A sign-off including your name and role ("Santiago \nCo-founder Shameless Collective").

Use the same language as the customer's query:
- If the query is in English, respond in English.
- If the query is in Spanish, respond in Spanish.
Don't translate the structure of the response, always maintain the "subject" and "body" structure

Use the following rules when responding:
- For tracking an order, always include this link: https://e.amphoralogistics.com/457409f7-05cb-48b1-8805-6ac8f214552f .
- For returns or exchanges, include this link: https://e.amphoralogistics.com/457409f7-05cb-48b1-8805-6ac8f214552f and explain the steps for requesting a return or exchange.
- For issues like wrong or stained items, apologize, assure the customer the issue will be resolved, and include instructions on how to request a replacement using the returns link. Include also that the change or return will be completely free of charge
- Use formatting like bullet points or numbered steps when helpful.
- Keep the response in the below 250 tokens
- Do not use bold
"""

# Path to your service account key file
SERVICE_ACCOUNT_FILE = "google-cloud-sdk/gmail-function/gmailgenai-bc2830d7f440.json"

# Scopes for Gmail API
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Authenticate using service account
credentials = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

# Impersonate the user (replace with the email address of the Gmail account)
delegated_credentials = credentials.with_subject("hello@shamelesscollective.com")

# Build the Gmail service
service = build("gmail", "v1", credentials=delegated_credentials)

def get_unread_emails(service):
    results = service.users().messages().list(
        userId='me', q='is:unread -in:archive'
    ).execute()
    
    messages = results.get('messages', [])
    email_data = []
    
    if not messages:
        print("No new emails found.")
        return email_data

    for msg in messages:
        msg_id = msg['id']
        message = service.users().messages().get(userId='me', id=msg_id).execute()

        thread_id = message.get('threadId')

        # Skip processing if this thread is already handled
        if thread_id in processed_threads:
            print(f"Skipping thread {thread_id}, already processed.")
            continue

        email = {
            'id': msg_id,
            'threadId': thread_id,  # Store thread ID
            'snippet': message['snippet'],  # Email preview/snippet
            'payload': message['payload']  # Contains headers like sender, subject
        }
        email_data.append(email)

        # Mark this thread as processed
        processed_threads.add(thread_id)

    return email_data

def get_latest_message_in_thread(service, thread_id):
    thread = service.users().threads().get(userId="me", id=thread_id).execute()
    messages = thread.get('messages', [])
    latest_recipient_message = None
    for message in reversed(messages):  # Reverse to start with the latest message
        headers = message.get('payload', {}).get('headers', [])
        sender = next(
            (header['value'] for header in headers if header['name'].lower() == 'from'), ""
        )
        if "hello@shamelesscollective.com" not in sender:
            latest_recipient_message = message
            break
    return latest_recipient_message 

def classify_email_content(email_snippet):
    prompt = f"""
You are a helpful assistant. Categorize the following email into one of these categories:
1. Order Tracking
2. Returns or Exchanges
3. Complaint About Products
If the email does not match any of these categories, label it as 'Other'.

Email Content: "{email_snippet}"
Provide only the category number and name as the response.
"""
    return prompt

def classify_email_with_gpt(email_snippet):
    prompt = classify_email_content(email_snippet)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=50
    )
    
    return response.choices[0].message.content.strip()

# Function to generate responses using OpenAI API
def generate_response(customer_question):   
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": customer_question}
        ],
        max_tokens=250,
        temperature=0.7, 
    )
    assistant_response =  response.choices[0].message.content.strip()
    
    # Parse subject and body from the response
    if "subject:" in assistant_response.lower() and "body:" in assistant_response.lower():
        parts = assistant_response.split("body:", 1)
        response_subject = parts[0].replace("subject:", "").strip()
        response_body = parts[1].strip()
    elif "asunto:" in assistant_response.lower() and "cuerpo:" in assistant_response.lower():
        parts = assistant_response.split("cuerpo:", 1)
        response_subject = parts[0].replace("asunto:", "").strip()
        response_body = parts[1].strip()
    else:
        response_subject = "No subject found"
        response_body = assistant_response  # Fallback to full response if parsing fails

    # Replace markdown-style bold with HTML bold
    response_body = response_body.replace("**", "<b>").replace("**", "</b>")

    return response_subject, response_body

def get_email_body_with_attachments(service, message_id):
    message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = message.get('payload', {})

    def extract_body(payload):
        """
        Recursively extract the body content from the email payload.
        """
        if 'parts' in payload:
            for part in payload['parts']:
                # Prefer 'text/plain'
                if part.get('mimeType') == 'text/plain':
                    return base64.urlsafe_b64decode(part['body']['data']).decode("utf-8")
                # Fallback to 'text/html'
                elif part.get('mimeType') == 'text/html':
                    html_content = base64.urlsafe_b64decode(part['body']['data']).decode("utf-8")
                    # Optionally, strip HTML tags if needed
                    return html_content
                # Recursively handle nested parts
                elif 'parts' in part:
                    result = extract_body(part)
                    if result:  # Return the first valid result
                        return result
        
        # Handle cases where body is directly available
        if 'body' in payload and 'data' in payload['body']:
            return base64.urlsafe_b64decode(payload['body']['data']).decode("utf-8")
        
        return None

    email_body = extract_body(payload)
    return email_body if email_body else "Unable to fetch email body"

def send_email(service, recipient, subject, message_body,message_id):
    message = MIMEText(message_body)
    message['to'] = recipient
    message['subject'] = subject

    raw = base64.urlsafe_b64encode(message.as_string().encode()).decode()
    message = {'raw': raw}

    service.users().messages().send(userId="me", body=message).execute()
    
    print(f"Marking email {message_id} as read.")
    # Mark the email as read
    try:
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        print(f"Email {message_id} marked as read successfully.")
        print("------------------------------------------------")
    except Exception as e:
        print(f"Failed to mark email {message_id} as read. Error: {e}")
    

# Fetch unread emails
emails = get_unread_emails(service)

# Access the API key
api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(
    api_key=api_key,
    organization='org-UNgslyOscZ3JmJAuwBhIDndV',
    project='proj_kHAvk9c4EEcRDG2axjeMS5gC',
)

# Classify each email
for email in emails:
    thread_id = email['threadId']
    # Get the last message of the thread
    latest_message = get_latest_message_in_thread(service,thread_id)
    if not latest_message:
        print(f"No messages found in thread {thread_id}. Skipping.")
        continue
    message_id = latest_message['id']
    print(f"Processing message ID: {message_id}")
    print(latest_message['snippet'])
    # Get the body of the mail
    email_body = get_email_body_with_attachments(service, message_id)
    if not email_body:
        print(f"Unable to fetch body for message ID: {message_id}. Skipping.")
        continue
    # Classify email
    category = classify_email_with_gpt(email_body)
    print(category)
    if(category != 'Other'):
        # Generate a response
        response_subject, response_body = generate_response(email_body)
        # recipient = email['headers']['From']
        recipient = "sgerickee@gmail.com"
        subject = response_subject
        send_email(service, recipient, subject, response_body,message_id)