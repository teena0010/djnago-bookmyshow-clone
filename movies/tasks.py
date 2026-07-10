import logging
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from celery import shared_task
from django.core.mail import send_mail
from .models import Order, Seat
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import Booking

logger = logging.getLogger('celery_tasks')

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def send_ticket_email(self,booking_id, payment_id):
    try:
        booking = Booking.objects.get(id=booking_id)
        
        context = {'booking': booking, 'payment_id': payment_id}
        html_content = render_to_string('emails/ticket_confirmation.html', context)
        text_content = f"Your tickets for {booking.movie.name} are confirmed."

        email = EmailMultiAlternatives(
            subject=f"Ticket Confirmation - {booking.movie.name}",
            body=text_content,
            from_email=settings.EMAIL_HOST_USER,
            to=[booking.user.email]
        )
        email.attach_alternative(html_content, "text/html")
        
        email.send(fail_silently=False)
        return f"Email sent successfully to {booking.user.email}"
    
    except Booking.DoesNotExist:
        return "Booking not found, skipping email."

    except Exception as e:
        logger.error(f"Failed to send email for booking {booking_id}. Error: {str(e)}")
        raise self.retry(exc=e)
 
@shared_task
def release_expired_reservations():
    # 1. Define the threshold variable here
    expiration_time = timezone.now() - timedelta(minutes=15)
    print(f"DEBUG: Current Time: {timezone.now()}, Expiration Limit: {expiration_time}")
    
    # DEBUG PRINT: How many orders are even marked as Pending?
    all_pending = Order.objects.filter(payment_status='Pending').count()
    print(f"DEBUG: Total 'Pending' orders in DB: {all_pending}")
    
    expired_orders = Order.objects.filter(
        payment_status='Pending', 
        created_at__lt=expiration_time
    )
    print(f"DEBUG: Found {expired_orders.count()} orders to expire.")
    count = 0
    for order in expired_orders:
        print(f"DEBUG: Processing Order ID {order.id}, Created At: {order.created_at}")
        
        # Release the seats
        seat_numbers = [s.strip() for s in order.seat_numbers.split(',')]
        seats_to_release = Seat.objects.filter(seat_number__in=seat_numbers)
        
        seats_to_release.update(is_booked=False)
        count += seats_to_release.count()
            
        order.payment_status = 'Expired'
        order.save()
        
    return f"Released {count} expired reservations."
