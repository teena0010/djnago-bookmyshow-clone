from django.urls import path
from . import views
from django.shortcuts import render
urlpatterns=[
    path('',views.movie_list,name='movie_list'),
    path('<int:movie_id>/theaters',views.theater_list,name='theater_list'),
    path('theater/<int:theater_id>/seats/book/',views.book_seats,name='book_seats'),
    path('checkout/<int:order_id>/', views.razorpay_checkout, name='checkout'),
    path('webhook/razorpay/', views.razorpay_webhook, name='razorpay_webhook'),
    path('payment/verify/', views.razorpay_verify, name='razorpay_verify'),
    path('payment-success/', lambda request: render(request, 'movies/success.html'), name='payment_success'),
    path('payment-cancel/', lambda request: render(request, 'movies/cancel.html'), name='payment_cancel'),
    path('email-webhook/', views.email_webhook, name='email-webhook'),
    path('cron/release-seats/', views.cron_release_seats),
]
