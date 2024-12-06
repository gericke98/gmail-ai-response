# Gmail AI Response System

A fully automated email response system that integrates OpenAI's GPT-4 for natural language understanding and Gmail API for email management. The system reads unread emails, classifies them based on predefined categories, and sends appropriate responses tailored to each query.

---

## Features

- **Email Automation**:

  - Reads unread emails from Gmail.
  - Handles email threads to respond to the latest message.
  - Supports only unarchived emails.

- **AI-Powered Classification**:

  - Classifies emails into predefined categories:
    1. Order Tracking
    2. Returns or Exchanges
    3. Complaints About Products
    4. Other

- **Dynamic Email Responses**:

  - Generates personalized email responses using OpenAI's GPT-4.
  - Ensures responses are warm, professional, and empathetic.
  - Supports responses in the language of the customer query (English or Spanish).
  - Includes specific instructions and links for:
    - Order tracking
    - Returns and exchanges
    - Issue resolutions

- **Push Notification Integration**:
  - Uses Gmail push notifications to automatically execute when a new email is received.

---

## Technology Stack

- **Python**:
  - Core programming language.
- **Google APIs**:
  - Gmail API for email reading, sending, and thread handling.
- **OpenAI GPT-4**:
  - Natural language understanding and response generation.
- **Google Cloud**:
  - Hosting service for automated execution.
- **OAuth 2.0**:
  - Secure authentication and authorization.

---

## Project Structure
