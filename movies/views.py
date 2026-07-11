import os
import requests
from django.shortcuts import render, redirect ,get_object_or_404
from .models import Movie,Genre, Language, Theater,Seat,Booking
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count, Q
from django.core.paginator import Paginator
from .tasks import send_ticket_email
import razorpay
import json
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Order, Movie, ProcessedWebhook
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

@csrf_exempt
def email_webhook(request):
    if request.method == "POST":
        data = json.loads(request.body)
        send_ticket_email(data['booking_id'], data['payment_id'])
        return HttpResponse("Email processed", status=200)
    return HttpResponse("Bad Request", status=400)

def movie_list(request):
    search_query=request.GET.get('search')
    selected_genres = request.GET.getlist('genre')
    selected_languages = request.GET.getlist('lang')
    sort_by = request.GET.get('sort', '-release_date')
    movies = Movie.objects.prefetch_related('genres', 'languages')
    movies = movies.order_by(sort_by)
    if selected_genres:
        movies = movies.filter(genres__name__in=selected_genres).distinct()     
    if selected_languages:
        movies = movies.filter(languages__name__in=selected_languages).distinct()
    if search_query:
        movies=Movie.objects.filter(name__icontains=search_query)
    active_movie_filters = Q()
    if selected_languages:
        active_movie_filters &= Q(movies__languages__name__in=selected_languages)
        
    active_genre_filters = Q()
    if selected_genres:
        active_genre_filters &= Q(movies__genres__name__in=selected_genres)
    genres_with_counts = Genre.objects.annotate(
        available_count=Count('movies', filter=active_movie_filters, distinct=True)
    )
    
    languages_with_counts = Language.objects.annotate(
        available_count=Count('movies', filter=active_genre_filters, distinct=True)
    )
    paginator = Paginator(movies, 20) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'genres': genres_with_counts,
        'languages': languages_with_counts,
        'selected_genres': selected_genres,
        'selected_languages': selected_languages,
        'current_sort': sort_by,
    }
    return render(request, 'movies/movie_list.html', context)

def theater_list(request,movie_id):
    movie = get_object_or_404(Movie,id=movie_id)
    theater=Theater.objects.filter(movie=movie)
    return render(request,'movies/theater_list.html',{'movie':movie,'theaters':theater})


@login_required(login_url='/login/')
def book_seats(request, theater_id):
    theaters = get_object_or_404(Theater, id=theater_id)
    seats = Seat.objects.filter(theater=theaters)
    if request.method == 'POST':
        selected_seats = request.POST.getlist('seats')
        error_seats = []
        if not selected_seats:
            return render(request, "movies/seat_selection.html", {'theater': theaters, "seats": seats, 'error': "No seat selected"})
        
        with transaction.atomic():
            # 1. Lock rows: select_for_update prevents anyone else from grabbing these rows
            # until this block finishes (or rolls back).
            locked_seats = Seat.objects.select_for_update().filter(id__in=selected_seats)
            
            # 2. Safety Check: If ANY of the requested seats are already booked, reject the request
            if locked_seats.filter(is_booked=True).exists():
                return render(request, "movies/seat_selection.html", {'theater': theaters, "seats": seats, 'error': "One or more seats just got booked. Please try again."})
            
            # 3. Temporary Lock: Set is_booked=True now to "reserve" them for 2 minutes
            locked_seats.update(is_booked=True)
            
            # 4. Create Order & Session data
            total_price = locked_seats.count() * 200
            seat_numbers_str = ", ".join([s.seat_number for s in locked_seats])
            
            order = Order.objects.create(
                user=request.user, movie=theaters.movie, theater=theaters,
                seat_numbers=seat_numbers_str, total_price=total_price
            )
            
            request.session['pending_seat_ids'] = selected_seats
            request.session['pending_theater_id'] = theater_id
            request.session['reservation_expiry'] = (timezone.now() + timedelta(minutes=2)).isoformat()
        return redirect('checkout', order_id=order.id)
    return render(request, 'movies/seat_selection.html', {'theaters': theaters, "seats": seats})

# Initialize Razorpay Client
razorpay_client = razorpay.Client(
    auth=(getattr(settings, 'RAZORPAY_KEY_ID', ''), getattr(settings, 'RAZORPAY_KEY_SECRET', ''))
)

def razorpay_checkout(request, order_id):
    """Step 1: Create a Razorpay Order and render the payment page"""
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)

    # Create Razorpay Order
    razorpay_order = razorpay_client.order.create({
        "amount": int(order.total_price * 100),  # Amount in paise (1 INR = 100 paise)
        "currency": "INR",
        "receipt": f"receipt_order_{order.id}",
        "payment_capture": "1" # Auto capture payment
    })

    # Save the Razorpay Order ID to our database
    order.razorpay_order_id = razorpay_order['id']
    order.save()

    context = {
        'order': order,
        'razorpay_order_id': razorpay_order['id'],
        'razorpay_merchant_key': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'razorpay_amount': int(order.total_price * 100),
        'currency': 'INR',
        'callback_url': request.build_absolute_uri('/movies/payment/verify/'),
    }
    return render(request, 'movies/razorpay_checkout.html', context)

def trigger_email_task(booking_id, payment_id):
    # Retrieve configuration from Environment Variables
    base_url = os.environ.get('QSTASH_URL')
    token = os.environ.get('QSTASH_TOKEN')
    
    # The URL where your Django app is hosted (e.g., https://your-app.vercel.app)
    app_url = "https://djnago-bookmyshow-clone-4fje-6r3rl513a-teena33.vercel.app"
    destination = f"{app_url}/email-webhook/"
    
    url = f"{base_url}/v2/publish/{destination}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "booking_id": booking_id,
        "payment_id": payment_id
    }
    
    # Triggering the task
    requests.post(url, json=payload, headers=headers)

@csrf_exempt
def razorpay_verify(request):
    if request.method == "POST":
        params = {
            'razorpay_order_id': request.POST.get('razorpay_order_id'),
            'razorpay_payment_id': request.POST.get('razorpay_payment_id'),
            'razorpay_signature': request.POST.get('razorpay_signature')
        }
        try:
            # Verify signature first
            razorpay_client.utility.verify_payment_signature(params)
            order = Order.objects.get(razorpay_order_id=params['razorpay_order_id'])
            order.payment_status = 'Paid'
            order.razorpay_payment_id = params['razorpay_payment_id']
            order.save()
            
            # Use data from the Order to book seats (more reliable than session)
            seat_names = [s.strip() for s in order.seat_numbers.split(',')]
            seats = Seat.objects.filter(seat_number__in=seat_names, theater=order.theater)
            
            for seat in seats:
                # Create the Booking record
                booking, created = Booking.objects.get_or_create(
                    seat=seat,
                    defaults={
                        'user': order.user,
                        'movie': order.movie,
                        'theater': seat.theater
                    }
                )
                if created:
                    seat.is_booked = True
                    seat.save()
                    trigger_email_task(booking.id, params['razorpay_payment_id'])
                    
            return redirect('payment_success')
        except Exception as e:
            # IMPORTANT: Print this in your terminal to see WHY it's failing
            print(f"CRITICAL FULFILLMENT ERROR: {e}")
            return redirect('payment_cancel')

@csrf_exempt
def email_webhook(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            send_ticket_email(data['booking_id'], data['payment_id'])
            return HttpResponse("Email processed", status=200)
        except Exception as e:
            return HttpResponse(str(e), status=500)
    return HttpResponse("Invalid request", status=400)

@csrf_exempt
def razorpay_webhook(request):
    """Step 3: Secure Webhook listener for background verification"""
    webhook_body = request.body.decode('utf-8')
    webhook_signature = request.headers.get('X-Razorpay-Signature')
    webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', 'placeholder_secret') 

    try:
        # Cryptographic Signature Verification
        razorpay_client.utility.verify_webhook_signature(
            webhook_body, webhook_signature, webhook_secret
        )
    except razorpay.errors.SignatureVerificationError:
        return HttpResponse(status=400) # Hacker spoofing blocked

    # Parse payload
    payload = json.loads(webhook_body)
    event_id = payload.get('id', '')
    
    # Idempotency / Replay Attack Prevention
    if ProcessedWebhook.objects.filter(event_id=event_id).exists():
        return HttpResponse(status=200) # Duplicate detected and ignored
    
    ProcessedWebhook.objects.create(event_id=event_id)

    # Process Payment Captured Event
    if payload['event'] == 'payment.captured':
        payment_entity = payload['payload']['payment']['entity']
        razorpay_order_id = payment_entity.get('order_id')
        
        try:
            order = Order.objects.get(razorpay_order_id=razorpay_order_id)
            if order.payment_status != 'Paid':
                order.payment_status = 'Paid'
                order.razorpay_payment_id = payment_entity.get('id')
                order.save()
                # TODO: Trigger Celery email fallback here
        except Order.DoesNotExist:
            pass

    return HttpResponse(status=200)

