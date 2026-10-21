import smtplib


SENDER_EMAIL = 
SENDER_PASSWORD = 
RECIPIENT_EMAIL =
def send_invoice_email(recipient_email, subject, body, sender_email, sender_password):
    """
    Sends an email with the attached PDF invoice.

    Args:
        pdf_buffer (BytesIO): The PDF file in memory.
        recipient_email (str): The recipient's email address.
        subject (str): The subject of the email.
        body (str): The body text of the email.
        sender_email (str): The sender's email address.
        sender_password (str): The sender's email password.

    Returns:
        None
    """
    # Set up the email


    # Send the email
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email)
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")